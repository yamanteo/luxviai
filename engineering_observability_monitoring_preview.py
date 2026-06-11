from __future__ import annotations

from typing import Any, Dict, List, Optional

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


ENGINEERING_MONITORING_CAPABILITIES = [
    "system_health_monitoring",
    "workflow_monitoring",
    "task_monitoring",
    "verification_monitoring",
    "deployment_monitoring",
    "workspace_monitoring",
    "anomaly_detection",
    "drift_detection",
    "stuck_detection",
    "engineering_telemetry",
    "monitoring_summary_generation",
    "attention_priority_engine",
]

MONITORING_PIPELINE = [
    "activity_detection",
    "state_observation",
    "health_evaluation",
    "risk_evaluation",
    "anomaly_detection",
    "priority_classification",
    "monitoring_summary",
]

MONITORING_PROFILES: Dict[str, Dict[str, Any]] = {
    "healthy_system": {
        "aliases": ["healthy", "saglikli", "stable", "normal", "nominal"],
        "monitoring_status": "healthy_system",
        "monitoring_health": "pass",
        "monitoring_summary": "System healthy. All monitored subsystems nominal. No anomalies or drift detected. Normal operations.",
        "health_score": 0.96,
        "risk_score": 0.04,
        "anomaly_count": 0,
        "drift_count": 0,
        "attention_priority": "low_priority",
        "recommended_actions": ["continue_monitoring", "standard_telemetry"],
        "recommended_next_action": "system healthy — continue standard monitoring",
        "monitoring_signals": {
            "has_anomalies": False,
            "has_drift": False,
            "has_stuck_items": False,
            "needs_attention": False,
        },
    },
    "active_system": {
        "aliases": ["active", "aktif", "running", "calisiyor", "busy"],
        "monitoring_status": "active_system",
        "monitoring_health": "pass",
        "monitoring_summary": "System active with ongoing operations. All metrics within normal ranges. Monitoring nominal.",
        "health_score": 0.88,
        "risk_score": 0.12,
        "anomaly_count": 0,
        "drift_count": 0,
        "attention_priority": "normal_priority",
        "recommended_actions": ["continue_monitoring", "observe_workflows"],
        "recommended_next_action": "active system — continue observation",
        "monitoring_signals": {
            "has_anomalies": False,
            "has_drift": False,
            "has_stuck_items": False,
            "needs_attention": False,
        },
    },
    "high_activity_system": {
        "aliases": ["high_activity", "yogun", "many_operations", "cok_islem"],
        "monitoring_status": "high_activity_system",
        "monitoring_health": "warning",
        "monitoring_summary": "High activity detected. Multiple concurrent operations. Monitoring at increased scrutiny.",
        "health_score": 0.76,
        "risk_score": 0.28,
        "anomaly_count": 1,
        "drift_count": 0,
        "attention_priority": "important",
        "recommended_actions": ["increase_monitoring_frequency", "track_active_workflows"],
        "recommended_next_action": "high activity — increase monitoring frequency",
        "monitoring_signals": {
            "has_anomalies": True,
            "has_drift": False,
            "has_stuck_items": False,
            "needs_attention": True,
        },
    },
    "warning_state": {
        "aliases": ["warning", "uyari", "unusual", "anormal"],
        "monitoring_status": "warning_state",
        "monitoring_health": "warning",
        "monitoring_summary": "Warning state detected. Minor anomalies or drift observed. Requires attention but not critical.",
        "health_score": 0.62,
        "risk_score": 0.45,
        "anomaly_count": 2,
        "drift_count": 1,
        "attention_priority": "high_priority",
        "recommended_actions": ["investigate_anomalies", "check_drift_sources"],
        "recommended_next_action": "warning state — investigate anomalies and drift",
        "monitoring_signals": {
            "has_anomalies": True,
            "has_drift": True,
            "has_stuck_items": False,
            "needs_attention": True,
        },
    },
    "degraded_state": {
        "aliases": ["degraded", "bozulmus", "failing", "problem"],
        "monitoring_status": "degraded_state",
        "monitoring_health": "degraded",
        "monitoring_summary": "Degraded state detected. Multiple anomalies or significant drift. System requires intervention.",
        "health_score": 0.40,
        "risk_score": 0.72,
        "anomaly_count": 4,
        "drift_count": 2,
        "attention_priority": "high_priority",
        "recommended_actions": ["intervene_immediately", "run_diagnostics", "check_all_subsystems"],
        "recommended_next_action": "degraded state — intervention required",
        "monitoring_signals": {
            "has_anomalies": True,
            "has_drift": True,
            "has_stuck_items": True,
            "needs_attention": True,
        },
    },
    "critical_attention_required": {
        "aliases": ["critical", "kritik", "emergency", "acil", "down"],
        "monitoring_status": "critical_attention_required",
        "monitoring_health": "critical",
        "monitoring_summary": "Critical state detected. System requires immediate attention. Multiple severe anomalies and drift detected.",
        "health_score": 0.18,
        "risk_score": 0.92,
        "anomaly_count": 8,
        "drift_count": 4,
        "attention_priority": "critical",
        "recommended_actions": ["immediate_intervention", "escalate", "run_full_system_diagnostics"],
        "recommended_next_action": "critical — immediate intervention required",
        "monitoring_signals": {
            "has_anomalies": True,
            "has_drift": True,
            "has_stuck_items": True,
            "needs_attention": True,
        },
    },
}

# ---------- internal helpers ----------


def _select_monitoring_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in MONITORING_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "healthy_system"


def _compute_system_health(pid: str) -> Dict[str, Any]:
    p = MONITORING_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)

    attention = "low" if health > 0.80 else (
        "medium" if health > 0.50 else "high"
    )
    return {
        "overall_system_health": "healthy" if health > 0.75 else (
            "warning" if health > 0.45 else "critical"
        ),
        "health_score": health,
        "attention_level": attention,
        "task_health": "nominal" if health > 0.70 else ("degraded" if health > 0.40 else "critical"),
        "workspace_health": "nominal" if health > 0.75 else ("degraded" if health > 0.45 else "critical"),
        "verification_health": "nominal" if health > 0.70 else ("degraded" if health > 0.40 else "critical"),
        "deployment_health": "nominal" if health > 0.65 else ("degraded" if health > 0.35 else "critical"),
        "memory_health": "nominal" if health > 0.75 else ("degraded" if health > 0.45 else "critical"),
        "decision_health": "nominal" if health > 0.70 else ("degraded" if health > 0.40 else "critical"),
        "read_only": True,
        "preview_only": True,
    }


def _compute_anomaly_analysis(pid: str) -> Dict[str, Any]:
    p = MONITORING_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    anomaly_count = p.get("anomaly_count", 0)

    risk = "low" if health > 0.75 else ("medium" if health > 0.45 else "high")
    return {
        "anomaly_score": round(1.0 - health, 2),
        "anomaly_summary": (
            "No anomalies detected" if anomaly_count == 0
            else f"{anomaly_count} anomalies detected across monitored subsystems"
        ),
        "risk_level": risk,
        "unexpected_behavior": anomaly_count > 0,
        "workflow_anomalies": anomaly_count >= 1,
        "verification_anomalies": anomaly_count >= 2,
        "deployment_anomalies": anomaly_count >= 3,
        "dependency_anomalies": anomaly_count >= 4,
        "anomaly_count": anomaly_count,
        "read_only": True,
        "preview_only": True,
    }


def _compute_drift_analysis(pid: str) -> Dict[str, Any]:
    p = MONITORING_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    drift_count = p.get("drift_count", 0)

    drift_score = round(1.0 - health, 2)
    return {
        "drift_score": drift_score,
        "drift_summary": (
            "No drift detected" if drift_count == 0
            else f"{drift_count} drift sources detected"
        ),
        "recommended_action": (
            "no_action_required" if drift_count == 0
            else "review_and_resync" if drift_count <= 2
            else "immediate_intervention"
        ),
        "workspace_drift": drift_count >= 1,
        "clone_drift": drift_count >= 2,
        "configuration_drift": drift_count >= 3,
        "dependency_drift": drift_count >= 4,
        "workflow_drift": drift_count >= 5,
        "drift_count": drift_count,
        "read_only": True,
        "preview_only": True,
    }


def _compute_priority_analysis(pid: str) -> Dict[str, Any]:
    p = MONITORING_PROFILES.get(pid, {})
    priority = p.get("attention_priority", "low_priority")

    return {
        "priority_level": priority,
        "priority_reason": (
            "no_attention_required" if priority == "low_priority"
            else "standard_monitoring_active" if priority == "normal_priority"
            else "increased_activity_detected" if priority == "important"
            else "anomalies_or_drift_require_attention" if priority == "high_priority"
            else "immediate_critical_intervention_required"
        ),
        "recommended_focus": (
            "none" if priority == "low_priority"
            else "monitor_active_workflows" if priority == "normal_priority"
            else "track_high_activity_operations" if priority == "important"
            else "investigate_anomalies_and_drift" if priority == "high_priority"
            else "immediate_system_wide_diagnostics"
        ),
        "priority_rank": {
            "low_priority": 1,
            "normal_priority": 2,
            "important": 3,
            "high_priority": 4,
            "critical": 5,
        }.get(priority, 1),
        "all_priorities": ["low_priority", "normal_priority", "important", "high_priority", "critical"],
        "read_only": True,
        "preview_only": True,
    }


def _compute_observability_score(pid: str) -> Dict[str, float]:
    p = MONITORING_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    health_score = round(health * 0.90, 2)
    monitoring_score = round(health * 0.85, 2)
    anomaly_score = round(1.0 - health, 2)
    drift_score = round(1.0 - health * 0.8, 2)
    overall = round(
        (health_score * 0.3 + monitoring_score * 0.25
         + (1.0 - anomaly_score) * 0.25 + (1.0 - drift_score) * 0.20), 2
    )
    return {
        "health_score": health_score,
        "monitoring_score": monitoring_score,
        "anomaly_score": anomaly_score,
        "drift_score": drift_score,
        "observability_score": overall,
    }


# ---------- public entry points ----------


def engineering_monitoring_intelligence_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "35.5",
        "name": "Engineering Observability & Monitoring Intelligence Preview",
        "status": "engineering_monitoring_ready",
        "version": "1.0",
        "capabilities": ENGINEERING_MONITORING_CAPABILITIES,
        "pipeline": MONITORING_PIPELINE,
        "monitoring_profile_count": len(MONITORING_PROFILES),
        "operation_mode": "read_only_preview_only",
        "connected_layers": ["35.4", "35.3", "35.2", "35.1", "35.0"],
        "available_endpoints": [
            "/engineering-monitoring/status",
            "/engineering-monitoring/capabilities",
            "/engineering-monitoring/preview",
            "/engineering-monitoring/health",
            "/engineering-monitoring/anomaly-analysis",
            "/engineering-monitoring/drift-analysis",
            "/engineering-monitoring/priority-analysis",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "monitoring_write": False,
        "repair_execution": False,
        "deployment_execution": False,
        "verification_execution": False,
        "system_modification": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only engineering monitoring preview. No monitoring data written or system modifications performed.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def engineering_monitoring_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "35.5",
        "name": "Engineering Monitoring Capabilities",
        "status": "monitoring_capabilities_ready",
        "capabilities": [
            {"name": "system_health_monitoring", "description": "Monitor overall system health across all engineering subsystems", "read_only": True},
            {"name": "workflow_monitoring", "description": "Monitor workflow states and progress", "read_only": True},
            {"name": "task_monitoring", "description": "Monitor task execution and completion", "read_only": True},
            {"name": "verification_monitoring", "description": "Monitor verification pipeline health", "read_only": True},
            {"name": "deployment_monitoring", "description": "Monitor deployment pipeline health", "read_only": True},
            {"name": "workspace_monitoring", "description": "Monitor workspace state and activity", "read_only": True},
            {"name": "anomaly_detection", "description": "Detect anomalies in workflow, verification, deployment, dependency behavior", "read_only": True},
            {"name": "drift_detection", "description": "Detect drift in workspace, clone, configuration, dependency, workflow", "read_only": True},
            {"name": "stuck_detection", "description": "Detect stuck workflows, tasks, and processes", "read_only": True},
            {"name": "engineering_telemetry", "description": "Collect and analyze engineering telemetry data", "read_only": True},
            {"name": "monitoring_summary_generation", "description": "Generate comprehensive monitoring summary", "read_only": True},
            {"name": "attention_priority_engine", "description": "Classify attention priorities from low to critical", "read_only": True},
        ],
        "pipeline": MONITORING_PIPELINE,
        "monitoring_profiles": list(MONITORING_PROFILES.keys()),
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def engineering_monitoring_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_monitoring_profile(target_issue, command, project_area)
    p = MONITORING_PROFILES[pid]
    health = _compute_system_health(pid)
    score = _compute_observability_score(pid)

    return {
        "monitoring_id": pid,
        "monitoring_status": p["monitoring_status"],
        "monitoring_health": p["monitoring_health"],
        "monitoring_summary": p.get("monitoring_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "system_health": health,
        "observability_score": score,
        "attention_priority": p.get("attention_priority"),
        "anomaly_count": p.get("anomaly_count"),
        "drift_count": p.get("drift_count"),
        "monitoring_signals": p.get("monitoring_signals", {}),
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_stage": "activity_detection",
        "pipeline_progress": {
            "completed": [],
            "current": "activity_detection",
            "remaining": MONITORING_PIPELINE[1:],
        },
        "read_only": True,
        "preview_only": True,
    }


def engineering_monitoring_intelligence_health(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_monitoring_profile(target_issue)
    health = _compute_system_health(pid)
    score = _compute_observability_score(pid)

    return {
        "system_health": health,
        "observability_score": score,
        "pipeline_stage": "health_evaluation",
        "read_only": True,
        "preview_only": True,
    }


def engineering_monitoring_intelligence_anomaly_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_monitoring_profile(target_issue)
    anomaly = _compute_anomaly_analysis(pid)
    score = _compute_observability_score(pid)

    return {
        "anomaly_analysis": anomaly,
        "observability_score": score,
        "pipeline_stage": "anomaly_detection",
        "read_only": True,
        "preview_only": True,
    }


def engineering_monitoring_intelligence_drift_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_monitoring_profile(target_issue)
    drift = _compute_drift_analysis(pid)
    score = _compute_observability_score(pid)

    return {
        "drift_analysis": drift,
        "observability_score": score,
        "pipeline_stage": "activity_detection",
        "read_only": True,
        "preview_only": True,
    }


def engineering_monitoring_intelligence_priority_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_monitoring_profile(target_issue)
    priority = _compute_priority_analysis(pid)
    score = _compute_observability_score(pid)

    return {
        "priority_analysis": priority,
        "observability_score": score,
        "pipeline_stage": "priority_classification",
        "read_only": True,
        "preview_only": True,
    }


def engineering_monitoring_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for mid, m in MONITORING_PROFILES.items():
        items.append({
            "monitoring_id": mid,
            "monitoring_status": m["monitoring_status"],
            "monitoring_health": m["monitoring_health"],
            "health_score": m.get("health_score"),
            "risk_score": m.get("risk_score"),
            "attention_priority": m.get("attention_priority"),
            "anomaly_count": m.get("anomaly_count"),
            "drift_count": m.get("drift_count"),
        })
    return {
        "layer": "35.5",
        "name": "Engineering Monitoring Registry",
        "status": "monitoring_registry_ready",
        "read_only": True,
        "preview_only": True,
        "monitoring_profile_count": len(items),
        "monitoring_profiles": items,
        "pass_count": sum(1 for i in items if i["monitoring_health"] == "pass"),
        "warning_count": sum(1 for i in items if i["monitoring_health"] == "warning"),
        "degraded_count": sum(1 for i in items if i["monitoring_health"] == "degraded"),
        "critical_count": sum(1 for i in items if i["monitoring_health"] == "critical"),
        "total_anomalies": sum(i.get("anomaly_count", 0) for i in items),
        "total_drift": sum(i.get("drift_count", 0) for i in items),
    }
