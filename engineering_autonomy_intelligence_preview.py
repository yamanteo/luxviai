from __future__ import annotations

from typing import Any, Dict, List, Optional

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


ENGINEERING_AUTONOMY_CAPABILITIES = [
    "autonomy_level_analysis",
    "permission_requirement_analysis",
    "risk_based_autonomy",
    "verification_based_autonomy",
    "deployment_based_autonomy",
    "workspace_based_autonomy",
    "repair_based_autonomy",
    "autonomy_recommendation_engine",
    "human_confirmation_analysis",
    "autonomy_boundary_detection",
    "autonomy_summary_generation",
    "autonomy_health_analysis",
]

AUTONOMY_PIPELINE = [
    "task_analysis",
    "risk_analysis",
    "verification_review",
    "decision_review",
    "boundary_analysis",
    "autonomy_recommendation",
    "human_confirmation_review",
    "execution_readiness_assessment",
]

AUTONOMY_LEVELS: Dict[int, Dict[str, Any]] = {
    0: {
        "aliases": ["level_0", "observation", "gozlem", "none"],
        "level": 0,
        "name": "Observation Only",
        "description": "No actions permitted. System observes and reports only.",
        "risk_threshold": 0.0,
        "requires_human_approval": False,
        "requires_verification": False,
        "enabled": True,
    },
    1: {
        "aliases": ["level_1", "recommendation", "tavsiye", "advisory"],
        "level": 1,
        "name": "Recommendations Only",
        "description": "System may recommend actions. Human decides. No automatic execution.",
        "risk_threshold": 0.20,
        "requires_human_approval": True,
        "requires_verification": False,
        "enabled": True,
    },
    2: {
        "aliases": ["level_2", "guided", "rehberli", "approval"],
        "level": 2,
        "name": "Guided Actions",
        "description": "System may prepare guided actions. Human approval required before execution.",
        "risk_threshold": 0.40,
        "requires_human_approval": True,
        "requires_verification": False,
        "enabled": True,
    },
    3: {
        "aliases": ["level_3", "semi_autonomous", "semi", "yarim_otonom"],
        "level": 3,
        "name": "Semi-Autonomous",
        "description": "System may execute autonomously with verification gates. Human approval for deployment.",
        "risk_threshold": 0.60,
        "requires_human_approval": False,
        "requires_verification": True,
        "enabled": True,
    },
    4: {
        "aliases": ["level_4", "high_autonomy", "yuksek_otonomi", "restricted"],
        "level": 4,
        "name": "High Autonomy",
        "description": "High autonomy in restricted domains only. Full verification required.",
        "risk_threshold": 0.80,
        "requires_human_approval": False,
        "requires_verification": True,
        "enabled": True,
    },
    5: {
        "aliases": ["level_5", "full_autonomy", "tam_otonomi", "future"],
        "level": 5,
        "name": "Full Autonomy",
        "description": "Future research only. Currently disabled. Requires additional safety validation.",
        "risk_threshold": 1.0,
        "requires_human_approval": False,
        "requires_verification": True,
        "enabled": False,
    },
}

AUTONOMY_PROFILES: Dict[str, Dict[str, Any]] = {
    "observation_only": {
        "aliases": ["observation", "watch", "izle", "monitor", "level_0"],
        "autonomy_status": "observation_only",
        "autonomy_health": "pass",
        "autonomy_level": 0,
        "health_score": 0.95,
        "risk_score": 0.05,
        "autonomy_summary": "Observation only. System monitors and reports. No actions permitted. Safest mode.",
        "recommended_actions": ["monitor_system", "generate_reports"],
        "recommended_next_action": "observation mode — monitoring active",
    },
    "recommendation_level": {
        "aliases": ["recommendation", "suggest", "advisory", "level_1"],
        "autonomy_status": "recommendation_level",
        "autonomy_health": "pass",
        "autonomy_level": 1,
        "health_score": 0.88,
        "risk_score": 0.12,
        "autonomy_summary": "Recommendation level. System suggests actions. Human makes all decisions. No automatic execution.",
        "recommended_actions": ["generate_recommendations", "await_human_decision"],
        "recommended_next_action": "recommendation mode — providing suggestions",
    },
    "guided_actions": {
        "aliases": ["guided", "approval", "level_2"],
        "autonomy_status": "guided_actions",
        "autonomy_health": "pass",
        "autonomy_level": 2,
        "health_score": 0.80,
        "risk_score": 0.22,
        "autonomy_summary": "Guided actions. System prepares actions. Human must approve before execution.",
        "recommended_actions": ["prepare_actions", "request_approval"],
        "recommended_next_action": "guided mode — awaiting human approval",
    },
    "semi_autonomous": {
        "aliases": ["semi", "semi_autonomous", "level_3"],
        "autonomy_status": "semi_autonomous",
        "autonomy_health": "warning",
        "autonomy_level": 3,
        "health_score": 0.68,
        "risk_score": 0.35,
        "autonomy_summary": "Semi-autonomous mode. System executes with verification gates. Deployment requires human approval.",
        "recommended_actions": ["execute_with_verification", "report_results"],
        "recommended_next_action": "semi-autonomous — executing with verification",
    },
    "high_autonomy": {
        "aliases": ["high_autonomy", "restricted", "level_4"],
        "autonomy_status": "high_autonomy",
        "autonomy_health": "warning",
        "autonomy_level": 4,
        "health_score": 0.55,
        "risk_score": 0.50,
        "autonomy_summary": "High autonomy in restricted domains. Full verification pipeline required. Not for critical systems.",
        "recommended_actions": ["verify_domain_safety", "run_full_verification"],
        "recommended_next_action": "high autonomy — restricted domain active",
    },
}

# ---------- internal helpers ----------


def _select_autonomy_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in AUTONOMY_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "observation_only"


def _compute_autonomy_recommendation(pid: str) -> Dict[str, Any]:
    p = AUTONOMY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)
    level = p.get("autonomy_level", 0)

    return {
        "recommended_autonomy_level": level,
        "autonomy_reasoning": f"Risk {risk:.2f} / Health {health:.2f} → Level {level} ({AUTONOMY_LEVELS[level]['name']})",
        "required_confirmations": (
            [] if level <= 0
            else ["human_approval_required"] if level <= 2
            else ["verification_required"]
        ),
        "task_risk": round(risk * 0.8, 2),
        "verification_confidence": round(health * 0.7, 2),
        "deployment_confidence": round(health * 0.6, 2),
        "memory_confidence": round(health * 0.85, 2),
        "strategy_confidence": round(health * 0.75, 2),
        "read_only": True,
        "preview_only": True,
    }


def _compute_boundary_analysis(pid: str) -> Dict[str, Any]:
    p = AUTONOMY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    level = p.get("autonomy_level", 0)

    boundary_risk = "low" if level <= 1 else ("medium" if level <= 3 else "high")
    return {
        "boundary_status": "safe" if level <= 2 else (
            "caution" if level <= 3 else "warning"
        ),
        "boundary_risk": boundary_risk,
        "recommended_limit": max(0, min(5, level + 1)),
        "unsafe_autonomy": level >= 4 and health < 0.50,
        "excessive_autonomy": level >= 3 and health < 0.40,
        "insufficient_autonomy": level <= 0 and health > 0.90,
        "boundary_conflicts": level >= 4 and health < 0.60,
        "read_only": True,
        "preview_only": True,
    }


def _compute_confirmation_analysis(pid: str) -> Dict[str, Any]:
    p = AUTONOMY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    level = p.get("autonomy_level", 0)

    req_human = level <= 2
    req_verification = level >= 3
    req_deploy_approval = level >= 3
    confirmation_risk = "low" if level <= 1 else ("medium" if level <= 3 else "high")

    return {
        "confirmation_requirements": {
            "approval_required": req_human,
            "review_required": level >= 1,
            "verification_required": req_verification,
            "deployment_approval_required": req_deploy_approval,
        },
        "confirmation_risk": confirmation_risk,
        "human_confirmation_needed": req_human,
        "verification_gates_needed": req_verification,
        "read_only": True,
        "preview_only": True,
    }


def _compute_autonomy_score(pid: str) -> Dict[str, float]:
    p = AUTONOMY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)

    confidence = round(health * 0.8, 2)
    autonomy_risk = round(1.0 - confidence, 2)
    boundary_score = round(health * 0.7, 2)
    approval_score = round((1.0 - risk) * 0.9, 2)
    overall = round(
        (confidence * 0.3 + (1.0 - autonomy_risk) * 0.2 + boundary_score * 0.25 + approval_score * 0.25), 2
    )
    return {
        "autonomy_confidence": confidence,
        "autonomy_risk": autonomy_risk,
        "boundary_score": boundary_score,
        "approval_score": approval_score,
        "overall_autonomy_score": overall,
    }


# ---------- public entry points ----------


def engineering_autonomy_intelligence_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "35.8",
        "name": "Engineering Autonomy Intelligence Preview",
        "status": "engineering_autonomy_ready",
        "version": "1.0",
        "capabilities": ENGINEERING_AUTONOMY_CAPABILITIES,
        "pipeline": AUTONOMY_PIPELINE,
        "autonomy_profiles": list(AUTONOMY_PROFILES.keys()),
        "autonomy_levels": {k: v["name"] for k, v in AUTONOMY_LEVELS.items()},
        "profile_count": len(AUTONOMY_PROFILES),
        "operation_mode": "read_only_preview_only",
        "core_principle": "safest_autonomy_that_achieves_objective",
        "connected_layers": ["35.7", "35.6", "35.5", "35.4", "35.3", "35.2", "35.1"],
        "available_endpoints": [
            "/engineering-autonomy/status",
            "/engineering-autonomy/capabilities",
            "/engineering-autonomy/preview",
            "/engineering-autonomy/recommendation",
            "/engineering-autonomy/boundary-analysis",
            "/engineering-autonomy/confirmation-analysis",
            "/engineering-autonomy/autonomy-score",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "automatic_execution": False,
        "deployment_execution": False,
        "repair_execution": False,
        "verification_execution": False,
        "autonomy_level_5_enabled": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only autonomy intelligence preview. No automatic execution. Level 5 disabled. All outputs advisory only.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def engineering_autonomy_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "35.8",
        "name": "Engineering Autonomy Capabilities",
        "status": "autonomy_capabilities_ready",
        "capabilities": [
            {"name": "autonomy_level_analysis", "description": "Analyze appropriate autonomy level for given task", "read_only": True},
            {"name": "permission_requirement_analysis", "description": "Analyze permissions required for autonomous execution", "read_only": True},
            {"name": "risk_based_autonomy", "description": "Determine autonomy level based on task risk", "read_only": True},
            {"name": "verification_based_autonomy", "description": "Determine autonomy level based on verification confidence", "read_only": True},
            {"name": "deployment_based_autonomy", "description": "Determine autonomy level for deployment tasks", "read_only": True},
            {"name": "workspace_based_autonomy", "description": "Determine autonomy level for workspace operations", "read_only": True},
            {"name": "repair_based_autonomy", "description": "Determine autonomy level for repair operations", "read_only": True},
            {"name": "autonomy_recommendation_engine", "description": "Generate autonomy recommendations based on task, risk, and confidence signals", "read_only": True},
            {"name": "human_confirmation_analysis", "description": "Analyze human confirmation requirements for autonomy level", "read_only": True},
            {"name": "autonomy_boundary_detection", "description": "Detect unsafe, excessive, or insufficient autonomy boundaries", "read_only": True},
            {"name": "autonomy_summary_generation", "description": "Generate comprehensive autonomy summary", "read_only": True},
            {"name": "autonomy_health_analysis", "description": "Analyze autonomy health and safety", "read_only": True},
        ],
        "pipeline": AUTONOMY_PIPELINE,
        "autonomy_levels": {k: v["name"] for k, v in AUTONOMY_LEVELS.items()},
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def engineering_autonomy_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_autonomy_profile(target_issue, command, project_area)
    p = AUTONOMY_PROFILES[pid]
    score = _compute_autonomy_score(pid)
    level_def = AUTONOMY_LEVELS.get(p.get("autonomy_level", 0), {})

    return {
        "autonomy_id": pid,
        "autonomy_status": p["autonomy_status"],
        "autonomy_health": p["autonomy_health"],
        "autonomy_level": p.get("autonomy_level"),
        "autonomy_level_name": level_def.get("name"),
        "autonomy_summary": p.get("autonomy_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "autonomy_score": score,
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_stage": "task_analysis",
        "pipeline_progress": {
            "completed": [],
            "current": "task_analysis",
            "remaining": AUTONOMY_PIPELINE[1:],
        },
        "read_only": True,
        "preview_only": True,
    }


def engineering_autonomy_intelligence_recommendation(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_autonomy_profile(target_issue)
    recommendation = _compute_autonomy_recommendation(pid)
    score = _compute_autonomy_score(pid)

    return {
        "autonomy_recommendation": recommendation,
        "autonomy_score": score,
        "pipeline_stage": "autonomy_recommendation",
        "read_only": True,
        "preview_only": True,
    }


def engineering_autonomy_intelligence_boundary_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_autonomy_profile(target_issue)
    boundary = _compute_boundary_analysis(pid)
    score = _compute_autonomy_score(pid)

    return {
        "boundary_analysis": boundary,
        "autonomy_score": score,
        "pipeline_stage": "boundary_analysis",
        "read_only": True,
        "preview_only": True,
    }


def engineering_autonomy_intelligence_confirmation_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_autonomy_profile(target_issue)
    confirmation = _compute_confirmation_analysis(pid)
    score = _compute_autonomy_score(pid)

    return {
        "confirmation_analysis": confirmation,
        "autonomy_score": score,
        "pipeline_stage": "human_confirmation_review",
        "read_only": True,
        "preview_only": True,
    }


def engineering_autonomy_intelligence_autonomy_score(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_autonomy_profile(target_issue)
    score = _compute_autonomy_score(pid)
    recommendation = _compute_autonomy_recommendation(pid)
    boundary = _compute_boundary_analysis(pid)
    confirmation = _compute_confirmation_analysis(pid)

    return {
        "autonomy_scores": score,
        "autonomy_recommendation": recommendation,
        "boundary_analysis": boundary,
        "confirmation_analysis": confirmation,
        "pipeline_stage": "execution_readiness_assessment",
        "read_only": True,
        "preview_only": True,
    }


def engineering_autonomy_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for aid, a in AUTONOMY_PROFILES.items():
        items.append({
            "autonomy_id": aid,
            "autonomy_status": a["autonomy_status"],
            "autonomy_health": a["autonomy_health"],
            "autonomy_level": a.get("autonomy_level"),
            "health_score": a.get("health_score"),
            "risk_score": a.get("risk_score"),
        })
    return {
        "layer": "35.8",
        "name": "Engineering Autonomy Registry",
        "status": "autonomy_registry_ready",
        "read_only": True,
        "preview_only": True,
        "autonomy_profile_count": len(items),
        "autonomy_profiles": items,
        "pass_count": sum(1 for i in items if i["autonomy_health"] == "pass"),
        "warning_count": sum(1 for i in items if i["autonomy_health"] == "warning"),
        "avg_autonomy_level": round(
            sum(i.get("autonomy_level", 0) for i in items) / max(1, len(items)), 1
        ),
        "enabled_levels": [k for k, v in AUTONOMY_LEVELS.items() if v["enabled"]],
    }
