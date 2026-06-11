from __future__ import annotations

from typing import Any, Dict

from patch_draft_engine_preview import patch_draft_status
from change_preview_engine_preview import change_preview_status
from diff_preview_engine_preview import diff_preview_status
from patch_risk_matrix_preview import patch_risk_status
from patch_approval_engine_preview import patch_approval_status
from patch_execution_readiness_preview import patch_execution_status


IMPLEMENTED_LAYERS = [
    "27.1 Patch Draft Engine",
    "27.2 Change Preview Engine",
    "27.3 Diff Preview Engine",
    "27.4 Patch Risk Matrix",
    "27.5 Patch Approval Engine",
    "27.6 Patch Execution Readiness",
]

ALL_LAYER_ENDPOINTS = [
    "/debug/patch-draft-status",
    "/debug/patch-draft-registry",
    "/debug/patch-draft-preview",
    "/debug/change-preview-status",
    "/debug/change-preview-registry",
    "/debug/change-preview",
    "/debug/diff-preview-status",
    "/debug/diff-preview-registry",
    "/debug/diff-preview",
    "/debug/patch-risk-status",
    "/debug/patch-risk-registry",
    "/debug/patch-risk-preview",
    "/debug/patch-approval-status",
    "/debug/patch-approval-registry",
    "/debug/patch-approval-preview",
    "/debug/patch-execution-status",
    "/debug/patch-execution-registry",
    "/debug/patch-execution-preview",
]

CONNECTED_LAYERS = [
    "26.7 Multi-Agent Coordinator",
    "26.6 Evidence Store",
    "25.6 Verification Planner",
    "25.5 Safe Patch Planner",
    "25.4 Safe Change Boundary",
    "24 Development / Investigation Layer",
    "23 Debug Intelligence Core",
]


def _collect_statuses() -> Dict[str, Any]:
    status_builders = [
        ("27.1", patch_draft_status),
        ("27.2", change_preview_status),
        ("27.3", diff_preview_status),
        ("27.4", patch_risk_status),
        ("27.5", patch_approval_status),
        ("27.6", patch_execution_status),
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


def layer27_status_snapshot() -> Dict[str, Any]:
    statuses = _collect_statuses()
    all_read_only = all(s.get("read_only") for s in statuses.values())
    total_endpoints = len(ALL_LAYER_ENDPOINTS)

    return {
        "snapshot_status": "layer_27_snapshot_ready",
        "layer_27_complete": True,
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
            "No file writes across any Layer 27 component",
            "No memory writes, DB writes, or git writes",
            "No patch application or subprocess execution",
            "All endpoints return read-only preview/draft data only",
        ],
        "development_readiness": {
            "all_layers_implemented": True,
            "all_endpoints_documented": True,
            "smoke_tests_implemented": True,
            "fault_report_integrated": True,
            "ready_for_production_review": False,
            "note": "Layer 27 is scaffold-complete but remains read-only. Real patch execution requires production hardening.",
        },
        "future_direction": [
            "Real patch application engine",
            "Automated regression runner",
            "Write permission boundary enforcement",
            "Production deployment pipeline integration",
        ],
        "read_only": True,
        "analysis_only": True,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
    }


def layer27_full_status() -> Dict[str, Any]:
    base = layer27_status_snapshot()
    statuses = _collect_statuses()

    full_details: Dict[str, Any] = {}
    status_builders: Dict[str, Any] = {
        "27.1": patch_draft_status,
        "27.2": change_preview_status,
        "27.3": diff_preview_status,
        "27.4": patch_risk_status,
        "27.5": patch_approval_status,
        "27.6": patch_execution_status,
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
