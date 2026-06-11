from __future__ import annotations
from typing import Any, Dict, List, Optional

from device_action_intelligence_preview import device_action_intelligence_registry
from deployment_bridge_intelligence_preview import deployment_bridge_intelligence_registry
from terminal_bridge_intelligence_preview import terminal_bridge_intelligence_registry
from github_bridge_intelligence_preview import github_bridge_intelligence_registry
# luxcode_core_status_snapshot not used in this file

TASK_STATES = ["queued", "waiting", "running", "blocked", "stuck", "verification", "completed"]

QUEUE_MODE = "simulation_only"

TASK_ORCHESTRATION_CAPABILITIES = [
    "active_task_tracking",
    "queue_management",
    "follow_up_capture",
    "guided_conversation",
    "completion_action_planning",
    "task_monitoring",
    "stuck_detection",
    "progress_analysis",
    "pending_context_tracking",
    "workspace_suggestion_generation",
]

TASK_PROFILES: Dict[str, Dict[str, Any]] = {
    "idle": {
        "aliases": ["idle", "bos", "waiting", "beklemede"],
        "health_score": 0.95,
        "queue_load": 0,
        "completion_forecast": "no_active_tasks",
        "risk_score": 0.02,
        "current_task": None,
        "current_phase": None,
        "completion_percent": 100,
        "estimated_remaining_steps": 0,
        "estimated_remaining_time": "0m",
        "task_health": "pass",
        "task_status": "completed",
        "pending_commands": [],
        "queue": [],
        "stuck_detected": False,
    },
    "single_task": {
        "aliases": ["single", "tek", "one", "bir"],
        "health_score": 0.82,
        "queue_load": 1,
        "completion_forecast": "55s",
        "risk_score": 0.10,
        "current_task": "Layer 34.5 Task Orchestration build",
        "current_phase": "implementation",
        "completion_percent": 65,
        "estimated_remaining_steps": 3,
        "estimated_remaining_time": "55s",
        "task_health": "pass",
        "task_status": "running",
        "pending_commands": [],
        "queue": [],
        "stuck_detected": False,
    },
    "multi_task": {
        "aliases": ["multi", "coklu", "multiple", "several"],
        "health_score": 0.68,
        "queue_load": 3,
        "completion_forecast": "3m 20s",
        "risk_score": 0.25,
        "current_task": "Execution Bridge integration",
        "current_phase": "verification",
        "completion_percent": 72,
        "estimated_remaining_steps": 5,
        "estimated_remaining_time": "3m 20s",
        "task_health": "warning",
        "task_status": "running",
        "pending_commands": [
            {"command": "verify_bridge_contracts", "queue_position": 2},
            {"command": "run_smoke_tests", "queue_position": 3},
        ],
        "queue": [
            {"id": 1, "command": "verify_bridge_contracts", "status": "waiting"},
            {"id": 2, "command": "run_smoke_tests", "status": "queued"},
            {"id": 3, "command": "generate_integration_report", "status": "queued"},
        ],
        "stuck_detected": False,
    },
    "heavy_queue": {
        "aliases": ["heavy", "agir", "many", "cok", "queue"],
        "health_score": 0.45,
        "queue_load": 8,
        "completion_forecast": "12m",
        "risk_score": 0.55,
        "current_task": "Full LuxCode verification suite",
        "current_phase": "regression_testing",
        "completion_percent": 38,
        "estimated_remaining_steps": 12,
        "estimated_remaining_time": "12m",
        "task_health": "degraded",
        "task_status": "running",
        "pending_commands": [
            {"command": "test_layer31", "queue_position": 3},
            {"command": "test_layer32", "queue_position": 4},
            {"command": "test_layer33", "queue_position": 5},
            {"command": "test_layer34", "queue_position": 6},
            {"command": "generate_full_report", "queue_position": 7},
        ],
        "queue": [
            {"id": 1, "command": "run_anomaly_tests", "status": "running"},
            {"id": 2, "command": "run_regression_tests", "status": "waiting"},
            {"id": 3, "command": "test_layer31", "status": "queued"},
            {"id": 4, "command": "test_layer32", "status": "queued"},
            {"id": 5, "command": "test_layer33", "status": "queued"},
            {"id": 6, "command": "test_layer34", "status": "queued"},
            {"id": 7, "command": "run_smoke_suite", "status": "queued"},
            {"id": 8, "command": "generate_full_report", "status": "queued"},
        ],
        "stuck_detected": False,
    },
    "verification_mode": {
        "aliases": ["verification", "dogrulama", "check", "kontrol"],
        "health_score": 0.60,
        "queue_load": 2,
        "completion_forecast": "2m 10s",
        "risk_score": 0.35,
        "current_task": "Verification gate checks",
        "current_phase": "verification",
        "completion_percent": 82,
        "estimated_remaining_steps": 4,
        "estimated_remaining_time": "2m 10s",
        "task_health": "warning",
        "task_status": "verification",
        "pending_commands": [
            {"command": "verify_sandbox_gate", "queue_position": 1},
            {"command": "verify_integration_gate", "queue_position": 2},
        ],
        "queue": [
            {"id": 1, "command": "verify_sandbox_gate", "status": "running"},
            {"id": 2, "command": "verify_integration_gate", "status": "waiting"},
        ],
        "stuck_detected": False,
    },
    "stuck_recovery": {
        "aliases": ["stuck", "takildi", "blocked", "engellendi"],
        "health_score": 0.25,
        "queue_load": 4,
        "completion_forecast": "indefinite",
        "risk_score": 0.85,
        "current_task": "Integration contract verification",
        "current_phase": "blocked",
        "completion_percent": 45,
        "estimated_remaining_steps": 6,
        "estimated_remaining_time": "unknown",
        "task_health": "critical",
        "task_status": "stuck",
        "pending_commands": [],
        "queue": [
            {"id": 1, "command": "verify_contract", "status": "stuck"},
            {"id": 2, "command": "test_fallback", "status": "blocked"},
            {"id": 3, "command": "validate_integration", "status": "blocked"},
            {"id": 4, "command": "generate_report", "status": "blocked"},
        ],
        "stuck_detected": True,
        "stuck_reason": "integration_contract_drift_loop_detected",
        "stuck_risk_level": "high",
        "stuck_alternative": "rebuild_working_clone_and_reapply_integration_changes",
    },
}

COMPLETION_ACTIONS = [
    {"action": "report_generation", "description": "Generate completion report", "preview_only": True},
    {"action": "workspace_summary", "description": "Create workspace summary", "preview_only": True},
    {"action": "notification_preview", "description": "Preview notification", "preview_only": True},
    {"action": "deployment_check", "description": "Check deployment readiness", "preview_only": True},
    {"action": "device_action_preview", "description": "Preview device action", "preview_only": True},
]

FOLLOW_UP_EXAMPLES = [
    {"captured_command": "Navbarı küçült", "queue_position": 2, "estimated_execution_order": "after_current_task"},
    {"captured_command": "Bu ekranı sadeleştir", "queue_position": 3, "estimated_execution_order": "after_current_task"},
    {"captured_command": "Bitince GitHub kontrol et", "queue_position": 4, "estimated_execution_order": "after_current_task"},
]

GUIDED_CONVERSATIONS = [
    {"question": "Devam ediyor mu?", "answer_preview": "Evet, task çalışıyor. Şu an verification aşamasında. %82 tamamlandı."},
    {"question": "Neden bunu seçtin?", "answer_preview": "Integration contract drift loop tespit edildi. Sandbox repair ve yeniden doğrulama gerekli."},
    {"question": "Kaç dakika kaldı?", "answer_preview": "Tahmini kalan süre: 2 dakika 10 saniye."},
]

WORKSPACE_SUGGESTIONS = [
    {"type": "performance", "suggestion": "Reduce queue depth by batching dependent tasks"},
    {"type": "security", "suggestion": "Run security scan after current verification completes"},
    {"type": "ux", "suggestion": "Show progress indicator for long-running tasks"},
    {"type": "maintenance", "suggestion": "Archive completed tasks older than 7 days"},
    {"type": "organization", "suggestion": "Group related tasks into task sequences"},
]


def _select_task_profile(task_type: Optional[str] = None, command: str = "", project_area: Optional[str] = None) -> str:
    targets = [task_type or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in TASK_PROFILES.items():
        if any(a in t_lower for a in profile.get("aliases", [])) or key in t_lower:
            return key
    return "idle"


def task_orchestration_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "34.5",
        "name": "Task Orchestration Intelligence Preview",
        "status": "task_orchestration_ready",
        "bridge_version": "1.0",
        "capabilities": TASK_ORCHESTRATION_CAPABILITIES,
        "task_states": TASK_STATES,
        "queue_mode": QUEUE_MODE,
        "operation_mode": "read_only_preview_only",
        "execution_rule": "tasks_simulated_and_analyzed_only_never_executed",
        "profile_count": len(TASK_PROFILES),
        "connected_layers": ["34.4", "34.3", "34.2", "34.1", "33.8"],
        "available_endpoints": [
            "/task-orchestration/status",
            "/task-orchestration/capabilities",
            "/task-orchestration/queue",
            "/task-orchestration/watch",
            "/task-orchestration/preview",
            "/task-orchestration/add-command",
            "/task-orchestration/follow-up",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "task_execution": False,
        "command_execution": False,
        "device_execution": False,
        "file_modification": False,
        "deployment_execution": False,
        "system_modification": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only task orchestration preview. No actual tasks executed.",
    }


def task_orchestration_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "34.5",
        "name": "Task Orchestration Intelligence Capabilities",
        "status": "task_orchestration_capabilities_ready",
        "capabilities": [
            {"name": "active_task_tracking", "description": "Track current active task state and progress", "read_only": True},
            {"name": "queue_management", "description": "Manage task queue with priority and dependency ordering", "read_only": True},
            {"name": "follow_up_capture", "description": "Capture follow-up commands during active tasks", "read_only": True},
            {"name": "guided_conversation", "description": "Enable natural conversation during active tasks", "read_only": True},
            {"name": "completion_action_planning", "description": "Plan actions to execute after task completion", "read_only": True},
            {"name": "task_monitoring", "description": "Monitor task health and progress in real-time", "read_only": True},
            {"name": "stuck_detection", "description": "Detect stuck tasks and suggest alternative strategies", "read_only": True},
            {"name": "progress_analysis", "description": "Analyze task progress and estimate completion", "read_only": True},
            {"name": "pending_context_tracking", "description": "Track pending commands and delayed requests", "read_only": True},
            {"name": "workspace_suggestion_generation", "description": "Generate workspace improvement suggestions", "read_only": True},
        ],
        "task_states": TASK_STATES,
        "queue_mode": QUEUE_MODE,
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def task_orchestration_intelligence_queue() -> Dict[str, Any]:
    return {
        "queue_mode": QUEUE_MODE,
        "total_queued": sum(p.get("queue_load", 0) for p in TASK_PROFILES.values()),
        "profiles": [
            {"profile": pid, "queue_load": p.get("queue_load"), "queue": p.get("queue", [])}
            for pid, p in TASK_PROFILES.items()
        ],
        "read_only": True,
        "preview_only": True,
    }


def task_orchestration_intelligence_watch() -> Dict[str, Any]:
    active = [p for p in TASK_PROFILES.values() if p.get("task_status") in ("running", "verification")]
    return {
        "watch_active": len(active) > 0,
        "watch_profiles": [
            {
                "current_task": p.get("current_task"),
                "current_phase": p.get("current_phase"),
                "completion_percent": p.get("completion_percent"),
                "task_health": p.get("task_health"),
                "estimated_remaining_time": p.get("estimated_remaining_time"),
            }
            for p in active
        ],
        "progress_bar_width": 84,
        "pixel_difference_allowed": 0,
        "status_stream": "real_task_stages_only",
        "no_fake_activity": True,
        "read_only": True,
        "preview_only": True,
    }


def task_orchestration_intelligence_preview(
    task_type: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_task_profile(task_type, command, project_area)
    p = TASK_PROFILES[pid]
    result = {
        "profile_id": pid,
        "health_score": p.get("health_score"),
        "queue_load": p.get("queue_load"),
        "completion_forecast": p.get("completion_forecast"),
        "risk_score": p.get("risk_score"),
        "current_task": p.get("current_task"),
        "current_phase": p.get("current_phase"),
        "completion_percent": p.get("completion_percent"),
        "estimated_remaining_steps": p.get("estimated_remaining_steps"),
        "estimated_remaining_time": p.get("estimated_remaining_time"),
        "task_health": p.get("task_health"),
        "task_status": p.get("task_status"),
        "pending_commands": p.get("pending_commands", []),
        "queue": p.get("queue", []),
        "stuck_detected": p.get("stuck_detected", False),
        "read_only": True,
        "preview_only": True,
    }
    if p.get("stuck_detected"):
        result["stuck_reason"] = p.get("stuck_reason")
        result["stuck_risk_level"] = p.get("stuck_risk_level")
        result["stuck_alternative"] = p.get("stuck_alternative")
    return result


def task_orchestration_intelligence_add_command(command: str = "") -> Dict[str, Any]:
    return {
        "captured_command": command or "default_command",
        "queue_position": 1,
        "status": "queued",
        "estimated_execution_order": "after_current_task",
        "queue_mode": QUEUE_MODE,
        "note": "Command captured and queued. Execution simulated only.",
        "read_only": True,
        "preview_only": True,
    }


def task_orchestration_intelligence_follow_up(captured_command: str = "") -> Dict[str, Any]:
    return {
        "captured_command": captured_command or "default_follow_up",
        "queue_position": 2,
        "estimated_execution_order": "after_current_task",
        "follow_up_examples": FOLLOW_UP_EXAMPLES,
        "guided_conversations": GUIDED_CONVERSATIONS,
        "completion_actions": COMPLETION_ACTIONS,
        "workspace_suggestions": WORKSPACE_SUGGESTIONS,
        "pending_context": {
            "pending_commands": 3,
            "future_actions": ["security_review", "report_generation", "github_check", "device_sleep"],
            "completion_requests": ["run_security_review", "create_report", "check_github", "schedule_sleep"],
        },
        "read_only": True,
        "preview_only": True,
    }
