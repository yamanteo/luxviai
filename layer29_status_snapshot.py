from __future__ import annotations

from typing import Any, Dict

from patch_permission_enforcement_preview import patch_permission_status
from patch_policy_evaluation_preview import patch_policy_status
from patch_compliance_preview import patch_compliance_status
from patch_governance_preview import patch_governance_status
from patch_oversight_preview import patch_oversight_status
from patch_accountability_preview import patch_accountability_status
from patch_assurance_preview import patch_assurance_status
from patch_confidence_preview import patch_confidence_status


IMPLEMENTED_LAYERS = [
    "29.1 Patch Permission Enforcement Preview",
    "29.2 Patch Policy Evaluation Preview",
    "29.3 Patch Compliance Preview",
    "29.4 Patch Governance Preview",
    "29.5 Patch Oversight Preview",
    "29.6 Patch Accountability Preview",
    "29.7 Patch Assurance Preview",
    "29.8 Patch Confidence Preview",
]

ALL_LAYER_ENDPOINTS = [
    "/debug/patch-permission-status",
    "/debug/patch-permission-registry",
    "/debug/patch-permission-preview",
    "/debug/patch-policy-status",
    "/debug/patch-policy-registry",
    "/debug/patch-policy-preview",
    "/debug/patch-compliance-status",
    "/debug/patch-compliance-registry",
    "/debug/patch-compliance-preview",
    "/debug/patch-governance-status",
    "/debug/patch-governance-registry",
    "/debug/patch-governance-preview",
    "/debug/patch-oversight-status",
    "/debug/patch-oversight-registry",
    "/debug/patch-oversight-preview",
    "/debug/patch-accountability-status",
    "/debug/patch-accountability-registry",
    "/debug/patch-accountability-preview",
    "/debug/patch-assurance-status",
    "/debug/patch-assurance-registry",
    "/debug/patch-assurance-preview",
    "/debug/patch-confidence-status",
    "/debug/patch-confidence-registry",
    "/debug/patch-confidence-preview",
    "/debug/layer29-status",
    "/debug/layer29-full-status",
]

CONNECTED_LAYERS = [
    "28.6 Patch Lifecycle",
    "28.5 Patch Audit Trail",
    "28.4 Patch Recovery",
    "28.3 Patch Validation",
    "28.2 Patch Rollback",
    "28.1 Safe Patch Application",
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
        ("29.1", patch_permission_status),
        ("29.2", patch_policy_status),
        ("29.3", patch_compliance_status),
        ("29.4", patch_governance_status),
        ("29.5", patch_oversight_status),
        ("29.6", patch_accountability_status),
        ("29.7", patch_assurance_status),
        ("29.8", patch_confidence_status),
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


def layer29_status_snapshot() -> Dict[str, Any]:
    statuses = _collect_statuses()
    all_read_only = all(s.get("read_only") for s in statuses.values())
    total_endpoints = len(ALL_LAYER_ENDPOINTS)

    return {
        "snapshot_status": "layer_29_snapshot_ready",
        "layer_29_complete": True,
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
            "No file writes across any Layer 29 component",
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
            "note": "Layer 29 is scaffold-complete but remains read-only. Real patch governance pipeline requires production hardening.",
        },
        "future_direction": [
            "Real patch governance and oversight orchestration",
            "Automated accountability tracking with owner assignment",
            "Confidence-based deployment gating",
            "Production deployment policy enforcement",
        ],
        "read_only": True,
        "analysis_only": True,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
    }


def layer29_full_status() -> Dict[str, Any]:
    base = layer29_status_snapshot()
    statuses = _collect_statuses()

    full_details: Dict[str, Any] = {}
    status_builders: Dict[str, Any] = {
        "29.1": patch_permission_status,
        "29.2": patch_policy_status,
        "29.3": patch_compliance_status,
        "29.4": patch_governance_status,
        "29.5": patch_oversight_status,
        "29.6": patch_accountability_status,
        "29.7": patch_assurance_status,
        "29.8": patch_confidence_status,
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