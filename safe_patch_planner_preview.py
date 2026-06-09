from __future__ import annotations

from typing import Any, Dict, List, Optional

from dependency_mapper_preview import build_dependency_mapper_preview
from impact_analyzer_preview import build_impact_analyzer_preview
from safe_change_boundary_preview import build_change_boundary_preview, change_boundary_registry


PATCH_PLANNER_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "recommended_change_areas": ["resume_flow", "runtime_state", "manual_continue_scenario"],
        "recommended_patch_scope": "small",
        "risk_assessment": "medium",
        "required_tests": ["smoke_check", "manual_continue_scenario", "multiple_stop_continue_cycle"],
        "recommended_validation_steps": ["root_flow_audit", "impact_review", "boundary_review", "manual_regression_check"],
        "estimated_complexity": "medium",
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "recommended_change_areas": ["stream_flow", "event_guard", "typewriter_queue"],
        "recommended_patch_scope": "medium",
        "risk_assessment": "high",
        "required_tests": ["smoke_check", "manual_background_tab_test", "websocket_stream_schema"],
        "recommended_validation_steps": ["root_flow_audit", "dependency_review", "impact_review", "boundary_review"],
        "estimated_complexity": "high",
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "recommended_change_areas": ["export_clean_flow", "block_filtering", "file_write_guard"],
        "recommended_patch_scope": "small",
        "risk_assessment": "medium",
        "required_tests": ["smoke_check", "workspace_export_preview", "file_written_false_guard"],
        "recommended_validation_steps": ["dependency_review", "impact_review", "boundary_review", "export_preview_validation"],
        "estimated_complexity": "medium",
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "recommended_change_areas": ["permission_flow", "confirmation_boundary", "private_data_guard"],
        "recommended_patch_scope": "medium",
        "risk_assessment": "high",
        "required_tests": ["smoke_check", "permission_preview", "device_safety_preview", "real_access_false_guard"],
        "recommended_validation_steps": ["dependency_review", "impact_review", "boundary_review", "privacy_boundary_validation"],
        "estimated_complexity": "high",
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "investigation", "planner", "priority", "explorer", "dependency", "impact", "boundary", "patch"],
        "recommended_change_areas": ["preview_schema", "debug_panel", "smoke_coverage"],
        "recommended_patch_scope": "small",
        "risk_assessment": "low",
        "required_tests": ["smoke_check", "py_compile"],
        "recommended_validation_steps": ["endpoint_coverage_review", "fault_report_preview_validation"],
        "estimated_complexity": "low",
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_issue: Optional[str], command: str) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''}")
    for profile_id, profile in PATCH_PLANNER_PROFILES.items():
        if any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def patch_planner_status() -> Dict[str, Any]:
    return {
        "layer": "25.5",
        "name": "Safe Patch Planner Preview",
        "status": "patch_planner_preview_ready",
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
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "available_endpoints": [
            "/debug/patch-planner-status",
            "/debug/patch-planner-registry",
            "/debug/patch-planner-preview",
        ],
        "connected_layers": [
            "25.1 Dev Agent Explorer",
            "25.2 Dependency Mapper",
            "25.3 Impact Analyzer",
            "25.4 Safe Change Boundary",
        ],
        "future_direction": ["Patch Preview Engine", "Verification Engine", "Lux Dev Agent"],
        "safety_note": "Safe Patch Planner only creates a read-only patch plan; it never applies patches, writes files, commits, pushes, deploys, or executes subprocesses.",
    }


def patch_planner_registry() -> Dict[str, Any]:
    plans: List[Dict[str, Any]] = []
    for profile_id, profile in PATCH_PLANNER_PROFILES.items():
        boundary = build_change_boundary_preview(target_area=profile_id, command=profile_id)
        plans.append(
            {
                "id": profile_id,
                "recommended_change_areas": profile["recommended_change_areas"],
                "recommended_patch_scope": profile["recommended_patch_scope"],
                "risk_assessment": profile["risk_assessment"],
                "required_tests": profile["required_tests"],
                "recommended_validation_steps": profile["recommended_validation_steps"],
                "approval_required": boundary.get("user_approval_required"),
                "estimated_complexity": profile["estimated_complexity"],
            }
        )

    return {
        "layer": "25.5",
        "name": "Safe Patch Planner Registry",
        "status": "patch_planner_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "plan_count": len(plans),
        "patch_plans": plans,
        "connected_endpoints": [
            "/debug/change-boundary-preview",
            "/debug/impact-analyzer-preview",
            "/debug/dependency-mapper-preview",
            "/debug/dev-agent-explorer-preview",
            "/debug/fault-report-preview",
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
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_patch_planner_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(target_issue, command)
    profile = PATCH_PLANNER_PROFILES[profile_id]
    detected_issue = target_issue or profile_id
    boundary = build_change_boundary_preview(
        target_area=detected_issue,
        command=command or detected_issue,
        related_layer=related_layer,
    )
    impact = build_impact_analyzer_preview(
        target_component=detected_issue,
        command=command or detected_issue,
        related_layer=related_layer,
    )
    dependency = build_dependency_mapper_preview(
        component_name=detected_issue,
        command=command or detected_issue,
        related_layer=related_layer,
    )
    boundary_registry = change_boundary_registry()
    approval_required = bool(boundary.get("user_approval_required"))

    return {
        "target_issue": detected_issue,
        "recommended_change_areas": _unique(
            list(profile["recommended_change_areas"]) + list(impact.get("potentially_affected_behaviors", []))[:2]
        ),
        "recommended_patch_scope": profile["recommended_patch_scope"],
        "risk_assessment": profile["risk_assessment"],
        "required_tests": _unique(list(profile["required_tests"]) + ["py_compile"]),
        "recommended_validation_steps": _unique(
            list(profile["recommended_validation_steps"]) + ["change_boundary_review"]
        ),
        "approval_required": approval_required,
        "estimated_complexity": profile["estimated_complexity"],
        "confidence_score": 0.89,
        "boundary_signal": {
            "boundary_level": boundary.get("boundary_level"),
            "criticality_level": boundary.get("criticality_level"),
            "allowed_actions": boundary.get("allowed_actions", []),
            "blocked_actions": boundary.get("blocked_actions", []),
            "risk_reason": boundary.get("risk_reason"),
        },
        "impact_signal": {
            "impact_risk": impact.get("impact_risk"),
            "recommended_caution_level": impact.get("recommended_caution_level"),
            "potentially_affected_components": impact.get("potentially_affected_components", []),
            "potentially_affected_layers": impact.get("potentially_affected_layers", []),
            "potentially_affected_endpoints": impact.get("potentially_affected_endpoints", []),
        },
        "dependency_signal": {
            "related_components": dependency.get("related_components", []),
            "related_layers": dependency.get("related_layers", []),
            "related_endpoints": dependency.get("related_endpoints", []),
            "related_behaviors": dependency.get("related_behaviors", []),
        },
        "registry_signal": {
            "boundary_count": boundary_registry.get("boundary_count"),
            "connected_endpoints": boundary_registry.get("connected_endpoints", []),
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
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "This is a strict read-only patch plan preview. It does not apply patches, write files, run commands, commit, push, deploy, or change runtime behavior.",
    }
