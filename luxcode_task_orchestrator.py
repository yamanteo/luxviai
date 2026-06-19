from __future__ import annotations

import hashlib
import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from lux_controlled_apply_engine import execute_controlled_apply, prepare_controlled_apply
from lux_debug_intelligence_core import analyze_lux_debug_request
from lux_safe_patch_draft_engine import build_safe_patch_draft
from lux_verification_recovery_engine import (
    analyze_verification_results,
    execute_verification_run,
    prepare_recovery_action,
    prepare_verification_run,
)
from luxcode_master_router_preview import build_luxcode_master_router_preview
from luxcode_autonomy_permission_controller import (
    approve_scope_expansion,
    create_permission_profile,
    evaluate_requested_action,
    get_autonomy_permission_status,
    get_safe_permission_metadata,
    revoke_scope_access,
)
from luxcode_task_persistence import (
    archive_task_state,
    delete_task_state,
    get_task_persistence_status,
    initialize_task_store,
    list_task_states,
    load_task_state,
    restore_active_tasks,
    save_task_state,
)
from luxcode_terminal_process_runtime import (
    cancel_terminal_runtime,
    execute_terminal_action,
    get_safe_runtime_metadata,
    plan_terminal_action,
)
from luxcode_tier1_local_worker import (
    TIER1_OLLAMA_MODEL_ID,
    TIER1_OLLAMA_RUNTIME_ID,
    execute_tier0_router_tier1_preview,
)
from luxcode_gemini_task_bridge import (
    execute_gemini_task_bridge,
)
from luxcode_free_cloud_task_bridge import (
    FREE_CLOUD_PRIMARY_MODEL_ID,
    execute_free_cloud_task_bridge,
)
from luxcode_direct_deepseek_task_bridge import (
    DIRECT_DEEPSEEK_MODEL_ID,
    EXACT_APPROVAL_TEXT as DEEPSEEK_EXACT_APPROVAL_TEXT,
    build_direct_deepseek_task_approval,
    execute_direct_deepseek_task_bridge,
)
from luxcode_codewhale_task_bridge import (
    EXACT_APPROVAL_TEXT as CODEWHALE_EXACT_APPROVAL_TEXT,
    build_codewhale_task_approval,
    execute_codewhale_task_bridge,
)
from luxcode_codex_task_bridge import (
    EXACT_APPROVAL_TEXT as CODEX_EXACT_APPROVAL_TEXT,
    build_codex_task_approval,
    execute_codex_task_bridge,
)
from luxcode_zero_cost_execution_router import (
    classify_zero_cost_task,
    capability_match_zero_cost_engine,
    evaluate_zero_cost_availability,
    get_zero_cost_router_policy,
    route_zero_cost_task,
    score_zero_cost_task,
    validate_zero_cost_route_decision,
)
from luxcode_live_app_interaction_testing import (
    cancel_live_test_runtime,
    execute_live_test,
    get_safe_live_test_metadata,
    plan_live_test,
)
from luxcode_local_network_access_intelligence import (
    cancel_network_access_runtime,
    create_network_access_plan,
    execute_network_access_plan,
    get_safe_network_access_metadata,
)
from luxcode_test_matrix_intelligence import (
    build_test_matrix_plan,
    execute_test_matrix,
    get_safe_test_matrix_metadata,
)
from luxcode_deployment_execution_url_verification import (
    build_deployment_plan,
    cancel_deployment,
    execute_deployment,
    get_safe_deployment_metadata,
)
from luxcode_render_provider_adapter import (
    analyze_render_readiness,
    build_render_deployment_plan,
    execute_render_dry_run,
    get_safe_render_metadata,
)
from luxcode_render_execution_gateway import (
    build_render_execution_request,
    evaluate_render_execution_authority,
    execute_render_gateway,
    get_safe_render_gateway_metadata,
)
from luxcode_render_credential_readiness_broker import (
    build_render_readiness_package,
    get_safe_render_readiness_metadata,
    issue_render_readiness_seal,
)


TASK_STATES = {
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
    "verified",
    "recovery_review",
    "rollback_recommended",
    "completed",
    "blocked",
    "failed",
    "cancelled",
    "paused",
    "test_matrix_planned",
    "test_matrix_running",
    "test_matrix_review",
    "test_matrix_completed",
    "test_matrix_blocked",
    "browser_selection_planned",
    "browser_selected",
    "browser_launching",
    "browser_identity_verifying",
    "browser_launch_completed",
    "browser_launch_blocked",
    "browser_identity_mismatch",
    "deployment_planned",
    "deployment_running",
    "deployment_verified",
    "deployment_blocked",
    "deployment_review",
    "render_planned",
    "render_gateway_planned",
    "render_gateway_running",
    "render_gateway_verified",
    "render_gateway_blocked",
    "render_readiness_packaged",
    "render_readiness_sealed",
    "render_readiness_blocked",
    "render_dry_run_completed",
    "render_blocked",
    "awaiting_scope_permission",
    "awaiting_irreversible_confirmation",
    "autonomy_paused",
    "budget_exhausted",
}

TERMINAL_STATES = {"cancelled", "blocked", "failed", "completed"}
EXECUTION_BLOCKED_STATES = TERMINAL_STATES | {"paused", "awaiting_scope_permission", "awaiting_irreversible_confirmation", "autonomy_paused", "budget_exhausted"}
SAFE_INVARIANTS = {
    "scope_expansion_blocked": True,
    "destructive_action_blocked": True,
    "external_api_used": False,
    "local_first": True,
}
DEFAULT_FORBIDDEN_FILES = [".env", "static/index.html"]
ZERO_COST_ROUTING_REQUIRED_KEYS = {
    "router_policy_version",
    "policy_version",
    "task_class",
    "secondary_task_classes",
    "difficulty_score",
    "risk_level",
    "required_capabilities",
    "required_engine_plan",
    "fallback_chain",
    "skipped_engines",
    "selected_tier",
    "selected_engine",
    "route_decision_digest",
    "routing_state",
    "routing_state_reason",
    "routing_updated_at",
    "paid_escalation_required",
    "paid_escalation_allowed",
    "recommended_paid_engine",
    "engine_health_snapshot",
}
MULTI_AGENT_METADATA_KEYS = {
    "task_contract_digest",
    "active_assignment_id",
    "active_worker_engine_id",
    "active_worker_tier",
    "assignment_state",
    "evidence_board_digest",
    "latest_progress_event_id",
    "attempt_fingerprints",
    "failure_signatures",
    "partial_completion_digest",
    "remaining_gap_digest",
    "active_handoff_id",
    "file_ownership_state",
    "technical_verification_state",
    "behavioral_verification_state",
    "finality_state",
    "reopen_state",
    "multi_agent_updated_at",
}
CODER_RUNTIME_METADATA_KEYS = {
    "coder_intake_id",
    "coder_intake_state",
    "coder_search_digest",
    "minimum_context_package_id",
    "minimum_context_digest",
    "coder_plan_id",
    "coder_plan_state",
    "patch_id",
    "patch_preview_state",
    "patch_execution_id",
    "patch_execution_state",
    "snapshot_id",
    "validation_plan_id",
    "validation_state",
    "rollback_state",
    "coder_result_id",
    "coder_remaining_gap",
    "coder_handoff_ready",
    "coder_updated_at",
    "coder_requires_revalidation",
    "restored_patch_apply_allowed",
    "restored_approval_valid",
    "restored_snapshot_trusted",
    "restored_validation_passed",
    "restored_worker_started",
    "restored_execution_resumed",
    "coder_cli_session_id",
    "coder_cli_run_id",
    "coder_cli_last_command",
    "coder_cli_session_state",
    "coder_cli_last_result_digest",
    "coder_cli_output_manifest",
    "coder_cli_approval_required",
    "coder_cli_revalidation_required",
    "coder_cli_completed_scope",
    "coder_cli_remaining_gap",
    "coder_cli_updated_at",
}

_TASKS: Dict[str, Dict[str, Any]] = {}
_PERSISTENCE_CONFIG: Dict[str, Any] = {"mode": "disabled", "storage_root": "", "enabled": False}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "lux-task-" + hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()[:32]


def _unique(items: Iterable[Any]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).replace("\\", "/").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _safe_root(repository_root: Optional[str]) -> str:
    if not repository_root:
        return ""
    try:
        return str(Path(repository_root).resolve())
    except OSError:
        return str(repository_root)


def _file_hashes(repository_root: str, files: List[str]) -> Dict[str, str]:
    root = Path(repository_root)
    hashes: Dict[str, str] = {}
    for rel in files:
        path = (root / rel).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            continue
        if path.exists() and path.is_file():
            hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        clean: Dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(secret in lowered for secret in ("secret", "api_key", "token", "password", ".env")):
                continue
            clean[key] = _redact(item)
        return clean
    if isinstance(value, list):
        return [_redact(item) for item in value[:40]]
    if isinstance(value, str):
        if ".env" in value or len(value) > 2000:
            return value[:2000].replace(".env", "[redacted-env]")
    return value


def _normalize_list(values: Any) -> List[str]:
    if not values:
        return []
    if isinstance(values, (list, tuple, set)):
        return [str(item).strip() for item in values if str(item).strip()]
    return [str(values).strip()] if str(values).strip() else []


def _default_multi_agent_metadata() -> Dict[str, Any]:
    return {
        "task_contract_digest": "",
        "active_assignment_id": "",
        "active_worker_engine_id": "",
        "active_worker_tier": "",
        "assignment_state": "",
        "evidence_board_digest": "",
        "latest_progress_event_id": "",
        "attempt_fingerprints": [],
        "failure_signatures": [],
        "partial_completion_digest": "",
        "remaining_gap_digest": "",
        "active_handoff_id": "",
        "file_ownership_state": "inactive",
        "technical_verification_state": "unknown",
        "behavioral_verification_state": "unknown",
        "finality_state": "not_finalized",
        "reopen_state": "closed",
        "multi_agent_updated_at": _now(),
        "multi_agent_requires_revalidation": False,
        "restored_assignment_active": False,
        "restored_handoff_executed": False,
        "restored_file_ownership_active": False,
        "restored_paid_approval": False,
        "restored_worker_execution_started": False,
    }


def _safe_multi_agent_metadata(task: Dict[str, Any]) -> Dict[str, Any]:
    metadata = _default_multi_agent_metadata()
    raw = task.get("multi_agent_metadata", {})
    if isinstance(raw, dict):
        for key in MULTI_AGENT_METADATA_KEYS:
            if key in raw:
                metadata[key] = _redact(raw[key])
    return metadata


def _default_coder_runtime_metadata() -> Dict[str, Any]:
    return {
        "coder_intake_id": "",
        "coder_intake_state": "not_started",
        "coder_search_digest": "",
        "minimum_context_package_id": "",
        "minimum_context_digest": "",
        "coder_plan_id": "",
        "coder_plan_state": "not_started",
        "patch_id": "",
        "patch_preview_state": "not_started",
        "patch_execution_id": "",
        "patch_execution_state": "not_started",
        "snapshot_id": "",
        "validation_plan_id": "",
        "validation_state": "not_started",
        "rollback_state": "not_started",
        "coder_result_id": "",
        "coder_remaining_gap": [],
        "coder_handoff_ready": False,
        "coder_updated_at": _now(),
        "coder_requires_revalidation": False,
        "restored_patch_apply_allowed": False,
        "restored_approval_valid": False,
        "restored_snapshot_trusted": False,
        "restored_validation_passed": False,
        "restored_worker_started": False,
        "restored_execution_resumed": False,
        "coder_cli_session_id": "",
        "coder_cli_run_id": "",
        "coder_cli_last_command": "",
        "coder_cli_session_state": "",
        "coder_cli_last_result_digest": "",
        "coder_cli_output_manifest": "",
        "coder_cli_approval_required": False,
        "coder_cli_revalidation_required": False,
        "coder_cli_completed_scope": [],
        "coder_cli_remaining_gap": [],
        "coder_cli_updated_at": _now(),
    }


def _safe_coder_runtime_metadata(task: Dict[str, Any]) -> Dict[str, Any]:
    metadata = _default_coder_runtime_metadata()
    raw = task.get("coder_runtime_metadata", {})
    if isinstance(raw, dict):
        for key in CODER_RUNTIME_METADATA_KEYS:
            if key in raw:
                metadata[key] = _redact(raw[key])
    return metadata


def _build_zero_cost_route_metadata(task: Dict[str, Any]) -> Dict[str, Any]:
    task_id = str(task.get("task_id") or "")
    title = str(task.get("original_request") or "")
    files = _normalize_list(task.get("selected_files", []))
    user_requires_free_only = bool(task.get("user_requires_free_only", True))
    selected_capabilities = _normalize_list(task.get("selected_capabilities", []))
    classification = classify_zero_cost_task(
        task_id=task_id,
        title=title,
        description=title,
        requested_capabilities=selected_capabilities,
        selected_files=files,
        risk_hint="low",
        user_requires_free_only=user_requires_free_only,
        prior_failures=0,
        retry_count=0,
    )
    task_class = str(classification.get("task_class") or "unknown")
    scored = score_zero_cost_task(
        task_id=task_id,
        task_class=task_class,
        title=title,
        description=title,
        required_capabilities=selected_capabilities or classification.get("required_capabilities", []),
        selected_files=files,
        risk_level=classification.get("risk_level", "low"),
        failed_attempts=0,
        unknown_root_causes=0,
        user_rejections=0,
    )
    matched = capability_match_zero_cost_engine(
        task_id=task_id,
        task_class=task_class,
        required_capabilities=selected_capabilities or scored.get("required_capabilities", []),
        forbidden_capabilities=classification.get("forbidden_capabilities", []),
        risk_level=classification.get("risk_level") or scored.get("risk_level") or "low",
        requested_tiers=_normalize_list(classification.get("selected_tier_ids", [])),
        user_requires_free_only=user_requires_free_only,
    )
    policy = get_zero_cost_router_policy()
    availability = evaluate_zero_cost_availability(
        task_id=task_id,
        engine_health_overrides=_sanitize_route_engine_states(matched.get("matched_tiers", [])),
        user_requires_network=bool(task.get("network_access_needed", False)),
        policy=policy,
    )
    route_decision = route_zero_cost_task(
        task_id=task_id,
        title=title,
        description=title,
        task_class=task_class,
        required_capabilities=_normalize_list(scored.get("required_capabilities", [])),
        forbidden_capabilities=classification.get("forbidden_capabilities", []),
        risk_level=classification.get("risk_level") or scored.get("risk_level") or "low",
        selected_files=files,
        difficulty_score=scored.get("difficulty_score", 5),
        failure_history={},
        availability=availability,
        policy=policy,
        resource_pressure=False,
        user_requires_free_only=user_requires_free_only,
        previous_attempts=0,
        user_rejection_count=0,
        direct_user_constraints={},
    )
    validation = validate_zero_cost_route_decision(task_id, route_decision, policy=policy)
    route_result = _redact(route_decision)
    safe_policy = route_result.get("policy_flags", {}) if isinstance(route_result.get("policy_flags"), dict) else {}
    required_capabilities = _normalize_list(route_result.get("required_capabilities", []))
    if not required_capabilities:
        required_capabilities = _normalize_list(scored.get("required_capabilities", []))
    return {
        "router_policy_version": str(classification.get("policy_version") or route_result.get("policy_version", "")),
        "task_class": task_class,
        "secondary_task_classes": _normalize_list(classification.get("secondary_classes", [])),
        "difficulty_score": int(scored.get("difficulty_score", 0)),
        "risk_level": str(scored.get("risk_level") or classification.get("risk_level") or "low"),
        "required_capabilities": required_capabilities,
        "required_engine_plan": _normalize_list(route_result.get("required_engine_plan", [])),
        "fallback_chain": _normalize_list(route_result.get("fallback_chain", [])),
        "skipped_engines": _normalize_list(route_result.get("skipped_engines", [])),
        "selected_tier": str(route_result.get("selected_primary_tier", "")),
        "selected_engine": str(route_result.get("selected_primary_engine", "")),
        "route_decision_digest": str(route_result.get("decision_digest", "")),
        "routing_state": str(route_result.get("routing_state", "")),
        "routing_state_reason": str(route_result.get("routing_state_reason", "")),
        "routing_updated_at": _now(),
        "routing_requires_revalidation": bool(task.get("routing_requires_revalidation", False)),
        "restored_route_executed": bool(task.get("restored_route_executed", False)),
        "paid_escalation_required": bool(route_result.get("paid_escalation_required", False)),
        "paid_escalation_allowed": bool(
            (not user_requires_free_only)
            and bool(route_result.get("paid_escalation_allowed", False))
            and bool(classification.get("user_requires_free_only") is False),
        ),
        "recommended_paid_engine": route_result.get("recommended_paid_engine", ""),
        "engine_health_snapshot": _redact(_normalize_dict(route_result.get("engine_health_snapshot", {}))),
        "routing_reasons": _normalize_list(route_result.get("decision_reasons", [])),
        "routing_replayable": bool(route_result.get("decision_source") == "deterministic_local_planner"),
        "routing_valid": bool(validation.get("ok", False)),
        "routing_validation_errors": _normalize_list(validation.get("errors", [])),
        "route_result": route_result,
        "user_network_allowed": bool(safe_policy.get("network_allowed")),
    }


def _sanitize_route_engine_states(matched_tiers: List[Dict[str, Any]]) -> Dict[str, Any]:
    state_map: Dict[str, str] = {}
    for tier in matched_tiers[:20]:
        if isinstance(tier, dict):
            tier_id = str(tier.get("tier_id", ""))
            if tier_id:
                state_map[tier_id] = "available"
    return {"availability": state_map}


def _normalize_dict(payload: Any) -> Dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def _classify_adjacent(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for item in raw or []:
        text = _stable_json(item).lower()
        if "directly_related" in text or "required" in text:
            scope = "required_for_current_task"
        elif "optional" in text or "nice" in text:
            scope = "optional_improvement"
        elif "out_of_scope" in text or "unrelated" in text:
            scope = "out_of_scope"
        else:
            scope = "recommended_follow_up"
        finding = dict(item)
        finding["scope_classification"] = scope
        finding["auto_added_to_patch_targets"] = scope == "required_for_current_task"
        findings.append(finding)
    return findings


def _make_patch_id(task: Dict[str, Any]) -> str:
    draft = task.get("patch_draft_result", {})
    return draft.get("request_id") or _digest([task["task_id"], task.get("selected_files"), task.get("original_request")])


def _patch_steps(task: Dict[str, Any], supplied: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    if supplied is not None:
        return deepcopy(supplied)
    approved = task.get("approval_state", {}).get("patch_steps")
    if approved:
        return deepcopy(approved)
    return deepcopy(task.get("patch_draft_result", {}).get("patch_steps", []))


def _approval_snapshot(
    task: Dict[str, Any],
    patch_id: str,
    patch_steps: List[Dict[str, Any]],
    approved_files: List[str],
    expected_hashes: Dict[str, str],
) -> Dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "patch_id": patch_id,
        "patch_digest": _digest({"patch_id": patch_id, "steps": patch_steps}),
        "approved_files": approved_files,
        "repository_root": task["repository_root"],
        "expected_file_hashes": expected_hashes,
        "patch_steps": patch_steps,
    }


def _approval_valid(task: Dict[str, Any]) -> Tuple[bool, str]:
    approval = task.get("approval_state", {})
    snapshot = approval.get("approval_snapshot") or {}
    if not approval.get("approved"):
        return False, "explicit task approval is required"
    current = _approval_snapshot(
        task,
        snapshot.get("patch_id", ""),
        _patch_steps(task),
        _unique(snapshot.get("approved_files", [])),
        dict(snapshot.get("expected_file_hashes", {})),
    )
    if current != snapshot:
        approval["approved"] = False
        approval["invalidated_reason"] = "approval-bound patch, file list, repository root, hashes, or steps changed"
        return False, approval["invalidated_reason"]
    return True, ""


def _pending_for_state(state: str) -> List[str]:
    order = [
        "route",
        "diagnose",
        "draft_patch",
        "approve_patch",
        "prepare_apply",
        "apply",
        "prepare_verification",
        "execute_verification",
        "review_recovery",
        "complete",
    ]
    completed_by_state = {
        "created": 0,
        "routed": 1,
        "diagnosis_ready": 2,
        "patch_ready": 3,
        "awaiting_approval": 3,
        "approval_verified": 4,
        "apply_prepared": 5,
        "applied": 6,
        "verification_prepared": 7,
        "verified": 9,
        "recovery_review": 9,
        "rollback_recommended": 9,
        "completed": 10,
    }
    return order[completed_by_state.get(state, 0) :]


def _summary(task: Dict[str, Any]) -> Dict[str, Any]:
    state = task["current_state"]
    can_advance = state not in EXECUTION_BLOCKED_STATES and state != "awaiting_approval"
    if state == "approval_verified":
        can_advance = True
    if state == "apply_prepared":
        can_advance = bool(task.get("approval_state", {}).get("apply_execution_approved"))
    if state == "verification_prepared":
        can_advance = bool(task.get("approval_state", {}).get("verification_execution_approved"))
    return {
        "task_id": task["task_id"],
        "current_state": state,
        "status": state,
        "active_engine": str(task.get("active_engine") or "-"),
        "active_model": str(task.get("active_model") or "-"),
        "real_attempts": _redact(task.get("model_attempts", [])),
        "evidence": _redact(task.get("model_evidence", [])),
        "token_usage": str(task.get("token_usage") or "unavailable"),
        "provider_cost": str(task.get("provider_cost") or "cost_status=unavailable"),
        "deepseek_escalation": _redact(task.get("deepseek_escalation", {})),
        "codewhale_escalation": _redact(task.get("codewhale_escalation", {})),
        "codex_escalation": _redact(task.get("codex_escalation", {})),
        "external_api_used": bool(task.get("external_api_used", False)),
        "network_access_used": bool(task.get("network_access_used", False)),
        "original_request": task["original_request"],
        "repository_root": task["repository_root"],
        "route_result": _redact(task.get("route_result", {})),
        "zero_cost_routing": _redact(task.get("zero_cost_routing", {})),
        "diagnosis_summary": _redact(task.get("diagnosis_result", {})),
        "patch_summary": _redact(task.get("patch_draft_result", {})),
        "approval_state": _redact(task.get("approval_state", {})),
        "apply_summary": _redact(task.get("apply_result", {})),
        "verification_summary": _redact(task.get("verification_result", {})),
        "recovery_summary": _redact(task.get("recovery_result", {})),
        "selected_files": list(task.get("selected_files", [])),
        "changed_files": list(task.get("changed_files", [])),
        "forbidden_files": list(task.get("forbidden_files", [])),
        "adjacent_findings": _redact(task.get("adjacent_findings", [])),
        "completed_steps": list(task.get("completed_steps", [])),
        "pending_steps": _pending_for_state(state),
        "blocked_reasons": list(task.get("blocked_reasons", [])),
        "next_safe_action": task.get("next_safe_action", ""),
        "persistence_status": dict(task.get("persistence_status", {})),
        "persistence_warning": task.get("persistence_warning", ""),
        "restored_from_persistence": bool(task.get("restored_from_persistence", False)),
        "requires_explicit_resume": bool(task.get("requires_explicit_resume", False)),
        "execution_triggered_on_restore": bool(task.get("execution_triggered_on_restore", False)),
        "routing_requires_revalidation": bool(task.get("routing_requires_revalidation", False)),
        "routing_update_count": int(task.get("routing_update_count", 0)),
        "zero_cost_routing_state": str(task.get("routing_state", "")),
        "multi_agent_metadata": _safe_multi_agent_metadata(task),
        "coder_runtime_metadata": _safe_coder_runtime_metadata(task),
        "permission_profile": _redact(task.get("permission_profile", {})),
        "safe_permission_metadata": _redact(task.get("safe_permission_metadata", {})),
        "permission_audit": _redact(task.get("permission_audit", [])),
        "last_permission_evaluation": _redact(task.get("last_permission_evaluation", {})),
        "scope_expansion_request": _redact(task.get("scope_expansion_request", {})),
        "terminal_runtime_plan": _redact(task.get("terminal_runtime_plan", {})),
        "terminal_runtime_result": _redact(task.get("terminal_runtime_result", {})),
        "live_test_plan": _redact(task.get("live_test_plan", {})),
        "live_test_result": _redact(task.get("live_test_result", {})),
        "network_access_plan": _redact(task.get("network_access_plan", {})),
        "network_access_result": _redact(task.get("network_access_result", {})),
        "test_matrix_plan": _redact(task.get("test_matrix_plan", {})),
        "selected_targets": _redact(task.get("selected_targets", [])),
        "matrix_execution_state": task.get("matrix_execution_state", ""),
        "matrix_summary": _redact(task.get("matrix_summary", {})),
        "matrix_failures": _redact(task.get("matrix_failures", [])),
        "matrix_required_for_completion": bool(task.get("matrix_required_for_completion", False)),
        "browser_launch_state": task.get("browser_launch_state", ""),
        "browser_identity_state": task.get("browser_identity_state", ""),
        "browser_launch_failures": _redact(task.get("browser_launch_failures", [])),
        "browser_identity_mismatches": _redact(task.get("browser_identity_mismatches", [])),
        "deployment_intent": bool(task.get("deployment_intent", False)),
        "deployment_provider": task.get("deployment_provider", ""),
        "deployment_plan_id": task.get("deployment_plan", {}).get("deployment_plan_id", ""),
        "deployment_runtime_id": task.get("deployment_result", {}).get("deployment_runtime_id", ""),
        "deployment_state": task.get("deployment_state", ""),
        "deployment_build_state": task.get("deployment_build_state", ""),
        "deployment_url_verification_state": task.get("deployment_url_verification_state", ""),
        "deployment_scenario_state": task.get("deployment_scenario_state", ""),
        "deployment_rollback_state": task.get("deployment_rollback_state", ""),
        "deployment_retry_count": int(task.get("deployment_retry_count", 0)),
        "deployment_next_safe_action": task.get("deployment_next_safe_action", ""),
        "deployment_result": _redact(task.get("deployment_result", {})),
        "render_intent": bool(task.get("render_intent", False)),
        "render_detection_state": task.get("render_detection_state", ""),
        "render_service_candidates": _redact(task.get("render_service_candidates", [])),
        "selected_render_service": _redact(task.get("selected_render_service", {})),
        "render_readiness_state": task.get("render_readiness_state", ""),
        "render_plan_id": task.get("render_plan", {}).get("render_plan_id", ""),
        "render_plan_digest": task.get("render_plan", {}).get("plan_digest", ""),
        "render_credential_reference_state": task.get("render_credential_reference_state", ""),
        "render_network_permission_state": task.get("render_network_permission_state", ""),
        "render_final_confirmation_state": task.get("render_final_confirmation_state", ""),
        "render_deployment_state": task.get("render_deployment_state", ""),
        "render_url_state": task.get("render_url_state", ""),
        "render_health_state": task.get("render_health_state", ""),
        "render_scenario_state": task.get("render_scenario_state", ""),
        "render_rollback_state": task.get("render_rollback_state", ""),
        "skipped_target_reasons": _redact(task.get("skipped_target_reasons", {})),
        "can_advance": can_advance,
        "requires_user_approval": state in {"awaiting_approval", "apply_prepared", "verification_prepared"},
        **SAFE_INVARIANTS,
    }


def _touch(task: Dict[str, Any], state: Optional[str] = None, step: Optional[str] = None) -> Dict[str, Any]:
    if state:
        if state not in TASK_STATES:
            raise ValueError(f"invalid task state: {state}")
        task["current_state"] = state
    if step and step not in task["completed_steps"]:
        task["completed_steps"].append(step)
    task["updated_at"] = _now()
    task["pending_steps"] = _pending_for_state(task["current_state"])
    return task


def _block(task: Dict[str, Any], reason: str, state: str = "blocked") -> Dict[str, Any]:
    if reason not in task["blocked_reasons"]:
        task["blocked_reasons"].append(reason)
    task["next_safe_action"] = "Resolve blocked reason or cancel the task."
    return _touch(task, state)


def _operation_for_action(action: str, state: str) -> str:
    if action == "route" or (action == "next" and state == "created"):
        return "inspect"
    if action == "diagnose" or (action == "next" and state == "routed"):
        return "read"
    if action in {"draft", "patch"} or (action == "next" and state == "diagnosis_ready"):
        return "read"
    if action == "prepare_apply" or (action == "next" and state == "approval_verified"):
        return "edit_file"
    if action == "apply" or (action == "next" and state == "apply_prepared"):
        return "edit_file"
    if action == "prepare_verification" or (action == "next" and state == "applied"):
        return "run_validator"
    if action == "execute_verification" or (action == "next" and state == "verification_prepared"):
        return "run_validator"
    return "inspect"


def _target_for_operation(task: Dict[str, Any], operation: str) -> str:
    files = task.get("changed_files") or task.get("selected_files") or task.get("requested_files") or []
    return files[0] if files else ""


def _permission_check(task: Dict[str, Any], action: str) -> Tuple[bool, Dict[str, Any]]:
    profile = task.get("permission_profile")
    if not profile:
        return True, {}
    operation = _operation_for_action(action, task.get("current_state", "created"))
    target = _target_for_operation(task, operation)
    result = evaluate_requested_action(
        profile=profile,
        task_id=task.get("task_id", ""),
        operation=operation,
        target_path=target,
        metadata={
            "files_changed": max(1, len(task.get("changed_files", []))) if operation in {"edit_file", "refactor"} else 0,
            "validation_runs": len([step for step in task.get("completed_steps", []) if "verification" in step]),
            "scope_expansions": profile.get("scope_expansion_count", 0),
            "why_needed": "The task transition needs this selected file or folder.",
        },
        recovery_plan_available=True,
    )
    task.setdefault("permission_audit", []).append(result.get("audit", result))
    task["last_permission_evaluation"] = result
    if result.get("allowed"):
        return True, result
    task["previous_state_before_scope_pause"] = task.get("current_state", "created")
    if result.get("state") == "awaiting_scope_permission":
        task["scope_expansion_request"] = result.get("scope_request", {})
        task["next_safe_action"] = "Review the scope-expansion request before continuing."
        _touch(task, "awaiting_scope_permission")
    elif result.get("state") == "budget_exhausted":
        task["next_safe_action"] = result.get("reason", "Autonomy budget exhausted.")
        _touch(task, "budget_exhausted")
    elif result.get("state") == "awaiting_irreversible_confirmation":
        task["next_safe_action"] = "Review irreversible-action confirmation before continuing."
        _touch(task, "awaiting_irreversible_confirmation")
    else:
        task["next_safe_action"] = result.get("reason", "Permission approval is required before continuing.")
        _touch(task, "autonomy_paused")
    return False, result


def _persist_task(task: Dict[str, Any], event_type: str = "state_transition", previous_state: Optional[str] = None) -> None:
    if not _PERSISTENCE_CONFIG.get("enabled"):
        return
    result = save_task_state(
        task,
        expected_revision=task.get("persistence_revision"),
        mode=_PERSISTENCE_CONFIG.get("mode"),
        storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
        event_type=event_type,
        previous_state=previous_state,
    )
    task["persistence_status"] = {
        "enabled": True,
        "durable": bool(result.get("durable")),
        "last_save_ok": bool(result.get("ok") and result.get("saved", True)),
        "revision": result.get("revision", task.get("persistence_revision", 0)),
    }
    if result.get("ok") and result.get("revision") is not None:
        task["persistence_revision"] = int(result["revision"])
        task.pop("persistence_warning", None)
    elif not result.get("ok"):
        task["persistence_warning"] = result.get("error", "persistence save failed")
        task["next_safe_action"] = "Retry persistence save or continue with in-memory task state."


def _persist_and_summarize(task: Dict[str, Any], event_type: str = "state_transition", previous_state: Optional[str] = None) -> Dict[str, Any]:
    _persist_task(task, event_type=event_type, previous_state=previous_state)
    return _summary(task)


def _restore_payload_to_task(payload: Dict[str, Any]) -> Tuple[bool, str]:
    task_id = str(payload.get("task_id") or "")
    state = str(payload.get("current_state") or "")
    if not task_id:
        return False, "restored task_id missing"
    if state not in TASK_STATES:
        return False, "restored task state invalid"
    task = deepcopy(payload)
    task.setdefault("completed_steps", [])
    task.setdefault("blocked_reasons", [])
    task.setdefault("pending_steps", _pending_for_state(state))
    task.setdefault("safety_flags", dict(SAFE_INVARIANTS))
    task["restored_from_persistence"] = True
    task["requires_explicit_resume"] = True
    task["execution_triggered_on_restore"] = False
    task["routing_requires_revalidation"] = True
    task["restored_route_executed"] = False
    task["restored_paid_escalation_allowed"] = False
    task["restored_engine_health_trusted"] = False
    restored_multi_agent = _safe_multi_agent_metadata(task)
    restored_multi_agent.update(
        {
            "multi_agent_requires_revalidation": True,
            "restored_assignment_active": False,
            "restored_handoff_executed": False,
            "restored_file_ownership_active": False,
            "restored_paid_approval": False,
            "restored_worker_execution_started": False,
            "assignment_state": "restore_requires_revalidation",
            "file_ownership_state": "inactive",
        }
    )
    task["multi_agent_metadata"] = restored_multi_agent
    restored_coder = _safe_coder_runtime_metadata(task)
    restored_coder.update(
        {
            "coder_requires_revalidation": True,
            "restored_patch_apply_allowed": False,
            "restored_approval_valid": False,
            "restored_snapshot_trusted": False,
            "restored_validation_passed": False,
            "restored_worker_started": False,
            "restored_execution_resumed": False,
            "patch_execution_state": "restore_requires_revalidation",
            "validation_state": "restore_requires_revalidation",
            "coder_cli_revalidation_required": True,
            "coder_cli_session_state": "restore_requires_revalidation",
            "coder_cli_last_result_digest": "",
            "coder_cli_output_manifest": "",
            "coder_cli_approval_required": False,
            "coder_cli_session_id": "",
            "coder_cli_run_id": "",
            "coder_cli_last_command": "restore",
            "coder_cli_completed_scope": [],
            "coder_cli_remaining_gap": [],
            "coder_cli_updated_at": _now(),
        }
    )
    task["coder_runtime_metadata"] = restored_coder
    route_state = _build_zero_cost_route_metadata(task) if isinstance(task.get("zero_cost_routing"), dict) else _build_zero_cost_route_metadata(
        {
            "task_id": task_id,
            "original_request": task.get("original_request", ""),
            "selected_files": task.get("selected_files", []),
            "selected_capabilities": [],
        }
    )
    route_state["routing_requires_revalidation"] = True
    route_state["restored_route_executed"] = False
    route_state["restored_paid_escalation_allowed"] = False
    route_state["restored_engine_health_trusted"] = False
    task["zero_cost_routing"] = _normalize_dict(route_state)
    engine_snapshot = task["zero_cost_routing"].get("engine_health_snapshot", {})
    if isinstance(engine_snapshot, dict):
        task["zero_cost_routing"]["engine_health_snapshot"] = {key: "restored_from_store" for key in engine_snapshot.keys()}
    task["zero_cost_routing"]["paid_escalation_allowed"] = False
    _TASKS[task_id] = task
    return True, ""


def get_task_orchestrator_schema() -> Dict[str, Any]:
    return {
        "name": "LuxCode Task Orchestrator & Continuity Core",
        "status": "local_first_in_memory_mvp",
        "supported_states": sorted(TASK_STATES),
        "public_functions": [
            "get_task_orchestrator_schema",
            "create_luxcode_task",
            "advance_luxcode_task",
            "approve_luxcode_task_step",
            "cancel_luxcode_task",
            "resume_luxcode_task",
            "get_luxcode_task_status",
            "get_task_orchestrator_status",
            "configure_luxcode_task_persistence",
            "save_luxcode_task_to_persistence",
            "load_luxcode_task_from_persistence",
            "list_luxcode_persisted_tasks",
            "archive_luxcode_persisted_task",
            "delete_luxcode_persisted_task",
            "restore_luxcode_active_tasks",
            "approve_luxcode_task_scope_expansion",
            "revoke_luxcode_task_scope",
            "plan_luxcode_task_terminal_action",
            "execute_luxcode_task_terminal_action",
            "cancel_luxcode_task_terminal_runtime",
            "plan_luxcode_task_live_test",
            "execute_luxcode_task_live_test",
            "cancel_luxcode_task_live_test",
            "plan_luxcode_task_network_access",
            "execute_luxcode_task_network_access",
            "cancel_luxcode_task_network_access",
            "plan_luxcode_task_test_matrix",
            "execute_luxcode_task_test_matrix",
            "request_luxcode_codewhale_escalation",
            "approve_luxcode_codewhale_escalation",
            "request_luxcode_codex_escalation",
            "approve_luxcode_codex_escalation",
        ],
        "integrated_engines": [
            "LuxCode Master Router Preview",
            "Lux Debug Intelligence Core",
            "Safe Patch Draft Engine",
            "Approval-Gated Controlled Apply Engine",
            "Local Verification Execution & Recovery Engine",
        ],
        "state_storage": "in_memory_with_optional_local_persistence",
        "known_limitation": "persistence is disabled until explicitly initialized",
        "persistence": get_task_persistence_status(),
        "autonomy_permission": get_autonomy_permission_status(),
        "terminal_runtime": "available_for_structured_actions",
        "live_testing": "available_for_localhost_structured_scenarios",
        "network_access": "available_for_localhost_and_selected_lan_verification",
        "test_matrix": "available_for_browser_device_screen_network_verification",
        "multi_agent_metadata_fields": sorted(MULTI_AGENT_METADATA_KEYS),
        "coder_runtime_metadata_fields": sorted(CODER_RUNTIME_METADATA_KEYS),
        "coder_runtime_restore_policy": "restored coder patch approvals, snapshots, validation, workers, and execution require revalidation and never auto-start",
        "multi_agent_execution_enabled": False,
        "multi_agent_paid_escalation_auto_enabled": False,
        "multi_agent_whale_auto_start": False,
        "multi_agent_codex_auto_start": False,
        "automatic_apply_enabled": False,
        "automatic_rollback_enabled": False,
        **SAFE_INVARIANTS,
    }


def create_luxcode_task(
    original_request: str = "",
    repository_root: Optional[str] = None,
    suspected_files: Optional[List[str]] = None,
    changed_files: Optional[List[str]] = None,
    mode: Optional[str] = None,
    traceback_text: str = "",
    selected_files: Optional[List[str]] = None,
    requested_files: Optional[List[str]] = None,
    forbidden_files: Optional[List[str]] = None,
    permission_mode: str = "approval_required",
    scope_items: Optional[List[Dict[str, Any]]] = None,
    selected_folders: Optional[List[str]] = None,
    autonomy_budgets: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    now = _now()
    root = _safe_root(repository_root)
    task_id = "lux-task-" + uuid.uuid4().hex[:16]
    files = _unique((selected_files or []) + (requested_files or []) + (suspected_files or []))
    task = {
        "task_id": task_id,
        "created_at": now,
        "updated_at": now,
        "current_state": "created",
        "original_request": original_request,
        "repository_root": root,
        "mode": mode or "plan",
        "traceback_text": traceback_text,
        "route_result": {},
        "routing_result": {},
        "diagnosis_result": {},
        "patch_draft_result": {},
        "approval_state": {"approved": False, "approval_events": []},
        "apply_result": {},
        "verification_result": {},
        "recovery_result": {},
        "active_engine": "-",
        "active_model": "-",
        "model_attempts": [],
        "model_evidence": [],
        "token_usage": "unavailable",
        "provider_cost": "cost_status=unavailable",
        "deepseek_escalation": {
            "state": "not_requested",
            "approved": False,
            "consumed": False,
            "approval_digest": "",
            "confirmation_text": "",
            "model_id": DIRECT_DEEPSEEK_MODEL_ID,
            "maximum_cost_usd": 0.001,
            "requested_at": "",
            "approved_at": "",
        },
        "codewhale_escalation": {
            "state": "not_requested",
            "approved": False,
            "consumed": False,
            "approval_digest": "",
            "confirmation_text": "",
            "manual_only": True,
            "auto_mode_allowed": False,
            "requested_at": "",
            "approved_at": "",
        },
        "codex_escalation": {
            "state": "not_requested",
            "approved": False,
            "consumed": False,
            "approval_digest": "",
            "confirmation_text": "",
            "manual_only": True,
            "emergency_only": True,
            "sandbox_mode": "read-only",
            "approval_policy": "never",
            "requested_at": "",
            "approved_at": "",
        },
        "selected_files": files,
        "changed_files": _unique(changed_files or []),
        "requested_files": _unique(requested_files or files),
        "forbidden_files": _unique((forbidden_files or []) + DEFAULT_FORBIDDEN_FILES),
        "adjacent_findings": [],
        "blocked_reasons": [],
        "completed_steps": [],
        "pending_steps": _pending_for_state("created"),
        "next_safe_action": "Advance to route the request.",
        "deployment_intent": any(word in original_request.lower() for word in ["deploy", "deployment", "yayina al", "yayına al"]),
        "deployment_provider": "",
        "deployment_state": "not_started",
        "deployment_build_state": "not_started",
        "deployment_url_verification_state": "not_started",
        "deployment_scenario_state": "not_started",
        "deployment_rollback_state": "not_started",
        "deployment_retry_count": 0,
        "deployment_next_safe_action": "Deployment requires explicit plan and execution request.",
        "deployment_plan": {},
        "deployment_result": {},
        "render_intent": "render" in original_request.lower() and any(word in original_request.lower() for word in ["deploy", "deployment", "gonder", "gönder"]),
        "render_detection_state": "not_started",
        "render_service_candidates": [],
        "selected_render_service": {},
        "render_readiness_state": "not_started",
        "render_credential_reference_state": "not_configured",
        "render_network_permission_state": "blocked_by_external_network_policy",
        "render_final_confirmation_state": "required",
        "render_deployment_state": "not_started",
        "render_url_state": "not_started",
        "render_health_state": "not_started",
        "render_scenario_state": "not_started",
        "render_rollback_state": "not_started",
        "render_plan": {},
        "render_result": {},
        "pause_reason": "",
        "cancellation_reason": "",
        "routing_requires_revalidation": False,
        "restored_route_executed": False,
        "routing_update_count": 0,
        "routing_state": "",
        "user_requires_free_only": True,
        "restored_paid_escalation_allowed": False,
        "restored_engine_health_trusted": False,
        "zero_cost_routing": _build_zero_cost_route_metadata(
            {
                "task_id": task_id,
                "original_request": original_request,
                "selected_files": files,
                "selected_capabilities": _normalize_list(requested_files or files),
            }
        ),
        "multi_agent_metadata": _default_multi_agent_metadata(),
        "coder_runtime_metadata": _default_coder_runtime_metadata(),
        "selected_capabilities": _normalize_list(requested_files or files),
        "safety_flags": dict(SAFE_INVARIANTS),
    }
    permission = create_permission_profile(
        task_id=task_id,
        permission_mode=permission_mode,
        repository_root=root or str(Path.cwd()),
        command_text=original_request,
        scope_items=scope_items,
        selected_files=files,
        selected_folders=selected_folders or [],
        autonomy_budgets=autonomy_budgets,
    )
    if permission.get("ok"):
        task["permission_profile"] = permission["profile"]
        task["safe_permission_metadata"] = get_safe_permission_metadata(permission["profile"])
    else:
        task["permission_profile"] = {}
        task["permission_warning"] = permission.get("reason", "permission profile could not be created")
    _TASKS[task_id] = task
    return _persist_and_summarize(task, event_type="create")


def _advance_route(task: Dict[str, Any]) -> None:
    if "route" in task["completed_steps"]:
        return
    task["route_result"] = {
        "luxcode_master_router_preview": build_luxcode_master_router_preview(
            task["original_request"],
            context=task.get("mode") or "",
        ),
        "zero_cost_routing": _build_zero_cost_route_metadata(task),
    }
    zero_cost_routing = _normalize_dict(task["route_result"].get("zero_cost_routing", {}))
    task["zero_cost_routing"] = zero_cost_routing
    task["routing_state"] = str(zero_cost_routing.get("routing_state", "routed"))
    task["routing_update_count"] = int(task.get("routing_update_count", 0)) + 1
    task["routing_requires_revalidation"] = False
    task["next_safe_action"] = "Advance to read-only diagnosis."
    _touch(task, "routed", "route")


def _advance_diagnosis(task: Dict[str, Any]) -> None:
    if "diagnose" in task["completed_steps"]:
        return
    _touch(task, "diagnosing")
    diagnosis = analyze_lux_debug_request(
        issue_text=task["original_request"],
        traceback_text=task.get("traceback_text", ""),
        suspected_files=task.get("selected_files", []),
        changed_files=task.get("changed_files", []),
        repository_root=task.get("repository_root") or None,
        max_files=8,
        mode="full_debug_preview",
    )
    task["diagnosis_result"] = diagnosis
    task["adjacent_findings"] = _classify_adjacent(diagnosis.get("adjacent_issues", []))
    selected = [
        item.get("relative_path") or item.get("path") or item.get("file")
        for item in diagnosis.get("selected_context", [])
        if isinstance(item, dict)
    ]
    task["selected_files"] = _unique(task.get("selected_files", []) + [item for item in selected if item])
    if (
        str(task.get("mode") or "") == "read_only_analysis"
        or str(
            task.get("route_result", {})
            .get("luxcode_master_router_preview", {})
            .get("context_hint", "")
        ) == "read_only_analysis"
    ):
        task["patch_draft_result"] = {}
        task["next_safe_action"] = (
            "Salt okunur analiz tamamlandı. Dosya değiştirilmedi, "
            "yama hazırlanmadı, komut çalıştırılmadı ve dış servis kullanılmadı."
        )
        _touch(task, "completed", "diagnose")
    else:
        task["next_safe_action"] = "Advance to safe patch draft preview."
        _touch(task, "diagnosis_ready", "diagnose")


def _tier1_targets_and_context(task: Dict[str, Any]) -> Tuple[List[str], Dict[str, str]]:
    root_text = str(task.get("repository_root") or "")
    if not root_text:
        return [], {}
    root = Path(root_text).resolve()
    diagnosis = _normalize_dict(task.get("diagnosis_result", {}))
    selected_context = diagnosis.get("selected_context", [])
    excerpts: Dict[str, str] = {}
    context_files: List[str] = []
    for item in selected_context if isinstance(selected_context, list) else []:
        if not isinstance(item, dict):
            continue
        rel = str(item.get("relative_path") or item.get("path") or item.get("file") or "").replace("\\", "/").strip()
        if not rel:
            continue
        context_files.append(rel)
        excerpt = str(item.get("excerpt") or "")
        if excerpt:
            excerpts[rel] = excerpt[:12000]

    candidates = _unique(
        list(task.get("requested_files", []))
        + list(task.get("selected_files", []))
        + context_files
    )
    forbidden = {str(item).replace("\\", "/").strip().lower() for item in task.get("forbidden_files", [])}
    targets: List[str] = []
    context: Dict[str, str] = {}
    for rel in candidates:
        normalized = str(rel).replace("\\", "/").strip()
        if not normalized or normalized.lower() in forbidden or normalized.startswith(("/", "../")):
            continue
        if ".." in Path(normalized).parts:
            continue
        path = (root / normalized).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if not path.is_file() or path.is_symlink():
            continue
        targets.append(normalized)
        if path.stat().st_size <= 12000:
            context[normalized] = path.read_text(encoding="utf-8", errors="replace")
        else:
            context[normalized] = excerpts.get(normalized, "")[:12000]
        if len(targets) >= 4:
            break
    return targets, context


def _tier1_diagnostics_stub(task: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "selected_tier": 0,
        "selected_engine": "deterministic_local_tools",
        "remaining_gap": {
            "ok": True,
            "remaining_gap": {
                "remaining_gap": "tier1_local_patch_draft_required",
                "completed_scope": list(task.get("completed_steps", [])),
                "failed_attempt_fingerprints": [],
                "required_capabilities": ["code_generation", "patch_candidate_draft"],
            },
        },
        "external_api_used": False,
        "network_access_used": False,
    }


def _record_model_attempt(task: Dict[str, Any], result: Dict[str, Any]) -> None:
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    model_response = result.get("model_response") if isinstance(result.get("model_response"), dict) else {}
    attempt = {
        "engine_id": "tier1_local_worker",
        "runtime_id": TIER1_OLLAMA_RUNTIME_ID,
        "model_id": TIER1_OLLAMA_MODEL_ID,
        "status": str(result.get("state") or ("completed" if result.get("ok") else "failed")),
        "ok": bool(result.get("ok")),
        "duration_ms": int(result.get("duration_ms") or evidence.get("duration_ms") or 0),
        "analysis_summary": str(model_response.get("analysis_summary") or result.get("analysis_summary") or result.get("error") or ""),
        "failure_fingerprint": str(evidence.get("failure_fingerprint") or ""),
        "external_api_used": False,
        "local_only": True,
    }
    task.setdefault("model_attempts", []).append(attempt)
    if evidence:
        task.setdefault("model_evidence", []).append(evidence)


def _record_gemini_attempt(task: Dict[str, Any], result: Dict[str, Any]) -> None:
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    model_response = result.get("model_response") if isinstance(result.get("model_response"), dict) else {}
    attempt = {
        "engine_id": "free_gemini",
        "runtime_id": "gemini_developer_api",
        "model_id": str(result.get("model_id") or "gemini-3.5-flash"),
        "status": str(result.get("state") or ("completed" if result.get("ok") else "failed")),
        "ok": bool(result.get("ok")),
        "duration_ms": int(result.get("duration_ms") or 0),
        "analysis_summary": str(
            model_response.get("analysis_summary")
            or result.get("analysis_summary")
            or result.get("error")
            or ""
        ),
        "failure_fingerprint": str(evidence.get("event_digest") or ""),
        "external_api_used": bool(result.get("external_api_used")),
        "local_only": False,
        "transport_called": bool(result.get("transport_called")),
    }
    task.setdefault("model_attempts", []).append(attempt)
    if evidence:
        task.setdefault("model_evidence", []).append(evidence)



def _record_free_cloud_attempt(task: Dict[str, Any], result: Dict[str, Any]) -> None:
    attempts = result.get("model_attempts", [])
    if not isinstance(attempts, list):
        attempts = []
    if not attempts:
        attempts = [
            {
                "model_id": str(result.get("model_id") or FREE_CLOUD_PRIMARY_MODEL_ID),
                "status": str(result.get("state") or ("completed" if result.get("ok") else "failed")),
                "ok": bool(result.get("ok")),
                "http_attempts": 0,
                "structured_result_valid": bool(result.get("ok")),
                "usage_metadata": _normalize_dict(result.get("token_usage", {})),
            }
        ]
    for item in attempts[:4]:
        if not isinstance(item, dict):
            continue
        usage = item.get("usage_metadata", {})
        if not isinstance(usage, dict):
            usage = {}
        task.setdefault("model_attempts", []).append(
            {
                "engine_id": "free_cloud_worker",
                "runtime_id": "openrouter_chat_completions",
                "model_id": str(item.get("model_id") or result.get("model_id") or FREE_CLOUD_PRIMARY_MODEL_ID),
                "status": str(item.get("status") or item.get("failure_reason") or result.get("state") or "unknown"),
                "ok": bool(item.get("ok")),
                "duration_ms": int(result.get("duration_ms") or 0),
                "analysis_summary": str(
                    item.get("failure_reason")
                    or _normalize_dict(result.get("model_response", {})).get("analysis_summary")
                    or result.get("error")
                    or ""
                ),
                "failure_fingerprint": str(_normalize_dict(result.get("evidence", {})).get("evidence_digest") or ""),
                "external_api_used": bool(result.get("external_api_used")),
                "local_only": False,
                "transport_called": int(item.get("http_attempts", 0) or 0) > 0,
                "structured_result_valid": bool(item.get("structured_result_valid")),
                "token_usage": _redact(usage),
            }
        )
    evidence = result.get("evidence")
    if isinstance(evidence, dict) and evidence:
        task.setdefault("model_evidence", []).append(evidence)



def _record_direct_deepseek_attempt(
    task: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    evidence = (
        result.get("evidence")
        if isinstance(result.get("evidence"), dict)
        else {}
    )
    transport = (
        result.get("transport")
        if isinstance(result.get("transport"), dict)
        else {}
    )
    response = (
        result.get("model_response")
        if isinstance(result.get("model_response"), dict)
        else {}
    )
    usage = (
        result.get("token_usage")
        if isinstance(result.get("token_usage"), dict)
        else {}
    )
    task.setdefault("model_attempts", []).append(
        {
            "engine_id": "direct_deepseek",
            "runtime_id": "deepseek_chat_completions",
            "model_id": str(
                result.get("model_id") or DIRECT_DEEPSEEK_MODEL_ID
            ),
            "status": str(
                result.get("state")
                or ("completed" if result.get("ok") else "failed")
            ),
            "ok": bool(result.get("ok")),
            "duration_ms": int(result.get("duration_ms") or 0),
            "analysis_summary": str(
                response.get("analysis_summary")
                or result.get("error")
                or ""
            ),
            "failure_fingerprint": str(
                evidence.get("evidence_id") or ""
            ),
            "external_api_used": bool(
                result.get("external_api_used")
            ),
            "local_only": False,
            "transport_called": bool(
                result.get("external_api_used")
            ),
            "structured_result_valid": bool(result.get("ok")),
            "token_usage": _redact(usage),
            "provider_cost": str(
                result.get("provider_cost")
                if result.get("provider_cost") is not None
                else transport.get("actual_estimated_cost", "unavailable")
            ),
        }
    )
    if evidence:
        task.setdefault("model_evidence", []).append(evidence)



def _record_codewhale_attempt(
    task: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    evidence = (
        result.get("evidence")
        if isinstance(result.get("evidence"), dict)
        else {}
    )
    response = (
        result.get("model_response")
        if isinstance(result.get("model_response"), dict)
        else {}
    )
    task.setdefault("model_attempts", []).append(
        {
            "engine_id": "whale",
            "runtime_id": "codewhale_cli",
            "model_id": str(result.get("model_id") or ""),
            "status": str(
                result.get("state")
                or ("completed" if result.get("ok") else "failed")
            ),
            "ok": bool(result.get("ok")),
            "duration_ms": int(
                _normalize_dict(result.get("process", {})).get(
                    "duration_ms", 0
                )
                or 0
            ),
            "analysis_summary": str(
                response.get("analysis_summary")
                or result.get("error")
                or ""
            ),
            "failure_fingerprint": str(
                evidence.get("evidence_id") or ""
            ),
            "external_api_used": bool(
                result.get("external_api_used")
            ),
            "local_only": False,
            "transport_called": bool(
                result.get("process_started")
            ),
            "structured_result_valid": bool(result.get("ok")),
            "provider_cost": str(
                result.get("provider_cost")
                or "unavailable_manual_agent"
            ),
            "manual_only": True,
            "auto_mode_used": False,
        }
    )
    if evidence:
        task.setdefault("model_evidence", []).append(evidence)




def _record_codex_attempt(
    task: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    evidence = (
        result.get("evidence")
        if isinstance(result.get("evidence"), dict)
        else {}
    )
    response = (
        result.get("model_response")
        if isinstance(result.get("model_response"), dict)
        else {}
    )
    task.setdefault("model_attempts", []).append(
        {
            "engine_id": "codex",
            "runtime_id": "codex_cli",
            "model_id": "account_default",
            "status": str(
                result.get("state")
                or ("completed" if result.get("ok") else "failed")
            ),
            "ok": bool(result.get("ok")),
            "duration_ms": int(
                _normalize_dict(result.get("process", {})).get(
                    "duration_ms", 0
                )
                or 0
            ),
            "analysis_summary": str(
                response.get("analysis_summary")
                or result.get("error")
                or ""
            ),
            "failure_fingerprint": str(
                evidence.get("evidence_id") or ""
            ),
            "external_api_used": bool(
                result.get("external_api_used")
            ),
            "local_only": False,
            "transport_called": bool(
                result.get("process_started")
            ),
            "structured_result_valid": bool(result.get("ok")),
            "provider_cost": str(
                result.get("provider_cost")
                or "chatgpt_plan_credit_or_unknown_manual_agent"
            ),
            "manual_only": True,
            "emergency_only": True,
            "sandbox_mode": "read-only",
            "approval_policy": "never",
            "dangerous_bypass_used": False,
        }
    )
    if evidence:
        task.setdefault("model_evidence", []).append(evidence)


def _advance_patch(task: Dict[str, Any]) -> None:
    if "draft_patch" in task["completed_steps"]:
        return
    _touch(task, "patch_drafting")
    diagnosis = task.get("diagnosis_result", {})
    targets, minimum_context = _tier1_targets_and_context(task)
    local_result: Dict[str, Any] = {}
    gemini_result: Dict[str, Any] = {}
    free_cloud_result: Dict[str, Any] = {}
    deepseek_result: Dict[str, Any] = {}
    codewhale_result: Dict[str, Any] = {}
    codex_result: Dict[str, Any] = {}

    if targets:
        task["active_engine"] = "tier1_local_worker"
        task["active_model"] = TIER1_OLLAMA_MODEL_ID
        task["next_safe_action"] = "Yerel Ollama modeli güvenli yama önizlemesi hazırlıyor. Dosya yazılmayacak."
        local_result = execute_tier0_router_tier1_preview(
            task_id=task["task_id"],
            repository_root=task.get("repository_root") or str(Path.cwd()),
            task_summary=task["original_request"],
            target_files=targets,
            target_symbols=[],
            minimum_context=minimum_context,
            model_id=TIER1_OLLAMA_MODEL_ID,
            persist=False,
            tier0_diagnostics=_tier1_diagnostics_stub(task),
        )
        _record_model_attempt(task, local_result)

    if local_result.get("ok"):
        model_response = _normalize_dict(local_result.get("model_response", {}))
        usage = _normalize_dict(model_response.get("usage_metadata", {}))
        task["token_usage"] = f"input={usage.get('input_tokens', 0)} output={usage.get('output_tokens', 0)}"
        task["provider_cost"] = "0.0 local"
        task["selected_files"] = _unique(task.get("selected_files", []) + local_result.get("files_to_modify", []))
        task["patch_draft_result"] = {
            "request_id": _normalize_dict(local_result.get("request", {})).get("request_id", ""),
            "mode": "preview",
            "source": "tier1_local_worker",
            "runtime_id": TIER1_OLLAMA_RUNTIME_ID,
            "model_id": TIER1_OLLAMA_MODEL_ID,
            "repository_root": task.get("repository_root", ""),
            "issue_summary": diagnosis.get("normalized_issue") or task["original_request"],
            "analysis_summary": model_response.get("analysis_summary", ""),
            "patch_steps": list(local_result.get("patch_steps", [])),
            "expected_file_hashes": dict(local_result.get("expected_file_hashes", {})),
            "files_to_modify": list(local_result.get("files_to_modify", [])),
            "safe_patch_contract": _redact(local_result.get("safe_patch_contract", {})),
            "safe_patch_preview": _redact(local_result.get("safe_patch_preview", {})),
            "validation": _redact(local_result.get("validation", {})),
            "model_response": _redact(model_response),
            "evidence": _redact(local_result.get("evidence", {})),
            "approval_required": True,
            "can_apply_now": False,
            "file_write_blocked": True,
            "real_execution_blocked": True,
            "external_api_used": False,
            "local_first": True,
        }
        task["next_safe_action"] = (
            "Ollama güvenli yama önizlemesini hazırladı. Dosya değiştirilmedi. "
            "Uygulama için önce yama ayrıntılarını inceleyip açık onay verin."
        )
        _touch(task, "awaiting_approval", "draft_patch")
        return

    if targets:
        task["active_engine"] = "free_gemini"
        task["active_model"] = str(os.getenv("LUXCODE_GEMINI_MODEL_ID") or "gemini-3.5-flash")
        task["next_safe_action"] = (
            "Ollama sonucu kullanılamadı. Açık Gemini ücretsiz-katman izinleri denetleniyor; "
            "izinler kapalıysa hiçbir ağ çağrısı yapılmayacak."
        )
        gemini_result = execute_gemini_task_bridge(
            task_id=task["task_id"],
            repository_root=task.get("repository_root") or str(Path.cwd()),
            task_summary=task["original_request"],
            target_files=targets,
            target_symbols=[],
            minimum_context=minimum_context,
            previous_engine_state=str(local_result.get("state") or "tier1_not_available"),
            environ=os.environ,
        )
        _record_gemini_attempt(task, gemini_result)

    if gemini_result.get("ok"):
        model_response = _normalize_dict(gemini_result.get("model_response", {}))
        usage = _normalize_dict(gemini_result.get("token_usage", {}))
        task["token_usage"] = (
            f"input={usage.get('input_tokens', 0)} "
            f"output={usage.get('output_tokens', 0)} "
            f"total={usage.get('total_tokens', 0)}"
        )
        task["provider_cost"] = str(gemini_result.get("provider_cost") or "0.0 free tier")
        task["external_api_used"] = True
        task["network_access_used"] = True
        task["selected_files"] = _unique(
            task.get("selected_files", []) + gemini_result.get("files_to_modify", [])
        )
        task["patch_draft_result"] = {
            "request_id": str(model_response.get("request_id") or ""),
            "mode": "preview",
            "source": "free_gemini",
            "runtime_id": "gemini_developer_api",
            "provider_id": "google_gemini",
            "model_id": str(gemini_result.get("model_id") or "gemini-3.5-flash"),
            "repository_root": task.get("repository_root", ""),
            "issue_summary": diagnosis.get("normalized_issue") or task["original_request"],
            "analysis_summary": model_response.get("analysis_summary", ""),
            "patch_steps": list(gemini_result.get("patch_steps", [])),
            "expected_file_hashes": dict(gemini_result.get("expected_file_hashes", {})),
            "files_to_modify": list(gemini_result.get("files_to_modify", [])),
            "model_response": _redact(model_response),
            "transport": _redact(gemini_result.get("transport", {})),
            "evidence": _redact(gemini_result.get("evidence", {})),
            "gate": _redact(gemini_result.get("gate", {})),
            "approval_required": True,
            "can_apply_now": False,
            "file_write_blocked": True,
            "real_execution_blocked": True,
            "external_api_used": True,
            "local_first": False,
            "free_tier_confirmed": True,
            "billing_allowed": False,
        }
        task["next_safe_action"] = (
            "Gemini ücretsiz katmanı güvenli yama önizlemesini hazırladı. Dosya değiştirilmedi. "
            "Uygulama için yama ayrıntılarını inceleyip açık onay verin."
        )
        _touch(task, "awaiting_approval", "draft_patch")
        return

    if targets:
        task["active_engine"] = "free_cloud_worker"
        task["active_model"] = FREE_CLOUD_PRIMARY_MODEL_ID
        task["next_safe_action"] = (
            "Ollama ve Gemini sonucu kullanılamadı. OpenRouter ücretsiz model kapıları denetleniyor; "
            "izinler kapalıysa hiçbir ağ çağrısı yapılmayacak."
        )
        free_cloud_result = execute_free_cloud_task_bridge(
            task_id=task["task_id"],
            repository_root=task.get("repository_root") or str(Path.cwd()),
            task_summary=task["original_request"],
            target_files=targets,
            target_symbols=[],
            minimum_context=minimum_context,
            previous_engine_state=str(
                gemini_result.get("state")
                or local_result.get("state")
                or "lower_tiers_not_available"
            ),
            environ=os.environ,
        )
        _record_free_cloud_attempt(task, free_cloud_result)

    if free_cloud_result.get("ok"):
        model_response = _normalize_dict(free_cloud_result.get("model_response", {}))
        usage = _normalize_dict(free_cloud_result.get("token_usage", {}))
        task["token_usage"] = (
            f"input={usage.get('prompt_tokens', 0)} "
            f"output={usage.get('completion_tokens', 0)} "
            f"total={usage.get('total_tokens', 0)}"
        )
        task["provider_cost"] = str(
            free_cloud_result.get("provider_cost")
            or "0.0 free models only"
        )
        task["external_api_used"] = bool(
            free_cloud_result.get("external_api_used")
        )
        task["network_access_used"] = bool(
            free_cloud_result.get("external_api_used")
        )
        task["active_model"] = str(
            free_cloud_result.get("selected_model")
            or FREE_CLOUD_PRIMARY_MODEL_ID
        )
        task["selected_files"] = _unique(
            task.get("selected_files", [])
            + free_cloud_result.get("files_to_modify", [])
        )
        task["patch_draft_result"] = {
            "request_id": str(model_response.get("request_digest") or ""),
            "mode": "preview",
            "source": "free_cloud_worker",
            "runtime_id": "openrouter_chat_completions",
            "provider_id": "openrouter",
            "model_id": task["active_model"],
            "repository_root": task.get("repository_root", ""),
            "issue_summary": diagnosis.get("normalized_issue") or task["original_request"],
            "analysis_summary": model_response.get("analysis_summary", ""),
            "patch_steps": list(free_cloud_result.get("patch_steps", [])),
            "expected_file_hashes": dict(
                free_cloud_result.get("expected_file_hashes", {})
            ),
            "files_to_modify": list(
                free_cloud_result.get("files_to_modify", [])
            ),
            "model_response": _redact(model_response),
            "model_attempts": _redact(
                free_cloud_result.get("model_attempts", [])
            ),
            "evidence": _redact(
                free_cloud_result.get("evidence", {})
            ),
            "gate": _redact(
                free_cloud_result.get("gate", {})
            ),
            "approval_required": True,
            "can_apply_now": False,
            "file_write_blocked": True,
            "real_execution_blocked": True,
            "external_api_used": bool(
                free_cloud_result.get("external_api_used")
            ),
            "local_first": False,
            "free_tier_confirmed": True,
            "billing_allowed": False,
            "paid_fallback_allowed": False,
        }
        task["next_safe_action"] = (
            "OpenRouter ücretsiz modeli güvenli yama önizlemesini hazırladı. Dosya değiştirilmedi. "
            "Uygulama için yama ayrıntılarını inceleyip açık onay verin."
        )
        _touch(task, "awaiting_approval", "draft_patch")
        return


    escalation = task.get("deepseek_escalation", {})
    if (
        targets
        and isinstance(escalation, dict)
        and escalation.get("approved") is True
        and escalation.get("consumed") is not True
    ):
        task["active_engine"] = "direct_deepseek"
        task["active_model"] = DIRECT_DEEPSEEK_MODEL_ID
        task["next_safe_action"] = (
            "Free tiers did not produce a safe patch. The task-scoped paid "
            "DeepSeek approval and hard cost cap are being revalidated. "
            "No file will be written."
        )
        deepseek_result = execute_direct_deepseek_task_bridge(
            task_id=task["task_id"],
            repository_root=task.get("repository_root") or str(Path.cwd()),
            task_summary=task["original_request"],
            target_files=targets,
            target_symbols=[],
            minimum_context=minimum_context,
            previous_result={
                "free_tier_exhaustion_confirmed": True,
                "remaining_gap": {
                    "remaining_gap": (
                        "tier4_direct_deepseek_patch_draft_required"
                    ),
                    "free_cloud_state": str(
                        free_cloud_result.get("state") or "failed"
                    ),
                },
            },
            approval=escalation,
            environ=os.environ,
        )
        _record_direct_deepseek_attempt(task, deepseek_result)
        if deepseek_result.get("external_api_used"):
            escalation["consumed"] = True
            escalation["state"] = "consumed"
            escalation["consumed_at"] = _now()
            task["deepseek_escalation"] = escalation

    if deepseek_result.get("ok"):
        model_response = _normalize_dict(
            deepseek_result.get("model_response", {})
        )
        usage = _normalize_dict(
            deepseek_result.get("token_usage", {})
        )
        task["token_usage"] = (
            f"input={usage.get('input_tokens', 0)} "
            f"output={usage.get('output_tokens', 0)}"
        )
        task["provider_cost"] = str(
            deepseek_result.get("provider_cost")
            if deepseek_result.get("provider_cost") is not None
            else "cost_status=unavailable"
        )
        task["external_api_used"] = bool(
            deepseek_result.get("external_api_used")
        )
        task["network_access_used"] = bool(
            deepseek_result.get("external_api_used")
        )
        task["selected_files"] = _unique(
            task.get("selected_files", [])
            + deepseek_result.get("files_to_modify", [])
        )
        task["patch_draft_result"] = {
            "request_id": str(
                _normalize_dict(
                    deepseek_result.get("evidence", {})
                ).get("evidence_id")
                or ""
            ),
            "mode": "preview",
            "source": "direct_deepseek",
            "runtime_id": "deepseek_chat_completions",
            "provider_id": "deepseek",
            "model_id": DIRECT_DEEPSEEK_MODEL_ID,
            "repository_root": task.get("repository_root", ""),
            "issue_summary": diagnosis.get("normalized_issue")
            or task["original_request"],
            "analysis_summary": model_response.get(
                "analysis_summary", ""
            ),
            "patch_steps": list(
                deepseek_result.get("patch_steps", [])
            ),
            "expected_file_hashes": dict(
                deepseek_result.get("expected_file_hashes", {})
            ),
            "files_to_modify": list(
                deepseek_result.get("files_to_modify", [])
            ),
            "model_response": _redact(model_response),
            "transport": _redact(
                deepseek_result.get("transport", {})
            ),
            "evidence": _redact(
                deepseek_result.get("evidence", {})
            ),
            "approval_required": True,
            "can_apply_now": False,
            "file_write_blocked": True,
            "real_execution_blocked": True,
            "external_api_used": bool(
                deepseek_result.get("external_api_used")
            ),
            "local_first": False,
            "free_tiers_exhausted": True,
            "paid_escalation_approved": True,
            "maximum_cost_usd": deepseek_result.get(
                "maximum_cost_usd", 0.001
            ),
            "automatic_purchase_allowed": False,
            "automatic_upgrade_allowed": False,
        }
        task["next_safe_action"] = (
            "Direct DeepSeek produced a validated paid safe patch preview. "
            "No file was changed. Review the patch and approve apply separately."
        )
        _touch(task, "awaiting_approval", "draft_patch")
        return


    codewhale_escalation = task.get("codewhale_escalation", {})
    if (
        targets
        and isinstance(codewhale_escalation, dict)
        and codewhale_escalation.get("approved") is True
        and codewhale_escalation.get("consumed") is not True
    ):
        task["active_engine"] = "whale"
        task["active_model"] = "configured_codewhale_model"
        task["next_safe_action"] = (
            "CodeWhale manual one-shot approval is being revalidated. "
            "The CLI will run without --auto or --continue and no file may change."
        )
        codewhale_result = execute_codewhale_task_bridge(
            task_id=task["task_id"],
            repository_root=task.get("repository_root") or str(Path.cwd()),
            task_summary=task["original_request"],
            target_files=targets,
            minimum_context=minimum_context,
            approval=codewhale_escalation,
            environ=os.environ,
        )
        _record_codewhale_attempt(task, codewhale_result)
        if codewhale_result.get("process_started"):
            codewhale_escalation["consumed"] = True
            codewhale_escalation["state"] = "consumed"
            codewhale_escalation["consumed_at"] = _now()
            task["codewhale_escalation"] = codewhale_escalation

    if codewhale_result.get("ok"):
        model_response = _normalize_dict(
            codewhale_result.get("model_response", {})
        )
        task["provider_cost"] = str(
            codewhale_result.get("provider_cost")
            or "unavailable_manual_agent"
        )
        task["external_api_used"] = bool(
            codewhale_result.get("external_api_used")
        )
        task["network_access_used"] = bool(
            codewhale_result.get("external_api_used")
        )
        task["selected_files"] = _unique(
            task.get("selected_files", [])
            + codewhale_result.get("files_to_modify", [])
        )
        task["patch_draft_result"] = {
            "request_id": str(
                _normalize_dict(
                    codewhale_result.get("evidence", {})
                ).get("evidence_id")
                or ""
            ),
            "mode": "preview",
            "source": "whale",
            "runtime_id": "codewhale_cli",
            "provider_id": str(
                codewhale_result.get("provider_id") or ""
            ),
            "model_id": str(
                codewhale_result.get("model_id") or ""
            ),
            "repository_root": task.get("repository_root", ""),
            "issue_summary": diagnosis.get("normalized_issue")
            or task["original_request"],
            "analysis_summary": model_response.get(
                "analysis_summary", ""
            ),
            "patch_steps": list(
                codewhale_result.get("patch_steps", [])
            ),
            "expected_file_hashes": dict(
                codewhale_result.get("expected_file_hashes", {})
            ),
            "files_to_modify": list(
                codewhale_result.get("files_to_modify", [])
            ),
            "model_response": _redact(model_response),
            "process": _redact(
                codewhale_result.get("process", {})
            ),
            "evidence": _redact(
                codewhale_result.get("evidence", {})
            ),
            "approval_required": True,
            "can_apply_now": False,
            "file_write_blocked": True,
            "real_execution_blocked": True,
            "external_api_used": bool(
                codewhale_result.get("external_api_used")
            ),
            "manual_only": True,
            "auto_mode_used": False,
            "continue_mode_used": False,
            "provider_cost": "unavailable_manual_agent",
        }
        task["next_safe_action"] = (
            "CodeWhale manual one-shot produced a validated safe patch preview. "
            "No file was changed. Review and approve apply separately."
        )
        _touch(task, "awaiting_approval", "draft_patch")
        return


    codex_escalation = task.get("codex_escalation", {})
    if (
        targets
        and isinstance(codex_escalation, dict)
        and codex_escalation.get("approved") is True
        and codex_escalation.get("consumed") is not True
    ):
        task["active_engine"] = "codex"
        task["active_model"] = "account_default"
        task["next_safe_action"] = (
            "Codex emergency one-shot approval is being revalidated. "
            "The CLI is restricted to read-only sandbox with approval policy never."
        )
        codex_result = execute_codex_task_bridge(
            task_id=task["task_id"],
            repository_root=task.get("repository_root") or str(Path.cwd()),
            task_summary=task["original_request"],
            target_files=targets,
            minimum_context=minimum_context,
            approval=codex_escalation,
            environ=os.environ,
        )
        _record_codex_attempt(task, codex_result)
        if codex_result.get("process_started"):
            codex_escalation["consumed"] = True
            codex_escalation["state"] = "consumed"
            codex_escalation["consumed_at"] = _now()
            task["codex_escalation"] = codex_escalation

    if codex_result.get("ok"):
        model_response = _normalize_dict(
            codex_result.get("model_response", {})
        )
        task["provider_cost"] = str(
            codex_result.get("provider_cost")
            or "chatgpt_plan_credit_or_unknown_manual_agent"
        )
        task["external_api_used"] = bool(
            codex_result.get("external_api_used")
        )
        task["network_access_used"] = bool(
            codex_result.get("external_api_used")
        )
        task["selected_files"] = _unique(
            task.get("selected_files", [])
            + codex_result.get("files_to_modify", [])
        )
        task["patch_draft_result"] = {
            "request_id": str(
                _normalize_dict(
                    codex_result.get("evidence", {})
                ).get("evidence_id")
                or ""
            ),
            "mode": "preview",
            "source": "codex",
            "runtime_id": "codex_cli",
            "model_id": "account_default",
            "repository_root": task.get("repository_root", ""),
            "issue_summary": diagnosis.get("normalized_issue")
            or task["original_request"],
            "analysis_summary": model_response.get(
                "analysis_summary", ""
            ),
            "patch_steps": list(
                codex_result.get("patch_steps", [])
            ),
            "expected_file_hashes": dict(
                codex_result.get("expected_file_hashes", {})
            ),
            "files_to_modify": list(
                codex_result.get("files_to_modify", [])
            ),
            "model_response": _redact(model_response),
            "process": _redact(
                codex_result.get("process", {})
            ),
            "evidence": _redact(
                codex_result.get("evidence", {})
            ),
            "approval_required": True,
            "can_apply_now": False,
            "file_write_blocked": True,
            "real_execution_blocked": True,
            "external_api_used": bool(
                codex_result.get("external_api_used")
            ),
            "manual_only": True,
            "emergency_only": True,
            "sandbox_mode": "read-only",
            "approval_policy": "never",
            "dangerous_bypass_used": False,
            "provider_cost": (
                "chatgpt_plan_credit_or_unknown_manual_agent"
            ),
        }
        task["next_safe_action"] = (
            "Codex emergency read-only run produced a validated safe patch preview. "
            "No file was changed. Review and approve apply separately."
        )
        _touch(task, "awaiting_approval", "draft_patch")
        return

    task["active_engine"] = "deterministic_local_tools"
    task["active_model"] = "-"
    draft = build_safe_patch_draft(
        issue_summary=diagnosis.get("normalized_issue") or task["original_request"],
        root_cause_hypotheses=diagnosis.get("root_cause_hypotheses", []),
        selected_context=diagnosis.get("selected_context", []),
        requested_files=task.get("requested_files") or task.get("selected_files", []),
        forbidden_files=task.get("forbidden_files", []),
        repository_root=task.get("repository_root") or None,
        change_intent=task["original_request"],
        mode="preview",
        max_patch_files=4,
        max_hunks_per_file=3,
    )
    if local_result:
        draft["local_worker_fallback"] = {
            "state": str(local_result.get("state") or "failed"),
            "error": str(local_result.get("error") or ""),
            "evidence": _redact(local_result.get("evidence", {})),
        }
    if gemini_result:
        draft["free_gemini_fallback"] = {
            "state": str(gemini_result.get("state") or "skipped"),
            "error": str(gemini_result.get("error") or ""),
            "transport_called": bool(gemini_result.get("transport_called")),
            "gate": _redact(gemini_result.get("gate", {})),
            "evidence": _redact(gemini_result.get("evidence", {})),
        }
    if free_cloud_result:
        draft["free_cloud_fallback"] = {
            "state": str(free_cloud_result.get("state") or "skipped"),
            "error": str(free_cloud_result.get("error") or ""),
            "models_attempted": _redact(
                free_cloud_result.get("model_attempts", [])
            ),
            "external_api_used": bool(
                free_cloud_result.get("external_api_used")
            ),
            "external_service_deferred": bool(
                free_cloud_result.get("external_service_deferred")
            ),
            "deferred_retry": _redact(
                free_cloud_result.get("deferred_retry", {})
            ),
            "gate": _redact(free_cloud_result.get("gate", {})),
            "evidence": _redact(
                free_cloud_result.get("evidence", {})
            ),
        }
    if codex_result:
        draft["codex_fallback"] = {
            "state": str(
                codex_result.get("state") or "skipped"
            ),
            "blockers": _redact(
                codex_result.get("blockers", [])
            ),
            "process": _redact(
                codex_result.get("process", {})
            ),
            "evidence": _redact(
                codex_result.get("evidence", {})
            ),
            "external_api_used": bool(
                codex_result.get("external_api_used")
            ),
            "manual_only": True,
            "emergency_only": True,
            "sandbox_mode": "read-only",
            "approval_policy": "never",
            "dangerous_bypass_used": False,
            "provider_cost": (
                "chatgpt_plan_credit_or_unknown_manual_agent"
            ),
        }
    if codewhale_result:
        draft["codewhale_fallback"] = {
            "state": str(
                codewhale_result.get("state") or "skipped"
            ),
            "blockers": _redact(
                codewhale_result.get("blockers", [])
            ),
            "process": _redact(
                codewhale_result.get("process", {})
            ),
            "evidence": _redact(
                codewhale_result.get("evidence", {})
            ),
            "external_api_used": bool(
                codewhale_result.get("external_api_used")
            ),
            "manual_only": True,
            "auto_mode_used": False,
            "provider_cost": "unavailable_manual_agent",
        }
    if deepseek_result:
        draft["direct_deepseek_fallback"] = {
            "state": str(
                deepseek_result.get("state") or "skipped"
            ),
            "blockers": _redact(
                deepseek_result.get("blockers", [])
            ),
            "transport": _redact(
                deepseek_result.get("transport", {})
            ),
            "evidence": _redact(
                deepseek_result.get("evidence", {})
            ),
            "external_api_used": bool(
                deepseek_result.get("external_api_used")
            ),
            "provider_cost": str(
                deepseek_result.get("provider_cost")
                if deepseek_result.get("provider_cost") is not None
                else "unavailable"
            ),
        }
    if (
        local_result
        or gemini_result
        or free_cloud_result
        or deepseek_result
        or codewhale_result
        or codex_result
    ):
        task["next_safe_action"] = (
            "Ollama, izinli Gemini, OpenRouter ücretsiz yolları, varsa "
            "task-scoped Direct DeepSeek, manuel CodeWhale ve acil durum "
            "Codex denemesi güvenli bir yama üretemedi; deterministik güvenli "
            "önizlemeye dönüldü. "
            "Dosya değiştirilmedi."
        )
    else:
        task["next_safe_action"] = "Review patch draft and submit exact approval before apply preparation."
    task["patch_draft_result"] = draft
    _touch(task, "awaiting_approval", "draft_patch")


def _prepare_apply(task: Dict[str, Any]) -> None:
    ok, reason = _approval_valid(task)
    if not ok:
        task["next_safe_action"] = "Review patch draft and submit exact approval before apply preparation."
        _block(task, reason, "awaiting_approval")
        return
    if "prepare_apply" in task["completed_steps"]:
        return
    approval = task["approval_state"]["approval_snapshot"]
    result = prepare_controlled_apply(
        repository_root=approval["repository_root"],
        patch_id=approval["patch_id"],
        patch_steps=approval["patch_steps"],
        approved_files=approval["approved_files"],
        forbidden_files=task.get("forbidden_files", []),
        expected_file_hashes=approval["expected_file_hashes"],
        mode="prepare",
        require_clean_tree=False,
    )
    task["apply_result"] = result
    task["next_safe_action"] = "Apply requires explicit apply_execution approval; no automatic apply occurs."
    _touch(task, "apply_prepared", "prepare_apply")


def _execute_apply(task: Dict[str, Any]) -> None:
    if "apply" in task["completed_steps"]:
        return
    ok, reason = _approval_valid(task)
    if not ok:
        _block(task, reason, "awaiting_approval")
        return
    if not task.get("approval_state", {}).get("apply_execution_approved"):
        _block(task, "apply execution requires explicit approval", "apply_prepared")
        return
    approval = task["approval_state"]["approval_snapshot"]
    _touch(task, "applying")
    result = execute_controlled_apply(
        repository_root=approval["repository_root"],
        patch_id=approval["patch_id"],
        patch_steps=approval["patch_steps"],
        approved_files=approval["approved_files"],
        forbidden_files=task.get("forbidden_files", []),
        approval_token=task["approval_state"].get("controlled_apply_approval_token"),
        expected_file_hashes=approval["expected_file_hashes"],
        mode="apply",
        require_clean_tree=False,
    )
    task["apply_result"] = result
    if result.get("transaction_state") == "applied":
        task["changed_files"] = _unique(task.get("changed_files", []) + result.get("files_changed", []))
        task["next_safe_action"] = "Advance to prepare verification."
        _touch(task, "applied", "apply")
    else:
        _block(task, "controlled apply did not complete", "blocked")


def _prepare_verification(task: Dict[str, Any]) -> None:
    if "prepare_verification" in task["completed_steps"]:
        return
    checks = task.get("verification_checks") or [
        {"check_type": "py_compile", "check_id": "compile_changed", "files": task.get("changed_files", [])[:5]},
        {"check_type": "git_diff_check", "check_id": "diff_check"},
    ]
    result = prepare_verification_run(
        repository_root=task.get("repository_root") or None,
        verification_id=_digest([task["task_id"], "verification"]),
        changed_files=task.get("changed_files", []),
        requested_checks=checks,
        mode="prepare",
        max_checks=4,
        timeout_seconds=20,
        controlled_apply_result=task.get("apply_result", {}),
    )
    task["verification_result"] = result
    task["next_safe_action"] = "Verification execution requires exact verification approval."
    _touch(task, "verification_prepared", "prepare_verification")


def _execute_verification(task: Dict[str, Any]) -> None:
    if "execute_verification" in task["completed_steps"]:
        return
    if not task.get("approval_state", {}).get("verification_execution_approved"):
        _block(task, "verification execution requires explicit approval", "verification_prepared")
        return
    prepared = task.get("verification_result", {})
    result = execute_verification_run(
        repository_root=task.get("repository_root") or None,
        verification_id=prepared.get("verification_id"),
        changed_files=task.get("changed_files", []),
        requested_checks=task.get("verification_checks") or [
            {"check_type": "py_compile", "check_id": "compile_changed", "files": task.get("changed_files", [])[:5]},
            {"check_type": "git_diff_check", "check_id": "diff_check"},
        ],
        approval_token=task["approval_state"].get("verification_approval_token"),
        mode="execute",
        max_checks=4,
        timeout_seconds=20,
        controlled_apply_result=task.get("apply_result", {}),
    )
    task["verification_result"] = result
    summary = result.get("summary", {})
    if summary.get("failed") or summary.get("timed_out") or summary.get("blocked"):
        task["recovery_result"] = prepare_recovery_action(
            repository_root=task.get("repository_root") or None,
            verification_id=result.get("verification_id"),
            changed_files=task.get("changed_files", []),
            controlled_apply_result=task.get("apply_result", {}),
            check_results=result.get("check_results", []),
            allow_automatic_rollback=False,
            mode="recovery_preview",
        )
        decision = task["recovery_result"].get("recovery_decision")
        if decision == "rollback_recommended":
            _touch(task, "rollback_recommended", "execute_verification")
        else:
            _touch(task, "recovery_review", "execute_verification")
        task["next_safe_action"] = task["recovery_result"].get("safe_next_step", "Review recovery result.")
    else:
        task["next_safe_action"] = "Task verified; no recovery needed."
        _touch(task, "completed", "execute_verification")



def request_luxcode_deepseek_escalation(
    task_id: str,
    maximum_cost_usd: float = 0.001,
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {
            "task_id": task_id,
            "found": False,
            "safe_response": True,
            **SAFE_INVARIANTS,
        }
    if task["current_state"] in EXECUTION_BLOCKED_STATES:
        return _summary(task)
    if "draft_patch" in task.get("completed_steps", []):
        task["next_safe_action"] = (
            "DeepSeek paid escalation must be requested before patch drafting."
        )
        return _persist_and_summarize(
            task,
            event_type="deepseek_escalation_request_rejected",
            previous_state=task["current_state"],
        )
    try:
        bounded_cost = max(0.0, min(float(maximum_cost_usd), 0.001))
    except (TypeError, ValueError):
        bounded_cost = 0.001
    package = build_direct_deepseek_task_approval(
        task_id=task_id,
        repository_root=task.get("repository_root") or str(Path.cwd()),
        target_files=task.get("requested_files")
        or task.get("selected_files", []),
        maximum_cost_usd=bounded_cost,
        model_id=DIRECT_DEEPSEEK_MODEL_ID,
    )
    task["deepseek_escalation"] = {
        **package,
        "state": "approval_required",
        "approved": False,
        "consumed": False,
        "confirmation_text": "",
        "requested_at": _now(),
        "approved_at": "",
    }
    task["next_safe_action"] = (
        "Direct DeepSeek is paid. Review the task-scoped approval digest, "
        f"maximum cost ${bounded_cost:.6f}, and submit the exact confirmation "
        f"text: {DEEPSEEK_EXACT_APPROVAL_TEXT}"
    )
    return _persist_and_summarize(
        task,
        event_type="deepseek_escalation_requested",
        previous_state=task["current_state"],
    )


def approve_luxcode_deepseek_escalation(
    task_id: str,
    approval_digest: str,
    confirmation_text: str,
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {
            "task_id": task_id,
            "found": False,
            "safe_response": True,
            **SAFE_INVARIANTS,
        }
    if task["current_state"] in EXECUTION_BLOCKED_STATES:
        return _summary(task)
    escalation = task.get("deepseek_escalation", {})
    if not isinstance(escalation, dict):
        escalation = {}
    expected = build_direct_deepseek_task_approval(
        task_id=task_id,
        repository_root=task.get("repository_root") or str(Path.cwd()),
        target_files=task.get("requested_files")
        or task.get("selected_files", []),
        maximum_cost_usd=escalation.get("maximum_cost_usd", 0.001),
        model_id=str(
            escalation.get("model_id") or DIRECT_DEEPSEEK_MODEL_ID
        ),
    )
    blockers = []
    if str(approval_digest or "") != expected["approval_digest"]:
        blockers.append("approval_digest_mismatch")
    if str(confirmation_text or "") != DEEPSEEK_EXACT_APPROVAL_TEXT:
        blockers.append("approval_text_mismatch")
    if escalation.get("state") != "approval_required":
        blockers.append("approval_request_missing")
    if blockers:
        escalation.update(
            {
                "state": "approval_rejected",
                "approved": False,
                "approval_blockers": blockers,
            }
        )
        task["deepseek_escalation"] = escalation
        task["next_safe_action"] = (
            "Paid DeepSeek approval was rejected; no external request was made."
        )
        return _persist_and_summarize(
            task,
            event_type="deepseek_escalation_approval_rejected",
            previous_state=task["current_state"],
        )

    escalation.update(
        {
            **expected,
            "state": "approved_for_one_request",
            "approved": True,
            "consumed": False,
            "confirmation_text": DEEPSEEK_EXACT_APPROVAL_TEXT,
            "approved_at": _now(),
            "approval_blockers": [],
        }
    )
    task["deepseek_escalation"] = escalation
    task["user_requires_free_only"] = False
    task["next_safe_action"] = (
        "One task-scoped Direct DeepSeek request is approved. "
        "Advance patch drafting to use it only after free tiers fail."
    )
    return _persist_and_summarize(
        task,
        event_type="deepseek_escalation_approved",
        previous_state=task["current_state"],
    )




def request_luxcode_codewhale_escalation(
    task_id: str,
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {
            "task_id": task_id,
            "found": False,
            "safe_response": True,
            **SAFE_INVARIANTS,
        }
    if task["current_state"] in EXECUTION_BLOCKED_STATES:
        return _summary(task)
    if "draft_patch" in task.get("completed_steps", []):
        task["next_safe_action"] = (
            "CodeWhale manual escalation must be requested before patch drafting."
        )
        return _persist_and_summarize(
            task,
            event_type="codewhale_escalation_request_rejected",
            previous_state=task["current_state"],
        )
    package = build_codewhale_task_approval(
        task_id=task_id,
        repository_root=task.get("repository_root") or str(Path.cwd()),
        target_files=task.get("requested_files")
        or task.get("selected_files", []),
    )
    task["codewhale_escalation"] = {
        **package,
        "state": "approval_required",
        "approved": False,
        "consumed": False,
        "confirmation_text": "",
        "requested_at": _now(),
        "approved_at": "",
    }
    task["next_safe_action"] = (
        "CodeWhale is configured with an external model and CLI cost telemetry "
        "is not bounded by LuxCode. Review the task-scoped digest and submit "
        f"the exact confirmation text: {CODEWHALE_EXACT_APPROVAL_TEXT}"
    )
    return _persist_and_summarize(
        task,
        event_type="codewhale_escalation_requested",
        previous_state=task["current_state"],
    )


def approve_luxcode_codewhale_escalation(
    task_id: str,
    approval_digest: str,
    confirmation_text: str,
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {
            "task_id": task_id,
            "found": False,
            "safe_response": True,
            **SAFE_INVARIANTS,
        }
    if task["current_state"] in EXECUTION_BLOCKED_STATES:
        return _summary(task)
    escalation = task.get("codewhale_escalation", {})
    if not isinstance(escalation, dict):
        escalation = {}
    expected = build_codewhale_task_approval(
        task_id=task_id,
        repository_root=task.get("repository_root") or str(Path.cwd()),
        target_files=task.get("requested_files")
        or task.get("selected_files", []),
    )
    blockers = []
    if str(approval_digest or "") != expected["approval_digest"]:
        blockers.append("approval_digest_mismatch")
    if str(confirmation_text or "") != CODEWHALE_EXACT_APPROVAL_TEXT:
        blockers.append("approval_text_mismatch")
    if escalation.get("state") != "approval_required":
        blockers.append("approval_request_missing")
    if blockers:
        escalation.update(
            {
                "state": "approval_rejected",
                "approved": False,
                "approval_blockers": blockers,
            }
        )
        task["codewhale_escalation"] = escalation
        task["next_safe_action"] = (
            "CodeWhale manual approval was rejected; no CLI process started."
        )
        return _persist_and_summarize(
            task,
            event_type="codewhale_escalation_approval_rejected",
            previous_state=task["current_state"],
        )

    escalation.update(
        {
            **expected,
            "state": "approved_for_one_request",
            "approved": True,
            "consumed": False,
            "confirmation_text": CODEWHALE_EXACT_APPROVAL_TEXT,
            "approved_at": _now(),
            "approval_blockers": [],
        }
    )
    task["codewhale_escalation"] = escalation
    task["user_requires_free_only"] = False
    task["next_safe_action"] = (
        "One manual CodeWhale plain-exec request is approved. "
        "It may run only after earlier tiers fail and will never use --auto."
    )
    return _persist_and_summarize(
        task,
        event_type="codewhale_escalation_approved",
        previous_state=task["current_state"],
    )




def request_luxcode_codex_escalation(
    task_id: str,
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {
            "task_id": task_id,
            "found": False,
            "safe_response": True,
            **SAFE_INVARIANTS,
        }
    if task["current_state"] in EXECUTION_BLOCKED_STATES:
        return _summary(task)
    if "draft_patch" in task.get("completed_steps", []):
        task["next_safe_action"] = (
            "Codex emergency escalation must be requested before patch drafting."
        )
        return _persist_and_summarize(
            task,
            event_type="codex_escalation_request_rejected",
            previous_state=task["current_state"],
        )

    package = build_codex_task_approval(
        task_id=task_id,
        repository_root=task.get("repository_root") or str(Path.cwd()),
        target_files=task.get("requested_files")
        or task.get("selected_files", []),
    )
    task["codex_escalation"] = {
        **package,
        "state": "approval_required",
        "approved": False,
        "consumed": False,
        "confirmation_text": "",
        "requested_at": _now(),
        "approved_at": "",
    }
    task["next_safe_action"] = (
        "Codex may consume ChatGPT plan credits and is emergency-only. "
        "Review the task-scoped digest and submit the exact confirmation text: "
        f"{CODEX_EXACT_APPROVAL_TEXT}"
    )
    return _persist_and_summarize(
        task,
        event_type="codex_escalation_requested",
        previous_state=task["current_state"],
    )


def approve_luxcode_codex_escalation(
    task_id: str,
    approval_digest: str,
    confirmation_text: str,
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {
            "task_id": task_id,
            "found": False,
            "safe_response": True,
            **SAFE_INVARIANTS,
        }
    if task["current_state"] in EXECUTION_BLOCKED_STATES:
        return _summary(task)

    escalation = task.get("codex_escalation", {})
    if not isinstance(escalation, dict):
        escalation = {}
    expected = build_codex_task_approval(
        task_id=task_id,
        repository_root=task.get("repository_root") or str(Path.cwd()),
        target_files=task.get("requested_files")
        or task.get("selected_files", []),
    )
    blockers = []
    if str(approval_digest or "") != expected["approval_digest"]:
        blockers.append("approval_digest_mismatch")
    if str(confirmation_text or "") != CODEX_EXACT_APPROVAL_TEXT:
        blockers.append("approval_text_mismatch")
    if escalation.get("state") != "approval_required":
        blockers.append("approval_request_missing")

    if blockers:
        escalation.update(
            {
                "state": "approval_rejected",
                "approved": False,
                "approval_blockers": blockers,
            }
        )
        task["codex_escalation"] = escalation
        task["next_safe_action"] = (
            "Codex emergency approval was rejected; no CLI process started."
        )
        return _persist_and_summarize(
            task,
            event_type="codex_escalation_approval_rejected",
            previous_state=task["current_state"],
        )

    escalation.update(
        {
            **expected,
            "state": "approved_for_one_request",
            "approved": True,
            "consumed": False,
            "confirmation_text": CODEX_EXACT_APPROVAL_TEXT,
            "approved_at": _now(),
            "approval_blockers": [],
        }
    )
    task["codex_escalation"] = escalation
    task["user_requires_free_only"] = False
    task["next_safe_action"] = (
        "One emergency Codex read-only request is approved. "
        "It may run only after earlier tiers fail; workspace writes and "
        "dangerous bypass remain forbidden."
    )
    return _persist_and_summarize(
        task,
        event_type="codex_escalation_approved",
        previous_state=task["current_state"],
    )


def advance_luxcode_task(
    task_id: str,
    action: str = "next",
    patch_steps: Optional[List[Dict[str, Any]]] = None,
    verification_checks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    if task["current_state"] in EXECUTION_BLOCKED_STATES:
        return _summary(task)
    previous_state = task["current_state"]
    allowed, _permission_result = _permission_check(task, action)
    if not allowed:
        return _persist_and_summarize(task, event_type=f"permission_pause:{action}", previous_state=previous_state)
    if patch_steps is not None:
        task["approval_state"]["patch_steps"] = deepcopy(patch_steps)
    if verification_checks is not None:
        task["verification_checks"] = deepcopy(verification_checks)
    state = task["current_state"]
    if action == "route" or (action == "next" and state == "created"):
        _advance_route(task)
    elif action == "diagnose" or (action == "next" and state == "routed"):
        _advance_diagnosis(task)
    elif action in {"draft", "patch"} or (action == "next" and state == "diagnosis_ready"):
        _advance_patch(task)
    elif action == "prepare_apply" or (action == "next" and state == "approval_verified"):
        _prepare_apply(task)
    elif action == "apply" or (action == "next" and state == "apply_prepared"):
        _execute_apply(task)
    elif action == "prepare_verification" or (action == "next" and state == "applied"):
        _prepare_verification(task)
    elif action == "execute_verification" or (action == "next" and state == "verification_prepared"):
        _execute_verification(task)
    else:
        _block(task, f"invalid transition from {state} via {action}")
    return _persist_and_summarize(task, event_type=f"advance:{action}", previous_state=previous_state)


def approve_luxcode_task_step(
    task_id: str,
    patch_id: Optional[str] = None,
    patch_digest: Optional[str] = None,
    approved_files: Optional[List[str]] = None,
    expected_file_hashes: Optional[Dict[str, str]] = None,
    patch_steps: Optional[List[Dict[str, Any]]] = None,
    repository_root: Optional[str] = None,
    approve_apply_execution: bool = False,
    controlled_apply_approval_token: Optional[str] = None,
    approve_verification_execution: bool = False,
    verification_approval_token: Optional[str] = None,
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    if task["current_state"] in EXECUTION_BLOCKED_STATES:
        return _summary(task)
    previous_state = task["current_state"]
    steps = _patch_steps(task, patch_steps)
    files = _unique(approved_files or [step.get("target_file") for step in steps if isinstance(step, dict)])
    hashes = dict(expected_file_hashes or _file_hashes(task["repository_root"], files))
    pid = patch_id or _make_patch_id(task)
    snapshot = _approval_snapshot(task, pid, steps, files, hashes)
    if repository_root and _safe_root(repository_root) != task["repository_root"]:
        _block(task, "approval repository root does not match task repository root", "awaiting_approval")
        return _persist_and_summarize(task, event_type="approval_blocked", previous_state=previous_state)
    if patch_digest and patch_digest != snapshot["patch_digest"]:
        _block(task, "approval patch digest does not match current patch", "awaiting_approval")
        return _persist_and_summarize(task, event_type="approval_blocked", previous_state=previous_state)
    task["approval_state"].update(
        {
            "approved": True,
            "approval_snapshot": snapshot,
            "patch_id": pid,
            "patch_digest": snapshot["patch_digest"],
            "approved_files": files,
            "expected_file_hashes": hashes,
            "patch_steps": steps,
            "apply_execution_approved": bool(approve_apply_execution),
            "controlled_apply_approval_token": controlled_apply_approval_token,
            "verification_execution_approved": bool(approve_verification_execution),
            "verification_approval_token": verification_approval_token,
        }
    )
    task["approval_state"].setdefault("approval_events", []).append({"approved_at": _now(), "patch_digest": snapshot["patch_digest"]})
    task["next_safe_action"] = "Advance to prepare controlled apply."
    _touch(task, "approval_verified", "approve_patch")
    return _persist_and_summarize(task, event_type="approve", previous_state=previous_state)


def cancel_luxcode_task(task_id: str, reason: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    previous_state = task["current_state"]
    task["cancellation_reason"] = reason
    task["next_safe_action"] = "Task cancelled; no execution transitions are allowed."
    _touch(task, "cancelled")
    return _persist_and_summarize(task, event_type="cancel", previous_state=previous_state)


def pause_luxcode_task(task_id: str, reason: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    if task["current_state"] in TERMINAL_STATES:
        return _summary(task)
    previous_state = task["current_state"]
    task["previous_state_before_pause"] = task["current_state"]
    task["pause_reason"] = reason
    task["next_safe_action"] = "Resume before any execution transition."
    _touch(task, "paused")
    return _persist_and_summarize(task, event_type="pause", previous_state=previous_state)


def resume_luxcode_task(task_id: str) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    if task["current_state"] != "paused":
        return _summary(task)
    previous_state = task["current_state"]
    prior = task.get("previous_state_before_pause") or "created"
    task["pause_reason"] = task.get("pause_reason", "")
    task["next_safe_action"] = "Continue from the next safe checkpoint."
    _touch(task, prior)
    return _persist_and_summarize(task, event_type="resume", previous_state=previous_state)


def get_luxcode_task_status(task_id: str) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    return _summary(task)


def get_task_orchestrator_status() -> Dict[str, Any]:
    states = [task["current_state"] for task in _TASKS.values()]
    return {
        "name": "LuxCode Task Orchestrator & Continuity Core",
        "status": "ready",
        "state_storage": "in_memory_with_optional_local_persistence",
        "known_limitation": "persistence is disabled until explicitly initialized",
        "persistence": {
            "enabled": bool(_PERSISTENCE_CONFIG.get("enabled")),
            **get_task_persistence_status(
                mode=_PERSISTENCE_CONFIG.get("mode"),
                storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
            ),
        },
        "autonomy_permission": get_autonomy_permission_status(),
        "terminal_runtime": "available_for_structured_actions",
        "live_testing": "available_for_localhost_structured_scenarios",
        "test_matrix": "available_for_browser_device_screen_network_verification",
        "multi_agent": {
            "metadata_fields": sorted(MULTI_AGENT_METADATA_KEYS),
            "execution_enabled": False,
            "paid_escalation_auto_enabled": False,
            "whale_auto_start": False,
            "codex_auto_start": False,
        },
        "task_count": len(_TASKS),
        "active_task_count": sum(1 for state in states if state not in TERMINAL_STATES and state != "paused"),
        "paused_task_count": states.count("paused"),
        "blocked_task_count": states.count("blocked"),
        "completed_task_count": states.count("completed"),
        "available_endpoints": [
            "/luxcode-task/schema",
            "/luxcode-task/create",
            "/luxcode-task/advance",
            "/luxcode-task/approve",
            "/luxcode-task/pause",
            "/luxcode-task/resume",
            "/luxcode-task/cancel",
            "/luxcode-task/{task_id}",
            "/debug/luxcode-task-orchestrator-status",
        ],
        **SAFE_INVARIANTS,
    }


def configure_luxcode_task_persistence(mode: str = "disabled", storage_root: Optional[str] = None, privacy_mode: bool = True) -> Dict[str, Any]:
    result = initialize_task_store(mode=mode, storage_root=storage_root, privacy_mode=privacy_mode)
    _PERSISTENCE_CONFIG.update({"mode": mode, "storage_root": storage_root or "", "enabled": mode != "disabled"})
    return result


def save_luxcode_task_to_persistence(task_id: str, expected_revision: Optional[int] = None) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = save_task_state(
        task,
        expected_revision=expected_revision if expected_revision is not None else task.get("persistence_revision"),
        mode=_PERSISTENCE_CONFIG.get("mode"),
        storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
        event_type="manual_save",
    )
    if result.get("ok") and result.get("revision") is not None:
        task["persistence_revision"] = int(result["revision"])
        task.pop("persistence_warning", None)
    elif not result.get("ok"):
        task["persistence_warning"] = result.get("error", "persistence save failed")
    return result


def load_luxcode_task_from_persistence(task_id: str, include_deleted: bool = False) -> Dict[str, Any]:
    result = load_task_state(
        task_id=task_id,
        mode=_PERSISTENCE_CONFIG.get("mode"),
        storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
        include_deleted=include_deleted,
    )
    if not result.get("ok") or not result.get("found"):
        return result
    ok, error = _restore_payload_to_task(result["task"])
    if not ok:
        return {"ok": False, "error": error, **SAFE_INVARIANTS}
    return {"ok": True, "task": _summary(_TASKS[task_id]), "execution_triggered": False, **SAFE_INVARIANTS}


def list_luxcode_persisted_tasks(**kwargs: Any) -> Dict[str, Any]:
    return list_task_states(
        mode=_PERSISTENCE_CONFIG.get("mode"),
        storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
        **kwargs,
    )


def archive_luxcode_persisted_task(task_id: str, expected_revision: Optional[int] = None) -> Dict[str, Any]:
    return archive_task_state(
        task_id=task_id,
        mode=_PERSISTENCE_CONFIG.get("mode"),
        storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
        expected_revision=expected_revision,
    )


def delete_luxcode_persisted_task(
    task_id: str,
    hard_delete: bool = False,
    approval_token: str = "",
    confirmation_phrase: str = "",
) -> Dict[str, Any]:
    return delete_task_state(
        task_id=task_id,
        mode=_PERSISTENCE_CONFIG.get("mode"),
        storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
        hard_delete=hard_delete,
        approval_token=approval_token,
        confirmation_phrase=confirmation_phrase,
    )


def restore_luxcode_active_tasks(limit: int = 50) -> Dict[str, Any]:
    result = restore_active_tasks(
        mode=_PERSISTENCE_CONFIG.get("mode"),
        storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
        limit=limit,
    )
    if not result.get("ok"):
        return result
    restored = []
    for payload in result.get("restored_tasks", []):
        ok, error = _restore_payload_to_task(payload)
        restored.append({"task_id": payload.get("task_id"), "restored": ok, "error": error, "execution_triggered": False})
    return {"ok": True, "restored_tasks": restored, "restored_count": len(restored), "execution_triggered": False, **SAFE_INVARIANTS}


def approve_luxcode_task_scope_expansion(
    task_id: str,
    requested_path: str,
    requested_operation: str = "read",
    approval_option: str = "allow_read_once",
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = approve_scope_expansion(
        profile=task.get("permission_profile", {}),
        requested_path=requested_path,
        requested_operation=requested_operation,
        approval_option=approval_option,
        repository_root=task.get("repository_root"),
    )
    if result.get("ok") and result.get("profile"):
        task["permission_profile"] = result["profile"]
        task["safe_permission_metadata"] = get_safe_permission_metadata(result["profile"])
        if task.get("current_state") == "awaiting_scope_permission":
            _touch(task, task.get("previous_state_before_scope_pause") or "created")
        task["next_safe_action"] = "Scope permission updated; explicitly advance to continue."
    return _persist_and_summarize(task, event_type="scope_permission_update")


def revoke_luxcode_task_scope(task_id: str, target_path: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = revoke_scope_access(profile=task.get("permission_profile", {}), target_path=target_path)
    if result.get("ok") and result.get("profile"):
        task["permission_profile"] = result["profile"]
        task["safe_permission_metadata"] = get_safe_permission_metadata(result["profile"])
        task["next_safe_action"] = "Scope access revoked immediately."
    return _persist_and_summarize(task, event_type="scope_permission_revoke")


def plan_luxcode_task_terminal_action(
    task_id: str,
    action_type: str,
    working_directory: str = ".",
    executable: str = "python",
    arguments: Optional[List[Any]] = None,
    timeout_seconds: int = 30,
    process_mode: str = "foreground",
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = plan_terminal_action(
        action_type=action_type,
        repository_root=task.get("repository_root") or str(Path.cwd()),
        working_directory=working_directory,
        executable=executable,
        arguments=arguments or [],
        timeout_seconds=timeout_seconds,
        process_mode=process_mode,
        permission_profile=task.get("permission_profile", {}),
        metadata={"task_id": task_id},
    )
    task["terminal_runtime_plan"] = result.get("plan", result)
    return _persist_and_summarize(task, event_type="terminal_runtime_plan")


def execute_luxcode_task_terminal_action(task_id: str, approval_digest: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = execute_terminal_action(task.get("terminal_runtime_plan", {}), approval_digest=approval_digest)
    if result.get("runtime"):
        task["terminal_runtime_result"] = get_safe_runtime_metadata(result["runtime"])
    else:
        task["terminal_runtime_result"] = result
    return _persist_and_summarize(task, event_type="terminal_runtime_execute")


def cancel_luxcode_task_terminal_runtime(task_id: str, runtime_id: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = cancel_terminal_runtime(task_id=task_id, runtime_id=runtime_id)
    task["terminal_runtime_result"] = result
    return _persist_and_summarize(task, event_type="terminal_runtime_cancel")


def plan_luxcode_task_live_test(
    task_id: str,
    scenario: Dict[str, Any],
    working_directory: str = ".",
    service: Optional[Dict[str, Any]] = None,
    approval_digest: str = "",
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    scenario = dict(scenario or {})
    scenario.setdefault("task_id", task_id)
    result = plan_live_test(
        scenario=scenario,
        repository_root=task.get("repository_root") or str(Path.cwd()),
        working_directory=working_directory,
        permission_profile=task.get("permission_profile", {}),
        service=service,
        approval_digest=approval_digest,
    )
    task["live_test_plan"] = result.get("plan", result)
    return _persist_and_summarize(task, event_type="live_test_plan")


def execute_luxcode_task_live_test(task_id: str, approval_digest: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = execute_live_test(task.get("live_test_plan", {}), approval_digest=approval_digest)
    if result.get("runtime"):
        task["live_test_result"] = get_safe_live_test_metadata(result["runtime"])
    else:
        task["live_test_result"] = result
    return _persist_and_summarize(task, event_type="live_test_execute")


def cancel_luxcode_task_live_test(task_id: str, runtime_id: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    target_runtime = runtime_id or task.get("live_test_result", {}).get("live_test_runtime_id") or task.get("live_test_plan", {}).get("live_test_runtime_id", "")
    result = cancel_live_test_runtime(target_runtime, reason=f"task {task_id} cancelled")
    task["live_test_result"] = result.get("runtime", result)
    return _persist_and_summarize(task, event_type="live_test_cancel")


def plan_luxcode_task_deployment(
    task_id: str,
    provider: str = "local_fixture",
    selected_scope: str = ".",
    command_text: str = "",
    deploy_intent: bool = False,
    verify_url_intent: bool = False,
    external_network_allowed: bool = False,
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    intent = bool(deploy_intent or task.get("deployment_intent"))
    result = build_deployment_plan(
        task_id=task_id,
        repository_root=task.get("repository_root") or str(Path.cwd()),
        selected_scope=selected_scope,
        provider=provider,
        command_text=command_text or task.get("original_request", ""),
        deploy_intent=intent,
        verify_url_intent=verify_url_intent,
        permission_profile=task.get("permission_profile", {}),
        external_network_allowed=external_network_allowed,
    )
    task["deployment_plan"] = result.get("plan", result)
    task["deployment_provider"] = provider
    task["deployment_state"] = "deployment_planned" if result.get("ok") else "deployment_blocked"
    task["deployment_next_safe_action"] = "Execute deployment only with explicit intent; restored tasks never auto-deploy."
    _touch(task, "deployment_planned" if result.get("ok") else "deployment_blocked")
    return _persist_and_summarize(task, event_type="deployment_plan")


def execute_luxcode_task_deployment(task_id: str, explicit_deployment_intent: bool = False) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    if task.get("restored_from_persistence"):
        task["deployment_state"] = "deployment_blocked"
        task["deployment_next_safe_action"] = "Restored deployment requires explicit user review before execution."
        return _persist_and_summarize(task, event_type="deployment_restore_blocked")
    plan = task.get("deployment_plan", {})
    if not explicit_deployment_intent or not plan.get("permission_decision", {}).get("deployment_intent"):
        task["deployment_state"] = "deployment_blocked"
        task["deployment_next_safe_action"] = "Explicit deployment intent is required."
        return _persist_and_summarize(task, event_type="deployment_intent_blocked")
    task["deployment_state"] = "deployment_running"
    _touch(task, "deployment_running")
    result = execute_deployment(plan)
    runtime = result.get("runtime", result)
    task["deployment_result"] = get_safe_deployment_metadata(runtime) if result.get("runtime") else runtime
    task["deployment_build_state"] = runtime.get("build_state", "")
    task["deployment_state"] = runtime.get("deployment_state", "deployment_review")
    task["deployment_url_verification_state"] = runtime.get("url_result", {}).get("final_verification_status", "")
    task["deployment_scenario_state"] = runtime.get("scenario_state", "")
    task["deployment_rollback_state"] = runtime.get("rollback_state", "")
    if task["deployment_url_verification_state"] == "fully_verified":
        _touch(task, "deployment_verified")
    elif result.get("ok"):
        _touch(task, "deployment_review")
    else:
        _touch(task, "deployment_blocked")
    task["deployment_next_safe_action"] = "Deliver URL only when final verification status is fully_verified."
    return _persist_and_summarize(task, event_type="deployment_execute")


def cancel_luxcode_task_deployment(task_id: str, runtime_id: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    target_runtime = runtime_id or task.get("deployment_result", {}).get("deployment_runtime_id", "")
    result = cancel_deployment(runtime_id=target_runtime, reason=f"task {task_id} cancelled")
    task["deployment_result"] = result.get("runtime", result)
    task["deployment_state"] = "cancelled" if result.get("ok") else "deployment_blocked"
    return _persist_and_summarize(task, event_type="deployment_cancel")


def plan_luxcode_task_render_deployment(
    task_id: str,
    selected_scope: str = ".",
    service_candidate_id: str = "",
    credential_reference: Optional[Dict[str, Any]] = None,
    external_network_allowed: bool = False,
    final_confirmation: bool = False,
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    readiness = analyze_render_readiness(
        repository_root=task.get("repository_root") or str(Path.cwd()),
        selected_scope=selected_scope,
        service_candidate_id=service_candidate_id,
        credential_reference=credential_reference or {},
        external_network_allowed=external_network_allowed,
        deployment_intent=bool(task.get("render_intent")),
        final_confirmation=final_confirmation,
    )
    task["render_readiness_state"] = readiness.get("readiness", {}).get("readiness_state", "render_manual_review_required")
    task["render_service_candidates"] = readiness.get("readiness", {}).get("detection", {}).get("service_candidates", [])
    plan = build_render_deployment_plan(
        task_id=task_id,
        repository_root=task.get("repository_root") or str(Path.cwd()),
        selected_scope=selected_scope,
        service_candidate_id=service_candidate_id,
        credential_reference=credential_reference or {},
        external_network_allowed=external_network_allowed,
        deployment_intent=bool(task.get("render_intent")),
        final_confirmation=final_confirmation,
    )
    task["render_plan"] = plan.get("plan", plan)
    task["render_deployment_state"] = "render_planned" if plan.get("ok") else "render_blocked"
    task["render_credential_reference_state"] = task["render_plan"].get("credential_reference", {}).get("availability", "not_configured") if isinstance(task["render_plan"], dict) else "not_configured"
    task["render_network_permission_state"] = task["render_plan"].get("network_permission_state", "blocked_by_external_network_policy") if isinstance(task["render_plan"], dict) else "blocked"
    task["render_final_confirmation_state"] = task["render_plan"].get("final_confirmation_state", "required") if isinstance(task["render_plan"], dict) else "required"
    _touch(task, "render_planned" if plan.get("ok") else "render_blocked")
    return _persist_and_summarize(task, event_type="render_plan")


def execute_luxcode_task_render_dry_run(task_id: str, fixture: str = "success") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    if task.get("restored_from_persistence"):
        task["render_deployment_state"] = "render_blocked"
        return _persist_and_summarize(task, event_type="render_restore_blocked")
    result = execute_render_dry_run(task.get("render_plan", {}), fixture=fixture)
    runtime = result.get("runtime", result)
    task["render_result"] = get_safe_render_metadata(runtime) if result.get("runtime") else runtime
    task["render_deployment_state"] = runtime.get("lifecycle_state", "render_manual_review_required")
    task["render_url_state"] = runtime.get("url_result", {}).get("final_verification_status", "")
    task["render_health_state"] = "render_health_verified" if "render_health_verified" in runtime.get("events", []) else ""
    task["render_scenario_state"] = "render_scenario_verified" if "render_scenario_verified" in runtime.get("events", []) else ""
    task["render_rollback_state"] = runtime.get("rollback_state", "")
    _touch(task, "render_dry_run_completed" if result.get("ok") else "render_blocked")
    return _persist_and_summarize(task, event_type="render_dry_run")


def plan_luxcode_task_render_gateway(
    task_id: str,
    expected_plan_digest: str = "",
    selected_service_id: str = "",
    transport_type: str = "disabled_transport",
    credential_reference: Optional[Dict[str, Any]] = None,
    final_confirmation: bool = False,
    fake_fixture: str = "success_web_service",
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    plan = task.get("render_plan", {})
    if task.get("restored_from_persistence"):
        task["render_gateway_state"] = "render_gateway_blocked"
        task["render_gateway_next_safe_action"] = "Restored tasks require user action before gateway execution."
        return _persist_and_summarize(task, event_type="render_gateway_restore_blocked")
    authority = evaluate_render_execution_authority(
        plan=plan,
        expected_plan_digest=expected_plan_digest or plan.get("plan_digest", ""),
        task_id=task_id,
        selected_service_id=selected_service_id or plan.get("service_candidate_id", ""),
        access_mode=task.get("permission_profile", {}).get("access_mode", "controlled_access"),
        deployment_intent=bool(task.get("render_intent") or plan.get("deployment_intent")),
        credential_reference=credential_reference or plan.get("credential_reference", {}),
        transport_type=transport_type,
        final_confirmation=final_confirmation,
    )
    request = build_render_execution_request(
        plan=plan,
        expected_plan_digest=expected_plan_digest or plan.get("plan_digest", ""),
        task_id=task_id,
        selected_service_id=selected_service_id or plan.get("service_candidate_id", ""),
        transport_type=transport_type,
        credential_reference=credential_reference or plan.get("credential_reference", {}),
        deployment_intent=bool(task.get("render_intent") or plan.get("deployment_intent")),
        permission_decision=authority.get("authority", {}),
        final_confirmation=final_confirmation,
        access_mode=task.get("permission_profile", {}).get("access_mode", "controlled_access"),
        fake_fixture=fake_fixture,
    )
    task["render_gateway_authority_state"] = authority.get("authority", {}).get("authority_state")
    task["render_gateway_transport_selection"] = transport_type
    task["render_gateway_credential_reference_state"] = authority.get("authority", {}).get("credential_reference_state", {}).get("availability")
    task["render_gateway_network_permission_state"] = authority.get("authority", {}).get("external_network_policy")
    task["render_gateway_production_enablement_state"] = "disabled_by_policy"
    task["render_gateway_final_confirmation_state"] = "confirmed" if final_confirmation else "required"
    task["render_gateway_request"] = request.get("request", request)
    task["render_gateway_deployment_request_state"] = "created" if request.get("ok") else "blocked"
    task["render_gateway_state"] = "render_gateway_planned" if request.get("ok") else "render_gateway_blocked"
    task["render_gateway_next_safe_action"] = authority.get("authority", {}).get("next_safe_action")
    _touch(task, "render_gateway_planned" if request.get("ok") else "render_gateway_blocked")
    return _persist_and_summarize(task, event_type="render_gateway_plan")


def execute_luxcode_task_render_gateway(task_id: str) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    if task.get("restored_from_persistence"):
        task["render_gateway_state"] = "render_gateway_blocked"
        task["render_gateway_next_safe_action"] = "Restore never auto-executes, polls, verifies, or rolls back."
        return _persist_and_summarize(task, event_type="render_gateway_restore_execute_blocked")
    if task.get("render_gateway_state") in {"render_gateway_verified", "render_gateway_running"}:
        task["render_gateway_next_safe_action"] = "Duplicate gateway execution blocked for completed or active runtime."
        return _persist_and_summarize(task, event_type="render_gateway_duplicate_blocked")
    request = task.get("render_gateway_request", {})
    plan = task.get("render_plan", {})
    if request.get("render_plan_digest") != plan.get("plan_digest"):
        task["render_gateway_state"] = "render_gateway_blocked"
        task["render_gateway_next_safe_action"] = "Plan digest mismatch blocks execution."
        return _persist_and_summarize(task, event_type="render_gateway_digest_blocked")
    task["render_gateway_state"] = "render_gateway_running"
    task["render_gateway_polling_state"] = "bounded_polling_ready"
    result = execute_render_gateway(request)
    runtime = result.get("runtime", result)
    task["render_gateway_result"] = get_safe_render_gateway_metadata(runtime) if result.get("runtime") else runtime
    task["render_gateway_runtime_id"] = runtime.get("gateway_runtime_id", "")
    task["render_gateway_provider_lifecycle_state"] = runtime.get("state", "")
    task["render_gateway_url_trust_state"] = runtime.get("url_metadata", {}).get("trusted")
    task["render_gateway_health_state"] = runtime.get("health_state", "")
    task["render_gateway_browser_scenario_state"] = runtime.get("browser_state", "")
    task["render_gateway_rollback_state"] = "recommendation_only_real_rollback_disabled"
    task["render_gateway_cleanup_state"] = runtime.get("cleanup_state", "")
    task["render_gateway_next_safe_action"] = "Deliver only verified fake result; real Render deployment remains blocked."
    _touch(task, "render_gateway_verified" if result.get("ok") and runtime.get("state") == "fake_render_gateway_verified" else "render_gateway_blocked")
    return _persist_and_summarize(task, event_type="render_gateway_execute")


def plan_luxcode_task_render_readiness(
    task_id: str,
    credential_reference: Optional[Dict[str, Any]] = None,
    network_authority: Optional[Dict[str, Any]] = None,
    environment: str = "preview",
    branch: str = "main",
    final_confirmation_state: str = "confirmation_missing",
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    if task.get("restored_from_persistence"):
        task["render_readiness_state"] = "render_readiness_blocked"
        task["render_readiness_next_safe_action"] = "Restore requires user action; no credential validation, seal creation, network permission, or execution is automatic."
        return _persist_and_summarize(task, event_type="render_readiness_restore_blocked")
    package = build_render_readiness_package(
        plan=task.get("render_plan", {}),
        credential_reference=credential_reference or {},
        network_authority=network_authority or {},
        task_id=task_id,
        environment=environment,
        branch=branch,
        commit_metadata=task.get("commit_metadata", {}),
        access_mode=task.get("permission_profile", {}).get("access_mode", "controlled_access"),
        deployment_intent=bool(task.get("render_intent") or task.get("render_plan", {}).get("deployment_intent")),
        final_confirmation_state=final_confirmation_state,
    )
    readiness_package = package.get("readiness_package", package)
    task["render_credential_reference_state"] = readiness_package.get("credential_reference_summary", {}).get("status")
    task["render_credential_scope_decision"] = readiness_package.get("credential_scope_decision", {})
    task["render_credential_expiration_state"] = readiness_package.get("credential_expiration_decision", {}).get("expiration_state")
    task["render_network_authority_state"] = readiness_package.get("network_authority_decision", {}).get("network_state")
    task["render_readiness_package_id"] = readiness_package.get("readiness_package_id")
    task["render_readiness_package_digest"] = readiness_package.get("package_digest")
    task["render_readiness_blockers"] = [item.get("category") for item in readiness_package.get("blocker_list", [])]
    task["render_readiness_warnings"] = [item.get("category") for item in readiness_package.get("warning_list", [])]
    task["render_final_confirmation_binding"] = final_confirmation_state
    task["render_production_execution_enabled"] = False
    task["render_readiness_next_safe_action"] = readiness_package.get("next_safe_action")
    task["render_readiness_package"] = readiness_package
    _touch(task, "render_readiness_packaged" if package.get("ok") else "render_readiness_blocked")
    return _persist_and_summarize(task, event_type="render_readiness_package")


def seal_luxcode_task_render_readiness(task_id: str, requested_level: str = "dry_run") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    if task.get("restored_from_persistence"):
        task["render_seal_status"] = "seal_reissue_required"
        task["render_readiness_next_safe_action"] = "Restore never auto-seals; user action is required."
        return _persist_and_summarize(task, event_type="render_readiness_restore_seal_blocked")
    result = issue_render_readiness_seal(task.get("render_readiness_package", {}), requested_level=requested_level)
    seal = result.get("seal", {})
    task["render_seal_id"] = seal.get("seal_id")
    task["render_seal_status"] = seal.get("seal_status")
    task["render_seal_digest"] = seal.get("seal_digest")
    task["render_readiness_metadata"] = get_safe_render_readiness_metadata(task.get("render_readiness_package", {}), seal)
    task["render_readiness_next_safe_action"] = "Use dry-run seal for fake gateway only; real execution remains disabled."
    _touch(task, "render_readiness_sealed" if seal.get("seal_status", "").startswith("seal_issued") else "render_readiness_blocked")
    return _persist_and_summarize(task, event_type="render_readiness_seal")


def plan_luxcode_task_network_access(
    task_id: str,
    bind_host: str = "127.0.0.1",
    port: int = 0,
    working_directory: str = ".",
    service: Optional[Dict[str, Any]] = None,
    selected_lan_ip: str = "",
    approval_digest: str = "",
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = create_network_access_plan(
        task_id=task_id,
        repository_root=task.get("repository_root") or str(Path.cwd()),
        working_directory=working_directory,
        bind_host=bind_host,
        port=port,
        permission_profile=task.get("permission_profile", {}),
        service=service,
        selected_lan_ip=selected_lan_ip,
        approval_digest=approval_digest,
    )
    task["network_access_plan"] = result.get("plan", result)
    return _persist_and_summarize(task, event_type="network_access_plan")


def execute_luxcode_task_network_access(task_id: str) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = execute_network_access_plan(task.get("network_access_plan", {}))
    if result.get("runtime"):
        task["network_access_result"] = get_safe_network_access_metadata(result["runtime"])
    else:
        task["network_access_result"] = result
    return _persist_and_summarize(task, event_type="network_access_execute")


def cancel_luxcode_task_network_access(task_id: str, runtime_id: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    target_runtime = runtime_id or task.get("network_access_result", {}).get("network_access_runtime_id") or task.get("network_access_plan", {}).get("network_access_runtime_id", "")
    result = cancel_network_access_runtime(target_runtime, reason=f"task {task_id} cancelled")
    task["network_access_result"] = result.get("runtime", result)
    return _persist_and_summarize(task, event_type="network_access_cancel")


def plan_luxcode_task_test_matrix(
    task_id: str,
    base_url: str,
    requested_targets: Optional[List[str]] = None,
    scenario_ids: Optional[List[str]] = None,
    device_families: Optional[List[str]] = None,
    network_profiles: Optional[List[str]] = None,
    required_targets: Optional[List[str]] = None,
    service: Optional[Dict[str, Any]] = None,
    matrix_required_for_completion: bool = False,
    approval_digest: str = "",
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    if task.get("matrix_execution_state") == "running":
        return {"ok": False, "task_id": task_id, "reason": "matrix execution already running", "safe_response": True, **SAFE_INVARIANTS}
    result = build_test_matrix_plan(
        task_id=task_id,
        repository_root=task.get("repository_root") or str(Path.cwd()),
        working_directory=".",
        base_url=base_url,
        requested_targets=requested_targets,
        scenario_ids=scenario_ids,
        device_families=device_families,
        network_profiles=network_profiles,
        required_targets=required_targets,
        service=service,
        permission_profile=task.get("permission_profile", {}),
        approval_digest=approval_digest,
    )
    task["test_matrix_plan"] = result.get("plan", result)
    task["selected_targets"] = requested_targets or []
    task["matrix_execution_state"] = "planned" if result.get("ok") else "blocked"
    task["browser_launch_state"] = "browser_selection_planned" if result.get("ok") else "browser_launch_blocked"
    task["browser_identity_state"] = "pending_identity_verification" if result.get("ok") else "not_started"
    task["matrix_required_for_completion"] = bool(matrix_required_for_completion)
    task["skipped_target_reasons"] = {item.get("target_id", ""): item.get("skip_reason", "") for item in result.get("plan", {}).get("skipped_targets", [])}
    _touch(task, "test_matrix_planned" if result.get("ok") else "test_matrix_blocked")
    return _persist_and_summarize(task, event_type="test_matrix_plan")


def execute_luxcode_task_test_matrix(task_id: str, retry_cell_ids: Optional[List[str]] = None, resume: bool = True) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    if task.get("matrix_execution_state") == "running":
        return {"ok": False, "task_id": task_id, "reason": "matrix execution already running", "safe_response": True, **SAFE_INVARIANTS}
    task["matrix_execution_state"] = "running"
    _touch(task, "test_matrix_running")
    result = execute_test_matrix(task.get("test_matrix_plan", {}), retry_cell_ids=retry_cell_ids, resume=resume)
    runtime = result.get("runtime", result)
    if result.get("runtime"):
        metadata = get_safe_test_matrix_metadata(runtime)
        task["matrix_summary"] = runtime.get("summary", metadata)
        task["matrix_failures"] = runtime.get("summary", {}).get("failures", [])
        task["matrix_execution_state"] = runtime.get("state", "test_matrix_review")
        task["test_matrix_result"] = metadata
        results = runtime.get("results", [])
        task["requested_browser_family"] = sorted({str(item.get("requested_browser_family", "")) for item in results if item.get("requested_browser_family")})
        task["selected_browser_family"] = sorted({str(item.get("selected_browser_family", "")) for item in results if item.get("selected_browser_family")})
        task["fallback_used"] = any(bool(item.get("fallback_used")) for item in results)
        task["browser_launch_failures"] = [item for item in results if "browser_launch_failure" in item.get("failure_categories", [])][:10]
        task["browser_identity_mismatches"] = [item for item in results if item.get("browser_identity_mismatch")][:10]
        if task["browser_identity_mismatches"]:
            task["browser_launch_state"] = "browser_identity_mismatch"
            task["browser_identity_state"] = "browser_identity_mismatch"
        elif task["browser_launch_failures"]:
            task["browser_launch_state"] = "browser_launch_blocked"
            task["browser_identity_state"] = "not_verified"
        else:
            task["browser_launch_state"] = "browser_launch_completed"
            task["browser_identity_state"] = "verified"
    else:
        task["matrix_summary"] = result
        task["matrix_failures"] = [result]
        task["matrix_execution_state"] = "blocked"
        task["browser_launch_state"] = "browser_launch_blocked"
        task["browser_identity_state"] = "not_verified"
    summary_state = task.get("matrix_summary", {}).get("overall_status") if isinstance(task.get("matrix_summary"), dict) else ""
    if summary_state == "passed" and not task.get("matrix_required_for_completion"):
        _touch(task, "test_matrix_completed")
    elif summary_state in {"passed", "partially_verified"}:
        _touch(task, "test_matrix_review")
    else:
        _touch(task, "test_matrix_blocked")
    task["next_safe_action"] = "Review matrix summary before claiming full verification."
    return _persist_and_summarize(task, event_type="test_matrix_execute")
