from __future__ import annotations

from typing import Any, Dict, List, Optional

from agent_constitution_engine_preview import build_constitution_preview
from explorer_agent_preview import build_explorer_agent_preview
from project_rules_loader_preview import build_project_rules_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


PLANNER_ALLOWED_CAPABILITIES: List[str] = [
    "task_planning",
    "risk_analysis",
    "validation_planning",
    "task_ordering",
    "read_only_plan_synthesis",
]

PLANNER_BLOCKED_CAPABILITIES: List[str] = [
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
    "real_repo_scan",
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


def _plan_for_issue(target_issue: str) -> List[str]:
    if target_issue == "stop_continue":
        return ["investigate_resume_owner", "review_runtime_state", "plan_continuation_validation", "validate_multiple_cycles"]
    if target_issue == "websocket_stream":
        return ["map_stream_events", "review_late_event_risk", "plan_background_tab_validation", "validate_stream_continuity"]
    if target_issue == "workspace_export":
        return ["review_export_boundaries", "plan_clean_block_filter_validation", "verify_no_file_write"]
    if target_issue == "luxway_permission":
        return ["review_permission_boundary", "plan_confirmation_checks", "verify_real_access_false"]
    return ["investigate", "analyze", "plan", "validate"]


def planner_agent_status() -> Dict[str, Any]:
    return {
        "layer": "26.4",
        "name": "Planner Agent Preview",
        "status": "planner_agent_preview_ready",
        "agent_role": "planner",
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
        "repo_scan_performed": False,
        "test_execution_enabled": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "allowed_capabilities": PLANNER_ALLOWED_CAPABILITIES,
        "blocked_capabilities": PLANNER_BLOCKED_CAPABILITIES,
        "available_endpoints": [
            "/debug/planner-agent-status",
            "/debug/planner-agent-registry",
            "/debug/planner-agent-preview",
        ],
        "connected_layers": [
            "25.5 Safe Patch Planner",
            "25.6 Verification Planner",
            "26.1 Agent Constitution Engine",
            "26.2 Project Rules Loader",
            "26.3 Explorer Agent",
        ],
        "future_direction": ["Verifier Agent", "Coordinator Agent"],
        "safety_note": "Planner Agent is strict read-only. It creates plans and validation strategy previews but does not write code, apply patches, run tests, commit, push, or deploy.",
    }


def planner_agent_registry() -> Dict[str, Any]:
    return {
        "layer": "26.4",
        "name": "Planner Agent Registry",
        "status": "planner_agent_registry_ready",
        "agent_role": "planner",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "allowed_capabilities": PLANNER_ALLOWED_CAPABILITIES,
        "blocked_capabilities": PLANNER_BLOCKED_CAPABILITIES,
        "role_contract": {
            "can_create_solution_plan": True,
            "can_order_tasks": True,
            "can_analyze_risk": True,
            "can_plan_validation": True,
            "can_write_code": False,
            "can_apply_patch": False,
            "can_run_tests": False,
            "can_commit": False,
            "can_push": False,
            "can_deploy": False,
        },
        "planning_inputs": [
            "constitution_signal",
            "project_rules_signal",
            "explorer_signal",
            "patch_plan_signal",
            "verification_signal",
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
            "real_repo_scan": False,
            "test_execution": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_planner_agent_preview(
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    target_issue = _select_target_issue(command, project_area)
    explorer = build_explorer_agent_preview(
        command=command or target_issue,
        project_area=project_area or target_issue,
        related_layer=related_layer,
    )
    constitution = build_constitution_preview(
        command=command or "planner agent strict read only planning",
        rule_source="project_rules",
        conflicting_rules=["plan_change", "read_only_mode"],
        target_area=project_area or target_issue,
    )
    project_rules = build_project_rules_preview(
        command=command or target_issue,
        project_rule_category="protected_runtime" if target_issue in {"stop_continue", "websocket_stream"} else None,
        target_area=project_area or target_issue,
    )
    patch_plan = build_patch_planner_preview(
        target_issue=target_issue,
        command=command or target_issue,
        related_layer=related_layer,
    )
    verification = build_verification_planner_preview(
        target_issue=target_issue,
        command=command or target_issue,
        related_layer=related_layer,
    )

    return {
        "agent_role": "planner",
        "allowed_capabilities": PLANNER_ALLOWED_CAPABILITIES,
        "blocked_capabilities": PLANNER_BLOCKED_CAPABILITIES,
        "recommended_plan": _plan_for_issue(target_issue),
        "recommended_task_order": patch_plan.get("recommended_validation_steps", []),
        "risk_considerations": {
            "risk_assessment": patch_plan.get("risk_assessment"),
            "approval_required": patch_plan.get("approval_required"),
            "estimated_complexity": patch_plan.get("estimated_complexity"),
            "protected_areas": project_rules.get("protected_areas", []),
            "blocked_actions": project_rules.get("blocked_actions", []),
        },
        "recommended_validation_strategy": {
            "recommended_smoke_tests": verification.get("recommended_smoke_tests", []),
            "recommended_manual_tests": verification.get("recommended_manual_tests", []),
            "recommended_regression_checks": verification.get("recommended_regression_checks", []),
            "success_criteria": verification.get("success_criteria", []),
        },
        "confidence_score": 0.9,
        "constitution_signal": {
            "selected_rule": constitution.get("selected_rule"),
            "resolution_reason": constitution.get("resolution_reason"),
            "rule_priority": constitution.get("rule_priority"),
        },
        "project_rules_signal": {
            "project_rule_category": project_rules.get("project_rule_category"),
            "required_checks": project_rules.get("required_checks", []),
            "recommended_actions": project_rules.get("recommended_actions", []),
            "blocked_actions": project_rules.get("blocked_actions", []),
        },
        "explorer_signal": {
            "recommended_entry_points": explorer.get("recommended_entry_points", []),
            "recommended_related_systems": explorer.get("recommended_related_systems", []),
            "investigation_focus": explorer.get("investigation_focus"),
        },
        "patch_plan_signal": {
            "target_issue": patch_plan.get("target_issue"),
            "recommended_change_areas": patch_plan.get("recommended_change_areas", []),
            "recommended_patch_scope": patch_plan.get("recommended_patch_scope"),
            "required_tests": patch_plan.get("required_tests", []),
        },
        "verification_signal": {
            "estimated_validation_effort": verification.get("estimated_validation_effort"),
            "risk_validation_points": verification.get("risk_validation_points", []),
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
        "repo_scan_performed": False,
        "test_execution_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Planner Agent only synthesizes a read-only plan. It does not write code, apply patches, run tests, scan the repo, commit, push, deploy, or change runtime behavior.",
    }
