from __future__ import annotations

from typing import Any, Dict, List, Optional

from engineering_autonomy_intelligence_preview import (
    engineering_autonomy_intelligence_registry,
)
from engineering_strategy_intelligence_preview import (
    engineering_strategy_intelligence_registry,
)
from engineering_prediction_forecast_intelligence_preview import (
    engineering_forecast_intelligence_registry,
)
from engineering_observability_monitoring_preview import (
    engineering_monitoring_intelligence_registry,
)
from engineering_decision_intelligence_preview import (
    engineering_decision_intelligence_registry,
)
from engineering_knowledge_graph_intelligence_preview import (
    engineering_graph_intelligence_registry,
)
from engineering_memory_failure_intelligence_preview import (
    engineering_memory_intelligence_registry,
)
from autonomous_engineering_coordinator_preview import (
    autonomous_engineering_coordinator_registry,
)
from engineering_self_reflection_meta_intelligence_preview import (
    engineering_meta_intelligence_registry,
)
from luxcode_core_status_snapshot import (
    luxcode_core_status_snapshot,
)


ENGINEERING_BRAIN_CAPABILITIES = [
    "engineering_reasoning",
    "engineering_planning",
    "engineering_coordination",
    "engineering_reflection",
    "engineering_prediction",
    "engineering_strategy",
    "engineering_memory_access",
    "engineering_graph_access",
    "engineering_risk_analysis",
    "engineering_summary_generation",
    "engineering_recommendation_generation",
    "engineering_health_analysis",
]

BRAIN_PIPELINE = [
    "task_intake",
    "context_collection",
    "memory_analysis",
    "knowledge_graph_analysis",
    "decision_analysis",
    "forecast_analysis",
    "strategy_generation",
    "autonomy_review",
    "meta_review",
    "engineering_recommendation",
]

BRAIN_STATES = [
    "idle",
    "observing",
    "analyzing",
    "planning",
    "reasoning",
    "reviewing",
    "recommending",
    "blocked",
    "recovery",
]

BRAIN_COMPONENTS = {
    "coordinator": "35.1",
    "memory": "35.2",
    "knowledge_graph": "35.3",
    "decision": "35.4",
    "monitoring": "35.5",
    "forecast": "35.6",
    "strategy": "35.7",
    "autonomy": "35.8",
    "meta": "35.9",
}

BRAIN_PROFILES: Dict[str, Dict[str, Any]] = {
    "idle": {
        "aliases": ["idle", "bos", "waiting", "ready", "hazir"],
        "brain_status": "idle",
        "brain_health": "pass",
        "brain_summary": "Engineering brain idle. All subsystems nominal. Ready for task intake.",
        "health_score": 0.96,
        "risk_score": 0.04,
        "active_component": None,
        "pipeline_stage": "idle",
        "recommended_actions": ["await_task", "maintain_readiness"],
        "recommended_next_action": "idle — awaiting engineering task",
        "brain_signals": {
            "all_subsystems_healthy": True,
            "active_reasoning": False,
            "pending_recommendation": False,
        },
    },
    "observing": {
        "aliases": ["observing", "gozlem", "watching", "monitoring"],
        "brain_status": "observing",
        "brain_health": "pass",
        "brain_summary": "Engineering brain observing. Monitoring and monitoring intelligence active. Collecting context.",
        "health_score": 0.90,
        "risk_score": 0.10,
        "active_component": "monitoring",
        "pipeline_stage": "context_collection",
        "recommended_actions": ["continue_observation", "collect_context"],
        "recommended_next_action": "observing — collecting engineering context",
        "brain_signals": {
            "all_subsystems_healthy": True,
            "active_reasoning": False,
            "pending_recommendation": False,
        },
    },
    "analyzing": {
        "aliases": ["analyzing", "analiz", "examining", "inceleme"],
        "brain_status": "analyzing",
        "brain_health": "pass",
        "brain_summary": "Engineering brain analyzing. Memory and knowledge graph access active. Patterns and relationships being evaluated.",
        "health_score": 0.85,
        "risk_score": 0.15,
        "active_component": "memory",
        "pipeline_stage": "memory_analysis",
        "recommended_actions": ["continue_analysis", "evaluate_patterns"],
        "recommended_next_action": "analyzing — memory and graph analysis in progress",
        "brain_signals": {
            "all_subsystems_healthy": True,
            "active_reasoning": True,
            "pending_recommendation": False,
        },
    },
    "planning": {
        "aliases": ["planning", "planlama", "strategizing", "coordinating"],
        "brain_status": "planning",
        "brain_health": "warning",
        "brain_summary": "Engineering brain planning. Decision, forecast, and strategy intelligence active. Multiple paths under evaluation.",
        "health_score": 0.78,
        "risk_score": 0.22,
        "active_component": "decision",
        "pipeline_stage": "strategy_generation",
        "recommended_actions": ["evaluate_strategies", "assess_risks"],
        "recommended_next_action": "planning — strategy evaluation in progress",
        "brain_signals": {
            "all_subsystems_healthy": True,
            "active_reasoning": True,
            "pending_recommendation": False,
        },
    },
    "reasoning": {
        "aliases": ["reasoning", "akil_yurutme", "thinking", "dusunme"],
        "brain_status": "reasoning",
        "brain_health": "warning",
        "brain_summary": "Engineering brain reasoning. Meta intelligence active. Self-reflection and consistency analysis in progress.",
        "health_score": 0.72,
        "risk_score": 0.30,
        "active_component": "meta",
        "pipeline_stage": "meta_review",
        "recommended_actions": ["complete_reasoning", "validate_consistency"],
        "recommended_next_action": "reasoning — meta review in progress",
        "brain_signals": {
            "all_subsystems_healthy": True,
            "active_reasoning": True,
            "pending_recommendation": False,
        },
    },
    "reviewing": {
        "aliases": ["reviewing", "gozden_gecirme", "checking", "kontrol"],
        "brain_status": "reviewing",
        "brain_health": "warning",
        "brain_summary": "Engineering brain reviewing. Autonomy and meta intelligence active. Safety and boundary validation in progress.",
        "health_score": 0.68,
        "risk_score": 0.35,
        "active_component": "autonomy",
        "pipeline_stage": "autonomy_review",
        "recommended_actions": ["validate_safety", "check_boundaries"],
        "recommended_next_action": "reviewing — autonomy and boundary validation",
        "brain_signals": {
            "all_subsystems_healthy": True,
            "active_reasoning": True,
            "pending_recommendation": False,
        },
    },
    "recommending": {
        "aliases": ["recommending", "tavsiye", "suggesting", "onerme"],
        "brain_status": "recommending",
        "brain_health": "pass",
        "brain_summary": "Engineering brain recommending. All analysis complete. Recommendation ready for review.",
        "health_score": 0.88,
        "risk_score": 0.12,
        "active_component": "coordinator",
        "pipeline_stage": "engineering_recommendation",
        "recommended_actions": ["review_recommendation", "prepare_delivery"],
        "recommended_next_action": "recommendation ready — review and act",
        "brain_signals": {
            "all_subsystems_healthy": True,
            "active_reasoning": False,
            "pending_recommendation": True,
        },
    },
    "blocked": {
        "aliases": ["blocked", "engellendi", "stuck", "takildi"],
        "brain_status": "blocked",
        "brain_health": "critical",
        "brain_summary": "Engineering brain blocked. Critical issue detected in one or more subsystems. Resolution required.",
        "health_score": 0.25,
        "risk_score": 0.85,
        "active_component": "unknown",
        "pipeline_stage": "blocked",
        "recommended_actions": ["diagnose_blocker", "resolve_issue"],
        "recommended_next_action": "blocked — diagnose and resolve",
        "brain_signals": {
            "all_subsystems_healthy": False,
            "active_reasoning": False,
            "pending_recommendation": False,
        },
    },
    "recovery": {
        "aliases": ["recovery", "kurtarma", "restore", "rebuild"],
        "brain_status": "recovery",
        "brain_health": "degraded",
        "brain_summary": "Engineering brain in recovery. Previous workflow interrupted. Restoration in progress.",
        "health_score": 0.38,
        "risk_score": 0.72,
        "active_component": "recovery",
        "pipeline_stage": "recovery",
        "recommended_actions": ["restore_state", "verify_integrity"],
        "recommended_next_action": "recovery — restoring engineering brain state",
        "brain_signals": {
            "all_subsystems_healthy": False,
            "active_reasoning": False,
            "pending_recommendation": False,
        },
    },
}

# ---------- internal helpers ----------


def _select_brain_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in BRAIN_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "idle"


def _compute_brain_health(pid: str) -> Dict[str, Any]:
    p = BRAIN_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)

    meta_reg = engineering_meta_intelligence_registry()
    autonomy_reg = engineering_autonomy_intelligence_registry()
    strategy_reg = engineering_strategy_intelligence_registry()
    forecast_reg = engineering_forecast_intelligence_registry()
    monitoring_reg = engineering_monitoring_intelligence_registry()
    decision_reg = engineering_decision_intelligence_registry()
    graph_reg = engineering_graph_intelligence_registry()
    memory_reg = engineering_memory_intelligence_registry()
    coord_reg = autonomous_engineering_coordinator_registry()

    subsystem_statuses = {
        "coordinator": coord_reg.get("status") == "coordinator_registry_ready",
        "memory": memory_reg.get("status") == "memory_registry_ready",
        "graph": graph_reg.get("status") == "graph_registry_ready",
        "decision": decision_reg.get("status") == "decision_registry_ready",
        "monitoring": monitoring_reg.get("status") == "monitoring_registry_ready",
        "forecast": forecast_reg.get("status") == "forecast_registry_ready",
        "strategy": strategy_reg.get("status") == "strategy_registry_ready",
        "autonomy": autonomy_reg.get("status") == "autonomy_registry_ready",
        "meta": meta_reg.get("status") == "meta_registry_ready",
    }
    healthy_count = sum(1 for v in subsystem_statuses.values() if v)
    total_count = len(subsystem_statuses)

    brain_health_val = round(health * 0.3 + (healthy_count / max(1, total_count)) * 0.7, 2)
    brain_confidence = round(brain_health_val * 0.9, 2)
    brain_risk = round(1.0 - brain_health_val, 2)

    return {
        "engineering_brain_health": "healthy" if brain_health_val > 0.70 else (
            "degraded" if brain_health_val > 0.40 else "critical"
        ),
        "engineering_brain_confidence": brain_confidence,
        "engineering_brain_risk": brain_risk,
        "subsystem_health": subsystem_statuses,
        "healthy_subsystem_count": healthy_count,
        "total_subsystem_count": total_count,
        "read_only": True,
        "preview_only": True,
    }


def _compute_brain_reasoning(pid: str) -> Dict[str, Any]:
    p = BRAIN_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    return {
        "reasoning_active": p.get("brain_signals", {}).get("active_reasoning", False),
        "reasoning_quality": "high" if health > 0.80 else (
            "medium" if health > 0.50 else "low"
        ),
        "reasoning_stage": p.get("pipeline_stage"),
        "active_component": p.get("active_component"),
        "components_involved": [
            comp for comp in BRAIN_COMPONENTS
            if health > 0.50 or comp == p.get("active_component")
        ],
        "read_only": True,
        "preview_only": True,
    }


def _compute_brain_planning(pid: str) -> Dict[str, Any]:
    p = BRAIN_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    return {
        "planning_stage": p.get("pipeline_stage"),
        "remaining_stages": BRAIN_PIPELINE[BRAIN_PIPELINE.index(p.get("pipeline_stage")) + 1:]
        if p.get("pipeline_stage") in BRAIN_PIPELINE else BRAIN_PIPELINE,
        "planning_confidence": round(health * 0.75, 2),
        "estimated_completion": "immediate" if health > 0.80 else (
            "short_term" if health > 0.50 else "extended"
        ),
        "read_only": True,
        "preview_only": True,
    }


def _compute_brain_recommendation(pid: str) -> Dict[str, Any]:
    p = BRAIN_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)

    return {
        "brain_summary": p.get("brain_summary"),
        "brain_confidence": round(health * 0.85, 2),
        "brain_reasoning": f"Brain state: {p.get('brain_status')}. "
                          f"Health: {health:.2f}, Risk: {risk:.2f}. "
                          f"Active component: {p.get('active_component', 'none')}.",
        "recommended_action": (
            "proceed_with_engineering_plan" if health > 0.70
            else "review_and_mitigate_risks" if health > 0.40
            else "do_not_proceed_resolve_issues"
        ),
        "recommended_strategy": "balanced" if health > 0.70 else (
            "conservative" if health > 0.40 else "recovery"
        ),
        "recommended_verification": "standard" if health > 0.70 else (
            "extended" if health > 0.40 else "full"
        ),
        "recommended_next_step": p.get("recommended_next_action"),
        "recommended_priority": "low" if health > 0.80 else (
            "medium" if health > 0.50 else "high"
        ),
        "read_only": True,
        "preview_only": True,
    }


def _compute_brain_score(pid: str) -> Dict[str, float]:
    p = BRAIN_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)

    reasoning_score = round(health * 0.80, 2)
    planning_score = round(health * 0.75, 2)
    strategy_score = round(health * 0.70 - risk * 0.1, 2)
    consistency_score = round(health * 0.85, 2)
    overall = round(
        (reasoning_score * 0.25 + planning_score * 0.25 + strategy_score * 0.25 + consistency_score * 0.25), 2
    )
    return {
        "reasoning_score": reasoning_score,
        "planning_score": planning_score,
        "strategy_score": strategy_score,
        "consistency_score": consistency_score,
        "engineering_brain_score": overall,
    }


# ---------- public entry points ----------


def luxcode_engineering_brain_core_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "36.0",
        "name": "LuxCode Engineering Brain Core Preview",
        "status": "engineering_brain_core_ready",
        "version": "1.0",
        "capabilities": ENGINEERING_BRAIN_CAPABILITIES,
        "pipeline": BRAIN_PIPELINE,
        "brain_states": BRAIN_STATES,
        "brain_components": BRAIN_COMPONENTS,
        "brain_profile_count": len(BRAIN_PROFILES),
        "operation_mode": "read_only_preview_only",
        "convergence_note": "first_major_convergence_layer_unifying_35.1_through_35.9",
        "connected_layers": ["35.9", "35.8", "35.7", "35.6", "35.5", "35.4", "35.3", "35.2", "35.1"],
        "available_endpoints": [
            "/engineering-brain/status",
            "/engineering-brain/capabilities",
            "/engineering-brain/preview",
            "/engineering-brain/reasoning",
            "/engineering-brain/planning",
            "/engineering-brain/recommendation",
            "/engineering-brain/health",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "brain_execution": False,
        "repair_execution": False,
        "deployment_execution": False,
        "verification_execution": False,
        "autonomous_actions": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only engineering brain core preview. All outputs advisory only. No autonomous actions permitted.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def luxcode_engineering_brain_core_capabilities() -> Dict[str, Any]:
    return {
        "layer": "36.0",
        "name": "Engineering Brain Core Capabilities",
        "status": "brain_capabilities_ready",
        "capabilities": [
            {"name": "engineering_reasoning", "description": "Unified engineering reasoning across all intelligence subsystems", "read_only": True},
            {"name": "engineering_planning", "description": "Engineering planning across the entire brain pipeline", "read_only": True},
            {"name": "engineering_coordination", "description": "Coordinate across all 9 engineering intelligence components", "read_only": True},
            {"name": "engineering_reflection", "description": "Reflect on engineering reasoning, decisions, and strategies", "read_only": True},
            {"name": "engineering_prediction", "description": "Predict outcomes and risks through unified forecast access", "read_only": True},
            {"name": "engineering_strategy", "description": "Generate and evaluate engineering strategies", "read_only": True},
            {"name": "engineering_memory_access", "description": "Access engineering memory and failure patterns", "read_only": True},
            {"name": "engineering_graph_access", "description": "Access knowledge graph relationships and dependencies", "read_only": True},
            {"name": "engineering_risk_analysis", "description": "Comprehensive risk analysis across all intelligence dimensions", "read_only": True},
            {"name": "engineering_summary_generation", "description": "Generate unified engineering brain summary", "read_only": True},
            {"name": "engineering_recommendation_generation", "description": "Generate unified engineering recommendations", "read_only": True},
            {"name": "engineering_health_analysis", "description": "Analyze health across all 9 engineering brain components", "read_only": True},
        ],
        "pipeline": BRAIN_PIPELINE,
        "brain_states": BRAIN_STATES,
        "brain_components": BRAIN_COMPONENTS,
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def luxcode_engineering_brain_core_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_brain_profile(target_issue, command, project_area)
    p = BRAIN_PROFILES[pid]
    health = _compute_brain_health(pid)
    score = _compute_brain_score(pid)
    recommendation = _compute_brain_recommendation(pid)

    return {
        "brain_id": pid,
        "brain_status": p["brain_status"],
        "brain_health": p["brain_health"],
        "brain_summary": p.get("brain_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "active_component": p.get("active_component"),
        "pipeline_stage": p.get("pipeline_stage"),
        "engineering_health": health,
        "brain_score": score,
        "brain_recommendation": recommendation,
        "brain_signals": p.get("brain_signals", {}),
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_progress": {
            "completed": BRAIN_PIPELINE[:BRAIN_PIPELINE.index(p.get("pipeline_stage"))]
            if p.get("pipeline_stage") in BRAIN_PIPELINE else [],
            "current": p.get("pipeline_stage"),
            "remaining": BRAIN_PIPELINE[BRAIN_PIPELINE.index(p.get("pipeline_stage")) + 1:]
            if p.get("pipeline_stage") in BRAIN_PIPELINE else BRAIN_PIPELINE,
        },
        "read_only": True,
        "preview_only": True,
    }


def luxcode_engineering_brain_core_reasoning(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_brain_profile(target_issue)
    reasoning = _compute_brain_reasoning(pid)
    score = _compute_brain_score(pid)
    health = _compute_brain_health(pid)

    return {
        "brain_reasoning": reasoning,
        "brain_score": score,
        "engineering_health": health,
        "pipeline_stage": "reasoning",
        "read_only": True,
        "preview_only": True,
    }


def luxcode_engineering_brain_core_planning(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_brain_profile(target_issue)
    planning = _compute_brain_planning(pid)
    score = _compute_brain_score(pid)
    health = _compute_brain_health(pid)

    return {
        "brain_planning": planning,
        "brain_score": score,
        "engineering_health": health,
        "pipeline_stage": "planning",
        "read_only": True,
        "preview_only": True,
    }


def luxcode_engineering_brain_core_recommendation(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_brain_profile(target_issue)
    recommendation = _compute_brain_recommendation(pid)
    score = _compute_brain_score(pid)
    health = _compute_brain_health(pid)

    return {
        "brain_recommendation": recommendation,
        "brain_score": score,
        "engineering_health": health,
        "pipeline_stage": "engineering_recommendation",
        "read_only": True,
        "preview_only": True,
    }


def luxcode_engineering_brain_core_health(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_brain_profile(target_issue)
    health = _compute_brain_health(pid)
    score = _compute_brain_score(pid)
    reasoning = _compute_brain_reasoning(pid)
    planning = _compute_brain_planning(pid)

    return {
        "engineering_health": health,
        "brain_score": score,
        "brain_reasoning": reasoning,
        "brain_planning": planning,
        "pipeline_stage": "context_collection",
        "read_only": True,
        "preview_only": True,
    }


def luxcode_engineering_brain_core_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for bid, b in BRAIN_PROFILES.items():
        items.append({
            "brain_id": bid,
            "brain_status": b["brain_status"],
            "brain_health": b["brain_health"],
            "health_score": b.get("health_score"),
            "risk_score": b.get("risk_score"),
            "pipeline_stage": b.get("pipeline_stage"),
            "active_component": b.get("active_component"),
        })
    return {
        "layer": "36.0",
        "name": "Engineering Brain Core Registry",
        "status": "brain_registry_ready",
        "read_only": True,
        "preview_only": True,
        "brain_profile_count": len(items),
        "brain_profiles": items,
        "brain_components": BRAIN_COMPONENTS,
        "pass_count": sum(1 for i in items if i["brain_health"] == "pass"),
        "warning_count": sum(1 for i in items if i["brain_health"] == "warning"),
        "degraded_count": sum(1 for i in items if i["brain_health"] == "degraded"),
        "critical_count": sum(1 for i in items if i["brain_health"] == "critical"),
    }
