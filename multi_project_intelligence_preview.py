from __future__ import annotations
from typing import Any, Dict, List, Optional


MULTI_PROJECT_INTELLIGENCE_CAPABILITIES = [
    "multi_project_detection",
    "project_priority_analysis",
    "inter_project_conflict_detection",
    "active_inactive_project_tracking",
    "project_handoff_planning",
    "cross_project_dependency_mapping",
    "project_resource_allocation",
    "project_switch_readiness",
]

NOT_ALLOWED_OPERATIONS = [
    "switch_project", "archive_project", "delete_project",
    "reorder_projects", "modify_project_config",
]

RISK_LEVELS = ["safe", "warning", "high_risk", "critical"]

MULTI_PROJECT_PROFILES: Dict[str, Dict[str, Any]] = {
    "single_active": {
        "aliases": ["single", "tek", "one", "active only", "yalniz"],
        "project_status": "single_active",
        "project_health": "pass",
        "project_summary": "Single active project. No multi-project coordination needed.",
        "active_projects": ["luxcode"],
        "inactive_projects": [],
        "project_priority": {"luxcode": 1},
        "conflicts": [],
        "pending_handoffs": [],
        "health_score": 0.95,
        "risk_score": 0.05,
        "recommended_next_action": "single project — no multi-project coordination required",
        "read_only": True,
        "preview_only": True,
    },
    "multi_active": {
        "aliases": ["multi", "coklu", "multiple", "several", "birkac"],
        "project_status": "multi_active",
        "project_health": "pass",
        "project_summary": "Multiple active projects. No conflicts detected. Priority established. Ready for coordinated operations.",
        "active_projects": ["luxcode", "luxviai"],
        "inactive_projects": [],
        "project_priority": {"luxcode": 1, "luxviai": 2},
        "conflicts": [],
        "pending_handoffs": [],
        "health_score": 0.88,
        "risk_score": 0.12,
        "recommended_next_action": "multiple projects active — specify target project or continue multi-project mode",
        "read_only": True,
        "preview_only": True,
    },
}

INTEGRATION_POINTS = [
    "37.3_project_intelligence_core",
    "37.0_github_project_intelligence",
    "33.8_luxcode_core_status",
    "37.8_agent_core",
]


def _select_multi_project_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in MULTI_PROJECT_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "single_active"


def multi_project_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "37.4",
        "series": "Agent Architecture",
        "name": "Multi Project Intelligence Preview",
        "status": "multi_project_intelligence_ready",
        "architecture_version": "1.0",
        "capabilities": MULTI_PROJECT_INTELLIGENCE_CAPABILITIES,
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "risk_model": RISK_LEVELS,
        "operation_mode": "read_only_preview_only",
        "execution_rule": "all_project_switch_must_go_through_luxcode_pipeline",
        "connected_layers": ["37.3", "37.0", "33.8", "37.8"],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "real_action_enabled": False,
        "real_code_modified": False,
        "file_created": False,
        "file_deleted": False,
        "command_executed": False,
        "terminal_command_executed": False,
        "github_write_performed": False,
        "github_commit_created": False,
        "github_push_performed": False,
        "deployment_triggered": False,
        "render_action_performed": False,
        "network_action_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "secret_accessed": False,
        "available_endpoints": [
            "/multi-project-intelligence/status",
            "/multi-project-intelligence/capabilities",
            "/multi-project-intelligence/preview",
        ],
        "safety_note": "Read-only multi-project intelligence preview. No project switching performed.",
    }


def multi_project_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "37.4",
        "series": "Agent Architecture",
        "name": "Multi Project Intelligence Capabilities",
        "status": "multi_project_intelligence_capabilities_ready",
        "capabilities": [
            {"name": "multi_project_detection", "description": "Detect all active and inactive projects in workspace", "read_only": True},
            {"name": "project_priority_analysis", "description": "Analyze and rank project priority from activity signals", "read_only": True},
            {"name": "inter_project_conflict_detection", "description": "Detect conflicts between active projects", "read_only": True},
            {"name": "active_inactive_project_tracking", "description": "Track active vs inactive project state changes", "read_only": True},
            {"name": "project_handoff_planning", "description": "Plan handoff between projects", "read_only": True},
            {"name": "cross_project_dependency_mapping", "description": "Map dependencies between projects", "read_only": True},
            {"name": "project_resource_allocation", "description": "Analyze resource allocation across projects", "read_only": True},
            {"name": "project_switch_readiness", "description": "Assess readiness for safe project switching", "read_only": True},
        ],
        "read_only": True,
        "preview_only": True,
        "real_action_enabled": False,
        "safety_note": "Capabilities are read-only. No project switching available.",
    }


def multi_project_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    repo_name: Optional[str] = None,
    task_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    context: str = "",
) -> Dict[str, Any]:
    pid = _select_multi_project_profile(target_issue, command, project_area)
    p = MULTI_PROJECT_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected

    return {
        "layer": "37.4",
        "series": "Agent Architecture",
        "module": "multi_project_intelligence",
        "status": "preview_ready",
        "input_summary": {
            "target_issue": target_issue,
            "command": command[:100] if command else "",
            "project_area": project_area,
            "repo_name": repo_name,
            "task_type": task_type,
            "risk_level": risk_level,
        },
        "detected_intent": pid,
        "profile": p,
        "recommended_next_step": p.get("recommended_next_action"),
        "integration_points": INTEGRATION_POINTS,
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "real_action_enabled": False,
        "real_code_modified": False,
        "file_created": False,
        "file_deleted": False,
        "command_executed": False,
        "terminal_command_executed": False,
        "github_write_performed": False,
        "github_commit_created": False,
        "github_push_performed": False,
        "deployment_triggered": False,
        "render_action_performed": False,
        "network_action_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "secret_accessed": False,
        "safety_note": "Read-only preview. No project switching performed.",
    }
