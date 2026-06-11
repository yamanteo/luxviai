from __future__ import annotations

from typing import Any, Dict, List, Optional

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
from engineering_self_reflection_meta_intelligence_preview import (
    engineering_meta_intelligence_registry,
)
from luxcode_core_status_snapshot import (
    luxcode_core_status_snapshot,
)


MULTI_SESSION_CAPABILITIES = [
    "session_continuity_tracking",
    "workspace_transition_analysis",
    "project_transition_analysis",
    "task_transition_analysis",
    "continuity_snapshot_generation",
    "resume_chain_generation",
    "cross_session_context_analysis",
    "continuity_risk_detection",
    "continuity_health_analysis",
    "continuity_summary_generation",
    "resume_recommendation_engine",
    "transition_reconciliation",
]

CONTINUITY_PIPELINE = [
    "session_detection",
    "workspace_analysis",
    "project_analysis",
    "task_analysis",
    "continuity_snapshot",
    "resume_chain_generation",
    "transition_validation",
    "continuity_summary",
]

CONTINUITY_STATES = [
    "active_session",
    "paused_session",
    "switched_session",
    "interrupted_session",
    "recovering_session",
    "resumed_session",
    "completed_session",
]

CONTINUITY_PROFILES: Dict[str, Dict[str, Any]] = {
    "active_session": {
        "aliases": ["active", "aktif", "current", "running", "devam_eden"],
        "continuity_status": "active_session",
        "continuity_health": "pass",
        "continuity_summary": "Active session with full continuity. All context preserved. Engineering thread intact.",
        "health_score": 0.94,
        "risk_score": 0.06,
        "session_id": "session_active",
        "continuity_confidence": 0.95,
        "recommended_actions": ["continue_work", "maintain_continuity"],
        "recommended_next_action": "active session — continuing engineering thread",
    },
    "paused_session": {
        "aliases": ["paused", "duraklatilmis", "on_hold", "bekleyen"],
        "continuity_status": "paused_session",
        "continuity_health": "pass",
        "continuity_summary": "Session paused. Full continuity snapshot preserved. Ready to resume.",
        "health_score": 0.88,
        "risk_score": 0.12,
        "session_id": "session_paused",
        "continuity_confidence": 0.90,
        "recommended_actions": ["resume_session", "verify_snapshot"],
        "recommended_next_action": "paused — full continuity snapshot ready",
    },
    "switched_session": {
        "aliases": ["switched", "degistirilmis", "tab_change", "workspace_change"],
        "continuity_status": "switched_session",
        "continuity_health": "warning",
        "continuity_summary": "Session switched. Previous context preserved. Resume chain available for return.",
        "health_score": 0.76,
        "risk_score": 0.28,
        "session_id": "session_switched",
        "continuity_confidence": 0.75,
        "recommended_actions": ["switch_back_when_ready", "review_chain"],
        "recommended_next_action": "switched — resume chain available",
    },
    "interrupted_session": {
        "aliases": ["interrupted", "yarida_kalmis", "broken", "cut_off"],
        "continuity_status": "interrupted_session",
        "continuity_health": "degraded",
        "continuity_summary": "Session interrupted. Partial continuity preserved. Recovery snapshot available.",
        "health_score": 0.55,
        "risk_score": 0.50,
        "session_id": "session_interrupted",
        "continuity_confidence": 0.50,
        "recommended_actions": ["restore_from_snapshot", "verify_context"],
        "recommended_next_action": "interrupted — restore continuity from snapshot",
    },
    "recovering_session": {
        "aliases": ["recovering", "kurtarilan", "restoring", "geri_yuklenen"],
        "continuity_status": "recovering_session",
        "continuity_health": "degraded",
        "continuity_summary": "Session recovering. Continuity restoration in progress. Chain reconstruction active.",
        "health_score": 0.48,
        "risk_score": 0.58,
        "session_id": "session_recovering",
        "continuity_confidence": 0.40,
        "recommended_actions": ["complete_recovery", "validate_chain"],
        "recommended_next_action": "recovering — continuity chain reconstruction",
    },
    "resumed_session": {
        "aliases": ["resumed", "devam_eden", "continued", "restarted"],
        "continuity_status": "resumed_session",
        "continuity_health": "pass",
        "continuity_summary": "Session resumed successfully. Continuity restored. Engineering thread re-established.",
        "health_score": 0.85,
        "risk_score": 0.15,
        "session_id": "session_resumed",
        "continuity_confidence": 0.85,
        "recommended_actions": ["verify_continuity", "continue_work"],
        "recommended_next_action": "resumed — engineering thread re-established",
    },
    "completed_session": {
        "aliases": ["completed", "tamamlanmis", "finished", "done", "bitti"],
        "continuity_status": "completed_session",
        "continuity_health": "pass",
        "continuity_summary": "Session completed. Full continuity archive available. No resume needed.",
        "health_score": 0.96,
        "risk_score": 0.04,
        "session_id": "session_completed",
        "continuity_confidence": 1.0,
        "recommended_actions": ["archive_snapshot", "review_summary"],
        "recommended_next_action": "completed — continuity archived",
    },
}

# ---------- internal helpers ----------


def _select_continuity_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in CONTINUITY_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "active_session"


def _compute_snapshot(pid: str) -> Dict[str, Any]:
    p = CONTINUITY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    return {
        "snapshot_summary": f"Session continuity snapshot for {pid}. Health: {health:.2f}. Context preserved.",
        "snapshot_confidence": round(health * 0.85, 2),
        "snapshot_completeness": "full" if health > 0.75 else (
            "partial" if health > 0.40 else "minimal"
        ),
        "workspace_snapshot": "available" if health > 0.60 else "degraded",
        "project_snapshot": "available" if health > 0.65 else "degraded",
        "task_snapshot": "available" if health > 0.70 else "degraded",
        "execution_snapshot": "available" if health > 0.60 else "degraded",
        "read_only": True,
        "preview_only": True,
    }


def _compute_resume_chain(pid: str) -> Dict[str, Any]:
    p = CONTINUITY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    return {
        "resume_order": [
            "restore_workspace_context",
            "restore_project_state",
            "restore_task_position",
            "restore_execution_state",
        ],
        "resume_dependencies": (
            [] if health > 0.70
            else ["context_reconstruction_required"]
        ),
        "resume_requirements": (
            "none" if health > 0.80
            else "snapshot_restoration_required" if health > 0.50
            else "full_continuity_rebuild_required"
        ),
        "resume_priority": "immediate" if health > 0.80 else (
            "high" if health > 0.50 else "critical"
        ),
        "resume_chain": f"chain_{pid}_ready" if health > 0.50 else "chain_degraded",
        "resume_confidence": round(health * 0.80, 2),
        "resume_complexity": "simple" if health > 0.80 else (
            "moderate" if health > 0.50 else "complex"
        ),
        "read_only": True,
        "preview_only": True,
    }


def _compute_transition_analysis(pid: str) -> Dict[str, Any]:
    p = CONTINUITY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    return {
        "transition_summary": f"Transition analysis for {pid}. Risk level: {'low' if health > 0.70 else 'medium' if health > 0.40 else 'high'}.",
        "continuity_risk": "low" if health > 0.70 else (
            "medium" if health > 0.40 else "high"
        ),
        "recommended_recovery": (
            "no_recovery_needed" if health > 0.80
            else "snapshot_based_recovery" if health > 0.50
            else "full_continuity_restoration"
        ),
        "workspace_changes": "tracked" if health > 0.60 else "unknown",
        "project_changes": "tracked" if health > 0.65 else "unknown",
        "task_changes": "tracked" if health > 0.70 else "unknown",
        "context_changes": "tracked" if health > 0.60 else "unknown",
        "read_only": True,
        "preview_only": True,
    }


def _compute_multi_session_score(pid: str) -> Dict[str, float]:
    p = CONTINUITY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    continuity = round(health * 0.85, 2)
    resume = round(health * 0.75, 2)
    snapshot = round(health * 0.80, 2)
    transition = round(health * 0.70, 2)
    overall = round(
        (continuity * 0.30 + resume * 0.25 + snapshot * 0.25 + transition * 0.20), 2
    )
    return {
        "continuity_score": continuity,
        "resume_score": resume,
        "snapshot_score": snapshot,
        "transition_score": transition,
        "overall_multi_session_score": overall,
    }


# ---------- public entry points ----------


def multi_session_continuity_intelligence_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "36.4",
        "name": "Engineering Brain Multi-Session Continuity Intelligence Preview",
        "status": "multi_session_continuity_ready",
        "version": "1.0",
        "capabilities": MULTI_SESSION_CAPABILITIES,
        "pipeline": CONTINUITY_PIPELINE,
        "continuity_states": CONTINUITY_STATES,
        "continuity_profile_count": len(CONTINUITY_PROFILES),
        "operation_mode": "read_only_preview_only",
        "core_mission": "never_lose_the_engineering_thread_across_sessions",
        "connected_layers": ["36.3", "36.2", "36.1", "36.0", "35.9"],
        "available_endpoints": [
            "/multi-session/status",
            "/multi-session/capabilities",
            "/multi-session/preview",
            "/multi-session/snapshot",
            "/multi-session/resume-chain",
            "/multi-session/transition-analysis",
            "/multi-session/continuity-health",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "session_restore": False,
        "workspace_restore": False,
        "task_restore": False,
        "execution_restore": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only multi-session continuity preview. No real session restoration performed.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def multi_session_continuity_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "36.4",
        "name": "Multi-Session Continuity Capabilities",
        "status": "continuity_capabilities_ready",
        "capabilities": [
            {"name": "session_continuity_tracking", "description": "Track continuity across session boundaries", "read_only": True},
            {"name": "workspace_transition_analysis", "description": "Analyze workspace transitions for continuity impact", "read_only": True},
            {"name": "project_transition_analysis", "description": "Analyze project transitions for continuity impact", "read_only": True},
            {"name": "task_transition_analysis", "description": "Analyze task transitions for continuity impact", "read_only": True},
            {"name": "continuity_snapshot_generation", "description": "Generate continuity snapshots for future resumption", "read_only": True},
            {"name": "resume_chain_generation", "description": "Generate resume chains for ordered restoration", "read_only": True},
            {"name": "cross_session_context_analysis", "description": "Analyze context across session boundaries", "read_only": True},
            {"name": "continuity_risk_detection", "description": "Detect continuity risks during transitions", "read_only": True},
            {"name": "continuity_health_analysis", "description": "Analyze continuity health across sessions", "read_only": True},
            {"name": "continuity_summary_generation", "description": "Generate comprehensive continuity summary", "read_only": True},
            {"name": "resume_recommendation_engine", "description": "Generate resume recommendations based on continuity state", "read_only": True},
            {"name": "transition_reconciliation", "description": "Reconcile transitions across workspace, project, task, and context changes", "read_only": True},
        ],
        "pipeline": CONTINUITY_PIPELINE,
        "continuity_states": CONTINUITY_STATES,
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def multi_session_continuity_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_continuity_profile(target_issue, command, project_area)
    p = CONTINUITY_PROFILES[pid]
    score = _compute_multi_session_score(pid)
    snapshot = _compute_snapshot(pid)

    return {
        "continuity_id": pid,
        "continuity_status": p["continuity_status"],
        "continuity_health": p["continuity_health"],
        "continuity_summary": p.get("continuity_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "multi_session_score": score,
        "snapshot_analysis": snapshot,
        "session_id": p.get("session_id"),
        "continuity_confidence": p.get("continuity_confidence"),
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_stage": "session_detection",
        "pipeline_progress": {
            "completed": [],
            "current": "session_detection",
            "remaining": CONTINUITY_PIPELINE[1:],
        },
        "read_only": True,
        "preview_only": True,
    }


def multi_session_continuity_intelligence_snapshot(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_continuity_profile(target_issue)
    snapshot = _compute_snapshot(pid)
    score = _compute_multi_session_score(pid)

    return {
        "continuity_snapshot": snapshot,
        "multi_session_score": score,
        "pipeline_stage": "continuity_snapshot",
        "read_only": True,
        "preview_only": True,
    }


def multi_session_continuity_intelligence_resume_chain(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_continuity_profile(target_issue)
    chain = _compute_resume_chain(pid)
    score = _compute_multi_session_score(pid)

    return {
        "resume_chain": chain,
        "multi_session_score": score,
        "pipeline_stage": "resume_chain_generation",
        "read_only": True,
        "preview_only": True,
    }


def multi_session_continuity_intelligence_transition_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_continuity_profile(target_issue)
    transition = _compute_transition_analysis(pid)
    score = _compute_multi_session_score(pid)

    return {
        "transition_analysis": transition,
        "multi_session_score": score,
        "pipeline_stage": "transition_validation",
        "read_only": True,
        "preview_only": True,
    }


def multi_session_continuity_intelligence_continuity_health(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_continuity_profile(target_issue)
    score = _compute_multi_session_score(pid)
    snapshot = _compute_snapshot(pid)
    chain = _compute_resume_chain(pid)
    transition = _compute_transition_analysis(pid)

    return {
        "continuity_health": score,
        "snapshot_analysis": snapshot,
        "resume_chain": chain,
        "transition_analysis": transition,
        "pipeline_stage": "continuity_summary",
        "read_only": True,
        "preview_only": True,
    }


def multi_session_continuity_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for cid, c in CONTINUITY_PROFILES.items():
        items.append({
            "continuity_id": cid,
            "continuity_status": c["continuity_status"],
            "continuity_health": c["continuity_health"],
            "health_score": c.get("health_score"),
            "risk_score": c.get("risk_score"),
            "continuity_confidence": c.get("continuity_confidence"),
        })
    return {
        "layer": "36.4",
        "name": "Multi-Session Continuity Registry",
        "status": "continuity_registry_ready",
        "read_only": True,
        "preview_only": True,
        "continuity_profile_count": len(items),
        "continuity_profiles": items,
        "pass_count": sum(1 for i in items if i["continuity_health"] == "pass"),
        "warning_count": sum(1 for i in items if i["continuity_health"] == "warning"),
        "degraded_count": sum(1 for i in items if i["continuity_health"] == "degraded"),
        "critical_count": sum(1 for i in items if i["continuity_health"] == "critical"),
        "avg_continuity_confidence": round(
            sum(i.get("continuity_confidence", 0) for i in items) / max(1, len(items)), 2
        ),
    }
