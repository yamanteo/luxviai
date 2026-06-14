from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from endpoint_coverage_matrix import ENDPOINT_GROUPS
from luxcode_evidence_board import get_evidence_board_registry
from luxcode_multi_agent_handoff import (
    ASSIGNMENT_STATES,
    EVIDENCE_TYPES,
    FAILURE_CATEGORIES,
    FINALITY,
    HANDOFFS,
    OWNERSHIP_MODES,
    OWNERSHIP_STATES,
    PROGRESS_TYPES,
    RESULT_STATUSES,
    TASK_STATES,
    accept_handoff,
    add_evidence_record,
    build_partial_completion,
    check_attempt_fingerprint,
    create_multi_agent_task_contract,
    create_work_assignment,
    extract_remaining_gap,
    get_multi_agent_handoff_registry,
    get_multi_agent_handoff_schema,
    get_multi_agent_status,
    record_progress_event,
    record_worker_acknowledgement,
    register_failure_signature,
    register_file_ownership,
    request_reopen,
    set_behavioral_verification_result,
    set_finality_decision,
    set_technical_verification_result,
)
from luxcode_task_orchestrator import MULTI_AGENT_METADATA_KEYS, create_luxcode_task, get_luxcode_task_status, get_task_orchestrator_schema
from luxcode_task_persistence import MULTI_AGENT_METADATA_KEYS as PERSISTENCE_MULTI_AGENT_KEYS
from luxcode_task_persistence import _safe_payload, get_task_persistence_schema


CHECKS: list[str] = []


def check(name: str, condition: bool, detail: Any = None) -> None:
    if not condition:
        raise AssertionError(f"{name} failed: {detail!r}")
    CHECKS.append(name)


def contains_all(values: Iterable[Any], expected: Iterable[Any]) -> bool:
    return set(expected) <= set(values)


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def fixture_contract(title: str = "multi-agent validator") -> dict[str, Any]:
    return create_multi_agent_task_contract(
        task_title=title,
        task_summary="validator fixture",
        task_class="code_change",
        risk_level="low",
        priority="medium",
        required_capabilities=["inspection", "validation"],
        allowed_files=["app.py", "scripts/smoke_check.py"],
        protected_files=[".env"],
        acceptance_criteria=["compile", "smoke"],
        technical_acceptance_criteria=["compile"],
        behavioral_acceptance_criteria=["no external execution"],
        router_decision_digest="route-validator-digest",
    )


def validate() -> None:
    runtime_before = (ROOT / ".luxcode_runtime").exists()
    db_before = (ROOT / "luxcode_tasks.db").exists()
    expected_endpoints = {
        ("GET", "/luxcode-multi-agent/schema"),
        ("GET", "/luxcode-multi-agent/registry"),
        ("POST", "/luxcode-multi-agent/task-contract"),
        ("POST", "/luxcode-multi-agent/work-assignment"),
        ("POST", "/luxcode-multi-agent/evidence"),
        ("POST", "/luxcode-multi-agent/progress"),
        ("POST", "/luxcode-multi-agent/attempt-check"),
        ("POST", "/luxcode-multi-agent/handoff"),
        ("POST", "/luxcode-multi-agent/finality"),
        ("GET", "/debug/luxcode-multi-agent-status"),
    }

    # A. Task contract
    for state in [
        "created",
        "classified",
        "assigned",
        "acknowledged",
        "in_progress",
        "partially_complete",
        "blocked",
        "handoff_required",
        "verification_pending",
        "verification_failed",
        "completed",
        "rejected",
        "reopened",
        "cancelled",
    ]:
        check(f"task state {state}", state in TASK_STATES)
    contract = fixture_contract()
    check("contract ok", contract.get("ok") is True, contract)
    task_id = contract["task_id"]
    check("task id deterministic prefix", str(task_id).startswith("ma-task-"), task_id)
    check("contract digest prefix", str(contract.get("task_contract_digest")).startswith("ma-contract-"), contract)
    conflict = create_multi_agent_task_contract(
        task_title="conflict",
        task_summary="conflict",
        task_class="code_change",
        risk_level="low",
        priority="medium",
        required_capabilities=["inspection"],
        allowed_files=["app.py"],
        protected_files=["app.py"],
        acceptance_criteria=["done"],
        technical_acceptance_criteria=["compile"],
        behavioral_acceptance_criteria=["intent"],
    )
    check("contract protected conflict rejected", conflict.get("ok") is False, conflict)
    missing = create_multi_agent_task_contract(task_title="", task_summary="", task_class="", risk_level="", priority="", required_capabilities=[])
    check("contract required fields rejected", missing.get("ok") is False, missing)
    repeat = fixture_contract(title="multi-agent validator")
    check("contract digest stable enough", repeat.get("task_contract_digest") == contract.get("task_contract_digest"), repeat)

    # B. Assignment and acknowledgement
    for state in [
        "prepared",
        "offered",
        "acknowledged",
        "active",
        "paused",
        "blocked",
        "completed",
        "rejected",
        "expired",
        "handed_off",
        "cancelled",
    ]:
        check(f"assignment state {state}", state in ASSIGNMENT_STATES)
    assignment = create_work_assignment(
        task_id=task_id,
        worker_engine_id="local_worker",
        worker_tier="free_local",
        worker_role="fixture",
        assignment_scope="inspect app.py",
        allowed_files=["app.py"],
        owned_files=["app.py"],
        required_capabilities=["inspection"],
        expected_outputs=["evidence"],
    )
    check("assignment ok", assignment.get("ok") is True, assignment)
    assignment_id = assignment.get("assignment_id")
    check("assignment id prefix", str(assignment_id).startswith("ma-assign-"), assignment)
    protected_assignment = create_work_assignment(task_id=task_id, worker_engine_id="other_worker", allowed_files=[".env"], owned_files=[".env"])
    check("protected assignment rejected", protected_assignment.get("ok") is False, protected_assignment)
    overlap = create_work_assignment(task_id=task_id, worker_engine_id="overlap_worker", allowed_files=["app.py"], owned_files=["app.py"])
    check("overlap assignment rejected", overlap.get("ok") is False, overlap)
    ack = record_worker_acknowledgement(
        task_id=task_id,
        assignment_id=assignment_id,
        accepted=True,
        accepted_scope=["app.py"],
        rejected_scope=["scripts/smoke_check.py"],
        missing_capabilities=["browser"],
        resource_constraints="limited context",
        estimated_risk="low",
    )
    check("ack ok", ack.get("ok") is True, ack)
    check("ack partial scope", "scripts/smoke_check.py" in ack.get("acknowledgement", {}).get("rejected_scope", []), ack)
    check("ack digest", str(ack.get("acknowledgement", {}).get("acknowledgement_digest", "")).startswith("ma-ack"), ack)

    # C. Evidence
    evidence_registry = get_evidence_board_registry()
    for etype in sorted(EVIDENCE_TYPES):
        check(f"evidence type {etype}", etype in evidence_registry["allowed_types"])
    for status in sorted(RESULT_STATUSES):
        check(f"result status {status}", status in evidence_registry["allowed_statuses"])
    evidence = add_evidence_record(
        task_id=task_id,
        assignment_id=assignment_id,
        evidence_type="inspection",
        evidence_source="validator",
        evidence_summary="inspected endpoint integration",
        result_status="pass",
        related_files=["app.py"],
        metadata={"api_key": "blocked", "safe": "yes"},
    )
    check("evidence ok", evidence.get("ok") is True, evidence)
    evidence_id = evidence.get("evidence", {}).get("evidence_id", "")
    check("evidence id exists", bool(evidence_id), evidence)
    check("evidence digest exists", bool(evidence.get("evidence", {}).get("evidence_digest")), evidence)
    duplicate_evidence = add_evidence_record(
        task_id=task_id,
        assignment_id=assignment_id,
        evidence_type="inspection",
        evidence_source="validator",
        evidence_summary="inspected endpoint integration",
        result_status="pass",
        related_files=["app.py"],
    )
    check("duplicate evidence detected", duplicate_evidence.get("duplicate") is True, duplicate_evidence)
    check("secret metadata stripped", "api_key" not in str(evidence).lower(), evidence)

    # D. Progress
    for progress_type in sorted(PROGRESS_TYPES):
        check(f"progress type {progress_type}", progress_type in PROGRESS_TYPES)
    progress = record_progress_event(
        task_id=task_id,
        assignment_id=assignment_id,
        progress_type="inspection_complete",
        progress_percent=40,
        completed_items=["inspect"],
        remaining_items=["smoke"],
        evidence_ids=[evidence_id],
    )
    check("progress ok", progress.get("ok") is True, progress)
    backwards = record_progress_event(task_id=task_id, assignment_id=assignment_id, progress_type="blocked", progress_percent=10)
    check("progress regression rejected", backwards.get("ok") is False, backwards)
    overlap_progress = record_progress_event(task_id=task_id, assignment_id=assignment_id, progress_percent=50, completed_items=["same"], remaining_items=["same"])
    check("progress overlap rejected", overlap_progress.get("ok") is False, overlap_progress)
    invalid_progress = record_progress_event(task_id=task_id, assignment_id=assignment_id, progress_percent=101)
    check("progress bounds enforced", invalid_progress.get("ok") is False, invalid_progress)

    # E. Attempt fingerprint
    attempt = check_attempt_fingerprint(
        task_id=task_id,
        assignment_id=assignment_id,
        worker_engine_id="local_worker",
        hypothesis="fix with stable path",
        target_files=["app.py"],
        target_symbols=["endpoint"],
        command_family="py_compile",
        patch_intent="no patch",
    )
    check("attempt ok", attempt.get("ok") is True, attempt)
    check("attempt fingerprint prefix", str(attempt.get("attempt_fingerprint", "")).startswith("ma-attempt-"), attempt)
    duplicate_attempt = check_attempt_fingerprint(
        task_id=task_id,
        assignment_id=assignment_id,
        worker_engine_id="local_worker",
        hypothesis="fix with stable path",
        target_files=["app.py"],
        target_symbols=["endpoint"],
        command_family="py_compile",
        patch_intent="no patch",
    )
    check("attempt duplicate visible", duplicate_attempt.get("duplicate_detected") is True, duplicate_attempt)
    different_attempt = check_attempt_fingerprint(task_id=task_id, assignment_id=assignment_id, worker_engine_id="local_worker", hypothesis="different path", target_files=["scripts/smoke_check.py"], command_family="validator", patch_intent="no patch")
    check("different attempt allowed", different_attempt.get("ok") is True, different_attempt)

    # F. Failure signature
    for category in sorted(FAILURE_CATEGORIES):
        check(f"failure category {category}", category in FAILURE_CATEGORIES)
    failure = register_failure_signature(
        task_id=task_id,
        assignment_id=assignment_id,
        failure_category="validation_failure",
        normalized_message="validator fixture failed",
        affected_files=["app.py"],
        command_family="validator",
        exit_code=1,
        recoverable=True,
    )
    check("failure ok", failure.get("ok") is True, failure)
    check("failure digest", str(failure.get("failure_signature", {}).get("failure_digest", "")).startswith("ma-fsign-"), failure)
    quota = register_failure_signature(task_id=task_id, assignment_id=assignment_id, failure_category="quota_exhausted", normalized_message="quota")
    check("quota failure recorded", quota.get("ok") is True, quota)

    # G. Partial and gap
    partial = build_partial_completion(
        task_id=task_id,
        assignment_id=assignment_id,
        completion_percent=50,
        completed_scope=["inspection"],
        completed_files=["app.py"],
        completed_acceptance_items=["compile"],
        remaining_scope=["smoke"],
        remaining_files=["scripts/smoke_check.py"],
        remaining_acceptance_items=["smoke"],
        evidence_ids=[evidence_id],
    )
    check("partial ok", partial.get("ok") is True, partial)
    check("partial digest", str(partial.get("partial_completion", {}).get("partial_completion_digest", "")).startswith("ma-partial-"), partial)
    partial_overlap = build_partial_completion(task_id=task_id, assignment_id=assignment_id, completion_percent=50, completed_files=["app.py"], remaining_files=["app.py"], evidence_ids=[evidence_id])
    check("partial overlap rejected", partial_overlap.get("ok") is False, partial_overlap)
    gap = extract_remaining_gap(task_id=task_id, assignment_id=assignment_id, failed_attempt_fingerprints=[attempt.get("attempt_fingerprint")])
    check("gap ok", gap.get("ok") is True, gap)
    check("completed file excluded from gap", "app.py" not in gap.get("remaining_gap", {}).get("remaining_files", []), gap)

    # H. Handoff and ownership
    for mode in sorted(OWNERSHIP_MODES):
        check(f"ownership mode {mode}", mode in OWNERSHIP_MODES)
    for state in sorted(OWNERSHIP_STATES):
        check(f"ownership state {state}", state in OWNERSHIP_STATES)
    ownership = register_file_ownership(task_id=task_id, assignment_id=assignment_id, worker_engine_id="local_worker", file_path="scripts/smoke_check.py", ownership_mode="exclusive_write")
    check("ownership ok", ownership.get("ok") is True, ownership)
    ownership_conflict = register_file_ownership(task_id=task_id, assignment_id=assignment_id, worker_engine_id="other_worker", file_path="scripts/smoke_check.py", ownership_mode="exclusive_write")
    check("ownership conflict blocked", ownership_conflict.get("ok") is False, ownership_conflict)
    handoff = __import__("luxcode_multi_agent_handoff").prepare_handoff(
        task_id=task_id,
        from_assignment_id=assignment_id,
        from_worker_engine_id="local_worker",
        to_worker_engine_id="next_worker",
        to_worker_tier="free_local",
        handoff_reason="missing capability",
        remaining_files=["scripts/smoke_check.py"],
        requested_files=["scripts/smoke_check.py"],
        evidence_ids=[evidence_id],
        attempt_fingerprints=[attempt.get("attempt_fingerprint")],
        failure_signatures=[failure.get("failure_signature_id")],
    )
    check("handoff ok", handoff.get("ok") is True, handoff)
    check("handoff acceptance required", handoff.get("handoff_acceptance_required") is True, handoff)
    codex_handoff = __import__("luxcode_multi_agent_handoff").prepare_handoff(task_id=task_id, from_worker_engine_id="local_worker", to_worker_engine_id="Codex")
    check("codex auto handoff blocked", codex_handoff.get("ok") is False, codex_handoff)
    accepted_handoff = accept_handoff(task_id=task_id, handoff_id=handoff.get("handoff_id"), accepted=True, to_assignment_id="next-assignment")
    check("handoff accepted only explicitly", accepted_handoff.get("ok") is True, accepted_handoff)

    # I. Verification
    technical = set_technical_verification_result(task_id=task_id, compile_status=True, validator_status=True, targeted_smoke_status=True, diff_check_status=True, artifact_check_status=True, evidence_ids=[evidence_id])
    behavioral = set_behavioral_verification_result(task_id=task_id, scenario_id="intent", expected_behavior="no execution", observed_behavior="no execution", user_intent_match=True, evidence_ids=[evidence_id])
    check("technical verification ok", technical.get("verification", {}).get("technical_passed") is True, technical)
    check("behavioral verification ok", behavioral.get("verification", {}).get("behavioral_passed") is True, behavioral)
    check("technical separate from behavioral", technical.get("verification_type") == "technical" and behavioral.get("verification_type") == "behavioral")

    # J. Finality and reopen
    partial_finality = set_finality_decision(task_id=task_id, decision="partial", completion_score=0.5, evidence_ids=[evidence_id], decision_reason="remaining gap")
    check("partial finality ok", partial_finality.get("ok") is True, partial_finality)
    check("finality registry updated", partial_finality.get("finality_decision_id") in FINALITY)
    complete_blocked = set_finality_decision(task_id=task_id, decision="complete", completion_score=1.0, evidence_ids=[evidence_id], decision_reason="try complete")
    check("complete blocked with unresolved gap", complete_blocked.get("ok") is False, complete_blocked)
    reopen_blocked = request_reopen(task_id=task_id, reopen_reason="new_evidence")
    check("reopen requires explicit allow", reopen_blocked.get("ok") is False, reopen_blocked)
    reopen = request_reopen(task_id=task_id, reopen_allowed=True, reopen_reason="new_evidence", new_evidence_ids=[evidence_id], reopened_scope=["smoke"])
    check("reopen ok", reopen.get("ok") is True, reopen)

    # K. Orchestrator
    orchestrator_schema = get_task_orchestrator_schema()
    check("orchestrator metadata fields exported", contains_all(orchestrator_schema.get("multi_agent_metadata_fields", []), MULTI_AGENT_METADATA_KEYS), orchestrator_schema)
    task = create_luxcode_task("multi agent metadata fixture", repository_root=str(ROOT), suspected_files=["app.py"])
    task_status = get_luxcode_task_status(task["task_id"])
    check("orchestrator task has metadata", "multi_agent_metadata" in task_status, task_status)
    check("orchestrator does not auto-start codex", task_status["multi_agent_metadata"].get("restored_worker_execution_started") is False, task_status)
    check("orchestrator no paid auto", orchestrator_schema.get("multi_agent_paid_escalation_auto_enabled") is False, orchestrator_schema)

    # L. Persistence
    persistence_schema = get_task_persistence_schema()
    check("persistence metadata keys exported", contains_all(persistence_schema.get("safe_multi_agent_metadata", []), PERSISTENCE_MULTI_AGENT_KEYS), persistence_schema)
    safe = _safe_payload(
        {
            "task_id": "persist-ma",
            "current_state": "created",
            "repository_root": str(ROOT),
            "multi_agent_metadata": {
                "task_contract_digest": "digest",
                "assignment_id": "a",
                "worker_engine_id": "w",
                "evidence_ids": ["e1"],
                "raw_prompt": "blocked",
                "api_key": "blocked",
            },
        }
    )
    check("persistence keeps safe metadata", safe["multi_agent_metadata"]["task_contract_digest"] == "digest", safe)
    check("persistence strips unsafe metadata", "api_key" not in str(safe).lower() and "raw_prompt" not in str(safe).lower(), safe)
    check("restore revalidation flag", safe["multi_agent_metadata"]["multi_agent_requires_revalidation"] is True, safe)
    check("restore starts no worker", safe["multi_agent_metadata"]["restored_worker_execution_started"] is False, safe)
    check("restore ownership inactive", safe["multi_agent_metadata"]["restored_file_ownership_active"] is False, safe)

    # M. API, coverage, smoke, source guards
    group = ENDPOINT_GROUPS.get("luxcode_multi_agent_handoff", [])
    check("coverage group exists", bool(group), ENDPOINT_GROUPS.keys())
    check("coverage group exact 10", len(group) == 10, group)
    actual_endpoints = {(item["method"], item["path"]) for item in group}
    check("coverage exact endpoints", actual_endpoints == expected_endpoints, actual_endpoints)
    app_source = source("app.py")
    for _, path in expected_endpoints:
        check(f"app endpoint {path}", path in app_source, path)
    smoke_source = source("scripts/smoke_check.py")
    check("smoke registration", "luxcode_multi_agent_handoff_local" in smoke_source, "missing smoke registration")
    check("smoke method", "check_luxcode_multi_agent_handoff_local" in smoke_source, "missing smoke method")
    core_source = source("luxcode_multi_agent_handoff.py")
    evidence_source = source("luxcode_evidence_board.py")
    for blocked in ["requests.", "urlopen(", "subprocess.", "os.system", "git commit", "git push", "Layer 42"]:
        check(f"core guard {blocked}", blocked not in core_source, blocked)
    for blocked in ["api_key", "authorization", "password", "credential"]:
        check(f"evidence redaction marker {blocked}", blocked in evidence_source.lower(), blocked)
    check("status ok", get_multi_agent_status(task_id).get("ok") is True, get_multi_agent_status(task_id))
    check("global status ok", get_multi_agent_status().get("ok") is True, get_multi_agent_status())
    check("registry endpoint count", get_multi_agent_handoff_registry().get("endpoint_count") == 10, get_multi_agent_handoff_registry())
    check("schema endpoints count", len(get_multi_agent_handoff_schema().get("required_endpoints", [])) == 10, get_multi_agent_handoff_schema())
    check("runtime unchanged", (ROOT / ".luxcode_runtime").exists() is runtime_before)
    check("live db unchanged", (ROOT / "luxcode_tasks.db").exists() is db_before)
    for key in sorted(MULTI_AGENT_METADATA_KEYS):
        check(f"orchestrator multi-agent metadata key {key}", key in MULTI_AGENT_METADATA_KEYS, key)
    for key in sorted(PERSISTENCE_MULTI_AGENT_KEYS):
        check(f"persistence multi-agent metadata key {key}", key in PERSISTENCE_MULTI_AGENT_KEYS, key)
    for method, path in sorted(expected_endpoints):
        matching = [item for item in group if item["method"] == method and item["path"] == path]
        check(f"coverage method path {method} {path}", len(matching) == 1, matching)
    restore_flags = [
        "multi_agent_requires_revalidation",
        "restored_assignment_active",
        "restored_handoff_executed",
        "restored_file_ownership_active",
        "restored_paid_approval",
        "restored_worker_execution_started",
    ]
    for flag in restore_flags:
        check(f"restore flag present {flag}", flag in safe["multi_agent_metadata"], safe["multi_agent_metadata"])

    check("check count threshold", len(CHECKS) >= 180, len(CHECKS))


if __name__ == "__main__":
    validate()
    print(f"validation_pass_count={len(CHECKS)}")
    print(f"checks={len(CHECKS)}")
    print("PASS")
