from __future__ import annotations

from typing import Any, Dict, List, Optional

from agent_constitution_engine_preview import build_constitution_preview
from planner_agent_preview import build_planner_agent_preview
from project_rules_loader_preview import build_project_rules_preview
from safe_change_boundary_preview import build_change_boundary_preview
from safe_verification_planner_preview import build_verification_planner_preview


VERIFIER_ALLOWED_CAPABILITIES: List[str] = [
    "verification_planning",
    "regression_review",
    "success_validation",
    "test_coverage_review",
    "read_only_validation_synthesis",
]

VERIFIER_BLOCKED_CAPABILITIES: List[str] = [
    "code_generation",
    "patch_execution",
    "patch_application",
    "test_execution",
    "file_write",
    "memory_write",
    "db_write",
    "git_write",
    "commit",
    "push",
    "deploy",
    "subprocess_execution",
    "real_test_run",
]


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_target_issue(command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{project_area or ''} {command or ''}")
    if any(term in haystack for term in ["stop", "continue", "dur", "devam", "arm"]):
        return "stop_continue"
    if any(term in haystack for term in ["websocket", "stream", "typewriter", "tab"]):
        return "websocket_stream"
    if any(term in haystack for term in ["workspace", "export", "file", "dosya"]):
        return "workspace_export"
    if any(term in haystack for term in ["luxway", "permission", "izin", "phone", "telefon"]):
        return "luxway_permission"
    return "debug_intelligence"


def verifier_agent_status() -> Dict[str, Any]:
    return {
        "layer": "26.5",
        "name": "Verifier Agent Preview",
        "status": "verifier_agent_preview_ready",
        "agent_role": "verifier",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "real_action_performed": False,
        "file_write_enabled": False,
        "memory_write_enabled": False,
        "db_write_enabled": False,
        "git_write_enabled": False,
        "commit_enabled": False,
        "push_enabled": False,
        "deploy_enabled": False,
        "auto_fix_enabled": False,
        "patch_apply_enabled": False,
        "subprocess_execution_enabled": False,
        "test_execution_enabled": False,
        "real_test_run_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "allowed_capabilities": VERIFIER_ALLOWED_CAPABILITIES,
        "blocked_capabilities": VERIFIER_BLOCKED_CAPABILITIES,
        "available_endpoints": [
            "/debug/verifier-agent-status",
            "/debug/verifier-agent-registry",
            "/debug/verifier-agent-preview",
        ],
        "connected_layers": [
            "25.4 Safe Change Boundary",
            "25.6 Verification Planner",
            "26.1 Agent Constitution Engine",
            "26.2 Project Rules Loader",
            "26.4 Planner Agent",
        ],
        "future_direction": ["Coordinator Agent", "Regression Guard", "Validation Engine"],
        "safety_note": "Verifier Agent is strict read-only. It reviews verification strategy, coverage, regression risk, and success criteria but does not execute tests, apply patches, commit, push, or deploy.",
    }


def verifier_agent_registry() -> Dict[str, Any]:
    return {
        "layer": "26.5",
        "name": "Verifier Agent Registry",
        "status": "verifier_agent_registry_ready",
        "agent_role": "verifier",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "allowed_capabilities": VERIFIER_ALLOWED_CAPABILITIES,
        "blocked_capabilities": VERIFIER_BLOCKED_CAPABILITIES,
        "role_contract": {
            "can_plan_verification": True,
            "can_review_regressions": True,
            "can_review_success_criteria": True,
            "can_review_test_coverage": True,
            "can_write_code": False,
            "can_apply_patch": False,
            "can_run_tests": False,
            "can_commit": False,
            "can_push": False,
            "can_deploy": False,
        },
        "verification_inputs": [
            "constitution_signal",
            "project_rules_signal",
            "planner_signal",
            "verification_plan_signal",
            "boundary_signal",
        ],
        "safety_flags": {
            "file_write": False,
            "memory_write": False,
            "db_write": False,
            "git_write": False,
            "commit": False,
            "push": False,
            "deploy": False,
            "auto_fix": False,
            "patch_apply": False,
            "subprocess_execution": False,
            "test_execution": False,
            "real_test_run": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_verifier_agent_preview(
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    target_issue = _select_target_issue(command, project_area)
    constitution = build_constitution_preview(
        command=command or "verifier agent strict read only validation",
        rule_source="project_rules",
        conflicting_rules=["run_tests", "read_only_mode"],
        target_area=project_area or target_issue,
    )
    project_rules = build_project_rules_preview(
        command=command or target_issue,
        project_rule_category="required_tests",
        target_area=project_area or target_issue,
    )
    planner = build_planner_agent_preview(
        command=command or target_issue,
        project_area=project_area or target_issue,
        related_layer=related_layer,
    )
    verification = build_verification_planner_preview(
        target_issue=target_issue,
        command=command or target_issue,
        related_layer=related_layer,
    )
    boundary = build_change_boundary_preview(
        target_area=project_area or target_issue,
        command=command or target_issue,
        related_layer=related_layer,
    )

    return {
        "agent_role": "verifier",
        "allowed_capabilities": VERIFIER_ALLOWED_CAPABILITIES,
        "blocked_capabilities": VERIFIER_BLOCKED_CAPABILITIES,
        "recommended_verification_steps": verification.get("recommended_smoke_tests", []) + verification.get("recommended_manual_tests", []),
        "recommended_regression_checks": verification.get("recommended_regression_checks", []),
        "recommended_success_criteria": verification.get("success_criteria", []),
        "risk_validation_focus": verification.get("risk_validation_points", []),
        "confidence_score": 0.91,
        "constitution_signal": {
            "selected_rule": constitution.get("selected_rule"),
            "resolution_reason": constitution.get("resolution_reason"),
            "rule_priority": constitution.get("rule_priority"),
        },
        "project_rules_signal": {
            "project_rule_category": project_rules.get("project_rule_category"),
            "required_checks": project_rules.get("required_checks", []),
            "blocked_actions": project_rules.get("blocked_actions", []),
        },
        "planner_signal": {
            "recommended_plan": planner.get("recommended_plan", []),
            "recommended_task_order": planner.get("recommended_task_order", []),
            "risk_considerations": planner.get("risk_considerations", {}),
        },
        "verification_plan_signal": {
            "target_issue": verification.get("target_issue"),
            "estimated_validation_effort": verification.get("estimated_validation_effort"),
            "recommended_smoke_tests": verification.get("recommended_smoke_tests", []),
        },
        "boundary_signal": {
            "boundary_level": boundary.get("boundary_level"),
            "criticality_level": boundary.get("criticality_level"),
            "user_approval_required": boundary.get("user_approval_required"),
            "blocked_actions": boundary.get("blocked_actions", []),
        },
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "real_action_performed": False,
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_write_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "auto_fix_performed": False,
        "patch_apply_performed": False,
        "subprocess_execution_performed": False,
        "test_execution_performed": False,
        "real_test_run_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Verifier Agent only reviews validation strategy in preview mode. It does not execute tests, write files, apply patches, commit, push, deploy, or alter runtime behavior.",
    }
