from __future__ import annotations

from typing import Any, Dict, List, Optional

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
from luxcode_core_status_snapshot import (
    luxcode_core_status_snapshot,
)


ENGINEERING_DECISION_CAPABILITIES = [
    "strategy_selection",
    "decision_ranking",
    "path_comparison",
    "risk_weighting",
    "confidence_weighting",
    "repair_decision_analysis",
    "verification_decision_analysis",
    "deployment_decision_analysis",
    "alternative_path_generation",
    "decision_summary_generation",
    "decision_conflict_detection",
    "decision_health_analysis",
]

DECISION_PIPELINE = [
    "problem",
    "analysis",
    "possible_strategies",
    "historical_review",
    "knowledge_graph_review",
    "verification_review",
    "risk_comparison",
    "decision_recommendation",
]

DECISION_PROFILES: Dict[str, Dict[str, Any]] = {
    "clear_decision": {
        "aliases": ["clear", "net", "obvious", "acik", "certain"],
        "decision_status": "clear_decision",
        "decision_health": "pass",
        "decision_summary": "Clear decision path identified. All signals aligned. Preferred strategy recommended with high confidence.",
        "health_score": 0.95,
        "risk_score": 0.05,
        "signal_agreement": 1.0,
        "conflict_count": 0,
        "recommended_actions": ["execute_preferred_strategy", "monitor_execution"],
        "recommended_next_action": "clear decision — execute preferred strategy",
        "decision_signals": {
            "verification_aligned": True,
            "memory_aligned": True,
            "graph_aligned": True,
            "deployment_aligned": True,
        },
    },
    "low_risk_choice": {
        "aliases": ["low_risk", "dusuk_risk", "safe", "guvenli", "conservative"],
        "decision_status": "low_risk_choice",
        "decision_health": "pass",
        "decision_summary": "Low risk decision path available. Minor trade-offs exist. Recommended path is safe and verified.",
        "health_score": 0.88,
        "risk_score": 0.12,
        "signal_agreement": 0.85,
        "conflict_count": 1,
        "recommended_actions": ["recommended_path", "review_alternatives"],
        "recommended_next_action": "low risk choice — follow recommended path",
        "decision_signals": {
            "verification_aligned": True,
            "memory_aligned": True,
            "graph_aligned": True,
            "deployment_aligned": False,
        },
    },
    "balanced_decision": {
        "aliases": ["balanced", "dengeli", "moderate", "orta", "tradeoff"],
        "decision_status": "balanced_decision",
        "decision_health": "warning",
        "decision_summary": "Balanced decision with moderate trade-offs. Multiple viable paths exist. Compare alternatives before committing.",
        "health_score": 0.72,
        "risk_score": 0.32,
        "signal_agreement": 0.65,
        "conflict_count": 2,
        "recommended_actions": ["compare_alternatives", "weight_risks"],
        "recommended_next_action": "balanced decision — compare alternatives and weight risks",
        "decision_signals": {
            "verification_aligned": True,
            "memory_aligned": True,
            "graph_aligned": False,
            "deployment_aligned": False,
        },
    },
    "conflicting_signals": {
        "aliases": ["conflict", "catisma", "mixed", "karma", "contradictory"],
        "decision_status": "conflicting_signals",
        "decision_health": "degraded",
        "decision_summary": "Conflicting signals detected across decision sources. Verification and memory disagree. Additional analysis required.",
        "health_score": 0.52,
        "risk_score": 0.60,
        "signal_agreement": 0.40,
        "conflict_count": 3,
        "recommended_actions": ["additional_analysis", "resolve_conflicts", "gather_more_data"],
        "recommended_next_action": "conflicting signals — additional analysis required",
        "decision_signals": {
            "verification_aligned": True,
            "memory_aligned": False,
            "graph_aligned": False,
            "deployment_aligned": False,
        },
    },
    "high_uncertainty": {
        "aliases": ["high_uncertainty", "belirsiz", "unknown", "bilinmeyen", "risky"],
        "decision_status": "high_uncertainty",
        "decision_health": "critical",
        "decision_summary": "High uncertainty decision. No clear path identified. Most signal sources disagree or are unavailable. Do not commit.",
        "health_score": 0.30,
        "risk_score": 0.85,
        "signal_agreement": 0.15,
        "conflict_count": 4,
        "recommended_actions": ["do_not_commit", "gather_more_data", "run_root_cause_analysis"],
        "recommended_next_action": "high uncertainty — do not commit, gather more data",
        "decision_signals": {
            "verification_aligned": False,
            "memory_aligned": False,
            "graph_aligned": False,
            "deployment_aligned": False,
        },
    },
}

# ---------- internal helpers ----------


def _select_decision_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in DECISION_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "clear_decision"


def _compute_strategy_selection(pid: str) -> Dict[str, Any]:
    p = DECISION_PROFILES.get(pid, {})
    signals = p.get("decision_signals", {})
    health = p.get("health_score", 0.50)

    aligned_count = sum(1 for v in signals.values() if v)
    confidence = round(health * (aligned_count / max(1, len(signals))), 2)

    return {
        "preferred_strategy": (
            "full_repair_pipeline" if health > 0.80
            else "targeted_repair" if health > 0.60
            else "minimal_patch" if health > 0.40
            else "do_not_proceed"
        ),
        "alternative_strategies": [
            "minimal_patch",
            "safe_rebuild",
            "rollback_recovery",
        ] if health < 0.80 else ["minimal_patch"],
        "decision_confidence": confidence,
        "repair_options": ["targeted_fix", "minimal_patch"] if health > 0.50 else ["rollback_recovery"],
        "verification_options": ["full_verification"] if health > 0.60 else ["extended_verification"],
        "deployment_options": ["standard_deployment"] if health > 0.70 else ["conditional_deployment"],
        "rollback_options": ["immediate_rollback", "staged_rollback"],
        "read_only": True,
        "preview_only": True,
    }


def _compute_conflict_analysis(pid: str) -> Dict[str, Any]:
    p = DECISION_PROFILES.get(pid, {})
    signals = p.get("decision_signals", {})
    health = p.get("health_score", 0.50)
    conflict_count = p.get("conflict_count", 0)

    conflict_risk = "low" if health > 0.75 else ("medium" if health > 0.45 else "high")
    return {
        "conflict_summary": (
            "No conflicts detected — all signals aligned"
            if conflict_count == 0
            else f"{conflict_count} conflicts detected across decision sources"
        ),
        "conflict_risk": conflict_risk,
        "resolution_recommendation": (
            "no_resolution_needed" if conflict_count == 0
            else "review_verification_and_memory" if conflict_count <= 2
            else "full_review_all_sources"
        ),
        "verification_conflicts": not signals.get("verification_aligned", True),
        "dependency_conflicts": not signals.get("deployment_aligned", True),
        "memory_conflicts": not signals.get("memory_aligned", True),
        "graph_conflicts": not signals.get("graph_aligned", True),
        "deployment_conflicts": not signals.get("deployment_aligned", True),
        "read_only": True,
        "preview_only": True,
    }


def _compute_risk_weighting(pid: str) -> Dict[str, Any]:
    p = DECISION_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)

    weighted_risk = round(
        risk * 0.3 + (1.0 - health) * 0.7, 2
    )
    weighted_confidence = round(
        health * 0.6 + (1.0 - risk) * 0.4, 2
    )

    return {
        "weighted_risk_score": weighted_risk,
        "weighted_confidence_score": weighted_confidence,
        "repair_risk": round(risk * 0.8, 2),
        "verification_risk": round(risk * 0.6, 2),
        "deployment_risk": round(risk * 0.9, 2),
        "dependency_risk": round(risk * 0.7, 2),
        "rollback_risk": round(risk * 0.3, 2),
        "read_only": True,
        "preview_only": True,
    }


def _compute_decision_score(pid: str) -> Dict[str, float]:
    p = DECISION_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)
    agreement = p.get("signal_agreement", 0.50)

    decision_confidence = round(health * 0.4 + agreement * 0.6, 2)
    decision_risk = round(1.0 - decision_confidence, 2)
    strategy_score = round(health * 0.7 + (1.0 - risk) * 0.3, 2)
    execution_readiness = round(
        decision_confidence * 0.5 + strategy_score * 0.5, 2
    )
    overall = round(
        (decision_confidence * 0.3 + strategy_score * 0.3
         + (1.0 - decision_risk) * 0.2 + execution_readiness * 0.2), 2
    )

    return {
        "decision_confidence": decision_confidence,
        "decision_risk": decision_risk,
        "strategy_score": strategy_score,
        "execution_readiness": execution_readiness,
        "overall_decision_score": overall,
    }


# ---------- public entry points ----------


def engineering_decision_intelligence_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "35.4",
        "name": "Engineering Decision Intelligence Preview",
        "status": "engineering_decision_ready",
        "version": "1.0",
        "capabilities": ENGINEERING_DECISION_CAPABILITIES,
        "pipeline": DECISION_PIPELINE,
        "decision_profile_count": len(DECISION_PROFILES),
        "operation_mode": "read_only_preview_only",
        "core_rule": "never_choose_based_on_single_signal",
        "connected_layers": ["35.3", "35.2", "35.1", "35.0", "34.9", "34.8", "34.7"],
        "available_endpoints": [
            "/engineering-decision/status",
            "/engineering-decision/capabilities",
            "/engineering-decision/preview",
            "/engineering-decision/strategy-selection",
            "/engineering-decision/risk-analysis",
            "/engineering-decision/conflict-analysis",
            "/engineering-decision/decision-score",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "decision_execution": False,
        "repair_execution": False,
        "deployment_execution": False,
        "verification_execution": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only engineering decision intelligence preview. No actual decisions executed.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def engineering_decision_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "35.4",
        "name": "Engineering Decision Intelligence Capabilities",
        "status": "decision_capabilities_ready",
        "capabilities": [
            {"name": "strategy_selection", "description": "Select optimal strategy from available options", "read_only": True},
            {"name": "decision_ranking", "description": "Rank decision paths by confidence and risk", "read_only": True},
            {"name": "path_comparison", "description": "Compare multiple decision paths side by side", "read_only": True},
            {"name": "risk_weighting", "description": "Weight risk across repair, verification, deployment, dependency, rollback", "read_only": True},
            {"name": "confidence_weighting", "description": "Weight confidence across all decision signals", "read_only": True},
            {"name": "repair_decision_analysis", "description": "Analyze repair decisions with historical context", "read_only": True},
            {"name": "verification_decision_analysis", "description": "Analyze verification decisions with confidence scoring", "read_only": True},
            {"name": "deployment_decision_analysis", "description": "Analyze deployment decisions with risk weighting", "read_only": True},
            {"name": "alternative_path_generation", "description": "Generate alternative decision paths", "read_only": True},
            {"name": "decision_summary_generation", "description": "Generate comprehensive decision summary", "read_only": True},
            {"name": "decision_conflict_detection", "description": "Detect conflicts between decision sources", "read_only": True},
            {"name": "decision_health_analysis", "description": "Analyze decision health and signal agreement", "read_only": True},
        ],
        "pipeline": DECISION_PIPELINE,
        "decision_profiles": list(DECISION_PROFILES.keys()),
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def engineering_decision_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_decision_profile(target_issue, command, project_area)
    p = DECISION_PROFILES[pid]
    score = _compute_decision_score(pid)
    strategy = _compute_strategy_selection(pid)

    return {
        "decision_id": pid,
        "decision_status": p["decision_status"],
        "decision_health": p["decision_health"],
        "decision_summary": p.get("decision_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "signal_agreement": p.get("signal_agreement"),
        "conflict_count": p.get("conflict_count"),
        "decision_score": score,
        "strategy_selection": strategy,
        "decision_signals": p.get("decision_signals", {}),
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_stage": "problem",
        "pipeline_progress": {
            "completed": [],
            "current": "problem",
            "remaining": DECISION_PIPELINE[1:],
        },
        "read_only": True,
        "preview_only": True,
    }


def engineering_decision_intelligence_strategy(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_decision_profile(target_issue)
    strategy = _compute_strategy_selection(pid)
    score = _compute_decision_score(pid)

    return {
        "strategy_selection": strategy,
        "decision_score": score,
        "pipeline_stage": "possible_strategies",
        "read_only": True,
        "preview_only": True,
    }


def engineering_decision_intelligence_risk_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_decision_profile(target_issue)
    risk = _compute_risk_weighting(pid)
    score = _compute_decision_score(pid)

    return {
        "risk_analysis": risk,
        "decision_score": score,
        "pipeline_stage": "risk_comparison",
        "read_only": True,
        "preview_only": True,
    }


def engineering_decision_intelligence_conflict_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_decision_profile(target_issue)
    conflict = _compute_conflict_analysis(pid)
    score = _compute_decision_score(pid)

    return {
        "conflict_analysis": conflict,
        "decision_score": score,
        "pipeline_stage": "analysis",
        "read_only": True,
        "preview_only": True,
    }


def engineering_decision_intelligence_decision_score(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_decision_profile(target_issue)
    score = _compute_decision_score(pid)
    strategy = _compute_strategy_selection(pid)
    risk = _compute_risk_weighting(pid)

    return {
        "decision_scores": score,
        "strategy_selection": strategy,
        "risk_analysis": risk,
        "pipeline_stage": "decision_recommendation",
        "read_only": True,
        "preview_only": True,
    }


def engineering_decision_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for did, d in DECISION_PROFILES.items():
        items.append({
            "decision_id": did,
            "decision_status": d["decision_status"],
            "decision_health": d["decision_health"],
            "health_score": d.get("health_score"),
            "risk_score": d.get("risk_score"),
            "signal_agreement": d.get("signal_agreement"),
            "conflict_count": d.get("conflict_count"),
        })
    return {
        "layer": "35.4",
        "name": "Engineering Decision Intelligence Registry",
        "status": "decision_registry_ready",
        "read_only": True,
        "preview_only": True,
        "decision_profile_count": len(items),
        "decision_profiles": items,
        "pass_count": sum(1 for i in items if i["decision_health"] == "pass"),
        "warning_count": sum(1 for i in items if i["decision_health"] == "warning"),
        "degraded_count": sum(1 for i in items if i["decision_health"] == "degraded"),
        "critical_count": sum(1 for i in items if i["decision_health"] == "critical"),
    }
