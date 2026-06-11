from __future__ import annotations

from typing import Any, Dict, List, Optional

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


USER_INTENT_CAPABILITIES = [
    "intent_tracking",
    "intent_history_analysis",
    "intent_change_detection",
    "priority_shift_detection",
    "added_command_tracking",
    "deferred_intent_tracking",
    "goal_continuity_analysis",
    "intent_conflict_detection",
    "intent_reconciliation",
    "intent_summary_generation",
    "intent_health_analysis",
    "intent_priority_engine",
]

INTENT_PIPELINE = [
    "user_request_detection",
    "intent_extraction",
    "intent_tracking",
    "priority_analysis",
    "intent_change_detection",
    "goal_continuity_analysis",
    "intent_reconciliation",
    "intent_summary",
]

INTENT_STATES = [
    "new_intent",
    "active_intent",
    "queued_intent",
    "deferred_intent",
    "conflicting_intent",
    "completed_intent",
    "abandoned_intent",
]

INTENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "new_intent": {
        "aliases": ["new", "yeni", "fresh", "just_added"],
        "intent_status": "new_intent",
        "intent_health": "pass",
        "intent_summary": "New user intent detected. Intent captured and queued for processing.",
        "health_score": 0.92,
        "risk_score": 0.08,
        "intent_clarity": 0.88,
        "priority_carry_over": 0.0,
        "recommended_actions": ["process_intent", "clarify_if_needed"],
        "recommended_next_action": "new intent — queued for processing",
    },
    "active_intent": {
        "aliases": ["active", "aktif", "in_progress", "current"],
        "intent_status": "active_intent",
        "intent_health": "pass",
        "intent_summary": "Active user intent being executed. Primary goal tracked. Progress maintained.",
        "health_score": 0.88,
        "risk_score": 0.12,
        "intent_clarity": 0.85,
        "priority_carry_over": 0.0,
        "recommended_actions": ["continue_execution", "track_progress"],
        "recommended_next_action": "active intent — continuing execution",
    },
    "queued_intent": {
        "aliases": ["queued", "siralanmis", "pending", "bekleyen"],
        "intent_status": "queued_intent",
        "intent_health": "pass",
        "intent_summary": "Queued user intent. Waiting for execution. Priority tracked.",
        "health_score": 0.84,
        "risk_score": 0.16,
        "intent_clarity": 0.82,
        "priority_carry_over": 0.0,
        "recommended_actions": ["maintain_queue", "monitor_priority"],
        "recommended_next_action": "queued intent — awaiting execution slot",
    },
    "deferred_intent": {
        "aliases": ["deferred", "ertelenmis", "postponed", "later"],
        "intent_status": "deferred_intent",
        "intent_health": "warning",
        "intent_summary": "User intent deferred. Context preserved. Intent tracked for future resumption.",
        "health_score": 0.72,
        "risk_score": 0.30,
        "intent_clarity": 0.78,
        "priority_carry_over": 0.15,
        "recommended_actions": ["keep_for_resumption", "review_when_possible"],
        "recommended_next_action": "deferred — preserved for future resumption",
    },
    "conflicting_intent": {
        "aliases": ["conflicting", "catisan", "contradictory", "overlapping"],
        "intent_status": "conflicting_intent",
        "intent_health": "degraded",
        "intent_summary": "Conflicting user intents detected. Original goal may need reconciliation.",
        "health_score": 0.52,
        "risk_score": 0.58,
        "intent_clarity": 0.45,
        "priority_carry_over": 0.30,
        "recommended_actions": ["reconcile_intents", "clarify_with_user"],
        "recommended_next_action": "conflicting — reconciliation required",
    },
    "completed_intent": {
        "aliases": ["completed", "tamamlanmis", "done", "bitti", "achieved"],
        "intent_status": "completed_intent",
        "intent_health": "pass",
        "intent_summary": "User intent completed successfully. Goal achieved. Results available.",
        "health_score": 0.94,
        "risk_score": 0.06,
        "intent_clarity": 0.95,
        "priority_carry_over": 0.0,
        "recommended_actions": ["present_results", "confirm_with_user"],
        "recommended_next_action": "completed — results available for user",
    },
    "abandoned_intent": {
        "aliases": ["abandoned", "terk_edilmis", "cancelled", "iptal"],
        "intent_status": "abandoned_intent",
        "intent_health": "warning",
        "intent_summary": "User intent abandoned or superseded. Original goal no longer active.",
        "health_score": 0.65,
        "risk_score": 0.35,
        "intent_clarity": 0.60,
        "priority_carry_over": 0.20,
        "recommended_actions": ["archive_intent", "note_superseding_request"],
        "recommended_next_action": "abandoned — superseded by newer intent",
    },
}

# ---------- internal helpers ----------


def _select_intent_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in INTENT_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "new_intent"


def _compute_intent_analysis(pid: str) -> Dict[str, Any]:
    p = INTENT_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    return {
        "intent_map": {
            "primary_intent": f"primary_{pid}_goal",
            "secondary_intents": (
                [] if health > 0.80
                else ["follow_up_request", "additional_command"]
            ),
            "added_commands": (
                [] if health > 0.70
                else ["command_1", "command_2"]
            ),
            "deferred_requests": (
                [] if health > 0.75
                else ["future_request_1"]
            ),
            "future_requests": (
                [] if health > 0.85
                else ["planned_enhancement"]
            ),
        },
        "intent_priority": "low" if health > 0.80 else (
            "medium" if health > 0.50 else "high"
        ),
        "intent_confidence": round(health * 0.85, 2),
        "read_only": True,
        "preview_only": True,
    }


def _compute_priority_shift(pid: str) -> Dict[str, Any]:
    p = INTENT_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    carry_over = p.get("priority_carry_over", 0.0)

    shift_score = round(carry_over + (1.0 - health) * 0.3, 2)
    return {
        "priority_shift_score": shift_score,
        "priority_summary": (
            "no_priority_changes_detected" if shift_score < 0.15
            else "minor_priority_adjustments" if shift_score < 0.40
            else "significant_priority_shift_detected"
        ),
        "recommended_focus": (
            "maintain_current_focus" if shift_score < 0.15
            else "review_priority_changes" if shift_score < 0.40
            else "reassess_user_priorities"
        ),
        "priority_changes": shift_score > 0.15,
        "goal_changes": shift_score > 0.30,
        "scope_changes": shift_score > 0.45,
        "user_focus_changes": shift_score > 0.20,
        "read_only": True,
        "preview_only": True,
    }


def _compute_command_analysis(pid: str) -> Dict[str, Any]:
    p = INTENT_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    return {
        "command_queue_health": "healthy" if health > 0.70 else (
            "degraded" if health > 0.40 else "critical"
        ),
        "command_priority": "low" if health > 0.80 else (
            "medium" if health > 0.50 else "high"
        ),
        "command_summary": (
            "no_additional_commands" if health > 0.80
            else "additional_commands_tracked"
        ),
        "added_commands": 0 if health > 0.80 else 2,
        "queued_commands": 0 if health > 0.75 else 1,
        "future_commands": 0 if health > 0.85 else 1,
        "post_task_commands": 0 if health > 0.90 else 1,
        "read_only": True,
        "preview_only": True,
    }


def _compute_reconciliation(pid: str) -> Dict[str, Any]:
    p = INTENT_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    return {
        "reconciliation_summary": (
            "no_reconciliation_needed" if health > 0.80
            else "minor_reconciliation_required" if health > 0.50
            else "full_reconciliation_required"
        ),
        "continuity_risk": "low" if health > 0.70 else (
            "medium" if health > 0.40 else "high"
        ),
        "recommended_resolution": (
            "none_required" if health > 0.80
            else "review_and_align" if health > 0.50
            else "user_clarification_required"
        ),
        "conflicting_requests": health < 0.60,
        "changed_goals": health < 0.55,
        "updated_priorities": health < 0.50,
        "interrupted_tasks": health < 0.45,
        "read_only": True,
        "preview_only": True,
    }


def _compute_intent_score(pid: str) -> Dict[str, float]:
    p = INTENT_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    clarity = p.get("intent_clarity", 0.50)

    intent_clarity = round(clarity * 0.9, 2)
    intent_continuity = round(health * 0.85, 2)
    intent_alignment = round(clarity * health, 2)
    priority_health = round(health * 0.75, 2)
    overall = round(
        (intent_clarity * 0.25 + intent_continuity * 0.25 + intent_alignment * 0.25 + priority_health * 0.25), 2
    )
    return {
        "intent_clarity": intent_clarity,
        "intent_continuity": intent_continuity,
        "intent_alignment": intent_alignment,
        "intent_priority_health": priority_health,
        "overall_intent_score": overall,
    }


# ---------- public entry points ----------


def user_intent_continuity_intelligence_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "36.5",
        "name": "Engineering Brain User Intent Continuity Intelligence Preview",
        "status": "user_intent_continuity_ready",
        "version": "1.0",
        "capabilities": USER_INTENT_CAPABILITIES,
        "pipeline": INTENT_PIPELINE,
        "intent_states": INTENT_STATES,
        "intent_profile_count": len(INTENT_PROFILES),
        "operation_mode": "read_only_preview_only",
        "core_concept": "intent_is_a_first_class_engineering_object",
        "connected_layers": ["36.4", "36.3", "36.2", "36.1", "36.0"],
        "available_endpoints": [
            "/intent-continuity/status",
            "/intent-continuity/capabilities",
            "/intent-continuity/preview",
            "/intent-continuity/intent-analysis",
            "/intent-continuity/priority-analysis",
            "/intent-continuity/command-analysis",
            "/intent-continuity/reconciliation",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "intent_execution": False,
        "command_execution": False,
        "goal_modification": False,
        "deployment_execution": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only user intent continuity preview. No intent or command execution performed.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def user_intent_continuity_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "36.5",
        "name": "User Intent Continuity Capabilities",
        "status": "intent_capabilities_ready",
        "capabilities": [
            {"name": "intent_tracking", "description": "Track user intent as a first-class engineering object", "read_only": True},
            {"name": "intent_history_analysis", "description": "Analyze the history of user intents and their evolution", "read_only": True},
            {"name": "intent_change_detection", "description": "Detect changes in user intent over time", "read_only": True},
            {"name": "priority_shift_detection", "description": "Detect shifts in user priorities and focus", "read_only": True},
            {"name": "added_command_tracking", "description": "Track commands added during execution", "read_only": True},
            {"name": "deferred_intent_tracking", "description": "Track deferred intents for future resumption", "read_only": True},
            {"name": "goal_continuity_analysis", "description": "Analyze continuity of user goals across changes", "read_only": True},
            {"name": "intent_conflict_detection", "description": "Detect conflicts between different user intents", "read_only": True},
            {"name": "intent_reconciliation", "description": "Reconcile conflicting or changed user intents", "read_only": True},
            {"name": "intent_summary_generation", "description": "Generate comprehensive intent summary", "read_only": True},
            {"name": "intent_health_analysis", "description": "Analyze intent health and clarity", "read_only": True},
            {"name": "intent_priority_engine", "description": "Engine for user intent priority management", "read_only": True},
        ],
        "pipeline": INTENT_PIPELINE,
        "intent_states": INTENT_STATES,
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def user_intent_continuity_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_intent_profile(target_issue, command, project_area)
    p = INTENT_PROFILES[pid]
    score = _compute_intent_score(pid)
    intent = _compute_intent_analysis(pid)

    return {
        "intent_id": pid,
        "intent_status": p["intent_status"],
        "intent_health": p["intent_health"],
        "intent_summary": p.get("intent_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "intent_score": score,
        "intent_analysis": intent,
        "intent_clarity": p.get("intent_clarity"),
        "priority_carry_over": p.get("priority_carry_over"),
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_stage": "user_request_detection",
        "pipeline_progress": {
            "completed": [],
            "current": "user_request_detection",
            "remaining": INTENT_PIPELINE[1:],
        },
        "read_only": True,
        "preview_only": True,
    }


def user_intent_continuity_intelligence_intent_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_intent_profile(target_issue)
    intent = _compute_intent_analysis(pid)
    score = _compute_intent_score(pid)

    return {
        "intent_analysis": intent,
        "intent_score": score,
        "pipeline_stage": "intent_tracking",
        "read_only": True,
        "preview_only": True,
    }


def user_intent_continuity_intelligence_priority_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_intent_profile(target_issue)
    priority = _compute_priority_shift(pid)
    score = _compute_intent_score(pid)

    return {
        "priority_analysis": priority,
        "intent_score": score,
        "pipeline_stage": "priority_analysis",
        "read_only": True,
        "preview_only": True,
    }


def user_intent_continuity_intelligence_command_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_intent_profile(target_issue)
    command = _compute_command_analysis(pid)
    score = _compute_intent_score(pid)

    return {
        "command_analysis": command,
        "intent_score": score,
        "pipeline_stage": "intent_extraction",
        "read_only": True,
        "preview_only": True,
    }


def user_intent_continuity_intelligence_reconciliation(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_intent_profile(target_issue)
    reconciliation = _compute_reconciliation(pid)
    score = _compute_intent_score(pid)

    return {
        "reconciliation_analysis": reconciliation,
        "intent_score": score,
        "pipeline_stage": "intent_reconciliation",
        "read_only": True,
        "preview_only": True,
    }


def user_intent_continuity_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for iid, i in INTENT_PROFILES.items():
        items.append({
            "intent_id": iid,
            "intent_status": i["intent_status"],
            "intent_health": i["intent_health"],
            "health_score": i.get("health_score"),
            "risk_score": i.get("risk_score"),
            "intent_clarity": i.get("intent_clarity"),
            "priority_carry_over": i.get("priority_carry_over"),
        })
    return {
        "layer": "36.5",
        "name": "User Intent Continuity Registry",
        "status": "intent_registry_ready",
        "read_only": True,
        "preview_only": True,
        "intent_profile_count": len(items),
        "intent_profiles": items,
        "pass_count": sum(1 for i in items if i["intent_health"] == "pass"),
        "warning_count": sum(1 for i in items if i["intent_health"] == "warning"),
        "degraded_count": sum(1 for i in items if i["intent_health"] == "degraded"),
        "critical_count": sum(1 for i in items if i["intent_health"] == "critical"),
        "avg_clarity": round(
            sum(i.get("intent_clarity", 0) for i in items) / max(1, len(items)), 2
        ),
    }
