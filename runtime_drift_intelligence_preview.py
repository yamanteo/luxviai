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


DRIFT_PROFILES: Dict[str, Dict[str, Any]] = {
    "config_drift": {
        "aliases": ["config", "configuration", "env", "setting", "ayar", "yapilandirma"],
        "target_component": "configuration_runtime",
        "drift_category": "config_integrity",
        "drift_status": "warning",
        "drift_score": 0.54,
        "drift_findings": [
            "env_values_not_validated_against_schema",
            "configuration_documentation_missing",
        ],
        "drift_warnings": [
            "fallback_mode_changes_runtime_behavior",
            "env_file_can_be_bypassed",
        ],
        "drift_blockers": [],
        "drift_risk_level": "medium",
        "drift_recommendations": [
            "add_config_validation_at_boot",
            "document_all_configuration_parameters",
            "create_config_schema_with_expected_ranges",
        ],
        "drift_summary": "Configuration drift is at medium risk. Environment values lack validation against a schema.",
        "required_actions": [],
        "recommended_next_action": "implement configuration validation schema and boot-time checks",
        "confidence_score": 0.66,
    },
    "dependency_drift": {
        "aliases": ["dependency", "version", "package", "module", "bagimlilik"],
        "target_component": "dependency_graph_runtime",
        "drift_category": "dependency_consistency",
        "drift_status": "warning",
        "drift_score": 0.56,
        "drift_findings": [
            "dependency_versions_not_pinned",
            "no_automated_dependency_audit",
        ],
        "drift_warnings": [
            "transitive_dependency_shifts_unmonitored",
            "no_lockfile_for_all_environments",
        ],
        "drift_blockers": [],
        "drift_risk_level": "medium",
        "drift_recommendations": [
            "pin_all_dependency_versions",
            "add_automated_dependency_audit",
            "generate_lockfile_for_production",
        ],
        "drift_summary": "Dependency drift is at medium risk. Versions are not pinned across environments.",
        "required_actions": [],
        "recommended_next_action": "pin all dependency versions and generate production lockfile",
        "confidence_score": 0.68,
    },
    "state_drift": {
        "aliases": ["state", "session", "runtime_state", "memory", "durum"],
        "target_component": "state_management_runtime",
        "drift_category": "state_consistency",
        "drift_status": "pass",
        "drift_score": 0.78,
        "drift_findings": [
            "user_state_persistence_verified",
            "session_isolation_active",
        ],
        "drift_warnings": [
            "state_recovery_not_tested_after_crash",
            "no_state_version_tracking",
        ],
        "drift_blockers": [],
        "drift_risk_level": "low",
        "drift_recommendations": [
            "implement_state_version_tracking",
            "test_state_recovery_after_crash",
        ],
        "drift_summary": "State drift is low. Persistence verified but recovery after crash untested.",
        "required_actions": [],
        "recommended_next_action": "implement state version tracking and test crash recovery",
        "confidence_score": 0.74,
    },
    "performance_drift": {
        "aliases": ["performance", "latency", "speed", "throughput", "performans"],
        "target_component": "performance_runtime",
        "drift_category": "performance_consistency",
        "drift_status": "warning",
        "drift_score": 0.50,
        "drift_findings": [
            "no_performance_baseline_established",
            "load_testing_not_executed",
        ],
        "drift_warnings": [
            "websocket_latency_not_monitored",
            "typewriter_queue_backpressure_untested",
            "memory_usage_trend_not_tracked",
        ],
        "drift_blockers": [],
        "drift_risk_level": "medium",
        "drift_recommendations": [
            "establish_performance_baseline",
            "execute_load_testing",
            "monitor_websocket_latency_continuously",
            "track_memory_usage_over_time",
        ],
        "drift_summary": "Performance drift is at medium risk. No baseline established to detect regression.",
        "required_actions": [],
        "recommended_next_action": "establish performance baseline and begin monitoring",
        "confidence_score": 0.70,
    },
    "data_drift": {
        "aliases": ["data", "content", "consistency", "integrity", "veri"],
        "target_component": "data_layer_runtime",
        "drift_category": "data_consistency",
        "drift_status": "pass",
        "drift_score": 0.76,
        "drift_findings": [
            "file_locks_prevent_concurrent_corruption",
            "data_directory_structure_valid",
        ],
        "drift_warnings": [
            "no_data_integrity_checksum",
            "backup_and_restore_not_tested",
        ],
        "drift_blockers": [],
        "drift_risk_level": "low",
        "drift_recommendations": [
            "add_data_integrity_checksums",
            "test_backup_and_restore_procedure",
        ],
        "drift_summary": "Data drift is low. File structure valid but integrity checksums absent.",
        "required_actions": [],
        "recommended_next_action": "add data integrity checksums and test backup/restore",
        "confidence_score": 0.72,
    },
    "deployment_drift": {
        "aliases": ["deploy", "deployment", "environment", "production", "release", "ortam"],
        "target_component": "deployment_environment_runtime",
        "drift_category": "environment_consistency",
        "drift_status": "warning",
        "drift_score": 0.46,
        "drift_findings": [
            "environment_parity_not_verified",
            "no_infrastructure_as_code",
        ],
        "drift_warnings": [
            "manual_deployment_steps_subject_to_error",
            "no_environment_config_diff_tool",
        ],
        "drift_blockers": [],
        "drift_risk_level": "medium",
        "drift_recommendations": [
            "verify_environment_parity",
            "adopt_infrastructure_as_code",
            "automate_environment_config_diff_check",
        ],
        "drift_summary": "Deployment drift is at medium risk. Environment parity between dev and production unverified.",
        "required_actions": [],
        "recommended_next_action": "verify environment parity and adopt infrastructure as code",
        "confidence_score": 0.72,
    },
    "security_drift": {
        "aliases": ["security", "auth", "cors", "token", "guvenlik"],
        "target_component": "security_posture_runtime",
        "drift_category": "security_consistency",
        "drift_status": "warning",
        "drift_score": 0.50,
        "drift_findings": [
            "cors_policy_permissive",
            "no_rate_limiting_middleware",
        ],
        "drift_warnings": [
            "security_headers_not_set",
            "auth_token_rotation_not_scheduled",
        ],
        "drift_blockers": [],
        "drift_risk_level": "medium",
        "drift_recommendations": [
            "tighten_cors_policy",
            "add_rate_limiting_middleware",
            "add_security_headers_to_responses",
            "schedule_auth_token_rotation",
        ],
        "drift_summary": "Security drift is at medium risk. CORS policy is permissive and security headers absent.",
        "required_actions": [],
        "recommended_next_action": "tighten CORS policy, add rate limiting, and set security headers",
        "confidence_score": 0.68,
    },
    "behavioral_drift": {
        "aliases": ["behavior", "behaviour", "flow", "runtime_flow", "davranis"],
        "target_component": "runtime_behavior_runtime",
        "drift_category": "behavioral_consistency",
        "drift_status": "pass",
        "drift_score": 0.80,
        "drift_findings": [
            "stop_continue_flow_verified",
            "chat_response_pattern_consistent",
        ],
        "drift_warnings": [
            "typewriter_queue_behavior_not_formalized",
            "websocket_done_signal_ordering_not_validated",
        ],
        "drift_blockers": [],
        "drift_risk_level": "low",
        "drift_recommendations": [
            "formalize_typewriter_queue_behavior",
            "validate_websocket_done_signal_ordering",
        ],
        "drift_summary": "Behavioral drift is low. Core flows consistent but queue behavior needs formal definition.",
        "required_actions": [],
        "recommended_next_action": "formalize typewriter queue behavior and validate done signal ordering",
        "confidence_score": 0.76,
    },
    "memory_drift": {
        "aliases": ["memory", "ram", "leak", "allocation", "bellek"],
        "target_component": "memory_runtime",
        "drift_category": "memory_consistency",
        "drift_status": "warning",
        "drift_score": 0.52,
        "drift_findings": [
            "memory_usage_trend_not_monitored",
            "no_memory_leak_detection",
        ],
        "drift_warnings": [
            "large_context_window_may_cause_growth",
            "session_data_accumulates_indefinitely",
        ],
        "drift_blockers": [],
        "drift_risk_level": "medium",
        "drift_recommendations": [
            "monitor_memory_usage_over_time",
            "implement_memory_leak_detection",
            "add_session_data_retention_policy",
        ],
        "drift_summary": "Memory drift is at medium risk. Usage trends not monitored and leak detection absent.",
        "required_actions": [],
        "recommended_next_action": "monitor memory usage trends and implement leak detection",
        "confidence_score": 0.64,
    },
}


def _select_drift_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    for key, profile in DRIFT_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(t.lower() in aliases or t.lower() == key for t in targets for t2 in [t]):
            for target in targets:
                tl = target.lower().strip()
                if tl in aliases or tl == key:
                    return key
    return "config_drift"


def runtime_drift_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "31.4",
        "name": "Runtime Drift Intelligence Preview",
        "status": "runtime_drift_intelligence_ready",
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
            "/debug/runtime-drift-status",
            "/debug/runtime-drift-registry",
            "/debug/runtime-drift-preview",
        ],
        "connected_layers": [
            "31.3", "31.2", "31.1", "30", "30.1", "30.2", "30.3", "30.4", "30.5",
            "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
        ],
        "safety_note": "Read-only runtime drift intelligence preview. No actual drift remediation actions performed.",
    }


def runtime_drift_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for did, d in DRIFT_PROFILES.items():
        items.append(
            {
                "drift_id": did,
                "target_component": d["target_component"],
                "drift_category": d["drift_category"],
                "drift_status": d["drift_status"],
                "drift_score": d["drift_score"],
                "drift_risk_level": d["drift_risk_level"],
                "blocker_count": len(d.get("drift_blockers", [])),
                "warning_count": len(d.get("drift_warnings", [])),
                "confidence_score": d["confidence_score"],
            }
        )
    return {
        "layer": "31.4",
        "name": "Runtime Drift Intelligence Registry",
        "status": "runtime_drift_intelligence_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "drift_count": len(items),
        "drift_items": items,
        "pass_count": sum(1 for i in items if i["drift_status"] == "pass"),
        "warning_count": sum(1 for i in items if i["drift_status"] == "warning"),
        "degraded_count": sum(1 for i in items if i["drift_status"] == "degraded"),
        "blocked_count": sum(1 for i in items if i["drift_status"] == "blocked"),
        "overall_drift_score": round(
            sum(i["drift_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "overall_drift_status": _compute_overall_drift_status(items),
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


def _compute_overall_drift_status(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    statuses = [i.get("drift_status", "") for i in items]
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
    L = related_layer or "Layer 31.4"
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


def build_runtime_drift_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    did = _select_drift_profile(target_issue, command, project_area)
    d = DRIFT_PROFILES[did]
    detected = target_issue or project_area or did
    cmd = command or detected
    L = related_layer or "Layer 31.4"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "drift_id": did,
        "target_component": d["target_component"],
        "drift_category": d["drift_category"],
        "drift_status": d["drift_status"],
        "drift_score": d["drift_score"],
        "drift_findings": d.get("drift_findings", []),
        "drift_warnings": d.get("drift_warnings", []),
        "drift_blockers": d.get("drift_blockers", []),
        "drift_risk_level": d.get("drift_risk_level"),
        "drift_recommendations": d.get("drift_recommendations", []),
        "drift_summary": d.get("drift_summary"),
        "required_actions": d.get("required_actions", []),
        "recommended_next_action": d.get("recommended_next_action"),
        "confidence_score": d["confidence_score"],
        "drift_signals": integration,
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
        "safety_note": "Read-only runtime drift intelligence preview. No actual drift remediation actions performed.",
    }
