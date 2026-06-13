from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from endpoint_coverage_matrix import ENDPOINT_GROUPS
from luxcode_task_orchestrator import (
    TASK_STATES,
    advance_luxcode_task,
    approve_luxcode_task_step,
    cancel_luxcode_task,
    create_luxcode_task,
    get_luxcode_task_status,
    get_task_orchestrator_schema,
    get_task_orchestrator_status,
    pause_luxcode_task,
    resume_luxcode_task,
)

EXPECTED_FILES = {
    "luxcode_task_orchestrator.py",
    "app.py",
    "endpoint_coverage_matrix.py",
    "scripts/validate_luxcode_task_orchestrator.py",
    "scripts/smoke_check.py",
}
ENDPOINTS = {
    "/luxcode-task/schema",
    "/luxcode-task/create",
    "/luxcode-task/advance",
    "/luxcode-task/approve",
    "/luxcode-task/pause",
    "/luxcode-task/resume",
    "/luxcode-task/cancel",
    "/luxcode-task/{task_id}",
    "/debug/luxcode-task-orchestrator-status",
}


class CheckCounter:
    def __init__(self) -> None:
        self.count = 0

    def check(self, condition: bool, message: str) -> None:
        self.count += 1
        if not condition:
            raise AssertionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_fixture() -> tempfile.TemporaryDirectory[str]:
    temp = tempfile.TemporaryDirectory(prefix="lux_task_orchestrator_fixture_")
    root = Path(temp.name)
    (root / "target.py").write_text("VALUE = 'old'\n", encoding="utf-8")
    (root / "scripts").mkdir()
    (root / "scripts" / "validate_fixture.py").write_text("import target\nassert target.VALUE == 'new'\n", encoding="utf-8")
    return temp


def create_ready_task(root: Path) -> Dict[str, Any]:
    task = create_luxcode_task(
        original_request="Change VALUE safely",
        repository_root=str(root),
        suspected_files=["target.py"],
        requested_files=["target.py"],
    )
    task = advance_luxcode_task(task["task_id"])
    task = advance_luxcode_task(task["task_id"])
    task = advance_luxcode_task(task["task_id"])
    return task


def executable_step() -> Dict[str, Any]:
    return {
        "target_file": "target.py",
        "change_type": "replace_exact",
        "expected_original_text": "VALUE = 'old'\n",
        "replacement_text": "VALUE = 'new'\n",
        "target_region": "fixture value",
        "purpose": "fixture apply",
        "validation_after_change": ["python -m py_compile target.py"],
    }


def assert_invariants(counter: CheckCounter, payload: Dict[str, Any]) -> None:
    counter.check(payload.get("scope_expansion_blocked") is True, "scope expansion must stay blocked")
    counter.check(payload.get("destructive_action_blocked") is True, "destructive action must stay blocked")
    counter.check(payload.get("external_api_used") is False, "external API flag must be false")
    counter.check(payload.get("local_first") is True, "local-first flag must be true")


def main() -> None:
    checks = CheckCounter()
    live_hashes = {rel: sha(ROOT / rel) for rel in EXPECTED_FILES if (ROOT / rel).exists()}
    runtime_before = (ROOT / ".luxcode_runtime").exists()

    schema = get_task_orchestrator_schema()
    checks.check(schema["state_storage"] == "in_memory_only", "schema must declare in-memory storage")
    checks.check("in-memory state is lost on process restart" in schema["known_limitation"], "schema must include restart limitation")
    checks.check(set(schema["supported_states"]) == TASK_STATES, "schema must list valid states only")
    assert_invariants(checks, schema)

    with make_fixture() as temp_name:
        fixture = Path(temp_name)
        task = create_luxcode_task(
            original_request="Bu hatayi bul ve guvenli sekilde duzelt",
            repository_root=str(fixture),
            suspected_files=["target.py"],
            selected_files=["target.py"],
            requested_files=["target.py"],
            changed_files=[],
        )
        task_id = task["task_id"]
        checks.check(task["current_state"] == "created", "new task must start created")
        checks.check(task["repository_root"] == str(fixture.resolve()), "repository root must be preserved")
        checks.check("target.py" in task["pending_steps"] or task["pending_steps"], "pending steps must be present")
        assert_invariants(checks, task)

        routed = advance_luxcode_task(task_id, "route")
        checks.check(routed["current_state"] == "routed", "routing transition failed")
        checks.check(routed["route_result"].get("route_family"), "route result missing family")

        diagnosed = advance_luxcode_task(task_id, "diagnose")
        checks.check(diagnosed["current_state"] == "diagnosis_ready", "diagnosis transition failed")
        checks.check(diagnosed["diagnosis_summary"].get("root_cause_hypotheses") is not None, "diagnosis missing hypotheses")
        checks.check(diagnosed["selected_files"], "selected files must be preserved")

        patch_ready = advance_luxcode_task(task_id, "draft")
        checks.check(patch_ready["current_state"] == "awaiting_approval", "patch draft must await approval")
        checks.check(patch_ready["patch_summary"].get("patch_steps") is not None, "patch draft missing steps")
        checks.check(patch_ready["requires_user_approval"] is True, "patch approval must be required")

        blocked_apply = advance_luxcode_task(task_id, "prepare_apply")
        checks.check(blocked_apply["current_state"] in {"awaiting_approval", "blocked"}, "apply must block without approval")
        checks.check(blocked_apply["blocked_reasons"], "missing approval must be recorded")

        wrong = approve_luxcode_task_step(
            task_id,
            patch_digest="wrong",
            approved_files=["target.py"],
            patch_steps=[executable_step()],
            repository_root=str(fixture),
        )
        checks.check(wrong["current_state"] in {"awaiting_approval", "blocked"}, "wrong approval must be blocked")

        approved = approve_luxcode_task_step(
            task_id,
            approved_files=["target.py"],
            patch_steps=[executable_step()],
            repository_root=str(fixture),
        )
        checks.check(approved["current_state"] == "approval_verified", "valid approval not accepted")
        checks.check(approved["approval_state"].get("approved") is True, "approval state not marked approved")
        checks.check(approved["approval_state"].get("patch_digest"), "approval digest not bound to task")

        mutated_patch = advance_luxcode_task(
            task_id,
            "prepare_apply",
            patch_steps=[dict(executable_step(), replacement_text="VALUE = 'mutated'\n")],
        )
        checks.check(mutated_patch["current_state"] in {"awaiting_approval", "blocked"}, "patch mutation must invalidate approval")
        checks.check(mutated_patch["approval_state"].get("approved") is False, "mutated patch approval must be invalid")

        approved = approve_luxcode_task_step(task_id, approved_files=["target.py"], patch_steps=[executable_step()], repository_root=str(fixture))
        prepared = advance_luxcode_task(task_id, "prepare_apply")
        checks.check(prepared["current_state"] == "apply_prepared", "apply prepare requires valid approval")
        checks.check(prepared["apply_summary"].get("approval_digest", "").startswith("lux-approve-"), "apply digest missing")

        wrong_root = approve_luxcode_task_step(task_id, approved_files=["target.py"], patch_steps=[executable_step()], repository_root=str(fixture / "other"))
        checks.check(wrong_root["current_state"] in {"awaiting_approval", "blocked"}, "repository root mutation must be blocked")

        bad_hash_task = create_ready_task(fixture)
        expected = {"target.py": "bad"}
        bad_hash = approve_luxcode_task_step(
            bad_hash_task["task_id"],
            approved_files=["target.py"],
            patch_steps=[executable_step()],
            expected_file_hashes=expected,
            repository_root=str(fixture),
        )
        bad_prepared = advance_luxcode_task(bad_hash_task["task_id"], "prepare_apply")
        checks.check(bad_prepared["apply_summary"].get("precondition_failures"), "expected hash mutation must fail preconditions")

        approved = approve_luxcode_task_step(task_id, approved_files=["target.py"], patch_steps=[executable_step()], repository_root=str(fixture))
        prepared = advance_luxcode_task(task_id, "prepare_apply")
        token = prepared["apply_summary"]["approval_digest"]
        approved_for_apply = approve_luxcode_task_step(
            task_id,
            approved_files=["target.py"],
            patch_steps=[executable_step()],
            repository_root=str(fixture),
            approve_apply_execution=True,
            controlled_apply_approval_token=token,
        )
        checks.check(approved_for_apply["approval_state"].get("apply_execution_approved") is True, "apply execution approval missing")

        applied = advance_luxcode_task(task_id, "apply")
        checks.check(applied["current_state"] == "applied", "fixture apply did not succeed")
        checks.check((fixture / "target.py").read_text(encoding="utf-8") == "VALUE = 'new'\n", "fixture file not changed")
        duplicate_apply = advance_luxcode_task(task_id, "apply")
        checks.check(duplicate_apply["completed_steps"].count("apply") == 1, "duplicate apply must not repeat")

        verification = advance_luxcode_task(
            task_id,
            "prepare_verification",
            verification_checks=[{"check_type": "py_compile", "check_id": "compile_target", "files": ["target.py"]}],
        )
        checks.check(verification["current_state"] == "verification_prepared", "verification not prepared")
        checks.check(verification["requires_user_approval"] is True, "verification execution approval required")
        verification_token = verification["verification_summary"]["verification_digest"]
        verified_approval = approve_luxcode_task_step(
            task_id,
            approved_files=["target.py"],
            patch_steps=[executable_step()],
            repository_root=str(fixture),
            approve_verification_execution=True,
            verification_approval_token=verification_token,
        )
        checks.check(verified_approval["approval_state"].get("verification_execution_approved") is True, "verification approval missing")
        completed = advance_luxcode_task(task_id, "execute_verification")
        checks.check(completed["current_state"] == "completed", "successful task must complete")
        checks.check(completed["verification_summary"]["summary"]["passed"] >= 1, "fixture verification must pass")

        status = get_luxcode_task_status(task_id)
        checks.check(status["task_id"] == task_id, "task state retrieval failed")
        checks.check(status["completed_steps"].count("apply") == 1, "completed steps repeated")
        checks.check(status["completed_steps"].count("execute_verification") == 1, "verification repeated")
        checks.check(status["current_state"] == "completed", "completed state not preserved")

        missing = get_luxcode_task_status("missing-task-id")
        checks.check(missing.get("safe_response") is True and missing.get("found") is False, "unknown task safe response failed")

        failed_task = create_ready_task(fixture)
        failing_step = {
            "target_file": "broken.py",
            "change_type": "create_new_text_file",
            "replacement_text": "def broken(:\n",
            "purpose": "create failing fixture",
            "target_region": "new file",
        }
        fail_approved = approve_luxcode_task_step(failed_task["task_id"], approved_files=["broken.py"], patch_steps=[failing_step], repository_root=str(fixture))
        fail_prepared = advance_luxcode_task(failed_task["task_id"], "prepare_apply")
        fail_token = fail_prepared["apply_summary"]["approval_digest"]
        approve_luxcode_task_step(
            failed_task["task_id"],
            approved_files=["broken.py"],
            patch_steps=[failing_step],
            repository_root=str(fixture),
            approve_apply_execution=True,
            controlled_apply_approval_token=fail_token,
        )
        fail_applied = advance_luxcode_task(failed_task["task_id"], "apply")
        checks.check(fail_applied["current_state"] == "applied", "failing fixture apply should still apply")
        fail_verification = advance_luxcode_task(
            failed_task["task_id"],
            "prepare_verification",
            verification_checks=[{"check_type": "py_compile", "check_id": "compile_broken", "files": ["broken.py"]}],
        )
        fail_verify_token = fail_verification["verification_summary"]["verification_digest"]
        approve_luxcode_task_step(
            failed_task["task_id"],
            approved_files=["broken.py"],
            patch_steps=[failing_step],
            repository_root=str(fixture),
            approve_verification_execution=True,
            verification_approval_token=fail_verify_token,
        )
        recovery = advance_luxcode_task(failed_task["task_id"], "execute_verification")
        checks.check(recovery["current_state"] in {"recovery_review", "rollback_recommended"}, "verification failure must enter recovery")
        checks.check(recovery["recovery_summary"].get("recovery_decision") in {"generate_patch_revision", "rollback_recommended"}, "failure recovery decision missing")

    retry = advance_luxcode_task(create_luxcode_task("retry", repository_root=str(ROOT))["task_id"], "route")
    checks.check(retry["current_state"] == "routed", "deterministic transition route failed")
    deterministic_a = get_luxcode_task_status(retry["task_id"])
    deterministic_b = get_luxcode_task_status(retry["task_id"])
    checks.check(deterministic_a == deterministic_b, "task summary must be deterministic")

    paused = create_luxcode_task("pause", repository_root=str(ROOT))
    paused = pause_luxcode_task(paused["task_id"], "need approval")
    checks.check(paused["current_state"] == "paused", "pause failed")
    checks.check(paused["approval_state"] is not None, "pause must preserve state")
    checks.check(paused["next_safe_action"], "pause next safe action missing")
    paused_advance = advance_luxcode_task(paused["task_id"])
    checks.check(paused_advance["current_state"] == "paused", "paused task must not advance")
    resumed = resume_luxcode_task(paused["task_id"])
    checks.check(resumed["current_state"] == "created", "resume must return to checkpoint")
    checks.check(resumed["pending_steps"], "resumed pending steps missing")

    cancelled = create_luxcode_task("cancel", repository_root=str(ROOT))
    cancelled = cancel_luxcode_task(cancelled["task_id"], "no longer needed")
    checks.check(cancelled["current_state"] == "cancelled", "cancel failed")
    checks.check(cancelled["next_safe_action"], "cancel next safe action missing")
    cancelled_advance = advance_luxcode_task(cancelled["task_id"])
    checks.check(cancelled_advance["current_state"] == "cancelled", "cancelled task must not advance")

    insufficient = create_luxcode_task("", repository_root=str(ROOT))
    insufficient = advance_luxcode_task(insufficient["task_id"])
    checks.check(insufficient["current_state"] == "routed", "insufficient request must use safe fallback")
    checks.check(insufficient["route_result"].get("real_execution_blocked") is True, "default mode must not execute")

    status_counts = get_task_orchestrator_status()
    checks.check(status_counts["task_count"] >= 5, "task count missing")
    checks.check(status_counts["active_task_count"] >= 1, "active task count missing")
    checks.check(status_counts["paused_task_count"] >= 0, "paused task count missing")
    checks.check(status_counts["blocked_task_count"] >= 0, "blocked task count missing")
    checks.check(status_counts["completed_task_count"] >= 1, "completed task count missing")

    adjacent_task = create_luxcode_task("missing validation optional cleanup out_of_scope note", repository_root=str(ROOT), suspected_files=["app.py"])
    adjacent_task = advance_luxcode_task(adjacent_task["task_id"])
    adjacent_task = advance_luxcode_task(adjacent_task["task_id"])
    findings = adjacent_task.get("adjacent_findings", [])
    checks.check(isinstance(findings, list), "adjacent findings must be list")
    checks.check(all(item.get("scope_classification") for item in findings), "adjacent findings must be classified")
    checks.check(all(item.get("auto_added_to_patch_targets") is False for item in findings if item.get("scope_classification") != "required_for_current_task"), "non-required findings must not auto-apply")
    checks.check(adjacent_task.get("scope_expansion_blocked") is True, "scope expansion blocked flag missing")
    checks.check("static/index.html" in get_luxcode_task_status(adjacent_task["task_id"]).get("forbidden_files", []), "forbidden files must not silently expand")

    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    checks.check("luxcode_task_schema_endpoint" in app_source, "app schema endpoint missing")
    checks.check("luxcode_task_create_endpoint" in app_source, "app create endpoint missing")
    matrix_paths = {item["path"] for item in ENDPOINT_GROUPS.get("luxcode_task_orchestrator", [])}
    checks.check(matrix_paths == ENDPOINTS, "endpoint matrix records missing")
    checks.check(len(ENDPOINT_GROUPS.get("luxcode_task_orchestrator", [])) == 9, "endpoint matrix must have exactly nine records")
    smoke_source = (ROOT / "scripts" / "smoke_check.py").read_text(encoding="utf-8")
    checks.check("luxcode_task_orchestrator_local" in smoke_source, "targeted smoke registration missing")
    orchestrator_source = (ROOT / "luxcode_task_orchestrator.py").read_text(encoding="utf-8")
    checks.check("build_luxcode_master_router_preview" in orchestrator_source, "router engine not integrated")
    checks.check("analyze_lux_debug_request" in orchestrator_source, "debug engine not integrated")
    checks.check("build_safe_patch_draft" in orchestrator_source, "patch draft engine not integrated")
    checks.check("prepare_controlled_apply" in orchestrator_source and "execute_controlled_apply" in orchestrator_source, "controlled apply engine not integrated")
    checks.check("prepare_verification_run" in orchestrator_source and "execute_verification_run" in orchestrator_source, "verification engine not integrated")
    checks.check(".env" not in str(get_task_orchestrator_status()), ".env must not be stored")
    checks.check("api_key" not in str(get_task_orchestrator_status()).lower(), "secret fields must not be stored")
    checks.check("full repository contents" not in orchestrator_source.lower(), "full file body storage not allowed")
    checks.check("rollback_controlled_apply" not in orchestrator_source, "orchestrator must not execute rollback")
    checks.check("requests." not in orchestrator_source and "urlopen(" not in orchestrator_source, "no network calls allowed")
    checks.check("Layer 42" not in orchestrator_source and "layer 42" not in orchestrator_source.lower(), "Layer 42.x must not start")
    checks.check(all(sha(ROOT / rel) == digest for rel, digest in live_hashes.items()), "live LUXDEEP files changed during validator")
    checks.check((ROOT / ".luxcode_runtime").exists() is runtime_before, "live runtime state file created")
    checks.check(checks.count >= 75, f"expected at least 75 checks before final count, got {checks.count}")
    print(f"PASS luxcode task orchestrator validator: {checks.count} checks")


if __name__ == "__main__":
    main()
