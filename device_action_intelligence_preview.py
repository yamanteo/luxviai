from __future__ import annotations
from typing import Any, Dict, List, Optional

from deployment_bridge_intelligence_preview import (
    deployment_bridge_intelligence_registry,
)
from terminal_bridge_intelligence_preview import (
    terminal_bridge_intelligence_registry,
)
from github_bridge_intelligence_preview import (
    github_bridge_intelligence_registry,
)
from luxcode_core_status_snapshot import (
    luxcode_core_status_snapshot,
)


DEVICE_ACTION_CAPABILITIES = [
    "action_planning",
    "action_validation",
    "permission_validation",
    "scheduled_action_planning",
    "post_task_action_planning",
    "risk_analysis",
]

SUPPORTED_ACTIONS = [
    "shutdown", "sleep", "restart",
    "notification", "scheduled_action",
    "post_task_action", "system_reminder",
]

NOT_ALLOWED_OPERATIONS = [
    "shutdown", "sleep", "restart",
    "execute_action", "modify_system", "delete_data",
]

ACTION_LEVELS = ["not_ready", "conditional", "ready", "action_ready"]
RISK_LEVELS = ["safe", "warning", "high_risk", "critical"]

DEVICE_ACTION_PROFILES: Dict[str, Dict[str, Any]] = {
    "device_online": {
        "aliases": ["online", "active", "ready", "hazir", "available"],
        "device_status": "online",
        "device_health": "pass",
        "device_summary": "Device online and healthy. All permissions granted. Actions ready for planning. No pending restrictions. Battery and network optimal.",
        "action_readiness": "action_ready",
        "action_risk_score": 0.05,
        "action_preview": {
            "available_actions": ["notification", "scheduled_action", "post_task_action", "system_reminder"],
            "blocked_actions": ["shutdown", "sleep", "restart"],
            "risk_assessment": "safe",
        },
        "action_requirements": [],
        "action_blockers": [],
        "action_warnings": [],
        "permission_status": "granted",
        "recommended_next_action": "device ready — plan non-destructive actions (notification, reminder, scheduled)",
        "read_only": True,
        "preview_only": True,
    },
    "device_low_battery": {
        "aliases": ["low battery", "batarya", "battery", "power", "enerji"],
        "device_status": "warning",
        "device_health": "warning",
        "device_summary": "Device online with low battery. Critical actions only. Non-essential actions deferred. Scheduled actions require power source confirmation.",
        "action_readiness": "conditional",
        "action_risk_score": 0.35,
        "action_preview": {
            "available_actions": ["notification", "system_reminder"],
            "blocked_actions": ["shutdown", "sleep", "restart", "scheduled_action"],
            "deferred_actions": ["post_task_action"],
            "risk_assessment": "warning",
            "risk_factors": ["low_battery_30pct", "scheduled_action_requires_power"],
        },
        "action_requirements": [
            "connect_to_power_source_for_scheduled_actions",
        ],
        "action_blockers": [],
        "action_warnings": [
            "battery_below_30pct",
            "scheduled_actions_deferred",
        ],
        "permission_status": "granted",
        "recommended_next_action": "connect to power source before planning scheduled actions",
        "read_only": True,
        "preview_only": True,
    },
    "device_permission_restricted": {
        "aliases": ["permission", "izin", "restricted", "kisitli"],
        "device_status": "warning",
        "device_health": "warning",
        "device_summary": "Device online but permissions restricted. Notification permission denied. System reminder permission requires approval. Action planning limited by permission state.",
        "action_readiness": "conditional",
        "action_risk_score": 0.45,
        "action_preview": {
            "available_actions": ["scheduled_action"],
            "blocked_actions": ["shutdown", "sleep", "restart", "notification", "system_reminder"],
            "risk_assessment": "warning",
            "risk_factors": ["notification_permission_denied", "reminder_permission_pending"],
        },
        "action_requirements": [
            "grant_notification_permission",
            "approve_system_reminder_permission",
        ],
        "action_blockers": [
            "notification_permission_denied",
        ],
        "action_warnings": [
            "system_reminder_permission_pending",
        ],
        "permission_status": "restricted",
        "recommended_next_action": "grant missing permissions before planning device actions",
        "read_only": True,
        "preview_only": True,
    },
    "device_offline": {
        "aliases": ["offline", "disconnected", "closed", "sleeping"],
        "device_status": "offline",
        "device_health": "degraded",
        "device_summary": "Device offline or in sleep mode. No actions can be planned until device is online. Wake or power on required before action planning.",
        "action_readiness": "not_ready",
        "action_risk_score": 0.90,
        "action_preview": {
            "available_actions": [],
            "blocked_actions": ["shutdown", "sleep", "restart", "notification", "scheduled_action", "post_task_action", "system_reminder"],
            "risk_assessment": "critical",
            "risk_factors": ["device_offline", "action_planning_impossible"],
        },
        "action_requirements": [
            "wake_device_or_power_on",
        ],
        "action_blockers": [
            "device_offline",
        ],
        "action_warnings": [],
        "permission_status": "unknown",
        "recommended_next_action": "wake device or power on before planning any actions",
        "read_only": True,
        "preview_only": True,
    },
    "device_action_ready": {
        "aliases": ["action ready", "active", "full", "tam"],
        "device_status": "online",
        "device_health": "pass",
        "device_summary": "Device fully ready for action execution. All permissions granted. Battery optimal. Network connected. All action types available for planning including scheduled and post-task actions.",
        "action_readiness": "action_ready",
        "action_risk_score": 0.03,
        "action_preview": {
            "available_actions": ["notification", "scheduled_action", "post_task_action", "system_reminder"],
            "blocked_actions": ["shutdown", "sleep", "restart"],
            "risk_assessment": "safe",
        },
        "action_requirements": [],
        "action_blockers": [],
        "action_warnings": [],
        "permission_status": "granted",
        "recommended_next_action": "all actions available — plan actions for post-task and scheduled execution",
        "read_only": True,
        "preview_only": True,
    },
}


def _select_device_action_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in DEVICE_ACTION_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "device_online"


def device_action_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "34.4",
        "name": "Device Action Intelligence Preview",
        "status": "device_action_intelligence_ready",
        "bridge_version": "1.0",
        "capabilities": DEVICE_ACTION_CAPABILITIES,
        "supported_actions": SUPPORTED_ACTIONS,
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "action_levels": ACTION_LEVELS,
        "risk_model": RISK_LEVELS,
        "operation_mode": "read_only_preview_only",
        "execution_rule": "all_device_actions_must_be_planned_not_executed",
        "connected_layers": ["34.3", "34.2", "34.1", "33.8"],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
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
            "/device-action/status",
            "/device-action/capabilities",
            "/device-action/preview",
        ],
        "safety_note": "Read-only device action intelligence preview. No actual device actions performed.",
    }


def device_action_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "34.4",
        "name": "Device Action Intelligence Capabilities",
        "status": "device_action_capabilities_ready",
        "capabilities": [
            {
                "name": "action_planning",
                "description": "Plan device actions based on task requirements and device state",
                "read_only": True,
            },
            {
                "name": "action_validation",
                "description": "Validate planned actions against risk model before execution",
                "read_only": True,
            },
            {
                "name": "permission_validation",
                "description": "Validate device permissions for planned actions",
                "read_only": True,
            },
            {
                "name": "scheduled_action_planning",
                "description": "Plan scheduled actions with time and condition constraints",
                "read_only": True,
            },
            {
                "name": "post_task_action_planning",
                "description": "Plan actions to execute after task completion",
                "read_only": True,
            },
            {
                "name": "risk_analysis",
                "description": "Analyze device-level risks for planned actions",
                "read_only": True,
            },
        ],
        "supported_actions": SUPPORTED_ACTIONS,
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "action_levels": ACTION_LEVELS,
        "risk_model": RISK_LEVELS,
        "operation_mode": "read_only_preview_only",
        "integration_layers": ["34.3", "34.2", "34.1", "33.8"],
        "read_only": True,
        "preview_only": True,
    }


def device_action_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in DEVICE_ACTION_PROFILES.items():
        items.append(
            {
                "profile_id": pid,
                "device_status": p["device_status"],
                "device_health": p["device_health"],
                "action_readiness": p.get("action_readiness"),
                "action_risk_score": p.get("action_risk_score"),
                "permission_status": p.get("permission_status"),
                "available_action_count": len(p.get("action_preview", {}).get("available_actions", [])),
                "blocked_action_count": len(p.get("action_preview", {}).get("blocked_actions", [])),
            }
        )
    return {
        "layer": "34.4",
        "name": "Device Action Intelligence Registry",
        "status": "device_action_intelligence_registry_ready",
        "profile_count": len(items),
        "profiles": items,
        "aggregate": {
            "min_risk_score": min(i["action_risk_score"] for i in items) if items else 0.0,
            "max_risk_score": max(i["action_risk_score"] for i in items) if items else 0.0,
            "avg_risk_score": round(
                sum(i["action_risk_score"] for i in items) / len(items), 2
            ) if items else 0.0,
        },
        "read_only": True,
        "preview_only": True,
    }


def _build_integration_signals(
    target: str, command: str, project_area: str, related_layer: str
) -> Dict[str, Any]:
    L = related_layer or "Layer 34.4"
    deployment_reg = deployment_bridge_intelligence_registry()
    terminal_reg = terminal_bridge_intelligence_registry()
    github_reg = github_bridge_intelligence_registry()
    core_status = luxcode_core_status_snapshot()

    return {
        "layer34_3_deployment_bridge": {
            "profile_count": deployment_reg.get("profile_count"),
            "avg_risk_score": deployment_reg.get("aggregate", {}).get("avg_risk_score"),
        },
        "layer34_2_terminal_bridge": {
            "profile_count": terminal_reg.get("profile_count"),
            "avg_risk_score": terminal_reg.get("aggregate", {}).get("avg_risk_score"),
        },
        "layer34_1_github_bridge": {
            "profile_count": github_reg.get("profile_count"),
            "avg_risk_score": github_reg.get("aggregate", {}).get("avg_risk_score"),
        },
        "luxcode_core_status": {
            "core_version": core_status.get("core_version"),
            "core_health_score": core_status.get("core_health_score"),
        },
    }


def build_device_action_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_device_action_profile(target_issue, command, project_area)
    p = DEVICE_ACTION_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 34.4"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "device_status": p["device_status"],
        "device_health": p["device_health"],
        "device_summary": p.get("device_summary"),
        "action_readiness": p.get("action_readiness"),
        "action_risk_score": p.get("action_risk_score"),
        "action_preview": p.get("action_preview", {}),
        "action_requirements": p.get("action_requirements", []),
        "action_blockers": p.get("action_blockers", []),
        "action_warnings": p.get("action_warnings", []),
        "permission_status": p.get("permission_status"),
        "recommended_next_action": p.get("recommended_next_action"),
        "runtime_signals": integration,
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
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
        "safety_note": "Read-only device action intelligence preview. No actual device actions performed.",
    }
