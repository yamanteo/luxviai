from __future__ import annotations

from typing import Any, Dict, List, Optional

from engineering_brain_workspace_consciousness_preview import (
    workspace_consciousness_intelligence_registry,
)
from luxcode_engineering_brain_core_preview import (
    luxcode_engineering_brain_core_registry,
)
from engineering_self_reflection_meta_intelligence_preview import (
    engineering_meta_intelligence_registry,
)
from engineering_autonomy_intelligence_preview import (
    engineering_autonomy_intelligence_registry,
)
from engineering_strategy_intelligence_preview import (
    engineering_strategy_intelligence_registry,
)
from task_orchestration_intelligence_preview import (
    task_orchestration_intelligence_status,
)
from luxcode_core_status_snapshot import (
    luxcode_core_status_snapshot,
)


TASK_CONSCIOUSNESS_CAPABILITIES = [
    "active_task_awareness",
    "multi_task_awareness",
    "task_priority_tracking",
    "task_state_tracking",
    "command_queue_awareness",
    "conversation_awareness",
    "follow_up_awareness",
    "execution_continuity_tracking",
    "task_summary_generation",
    "task_attention_analysis",
    "task_health_analysis",
    "task_focus_management",
]

TASK_CONSCIOUSNESS_PIPELINE = [
    "task_detection",
    "task_classification",
    "priority_assignment",
    "queue_analysis",
    "conversation_analysis",
    "execution_continuity_analysis",
    "task_understanding",
    "task_summary",
]

TASK_PROFILES: Dict[str, Dict[str, Any]] = {
    "idle_task": {
        "aliases": ["idle", "bos", "no_task", "waiting", "beklemede"],
        "task_status": "idle_task",
        "task_health": "pass",
        "task_summary": "No active tasks. Task consciousness idle. Ready for new task intake.",
        "health_score": 0.95,
        "risk_score": 0.05,
        "active_task_count": 0,
        "queued_command_count": 0,
        "continuity_score": 1.0,
        "recommended_actions": ["await_task", "maintain_continuity"],
        "recommended_next_action": "idle — awaiting new task",
    },
    "active_task": {
        "aliases": ["active", "aktif", "running", "calisiyor", "in_progress"],
        "task_status": "active_task",
        "task_health": "pass",
        "task_summary": "Active task in progress. Context preserved. Execution continuing normally.",
        "health_score": 0.88,
        "risk_score": 0.12,
        "active_task_count": 1,
        "queued_command_count": 1,
        "continuity_score": 0.92,
        "recommended_actions": ["continue_execution", "preserve_context"],
        "recommended_next_action": "active task — continuing execution",
    },
    "queued_task": {
        "aliases": ["queued", "sira", "pending", "bekleyen"],
        "task_status": "queued_task",
        "task_health": "pass",
        "task_summary": "Tasks queued and waiting for execution. Queue order maintained. Priority levels assigned.",
        "health_score": 0.82,
        "risk_score": 0.18,
        "active_task_count": 1,
        "queued_command_count": 3,
        "continuity_score": 0.85,
        "recommended_actions": ["process_queue", "monitor_priority"],
        "recommended_next_action": "queued tasks — processing in priority order",
    },
    "paused_task": {
        "aliases": ["paused", "duraklatilmis", "on_hold", "suspended"],
        "task_status": "paused_task",
        "task_health": "warning",
        "task_summary": "Task paused. Context preserved. Ready to resume when conditions met.",
        "health_score": 0.70,
        "risk_score": 0.32,
        "active_task_count": 1,
        "queued_command_count": 0,
        "continuity_score": 0.75,
        "recommended_actions": ["resume_when_ready", "verify_context_integrity"],
        "recommended_next_action": "paused — context preserved for resumption",
    },
    "blocked_task": {
        "aliases": ["blocked", "engellenmis", "stuck", "takili", "waiting_for"],
        "task_status": "blocked_task",
        "task_health": "degraded",
        "task_summary": "Task blocked. External dependency or condition required. Resolution needed before continuation.",
        "health_score": 0.45,
        "risk_score": 0.65,
        "active_task_count": 1,
        "queued_command_count": 0,
        "continuity_score": 0.40,
        "recommended_actions": ["resolve_blocker", "clear_dependency"],
        "recommended_next_action": "blocked — resolve dependency to continue",
    },
    "completed_task": {
        "aliases": ["completed", "tamamlanmis", "done", "bitti", "finished"],
        "task_status": "completed_task",
        "task_health": "pass",
        "task_summary": "Task completed successfully. Results available. Ready for next task.",
        "health_score": 0.92,
        "risk_score": 0.08,
        "active_task_count": 0,
        "queued_command_count": 0,
        "continuity_score": 1.0,
        "recommended_actions": ["review_results", "prepare_next_task"],
        "recommended_next_action": "completed — results ready for review",
    },
}

# ---------- internal helpers ----------


def _select_task_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in TASK_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "idle_task"


def _compute_task_analysis(pid: str) -> Dict[str, Any]:
    p = TASK_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)

    return {
        "task_focus": p.get("task_status"),
        "task_status": "focused" if p.get("active_task_count", 0) >= 1 else "idle",
        "task_confidence": round(health * 0.85, 2),
        "current_task": "engineering_analysis" if p.get("active_task_count", 0) > 0 else None,
        "current_step": "execution" if p.get("active_task_count", 0) > 0 else None,
        "current_progress": "in_progress" if p.get("active_task_count", 0) > 0 else "idle",
        "current_context": p.get("task_summary"),
        "current_dependencies": (
            ["external_input"] if risk > 0.50 else []
        ),
        "read_only": True,
        "preview_only": True,
    }


def _compute_continuity_analysis(pid: str) -> Dict[str, Any]:
    p = TASK_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    continuity = p.get("continuity_score", 0.50)

    return {
        "continuity_score": continuity,
        "resume_point": (
            "no_resume_needed" if p.get("task_status") in ("idle_task", "completed_task")
            else "current_position_preserved" if continuity > 0.60
            else "partial_context_loss"
        ),
        "continuity_health": "healthy" if continuity > 0.70 else (
            "degraded" if continuity > 0.40 else "critical"
        ),
        "active_context": p.get("task_summary"),
        "task_position": f"task_{p.get('task_status')}",
        "execution_state": p.get("task_status"),
        "conversation_state": "active" if health > 0.50 else "awaiting_input",
        "follow_up_state": (
            "none_pending" if health > 0.80
            else "follow_up_available"
        ),
        "read_only": True,
        "preview_only": True,
    }


def _compute_queue_analysis(pid: str) -> Dict[str, Any]:
    p = TASK_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    q_count = p.get("queued_command_count", 0)

    return {
        "queue_status": "empty" if q_count == 0 else (
            "processing" if q_count <= 2 else "backlog"
        ),
        "queue_priority": "low" if q_count == 0 else (
            "normal" if q_count <= 3 else "high"
        ),
        "queue_health": "healthy" if health > 0.70 else (
            "degraded" if health > 0.40 else "critical"
        ),
        "added_commands": max(0, q_count),
        "pending_commands": max(0, q_count - 1),
        "scheduled_commands": max(0, q_count - 2),
        "deferred_commands": max(0, q_count - 3),
        "read_only": True,
        "preview_only": True,
    }


def _compute_conversation_analysis(pid: str) -> Dict[str, Any]:
    p = TASK_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    return {
        "conversation_summary": (
            "no_active_conversation" if health > 0.85
            else "user_interaction_in_progress" if health > 0.50
            else "awaiting_user_input"
        ),
        "conversation_context": p.get("task_summary"),
        "conversation_priority": "low" if health > 0.80 else (
            "normal" if health > 0.50 else "high"
        ),
        "user_questions": "none_pending" if health > 0.70 else "questions_queued",
        "status_requests": "none" if health > 0.80 else "pending",
        "clarifications": "none_needed" if health > 0.70 else "clarification_requested",
        "follow_ups": "none" if health > 0.80 else "follow_up_available",
        "background_execution": "continuing" if p.get("active_task_count", 0) > 0 else "idle",
        "read_only": True,
        "preview_only": True,
    }


def _compute_task_score(pid: str) -> Dict[str, float]:
    p = TASK_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    continuity = p.get("continuity_score", 0.50)

    task_health = round(health * 0.85, 2)
    continuity_health = round(continuity * 0.9, 2)
    queue_health = round(health * 0.75, 2)
    focus_health = round(health * 0.70, 2)
    overall = round(
        (task_health * 0.25 + continuity_health * 0.30 + queue_health * 0.20 + focus_health * 0.25), 2
    )
    return {
        "task_health": task_health,
        "continuity_health": continuity_health,
        "queue_health": queue_health,
        "focus_health": focus_health,
        "overall_task_score": overall,
    }


# ---------- public entry points ----------


def task_consciousness_intelligence_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "36.2",
        "name": "Engineering Brain Task Consciousness Preview",
        "status": "task_consciousness_ready",
        "version": "1.0",
        "capabilities": TASK_CONSCIOUSNESS_CAPABILITIES,
        "pipeline": TASK_CONSCIOUSNESS_PIPELINE,
        "task_profile_count": len(TASK_PROFILES),
        "operation_mode": "read_only_preview_only",
        "core_mission": "work_continues_questions_answered_nothing_forgotten",
        "connected_layers": ["36.1", "36.0", "35.9", "35.8", "35.7"],
        "available_endpoints": [
            "/task-consciousness/status",
            "/task-consciousness/capabilities",
            "/task-consciousness/preview",
            "/task-consciousness/task-analysis",
            "/task-consciousness/continuity-analysis",
            "/task-consciousness/queue-analysis",
            "/task-consciousness/conversation-analysis",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "task_execution": False,
        "command_execution": False,
        "conversation_override": False,
        "deployment_execution": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only task consciousness preview. No task execution or command modifications performed.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def task_consciousness_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "36.2",
        "name": "Task Consciousness Capabilities",
        "status": "task_capabilities_ready",
        "capabilities": [
            {"name": "active_task_awareness", "description": "Maintain awareness of currently active task", "read_only": True},
            {"name": "multi_task_awareness", "description": "Maintain awareness across multiple concurrent tasks", "read_only": True},
            {"name": "task_priority_tracking", "description": "Track task priority levels and ordering", "read_only": True},
            {"name": "task_state_tracking", "description": "Track task state transitions", "read_only": True},
            {"name": "command_queue_awareness", "description": "Maintain awareness of queued commands", "read_only": True},
            {"name": "conversation_awareness", "description": "Maintain awareness of user conversations", "read_only": True},
            {"name": "follow_up_awareness", "description": "Track follow-up items and pending actions", "read_only": True},
            {"name": "execution_continuity_tracking", "description": "Track execution continuity for seamless resumption", "read_only": True},
            {"name": "task_summary_generation", "description": "Generate comprehensive task summary", "read_only": True},
            {"name": "task_attention_analysis", "description": "Analyze task attention and focus requirements", "read_only": True},
            {"name": "task_health_analysis", "description": "Analyze task health across all dimensions", "read_only": True},
            {"name": "task_focus_management", "description": "Manage task focus and attention allocation", "read_only": True},
        ],
        "pipeline": TASK_CONSCIOUSNESS_PIPELINE,
        "task_profiles": list(TASK_PROFILES.keys()),
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def task_consciousness_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_task_profile(target_issue, command, project_area)
    p = TASK_PROFILES[pid]
    score = _compute_task_score(pid)
    task_analysis = _compute_task_analysis(pid)
    continuity = _compute_continuity_analysis(pid)

    return {
        "task_id": pid,
        "task_status": p["task_status"],
        "task_health": p["task_health"],
        "task_summary": p.get("task_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "task_score": score,
        "task_analysis": task_analysis,
        "continuity_analysis": continuity,
        "active_task_count": p.get("active_task_count"),
        "queued_command_count": p.get("queued_command_count"),
        "continuity_score": p.get("continuity_score"),
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_stage": "task_detection",
        "pipeline_progress": {
            "completed": [],
            "current": "task_detection",
            "remaining": TASK_CONSCIOUSNESS_PIPELINE[1:],
        },
        "read_only": True,
        "preview_only": True,
    }


def task_consciousness_intelligence_task_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_task_profile(target_issue)
    task_analysis = _compute_task_analysis(pid)
    score = _compute_task_score(pid)

    return {
        "task_analysis": task_analysis,
        "task_score": score,
        "pipeline_stage": "task_classification",
        "read_only": True,
        "preview_only": True,
    }


def task_consciousness_intelligence_continuity_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_task_profile(target_issue)
    continuity = _compute_continuity_analysis(pid)
    score = _compute_task_score(pid)

    return {
        "continuity_analysis": continuity,
        "task_score": score,
        "pipeline_stage": "execution_continuity_analysis",
        "read_only": True,
        "preview_only": True,
    }


def task_consciousness_intelligence_queue_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_task_profile(target_issue)
    queue = _compute_queue_analysis(pid)
    score = _compute_task_score(pid)

    return {
        "queue_analysis": queue,
        "task_score": score,
        "pipeline_stage": "queue_analysis",
        "read_only": True,
        "preview_only": True,
    }


def task_consciousness_intelligence_conversation_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_task_profile(target_issue)
    conversation = _compute_conversation_analysis(pid)
    score = _compute_task_score(pid)

    return {
        "conversation_analysis": conversation,
        "task_score": score,
        "pipeline_stage": "conversation_analysis",
        "read_only": True,
        "preview_only": True,
    }


def task_consciousness_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for tid, t in TASK_PROFILES.items():
        items.append({
            "task_id": tid,
            "task_status": t["task_status"],
            "task_health": t["task_health"],
            "health_score": t.get("health_score"),
            "risk_score": t.get("risk_score"),
            "active_task_count": t.get("active_task_count"),
            "queued_command_count": t.get("queued_command_count"),
            "continuity_score": t.get("continuity_score"),
        })
    return {
        "layer": "36.2",
        "name": "Task Consciousness Registry",
        "status": "task_registry_ready",
        "read_only": True,
        "preview_only": True,
        "task_profile_count": len(items),
        "task_profiles": items,
        "pass_count": sum(1 for i in items if i["task_health"] == "pass"),
        "warning_count": sum(1 for i in items if i["task_health"] == "warning"),
        "degraded_count": sum(1 for i in items if i["task_health"] == "degraded"),
        "critical_count": sum(1 for i in items if i["task_health"] == "critical"),
        "avg_continuity": round(
            sum(i.get("continuity_score", 0) for i in items) / max(1, len(items)), 2
        ),
    }
