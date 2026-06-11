from __future__ import annotations

from typing import Any, Dict, List, Optional

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
from luxcode_core_status_snapshot import (
    luxcode_core_status_snapshot,
)


ENGINEERING_FORECAST_CAPABILITIES = [
    "failure_forecasting",
    "deployment_forecasting",
    "verification_forecasting",
    "dependency_risk_prediction",
    "workspace_risk_prediction",
    "repair_outcome_prediction",
    "timeline_forecasting",
    "resource_prediction",
    "engineering_trend_analysis",
    "forecast_summary_generation",
    "forecast_confidence_analysis",
    "predictive_risk_engine",
]

FORECAST_PIPELINE = [
    "current_state_analysis",
    "historical_review",
    "pattern_detection",
    "risk_prediction",
    "outcome_forecast",
    "confidence_evaluation",
    "forecast_summary",
]

FORECAST_PROFILES: Dict[str, Dict[str, Any]] = {
    "stable_forecast": {
        "aliases": ["stable", "stabil", "calm", "sakin", "predictable"],
        "forecast_status": "stable_forecast",
        "forecast_health": "pass",
        "forecast_summary": "Stable forecast. No significant risks predicted. All metrics indicate continued normal operation.",
        "health_score": 0.94,
        "risk_score": 0.06,
        "failure_probability": 0.05,
        "forecast_confidence": 0.92,
        "recommended_actions": ["standard_monitoring", "periodic_review"],
        "recommended_next_action": "stable forecast — continue standard operations",
    },
    "low_risk_forecast": {
        "aliases": ["low_risk", "dusuk_risk", "minor", "kucuk"],
        "forecast_status": "low_risk_forecast",
        "forecast_health": "pass",
        "forecast_summary": "Low risk forecast. Minor concerns identified but unlikely to materialize. Normal operations with awareness.",
        "health_score": 0.86,
        "risk_score": 0.16,
        "failure_probability": 0.12,
        "forecast_confidence": 0.82,
        "recommended_actions": ["monitor_risk_indicators", "review_weekly"],
        "recommended_next_action": "low risk — monitor risk indicators",
    },
    "medium_risk_forecast": {
        "aliases": ["medium_risk", "orta_risk", "moderate", "warning"],
        "forecast_status": "medium_risk_forecast",
        "forecast_health": "warning",
        "forecast_summary": "Medium risk forecast. Several risk indicators elevated. Failure probability moderate. Increased monitoring recommended.",
        "health_score": 0.70,
        "risk_score": 0.38,
        "failure_probability": 0.30,
        "forecast_confidence": 0.68,
        "recommended_actions": ["increase_monitoring", "review_risk_factors", "prepare_contingency"],
        "recommended_next_action": "medium risk — increase monitoring and prepare contingencies",
    },
    "high_risk_forecast": {
        "aliases": ["high_risk", "yuksek_risk", "danger", "tehlikeli"],
        "forecast_status": "high_risk_forecast",
        "forecast_health": "degraded",
        "forecast_summary": "High risk forecast. Significant probability of failures or issues. Active risk mitigation required.",
        "health_score": 0.48,
        "risk_score": 0.65,
        "failure_probability": 0.55,
        "forecast_confidence": 0.52,
        "recommended_actions": ["active_mitigation", "run_preventive_actions", "escalate_risks"],
        "recommended_next_action": "high risk — active mitigation required",
    },
    "critical_forecast": {
        "aliases": ["critical", "kritik", "severe", "siddetli"],
        "forecast_status": "critical_forecast",
        "forecast_health": "critical",
        "forecast_summary": "Critical forecast. High probability of significant failures. Immediate preventive action recommended.",
        "health_score": 0.25,
        "risk_score": 0.88,
        "failure_probability": 0.82,
        "forecast_confidence": 0.30,
        "recommended_actions": ["immediate_prevention", "halt_noncritical_ops", "run_emergency_procedures"],
        "recommended_next_action": "critical forecast — immediate preventive action required",
    },
    "uncertain_forecast": {
        "aliases": ["uncertain", "belirsiz", "unclear", "unknown"],
        "forecast_status": "uncertain_forecast",
        "forecast_health": "warning",
        "forecast_summary": "Uncertain forecast. Insufficient data for reliable prediction. Data collection and analysis recommended.",
        "health_score": 0.55,
        "risk_score": 0.50,
        "failure_probability": 0.40,
        "forecast_confidence": 0.25,
        "recommended_actions": ["gather_more_data", "improve_observability", "rerun_forecast"],
        "recommended_next_action": "uncertain forecast — gather more data for reliable prediction",
    },
}

# ---------- internal helpers ----------


def _select_forecast_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in FORECAST_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "stable_forecast"


def _compute_failure_forecast(pid: str) -> Dict[str, Any]:
    p = FORECAST_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    fail_prob = p.get("failure_probability", 0.50)

    return {
        "failure_probability": fail_prob,
        "failure_confidence": round(1.0 - abs(fail_prob - health), 2),
        "risk_summary": "low_failure_risk" if fail_prob < 0.20 else (
            "medium_failure_risk" if fail_prob < 0.50 else (
                "high_failure_risk" if fail_prob < 0.75 else "critical_failure_risk"
            )
        ),
        "repair_failures": round(fail_prob * 0.6, 2),
        "verification_failures": round(fail_prob * 0.5, 2),
        "deployment_failures": round(fail_prob * 0.7, 2),
        "dependency_failures": round(fail_prob * 0.4, 2),
        "workflow_failures": round(fail_prob * 0.3, 2),
        "read_only": True,
        "preview_only": True,
    }


def _compute_deployment_forecast(pid: str) -> Dict[str, Any]:
    p = FORECAST_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    fail_prob = p.get("failure_probability", 0.50)

    success_prob = round(1.0 - fail_prob, 2)
    return {
        "deployment_forecast": "success" if success_prob > 0.70 else (
            "warning" if success_prob > 0.40 else "failure_likely"
        ),
        "deployment_confidence": round(health * 0.85, 2),
        "deployment_success": success_prob,
        "deployment_warnings": round(fail_prob * 0.6, 2),
        "deployment_failures": round(fail_prob * 0.8, 2),
        "rollback_probability": round(fail_prob * 0.3, 2),
        "read_only": True,
        "preview_only": True,
    }


def _compute_dependency_risk(pid: str) -> Dict[str, Any]:
    p = FORECAST_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    dep_risk = round(1.0 - health * 0.7, 2)
    return {
        "dependency_forecast": "stable" if dep_risk < 0.30 else (
            "volatile" if dep_risk < 0.60 else "unstable"
        ),
        "dependency_risk_score": dep_risk,
        "dependency_instability": round(dep_risk * 0.8, 2),
        "version_conflicts": round(dep_risk * 0.5, 2),
        "integration_risks": round(dep_risk * 0.6, 2),
        "configuration_risks": round(dep_risk * 0.4, 2),
        "read_only": True,
        "preview_only": True,
    }


def _compute_trend_analysis(pid: str) -> Dict[str, Any]:
    p = FORECAST_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    trend_dir = "improving" if health > 0.75 else (
        "stable" if health > 0.45 else "deteriorating"
    )
    return {
        "trend_summary": f"Engineering trends are {trend_dir}. "
                         f"Current health score: {health}. "
                         f"Predictive indicators suggest continued {trend_dir} trajectory.",
        "trend_direction": trend_dir,
        "trend_confidence": round(health * 0.7, 2),
        "repair_trends": trend_dir if health > 0.50 else "deteriorating",
        "verification_trends": trend_dir if health > 0.55 else "deteriorating",
        "deployment_trends": trend_dir if health > 0.60 else "deteriorating",
        "workflow_trends": trend_dir if health > 0.50 else "deteriorating",
        "read_only": True,
        "preview_only": True,
    }


def _compute_forecast_score(pid: str) -> Dict[str, float]:
    p = FORECAST_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)

    forecast_confidence = round(health * 0.8, 2)
    forecast_risk = round(1.0 - forecast_confidence, 2)
    accuracy_est = round(health * 0.7, 2)
    overall = round(
        (forecast_confidence * 0.35 + (1.0 - forecast_risk) * 0.25 + accuracy_est * 0.4), 2
    )
    return {
        "forecast_confidence": forecast_confidence,
        "forecast_risk": forecast_risk,
        "prediction_accuracy_estimate": accuracy_est,
        "engineering_forecast_score": overall,
    }


# ---------- public entry points ----------


def engineering_forecast_intelligence_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "35.6",
        "name": "Engineering Prediction & Forecast Intelligence Preview",
        "status": "engineering_prediction_ready",
        "version": "1.0",
        "capabilities": ENGINEERING_FORECAST_CAPABILITIES,
        "pipeline": FORECAST_PIPELINE,
        "forecast_profile_count": len(FORECAST_PROFILES),
        "operation_mode": "read_only_preview_only",
        "core_principle": "all_predictions_advisory_only_no_automated_actions",
        "connected_layers": ["35.5", "35.4", "35.3", "35.2", "35.1"],
        "available_endpoints": [
            "/engineering-forecast/status",
            "/engineering-forecast/capabilities",
            "/engineering-forecast/preview",
            "/engineering-forecast/failure-prediction",
            "/engineering-forecast/deployment-prediction",
            "/engineering-forecast/dependency-prediction",
            "/engineering-forecast/trend-analysis",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "prediction_execution": False,
        "repair_execution": False,
        "deployment_execution": False,
        "verification_execution": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only engineering forecast preview. All predictions advisory only. No automated actions allowed.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def engineering_forecast_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "35.6",
        "name": "Engineering Forecast Capabilities",
        "status": "forecast_capabilities_ready",
        "capabilities": [
            {"name": "failure_forecasting", "description": "Forecast likely failures across engineering systems", "read_only": True},
            {"name": "deployment_forecasting", "description": "Forecast deployment outcomes and rollback probability", "read_only": True},
            {"name": "verification_forecasting", "description": "Forecast verification outcomes and coverage", "read_only": True},
            {"name": "dependency_risk_prediction", "description": "Predict dependency instability and version conflicts", "read_only": True},
            {"name": "workspace_risk_prediction", "description": "Predict workspace health and drift risks", "read_only": True},
            {"name": "repair_outcome_prediction", "description": "Predict repair success probability", "read_only": True},
            {"name": "timeline_forecasting", "description": "Forecast engineering timeline estimates", "read_only": True},
            {"name": "resource_prediction", "description": "Predict resource requirements and constraints", "read_only": True},
            {"name": "engineering_trend_analysis", "description": "Analyze engineering trends and direction", "read_only": True},
            {"name": "forecast_summary_generation", "description": "Generate comprehensive forecast summary", "read_only": True},
            {"name": "forecast_confidence_analysis", "description": "Analyze forecast confidence and reliability", "read_only": True},
            {"name": "predictive_risk_engine", "description": "Engine predictive risk scoring across all dimensions", "read_only": True},
        ],
        "pipeline": FORECAST_PIPELINE,
        "forecast_profiles": list(FORECAST_PROFILES.keys()),
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def engineering_forecast_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_forecast_profile(target_issue, command, project_area)
    p = FORECAST_PROFILES[pid]
    score = _compute_forecast_score(pid)
    failure = _compute_failure_forecast(pid)

    return {
        "forecast_id": pid,
        "forecast_status": p["forecast_status"],
        "forecast_health": p["forecast_health"],
        "forecast_summary": p.get("forecast_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "failure_probability": p.get("failure_probability"),
        "forecast_confidence": p.get("forecast_confidence"),
        "forecast_score": score,
        "failure_forecast": failure,
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_stage": "current_state_analysis",
        "pipeline_progress": {
            "completed": [],
            "current": "current_state_analysis",
            "remaining": FORECAST_PIPELINE[1:],
        },
        "read_only": True,
        "preview_only": True,
    }


def engineering_forecast_intelligence_failure_prediction(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_forecast_profile(target_issue)
    failure = _compute_failure_forecast(pid)
    score = _compute_forecast_score(pid)

    return {
        "failure_prediction": failure,
        "forecast_score": score,
        "pipeline_stage": "risk_prediction",
        "read_only": True,
        "preview_only": True,
    }


def engineering_forecast_intelligence_deployment_prediction(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_forecast_profile(target_issue)
    deploy = _compute_deployment_forecast(pid)
    score = _compute_forecast_score(pid)

    return {
        "deployment_prediction": deploy,
        "forecast_score": score,
        "pipeline_stage": "outcome_forecast",
        "read_only": True,
        "preview_only": True,
    }


def engineering_forecast_intelligence_dependency_prediction(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_forecast_profile(target_issue)
    dep_risk = _compute_dependency_risk(pid)
    score = _compute_forecast_score(pid)

    return {
        "dependency_prediction": dep_risk,
        "forecast_score": score,
        "pipeline_stage": "pattern_detection",
        "read_only": True,
        "preview_only": True,
    }


def engineering_forecast_intelligence_trend_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_forecast_profile(target_issue)
    trend = _compute_trend_analysis(pid)
    score = _compute_forecast_score(pid)
    failure = _compute_failure_forecast(pid)

    return {
        "trend_analysis": trend,
        "failure_forecast": failure,
        "forecast_score": score,
        "pipeline_stage": "forecast_summary",
        "read_only": True,
        "preview_only": True,
    }


def engineering_forecast_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for fid, f in FORECAST_PROFILES.items():
        items.append({
            "forecast_id": fid,
            "forecast_status": f["forecast_status"],
            "forecast_health": f["forecast_health"],
            "health_score": f.get("health_score"),
            "risk_score": f.get("risk_score"),
            "failure_probability": f.get("failure_probability"),
            "forecast_confidence": f.get("forecast_confidence"),
        })
    return {
        "layer": "35.6",
        "name": "Engineering Forecast Registry",
        "status": "forecast_registry_ready",
        "read_only": True,
        "preview_only": True,
        "forecast_profile_count": len(items),
        "forecast_profiles": items,
        "pass_count": sum(1 for i in items if i["forecast_health"] == "pass"),
        "warning_count": sum(1 for i in items if i["forecast_health"] == "warning"),
        "degraded_count": sum(1 for i in items if i["forecast_health"] == "degraded"),
        "critical_count": sum(1 for i in items if i["forecast_health"] == "critical"),
        "avg_failure_probability": round(
            sum(i.get("failure_probability", 0) for i in items) / max(1, len(items)), 2
        ),
        "avg_forecast_confidence": round(
            sum(i.get("forecast_confidence", 0) for i in items) / max(1, len(items)), 2
        ),
    }
