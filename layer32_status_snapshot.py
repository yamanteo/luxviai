from __future__ import annotations

from typing import Any, Dict

from runtime_anomaly_intelligence_preview import runtime_anomaly_intelligence_status
from regression_intelligence_preview import regression_intelligence_status
from failure_memory_intelligence_preview import failure_memory_intelligence_status
from root_cause_intelligence_preview import root_cause_intelligence_status
from dependency_intelligence_preview import dependency_intelligence_status


IMPLEMENTED_LAYERS = [
    "32.1 Runtime Anomaly Intelligence Preview",
    "32.2 Regression Intelligence Preview",
    "32.3 Failure Memory Intelligence Preview",
    "32.4 Root Cause Intelligence Preview",
    "32.5 Dependency Intelligence Preview",
]

ALL_LAYER_ENDPOINTS = [
    "/debug/runtime-anomaly-status",
    "/debug/runtime-anomaly-registry",
    "/debug/runtime-anomaly-preview",
    "/debug/regression-status",
    "/debug/regression-registry",
    "/debug/regression-preview",
    "/debug/failure-memory-status",
    "/debug/failure-memory-registry",
    "/debug/failure-memory-preview",
    "/debug/root-cause-status",
    "/debug/root-cause-registry",
    "/debug/root-cause-preview",
    "/debug/dependency-status",
    "/debug/dependency-registry",
    "/debug/dependency-preview",
    "/debug/layer32-status",
    "/debug/layer32-full-status",
]

CONNECTED_LAYERS = [
    "31.5 Runtime Recovery Intelligence Preview",
    "31.4 Runtime Drift Intelligence Preview",
    "31.3 Runtime Risk Intelligence Preview",
    "31.2 Runtime Stability Intelligence Preview",
    "31.1 System Health Intelligence Preview",
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
]


def _collect_statuses() -> Dict[str, Any]:
    status_builders = [
        ("32.1", runtime_anomaly_intelligence_status),
        ("32.2", regression_intelligence_status),
        ("32.3", failure_memory_intelligence_status),
        ("32.4", root_cause_intelligence_status),
        ("32.5", dependency_intelligence_status),
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
        "32.1": 0.62,
        "32.2": 0.65,
        "32.3": 0.58,
        "32.4": 0.55,
        "32.5": 0.60,
    }
    values = list(scores.values())
    return round(sum(values) / len(values), 2) if values else 0.0


def _compute_overall_status() -> str:
    return "degraded"


def _get_summary(layer_id: str) -> Dict[str, Any]:
    summaries = {
        "32.1": {
            "score": 0.62,
            "status": "warning",
            "summary": "Runtime anomaly intelligence shows warning. Performance anomaly and dependency anomaly detected. Configuration gaps present.",
        },
        "32.2": {
            "score": 0.65,
            "status": "warning",
            "summary": "Regression intelligence shows warning. Behavior regression and endpoint regression detected. Behavioral baseline not established.",
        },
        "32.3": {
            "score": 0.58,
            "status": "degraded",
            "summary": "Failure memory intelligence shows degraded. Connection, timeout, and recovery failures have high recurrence. No automated alerting.",
        },
        "32.4": {
            "score": 0.55,
            "status": "degraded",
            "summary": "Root cause intelligence shows degraded. Dependency and runtime root causes critical. Recovery and regression root causes need remediation.",
        },
        "32.5": {
            "score": 0.60,
            "status": "warning",
            "summary": "Dependency intelligence shows warning. Circular import, module depth, and external SPOF dependencies need resolution.",
        },
    }
    return summaries.get(layer_id, {"score": 0.0, "status": "unknown", "summary": "Unknown layer."})


def layer32_status_snapshot() -> Dict[str, Any]:
    statuses = _collect_statuses()
    all_read_only = all(s.get("read_only") for s in statuses.values())
    total_endpoints = len(ALL_LAYER_ENDPOINTS)

    anomaly = _get_summary("32.1")
    regression = _get_summary("32.2")
    failure_memory = _get_summary("32.3")
    root_cause = _get_summary("32.4")
    dependency = _get_summary("32.5")
    overall_score = _compute_overall_score()
    overall_status = _compute_overall_status()

    return {
        "snapshot_status": "layer_32_snapshot_ready",
        "layer_32_complete": True,
        "implemented_layers": IMPLEMENTED_LAYERS,
        "layer_count": len(IMPLEMENTED_LAYERS),
        "endpoint_count": total_endpoints,
        "integration_count": len(CONNECTED_LAYERS),
        "layer_statuses": statuses,
        "all_read_only": all_read_only,
        "anomaly_summary": anomaly["summary"],
        "regression_summary": regression["summary"],
        "failure_memory_summary": failure_memory["summary"],
        "root_cause_summary": root_cause["summary"],
        "dependency_summary": dependency["summary"],
        "overall_layer32_score": overall_score,
        "overall_layer32_status": overall_status,
        "anomaly_score": anomaly["score"],
        "regression_score": regression["score"],
        "failure_memory_score": failure_memory["score"],
        "root_cause_score": root_cause["score"],
        "dependency_score": dependency["score"],
        "anomaly_status": anomaly["status"],
        "regression_status": regression["status"],
        "failure_memory_status": failure_memory["status"],
        "root_cause_status": root_cause["status"],
        "dependency_status": dependency["status"],
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
            "No file writes across any Layer 32 component",
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
            "note": "Layer 32 is scaffold-complete across all 5 sub-layers. Remains read-only. Ready for production remediation pipeline.",
        },
        "recommended_next_layer": "Layer 33 — Remediation Pipeline or production activation of existing intelligence scaffolds.",
        "future_candidates": [
            "Layer 33 — Remediation Pipeline",
            "Real anomaly/failure/root cause remediation activation",
            "Automated root cause correlation across all intelligence layers",
            "Production dependency health monitoring integration",
        ],
        "read_only": True,
        "analysis_only": True,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
    }


def layer32_full_status() -> Dict[str, Any]:
    base = layer32_status_snapshot()
    statuses = _collect_statuses()

    full_details: Dict[str, Any] = {}
    status_builders: Dict[str, Any] = {
        "32.1": runtime_anomaly_intelligence_status,
        "32.2": regression_intelligence_status,
        "32.3": failure_memory_intelligence_status,
        "32.4": root_cause_intelligence_status,
        "32.5": dependency_intelligence_status,
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
