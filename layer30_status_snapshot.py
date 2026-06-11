from __future__ import annotations

from typing import Any, Dict

from production_readiness_preview import production_readiness_status
from operational_readiness_preview import operational_readiness_status
from system_readiness_preview import system_readiness_status
from validation_readiness_preview import validation_readiness_status
from release_readiness_preview import release_readiness_status


IMPLEMENTED_LAYERS = [
    "30.1 Production Readiness Preview",
    "30.2 Operational Readiness Preview",
    "30.3 System Readiness Preview",
    "30.4 Validation Readiness Preview",
    "30.5 Release Readiness Preview",
]

ALL_LAYER_ENDPOINTS = [
    "/debug/production-readiness-status",
    "/debug/production-readiness-registry",
    "/debug/production-readiness-preview",
    "/debug/operational-readiness-status",
    "/debug/operational-readiness-registry",
    "/debug/operational-readiness-preview",
    "/debug/system-readiness-status",
    "/debug/system-readiness-registry",
    "/debug/system-readiness-preview",
    "/debug/validation-readiness-status",
    "/debug/validation-readiness-registry",
    "/debug/validation-readiness-preview",
    "/debug/release-readiness-status",
    "/debug/release-readiness-registry",
    "/debug/release-readiness-preview",
    "/debug/layer30-status",
    "/debug/layer30-full-status",
]

CONNECTED_LAYERS = [
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
    "27.6 Patch Execution Readiness",
    "27.5 Patch Approval Engine",
    "27.4 Patch Risk Matrix",
    "26.7 Multi-Agent Coordinator",
    "25.6 Verification Planner",
    "25.5 Safe Patch Planner",
    "25.4 Safe Change Boundary",
]


def _collect_statuses() -> Dict[str, Any]:
    status_builders = [
        ("30.1", production_readiness_status),
        ("30.2", operational_readiness_status),
        ("30.3", system_readiness_status),
        ("30.4", validation_readiness_status),
        ("30.5", release_readiness_status),
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


def layer30_status_snapshot() -> Dict[str, Any]:
    statuses = _collect_statuses()
    all_read_only = all(s.get("read_only") for s in statuses.values())
    total_endpoints = len(ALL_LAYER_ENDPOINTS)

    return {
        "snapshot_status": "layer_30_snapshot_ready",
        "layer_30_complete": True,
        "implemented_layers": IMPLEMENTED_LAYERS,
        "layer_count": len(IMPLEMENTED_LAYERS),
        "endpoint_count": total_endpoints,
        "integration_count": len(CONNECTED_LAYERS),
        "layer_statuses": statuses,
        "all_read_only": all_read_only,
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
            "No file writes across any Layer 30 component",
            "No memory writes, DB writes, or git writes",
            "No patch application or subprocess execution",
            "All endpoints return read-only preview data only",
        ],
        "development_readiness": {
            "all_layers_implemented": True,
            "all_endpoints_documented": True,
            "smoke_tests_implemented": True,
            "fault_report_integrated": True,
            "ready_for_production_review": False,
            "note": "Layer 30 is scaffold-complete but remains read-only. Real readiness pipeline requires production hardening.",
        },
        "future_direction": [
            "Real production readiness gating and deployment orchestration",
            "Automated operational readiness verification with runbook execution",
            "System-wide blocker propagation monitoring",
            "Validation and release pipeline automation",
        ],
        "read_only": True,
        "analysis_only": True,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
    }


def layer30_full_status() -> Dict[str, Any]:
    base = layer30_status_snapshot()
    statuses = _collect_statuses()

    full_details: Dict[str, Any] = {}
    status_builders: Dict[str, Any] = {
        "30.1": production_readiness_status,
        "30.2": operational_readiness_status,
        "30.3": system_readiness_status,
        "30.4": validation_readiness_status,
        "30.5": release_readiness_status,
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
