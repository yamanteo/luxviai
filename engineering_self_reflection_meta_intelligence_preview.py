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
from luxcode_core_status_snapshot import (
    luxcode_core_status_snapshot,
)


ENGINEERING_META_CAPABILITIES = [
    "decision_reflection",
    "strategy_reflection",
    "repair_reflection",
    "verification_reflection",
    "deployment_reflection",
    "autonomy_reflection",
    "meta_reasoning_analysis",
    "alternative_reasoning_generation",
    "confidence_reassessment",
    "reflection_summary_generation",
    "self_consistency_analysis",
    "meta_health_analysis",
]

REFLECTION_PIPELINE = [
    "decision_review",
    "reasoning_review",
    "alternative_review",
    "risk_review",
    "confidence_reassessment",
    "meta_reflection",
    "improvement_suggestions",
]

REFLECTION_PROFILES: Dict[str, Dict[str, Any]] = {
    "high_confidence_reasoning": {
        "aliases": ["high_confidence", "yuksek_guven", "certain", "kesin", "strong"],
        "reflection_status": "high_confidence_reasoning",
        "reflection_health": "pass",
        "reflection_summary": "High confidence reasoning. Decision logic sound. All signals consistent. No significant improvements identified.",
        "health_score": 0.94,
        "risk_score": 0.06,
        "reasoning_quality": "excellent",
        "consistency_score": 0.92,
        "recommended_actions": ["document_reasoning", "proceed_with_confidence"],
        "recommended_next_action": "high confidence — document and proceed",
    },
    "stable_reasoning": {
        "aliases": ["stable", "stabil", "solid", "saglam", "reliable"],
        "reflection_status": "stable_reasoning",
        "reflection_health": "pass",
        "reflection_summary": "Stable reasoning with minor areas for improvement. Core logic sound. Some alternatives worth reviewing.",
        "health_score": 0.85,
        "risk_score": 0.15,
        "reasoning_quality": "good",
        "consistency_score": 0.80,
        "recommended_actions": ["review_alternatives", "document_assumptions"],
        "recommended_next_action": "stable reasoning — review alternatives",
    },
    "alternative_available": {
        "aliases": ["alternative", "alternatif", "option", "secenek"],
        "reflection_status": "alternative_available",
        "reflection_health": "warning",
        "reflection_summary": "Alternative reasoning paths available. Current choice reasonable but other valid options exist. Worth comparing.",
        "health_score": 0.72,
        "risk_score": 0.30,
        "reasoning_quality": "fair",
        "consistency_score": 0.65,
        "recommended_actions": ["compare_alternatives", "weight_tradeoffs"],
        "recommended_next_action": "alternatives available — compare before committing",
    },
    "conflicting_reasoning": {
        "aliases": ["conflicting", "catismali", "contradictory", "tutarsiz"],
        "reflection_status": "conflicting_reasoning",
        "reflection_health": "degraded",
        "reflection_summary": "Conflicting reasoning detected. Different signals point in different directions. Deeper analysis recommended.",
        "health_score": 0.55,
        "risk_score": 0.55,
        "reasoning_quality": "poor",
        "consistency_score": 0.40,
        "recommended_actions": ["resolve_conflicts", "gather_more_data", "rerun_analysis"],
        "recommended_next_action": "conflicting reasoning — resolve before proceeding",
    },
    "uncertain_reasoning": {
        "aliases": ["uncertain", "belirsiz", "unclear", "vague"],
        "reflection_status": "uncertain_reasoning",
        "reflection_health": "degraded",
        "reflection_summary": "Uncertain reasoning with low confidence. Multiple gaps identified. Significant improvement needed before execution.",
        "health_score": 0.40,
        "risk_score": 0.70,
        "reasoning_quality": "poor",
        "consistency_score": 0.30,
        "recommended_actions": ["improve_data_quality", "rerun_analysis", "seek_review"],
        "recommended_next_action": "uncertain reasoning — improve before proceeding",
    },
    "meta_review_required": {
        "aliases": ["meta_review", "meta", "review", "full_review"],
        "reflection_status": "meta_review_required",
        "reflection_health": "critical",
        "reflection_summary": "Meta review required. Significant reasoning gaps or conflicts. Full review of all assumptions and logic recommended.",
        "health_score": 0.25,
        "risk_score": 0.88,
        "reasoning_quality": "critical",
        "consistency_score": 0.15,
        "recommended_actions": ["full_meta_review", "reassess_all_assumptions", "restart_analysis"],
        "recommended_next_action": "meta review required — full reassessment needed",
    },
}

# ---------- internal helpers ----------


def _select_reflection_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in REFLECTION_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "stable_reasoning"


def _compute_meta_reasoning(pid: str) -> Dict[str, Any]:
    p = REFLECTION_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    quality = p.get("reasoning_quality", "fair")

    return {
        "reasoning_summary": f"Reasoning quality: {quality}. "
                             f"Confidence level: {health:.2f}. "
                             f"Review assessment: {'no_major_issues' if health > 0.70 else 'improvements_needed'}.",
        "reasoning_confidence": round(health * 0.85, 2),
        "reasoning_quality": quality,
        "chosen_strategy": "appropriate" if health > 0.70 else (
            "needs_review" if health > 0.40 else "should_be_reconsidered"
        ),
        "alternative_strategies_evaluated": health > 0.50,
        "verification_results_aligned": health > 0.60,
        "risk_analysis_complete": health > 0.50,
        "historical_patterns_considered": health > 0.55,
        "read_only": True,
        "preview_only": True,
    }


def _compute_self_consistency(pid: str) -> Dict[str, Any]:
    p = REFLECTION_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    consistency = p.get("consistency_score", 0.50)

    c_risk = "low" if consistency > 0.70 else ("medium" if consistency > 0.40 else "high")
    return {
        "consistency_score": consistency,
        "consistency_risk": c_risk,
        "recommended_review": "none_required" if consistency > 0.80 else (
            "review_conflicts" if consistency > 0.50 else "full_review_required"
        ),
        "decision_conflicts": consistency < 0.70,
        "strategy_conflicts": consistency < 0.60,
        "memory_conflicts": consistency < 0.50,
        "verification_conflicts": consistency < 0.55,
        "autonomy_conflicts": consistency < 0.65,
        "read_only": True,
        "preview_only": True,
    }


def _compute_alternative_reasoning(pid: str) -> Dict[str, Any]:
    p = REFLECTION_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    alt_conf = round(health * 0.6, 2)
    return {
        "alternative_summary": (
            "Multiple valid alternatives exist" if health > 0.70 else
            "Limited alternatives — current path is optimal" if health > 0.45 else
            "Few alternatives — constraints limit options"
        ),
        "alternative_confidence": alt_conf,
        "alternative_paths": [
            "full_pipeline_approach",
            "minimal_intervention",
            "phased_execution",
        ],
        "alternative_decisions": [
            "proceed_with_current",
            "delay_for_additional_analysis",
            "escalate_to_human",
        ],
        "alternative_strategies": [
            "conservative",
            "balanced",
            "aggressive",
        ] if health > 0.50 else ["conservative"],
        "alternative_priorities": [
            "safety_first",
            "speed_first",
            "quality_first",
        ],
        "read_only": True,
        "preview_only": True,
    }


def _compute_meta_score(pid: str) -> Dict[str, float]:
    p = REFLECTION_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    consistency = p.get("consistency_score", 0.50)

    reflection = round(health * 0.8, 2)
    consistency_score = round(consistency * 0.9, 2)
    reasoning_score = round(health * 0.75, 2)
    improvement = round((1.0 - health) * 0.5, 2)
    overall = round(
        (reflection * 0.25 + consistency_score * 0.25 + reasoning_score * 0.3 + (1.0 - improvement) * 0.2), 2
    )
    return {
        "reflection_score": reflection,
        "consistency_score": consistency_score,
        "reasoning_score": reasoning_score,
        "improvement_score": improvement,
        "overall_meta_score": overall,
    }


# ---------- public entry points ----------


def engineering_meta_intelligence_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "35.9",
        "name": "Engineering Self-Reflection & Meta Intelligence Preview",
        "status": "engineering_meta_ready",
        "version": "1.0",
        "capabilities": ENGINEERING_META_CAPABILITIES,
        "pipeline": REFLECTION_PIPELINE,
        "reflection_profile_count": len(REFLECTION_PROFILES),
        "operation_mode": "read_only_preview_only",
        "core_mission": "evaluate_own_reasoning_not_just_what_but_why",
        "connected_layers": ["35.8", "35.7", "35.6", "35.5", "35.4", "35.3", "35.2", "35.1"],
        "available_endpoints": [
            "/engineering-meta/status",
            "/engineering-meta/capabilities",
            "/engineering-meta/preview",
            "/engineering-meta/reflection",
            "/engineering-meta/reasoning-review",
            "/engineering-meta/consistency-analysis",
            "/engineering-meta/alternative-analysis",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "meta_execution": False,
        "decision_override": False,
        "deployment_execution": False,
        "repair_execution": False,
        "verification_execution": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only meta intelligence preview. All reflections advisory only. No decision overrides permitted.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def engineering_meta_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "35.9",
        "name": "Engineering Meta Intelligence Capabilities",
        "status": "meta_capabilities_ready",
        "capabilities": [
            {"name": "decision_reflection", "description": "Reflect on decisions and evaluate their quality", "read_only": True},
            {"name": "strategy_reflection", "description": "Reflect on strategies and evaluate their effectiveness", "read_only": True},
            {"name": "repair_reflection", "description": "Reflect on repair choices and outcomes", "read_only": True},
            {"name": "verification_reflection", "description": "Reflect on verification approaches and coverage", "read_only": True},
            {"name": "deployment_reflection", "description": "Reflect on deployment decisions and outcomes", "read_only": True},
            {"name": "autonomy_reflection", "description": "Reflect on autonomy level choices and appropriateness", "read_only": True},
            {"name": "meta_reasoning_analysis", "description": "Analyze the quality and completeness of reasoning", "read_only": True},
            {"name": "alternative_reasoning_generation", "description": "Generate alternative reasoning paths and decisions", "read_only": True},
            {"name": "confidence_reassessment", "description": "Reassess confidence in decisions and strategies", "read_only": True},
            {"name": "reflection_summary_generation", "description": "Generate comprehensive reflection summary", "read_only": True},
            {"name": "self_consistency_analysis", "description": "Analyze self-consistency across decisions, strategies, memory, verification, autonomy", "read_only": True},
            {"name": "meta_health_analysis", "description": "Analyze meta intelligence health and effectiveness", "read_only": True},
        ],
        "pipeline": REFLECTION_PIPELINE,
        "reflection_profiles": list(REFLECTION_PROFILES.keys()),
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def engineering_meta_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_reflection_profile(target_issue, command, project_area)
    p = REFLECTION_PROFILES[pid]
    score = _compute_meta_score(pid)
    reasoning = _compute_meta_reasoning(pid)

    return {
        "reflection_id": pid,
        "reflection_status": p["reflection_status"],
        "reflection_health": p["reflection_health"],
        "reflection_summary": p.get("reflection_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "reasoning_quality": p.get("reasoning_quality"),
        "consistency_score": p.get("consistency_score"),
        "meta_score": score,
        "meta_reasoning": reasoning,
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_stage": "decision_review",
        "pipeline_progress": {
            "completed": [],
            "current": "decision_review",
            "remaining": REFLECTION_PIPELINE[1:],
        },
        "read_only": True,
        "preview_only": True,
    }


def engineering_meta_intelligence_reflection(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_reflection_profile(target_issue)
    p = REFLECTION_PROFILES.get(pid, {})
    score = _compute_meta_score(pid)
    reasoning = _compute_meta_reasoning(pid)
    consistency = _compute_self_consistency(pid)

    return {
        "reflection_analysis": {
            "reflection_id": pid,
            "reasoning_quality": p.get("reasoning_quality"),
            "consistency_score": p.get("consistency_score"),
            "improvement_areas": (
                [] if p.get("health_score", 0.50) > 0.80
                else ["consider_alternatives", "validate_assumptions"]
            ),
        },
        "meta_reasoning": reasoning,
        "self_consistency": consistency,
        "meta_score": score,
        "pipeline_stage": "meta_reflection",
        "read_only": True,
        "preview_only": True,
    }


def engineering_meta_intelligence_reasoning_review(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_reflection_profile(target_issue)
    reasoning = _compute_meta_reasoning(pid)
    score = _compute_meta_score(pid)
    alternative = _compute_alternative_reasoning(pid)

    return {
        "reasoning_review": reasoning,
        "alternative_reasoning": alternative,
        "meta_score": score,
        "pipeline_stage": "reasoning_review",
        "read_only": True,
        "preview_only": True,
    }


def engineering_meta_intelligence_consistency_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_reflection_profile(target_issue)
    consistency = _compute_self_consistency(pid)
    score = _compute_meta_score(pid)

    return {
        "consistency_analysis": consistency,
        "meta_score": score,
        "pipeline_stage": "decision_review",
        "read_only": True,
        "preview_only": True,
    }


def engineering_meta_intelligence_alternative_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_reflection_profile(target_issue)
    alternative = _compute_alternative_reasoning(pid)
    score = _compute_meta_score(pid)
    reasoning = _compute_meta_reasoning(pid)

    return {
        "alternative_analysis": alternative,
        "meta_reasoning": reasoning,
        "meta_score": score,
        "pipeline_stage": "alternative_review",
        "read_only": True,
        "preview_only": True,
    }


def engineering_meta_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for rid, r in REFLECTION_PROFILES.items():
        items.append({
            "reflection_id": rid,
            "reflection_status": r["reflection_status"],
            "reflection_health": r["reflection_health"],
            "health_score": r.get("health_score"),
            "risk_score": r.get("risk_score"),
            "reasoning_quality": r.get("reasoning_quality"),
            "consistency_score": r.get("consistency_score"),
        })
    return {
        "layer": "35.9",
        "name": "Engineering Meta Intelligence Registry",
        "status": "meta_registry_ready",
        "read_only": True,
        "preview_only": True,
        "reflection_profile_count": len(items),
        "reflection_profiles": items,
        "pass_count": sum(1 for i in items if i["reflection_health"] == "pass"),
        "warning_count": sum(1 for i in items if i["reflection_health"] == "warning"),
        "degraded_count": sum(1 for i in items if i["reflection_health"] == "degraded"),
        "critical_count": sum(1 for i in items if i["reflection_health"] == "critical"),
        "avg_consistency": round(
            sum(i.get("consistency_score", 0) for i in items) / max(1, len(items)), 2
        ),
    }
