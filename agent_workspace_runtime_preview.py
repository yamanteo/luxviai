from __future__ import annotations

from typing import Any, Dict


LAYER = "39.2"
SERIES = "Agent Runtime Systems"
MODULE = "agent_workspace_runtime"
CAPABILITIES = [
    "workspace_state_preview",
    "clone_sandbox_relation_preview",
    "visible_task_surface_mapping",
    "hidden_technical_state_mapping",
    "workspace_readiness_preview",
]
INTEGRATION_POINTS = ["39.0_agent_runtime_core", "37.5_workspace_agent", "34.6_workspace_intelligence"]


def _safety() -> Dict[str, bool]:
    return {
        "real_action_enabled": False,
        "runtime_execution_enabled": False,
        "session_started": False,
        "session_modified": False,
        "workspace_runtime_modified": False,
        "memory_loop_executed": False,
        "collaboration_started": False,
        "lifecycle_transition_applied": False,
        "recovery_action_performed": False,
        "continuity_state_written": False,
        "consolidation_applied": False,
        "action_performed": False,
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
        "memory_read_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "secret_accessed": False,
        "read_only": True,
    }


def _input_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "command": str(payload.get("command") or "")[:200],
        "project_area": payload.get("project_area"),
        "runtime_state": payload.get("runtime_state"),
        "session_state": payload.get("session_state"),
        "workspace_state": payload.get("workspace_state"),
        "task_type": payload.get("task_type"),
        "risk_level": payload.get("risk_level"),
        "context_length": len(str(payload.get("context") or "")),
    }


def agent_workspace_runtime_status() -> Dict[str, Any]:
    return {
        "layer": LAYER,
        "series": SERIES,
        "module": MODULE,
        "status": "agent_workspace_runtime_preview_ready",
        "operation_mode": "read_only_preview_only",
        "capabilities": CAPABILITIES,
        "integration_points": INTEGRATION_POINTS,
        "read_only": True,
        "safety": _safety(),
    }


def agent_workspace_runtime_capabilities() -> Dict[str, Any]:
    return {
        "layer": LAYER,
        "series": SERIES,
        "module": MODULE,
        "status": "capabilities_ready",
        "capabilities": [{"name": item, "read_only": True} for item in CAPABILITIES],
        "read_only": True,
        "safety": _safety(),
    }


def agent_workspace_runtime_preview(payload: Dict[str, Any]) -> Dict[str, Any]:
    workspace_state = payload.get("workspace_state") or "workspace_preview_only"
    return {
        "layer": LAYER,
        "series": SERIES,
        "module": MODULE,
        "status": "preview_ready",
        "input_summary": _input_summary(payload),
        "detected_runtime_state": payload.get("runtime_state") or workspace_state,
        "detected_session_need": payload.get("session_state") or "workspace_context_review",
        "recommended_runtime_model": "read_only_workspace_runtime_preview",
        "active_workspace": payload.get("project_area") or "current_workspace_preview",
        "clone_sandbox_relation": "described_only_no_workspace_mutation",
        "visible_task_surface": ["active_task", "queued_command", "verification_state"],
        "hidden_technical_state": ["route_contracts", "safety_flags", "coverage_entries"],
        "workspace_readiness": "requires_confirmation_before_mutation",
        "required_confirmations": ["before_workspace_runtime_mutation", "before_file_or_clone_action"],
        "continuity_notes": ["workspace_state_is_not_persisted"],
        "recovery_notes": ["use_safe_pause_if_workspace_state_is_unclear"],
        "integration_points": INTEGRATION_POINTS,
        "safety": _safety(),
        "read_only": True,
    }
