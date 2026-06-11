from __future__ import annotations

from typing import Any, Dict

from safe_patch_application_preview import safe_patch_status
from patch_rollback_preview import patch_rollback_status
from patch_validation_preview import patch_validation_status
from patch_recovery_preview import patch_recovery_status
from patch_audit_trail_preview import patch_audit_status
from patch_lifecycle_preview import patch_lifecycle_status


IMPLEMENTED_LAYERS = [
    "28.1 Safe Patch Application Preview",
    "28.2 Patch Rollback Preview",
    "28.3 Patch Validation Preview",
    "28.4 Patch Recovery Preview",
    "28.5 Patch Audit Trail Preview",
    "28.6 Patch Lifecycle Preview",
]

ALL_LAYER_ENDPOINTS = [
    "/debug/safe-patch-status",
    "/debug/safe-patch-registry",
    "/debug/safe-patch-preview",
    "/debug/patch-rollback-status",
    "/debug/patch-rollback-registry",
    "/debug/patch-rollback-preview",
    "/debug/patch-validation-status",
    "/debug/patch-validation-registry",
    "/debug/patch-validation-preview",
    "/debug/patch-recovery-status",
    "/debug/patch-recovery-registry",
    "/debug/patch-recovery-preview",
    "/debug/patch-audit-status",
    "/debug/patch-audit-registry",
    "/debug/patch-audit-preview",
    "/debug/patch-lifecycle-status",
    "/debug/patch-lifecycle-registry",
    "/debug/patch-lifecycle-preview",
    "/debug/layer28-status",
    "/debug/layer28-full-status",
]

CONNECTED_LAYERS = [
    "27.6 Patch Execution Readiness",
    "27.5 Patch Approval Engine",
    "27.4 Patch Risk Matrix",
    "27.3 Diff Preview Engine",
    "27.2 Change Preview Engine",
    "27.1 Patch Draft Engine",
    "26.7 Multi-Agent Coordinator",
    "26.6 Evidence Store",
    "25.6 Verification Planner",
    "25.5 Safe Patch Planner",
    "25.4 Safe Change Boundary",
]


def _collect_statuses() -> Dict[str, Any]:
    status_builders = [
        ("28.1", safe_patch_status),
        ("28.2", patch_rollback_status),
        ("28.3", patch_validation_status),
        ("28.4", patch_recovery_status),
        ("28.5", patch_audit_status),
        ("28.6", patch_lifecycle_status),
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


def layer28_status_snapshot() -> Dict[str, Any]:
    statuses = _collect_statuses()
    all_read_only = all(s.get("read_only") for s in statuses.values())
    total_endpoints = len(ALL_LAYER_ENDPOINTS)

    return {
        "snapshot_status": "layer_28_snapshot_ready",
        "layer_28_complete": True,
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
            "No file writes across any Layer 28 component",
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
            "note": "Layer 28 is scaffold-complete but remains read-only. Real patch lifecycle execution requires production hardening.",
        },
        "future_direction": [
            "Real patch lifecycle orchestration engine",
            "Automated recovery trigger pipeline",
            "Write permission enforcement across lifecycle stages",
            "Production deployment pipeline integration",
        ],
        "read_only": True,
        "analysis_only": True,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
    }


def layer28_full_status() -> Dict[str, Any]:
    base = layer28_status_snapshot()
    statuses = _collect_statuses()

    full_details: Dict[str, Any] = {}
    status_builders: Dict[str, Any] = {
        "28.1": safe_patch_status,
        "28.2": patch_rollback_status,
        "28.3": patch_validation_status,
        "28.4": patch_recovery_status,
        "28.5": patch_audit_status,
        "28.6": patch_lifecycle_status,
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
