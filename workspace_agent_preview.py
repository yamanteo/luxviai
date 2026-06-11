from __future__ import annotations
from typing import Any, Dict, List, Optional


WORKSPACE_AGENT_CAPABILITIES = [
    "task_organization",
    "file_management_preview",
    "report_generation_preview",
    "note_management_preview",
    "queued_command_visibility",
    "workspace_state_assembly",
    "workspace_cleanup_preview",
    "workspace_summary_generation",
]

NOT_ALLOWED_OPERATIONS = [
    "write_file", "delete_file", "modify_file", "execute_command",
    "create_directory", "move_file", "copy_file",
]

RISK_LEVELS = ["safe", "warning", "high_risk", "critical"]

WORKSPACE_AGENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "organized_workspace": {
        "aliases": ["organized", "duzenli", "clean", "temiz", "orderly"],
        "workspace_status": "organized",
        "workspace_health": "pass",
        "workspace_summary": "Workspace is organized. Files structured. Tasks queued. Notes in place. Reports ready for generation.",
        "file_count": 120,
        "task_count": 3,
        "queued_commands": 1,
        "note_count": 5,
        "report_status": "ready",
        "organization_score": 0.91,
        "risk_score": 0.09,
        "recommended_next_action": "workspace organized — proceed with task execution",
        "read_only": True,
        "preview_only": True,
    },
    "needs_organization": {
        "aliases": ["messy", "dagınık", "cluttered", "disorganized"],
        "workspace_status": "needs_organization",
        "workspace_health": "warning",
        "workspace_summary": "Workspace needs organization. Files need sorting. Tasks need prioritization. Notes need cleanup.",
        "file_count": 250,
        "task_count": 8,
        "queued_commands": 3,
        "note_count": 15,
        "report_status": "needs_attention",
        "organization_score": 0.45,
        "risk_score": 0.55,
        "recommended_next_action": "organize workspace before proceeding with complex operations",
        "read_only": True,
        "preview_only": True,
    },
}

INTEGRATION_POINTS = [
    "34.6_workspace_intelligence",
    "34.5_task_orchestration",
    "34.4_device_action_intelligence",
    "33.8_luxcode_core_status",
    "37.8_agent_core",
]


def _select_workspace_agent_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in WORKSPACE_AGENT_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "organized_workspace"


def workspace_agent_status() -> Dict[str, Any]:
    return {
        "layer": "37.5",
        "series": "Agent Architecture",
        "name": "Workspace Agent Preview",
        "status": "workspace_agent_ready",
        "architecture_version": "1.0",
        "capabilities": WORKSPACE_AGENT_CAPABILITIES,
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "risk_model": RISK_LEVELS,
        "operation_mode": "read_only_preview_only",
        "execution_rule": "all_file_operations_must_go_through_luxcode_sandbox",
        "connected_layers": ["34.6", "34.5", "34.4", "33.8", "37.8"],
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
            "/workspace-agent/status",
            "/workspace-agent/capabilities",
            "/workspace-agent/preview",
        ],
        "safety_note": "Read-only workspace agent preview. No file operations performed.",
    }


def workspace_agent_capabilities() -> Dict[str, Any]:
    return {
        "layer": "37.5",
        "series": "Agent Architecture",
        "name": "Workspace Agent Capabilities",
        "status": "workspace_agent_capabilities_ready",
        "capabilities": [
            {"name": "task_organization", "description": "Organize tasks by priority, project, and status", "read_only": True},
            {"name": "file_management_preview", "description": "Preview file organization and recommend structure", "read_only": True},
            {"name": "report_generation_preview", "description": "Preview report generation from workspace data", "read_only": True},
            {"name": "note_management_preview", "description": "Preview note organization and cleanup suggestions", "read_only": True},
            {"name": "queued_command_visibility", "description": "Show all queued commands across projects", "read_only": True},
            {"name": "workspace_state_assembly", "description": "Assemble current workspace state", "read_only": True},
            {"name": "workspace_cleanup_preview", "description": "Preview workspace cleanup recommendations", "read_only": True},
            {"name": "workspace_summary_generation", "description": "Generate workspace summary for agent context", "read_only": True},
        ],
        "read_only": True,
        "preview_only": True,
        "real_action_enabled": False,
        "safety_note": "Capabilities are read-only. No file operations available.",
    }


def workspace_agent_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    repo_name: Optional[str] = None,
    task_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    context: str = "",
) -> Dict[str, Any]:
    pid = _select_workspace_agent_profile(target_issue, command, project_area)
    p = WORKSPACE_AGENT_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected

    return {
        "layer": "37.5",
        "series": "Agent Architecture",
        "module": "workspace_agent",
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
        "safety_note": "Read-only preview. No file operations performed.",
    }
