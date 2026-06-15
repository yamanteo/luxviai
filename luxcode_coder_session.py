from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SESSION_STATES = [
    "created",
    "intake_complete",
    "analysis_complete",
    "context_ready",
    "plan_ready",
    "patch_preview_ready",
    "approval_required",
    "patch_applied",
    "validation_complete",
    "rolled_back",
    "completed",
    "blocked",
    "failed",
    "closed",
]


SECRET_MARKERS = ("api_key", "api-key", "token", "secret", "password", "credential", "authorization", "private_key")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any, prefix: str = "coder-session") -> str:
    return f"{prefix}-{hashlib.sha256(_stable_json(value).encode('utf-8')).hexdigest()[:24]}"


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in SECRET_MARKERS):
            return "[redacted-secret]"
        if "secret" in lowered and "=" in value:
            return "[redacted-secret-value]"
        return value
    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in SECRET_MARKERS):
                continue
            result[key] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value[:60]]
    return value


def _normalize_list(values: Any, *, limit: int = 80) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        items = [values]
    elif isinstance(values, (list, tuple, set)):
        items = list(values)
    else:
        items = [values]
    out: List[str] = []
    seen = set()
    for item in items:
        text = str(item).replace("\\", "/").strip()
        if text and text not in seen:
            out.append(text)
            seen.add(text)
        if len(out) >= limit:
            break
    return out


def _normalize_path(path_text: Any) -> str:
    return str(path_text or "").replace("\\", "/").strip().lstrip("/")


def get_coder_session_schema() -> Dict[str, Any]:
    return {
        "name": "LuxCode Coder Operator Session",
        "status": "local_first",
        "supported_states": SESSION_STATES,
        "state_transitions": [
            "created->intake_complete",
            "intake_complete->analysis_complete",
            "analysis_complete->context_ready",
            "context_ready->plan_ready",
            "plan_ready->patch_preview_ready",
            "patch_preview_ready->approval_required",
            "approval_required->patch_applied",
            "patch_applied->validation_complete",
            "validation_complete->completed",
            "validation_complete->rolled_back",
            "any->blocked",
            "any->failed",
            "any->closed",
        ],
        "external_api_used": False,
        "network_access_used": False,
        "secret_redaction": True,
        "artifact_path_template": ".luxcode_runtime/coder_sessions/<session_id>/",
    }


def _safe_repo_root(repository_root: str) -> Path:
    root = Path(repository_root or "").expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError("repository root not found")
    return root


def get_coder_session_output_root(repository_root: str, session_id: str) -> Path:
    root = _safe_repo_root(repository_root)
    return root / ".luxcode_runtime" / "coder_sessions" / _normalize_path(session_id)


def create_coder_session(
    repository_root: str,
    task_summary: str = "",
    permission_mode: str = "approval_required",
    risk_level: str = "normal",
    max_context_bytes: int = 32000,
    max_file_bytes: int = 250000,
    allowed_files: Optional[List[str]] = None,
    protected_files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    root = _safe_repo_root(repository_root)
    session_id = _digest({"root": str(root), "task": str(task_summary), "created": _now()}, prefix="coder-session")
    now = _now()
    session = {
        "session_id": session_id,
        "repository_root": str(root),
        "repository_head": "",
        "task_summary": _redact(task_summary)[:2000],
        "permission_mode": permission_mode,
        "risk_level": risk_level,
        "created_at": now,
        "updated_at": now,
        "session_state": "created",
        "intake_id": "",
        "search_ids": [],
        "context_package_ids": [],
        "plan_ids": [],
        "patch_ids": [],
        "execution_ids": [],
        "validation_ids": [],
        "snapshot_ids": [],
        "evidence_ids": [],
        "completed_scope": [],
        "remaining_gap": [],
        "last_command": "",
        "last_result_digest": "",
        "max_context_bytes": max(1024, int(max_context_bytes or 32000)),
        "max_file_bytes": max(4096, int(max_file_bytes or 250000)),
        "allowed_files": _normalize_list(allowed_files),
        "protected_files": _normalize_list(protected_files),
        "repository_head": "",
        "local_first": True,
        "external_api_used": False,
        "network_access_used": False,
        "read_only_default": True,
    }
    return build_coder_session_manifest(session)


def build_coder_session_digest(session: Dict[str, Any]) -> str:
    return _digest(session, prefix="coder-session-state")


def build_coder_session_manifest(session: Dict[str, Any]) -> Dict[str, Any]:
    now = _now()
    session = dict(session)
    session.setdefault("updated_at", now)
    session["session_digest"] = build_coder_session_digest(session)
    return _redact(session)


def safe_coder_session_payload(session: Dict[str, Any]) -> Dict[str, Any]:
    raw = dict(session)
    safe = _redact(raw)
    for key in ("task_summary", "session_state"):
        if key in safe:
            safe[key] = str(safe[key])[:2000]
    safe["safe_session_payload"] = True
    return safe


def save_session_manifest(session: Dict[str, Any], path: Path, *, allow_empty: bool = False) -> Dict[str, Any]:
    payload = build_coder_session_manifest(session)
    if payload.get("session_state") == "closed" and not allow_empty:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(payload), encoding="utf-8")
    return payload


def load_coder_session(session_id: str, repository_root: str) -> Dict[str, Any]:
    root = _safe_repo_root(repository_root)
    manifest = get_coder_session_output_root(str(root), session_id) / "session.json"
    if not manifest.exists():
        return {"ok": False, "error": "session manifest not found", "session_id": session_id}
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"session manifest parse error: {exc}", "session_id": session_id}
    return {"ok": True, "session": payload}


def update_coder_session_state(session: Dict[str, Any], state: str, *, command: str = "") -> Dict[str, Any]:
    if state not in SESSION_STATES:
        return {"ok": False, "error": f"invalid state: {state}", "session": session}
    session["session_state"] = state
    session["updated_at"] = _now()
    if command:
        session["last_command"] = command
    session["last_result_digest"] = build_coder_session_digest(session)
    return {"ok": True, "session": session}


def append_coder_scope(session: Dict[str, Any], *, completed_scope: Optional[List[str]] = None, remaining_gap: Optional[List[str]] = None) -> Dict[str, Any]:
    completed = _normalize_list(session.get("completed_scope", []), limit=200)
    remaining = _normalize_list(session.get("remaining_gap", []), limit=200)
    completed.extend(_normalize_list(completed_scope))
    remaining = [item for item in remaining if item not in session.get("completed_scope", [])]
    remaining.extend(_normalize_list(remaining_gap))
    # de-dup
    seen = set()
    session["completed_scope"] = []
    for item in completed:
        if item not in seen:
            session["completed_scope"].append(item)
            seen.add(item)
    seen = set()
    session["remaining_gap"] = []
    for item in remaining:
        if item not in seen:
            session["remaining_gap"].append(item)
            seen.add(item)
    session["updated_at"] = _now()
    return session


def record_coder_step(
    session: Dict[str, Any],
    *,
    step_type: str,
    command: str,
    result: Dict[str, Any],
    step_digest: Optional[str] = None,
) -> str:
    history = list(session.get("evidence_ids", []))
    digest = step_digest or _digest({"step": step_type, "command": command, "result": result}, prefix="coder-session-step")
    entry = {
        "step_id": digest,
        "step_type": step_type,
        "command": command,
        "result_digest": _digest(result, prefix="coder-session-result"),
        "result_ok": bool(result.get("ok") is not False),
        "created_at": _now(),
    }
    if not history:
        history = []
    # keep short history
    if len(history) >= 200:
        del history[0 : len(history) - 199]
    history.append(digest)
    session["evidence_ids"] = history
    session["last_result_digest"] = _digest(result, prefix="coder-session-result")
    session["updated_at"] = _now()
    return digest


def append_coder_step(
    session: Dict[str, Any],
    step_type: str,
    command: str,
    result: Dict[str, Any],
    step_digest: Optional[str] = None,
) -> str:
    return record_coder_step(session, step_type=step_type, command=command, result=result, step_digest=step_digest)


def _is_state_file_present(repository_root: str, session_id: str) -> bool:
    root = _safe_repo_root(repository_root)
    return (root / ".luxcode_runtime" / "coder_sessions" / _normalize_path(session_id) / "session.json").exists()


def session_output_files(session_root: Path) -> Dict[str, str]:
    return {
        "session": str(session_root / "session.json"),
        "status": str(session_root / "status.json"),
        "intake": str(session_root / "intake_result.json"),
        "search": str(session_root / "search_result.json"),
        "context": str(session_root / "context_manifest.json"),
        "plan": str(session_root / "coder_plan.json"),
        "patch_preview": str(session_root / "patch_preview.json"),
        "validation": str(session_root / "validation_result.json"),
        "rollback": str(session_root / "rollback_result.json"),
        "run": str(session_root / "run_manifest.json"),
    }


def build_run_manifest(
    session: Dict[str, Any],
    *,
    run_id: str,
    task: str,
    steps: List[Dict[str, Any]],
    completed_steps: List[str],
    failed_step: str,
    current_state: str,
    evidence_records: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    evidence_records = evidence_records or []
    manifest = {
        "run_id": run_id,
        "session_id": session.get("session_id", ""),
        "task": _redact(task)[:2000],
        "steps": steps,
        "completed_steps": _normalize_list(completed_steps),
        "failed_step": failed_step,
        "current_state": current_state,
        "completed_scope": _normalize_list(session.get("completed_scope", [])),
        "remaining_gap": _normalize_list(session.get("remaining_gap", [])),
        "evidence_records": evidence_records,
        "run_manifest": "",
        "recommended_next_action": "",
        "updated_at": _now(),
        "local_first": True,
        "external_api_used": False,
        "network_access_used": False,
    }
    manifest["run_manifest"] = _digest(manifest, prefix="coder-run")
    manifest["final_digest"] = _digest(manifest, prefix="coder-run-final")
    manifest["safe_digest"] = re.sub(r"[^a-f0-9-]", "", manifest["run_manifest"])
    return manifest
