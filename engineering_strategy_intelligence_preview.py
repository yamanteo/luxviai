from __future__ import annotations

from typing import Any, Dict, List, Optional

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
from deployment_verification_intelligence_preview import (
    deployment_verification_intelligence_registry,
)
# clone_workspace_intelligence_registry not used in this file
from verification_intelligence_preview import (
    verification_intelligence_registry,
)
from autonomous_repair_intelligence_preview import (
    autonomous_repair_intelligence_registry,
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


ENGINEERING_STRATEGY_CAPABILITIES = [
    "strategy_generation",
    "strategy_comparison",
    "long_term_planning",
    "engineering_roadmap_generation",
    "risk_aware_planning",
    "resource_strategy_analysis",
    "dependency_strategy_analysis",
    "verification_strategy_analysis",
    "deployment_strategy_analysis",
    "alternative_strategy_generation",
    "strategy_summary_generation",
    "strategy_health_analysis",
]

STRATEGY_PIPELINE = [
    "current_state_analysis",
    "historical_review",
    "knowledge_graph_review",
    "forecast_review",
    "risk_analysis",
    "strategy_generation",
    "roadmap_planning",
    "recommended_path",
]

STRATEGY_PROFILES: Dict[str, Dict[str, Any]] = {
    "short_term_strategy": {
        "aliases": ["short_term", "kisa_vade", "immediate", "acil", "tactical"],
        "strategy_status": "short_term_strategy",
        "strategy_health": "pass",
        "strategy_summary": "Short-term tactical strategy. Focus on immediate improvements and quick wins. Lower risk, faster execution.",
        "health_score": 0.90,
        "risk_score": 0.10,
        "planning_horizon": "1-4 weeks",
        "strategy_type": "tactical",
        "recommended_actions": ["immediate_execution", "quick_wins"],
        "recommended_next_action": "short-term tactical — execute immediate improvements",
    },
    "balanced_strategy": {
        "aliases": ["balanced", "dengeli", "moderate", "mixed"],
        "strategy_status": "balanced_strategy",
        "strategy_health": "pass",
        "strategy_summary": "Balanced strategy with mix of tactical and strategic actions. Sustainable pace with moderate risk.",
        "health_score": 0.82,
        "risk_score": 0.20,
        "planning_horizon": "1-3 months",
        "strategy_type": "balanced",
        "recommended_actions": ["balance_short_and_long_term", "sustainable_pacing"],
        "recommended_next_action": "balanced — execute tactical and strategic actions",
    },
    "growth_strategy": {
        "aliases": ["growth", "buyume", "expansion", "genisleme", "ambitious"],
        "strategy_status": "growth_strategy",
        "strategy_health": "warning",
        "strategy_summary": "Growth-oriented strategy focusing on expansion and capability building. Higher risk, higher reward potential.",
        "health_score": 0.72,
        "risk_score": 0.32,
        "planning_horizon": "3-6 months",
        "strategy_type": "growth",
        "recommended_actions": ["invest_in_capabilities", "expand_coverage", "build_long_term_assets"],
        "recommended_next_action": "growth — invest in capability expansion",
    },
    "stability_strategy": {
        "aliases": ["stability", "istikrar", "safe", "guvenli", "defensive"],
        "strategy_status": "stability_strategy",
        "strategy_health": "warning",
        "strategy_summary": "Stability-focused strategy prioritizing risk reduction and system hardening. Lower risk, slower change.",
        "health_score": 0.65,
        "risk_score": 0.38,
        "planning_horizon": "2-4 months",
        "strategy_type": "defensive",
        "recommended_actions": ["harden_systems", "reduce_technical_debt", "improve_reliability"],
        "recommended_next_action": "stability — focus on hardening and risk reduction",
    },
    "recovery_strategy": {
        "aliases": ["recovery", "kurtarma", "restore", "rebuild", "recovery_mode"],
        "strategy_status": "recovery_strategy",
        "strategy_health": "degraded",
        "strategy_summary": "Recovery strategy focused on restoring system health. Priorities: stabilize, recover, then optimize.",
        "health_score": 0.45,
        "risk_score": 0.65,
        "planning_horizon": "1-2 months",
        "strategy_type": "recovery",
        "recommended_actions": ["stabilize_systems", "recover_functionality", "plan_long_term_fixes"],
        "recommended_next_action": "recovery — stabilize and recover before optimization",
    },
    "high_uncertainty_strategy": {
        "aliases": ["uncertain", "belirsiz", "unknown", "exploratory"],
        "strategy_status": "high_uncertainty_strategy",
        "strategy_health": "critical",
        "strategy_summary": "High uncertainty strategy. Insufficient data for confident planning. Exploration and learning recommended before commitment.",
        "health_score": 0.30,
        "risk_score": 0.80,
        "planning_horizon": "unknown",
        "strategy_type": "exploratory",
        "recommended_actions": ["gather_data", "run_exploration", "reduce_uncertainty"],
        "recommended_next_action": "high uncertainty — gather data before strategic commitment",
    },
}

# ---------- internal helpers ----------


def _select_strategy_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in STRATEGY_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "balanced_strategy"


def _compute_roadmap(pid: str) -> Dict[str, Any]:
    p = STRATEGY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    horizon = p.get("planning_horizon", "unknown")

    confidence = round(health * 0.8, 2)
    risk = round(1.0 - confidence, 2)

    return {
        "roadmap": {
            "immediate_actions": [
                "assess_current_system_state",
                "identify_quick_wins",
                "stabilize_critical_paths",
            ],
            "short_term_actions": [
                "implement_priority_fixes",
                "run_verification_pipeline",
                "update_documentation",
            ],
            "mid_term_actions": [
                "expand_test_coverage",
                "reduce_technical_debt",
                "improve_monitoring",
            ],
            "long_term_actions": [
                "architectural_improvements",
                "automation_expansion",
                "capability_building",
            ],
        },
        "roadmap_confidence": confidence,
        "roadmap_risk": risk,
        "planning_horizon": horizon,
        "read_only": True,
        "preview_only": True,
    }


def _compute_strategy_comparison(pid: str) -> Dict[str, Any]:
    strategies = list(STRATEGY_PROFILES.keys())
    scores = {s: STRATEGY_PROFILES[s].get("health_score", 0.50) for s in strategies}
    best = max(scores, key=scores.get)

    return {
        "best_strategy": best,
        "alternative_strategies": [s for s in strategies if s != best],
        "comparison_score": round(scores[best], 2),
        "strategy_scores": scores,
        "read_only": True,
        "preview_only": True,
    }


def _compute_risk_aware_strategy(pid: str) -> Dict[str, Any]:
    p = STRATEGY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)

    weighted = round(health * 0.6 + (1.0 - risk) * 0.4, 2)
    return {
        "risk_weighted_strategy": p.get("strategy_type", "unknown"),
        "risk_summary": "low_risk_strategy" if risk < 0.25 else (
            "moderate_risk_strategy" if risk < 0.50 else (
                "high_risk_strategy" if risk < 0.75 else "critical_risk_strategy"
            )
        ),
        "technical_risk": round(risk * 0.8, 2),
        "verification_risk": round(risk * 0.6, 2),
        "deployment_risk": round(risk * 0.7, 2),
        "dependency_risk": round(risk * 0.5, 2),
        "maintenance_risk": round(risk * 0.4, 2),
        "risk_weighted_score": weighted,
        "read_only": True,
        "preview_only": True,
    }


def _compute_strategy_score(pid: str) -> Dict[str, float]:
    p = STRATEGY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)

    confidence = round(health * 0.85, 2)
    strategy_risk = round(1.0 - confidence, 2)
    roadmap_score = round(health * 0.75, 2)
    readiness = round(health * 0.8 - risk * 0.1, 2)
    overall = round(
        (confidence * 0.3 + (1.0 - strategy_risk) * 0.2 + roadmap_score * 0.25 + readiness * 0.25), 2
    )
    return {
        "strategy_confidence": confidence,
        "strategy_risk": strategy_risk,
        "roadmap_score": roadmap_score,
        "execution_readiness": readiness,
        "overall_strategy_score": overall,
    }


# ---------- public entry points ----------


def engineering_strategy_intelligence_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "35.7",
        "name": "Engineering Strategy Intelligence Preview",
        "status": "engineering_strategy_ready",
        "version": "1.0",
        "capabilities": ENGINEERING_STRATEGY_CAPABILITIES,
        "pipeline": STRATEGY_PIPELINE,
        "strategy_profile_count": len(STRATEGY_PROFILES),
        "operation_mode": "read_only_preview_only",
        "core_principle": "advisory_only_no_automatic_execution",
        "connected_layers": ["35.6", "35.5", "35.4", "35.3", "35.2", "35.1"],
        "available_endpoints": [
            "/engineering-strategy/status",
            "/engineering-strategy/capabilities",
            "/engineering-strategy/preview",
            "/engineering-strategy/generate",
            "/engineering-strategy/compare",
            "/engineering-strategy/roadmap",
            "/engineering-strategy/risk-analysis",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "strategy_execution": False,
        "repair_execution": False,
        "deployment_execution": False,
        "verification_execution": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only engineering strategy preview. All outputs advisory only. No automatic execution permitted.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def engineering_strategy_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "35.7",
        "name": "Engineering Strategy Capabilities",
        "status": "strategy_capabilities_ready",
        "capabilities": [
            {"name": "strategy_generation", "description": "Generate optimal engineering strategy based on state, history, graph, and forecasts", "read_only": True},
            {"name": "strategy_comparison", "description": "Compare multiple strategies and identify the best approach", "read_only": True},
            {"name": "long_term_planning", "description": "Plan engineering activities across multiple time horizons", "read_only": True},
            {"name": "engineering_roadmap_generation", "description": "Generate engineering roadmap with immediate to long-term actions", "read_only": True},
            {"name": "risk_aware_planning", "description": "Plan with risk-weighting across technical, verification, deployment, dependency, maintenance dimensions", "read_only": True},
            {"name": "resource_strategy_analysis", "description": "Analyze resource requirements and constraints for strategies", "read_only": True},
            {"name": "dependency_strategy_analysis", "description": "Analyze dependency implications of different strategies", "read_only": True},
            {"name": "verification_strategy_analysis", "description": "Analyze verification requirements for different strategies", "read_only": True},
            {"name": "deployment_strategy_analysis", "description": "Analyze deployment implications of different strategies", "read_only": True},
            {"name": "alternative_strategy_generation", "description": "Generate alternative strategies for consideration", "read_only": True},
            {"name": "strategy_summary_generation", "description": "Generate comprehensive strategy summary", "read_only": True},
            {"name": "strategy_health_analysis", "description": "Analyze strategy health and viability", "read_only": True},
        ],
        "pipeline": STRATEGY_PIPELINE,
        "strategy_profiles": list(STRATEGY_PROFILES.keys()),
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def engineering_strategy_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_strategy_profile(target_issue, command, project_area)
    p = STRATEGY_PROFILES[pid]
    score = _compute_strategy_score(pid)
    roadmap = _compute_roadmap(pid)

    return {
        "strategy_id": pid,
        "strategy_status": p["strategy_status"],
        "strategy_health": p["strategy_health"],
        "strategy_summary": p.get("strategy_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "planning_horizon": p.get("planning_horizon"),
        "strategy_type": p.get("strategy_type"),
        "strategy_score": score,
        "roadmap": roadmap,
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_stage": "strategy_generation",
        "pipeline_progress": {
            "completed": ["current_state_analysis", "historical_review", "knowledge_graph_review", "forecast_review", "risk_analysis"],
            "current": "strategy_generation",
            "remaining": STRATEGY_PIPELINE[6:],
        },
        "read_only": True,
        "preview_only": True,
    }


def engineering_strategy_intelligence_generate(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_strategy_profile(target_issue)
    p = STRATEGY_PROFILES.get(pid, {})
    score = _compute_strategy_score(pid)
    roadmap = _compute_roadmap(pid)

    return {
        "selected_strategy": {
            "strategy_id": pid,
            "strategy_type": p.get("strategy_type"),
            "planning_horizon": p.get("planning_horizon"),
            "health_score": p.get("health_score"),
        },
        "strategy_score": score,
        "roadmap": roadmap,
        "pipeline_stage": "recommended_path",
        "read_only": True,
        "preview_only": True,
    }


def engineering_strategy_intelligence_compare(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_strategy_profile(target_issue)
    comparison = _compute_strategy_comparison(pid)
    score = _compute_strategy_score(pid)

    return {
        "strategy_comparison": comparison,
        "strategy_score": score,
        "pipeline_stage": "strategy_generation",
        "read_only": True,
        "preview_only": True,
    }


def engineering_strategy_intelligence_roadmap(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_strategy_profile(target_issue)
    roadmap = _compute_roadmap(pid)
    score = _compute_strategy_score(pid)

    return {
        "roadmap": roadmap,
        "strategy_score": score,
        "pipeline_stage": "roadmap_planning",
        "read_only": True,
        "preview_only": True,
    }


def engineering_strategy_intelligence_risk_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_strategy_profile(target_issue)
    risk = _compute_risk_aware_strategy(pid)
    score = _compute_strategy_score(pid)

    return {
        "risk_analysis": risk,
        "strategy_score": score,
        "pipeline_stage": "risk_analysis",
        "read_only": True,
        "preview_only": True,
    }


def engineering_strategy_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for sid, s in STRATEGY_PROFILES.items():
        items.append({
            "strategy_id": sid,
            "strategy_status": s["strategy_status"],
            "strategy_health": s["strategy_health"],
            "health_score": s.get("health_score"),
            "risk_score": s.get("risk_score"),
            "planning_horizon": s.get("planning_horizon"),
            "strategy_type": s.get("strategy_type"),
        })
    return {
        "layer": "35.7",
        "name": "Engineering Strategy Registry",
        "status": "strategy_registry_ready",
        "read_only": True,
        "preview_only": True,
        "strategy_profile_count": len(items),
        "strategy_profiles": items,
        "pass_count": sum(1 for i in items if i["strategy_health"] == "pass"),
        "warning_count": sum(1 for i in items if i["strategy_health"] == "warning"),
        "degraded_count": sum(1 for i in items if i["strategy_health"] == "degraded"),
        "critical_count": sum(1 for i in items if i["strategy_health"] == "critical"),
        "horizons": list(set(i.get("planning_horizon") for i in items if i.get("planning_horizon"))),
    }
