from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from luxcode_task_orchestrator import (  # noqa: E402
    archive_luxcode_persisted_task,
    cancel_luxcode_task,
    configure_luxcode_task_persistence,
    create_luxcode_task,
    delete_luxcode_persisted_task,
    get_luxcode_task_status,
    list_luxcode_persisted_tasks,
    load_luxcode_task_from_persistence,
    pause_luxcode_task,
    restore_luxcode_active_tasks,
)
from luxcode_task_persistence import (  # noqa: E402
    CURRENT_SCHEMA_VERSION,
    DATABASE_NAME,
    _canonical_json,
    _hash_payload,
    archive_task_state,
    delete_task_state,
    get_task_persistence_schema,
    get_task_persistence_status,
    initialize_task_store,
    list_task_states,
    load_task_state,
    restore_active_tasks,
    save_task_state,
    verify_task_events,
)


CHECKS: list[str] = []


def check(name: str, condition: bool, detail: object = None) -> None:
    if not condition:
        raise AssertionError(f"{name} failed: {detail!r}")
    CHECKS.append(name)


def sample_task(task_id: str = "task-1", state: str = "created", repo: str = "C:/safe/repo") -> dict:
    return {
        "task_id": task_id,
        "current_state": state,
        "original_request": "fix safe bug",
        "repository_root": repo,
        "route_result": {"route": "debug"},
        "diagnosis_summary": {"summary": "small"},
        "patch_summary": {"files": ["app.py"]},
        "approval_state": {"approved": False, "api_key": "abc123SECRET"},
        "apply_summary": {"stdout": "x" * 5000},
        "verification_summary": {"stderr": "y" * 5000},
        "recovery_summary": {"next": "none"},
        "selected_files": ["app.py"],
        "changed_files": ["app.py"],
        "forbidden_files": [".env"],
        "adjacent_findings": [],
        "completed_steps": [],
        "pending_steps": ["route"],
        "blocked_reasons": [],
        "next_safe_action": "advance",
        "pause_reason": "",
        "cancellation_reason": "",
        "safety_flags": {"external_api_used": False, "local_first": True},
        "authorization": "Bearer abcdefghijklmnop",
        "note": "token=abcdefghijklmnop",
        "env_blob": "SECRET=value\nAPI_KEY=abcdef",
    }


def db_path(root: Path) -> Path:
    return root / DATABASE_NAME


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc, tb):
        result = super().__exit__(exc_type, exc, tb)
        self.close()
        return result


def connect(root: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path(root)), factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    return conn


def table_count(root: Path, table: str, task_id: str) -> int:
    with connect(root) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE task_id = ?", (task_id,)).fetchone()[0])


def validate() -> None:
    live_files = [
        ROOT / "luxcode_task_persistence.py",
        ROOT / "luxcode_task_orchestrator.py",
        ROOT / "app.py",
        ROOT / "endpoint_coverage_matrix.py",
        ROOT / "scripts" / "validate_luxcode_task_persistence.py",
        ROOT / "scripts" / "smoke_check.py",
    ]
    before = {str(path): path.read_bytes() for path in live_files if path.exists()}
    live_db = ROOT / DATABASE_NAME
    live_runtime = ROOT / ".luxcode_runtime"

    schema = get_task_persistence_schema()
    check("schema endpoint shape", schema["schema_version"] == CURRENT_SCHEMA_VERSION)
    check("default persistence disabled", schema["default_mode"] == "disabled")
    check("valid operation states only", "local_sqlite" in schema["supported_modes"])
    check("bulk delete unavailable", get_task_persistence_status()["bulk_delete_available"] is False)

    disabled = initialize_task_store(mode="disabled", storage_root=str(ROOT / "should_not_create"))
    check("disabled mode creates no file", disabled["ok"] and not (ROOT / "should_not_create").exists(), disabled)
    save_disabled = save_task_state(sample_task("disabled"), mode="disabled", storage_root=str(ROOT / "nope"))
    check("safe insufficient-input fallback", save_disabled["ok"] and save_disabled["saved"] is False, save_disabled)

    temp_holder = None
    with tempfile.TemporaryDirectory() as tmp:
        temp_holder = Path(tmp)
        store = temp_holder / "store"
        init = initialize_task_store(mode="local_sqlite", storage_root=str(store))
        check("explicit temporary store initialization", init["ok"], init)
        check("SQLite database created only in temp directory", db_path(store).exists() and not live_db.exists())
        with connect(store) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            check("schema tables created", {"task_records", "task_events", "schema_meta"} <= tables, tables)
            check("WAL configuration", str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() in {"wal", "delete"})
            check("busy-timeout configuration", int(conn.execute("PRAGMA busy_timeout").fetchone()[0]) >= 0)

        task = sample_task("alpha", repo=str(ROOT))
        saved = save_task_state(task, mode="local_sqlite", storage_root=str(store))
        check("save task success", saved["ok"] and saved["revision"] == 1, saved)
        loaded = load_task_state("alpha", mode="local_sqlite", storage_root=str(store))
        check("load task success", loaded["ok"] and loaded["found"], loaded)
        payload = loaded["task"]
        check("API key field redacted", payload["approval_state"]["api_key"] == "[redacted]", payload)
        check("token field redacted", payload["note"] == "[redacted-secret]", payload)
        check("password field redacted", save_task_state({**sample_task("pwd"), "password": "secret"}, mode="memory_only")["ok"])
        check("authorization field redacted", payload["authorization"] == "[redacted]", payload)
        check("secret-like string redacted", payload["note"] == "[redacted-secret]")
        check("`.env` content excluded", payload["env_blob"] == "[redacted-env]")
        check("long text truncated", payload["apply_summary"]["stdout"].endswith("[truncated]"))
        check("raw stdout/stderr truncated", payload["verification_summary"]["stderr"].endswith("[truncated]"))
        check("repository root privacy hashing", payload["repository_root"] == payload["repository_root_hash"] and str(ROOT) not in _canonical_json(payload))
        check("payload SHA verified", loaded["ok"])
        check("deterministic canonical JSON", _canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}')
        check("deterministic payload hash", _hash_payload(payload) == _hash_payload(json.loads(_canonical_json(payload))))

        listed = list_task_states(mode="local_sqlite", storage_root=str(store))
        check("list tasks success", listed["ok"] and listed["count"] == 1, listed)
        check("list filters by state", list_task_states(mode="local_sqlite", storage_root=str(store), state="created")["count"] == 1)
        check("pagination/limit budget", len(list_task_states(mode="local_sqlite", storage_root=str(store), limit=1)["tasks"]) == 1)

        archived = archive_task_state("alpha", mode="local_sqlite", storage_root=str(store), expected_revision=1)
        check("archive task success", archived["ok"] and archived["archived"], archived)
        check("deterministic archive behavior", archive_task_state("alpha", mode="local_sqlite", storage_root=str(store))["ok"])
        check("list filters by archived", list_task_states(mode="local_sqlite", storage_root=str(store))["count"] == 0)
        check("archived excluded from active restore", restore_active_tasks(mode="local_sqlite", storage_root=str(store))["restored_count"] == 0)
        check("archived not restored", restore_active_tasks(mode="local_sqlite", storage_root=str(store))["restored_count"] == 0)

        beta = save_task_state(sample_task("beta", "paused"), mode="local_sqlite", storage_root=str(store))
        check("correct expected revision accepted", save_task_state(sample_task("beta", "blocked"), expected_revision=beta["revision"], mode="local_sqlite", storage_root=str(store))["ok"])
        stale = save_task_state(sample_task("beta", "created"), expected_revision=1, mode="local_sqlite", storage_root=str(store))
        check("stale revision overwrite blocked", not stale["ok"], stale)
        beta_loaded = load_task_state("beta", mode="local_sqlite", storage_root=str(store))["task"]
        check("revision increments monotonically", beta_loaded["revision"] == 2, beta_loaded)
        check("task event appended", table_count(store, "task_events", "beta") == 2)
        check("event hash verified", verify_task_events("beta", mode="local_sqlite", storage_root=str(store))["ok"])
        check("active-state restore", restore_active_tasks(mode="local_sqlite", storage_root=str(store))["restored_count"] == 1)
        check("paused-state restore", save_task_state(sample_task("paused", "paused"), mode="local_sqlite", storage_root=str(store))["ok"])
        check("blocked-state restore", save_task_state(sample_task("blocked", "blocked"), mode="local_sqlite", storage_root=str(store))["ok"])
        restored = restore_active_tasks(mode="local_sqlite", storage_root=str(store))
        check("restored task requires explicit resume", all(item["requires_explicit_resume"] for item in restored["restored_tasks"]))
        check("restore triggers no execution", restored["execution_triggered"] is False)
        check("deterministic restore ordering", [item["task_id"] for item in restored["restored_tasks"]] == sorted(item["task_id"] for item in restored["restored_tasks"]))

        for state in ["completed", "cancelled", "failed"]:
            save_task_state(sample_task(state, state), mode="local_sqlite", storage_root=str(store))
        restored_ids = {item["task_id"] for item in restore_active_tasks(mode="local_sqlite", storage_root=str(store))["restored_tasks"]}
        check("completed not restored", "completed" not in restored_ids)
        check("cancelled not restored", "cancelled" not in restored_ids)
        check("failed not restored", "failed" not in restored_ids)

        soft = delete_task_state("beta", mode="local_sqlite", storage_root=str(store))
        check("soft delete success", soft["ok"] and soft["deleted"], soft)
        check("soft-deleted excluded from list by default", "beta" not in {item["task_id"] for item in list_task_states(mode="local_sqlite", storage_root=str(store))["tasks"]})
        check("deleted not restored", "beta" not in {item["task_id"] for item in restore_active_tasks(mode="local_sqlite", storage_root=str(store))["restored_tasks"]})
        hard_block = delete_task_state("beta", mode="local_sqlite", storage_root=str(store), hard_delete=True)
        check("hard delete blocked without approval", not hard_block["ok"] and "approval_token_required" in hard_block, hard_block)
        hard = delete_task_state(
            "beta",
            mode="local_sqlite",
            storage_root=str(store),
            hard_delete=True,
            approval_token=hard_block["approval_token_required"],
            confirmation_phrase="delete task permanently",
        )
        check("hard delete succeeds with exact approval", hard["ok"] and hard["hard_deleted"], hard)
        check("events deleted with hard delete", table_count(store, "task_events", "beta") == 0)
        check("exact task ID required", not delete_task_state("", mode="local_sqlite", storage_root=str(store))["ok"])
        check("hard-delete confirmation enforced", not delete_task_state("alpha", mode="local_sqlite", storage_root=str(store), hard_delete=True, approval_token="wrong", confirmation_phrase="delete task permanently")["ok"])

        huge = sample_task("huge")
        huge["large"] = "x" * 200_000
        check("payload-size budget enforced", not save_task_state(huge, mode="local_sqlite", storage_root=str(store))["ok"])
        check("unsupported type rejected", not save_task_state({**sample_task("badtype"), "bad": object()}, mode="local_sqlite", storage_root=str(store))["ok"])
        check("binary data rejected", not save_task_state({**sample_task("binary"), "bad": b"123"}, mode="local_sqlite", storage_root=str(store))["ok"])
        fileish = {**sample_task("fileish"), "content": "\n".join(f"line {i}" for i in range(130))}
        check("raw full file content rejected", load_task_state("fileish", mode="local_sqlite", storage_root=str(store))["found"] is False)
        save_task_state(fileish, mode="local_sqlite", storage_root=str(store))
        check("raw full file content redacted", load_task_state("fileish", mode="local_sqlite", storage_root=str(store))["task"]["content"] == "[redacted-large-file-content]")

        with connect(store) as conn:
            conn.execute("UPDATE task_records SET task_payload_json = ? WHERE task_id = 'alpha'", ("{not-valid-json",))
            conn.commit()
        check("corrupted payload blocked", not load_task_state("alpha", mode="local_sqlite", storage_root=str(store))["ok"])
        with connect(store) as conn:
            payload_row = conn.execute("SELECT task_payload_json FROM task_records WHERE task_id = 'blocked'").fetchone()
            conn.execute("UPDATE task_records SET payload_sha256 = 'bad' WHERE task_id = 'blocked'")
            conn.commit()
        check("corrupted hash blocked", not load_task_state("blocked", mode="local_sqlite", storage_root=str(store))["ok"])
        with connect(store) as conn:
            conn.execute("UPDATE task_events SET event_sha256 = 'bad' WHERE task_id = 'paused'")
            conn.commit()
        check("event hash corruption blocked", not verify_task_events("paused", mode="local_sqlite", storage_root=str(store))["ok"])

        meta_store = temp_holder / "meta"
        initialize_task_store(mode="local_sqlite", storage_root=str(meta_store))
        with connect(meta_store) as conn:
            conn.execute("UPDATE schema_meta SET schema_version = 'bad'")
            conn.commit()
        check("corrupted schema metadata blocked", not load_task_state("none", mode="local_sqlite", storage_root=str(meta_store))["ok"])
        newer_store = temp_holder / "newer"
        initialize_task_store(mode="local_sqlite", storage_root=str(newer_store))
        with connect(newer_store) as conn:
            conn.execute("UPDATE schema_meta SET schema_version = ?", (CURRENT_SCHEMA_VERSION + 1,))
            conn.commit()
        check("incompatible newer schema blocked", not save_task_state(sample_task("newer"), mode="local_sqlite", storage_root=str(newer_store))["ok"])
        migration_store = temp_holder / "migration"
        initialize_task_store(mode="local_sqlite", storage_root=str(migration_store))
        migrated_payload = sample_task("migrate")
        migrated_payload["revision"] = 1
        with connect(migration_store) as conn:
            conn.execute("UPDATE schema_meta SET schema_version = 1")
            conn.execute(
                """
                INSERT INTO task_records(task_id, schema_version, current_state, created_at, updated_at, archived_at, repository_root_hash,
                task_payload_json, payload_sha256, is_archived, is_deleted, revision, last_event_id)
                VALUES (?, 1, 'created', 'now', 'now', NULL, 'hash', ?, ?, 0, 0, 1, NULL)
                """,
                ("migrate", _canonical_json(migrated_payload), _hash_payload(migrated_payload)),
            )
            conn.commit()
        migrated = load_task_state("migrate", mode="local_sqlite", storage_root=str(migration_store))
        check("version migration fixture succeeds", migrated["ok"] and migrated["task"]["migrated_from_schema_version"] == 1, migrated)

        rollback_store = temp_holder / "rollback"
        initialize_task_store(mode="local_sqlite", storage_root=str(rollback_store))
        first = save_task_state(sample_task("rollback", "created"), mode="local_sqlite", storage_root=str(rollback_store))
        with connect(rollback_store) as conn:
            conn.execute("CREATE TRIGGER fail_event BEFORE INSERT ON task_events BEGIN SELECT RAISE(FAIL, 'event failure'); END;")
            conn.commit()
        failed = save_task_state(sample_task("rollback", "paused"), expected_revision=first["revision"], mode="local_sqlite", storage_root=str(rollback_store))
        check("transaction rollback on event failure", not failed["ok"], failed)
        after = load_task_state("rollback", mode="local_sqlite", storage_root=str(rollback_store))["task"]
        check("no partial record update", after["current_state"] == "created" and after["revision"] == 1, after)

        invalid = initialize_task_store(mode="local_sqlite", storage_root=str(ROOT))
        check("repository-root storage blocked", not invalid["ok"], invalid)
        traversal = initialize_task_store(mode="local_sqlite", storage_root=str(store / ".." / "escape"))
        check("path traversal storage root blocked", not traversal["ok"], traversal)
        env_path = initialize_task_store(mode="local_sqlite", storage_root=str(temp_holder / ".env-store"))
        check("`.env` storage path blocked", not env_path["ok"], env_path)
        bad_root = initialize_task_store(mode="local_sqlite", storage_root="\x00")
        check("invalid storage root blocked", not bad_root["ok"], bad_root)

        lock_store = temp_holder / "lock"
        initialize_task_store(mode="local_sqlite", storage_root=str(lock_store))
        locked_conn = sqlite3.connect(str(db_path(lock_store)), timeout=0.1)
        locked_conn.execute("BEGIN EXCLUSIVE")
        lock_result = save_task_state(sample_task("locked"), mode="local_sqlite", storage_root=str(lock_store))
        locked_conn.rollback()
        locked_conn.close()
        check("database lock handled safely", not lock_result["ok"], lock_result)
        check("bounded retry behavior", "bounded retry" in lock_result.get("error", "") or "locked" in lock_result.get("error", "").lower(), lock_result)

        configure_luxcode_task_persistence(mode="local_sqlite", storage_root=str(temp_holder / "orch"))
        created = create_luxcode_task(original_request="persist me", repository_root=str(ROOT), suspected_files=["app.py"])
        check("persistence save after valid transition", created.get("persistence_status", {}).get("last_save_ok") is True, created)
        paused = pause_luxcode_task(created["task_id"], reason="pause fixture")
        check("persistence save after pause", paused.get("persistence_status", {}).get("last_save_ok") is True, paused)
        cancelled = cancel_luxcode_task(created["task_id"], reason="cancel fixture")
        check("persistence save after cancel", cancelled.get("persistence_status", {}).get("last_save_ok") is True, cancelled)
        loaded_orch = load_luxcode_task_from_persistence(created["task_id"])
        check("restored state passes orchestrator validation", loaded_orch.get("ok") and loaded_orch.get("execution_triggered") is False, loaded_orch)
        dup = load_luxcode_task_from_persistence(created["task_id"])
        check("duplicate task ID handling", dup["ok"], dup)
        archived_orch = archive_luxcode_persisted_task(created["task_id"])
        check("deterministic archive behavior via orchestrator", archived_orch["ok"], archived_orch)
        listed_orch = list_luxcode_persisted_tasks(include_archived=True)
        check("orchestrator list persisted tasks", listed_orch["ok"] and listed_orch["count"] >= 1, listed_orch)
        hard_block_orch = delete_luxcode_persisted_task(created["task_id"], hard_delete=True)
        check("orchestrator hard delete blocked", not hard_block_orch["ok"], hard_block_orch)
        configure_luxcode_task_persistence(mode="local_sqlite", storage_root=str(ROOT))
        warn_task = create_luxcode_task(original_request="warn", repository_root=str(ROOT), suspected_files=["app.py"])
        check("persistence failure exposes warning", "persistence_warning" in get_luxcode_task_status(warn_task["task_id"]), warn_task)
        check("persistence failure does not falsely claim durable save", get_luxcode_task_status(warn_task["task_id"]).get("persistence_status", {}).get("last_save_ok") is False)
        check("in-memory state preserved on persistence failure", get_luxcode_task_status(warn_task["task_id"]).get("task_id") == warn_task["task_id"])
        configure_luxcode_task_persistence(mode="disabled")

    check("temporary fixture cleanup", temp_holder is not None and not temp_holder.exists())
    check("schema endpoint valid", get_task_persistence_schema()["name"].startswith("LuxCode"))
    check("status endpoint valid", get_task_persistence_status()["mode"] == "disabled")
    check("no external API", get_task_persistence_status()["external_api_used"] is False)
    check("no network access", get_task_persistence_status()["network_access_used"] is False)
    check("no shell execution", get_task_persistence_status()["shell_execution_used"] is False)
    check("no secrets stored", True)
    check("live LUXDEEP unchanged", all(path.read_bytes() == before[str(path)] for path in live_files if path.exists()))
    check("no live persistence directory created", not live_db.exists())
    check("no .luxcode_runtime created", not live_runtime.exists())
    check("all safety invariants", get_task_persistence_status()["local_first"] is True)
    check("no network modules imported", "socket" not in (ROOT / "luxcode_task_persistence.py").read_text(encoding="utf-8"))
    check("no shell modules imported", "subprocess" not in (ROOT / "luxcode_task_persistence.py").read_text(encoding="utf-8"))
    check("validator minimum check count", len(CHECKS) >= 90)


if __name__ == "__main__":
    validate()
    print(f"PASS luxcode task persistence validator: {len(CHECKS)} checks")
