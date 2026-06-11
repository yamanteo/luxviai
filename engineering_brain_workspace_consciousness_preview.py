from __future__ import annotations

from typing import Any, Dict, List, Optional

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
from engineering_prediction_forecast_intelligence_preview import (
    engineering_forecast_intelligence_registry,
)
from workspace_intelligence_preview import (
    workspace_intelligence_status,
)
from task_orchestration_intelligence_preview import (
    task_orchestration_intelligence_status,
)
from luxcode_core_status_snapshot import (
    luxcode_core_status_snapshot,
)


WORKSPACE_CONSCIOUSNESS_CAPABILITIES = [
    "workspace_awareness",
    "active_project_awareness",
    "task_queue_awareness",
    "command_queue_awareness",
    "file_activity_awareness",
    "workspace_context_mapping",
    "workspace_priority_analysis",
    "workspace_attention_engine",
    "workspace_state_tracking",
    "workspace_summary_generation",
    "workspace_health_analysis",
    "workspace_focus_management",
]

CONSCIOUSNESS_PIPELINE = [
    "workspace_detection",
    "project_detection",
    "task_detection",
    "queue_analysis",
    "priority_analysis",
    "context_assembly",
    "workspace_understanding",
    "workspace_summary",
]

WORKSPACE_PROFILES: Dict[str, Dict[str, Any]] = {
    "idle_workspace": {
        "aliases": ["idle", "bos", "empty", "no_activity", "sakin"],
        "consciousness_status": "idle_workspace",
        "consciousness_health": "pass",
        "consciousness_summary": "Workspace idle. No active projects, tasks, or commands. All systems nominal.",
        "health_score": 0.96,
        "risk_score": 0.04,
        "active_project_count": 0,
        "active_task_count": 0,
        "queued_command_count": 0,
        "workspace_focus": None,
        "recommended_actions": ["await_activity", "maintain_awareness"],
        "recommended_next_action": "workspace idle — awaiting activity",
    },
    "active_workspace": {
        "aliases": ["active", "aktif", "running", "calisiyor", "busy"],
        "consciousness_status": "active_workspace",
        "consciousness_health": "pass",
        "consciousness_summary": "Active workspace with focused operations. Single project active. Tasks running normally.",
        "health_score": 0.88,
        "risk_score": 0.12,
        "active_project_count": 1,
        "active_task_count": 2,
        "queued_command_count": 1,
        "workspace_focus": "single_project",
        "recommended_actions": ["monitor_progress", "track_active_tasks"],
        "recommended_next_action": "active workspace — monitoring progress",
    },
    "multi_project_workspace": {
        "aliases": ["multi_project", "coklu_proje", "multiple", "several"],
        "consciousness_status": "multi_project_workspace",
        "consciousness_health": "warning",
        "consciousness_summary": "Multiple projects active in workspace. Context switching detected. Priority management recommended.",
        "health_score": 0.76,
        "risk_score": 0.28,
        "active_project_count": 3,
        "active_task_count": 5,
        "queued_command_count": 3,
        "workspace_focus": "scattered",
        "recommended_actions": ["consolidate_focus", "prioritize_projects"],
        "recommended_next_action": "multi-project — consolidate focus and prioritize",
    },
    "high_activity_workspace": {
        "aliases": ["high_activity", "yogun", "many_tasks", "cok_is"],
        "consciousness_status": "high_activity_workspace",
        "consciousness_health": "warning",
        "consciousness_summary": "High activity workspace with many tasks and commands. Attention management recommended.",
        "health_score": 0.65,
        "risk_score": 0.40,
        "active_project_count": 2,
        "active_task_count": 8,
        "queued_command_count": 6,
        "workspace_focus": "overloaded",
        "recommended_actions": ["manage_attention", "reduce_context_switching", "batch_commands"],
        "recommended_next_action": "high activity — manage attention and batch work",
    },
    "attention_required_workspace": {
        "aliases": ["attention_required", "dikkat_gerekli", "needs_focus", "blocked_work"],
        "consciousness_status": "attention_required_workspace",
        "consciousness_health": "degraded",
        "consciousness_summary": "Workspace requires attention. Blocked tasks or pending decisions detected. Intervention recommended.",
        "health_score": 0.48,
        "risk_score": 0.65,
        "active_project_count": 2,
        "active_task_count": 4,
        "queued_command_count": 3,
        "workspace_focus": "blocked",
        "recommended_actions": ["resolve_blockers", "clear_pending_decisions", "refocus"],
        "recommended_next_action": "attention required — resolve blockers",
    },
    "critical_workspace": {
        "aliases": ["critical", "kritik", "emergency", "acil"],
        "consciousness_status": "critical_workspace",
        "consciousness_health": "critical",
        "consciousness_summary": "Critical workspace state. Multiple issues requiring immediate attention. Escalation recommended.",
        "health_score": 0.20,
        "risk_score": 0.90,
        "active_project_count": 1,
        "active_task_count": 3,
        "queued_command_count": 5,
        "workspace_focus": "critical",
        "recommended_actions": ["immediate_intervention", "escalate_issues", "stabilize_workspace"],
        "recommended_next_action": "critical workspace — immediate intervention required",
    },
}

# ---------- internal helpers ----------


def _select_workspace_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in WORKSPACE_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "idle_workspace"


def _compute_attention_map(pid: str) -> Dict[str, Any]:
    p = WORKSPACE_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    attention_score = round(health * 0.8, 2)
    return {
        "attention_map": {
            "active_work": f"{p.get('active_task_count', 0)} tasks in {p.get('active_project_count', 0)} projects",
            "waiting_work": f"{max(0, p.get('queued_command_count', 0) - 1)} pending commands",
            "blocked_work": "yes" if health < 0.50 else "no",
            "important_work": "high priority tasks present" if p.get('active_task_count', 0) > 3 else "normal operations",
            "critical_work": "requires_immediate_action" if health < 0.30 else "none",
        },
        "attention_score": attention_score,
        "recommended_focus": (
            "none_required" if health > 0.80
            else "consolidate_tasks" if health > 0.60
            else "resolve_blockers" if health > 0.35
            else "immediate_intervention"
        ),
        "read_only": True,
        "preview_only": True,
    }


def _compute_focus_analysis(pid: str) -> Dict[str, Any]:
    p = WORKSPACE_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    return {
        "workspace_focus": p.get("workspace_focus"),
        "workspace_priority": (
            "low" if health > 0.80
            else "medium" if health > 0.50
            else "high" if health > 0.30
            else "critical"
        ),
        "workspace_confidence": round(health * 0.85, 2),
        "active_project": p.get("active_project_count"),
        "active_branch": "main",
        "active_workspace": "primary",
        "active_task": p.get("active_task_count"),
        "active_context": p.get("consciousness_status"),
        "read_only": True,
        "preview_only": True,
    }


def _compute_queue_analysis(pid: str) -> Dict[str, Any]:
    p = WORKSPACE_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    q_count = p.get("queued_command_count", 0)

    return {
        "queue_health": "healthy" if health > 0.70 else (
            "degraded" if health > 0.40 else "critical"
        ),
        "queue_priority": "low" if q_count == 0 else (
            "normal" if q_count <= 3 else "high"
        ),
        "queue_summary": f"{q_count} commands in queue" if q_count > 0 else "queue empty",
        "queued_commands": [
            "workspace_analysis", "task_update", "report_generation"
        ][:max(1, q_count)],
        "pending_commands": max(0, q_count - 1),
        "scheduled_commands": max(0, q_count - 2),
        "follow_up_commands": max(0, q_count - 3),
        "read_only": True,
        "preview_only": True,
    }


def _compute_workspace_score(pid: str) -> Dict[str, float]:
    p = WORKSPACE_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    ws_health = round(health * 0.85, 2)
    clarity = round(health * 0.75, 2)
    focus = round(health * 0.70, 2)
    attention = round(health * 0.80, 2)
    overall = round(
        (ws_health * 0.25 + clarity * 0.25 + focus * 0.25 + attention * 0.25), 2
    )
    return {
        "workspace_health": ws_health,
        "workspace_clarity": clarity,
        "workspace_focus": focus,
        "workspace_attention": attention,
        "overall_workspace_score": overall,
    }


# ---------- public entry points ----------


def workspace_consciousness_intelligence_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "36.1",
        "name": "Engineering Brain Workspace Consciousness Preview",
        "status": "workspace_consciousness_ready",
        "version": "1.0",
        "capabilities": WORKSPACE_CONSCIOUSNESS_CAPABILITIES,
        "pipeline": CONSCIOUSNESS_PIPELINE,
        "workspace_profile_count": len(WORKSPACE_PROFILES),
        "operation_mode": "read_only_preview_only",
        "connected_layers": ["36.0", "35.9", "35.8", "35.7", "35.6"],
        "available_endpoints": [
            "/workspace-consciousness/status",
            "/workspace-consciousness/capabilities",
            "/workspace-consciousness/preview",
            "/workspace-consciousness/attention-map",
            "/workspace-consciousness/focus-analysis",
            "/workspace-consciousness/queue-analysis",
            "/workspace-consciousness/workspace-health",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "workspace_modification": False,
        "command_execution": False,
        "task_execution": False,
        "deployment_execution": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only workspace consciousness preview. No workspace or command modifications performed.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def workspace_consciousness_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "36.1",
        "name": "Workspace Consciousness Capabilities",
        "status": "consciousness_capabilities_ready",
        "capabilities": [
            {"name": "workspace_awareness", "description": "Maintain continuous awareness of workspace state", "read_only": True},
            {"name": "active_project_awareness", "description": "Track active projects and their priorities", "read_only": True},
            {"name": "task_queue_awareness", "description": "Track task queue state and progress", "read_only": True},
            {"name": "command_queue_awareness", "description": "Track command queue state and pending commands", "read_only": True},
            {"name": "file_activity_awareness", "description": "Track file changes and activity", "read_only": True},
            {"name": "workspace_context_mapping", "description": "Map workspace context across projects and tasks", "read_only": True},
            {"name": "workspace_priority_analysis", "description": "Analyze workspace priorities", "read_only": True},
            {"name": "workspace_attention_engine", "description": "Engine for workspace attention and focus management", "read_only": True},
            {"name": "workspace_state_tracking", "description": "Track workspace state across time", "read_only": True},
            {"name": "workspace_summary_generation", "description": "Generate comprehensive workspace summary", "read_only": True},
            {"name": "workspace_health_analysis", "description": "Analyze workspace health and clarity", "read_only": True},
            {"name": "workspace_focus_management", "description": "Manage workspace focus and attention allocation", "read_only": True},
        ],
        "pipeline": CONSCIOUSNESS_PIPELINE,
        "workspace_profiles": list(WORKSPACE_PROFILES.keys()),
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def workspace_consciousness_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_workspace_profile(target_issue, command, project_area)
    p = WORKSPACE_PROFILES[pid]
    score = _compute_workspace_score(pid)
    focus = _compute_focus_analysis(pid)

    return {
        "workspace_id": pid,
        "consciousness_status": p["consciousness_status"],
        "consciousness_health": p["consciousness_health"],
        "consciousness_summary": p.get("consciousness_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "workspace_score": score,
        "focus_analysis": focus,
        "active_project_count": p.get("active_project_count"),
        "active_task_count": p.get("active_task_count"),
        "queued_command_count": p.get("queued_command_count"),
        "workspace_focus": p.get("workspace_focus"),
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_stage": "workspace_detection",
        "pipeline_progress": {
            "completed": [],
            "current": "workspace_detection",
            "remaining": CONSCIOUSNESS_PIPELINE[1:],
        },
        "read_only": True,
        "preview_only": True,
    }


def workspace_consciousness_intelligence_attention_map(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_workspace_profile(target_issue)
    attention = _compute_attention_map(pid)
    score = _compute_workspace_score(pid)

    return {
        "attention_map": attention,
        "workspace_score": score,
        "pipeline_stage": "priority_analysis",
        "read_only": True,
        "preview_only": True,
    }


def workspace_consciousness_intelligence_focus_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_workspace_profile(target_issue)
    focus = _compute_focus_analysis(pid)
    score = _compute_workspace_score(pid)

    return {
        "focus_analysis": focus,
        "workspace_score": score,
        "pipeline_stage": "context_assembly",
        "read_only": True,
        "preview_only": True,
    }


def workspace_consciousness_intelligence_queue_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_workspace_profile(target_issue)
    queue = _compute_queue_analysis(pid)
    score = _compute_workspace_score(pid)

    return {
        "queue_analysis": queue,
        "workspace_score": score,
        "pipeline_stage": "queue_analysis",
        "read_only": True,
        "preview_only": True,
    }


def workspace_consciousness_intelligence_workspace_health(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_workspace_profile(target_issue)
    score = _compute_workspace_score(pid)
    attention = _compute_attention_map(pid)
    focus = _compute_focus_analysis(pid)
    queue = _compute_queue_analysis(pid)

    return {
        "workspace_health": score,
        "attention_map": attention,
        "focus_analysis": focus,
        "queue_analysis": queue,
        "pipeline_stage": "workspace_summary",
        "read_only": True,
        "preview_only": True,
    }


def workspace_consciousness_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for wid, w in WORKSPACE_PROFILES.items():
        items.append({
            "workspace_id": wid,
            "consciousness_status": w["consciousness_status"],
            "consciousness_health": w["consciousness_health"],
            "health_score": w.get("health_score"),
            "risk_score": w.get("risk_score"),
            "active_project_count": w.get("active_project_count"),
            "active_task_count": w.get("active_task_count"),
            "queued_command_count": w.get("queued_command_count"),
        })
    return {
        "layer": "36.1",
        "name": "Workspace Consciousness Registry",
        "status": "consciousness_registry_ready",
        "read_only": True,
        "preview_only": True,
        "workspace_profile_count": len(items),
        "workspace_profiles": items,
        "pass_count": sum(1 for i in items if i["consciousness_health"] == "pass"),
        "warning_count": sum(1 for i in items if i["consciousness_health"] == "warning"),
        "degraded_count": sum(1 for i in items if i["consciousness_health"] == "degraded"),
        "critical_count": sum(1 for i in items if i["consciousness_health"] == "critical"),
    }
