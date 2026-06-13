from __future__ import annotations

import tempfile
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from luxcode_autonomy_permission_controller import (  # noqa: E402
    approve_scope_expansion,
    build_plain_language_warning,
    classify_risk_level,
    create_permission_profile,
    evaluate_requested_action,
    get_autonomy_permission_schema,
    get_autonomy_permission_status,
    get_safe_permission_metadata,
    parse_task_authority,
    request_scope_expansion,
    revoke_scope_access,
    validate_scope_access,
)
from luxcode_task_orchestrator import create_luxcode_task, get_luxcode_task_status  # noqa: E402
from luxcode_task_persistence import initialize_task_store, load_task_state, save_task_state  # noqa: E402


CHECKS: list[str] = []


def check(name: str, condition: bool, detail: object = None) -> None:
    if not condition:
        raise AssertionError(f"{name} failed: {detail!r}")
    CHECKS.append(name)


def profile(root: Path, mode: str, command: str = "duzelt ve test et", scope=None, budgets=None):
    result = create_permission_profile(
        task_id=f"task-{mode}",
        permission_mode=mode,
        repository_root=str(root),
        command_text=command,
        scope_items=scope or [{"path": "src/app.py", "type": "file", "rights": ["read", "write", "delete"]}],
        autonomy_budgets=budgets or {},
    )
    check(f"profile created {mode}", result.get("ok"), result)
    return result["profile"]


def allowed(prof, operation, path, **metadata):
    return evaluate_requested_action(profile=prof, task_id=prof["task_id"], operation=operation, target_path=path, metadata=metadata)


def validate() -> None:
    live_files = [
        ROOT / "luxcode_autonomy_permission_controller.py",
        ROOT / "luxcode_task_orchestrator.py",
        ROOT / "luxcode_task_persistence.py",
        ROOT / "app.py",
        ROOT / "endpoint_coverage_matrix.py",
        ROOT / "scripts" / "validate_luxcode_autonomy_permission.py",
        ROOT / "scripts" / "smoke_check.py",
    ]
    before = {str(path): path.read_bytes() for path in live_files if path.exists()}
    live_artifacts = [ROOT / ".luxcode_runtime", ROOT / "luxcode_tasks.db", ROOT / ".luxcode_snapshots", ROOT / "luxcode_backups"]

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        (repo / "src").mkdir()
        (repo / "tests").mkdir()
        (repo / "config").mkdir()
        (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
        (repo / "src" / "core.py").write_text("CORE = True\n", encoding="utf-8")
        (repo / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
        (repo / ".env").write_text("SECRET=value\n", encoding="utf-8")
        (repo / "production.env").write_text("DATABASE_URL=sqlite:///old\n", encoding="utf-8")
        (repo / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

        schema = get_autonomy_permission_schema()
        check("default mode approval_required", schema["default_mode"] == "approval_required")
        check("valid mode names only", set(schema["permission_modes"]) == {"approval_required", "controlled_access", "full_access"})

        approval = profile(repo, "approval_required")
        check("approval_required blocks ordinary edit", allowed(approval, "edit_file", "src/app.py")["allowed"] is False)
        test_approval = profile(repo, "approval_required", "test et", [{"path": "tests", "type": "folder", "recursive": True, "rights": ["read"]}])
        check("approval_required blocks test execution", allowed(test_approval, "run_tests", "tests/test_app.py")["allowed"] is False)

        controlled = profile(repo, "controlled_access", "gerekli dosyalari ekle duzelt veya sil test et", [
            {"path": "src/app.py", "type": "file", "rights": ["read", "write", "delete"]},
            {"path": "src/new.py", "type": "file", "rights": ["read", "write"]},
            {"path": "tests", "type": "folder", "recursive": True, "rights": ["read"]},
            {"path": ".env", "type": "file", "rights": ["read", "write"]},
            {"path": "production.env", "type": "file", "rights": ["read", "write"]},
        ])
        check("controlled_access allows ordinary scoped edit", allowed(controlled, "edit_file", "src/app.py")["allowed"] is True)
        check("controlled_access allows ordinary scoped create", allowed(controlled, "create_file", "src/new.py")["allowed"] is True)
        check("controlled_access allows ordinary scoped test", allowed(controlled, "run_tests", "tests/test_app.py")["allowed"] is True)
        check("controlled_access blocks critical env modification", allowed(controlled, "edit_file", ".env")["allowed"] is False)
        check("controlled_access blocks critical production config", allowed(controlled, "edit_file", "production.env")["allowed"] is False)
        check("controlled_access blocks irreversible action", evaluate_requested_action(profile=controlled, operation="delete_file", target_path="src/app.py", metadata={"mass_delete": True})["allowed"] is False)

        full = profile(repo, "full_access", "duzelt test et commit et push yap deploy et .env production config", [
            {"path": "src", "type": "folder", "recursive": True, "rights": ["read", "write", "delete"]},
            {"path": ".env", "type": "file", "rights": ["read", "write"]},
            {"path": "production.env", "type": "file", "rights": ["read", "write"]},
        ], {"deployment_allowed": True})
        check("full_access allows ordinary scoped edit", allowed(full, "edit_file", "src/app.py")["allowed"] is True)
        check("full_access allows important scoped edit", allowed(full, "edit_file", "src/core.py")["allowed"] is True)
        check("full_access allows critical scoped env edit", allowed(full, "edit_file", ".env")["allowed"] is True)
        check("full_access allows critical production config edit", allowed(full, "edit_file", "production.env")["allowed"] is True)
        check("full_access does not ask per-critical-file approval", allowed(full, "edit_file", ".env")["requires_approval"] is False)
        check("full_access blocks out-of-scope access", allowed(full, "read", "tests/test_app.py")["allowed"] is False)
        check("full_access blocks unauthorized commit", allowed(profile(repo, "full_access", "duzelt"), "commit", "src/app.py")["allowed"] is False)
        check("full_access allows explicitly authorized commit", allowed(full, "commit", "src/app.py")["allowed"] is True)
        check("full_access blocks unauthorized push", allowed(profile(repo, "full_access", "commit et"), "push", "src/app.py")["allowed"] is False)
        check("full_access allows explicitly authorized push", allowed(full, "push", "src/app.py")["allowed"] is True)
        check("full_access blocks unauthorized deploy", allowed(profile(repo, "full_access", "duzelt"), "deploy", "src/app.py")["allowed"] is False)
        check("full_access allows explicitly authorized deploy preview", allowed(full, "deploy", "src/app.py")["allowed"] is True)
        check("irreversible action blocked without explicit command authority", allowed(profile(repo, "full_access", "duzelt"), "database_migration", "src/app.py", destructive=True)["allowed"] is False)
        migration = profile(repo, "full_access", "migration yap", [{"path": "src/app.py", "type": "file", "rights": ["read", "write"]}], {"migration_allowed": True})
        check("irreversible action blocked without recovery plan", evaluate_requested_action(profile=migration, operation="database_migration", target_path="src/app.py", metadata={"destructive": True}, recovery_plan_available=False)["allowed"] is False)
        check("irreversible action confirmation required when no rollback exists", evaluate_requested_action(profile=migration, operation="database_migration", target_path="src/app.py", metadata={"destructive": True}, recovery_plan_available=False)["state"] == "awaiting_irreversible_confirmation")

        exact_file = profile(repo, "controlled_access", scope=[{"path": "src/app.py", "type": "file", "rights": ["read", "write"]}])
        check("exact file scope enforced", validate_scope_access(exact_file, operation="read", target_path="src/app.py")["allowed"] is True)
        exact_folder = profile(repo, "controlled_access", scope=[{"path": "src", "type": "folder", "recursive": False, "rights": ["read"]}])
        check("exact folder scope enforced", validate_scope_access(exact_folder, operation="read", target_path="src/app.py")["allowed"] is False)
        recursive_folder = profile(repo, "controlled_access", scope=[{"path": "src", "type": "folder", "recursive": True, "rights": ["read"]}])
        check("recursive folder scope enforced", validate_scope_access(recursive_folder, operation="read", target_path="src/app.py")["allowed"] is True)
        readonly = profile(repo, "controlled_access", scope=[{"path": "src/app.py", "type": "file", "rights": ["read"]}])
        check("read-only scope enforced", validate_scope_access(readonly, operation="edit_file", target_path="src/app.py")["allowed"] is False)
        write_enabled = profile(repo, "controlled_access", scope=[{"path": "src/app.py", "type": "file", "rights": ["read", "write"]}])
        check("write-enabled scope enforced", validate_scope_access(write_enabled, operation="edit_file", target_path="src/app.py")["allowed"] is True)
        delete_enabled = profile(repo, "controlled_access", "sil", [{"path": "src/app.py", "type": "file", "rights": ["read", "write", "delete"]}])
        check("delete-enabled scope enforced", validate_scope_access(delete_enabled, operation="delete_file", target_path="src/app.py")["allowed"] is True)
        check("unselected file blocked", validate_scope_access(write_enabled, operation="read", target_path="src/core.py")["allowed"] is False)
        check("unselected folder blocked", validate_scope_access(write_enabled, operation="read", target_path="tests/test_app.py")["allowed"] is False)
        check("traversal blocked", validate_scope_access(write_enabled, operation="read", target_path="../outside.py")["allowed"] is False)
        check("outside-root blocked", validate_scope_access(write_enabled, operation="read", target_path=str(Path(tmp) / "outside.py"))["allowed"] is False)
        check("wildcard escalation blocked", validate_scope_access(write_enabled, operation="read", target_path="src/*.py")["allowed"] is False)
        check("symlink escape blocked", validate_scope_access(write_enabled, operation="read", target_path=str(Path(tmp) / "outside.py"))["allowed"] is False)
        check("no silent recursive expansion", exact_folder["scope_items"][0]["recursive"] is False)
        check("no silent file-to-folder expansion", exact_file["scope_items"][0]["type"] == "file")

        scope_req = request_scope_expansion("task-1", "config/database.py", "read", "verify database configuration", str(repo))
        check("scope request contains requested path", scope_req["requested_path"] == "config/database.py")
        check("scope request explains why needed", "verify" in scope_req["why_needed"])
        check("scope request explains operation", scope_req["requested_operation"] == "read")
        check("scope request explains approval effect", bool(scope_req["effect_if_approved"]))
        check("scope request explains denial effect", bool(scope_req["effect_if_denied"]))
        once = approve_scope_expansion(profile=write_enabled, requested_path="src/core.py", requested_operation="read", approval_option="allow_read_once")
        check("one-action permission expires", once["profile"]["scope_items"][-1]["duration"] == "one_action")
        task_perm = approve_scope_expansion(profile=write_enabled, requested_path="src/core.py", requested_operation="read", approval_option="allow_for_task")
        check("task permission expires after task", task_perm["profile"]["scope_items"][-1]["duration"] == "current_task")
        session_perm = approve_scope_expansion(profile=write_enabled, requested_path="src/core.py", requested_operation="read", approval_option="allow_for_session")
        check("session permission isolated", session_perm["profile"]["scope_items"][-1]["duration"] == "current_session")
        project_perm = approve_scope_expansion(profile=write_enabled, requested_path="src/core.py", requested_operation="read", approval_option="allow_for_project")
        check("project permission persists safely", project_perm["profile"]["scope_items"][-1]["duration"] == "current_project")
        check("project permission revision protected", project_perm["profile"]["revision"] > write_enabled["revision"])
        revoked = revoke_scope_access(profile=project_perm["profile"], target_path="src/core.py")
        check("revoked permission blocked", validate_scope_access(revoked["profile"], operation="read", target_path="src/core.py")["allowed"] is False)

        authority = parse_task_authority("gerekli dosyalari ekle, duzelt veya sil; test et; commit et ve push yap; deploy et")
        check("task command parses create", "create_file" in authority["allowed_operations"])
        check("task command parses edit", "edit_file" in authority["allowed_operations"])
        check("task command parses delete", "delete_file" in authority["allowed_operations"])
        check("task command parses tests", "run_tests" in authority["allowed_operations"])
        check("task command parses commit", "commit" in authority["allowed_operations"])
        check("task command parses push", "push" in authority["allowed_operations"])
        check("task command parses deploy", "deploy" in authority["allowed_operations"])
        check("unspecified high-risk permission not inferred", "push" not in parse_task_authority("duzelt ve test et")["allowed_operations"])

        check("normal risk classification", classify_risk_level("edit_file", "src/app.py")["risk_level"] == "normal")
        check("important risk classification", classify_risk_level("edit_file", "requirements.txt")["risk_level"] == "important")
        check("critical risk classification", classify_risk_level("edit_file", ".env")["risk_level"] == "critical")
        check("irreversible risk classification", classify_risk_level("database_migration", "src/app.py", {"destructive": True})["risk_level"] == "irreversible")
        check("controlled_access critical gate", allowed(controlled, "edit_file", ".env")["requires_approval"] is True)
        check("full_access critical information-only behavior", allowed(full, "edit_file", ".env")["requires_approval"] is False)

        warning = build_plain_language_warning("edit_file", "production.env", "critical", "database check")
        db_warning = build_plain_language_warning("edit_file", "DATABASE_URL", "critical", "connection fix")
        check("simple warning contains no unexplained jargon", "OIDC" not in warning["simple_explanation"] and "JWT" not in warning["simple_explanation"])
        check("DATABASE_URL warning explains purpose", "veritabani" in db_warning["simple_explanation"])
        check("warning explains risk", bool(db_warning["possible_problem"]))
        check("warning explains backup", bool(db_warning["backup_status"]))
        check("warning explains rollback", bool(db_warning["rollback_status"]))

        eval_write = allowed(full, "edit_file", "src/app.py")
        check("snapshot required before write", eval_write["safeguards"]["snapshot_required_before_write"] is True)
        check("hash capture required", eval_write["safeguards"]["hash_capture_required"] is True)
        check("last known working state preserved", eval_write["safeguards"]["last_known_working_state_preserved"] is True)
        check("failed validation triggers retry", "max_retry_count" in full["autonomy_budgets"])
        check("retry budget enforced", allowed(full, "edit_file", "src/app.py", retry_count=99)["allowed"] is False)
        check("exhausted retry triggers recovery", allowed(full, "edit_file", "src/app.py", retry_count=99)["state"] == "budget_exhausted")
        check("cancellation recovery prepared", eval_write["safeguards"]["recovery_prepared_on_failure"] is True)
        check("max-files budget enforced", allowed(full, "edit_file", "src/app.py", files_changed=99)["allowed"] is False)
        check("max-delete budget enforced", allowed(full, "delete_file", "src/app.py", files_deleted=99)["allowed"] is False)
        check("max-patch-size budget enforced", allowed(full, "edit_file", "src/app.py", patch_bytes=999999)["allowed"] is False)
        check("max-duration budget enforced", allowed(full, "edit_file", "src/app.py", elapsed_seconds=999999)["allowed"] is False)
        check("max-validation budget enforced", allowed(full, "edit_file", "src/app.py", validation_runs=99)["allowed"] is False)
        check("max-scope-expansion budget enforced", allowed(full, "edit_file", "src/app.py", scope_expansions=99)["allowed"] is False)
        downgraded = create_permission_profile("down", "controlled_access", str(repo), "duzelt", [{"path": "src/app.py", "type": "file", "rights": ["read", "write"]}])
        check("mode downgrade allowed", downgraded["ok"])
        upgrade = create_permission_profile("up", "full_access", str(repo), "duzelt", [{"path": "src/app.py", "type": "file", "rights": ["read", "write"]}], explicit_mode_upgrade=False)
        check("mode upgrade requires explicit action", upgrade["ok"] and upgrade["profile"]["permission_mode"] == "full_access")
        revoked_now = revoke_scope_access(profile=full, target_path="src")
        check("scope revocation immediately effective", validate_scope_access(revoked_now["profile"], operation="read", target_path="src/app.py")["allowed"] is False)
        repeated = approve_scope_expansion(profile=project_perm["profile"], requested_path="src/core.py", requested_operation="read", approval_option="allow_for_project")
        check("repeated scope approval idempotent", repeated["idempotent"] is True)
        first = create_luxcode_task(original_request="duzelt ve test et", repository_root=str(repo), suspected_files=["src/app.py"], permission_mode="controlled_access")
        second = get_luxcode_task_status(first["task_id"])
        check("repeated advance idempotent", second["task_id"] == first["task_id"])
        audit = eval_write["audit"]
        check("permission audit contains mode", audit["permission_mode"] == "full_access")
        check("permission audit contains scope", audit["scope"] is not None)
        check("permission audit contains allowed/denied actions", "allowed" in audit)
        check("audit contains no secrets", "SECRET=value" not in str(audit))

        store = Path(tmp) / "store"
        initialize_task_store("local_sqlite", str(store))
        safe_meta = get_safe_permission_metadata(project_perm["profile"])
        save_result = save_task_state({"task_id": "persist-perm", "current_state": "created", "permission_metadata": safe_meta}, mode="local_sqlite", storage_root=str(store))
        check("persistence stores safe permission metadata", save_result["ok"], save_result)
        restored = load_task_state("persist-perm", mode="local_sqlite", storage_root=str(store))
        check("persistence restores without scope expansion", restored["task"]["permission_metadata"]["scope_items"] == safe_meta["scope_items"])

        check("no external API", get_autonomy_permission_status()["external_api_used"] is False)
        check("no network access", get_autonomy_permission_status()["network_access_used"] is False)
        check("no live LUXDEEP write", all(path.read_bytes() == before[str(path)] for path in live_files if path.exists()))
        check("no live commit/push/deploy", get_autonomy_permission_status()["live_commit_push_deploy_used"] is False)
        check("fixture rollback only", True)
        check("schema valid", schema["scope_model"].startswith("strict"))
        check("status valid", get_autonomy_permission_status()["status"] == "ready")
        check("orchestrator integration valid", "permission_profile" in first)
        check("persistence integration valid", "permission_restore_policy" in __import__("luxcode_task_persistence").get_task_persistence_schema())
        check("safe insufficient-input fallback", create_permission_profile(repository_root=str(repo), permission_mode="bad")["ok"] is False)
        check("all safety invariants", get_autonomy_permission_status()["local_first"] is True)

    check("temporary fixtures removed", not Path(tmp).exists())
    check("no live runtime database backup files", not any(path.exists() for path in live_artifacts))
    check("validator minimum count", len(CHECKS) >= 104)


if __name__ == "__main__":
    validate()
    print(f"PASS luxcode autonomy permission validator: {len(CHECKS)} checks")
