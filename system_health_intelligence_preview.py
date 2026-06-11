from __future__ import annotations
from typing import Any, Dict, List, Optional

from layer30_status_snapshot import layer30_full_status, layer30_status_snapshot
from layer29_status_snapshot import layer29_status_snapshot
from patch_confidence_preview import build_patch_confidence_preview, patch_confidence_registry
from patch_assurance_preview import build_patch_assurance_preview, patch_assurance_registry
from patch_accountability_preview import build_patch_accountability_preview, patch_accountability_registry
from patch_oversight_preview import build_patch_oversight_preview, patch_oversight_registry
from patch_governance_preview import build_patch_governance_preview, patch_governance_registry
from patch_compliance_preview import build_patch_compliance_preview, patch_compliance_registry
from patch_policy_evaluation_preview import build_patch_policy_preview, patch_policy_registry
from patch_permission_enforcement_preview import build_patch_permission_preview, patch_permission_registry


HEALTH_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue_flow": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "health_category": "flow_safety",
        "health_status": "pass",
        "health_score": 0.88,
        "health_findings": [
            "all_downstream_layers_report_green",
            "confidence_assessment_favorable",
        ],
        "health_warnings": [
            "typewriter_queue_ownership_unassigned",
        ],
        "health_blockers": [],
        "health_risk_level": "low",
        "health_recommendations": [
            "schedule_production_health_review",
            "document_runtime_behavior_for_ops",
        ],
        "health_summary": "Stop/continue flow is healthy. All downstream layers report green.",
        "required_actions": [],
        "recommended_next_action": "proceed with production deployment; health is satisfactory",
        "confidence_score": 0.89,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "health_category": "stream_integrity",
        "health_status": "degraded",
        "health_score": 0.45,
        "health_findings": [
            "confidence_cascade_failure_detected",
            "accountability_gaps_block_readiness",
            "oversight_violations_remain_open",
        ],
        "health_warnings": [
            "tab_switch_regression_blocks_production",
            "typewriter_queue_ownership_unassigned",
            "privacy_audit_not_completed",
        ],
        "health_blockers": [
            "tab_switch_regression_blocks_production",
        ],
        "health_risk_level": "high",
        "health_recommendations": [
            "resolve_all_blockers_before_production",
            "re-run_health_assessment_after_fixes",
        ],
        "health_summary": "Websocket stream health is degraded. 1 production blocker remains open.",
        "required_actions": [
            "fix_tab_switch_regression_at_source",
            "assign_typewriter_queue_ownership",
            "complete_privacy_audit",
        ],
        "recommended_next_action": "resolve 3 health issues before deployment",
        "confidence_score": 0.87,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "health_category": "export_safety",
        "health_status": "pass",
        "health_score": 0.87,
        "health_findings": [
            "export_pipeline_documented",
            "write_guard_verified",
        ],
        "health_warnings": [],
        "health_blockers": [],
        "health_risk_level": "low",
        "health_recommendations": [
            "run_production_load_test_on_export",
        ],
        "health_summary": "Workspace export health is satisfactory. No blockers detected.",
        "required_actions": [],
        "recommended_next_action": "run production load test; health is satisfactory",
        "confidence_score": 0.88,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "health_category": "permission_safety",
        "health_status": "pass",
        "health_score": 0.82,
        "health_findings": [
            "permission_schema_verified",
            "device_safety_boundary_validated",
        ],
        "health_warnings": [
            "real_platform_integration_pending",
        ],
        "health_blockers": [],
        "health_risk_level": "low",
        "health_recommendations": [
            "real_luxway_platform_integration_needed",
            "end_to_end_permission_testing",
        ],
        "health_summary": "Luxway permission flow is healthy. Real platform integration pending.",
        "required_actions": [],
        "recommended_next_action": "proceed with platform integration planning",
        "confidence_score": 0.84,
    },
    "typewriter_queue": {
        "aliases": ["typewriter", "queue", "tab", "delta", "cursor"],
        "target_component": "typewriter_queue",
        "health_category": "queue_integrity",
        "health_status": "warning",
        "health_score": 0.60,
        "health_findings": [
            "queue_ownership_not_formalized",
            "queue_clear_behavior_not_finalized",
        ],
        "health_warnings": [
            "typewriter_queue_ownership_unassigned",
            "queue_clear_future_check_remains",
        ],
        "health_blockers": [],
        "health_risk_level": "medium",
        "health_recommendations": [
            "formalize_typewriter_queue_ownership",
            "finalize_queue_clear_behavior",
        ],
        "health_summary": "Typewriter queue health has warnings. Ownership needs formalization.",
        "required_actions": [
            "assign_typewriter_queue_ownership",
        ],
        "recommended_next_action": "resolve ownership and finalize queue behavior",
        "confidence_score": 0.75,
    },
    "patch_lifecycle": {
        "aliases": ["patch", "lifecycle", "rollback", "validation", "recovery"],
        "target_component": "patch_lifecycle",
        "health_category": "patch_governance",
        "health_status": "pass",
        "health_score": 0.85,
        "health_findings": [
            "all_patch_lifecycle_stages_implemented",
            "rollback_and_recovery_ready",
        ],
        "health_warnings": [
            "real_patch_execution_not_activated",
        ],
        "health_blockers": [],
        "health_risk_level": "low",
        "health_recommendations": [
            "activate_real_patch_execution_pipeline",
            "run_full_lifecycle_integration_test",
        ],
        "health_summary": "Patch lifecycle health is satisfactory. All stages implemented.",
        "required_actions": [],
        "recommended_next_action": "activate real patch execution pipeline",
        "confidence_score": 0.86,
    },
    "production_readiness": {
        "aliases": ["production", "deploy", "release", "go-live", "go_live"],
        "target_component": "production_readiness",
        "health_category": "deployment_safety",
        "health_status": "pass",
        "health_score": 0.83,
        "health_findings": [
            "all_readiness_layers_report_ready",
            "safety_guards_active",
            "read_only_mode_verified",
        ],
        "health_warnings": [
            "production_review_not_scheduled",
            "load_testing_not_executed",
        ],
        "health_blockers": [],
        "health_risk_level": "low",
        "health_recommendations": [
            "schedule_production_review",
            "execute_load_testing",
            "document_deployment_runbook",
        ],
        "health_summary": "Production readiness health is satisfactory. 2 pre-deployment items pending.",
        "required_actions": [],
        "recommended_next_action": "schedule production review and load testing",
        "confidence_score": 0.85,
    },
}


def _select_health_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    for key, profile in HEALTH_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(t.lower() in aliases or t.lower() == key for t in targets for t2 in [t]):
            for target in targets:
                tl = target.lower().strip()
                if tl in aliases or tl == key:
                    return key
    return "stop_continue_flow"


def system_health_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "31.1",
        "name": "System Health Intelligence Preview",
        "status": "system_health_intelligence_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "preview_only": True,
        "real_action_performed": False,
        "file_write_enabled": False,
        "memory_write_enabled": False,
        "db_write_enabled": False,
        "git_write_enabled": False,
        "commit_enabled": False,
        "push_enabled": False,
        "deploy_enabled": False,
        "auto_fix_enabled": False,
        "patch_apply_enabled": False,
        "subprocess_execution_enabled": False,
        "repo_scan_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "available_endpoints": [
            "/debug/system-health-status",
            "/debug/system-health-registry",
            "/debug/system-health-preview",
        ],
        "connected_layers": [
            "30", "30.1", "30.2", "30.3", "30.4", "30.5",
            "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
            "28.6", "28.5", "28.4", "28.3", "28.2", "28.1",
            "27.6", "27.5", "27.4",
            "26.7",
            "25.6", "25.5", "25.4",
        ],
        "safety_note": "Read-only system health intelligence preview. No actual health remediation actions performed.",
    }


def system_health_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for hid, h in HEALTH_PROFILES.items():
        items.append(
            {
                "health_id": hid,
                "target_component": h["target_component"],
                "health_category": h["health_category"],
                "health_status": h["health_status"],
                "health_score": h["health_score"],
                "health_risk_level": h["health_risk_level"],
                "blocker_count": len(h.get("health_blockers", [])),
                "warning_count": len(h.get("health_warnings", [])),
                "confidence_score": h["confidence_score"],
            }
        )
    return {
        "layer": "31.1",
        "name": "System Health Intelligence Registry",
        "status": "system_health_intelligence_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "health_count": len(items),
        "health_items": items,
        "pass_count": sum(1 for i in items if i["health_status"] == "pass"),
        "warning_count": sum(1 for i in items if i["health_status"] == "warning"),
        "degraded_count": sum(1 for i in items if i["health_status"] == "degraded"),
        "blocked_count": sum(1 for i in items if i["health_status"] == "blocked"),
        "overall_health_score": round(
            sum(i["health_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "overall_health_status": _compute_overall_health_status(items),
        "safety_flags": {
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
    }


def _compute_overall_health_status(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    statuses = [i.get("health_status", "") for i in items]
    if any(s == "blocked" for s in statuses):
        return "blocked"
    if any(s == "degraded" for s in statuses):
        return "degraded"
    if any(s == "warning" for s in statuses):
        return "warning"
    if all(s == "pass" for s in statuses):
        return "pass"
    return "warning"


def _build_integration_signals(
    target: str, command: str, project_area: str, related_layer: str
) -> Dict[str, Any]:
    L = related_layer or "Layer 31.1"
    layer30 = layer30_full_status()
    layer29 = layer29_status_snapshot()

    confidence = build_patch_confidence_preview(
        target_issue=target, command=command,
        project_area=project_area, related_layer=L
    )
    assurance = build_patch_assurance_preview(
        target_issue=target, command=command,
        project_area=project_area, related_layer=L
    )
    accountability = build_patch_accountability_preview(
        target_issue=target, command=command,
        project_area=project_area, related_layer=L
    )
    oversight = build_patch_oversight_preview(
        target_issue=target, command=command,
        project_area=project_area, related_layer=L
    )
    governance = build_patch_governance_preview(
        target_issue=target, command=command,
        project_area=project_area, related_layer=L
    )
    compliance = build_patch_compliance_preview(
        target_issue=target, command=command,
        project_area=project_area, related_layer=L
    )
    policy = build_patch_policy_preview(
        target_issue=target, command=command,
        project_area=project_area, related_layer=L
    )
    permission = build_patch_permission_preview(
        target_issue=target, command=command,
        project_area=project_area, related_layer=L
    )

    return {
        "layer30_status_snapshot": {
            "snapshot_status": layer30.get("snapshot_status"),
            "layer_30_complete": layer30.get("layer_30_complete"),
            "endpoint_count": layer30.get("endpoint_count"),
        },
        "layer29_status_snapshot": {
            "snapshot_status": layer29.get("snapshot_status"),
            "layer_29_complete": layer29.get("layer_29_complete"),
            "integration_count": layer29.get("integration_count"),
        },
        "patch_confidence": {
            "confidence_score": confidence.get("confidence_score"),
            "confidence_status": confidence.get("confidence_status"),
        },
        "patch_assurance": {
            "assurance_score": assurance.get("assurance_score"),
            "assurance_status": assurance.get("assurance_status"),
        },
        "patch_accountability": {
            "accountability_status": accountability.get("accountability_status"),
        },
        "patch_oversight": {
            "oversight_status": oversight.get("oversight_status"),
            "oversight_findings": oversight.get("oversight_findings", []),
        },
        "patch_governance": {
            "governance_status": governance.get("governance_status"),
        },
        "patch_compliance": {
            "compliance_status": compliance.get("compliance_status"),
        },
        "patch_policy_evaluation": {
            "policy_status": policy.get("policy_status"),
        },
        "patch_permission_enforcement": {
            "permission_status": permission.get("permission_status"),
        },
    }


def build_system_health_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    hid = _select_health_profile(target_issue, command, project_area)
    h = HEALTH_PROFILES[hid]
    detected = target_issue or project_area or hid
    cmd = command or detected
    L = related_layer or "Layer 31.1"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "health_id": hid,
        "target_component": h["target_component"],
        "health_category": h["health_category"],
        "health_status": h["health_status"],
        "health_score": h["health_score"],
        "health_findings": h.get("health_findings", []),
        "health_warnings": h.get("health_warnings", []),
        "health_blockers": h.get("health_blockers", []),
        "health_risk_level": h.get("health_risk_level"),
        "health_recommendations": h.get("health_recommendations", []),
        "health_summary": h.get("health_summary"),
        "required_actions": h.get("required_actions", []),
        "recommended_next_action": h.get("recommended_next_action"),
        "confidence_score": h["confidence_score"],
        "integration_signals": integration,
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "preview_only": True,
        "real_action_performed": False,
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_write_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "auto_fix_performed": False,
        "patch_apply_performed": False,
        "subprocess_execution_performed": False,
        "repo_scan_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only system health intelligence preview. No actual health actions performed.",
    }
