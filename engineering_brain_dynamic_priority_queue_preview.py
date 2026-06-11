from __future__ import annotations

from typing import Any, Dict, List, Optional

from engineering_brain_user_intent_continuity_preview import (
    user_intent_continuity_intelligence_registry,
)
from engineering_brain_multi_session_continuity_preview import (
    multi_session_continuity_intelligence_registry,
)
from engineering_brain_persistent_execution_intelligence_preview import (
    persistent_execution_intelligence_registry,
)
from engineering_brain_task_consciousness_preview import (
    task_consciousness_intelligence_registry,
)
from engineering_brain_workspace_consciousness_preview import (
    workspace_consciousness_intelligence_registry,
)
from luxcode_engineering_brain_core_preview import (
    luxcode_engineering_brain_core_registry,
)
from luxcode_core_status_snapshot import (
    luxcode_core_status_snapshot,
)


DYNAMIC_PRIORITY_CAPABILITIES = [
    "dynamic_priority_analysis",
    "queue_health_monitoring",
    "priority_shift_detection",
    "command_queue_management",
    "task_queue_management",
    "follow_up_queue_management",
    "execution_order_generation",
    "queue_conflict_detection",
    "priority_reconciliation",
    "queue_summary_generation",
    "queue_health_analysis",
    "priority_attention_engine",
]

PRIORITY_PIPELINE = [
    "task_detection",
    "queue_analysis",
    "priority_scoring",
    "conflict_analysis",
    "execution_ordering",
    "priority_validation",
    "queue_optimization",
    "priority_summary",
]

PRIORITY_STATES = [
    "critical_priority",
    "high_priority",
    "normal_priority",
    "background_priority",
    "deferred_priority",
    "blocked_priority",
]

PRIORITY_PROFILES: Dict[str, Dict[str, Any]] = {
    "critical_priority": {
        "aliases": ["critical", "kritik", "urgent", "acil", "immediate"],
        "priority_status": "critical_priority",
        "priority_health": "warning",
        "priority_summary": "Critical priority items detected. Immediate attention required. System escalation recommended.",
        "health_score": 0.30,
        "risk_score": 0.85,
        "queue_load": 2,
        "priority_score": 0.95,
        "recommended_actions": ["execute_immediately", "escalate_if_blocked"],
        "recommended_next_action": "critical — immediate execution required",
    },
    "high_priority": {
        "aliases": ["high", "yuksek", "important", "onemli"],
        "priority_status": "high_priority",
        "priority_health": "warning",
        "priority_summary": "High priority items in queue. Should be processed before normal and background items.",
        "health_score": 0.55,
        "risk_score": 0.50,
        "queue_load": 3,
        "priority_score": 0.80,
        "recommended_actions": ["process_next", "reduce_queue_load"],
        "recommended_next_action": "high priority — process next available",
    },
    "normal_priority": {
        "aliases": ["normal", "normal", "standard", "regular"],
        "priority_status": "normal_priority",
        "priority_health": "pass",
        "priority_summary": "Normal priority queue operating within expected parameters. Standard processing.",
        "health_score": 0.82,
        "risk_score": 0.18,
        "queue_load": 5,
        "priority_score": 0.55,
        "recommended_actions": ["continue_normal_processing", "monitor_for_shifts"],
        "recommended_next_action": "normal priority — continuing standard processing",
    },
    "background_priority": {
        "aliases": ["background", "arka_plan", "low", "dusuk", "minor"],
        "priority_status": "background_priority",
        "priority_health": "pass",
        "priority_summary": "Background priority items. Processed when resources available. No urgency.",
        "health_score": 0.90,
        "risk_score": 0.10,
        "queue_load": 4,
        "priority_score": 0.25,
        "recommended_actions": ["process_when_idle", "defer_if_busy"],
        "recommended_next_action": "background — process when resources available",
    },
    "deferred_priority": {
        "aliases": ["deferred", "ertelenmis", "postponed", "later"],
        "priority_status": "deferred_priority",
        "priority_health": "pass",
        "priority_summary": "Deferred priority items. Scheduled for future processing. Context preserved.",
        "health_score": 0.85,
        "risk_score": 0.15,
        "queue_load": 2,
        "priority_score": 0.15,
        "recommended_actions": ["preserve_for_future", "review_when_ready"],
        "recommended_next_action": "deferred — preserved for future processing",
    },
    "blocked_priority": {
        "aliases": ["blocked", "engellenmis", "stuck", "dependency_blocked"],
        "priority_status": "blocked_priority",
        "priority_health": "degraded",
        "priority_summary": "Blocked priority items. Dependencies or conditions preventing execution.",
        "health_score": 0.40,
        "risk_score": 0.70,
        "queue_load": 2,
        "priority_score": 0.60,
        "recommended_actions": ["resolve_dependencies", "unblock_queue"],
        "recommended_next_action": "blocked — resolve dependencies to continue",
    },
}

# ---------- internal helpers ----------


def _select_priority_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in PRIORITY_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "normal_priority"


def _compute_priority_analysis(pid: str) -> Dict[str, Any]:
    p = PRIORITY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    score = p.get("priority_score", 0.50)

    return {
        "priority_map": {
            "active_tasks": [
                {"task": "engineering_analysis", "priority": score, "status": "running"},
                {"task": "report_generation", "priority": round(score * 0.7, 2), "status": "queued"},
            ],
            "queued_tasks": 3,
            "added_commands": 2,
            "follow_ups": 1,
            "workspace_events": 0,
        },
        "priority_score": score,
        "recommended_order": (
            "process_critical_first" if score > 0.80
            else "process_high_then_normal" if score > 0.50
            else "background_processing_idle"
        ),
        "read_only": True,
        "preview_only": True,
    }


def _compute_queue_analysis(pid: str) -> Dict[str, Any]:
    p = PRIORITY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    load = p.get("queue_load", 0)

    return {
        "queue_health": "healthy" if health > 0.70 else (
            "degraded" if health > 0.40 else "critical"
        ),
        "queue_complexity": "low" if load <= 2 else (
            "medium" if load <= 5 else "high"
        ),
        "queue_status": "balanced" if health > 0.70 else (
            "strained" if health > 0.40 else "overloaded"
        ),
        "active_queue": max(0, load - 1),
        "pending_queue": max(0, load),
        "deferred_queue": max(0, load - 2),
        "future_queue": max(0, load - 3),
        "read_only": True,
        "preview_only": True,
    }


def _compute_execution_order(pid: str) -> Dict[str, Any]:
    p = PRIORITY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    score = p.get("priority_score", 0.50)

    return {
        "execution_plan": {
            "recommended_execution_order": (
                ["critical_items", "high_items", "normal_items", "background_items"]
            ),
            "dependency_aware_order": (
                ["resolve_dependencies_first", "process_independent_items", "process_dependent_items"]
            ),
            "risk_aware_order": (
                ["risk_mitigation", "high_value_items", "standard_items"]
            ),
            "intent_aware_order": (
                ["user_requested_first", "continuation_items", "new_items"]
            ),
        },
        "execution_confidence": round(score * 0.85, 2),
        "read_only": True,
        "preview_only": True,
    }


def _compute_reconciliation(pid: str) -> Dict[str, Any]:
    p = PRIORITY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    return {
        "reconciliation_summary": (
            "no_reconciliation_needed" if health > 0.75
            else "priority_reconciliation_recommended"
        ),
        "recommended_priority_structure": (
            "maintain_current" if health > 0.75
            else "promote_critical_items" if health > 0.50
            else "restructure_queue"
        ),
        "competing_priorities": health < 0.60,
        "conflicting_commands": health < 0.50,
        "user_priority_changes": health < 0.55,
        "interrupted_tasks": health < 0.45,
        "read_only": True,
        "preview_only": True,
    }


def _compute_dynamic_score(pid: str) -> Dict[str, float]:
    p = PRIORITY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    p_score = p.get("priority_score", 0.50)

    priority_health = round(health * 0.80, 2)
    queue_health = round(health * 0.75, 2)
    exec_health = round(p_score * 0.70, 2)
    attention_health = round(health * 0.85, 2)
    overall = round(
        (priority_health * 0.25 + queue_health * 0.25 + exec_health * 0.25 + attention_health * 0.25), 2
    )
    return {
        "priority_health": priority_health,
        "queue_health": queue_health,
        "execution_order_health": exec_health,
        "attention_health": attention_health,
        "overall_priority_score": overall,
    }


# ---------- public entry points ----------


def dynamic_priority_intelligence_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "36.6",
        "name": "Engineering Brain Dynamic Priority & Queue Intelligence Preview",
        "status": "dynamic_priority_ready",
        "version": "1.0",
        "capabilities": DYNAMIC_PRIORITY_CAPABILITIES,
        "pipeline": PRIORITY_PIPELINE,
        "priority_states": PRIORITY_STATES,
        "priority_profile_count": len(PRIORITY_PROFILES),
        "operation_mode": "read_only_preview_only",
        "core_mission": "tasks_commands_and_requests_compete_luxcode_must_prioritize",
        "connected_layers": ["36.5", "36.4", "36.3", "36.2", "36.1", "36.0"],
        "available_endpoints": [
            "/dynamic-priority/status",
            "/dynamic-priority/capabilities",
            "/dynamic-priority/preview",
            "/dynamic-priority/priority-analysis",
            "/dynamic-priority/queue-analysis",
            "/dynamic-priority/execution-order",
            "/dynamic-priority/reconciliation",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "queue_execution": False,
        "priority_override": False,
        "command_execution": False,
        "deployment_execution": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only dynamic priority preview. No queue execution or priority override performed.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def dynamic_priority_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "36.6",
        "name": "Dynamic Priority Capabilities",
        "status": "priority_capabilities_ready",
        "capabilities": [
            {"name": "dynamic_priority_analysis", "description": "Analyze priorities dynamically across all queues", "read_only": True},
            {"name": "queue_health_monitoring", "description": "Monitor health of all active queues", "read_only": True},
            {"name": "priority_shift_detection", "description": "Detect shifts in priority levels", "read_only": True},
            {"name": "command_queue_management", "description": "Manage command queue priorities", "read_only": True},
            {"name": "task_queue_management", "description": "Manage task queue priorities", "read_only": True},
            {"name": "follow_up_queue_management", "description": "Manage follow-up queue priorities", "read_only": True},
            {"name": "execution_order_generation", "description": "Generate optimal execution order with dependency, risk, and intent awareness", "read_only": True},
            {"name": "queue_conflict_detection", "description": "Detect conflicts between queue items", "read_only": True},
            {"name": "priority_reconciliation", "description": "Reconcile competing priorities", "read_only": True},
            {"name": "queue_summary_generation", "description": "Generate comprehensive queue summary", "read_only": True},
            {"name": "queue_health_analysis", "description": "Analyze queue health across all dimensions", "read_only": True},
            {"name": "priority_attention_engine", "description": "Engine for priority attention management", "read_only": True},
        ],
        "pipeline": PRIORITY_PIPELINE,
        "priority_states": PRIORITY_STATES,
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def dynamic_priority_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_priority_profile(target_issue, command, project_area)
    p = PRIORITY_PROFILES[pid]
    score = _compute_dynamic_score(pid)
    priority = _compute_priority_analysis(pid)

    return {
        "priority_id": pid,
        "priority_status": p["priority_status"],
        "priority_health": p["priority_health"],
        "priority_summary": p.get("priority_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "dynamic_score": score,
        "priority_analysis": priority,
        "queue_load": p.get("queue_load"),
        "priority_score": p.get("priority_score"),
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_stage": "task_detection",
        "pipeline_progress": {
            "completed": [],
            "current": "task_detection",
            "remaining": PRIORITY_PIPELINE[1:],
        },
        "read_only": True,
        "preview_only": True,
    }


def dynamic_priority_intelligence_priority_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_priority_profile(target_issue)
    priority = _compute_priority_analysis(pid)
    score = _compute_dynamic_score(pid)

    return {
        "priority_analysis": priority,
        "dynamic_score": score,
        "pipeline_stage": "priority_scoring",
        "read_only": True,
        "preview_only": True,
    }


def dynamic_priority_intelligence_queue_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_priority_profile(target_issue)
    queue = _compute_queue_analysis(pid)
    score = _compute_dynamic_score(pid)

    return {
        "queue_analysis": queue,
        "dynamic_score": score,
        "pipeline_stage": "queue_analysis",
        "read_only": True,
        "preview_only": True,
    }


def dynamic_priority_intelligence_execution_order(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_priority_profile(target_issue)
    order = _compute_execution_order(pid)
    score = _compute_dynamic_score(pid)

    return {
        "execution_order": order,
        "dynamic_score": score,
        "pipeline_stage": "execution_ordering",
        "read_only": True,
        "preview_only": True,
    }


def dynamic_priority_intelligence_reconciliation(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_priority_profile(target_issue)
    reconciliation = _compute_reconciliation(pid)
    score = _compute_dynamic_score(pid)

    return {
        "reconciliation": reconciliation,
        "dynamic_score": score,
        "pipeline_stage": "priority_validation",
        "read_only": True,
        "preview_only": True,
    }


def dynamic_priority_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in PRIORITY_PROFILES.items():
        items.append({
            "priority_id": pid,
            "priority_status": p["priority_status"],
            "priority_health": p["priority_health"],
            "health_score": p.get("health_score"),
            "risk_score": p.get("risk_score"),
            "queue_load": p.get("queue_load"),
            "priority_score": p.get("priority_score"),
        })
    return {
        "layer": "36.6",
        "name": "Dynamic Priority Registry",
        "status": "priority_registry_ready",
        "read_only": True,
        "preview_only": True,
        "priority_profile_count": len(items),
        "priority_profiles": items,
        "pass_count": sum(1 for i in items if i["priority_health"] == "pass"),
        "warning_count": sum(1 for i in items if i["priority_health"] == "warning"),
        "degraded_count": sum(1 for i in items if i["priority_health"] == "degraded"),
        "critical_count": sum(1 for i in items if i["priority_health"] == "critical"),
        "total_queue_load": sum(i.get("queue_load", 0) for i in items),
        "avg_priority_score": round(
            sum(i.get("priority_score", 0) for i in items) / max(1, len(items)), 2
        ),
    }
