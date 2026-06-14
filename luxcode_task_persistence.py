from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sqlite3
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


CURRENT_SCHEMA_VERSION = 2
DATABASE_NAME = "luxcode_tasks.db"
PAYLOAD_SIZE_LIMIT = 120_000
TEXT_LIMIT = 4000
STDIO_LIMIT = 1600
SUPPORTED_MODES = {"disabled", "memory_only", "local_sqlite"}
SECRET_KEY_MARKERS = (
    "api_key",
    "token",
    "secret",
    "password",
    "authorization",
    "cookie",
    "private_key",
    "access_key",
)
ACTIVE_RESTORE_STATES = {
    "created",
    "routed",
    "diagnosing",
    "diagnosis_ready",
    "patch_drafting",
    "patch_ready",
    "awaiting_approval",
    "approval_verified",
    "apply_prepared",
    "applying",
    "applied",
    "verification_prepared",
    "verifying",
    "recovery_review",
    "rollback_recommended",
    "paused",
    "blocked",
}
SAFE_INVARIANTS = {
    "external_api_used": False,
    "network_access_used": False,
    "shell_execution_used": False,
    "local_first": True,
}

_CONFIG: Dict[str, Any] = {"mode": "disabled", "storage_root": "", "privacy_mode": True}
_MEMORY_RECORDS: Dict[str, Dict[str, Any]] = {}
_MEMORY_EVENTS: Dict[str, List[Dict[str, Any]]] = {}


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        result = super().__exit__(exc_type, exc, tb)
        self.close()
        return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_payload(payload: Dict[str, Any]) -> str:
    return _sha256_text(_canonical_json(payload))


def _repository_hash(repository_root: str) -> str:
    return _sha256_text(str(repository_root).replace("\\", "/"))[:32]


def _approval_token(task_id: str) -> str:
    return f"DELETE:{task_id}:PERMANENT"


def _safe_failure(message: str, **extra: Any) -> Dict[str, Any]:
    return {"ok": False, "error": message, **extra, **SAFE_INVARIANTS}


def _safe_success(**extra: Any) -> Dict[str, Any]:
    return {"ok": True, **extra, **SAFE_INVARIANTS}


def _unsupported(value: Any) -> bool:
    return not isinstance(value, (dict, list, str, int, float, bool, type(None)))


def _secretish_string(value: str) -> bool:
    if re.search(r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}", value):
        return True
    if re.search(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{12,}", value):
        return True
    if re.search(r"(^|[^A-Za-z0-9])sk-[A-Za-z0-9]{16,}", value):
        return True
    return False


def _looks_like_full_file(value: str) -> bool:
    line_count = value.count("\n")
    return line_count > 120 or ("-----BEGIN " in value and "PRIVATE KEY" in value)


def _sanitize_text(key: str, value: str) -> str:
    lowered = key.lower()
    if lowered in {"env", "env_blob", "dotenv"} or lowered.startswith(".env"):
        return "[redacted-env]"
    if ".env" in value and ("=" in value or _secretish_string(value)):
        return "[redacted-env]"
    if _secretish_string(value):
        return "[redacted-secret]"
    if _looks_like_full_file(value):
        return "[redacted-large-file-content]"
    limit = STDIO_LIMIT if lowered in {"stdout", "stderr", "traceback", "output"} else TEXT_LIMIT
    text = value.replace("\x00", "")
    if len(text) > limit:
        return text[:limit] + "...[truncated]"
    return text


def sanitize_task_payload(value: Any, key: str = "root", depth: int = 0) -> Any:
    if depth > 12:
        raise ValueError("payload nesting too deep")
    if isinstance(value, bytes):
        raise ValueError("binary data is not supported")
    if _unsupported(value):
        raise ValueError(f"unsupported value type for {key}")
    lowered = key.lower()
    if any(marker in lowered for marker in SECRET_KEY_MARKERS):
        return "[redacted]"
    if isinstance(value, dict):
        clean: Dict[str, Any] = {}
        for item_key, item_value in value.items():
            clean[str(item_key)] = sanitize_task_payload(item_value, str(item_key), depth + 1)
        return clean
    if isinstance(value, list):
        return [sanitize_task_payload(item, key, depth + 1) for item in value[:200]]
    if isinstance(value, str):
        return _sanitize_text(key, value)
    return value


def _safe_payload(task_state: Dict[str, Any], privacy_mode: bool = True) -> Dict[str, Any]:
    raw_encoded = json.dumps(task_state, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=lambda _item: "__unsupported__")
    if len(raw_encoded.encode("utf-8")) > PAYLOAD_SIZE_LIMIT:
        raise ValueError("payload size budget exceeded")
    original_task_id = str(task_state.get("task_id") or "")
    original_state = str(task_state.get("current_state") or "created")
    payload = sanitize_task_payload(deepcopy(task_state))
    if not isinstance(payload, dict):
        raise ValueError("task payload must be an object")
    payload["task_id"] = original_task_id
    payload["current_state"] = original_state
    task_id = str(payload.get("task_id") or "")
    if not task_id:
        raise ValueError("task_id is required")
    repository_root = str(payload.get("repository_root") or "")
    payload["repository_root_hash"] = _repository_hash(repository_root)
    payload["repository_root_display"] = Path(repository_root).name if repository_root else ""
    if privacy_mode:
        payload["repository_root"] = payload["repository_root_hash"]
    for blocked_key in ("controlled_apply_approval_token", "verification_approval_token", "approval_token"):
        if blocked_key in _canonical_json(payload):
            payload = sanitize_task_payload(payload)
            break
    encoded = _canonical_json(payload)
    if len(encoded.encode("utf-8")) > PAYLOAD_SIZE_LIMIT:
        raise ValueError("payload size budget exceeded")
    return payload


def _validate_storage_root(storage_root: Optional[str]) -> Tuple[bool, str, str]:
    if not storage_root:
        return False, "", "explicit storage_root is required"
    try:
        root = Path(storage_root).expanduser().resolve()
        cwd = Path.cwd().resolve()
    except (OSError, ValueError) as exc:
        return False, "", f"invalid storage_root: {exc}"
    root_text = str(root).lower()
    if root == cwd or cwd in root.parents:
        return False, str(root), "repository-root storage is blocked"
    if ".env" in root_text:
        return False, str(root), ".env storage path is blocked"
    if any(part == ".." for part in Path(storage_root).parts):
        return False, str(root), "path traversal storage root is blocked"
    return True, str(root), ""


def _db_path(storage_root: str) -> Path:
    return Path(storage_root) / DATABASE_NAME


def _connect(storage_root: str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path(storage_root)), timeout=0.35, factory=_ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=350")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        pass
    return conn


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            schema_version INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS task_records (
            task_id TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            current_state TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived_at TEXT,
            repository_root_hash TEXT NOT NULL,
            task_payload_json TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            is_archived INTEGER NOT NULL DEFAULT 0,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            revision INTEGER NOT NULL,
            last_event_id INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS task_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            previous_state TEXT,
            new_state TEXT,
            created_at TEXT NOT NULL,
            event_payload_json TEXT NOT NULL,
            event_sha256 TEXT NOT NULL
        )
        """
    )
    row = conn.execute("SELECT schema_version FROM schema_meta LIMIT 1").fetchone()
    now = _now()
    if row is None:
        conn.execute(
            "INSERT INTO schema_meta(schema_version, created_at, updated_at) VALUES (?, ?, ?)",
            (CURRENT_SCHEMA_VERSION, now, now),
        )
    elif int(row["schema_version"]) < CURRENT_SCHEMA_VERSION:
        conn.execute("UPDATE schema_meta SET schema_version = ?, updated_at = ?", (CURRENT_SCHEMA_VERSION, now))


def _check_schema(conn: sqlite3.Connection) -> Tuple[bool, str]:
    try:
        row = conn.execute("SELECT schema_version FROM schema_meta LIMIT 1").fetchone()
    except sqlite3.DatabaseError as exc:
        return False, f"schema metadata unavailable: {exc}"
    if row is None:
        return False, "schema metadata missing"
    try:
        version = int(row["schema_version"])
    except (TypeError, ValueError):
        return False, "schema metadata corrupted"
    if version > CURRENT_SCHEMA_VERSION:
        return False, "incompatible newer schema version blocked"
    if version < 1:
        return False, "schema metadata corrupted"
    return True, ""


def _with_retry(operation):
    last_error: Optional[Exception] = None
    for attempt in range(3):
        try:
            return operation(attempt)
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                raise
            last_error = exc
            time.sleep(0.025 * (attempt + 1))
    raise sqlite3.OperationalError(f"database lock not acquired after bounded retry: {last_error}")


def get_task_persistence_schema() -> Dict[str, Any]:
    return {
        "name": "LuxCode Local Task Persistence & Continuity Adapter",
        "schema_version": CURRENT_SCHEMA_VERSION,
        "default_mode": "disabled",
        "supported_modes": sorted(SUPPORTED_MODES),
        "database_name": DATABASE_NAME,
        "tables": ["task_records", "task_events", "schema_meta"],
        "public_functions": [
            "get_task_persistence_schema",
            "initialize_task_store",
            "save_task_state",
            "load_task_state",
            "list_task_states",
            "archive_task_state",
            "delete_task_state",
            "restore_active_tasks",
            "get_task_persistence_status",
        ],
        "hard_delete_requires": ["hard_delete=true", "exact task_id", "approval token", "confirmation phrase"],
        "payload_size_limit": PAYLOAD_SIZE_LIMIT,
        "safe_permission_metadata": [
            "permission_mode",
            "scope_items",
            "per_item_rights",
            "operation_authority",
            "permission_duration",
            "project_identifier_hash",
            "risk_policy",
            "autonomy_budgets",
            "revocation_state",
            "revision",
            "integrity_hash",
        ],
        "permission_restore_policy": "restored permissions never expand scope automatically",
        "safe_process_metadata": [
            "runtime_id",
            "task_id",
            "action_type",
            "executable",
            "normalized_args",
            "cwd",
            "pid",
            "exit_code",
            "timeout",
            "status",
            "health_result",
            "cleanup_result",
            "redacted_stdout_stderr_summary",
            "audit_events",
            "ownership",
        ],
        "process_restore_policy": "restored process records never auto-start execution",
        "safe_live_test_metadata": [
            "scenario_id",
            "live_test_runtime_id",
            "lifecycle_state",
            "current_step",
            "completed_steps",
            "redacted_result_summary",
            "evidence_metadata",
            "browser_ownership_metadata",
            "cleanup_state",
            "restore_policy",
            "audit_events",
        ],
        "live_test_restore_policy": "restored live test records never auto-start browser service or scenario execution",
        "safe_network_access_metadata": [
            "network_access_runtime_id",
            "task_id",
            "state",
            "selected_interface",
            "selected_lan_ip",
            "bind_host",
            "bind_port",
            "generated_urls",
            "physical_device_status",
            "cleanup_state",
            "audit_event_count",
        ],
        "network_access_restore_policy": "restored network access records never auto-start services, browsers, or LAN checks",
        "safe_test_matrix_metadata": [
            "matrix_plan_digest",
            "requested_targets",
            "available_targets",
            "skipped_targets",
            "summary_counts",
            "failure_categories",
            "scenario_ids",
            "viewport_device_metadata",
            "network_profile_names",
            "timestamps",
            "task_id",
            "result_revision",
        ],
        "safe_browser_launch_metadata": [
            "requested_family",
            "selected_family",
            "exact_match",
            "fallback_used",
            "executable_basename",
            "executable_digest",
            "version",
            "identity_verified",
            "failure_category",
            "timestamps",
        ],
        "safe_deployment_metadata": [
            "deployment_runtime_id",
            "deployment_plan_id",
            "provider",
            "build_state",
            "deployment_state",
            "url_verification_state",
            "scenario_state",
            "rollback_state",
            "failure_category",
            "cleanup_state",
            "audit_event_count",
        ],
        "test_matrix_restore_policy": "restored test matrix records never auto-start browsers, services, emulators, or network checks",
        "deployment_restore_policy": "restored deployment records never auto-build, auto-deploy, auto-probe URLs, or auto-rollback",
        "persistence_disabled_by_default": True,
        **SAFE_INVARIANTS,
    }


def initialize_task_store(
    mode: str = "disabled",
    storage_root: Optional[str] = None,
    privacy_mode: bool = True,
    create: bool = True,
) -> Dict[str, Any]:
    if mode not in SUPPORTED_MODES:
        return _safe_failure("unsupported persistence mode")
    _CONFIG.update({"mode": mode, "storage_root": storage_root or "", "privacy_mode": bool(privacy_mode)})
    if mode == "disabled":
        return _safe_success(mode=mode, durable=False, created=False)
    if mode == "memory_only":
        return _safe_success(mode=mode, durable=False, created=False, record_count=len(_MEMORY_RECORDS))
    ok, root, error = _validate_storage_root(storage_root)
    if not ok:
        return _safe_failure(error, storage_root=root)
    if create:
        Path(root).mkdir(parents=True, exist_ok=True)
    if not Path(root).exists():
        return _safe_failure("storage_root does not exist", storage_root=root)
    try:
        with _connect(root) as conn:
            conn.execute("BEGIN")
            _create_schema(conn)
            conn.commit()
            wal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        return _safe_success(
            mode=mode,
            durable=True,
            storage_root=root,
            database_path=str(_db_path(root)),
            schema_version=CURRENT_SCHEMA_VERSION,
            journal_mode=str(wal_mode).lower(),
            busy_timeout_ms=int(busy_timeout),
        )
    except sqlite3.Error as exc:
        return _safe_failure(f"sqlite initialization failed: {exc}", storage_root=root)


def _resolve_mode(mode: Optional[str], storage_root: Optional[str]) -> Tuple[str, str, bool]:
    resolved_mode = mode or _CONFIG.get("mode", "disabled")
    resolved_root = storage_root or _CONFIG.get("storage_root", "")
    privacy_mode = bool(_CONFIG.get("privacy_mode", True))
    return resolved_mode, resolved_root, privacy_mode


def save_task_state(
    task_state: Dict[str, Any],
    expected_revision: Optional[int] = None,
    mode: Optional[str] = None,
    storage_root: Optional[str] = None,
    event_type: str = "save",
    previous_state: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_mode, resolved_root, privacy_mode = _resolve_mode(mode, storage_root)
    if resolved_mode == "disabled":
        return _safe_success(mode="disabled", durable=False, saved=False, reason="persistence disabled")
    try:
        payload = _safe_payload(task_state, privacy_mode=privacy_mode)
    except ValueError as exc:
        return _safe_failure(str(exc))
    task_id = str(payload["task_id"])
    current_state = str(payload.get("current_state") or "created")
    repository_root_hash = str(payload.get("repository_root_hash") or "")
    now = _now()
    if resolved_mode == "memory_only":
        current = _MEMORY_RECORDS.get(task_id)
        current_revision = int(current.get("revision", 0)) if current else 0
        if expected_revision is not None and expected_revision != current_revision:
            return _safe_failure("stale revision overwrite blocked", current_revision=current_revision)
        revision = current_revision + 1
        payload["revision"] = revision
        digest = _hash_payload(payload)
        event = {"event_id": len(_MEMORY_EVENTS.get(task_id, [])) + 1, "event_type": event_type, "new_state": current_state}
        _MEMORY_EVENTS.setdefault(task_id, []).append(event)
        _MEMORY_RECORDS[task_id] = {
            "task_id": task_id,
            "schema_version": CURRENT_SCHEMA_VERSION,
            "current_state": current_state,
            "created_at": current.get("created_at", now) if current else now,
            "updated_at": now,
            "archived_at": current.get("archived_at") if current else None,
            "repository_root_hash": repository_root_hash,
            "task_payload_json": _canonical_json(payload),
            "payload_sha256": digest,
            "is_archived": int(current.get("is_archived", 0)) if current else 0,
            "is_deleted": int(current.get("is_deleted", 0)) if current else 0,
            "revision": revision,
            "last_event_id": event["event_id"],
        }
        return _safe_success(task_id=task_id, revision=revision, payload_sha256=digest, durable=False)
    ok, root, error = _validate_storage_root(resolved_root)
    if not ok:
        return _safe_failure(error, storage_root=root)
    def operation(_attempt: int) -> Dict[str, Any]:
        with _connect(root) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                schema_ok, schema_error = _check_schema(conn)
                if not schema_ok:
                    conn.rollback()
                    return _safe_failure(schema_error)
                row = conn.execute(
                    "SELECT revision, created_at, is_archived, is_deleted, archived_at, current_state FROM task_records WHERE task_id = ?",
                    (task_id,),
                ).fetchone()
                current_revision = int(row["revision"]) if row else 0
                if expected_revision is not None and expected_revision != current_revision:
                    conn.rollback()
                    return _safe_failure("stale revision overwrite blocked", current_revision=current_revision)
                revision = current_revision + 1
                payload["revision"] = revision
                digest = _hash_payload(payload)
                payload_json = _canonical_json(payload)
                event_payload = {"task_id": task_id, "revision": revision, "event_type": event_type, "state": current_state}
                event_json = _canonical_json(event_payload)
                event_hash = _hash_payload(event_payload)
                conn.execute(
                    """
                    INSERT INTO task_records(
                        task_id, schema_version, current_state, created_at, updated_at, archived_at,
                        repository_root_hash, task_payload_json, payload_sha256, is_archived, is_deleted, revision, last_event_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    ON CONFLICT(task_id) DO UPDATE SET
                        schema_version=excluded.schema_version,
                        current_state=excluded.current_state,
                        updated_at=excluded.updated_at,
                        repository_root_hash=excluded.repository_root_hash,
                        task_payload_json=excluded.task_payload_json,
                        payload_sha256=excluded.payload_sha256,
                        revision=excluded.revision
                    """,
                    (
                        task_id,
                        CURRENT_SCHEMA_VERSION,
                        current_state,
                        row["created_at"] if row else now,
                        now,
                        row["archived_at"] if row else None,
                        repository_root_hash,
                        payload_json,
                        digest,
                        int(row["is_archived"]) if row else 0,
                        int(row["is_deleted"]) if row else 0,
                        revision,
                    ),
                )
                cursor = conn.execute(
                    """
                    INSERT INTO task_events(task_id, event_type, previous_state, new_state, created_at, event_payload_json, event_sha256)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (task_id, event_type, previous_state or (row["current_state"] if row else None), current_state, now, event_json, event_hash),
                )
                event_id = int(cursor.lastrowid)
                conn.execute("UPDATE task_records SET last_event_id = ? WHERE task_id = ?", (event_id, task_id))
                conn.commit()
                return _safe_success(task_id=task_id, revision=revision, event_id=event_id, payload_sha256=digest, durable=True)
            except Exception:
                conn.rollback()
                raise
    try:
        return _with_retry(operation)
    except sqlite3.Error as exc:
        return _safe_failure(f"sqlite save failed: {exc}")


def _decode_record(row: Any) -> Dict[str, Any]:
    payload_json = row["task_payload_json"]
    expected_hash = row["payload_sha256"]
    payload = json.loads(payload_json)
    if _hash_payload(payload) != expected_hash:
        raise ValueError("payload hash mismatch")
    if int(row["schema_version"]) > CURRENT_SCHEMA_VERSION:
        raise ValueError("incompatible newer record schema blocked")
    if int(row["schema_version"]) == 1 and CURRENT_SCHEMA_VERSION > 1:
        payload["migrated_from_schema_version"] = 1
        payload.setdefault("revision", int(row["revision"]))
    payload["revision"] = int(row["revision"])
    return payload


def load_task_state(task_id: str, mode: Optional[str] = None, storage_root: Optional[str] = None, include_deleted: bool = False) -> Dict[str, Any]:
    resolved_mode, resolved_root, _privacy_mode = _resolve_mode(mode, storage_root)
    if not task_id:
        return _safe_failure("exact task_id is required")
    if resolved_mode == "disabled":
        return _safe_success(mode="disabled", found=False, durable=False)
    if resolved_mode == "memory_only":
        row = _MEMORY_RECORDS.get(task_id)
        if not row or (row.get("is_deleted") and not include_deleted):
            return _safe_success(found=False, durable=False)
        try:
            return _safe_success(found=True, task=_decode_record(row), durable=False)
        except Exception as exc:
            return _safe_failure(f"corrupted payload blocked: {exc}")
    ok, root, error = _validate_storage_root(resolved_root)
    if not ok:
        return _safe_failure(error, storage_root=root)
    try:
        with _connect(root) as conn:
            schema_ok, schema_error = _check_schema(conn)
            if not schema_ok:
                return _safe_failure(schema_error)
            row = conn.execute("SELECT * FROM task_records WHERE task_id = ?", (task_id,)).fetchone()
            if row is None or (int(row["is_deleted"]) and not include_deleted):
                return _safe_success(found=False, durable=True)
            return _safe_success(found=True, task=_decode_record(row), durable=True)
    except Exception as exc:
        return _safe_failure(f"corrupted payload blocked: {exc}")


def _verify_events(conn: sqlite3.Connection, task_id: str) -> Tuple[bool, str]:
    rows = conn.execute("SELECT event_payload_json, event_sha256 FROM task_events WHERE task_id = ?", (task_id,)).fetchall()
    for row in rows:
        payload = json.loads(row["event_payload_json"])
        if _hash_payload(payload) != row["event_sha256"]:
            return False, "event hash mismatch"
    return True, ""


def list_task_states(
    mode: Optional[str] = None,
    storage_root: Optional[str] = None,
    include_archived: bool = False,
    include_deleted: bool = False,
    state: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    resolved_mode, resolved_root, _privacy_mode = _resolve_mode(mode, storage_root)
    limit = max(1, min(int(limit or 50), 100))
    offset = max(0, int(offset or 0))
    if resolved_mode == "disabled":
        return _safe_success(tasks=[], count=0, durable=False)
    if resolved_mode == "memory_only":
        rows = list(_MEMORY_RECORDS.values())
        tasks = []
        for row in rows:
            if row.get("is_deleted") and not include_deleted:
                continue
            if row.get("is_archived") and not include_archived:
                continue
            if state and row.get("current_state") != state:
                continue
            tasks.append(_decode_record(row))
        tasks.sort(key=lambda item: (item.get("updated_at", ""), item.get("task_id", "")))
        return _safe_success(tasks=tasks[offset : offset + limit], count=len(tasks), durable=False)
    ok, root, error = _validate_storage_root(resolved_root)
    if not ok:
        return _safe_failure(error, storage_root=root)
    clauses = []
    params: List[Any] = []
    if not include_archived:
        clauses.append("is_archived = 0")
    if not include_deleted:
        clauses.append("is_deleted = 0")
    if state:
        clauses.append("current_state = ?")
        params.append(state)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    try:
        with _connect(root) as conn:
            schema_ok, schema_error = _check_schema(conn)
            if not schema_ok:
                return _safe_failure(schema_error)
            rows = conn.execute(f"SELECT * FROM task_records{where} ORDER BY updated_at ASC, task_id ASC LIMIT ? OFFSET ?", (*params, limit, offset)).fetchall()
            tasks = [_decode_record(row) for row in rows]
            return _safe_success(tasks=tasks, count=len(tasks), durable=True)
    except Exception as exc:
        return _safe_failure(f"list failed: {exc}")


def archive_task_state(task_id: str, mode: Optional[str] = None, storage_root: Optional[str] = None, expected_revision: Optional[int] = None) -> Dict[str, Any]:
    if not task_id:
        return _safe_failure("exact task_id is required")
    resolved_mode, resolved_root, _privacy_mode = _resolve_mode(mode, storage_root)
    now = _now()
    if resolved_mode == "disabled":
        return _safe_success(mode="disabled", archived=False, durable=False)
    if resolved_mode == "memory_only":
        row = _MEMORY_RECORDS.get(task_id)
        if not row:
            return _safe_success(found=False, archived=False, durable=False)
        if expected_revision is not None and expected_revision != int(row["revision"]):
            return _safe_failure("stale revision overwrite blocked", current_revision=int(row["revision"]))
        row["is_archived"] = 1
        row["archived_at"] = now
        return _safe_success(found=True, archived=True, durable=False)
    ok, root, error = _validate_storage_root(resolved_root)
    if not ok:
        return _safe_failure(error, storage_root=root)
    try:
        with _connect(root) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT revision FROM task_records WHERE task_id = ?", (task_id,)).fetchone()
            if not row:
                conn.commit()
                return _safe_success(found=False, archived=False, durable=True)
            if expected_revision is not None and expected_revision != int(row["revision"]):
                conn.rollback()
                return _safe_failure("stale revision overwrite blocked", current_revision=int(row["revision"]))
            conn.execute("UPDATE task_records SET is_archived = 1, archived_at = ?, updated_at = ? WHERE task_id = ?", (now, now, task_id))
            conn.commit()
        return _safe_success(found=True, archived=True, durable=True)
    except sqlite3.Error as exc:
        return _safe_failure(f"archive failed: {exc}")


def delete_task_state(
    task_id: str,
    mode: Optional[str] = None,
    storage_root: Optional[str] = None,
    hard_delete: bool = False,
    approval_token: str = "",
    confirmation_phrase: str = "",
) -> Dict[str, Any]:
    if not task_id:
        return _safe_failure("exact task_id is required")
    if hard_delete and (approval_token != _approval_token(task_id) or confirmation_phrase != "delete task permanently"):
        return _safe_failure("hard-delete confirmation enforced", approval_token_required=_approval_token(task_id))
    resolved_mode, resolved_root, _privacy_mode = _resolve_mode(mode, storage_root)
    if resolved_mode == "disabled":
        return _safe_success(mode="disabled", deleted=False, durable=False)
    if resolved_mode == "memory_only":
        if hard_delete:
            _MEMORY_RECORDS.pop(task_id, None)
            _MEMORY_EVENTS.pop(task_id, None)
            return _safe_success(deleted=True, hard_deleted=True, durable=False)
        row = _MEMORY_RECORDS.get(task_id)
        if row:
            row["is_deleted"] = 1
        return _safe_success(deleted=bool(row), hard_deleted=False, durable=False)
    ok, root, error = _validate_storage_root(resolved_root)
    if not ok:
        return _safe_failure(error, storage_root=root)
    try:
        with _connect(root) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if hard_delete:
                conn.execute("DELETE FROM task_events WHERE task_id = ?", (task_id,))
                conn.execute("DELETE FROM task_records WHERE task_id = ?", (task_id,))
                conn.commit()
                return _safe_success(deleted=True, hard_deleted=True, durable=True)
            cursor = conn.execute("UPDATE task_records SET is_deleted = 1, updated_at = ? WHERE task_id = ?", (_now(), task_id))
            conn.commit()
            return _safe_success(deleted=cursor.rowcount > 0, hard_deleted=False, durable=True)
    except sqlite3.Error as exc:
        return _safe_failure(f"delete failed: {exc}")


def restore_active_tasks(mode: Optional[str] = None, storage_root: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    result = list_task_states(mode=mode, storage_root=storage_root, include_archived=False, include_deleted=False, limit=limit)
    if not result.get("ok"):
        return result
    restored = []
    for task in result.get("tasks", []):
        if task.get("current_state") in ACTIVE_RESTORE_STATES:
            item = deepcopy(task)
            item["requires_explicit_resume"] = True
            item["execution_triggered"] = False
            item["next_safe_action"] = item.get("next_safe_action") or "Review restored task and explicitly resume."
            restored.append(item)
    restored.sort(key=lambda item: str(item.get("task_id", "")))
    return _safe_success(restored_tasks=restored, restored_count=len(restored), execution_triggered=False)


def verify_task_events(task_id: str, mode: Optional[str] = None, storage_root: Optional[str] = None) -> Dict[str, Any]:
    resolved_mode, resolved_root, _privacy_mode = _resolve_mode(mode, storage_root)
    if resolved_mode == "memory_only":
        return _safe_success(verified=True, event_count=len(_MEMORY_EVENTS.get(task_id, [])), durable=False)
    ok, root, error = _validate_storage_root(resolved_root)
    if not ok:
        return _safe_failure(error, storage_root=root)
    try:
        with _connect(root) as conn:
            ok_events, event_error = _verify_events(conn, task_id)
            if not ok_events:
                return _safe_failure(event_error)
            count = conn.execute("SELECT COUNT(*) FROM task_events WHERE task_id = ?", (task_id,)).fetchone()[0]
            return _safe_success(verified=True, event_count=int(count), durable=True)
    except Exception as exc:
        return _safe_failure(f"event verification failed: {exc}")


def get_task_persistence_status(mode: Optional[str] = None, storage_root: Optional[str] = None) -> Dict[str, Any]:
    resolved_mode, resolved_root, _privacy_mode = _resolve_mode(mode, storage_root)
    status = {
        "name": "LuxCode Local Task Persistence & Continuity Adapter",
        "status": "disabled" if resolved_mode == "disabled" else "ready",
        "mode": resolved_mode,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "persistence_disabled_by_default": True,
        "bulk_delete_available": False,
        "hard_delete_approval_shape": _approval_token("{task_id}"),
        "safe_permission_metadata_supported": True,
        "permission_restore_expands_scope": False,
        "safe_process_metadata_supported": True,
        "process_restore_auto_starts": False,
        "safe_live_test_metadata_supported": True,
        "live_test_restore_auto_starts": False,
        "safe_network_access_metadata_supported": True,
        "network_access_restore_auto_starts": False,
        "safe_test_matrix_metadata_supported": True,
        "safe_browser_launch_metadata_supported": True,
        "safe_deployment_metadata_supported": True,
        "test_matrix_restore_auto_starts": False,
        "deployment_restore_auto_starts": False,
        "deployment_restore_auto_probes": False,
        "deployment_restore_auto_rollbacks": False,
        **SAFE_INVARIANTS,
    }
    if resolved_mode == "local_sqlite" and resolved_root:
        ok, root, error = _validate_storage_root(resolved_root)
        status.update({"storage_root_valid": ok, "storage_root_error": error, "database_exists": _db_path(root).exists() if root else False})
    return status
