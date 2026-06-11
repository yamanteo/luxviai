from __future__ import annotations

from typing import Any, Dict


LAYER = "39.5"
SERIES = "Agent Runtime Systems"
MODULE = "agent_lifecycle_runtime"
CAPABILITIES = [
    "lifecycle_state_preview",
    "idle_planning_sandboxing_mapping",
    "verification_waiting_mapping",
    "applying_recovering_delivered_mapping",
    "transition_boundary_preview",
]
INTEGRATION_POINTS = ["39.0_agent_runtime_core", "39.1_agent_session_runtime", "38.8_autonomous_execution_governance_intelligence"]
LIFECYCLE_STATES = ["idle", "planning", "sandboxing", "verifying", "waiting_for_confirmation", "applying", "recovering", "delivered"]


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


def agent_lifecycle_runtime_status() -> Dict[str, Any]:
    return {
        "layer": LAYER,
        "series": SERIES,
        "module": MODULE,
        "status": "agent_lifecycle_runtime_preview_ready",
        "operation_mode": "read_only_preview_only",
        "capabilities": CAPABILITIES,
        "lifecycle_states": LIFECYCLE_STATES,
        "integration_points": INTEGRATION_POINTS,
        "read_only": True,
        "safety": _safety(),
    }


def agent_lifecycle_runtime_capabilities() -> Dict[str, Any]:
    return {
        "layer": LAYER,
        "series": SERIES,
        "module": MODULE,
        "status": "capabilities_ready",
        "capabilities": [{"name": item, "read_only": True} for item in CAPABILITIES],
        "read_only": True,
        "safety": _safety(),
    }


def agent_lifecycle_runtime_preview(payload: Dict[str, Any]) -> Dict[str, Any]:
    detected = payload.get("runtime_state") or "planning"
    if detected not in LIFECYCLE_STATES:
        detected = "planning"
    return {
        "layer": LAYER,
        "series": SERIES,
        "module": MODULE,
        "status": "preview_ready",
        "input_summary": _input_summary(payload),
        "detected_runtime_state": detected,
        "detected_session_need": payload.get("session_state") or "lifecycle_awareness_only",
        "recommended_runtime_model": "read_only_lifecycle_state_preview",
        "available_lifecycle_states": LIFECYCLE_STATES,
        "transition_boundary": "no_lifecycle_transition_applied",
        "required_confirmations": ["before_applying_state", "before_recovering_state"],
        "continuity_notes": ["lifecycle_state_is_not_written"],
        "recovery_notes": ["recovering_state_requires_explicit_confirmation"],
        "integration_points": INTEGRATION_POINTS,
        "safety": _safety(),
        "read_only": True,
    }
