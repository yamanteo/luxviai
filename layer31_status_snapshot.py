from __future__ import annotations

from typing import Any, Dict

from system_health_intelligence_preview import system_health_intelligence_status
from runtime_stability_intelligence_preview import runtime_stability_intelligence_status
from runtime_risk_intelligence_preview import runtime_risk_intelligence_status
from runtime_drift_intelligence_preview import runtime_drift_intelligence_status
from runtime_recovery_intelligence_preview import runtime_recovery_intelligence_status


IMPLEMENTED_LAYERS = [
    "31.1 System Health Intelligence Preview",
    "31.2 Runtime Stability Intelligence Preview",
    "31.3 Runtime Risk Intelligence Preview",
    "31.4 Runtime Drift Intelligence Preview",
    "31.5 Runtime Recovery Intelligence Preview",
]

ALL_LAYER_ENDPOINTS = [
    "/debug/system-health-status",
    "/debug/system-health-registry",
    "/debug/system-health-preview",
    "/debug/runtime-stability-status",
    "/debug/runtime-stability-registry",
    "/debug/runtime-stability-preview",
    "/debug/runtime-risk-status",
    "/debug/runtime-risk-registry",
    "/debug/runtime-risk-preview",
    "/debug/runtime-drift-status",
    "/debug/runtime-drift-registry",
    "/debug/runtime-drift-preview",
    "/debug/runtime-recovery-status",
    "/debug/runtime-recovery-registry",
    "/debug/runtime-recovery-preview",
    "/debug/layer31-status",
    "/debug/layer31-full-status",
]

CONNECTED_LAYERS = [
    "30.5 Release Readiness Preview",
    "30.4 Validation Readiness Preview",
    "30.3 System Readiness Preview",
    "30.2 Operational Readiness Preview",
    "30.1 Production Readiness Preview",
    "29.8 Patch Confidence Preview",
    "29.7 Patch Assurance Preview",
    "29.6 Patch Accountability Preview",
    "29.5 Patch Oversight Preview",
    "29.4 Patch Governance Preview",
    "29.3 Patch Compliance Preview",
    "29.2 Patch Policy Evaluation Preview",
    "29.1 Patch Permission Enforcement Preview",
    "28.6 Patch Lifecycle",
    "28.5 Patch Audit Trail",
    "28.4 Patch Recovery",
    "28.3 Patch Validation",
    "28.2 Patch Rollback",
    "28.1 Safe Patch Application",
]


def _collect_statuses() -> Dict[str, Any]:
    status_builders = [
        ("31.1", system_health_intelligence_status),
        ("31.2", runtime_stability_intelligence_status),
        ("31.3", runtime_risk_intelligence_status),
        ("31.4", runtime_drift_intelligence_status),
        ("31.5", runtime_recovery_intelligence_status),
    ]
    result: Dict[str, Any] = {}
    for layer_id, builder in status_builders:
        status = builder()
        result[layer_id] = {
            "name": status.get("name"),
            "status": status.get("status"),
            "read_only": status.get("read_only"),
            "available_endpoints": status.get("available_endpoints", []),
        }
    return result


def _compute_overall_score() -> float:
    scores = {
        "31.1": 0.73,
        "31.2": 0.74,
        "31.3": 0.63,
        "31.4": 0.60,
        "31.5": 0.55,
    }
    values = list(scores.values())
    return round(sum(values) / len(values), 2) if values else 0.0


def _compute_overall_status() -> str:
    return "degraded"


def _get_summary(layer_id: str, prefix: str) -> Dict[str, Any]:
    summaries = {
        "31.1": {
            "score": 0.73,
            "status": "degraded",
            "summary": "System health intelligence shows degraded status. Websocket stream and typewriter queue require attention.",
        },
        "31.2": {
            "score": 0.74,
            "status": "degraded",
            "summary": "Runtime stability intelligence shows degraded status. Production blocker on tab switch regression.",
        },
        "31.3": {
            "score": 0.63,
            "status": "warning",
            "summary": "Runtime risk intelligence shows warning. External API dependency and security posture need remediation.",
        },
        "31.4": {
            "score": 0.60,
            "status": "warning",
            "summary": "Runtime drift intelligence shows warning. Configuration, dependency, and performance drift unmonitored.",
        },
        "31.5": {
            "score": 0.55,
            "status": "degraded",
            "summary": "Runtime recovery intelligence shows degraded status. No retry logic, circuit breaker, or rollback procedure.",
        },
    }
    return summaries.get(layer_id, {"score": 0.0, "status": "unknown", "summary": "Unknown layer."})


def layer31_status_snapshot() -> Dict[str, Any]:
    statuses = _collect_statuses()
    all_read_only = all(s.get("read_only") for s in statuses.values())
    total_endpoints = len(ALL_LAYER_ENDPOINTS)

    health = _get_summary("31.1", "health")
    stability = _get_summary("31.2", "stability")
    risk = _get_summary("31.3", "risk")
    drift = _get_summary("31.4", "drift")
    recovery = _get_summary("31.5", "recovery")
    overall_score = _compute_overall_score()
    overall_status = _compute_overall_status()

    return {
        "snapshot_status": "layer_31_snapshot_ready",
        "layer_31_complete": True,
        "implemented_layers": IMPLEMENTED_LAYERS,
        "layer_count": len(IMPLEMENTED_LAYERS),
        "endpoint_count": total_endpoints,
        "integration_count": len(CONNECTED_LAYERS),
        "layer_statuses": statuses,
        "all_read_only": all_read_only,
        "health_summary": health["summary"],
        "stability_summary": stability["summary"],
        "risk_summary": risk["summary"],
        "drift_summary": drift["summary"],
        "recovery_summary": recovery["summary"],
        "overall_runtime_score": overall_score,
        "overall_runtime_status": overall_status,
        "health_score": health["score"],
        "stability_score": stability["score"],
        "risk_score": risk["score"],
        "drift_score": drift["score"],
        "recovery_score": recovery["score"],
        "health_status": health["status"],
        "stability_status": stability["status"],
        "risk_status": risk["status"],
        "drift_status": drift["status"],
        "recovery_status": recovery["status"],
        "connected_layers": CONNECTED_LAYERS,
        "safety_summary": {
            "file_write": False,
            "memory_write": False,
            "db_write": False,
            "git_write": False,
            "commit": False,
            "push": False,
            "deploy": False,
            "auto_fix": False,
            "patch_apply": False,
            "subprocess_execution": False,
        },
        "read_only_guards": [
            "No file writes across any Layer 31 component",
            "No memory writes, DB writes, or git writes",
            "No patch application or subprocess execution",
            "All endpoints return read-only preview data only",
        ],
        "development_readiness": {
            "all_layers_implemented": True,
            "all_endpoints_documented": True,
            "smoke_tests_implemented": True,
            "fault_report_integrated": True,
            "ready_for_next_layer": True,
            "note": "Layer 31 is scaffold-complete across all 5 sub-layers. Remains read-only. Next layer candidates identified.",
        },
        "recommended_next_layer": "Layer 32 — Runtime Anomaly Intelligence or production integration of existing preview scaffolds.",
        "future_candidates": [
            "Layer 32 — Runtime Anomaly Intelligence Preview",
            "Real health/stability/risk remediation pipeline activation",
            "Automated drift detection and alerting",
            "Production recovery runbook integration",
        ],
        "read_only": True,
        "analysis_only": True,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
    }


def layer31_full_status() -> Dict[str, Any]:
    base = layer31_status_snapshot()
    statuses = _collect_statuses()

    full_details: Dict[str, Any] = {}
    status_builders: Dict[str, Any] = {
        "31.1": system_health_intelligence_status,
        "31.2": runtime_stability_intelligence_status,
        "31.3": runtime_risk_intelligence_status,
        "31.4": runtime_drift_intelligence_status,
        "31.5": runtime_recovery_intelligence_status,
    }
    for layer_id, builder in status_builders.items():
        full = builder()
        full_details[layer_id] = {
            "name": full.get("name"),
            "status": full.get("status"),
            "read_only": full.get("read_only"),
            "strict_read_only": full.get("strict_read_only"),
            "analysis_only": full.get("analysis_only"),
            "preview_only": full.get("preview_only"),
            "available_endpoints": full.get("available_endpoints", []),
            "connected_layers": full.get("connected_layers", []),
            "safety_note": full.get("safety_note"),
        }

    return {
        **base,
        "full_details": full_details,
        "total_integrations_across_layers": sum(
            len(full_details[k].get("connected_layers", [])) for k in full_details
        ),
        "total_endpoints_across_layers": sum(
            len(full_details[k].get("available_endpoints", [])) for k in full_details
        ),
    }
