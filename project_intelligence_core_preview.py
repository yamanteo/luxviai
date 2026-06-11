from __future__ import annotations
from typing import Any, Dict, List, Optional


PROJECT_INTELLIGENCE_CORE_CAPABILITIES = [
    "active_project_detection",
    "project_state_tracking",
    "repo_identity_resolution",
    "workspace_project_mapping",
    "project_registry_management",
    "project_health_scoring",
    "project_readiness_assessment",
    "project_context_assembly",
]

NOT_ALLOWED_OPERATIONS = [
    "write_project_db", "delete_project", "modify_registry",
    "switch_project", "create_project", "archive_project",
]

RISK_LEVELS = ["safe", "warning", "high_risk", "critical"]

PROJECT_INTELLIGENCE_PROFILES: Dict[str, Dict[str, Any]] = {
    "active_single_project": {
        "aliases": ["active", "aktif", "single", "tek", "one project"],
        "project_status": "active",
        "project_health": "pass",
        "project_summary": "Single active project detected. Project state is healthy. Repository identity resolved. Workspace mapping complete.",
        "active_projects": [
            {
                "name": "luxcode",
                "repo": "github.com/user/luxcode",
                "workspace": "LUXDEEP",
                "status": "active",
                "health": "pass",
            }
        ],
        "project_count": 1,
        "health_score": 0.92,
        "risk_score": 0.08,
        "registry_status": "synced",
        "recommended_next_action": "single project active — proceed with project-specific operations",
        "read_only": True,
        "preview_only": True,
    },
    "multi_project_active": {
        "aliases": ["multi", "coklu", "multiple", "several", "birkac"],
        "project_status": "multi_active",
        "project_health": "pass",
        "project_summary": "Multiple active projects detected. All projects healthy. Registry synced. Workspace mapping resolved for all projects.",
        "active_projects": [
            {"name": "luxcode", "repo": "github.com/user/luxcode", "workspace": "LUXDEEP", "status": "active", "health": "pass"},
            {"name": "luxviai", "repo": "github.com/user/luxviai", "workspace": "luxviai", "status": "active", "health": "pass"},
        ],
        "project_count": 2,
        "health_score": 0.88,
        "risk_score": 0.12,
        "registry_status": "synced",
        "recommended_next_action": "multiple projects active — specify target project for operations",
        "read_only": True,
        "preview_only": True,
    },
}

INTEGRATION_POINTS = [
    "34.1_github_bridge_intelligence",
    "33.8_luxcode_core_status",
    "37.0_github_project_intelligence",
    "37.4_multi_project_intelligence",
    "37.8_agent_core",
]


def _select_project_core_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in PROJECT_INTELLIGENCE_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "active_single_project"


def project_intelligence_core_status() -> Dict[str, Any]:
    return {
        "layer": "37.3",
        "series": "Agent Architecture",
        "name": "Project Intelligence Core Preview",
        "status": "project_intelligence_core_ready",
        "architecture_version": "1.0",
        "capabilities": PROJECT_INTELLIGENCE_CORE_CAPABILITIES,
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "risk_model": RISK_LEVELS,
        "operation_mode": "read_only_preview_only",
        "execution_rule": "all_project_write_operations_must_go_through_luxcode_pipeline",
        "connected_layers": ["34.1", "33.8", "37.0", "37.4", "37.8"],
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
            "/project-intelligence-core/status",
            "/project-intelligence-core/capabilities",
            "/project-intelligence-core/preview",
        ],
        "safety_note": "Read-only project intelligence core preview. No project registry writes performed.",
    }


def project_intelligence_core_capabilities() -> Dict[str, Any]:
    return {
        "layer": "37.3",
        "series": "Agent Architecture",
        "name": "Project Intelligence Core Capabilities",
        "status": "project_intelligence_core_capabilities_ready",
        "capabilities": [
            {"name": "active_project_detection", "description": "Detect currently active projects from workspace state", "read_only": True},
            {"name": "project_state_tracking", "description": "Track project state changes over time", "read_only": True},
            {"name": "repo_identity_resolution", "description": "Resolve repository identity from workspace path", "read_only": True},
            {"name": "workspace_project_mapping", "description": "Map workspace directories to registered projects", "read_only": True},
            {"name": "project_registry_management", "description": "Manage project registry with read-only queries", "read_only": True},
            {"name": "project_health_scoring", "description": "Score project health from repository and workspace signals", "read_only": True},
            {"name": "project_readiness_assessment", "description": "Assess project readiness for change operations", "read_only": True},
            {"name": "project_context_assembly", "description": "Assemble full project context for agent operations", "read_only": True},
        ],
        "read_only": True,
        "preview_only": True,
        "real_action_enabled": False,
        "safety_note": "Capabilities are read-only. No project registry writes available.",
    }


def project_intelligence_core_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    repo_name: Optional[str] = None,
    task_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    context: str = "",
) -> Dict[str, Any]:
    pid = _select_project_core_profile(target_issue, command, project_area)
    p = PROJECT_INTELLIGENCE_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected

    return {
        "layer": "37.3",
        "series": "Agent Architecture",
        "module": "project_intelligence_core",
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
        "safety_note": "Read-only preview. No project registry writes performed.",
    }
