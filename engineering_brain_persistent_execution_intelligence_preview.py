from __future__ import annotations

from typing import Any, Dict, List, Optional

from engineering_brain_task_consciousness_preview import (
    task_consciousness_intelligence_registry,
)
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
from luxcode_core_status_snapshot import (
    luxcode_core_status_snapshot,
)


PERSISTENT_EXECUTION_CAPABILITIES = [
    "execution_state_tracking",
    "persistent_context_tracking",
    "resume_point_generation",
    "pause_state_management",
    "stop_state_management",
    "execution_recovery_analysis",
    "continuation_planning",
    "follow_up_reconciliation",
    "interruption_handling",
    "execution_summary_generation",
    "continuity_health_analysis",
    "persistent_execution_scoring",
]

EXECUTION_PIPELINE = [
    "execution_start",
    "context_tracking",
    "progress_tracking",
    "interruption_detection",
    "state_preservation",
    "resume_point_generation",
    "continuation_planning",
    "execution_recovery",
]

EXECUTION_STATES = [
    "running",
    "paused",
    "stopped",
    "waiting_for_input",
    "queued",
    "recovering",
    "resuming",
    "completed",
]

EXECUTION_PROFILES: Dict[str, Dict[str, Any]] = {
    "running": {
        "aliases": ["running", "calisiyor", "active", "in_progress"],
        "execution_status": "running",
        "execution_health": "pass",
        "execution_summary": "Execution running. Context tracked. Progress monitored. State stable.",
        "health_score": 0.92,
        "risk_score": 0.08,
        "continuity_score": 0.95,
        "resume_confidence": 0.90,
        "recommended_actions": ["continue_execution", "maintain_context"],
        "recommended_next_action": "running — continuing execution normally",
    },
    "paused": {
        "aliases": ["paused", "durakladi", "on_hold", "beklemede"],
        "execution_status": "paused",
        "execution_health": "pass",
        "execution_summary": "Execution paused. Context fully preserved. Ready to resume at any time.",
        "health_score": 0.85,
        "risk_score": 0.15,
        "continuity_score": 0.88,
        "resume_confidence": 0.92,
        "recommended_actions": ["resume_execution", "verify_context"],
        "recommended_next_action": "paused — ready to resume with preserved context",
    },
    "stopped": {
        "aliases": ["stopped", "durdu", "ended", "terminated"],
        "execution_status": "stopped",
        "execution_health": "warning",
        "execution_summary": "Execution stopped. Context partially preserved. Resume may require context restoration.",
        "health_score": 0.68,
        "risk_score": 0.32,
        "continuity_score": 0.60,
        "resume_confidence": 0.55,
        "recommended_actions": ["assess_context_state", "restore_if_needed"],
        "recommended_next_action": "stopped — assess context state before resuming",
    },
    "waiting_for_input": {
        "aliases": ["waiting", "bekliyor", "awaiting_input", "user_input"],
        "execution_status": "waiting_for_input",
        "execution_health": "pass",
        "execution_summary": "Execution waiting for user input. Context preserved. Will resume when input received.",
        "health_score": 0.82,
        "risk_score": 0.18,
        "continuity_score": 0.85,
        "resume_confidence": 0.88,
        "recommended_actions": ["await_input", "maintain_context"],
        "recommended_next_action": "waiting for input — context preserved",
    },
    "queued": {
        "aliases": ["queued", "siralanmis", "pending", "scheduled"],
        "execution_status": "queued",
        "execution_health": "pass",
        "execution_summary": "Execution queued. Will start when resources available. Queue position maintained.",
        "health_score": 0.88,
        "risk_score": 0.12,
        "continuity_score": 0.90,
        "resume_confidence": 0.85,
        "recommended_actions": ["wait_for_execution", "monitor_queue"],
        "recommended_next_action": "queued — awaiting execution slot",
    },
    "recovering": {
        "aliases": ["recovering", "kurtariliyor", "restoring", "recovery"],
        "execution_status": "recovering",
        "execution_health": "degraded",
        "execution_summary": "Execution recovering. Context restoration in progress. Recovery plan active.",
        "health_score": 0.50,
        "risk_score": 0.55,
        "continuity_score": 0.45,
        "resume_confidence": 0.50,
        "recommended_actions": ["complete_recovery", "verify_integrity"],
        "recommended_next_action": "recovering — context restoration in progress",
    },
    "resuming": {
        "aliases": ["resuming", "devam_ediyor", "continuing", "restarting"],
        "execution_status": "resuming",
        "execution_health": "warning",
        "execution_summary": "Execution resuming. Context loaded. Continuation plan active. Starting recovery position.",
        "health_score": 0.62,
        "risk_score": 0.38,
        "continuity_score": 0.70,
        "resume_confidence": 0.75,
        "recommended_actions": ["complete_resumption", "verify_position"],
        "recommended_next_action": "resuming — context loaded, continuing execution",
    },
    "completed": {
        "aliases": ["completed", "tamamlandi", "finished", "done", "bitti"],
        "execution_status": "completed",
        "execution_health": "pass",
        "execution_summary": "Execution completed successfully. Full context preserved for review. No resume needed.",
        "health_score": 0.95,
        "risk_score": 0.05,
        "continuity_score": 1.0,
        "resume_confidence": 1.0,
        "recommended_actions": ["review_results", "archive_context"],
        "recommended_next_action": "completed — results available for review",
    },
}

# ---------- internal helpers ----------


def _select_execution_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in EXECUTION_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "running"


def _compute_resume_analysis(pid: str) -> Dict[str, Any]:
    p = EXECUTION_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    resume_conf = p.get("resume_confidence", 0.50)

    return {
        "resume_point": {
            "resume_step": f"step_{pid}_continuation",
            "resume_context": p.get("execution_summary"),
            "resume_dependencies": (
                [] if resume_conf > 0.70
                else ["restore_execution_state", "reload_context"]
            ),
            "resume_requirements": (
                "none" if resume_conf > 0.80
                else "context_verification_required" if resume_conf > 0.50
                else "full_state_recovery_required"
            ),
        },
        "resume_confidence": resume_conf,
        "resume_complexity": "simple" if resume_conf > 0.80 else (
            "moderate" if resume_conf > 0.50 else "complex"
        ),
        "read_only": True,
        "preview_only": True,
    }


def _compute_interruption_analysis(pid: str) -> Dict[str, Any]:
    p = EXECUTION_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    continuity = p.get("continuity_score", 0.50)

    return {
        "interruption_summary": (
            "no_interruptions_detected" if health > 0.80
            else f"interruption_detected_in_{pid}_state"
        ),
        "continuation_strategy": (
            "continue_normally" if continuity > 0.80
            else "restore_and_continue" if continuity > 0.50
            else "full_recovery_required"
        ),
        "continuity_score": continuity,
        "user_questions": "handled" if health > 0.70 else "pending",
        "added_commands": "integrated" if health > 0.60 else "queued",
        "follow_ups": "reconciled" if health > 0.70 else "pending_reconciliation",
        "temporary_stops": "preserved" if health > 0.60 else "context_compromised",
        "context_switches": "tracked" if health > 0.70 else "potential_context_loss",
        "read_only": True,
        "preview_only": True,
    }


def _compute_recovery_analysis(pid: str) -> Dict[str, Any]:
    p = EXECUTION_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    continuity = p.get("continuity_score", 0.50)
    resume_conf = p.get("resume_confidence", 0.50)

    can_resume = health > 0.40 and continuity > 0.30
    recovery_plan = (
        "immediate_resume" if continuity > 0.80
        else "context_restoration_required" if continuity > 0.50
        else "full_execution_restart_required"
    )
    return {
        "recovery_analysis": {
            "can_resume": can_resume,
            "recovery_plan": recovery_plan,
            "estimated_recovery_time": "immediate" if continuity > 0.80 else (
                "short" if continuity > 0.50 else "extended"
            ),
        },
        "resume_point": {
            "resume_step": f"step_{pid}",
            "resume_confidence": resume_conf,
            "context_available": continuity > 0.40,
        },
        "recommended_next_action": (
            "resume_execution" if can_resume
            else "initiate_full_recovery"
        ),
        "read_only": True,
        "preview_only": True,
    }


def _compute_state_summary(pid: str) -> Dict[str, Any]:
    p = EXECUTION_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    continuity = p.get("continuity_score", 0.50)

    return {
        "current_state": pid,
        "state_health": p.get("execution_health"),
        "supported_transitions": {
            "running": ["paused", "waiting_for_input", "completed"],
            "paused": ["running", "stopped"],
            "stopped": ["recovering"],
            "waiting_for_input": ["running", "paused"],
            "queued": ["running", "completing"],
            "recovering": ["resuming", "completed"],
            "resuming": ["running", "completed"],
            "completed": ["running"],
        }.get(pid, []),
        "continuity_score": continuity,
        "execution_health": round(health * 0.85, 2),
        "can_resume_from_here": pid in ("paused", "waiting_for_input", "stopped", "recovering"),
        "read_only": True,
        "preview_only": True,
    }


def _compute_persistent_score(pid: str) -> Dict[str, float]:
    p = EXECUTION_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    continuity = p.get("continuity_score", 0.50)

    continuity_score = round(continuity * 0.95, 2)
    recovery_score = round(health * 0.70, 2)
    resume_score = round(health * 0.80, 2)
    exec_health = round(health * 0.85, 2)
    overall = round(
        (continuity_score * 0.30 + recovery_score * 0.25 + resume_score * 0.25 + exec_health * 0.20), 2
    )
    return {
        "continuity_score": continuity_score,
        "recovery_score": recovery_score,
        "resume_score": resume_score,
        "execution_health": exec_health,
        "overall_persistent_execution_score": overall,
    }


# ---------- public entry points ----------


def persistent_execution_intelligence_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "36.3",
        "name": "Engineering Brain Persistent Execution Intelligence Preview",
        "status": "persistent_execution_ready",
        "version": "1.0",
        "capabilities": PERSISTENT_EXECUTION_CAPABILITIES,
        "pipeline": EXECUTION_PIPELINE,
        "execution_states": EXECUTION_STATES,
        "execution_profile_count": len(EXECUTION_PROFILES),
        "operation_mode": "read_only_preview_only",
        "core_mission": "never_lose_position_never_lose_context_never_lose_progress",
        "connected_layers": ["36.2", "36.1", "36.0", "35.9", "35.8"],
        "available_endpoints": [
            "/persistent-execution/status",
            "/persistent-execution/capabilities",
            "/persistent-execution/preview",
            "/persistent-execution/resume-analysis",
            "/persistent-execution/interruption-analysis",
            "/persistent-execution/recovery-analysis",
            "/persistent-execution/state-summary",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "execution_resume": False,
        "execution_restart": False,
        "task_execution": False,
        "deployment_execution": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only persistent execution preview. No real execution recovery performed.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def persistent_execution_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "36.3",
        "name": "Persistent Execution Capabilities",
        "status": "persistent_capabilities_ready",
        "capabilities": [
            {"name": "execution_state_tracking", "description": "Track execution state across all transitions", "read_only": True},
            {"name": "persistent_context_tracking", "description": "Track context persistently across interruptions", "read_only": True},
            {"name": "resume_point_generation", "description": "Generate resume points for seamless continuation", "read_only": True},
            {"name": "pause_state_management", "description": "Manage pause states with full context preservation", "read_only": True},
            {"name": "stop_state_management", "description": "Manage stop states with context recovery options", "read_only": True},
            {"name": "execution_recovery_analysis", "description": "Analyze execution recovery requirements", "read_only": True},
            {"name": "continuation_planning", "description": "Plan continuation strategies after interruptions", "read_only": True},
            {"name": "follow_up_reconciliation", "description": "Reconcile follow-up items after execution transitions", "read_only": True},
            {"name": "interruption_handling", "description": "Handle user questions, commands, context switches during execution", "read_only": True},
            {"name": "execution_summary_generation", "description": "Generate comprehensive execution summary", "read_only": True},
            {"name": "continuity_health_analysis", "description": "Analyze continuity health across execution lifecycle", "read_only": True},
            {"name": "persistent_execution_scoring", "description": "Score persistent execution health across all dimensions", "read_only": True},
        ],
        "pipeline": EXECUTION_PIPELINE,
        "execution_states": EXECUTION_STATES,
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def persistent_execution_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_execution_profile(target_issue, command, project_area)
    p = EXECUTION_PROFILES[pid]
    score = _compute_persistent_score(pid)
    resume = _compute_resume_analysis(pid)

    return {
        "execution_id": pid,
        "execution_status": p["execution_status"],
        "execution_health": p["execution_health"],
        "execution_summary": p.get("execution_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "persistent_score": score,
        "resume_analysis": resume,
        "continuity_score": p.get("continuity_score"),
        "resume_confidence": p.get("resume_confidence"),
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_stage": "execution_start",
        "pipeline_progress": {
            "completed": [],
            "current": "execution_start",
            "remaining": EXECUTION_PIPELINE[1:],
        },
        "read_only": True,
        "preview_only": True,
    }


def persistent_execution_intelligence_resume_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_execution_profile(target_issue)
    resume = _compute_resume_analysis(pid)
    score = _compute_persistent_score(pid)

    return {
        "resume_analysis": resume,
        "persistent_score": score,
        "pipeline_stage": "resume_point_generation",
        "read_only": True,
        "preview_only": True,
    }


def persistent_execution_intelligence_interruption_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_execution_profile(target_issue)
    interruption = _compute_interruption_analysis(pid)
    score = _compute_persistent_score(pid)

    return {
        "interruption_analysis": interruption,
        "persistent_score": score,
        "pipeline_stage": "interruption_detection",
        "read_only": True,
        "preview_only": True,
    }


def persistent_execution_intelligence_recovery_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_execution_profile(target_issue)
    recovery = _compute_recovery_analysis(pid)
    score = _compute_persistent_score(pid)

    return {
        "recovery_analysis": recovery,
        "persistent_score": score,
        "pipeline_stage": "execution_recovery",
        "read_only": True,
        "preview_only": True,
    }


def persistent_execution_intelligence_state_summary(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_execution_profile(target_issue)
    state = _compute_state_summary(pid)
    score = _compute_persistent_score(pid)
    recovery = _compute_recovery_analysis(pid)

    return {
        "state_summary": state,
        "recovery_analysis": recovery,
        "persistent_score": score,
        "pipeline_stage": "state_preservation",
        "read_only": True,
        "preview_only": True,
    }


def persistent_execution_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for eid, e in EXECUTION_PROFILES.items():
        items.append({
            "execution_id": eid,
            "execution_status": e["execution_status"],
            "execution_health": e["execution_health"],
            "health_score": e.get("health_score"),
            "risk_score": e.get("risk_score"),
            "continuity_score": e.get("continuity_score"),
            "resume_confidence": e.get("resume_confidence"),
        })
    return {
        "layer": "36.3",
        "name": "Persistent Execution Registry",
        "status": "persistent_registry_ready",
        "read_only": True,
        "preview_only": True,
        "execution_profile_count": len(items),
        "execution_profiles": items,
        "pass_count": sum(1 for i in items if i["execution_health"] == "pass"),
        "warning_count": sum(1 for i in items if i["execution_health"] == "warning"),
        "degraded_count": sum(1 for i in items if i["execution_health"] == "degraded"),
        "critical_count": sum(1 for i in items if i["execution_health"] == "critical"),
        "avg_continuity": round(
            sum(i.get("continuity_score", 0) for i in items) / max(1, len(items)), 2
        ),
        "avg_resume_confidence": round(
            sum(i.get("resume_confidence", 0) for i in items) / max(1, len(items)), 2
        ),
    }
