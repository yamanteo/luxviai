from __future__ import annotations
from typing import Any, Dict, List, Optional

from layer31_status_snapshot import layer31_full_status, layer31_status_snapshot
from layer30_status_snapshot import layer30_full_status, layer30_status_snapshot
from layer29_status_snapshot import layer29_status_snapshot
from system_health_intelligence_preview import system_health_intelligence_status
from runtime_stability_intelligence_preview import runtime_stability_intelligence_status
from runtime_risk_intelligence_preview import runtime_risk_intelligence_status
from runtime_drift_intelligence_preview import runtime_drift_intelligence_status
from runtime_recovery_intelligence_preview import runtime_recovery_intelligence_status
from patch_confidence_preview import build_patch_confidence_preview, patch_confidence_registry
from patch_assurance_preview import build_patch_assurance_preview, patch_assurance_registry
from patch_accountability_preview import build_patch_accountability_preview, patch_accountability_registry
from patch_oversight_preview import build_patch_oversight_preview, patch_oversight_registry
from patch_governance_preview import build_patch_governance_preview, patch_governance_registry
from patch_compliance_preview import build_patch_compliance_preview, patch_compliance_registry
from patch_policy_evaluation_preview import build_patch_policy_preview, patch_policy_registry
from patch_permission_enforcement_preview import build_patch_permission_preview, patch_permission_registry


ANOMALY_PROFILES: Dict[str, Dict[str, Any]] = {
    "performance_anomaly": {
        "aliases": ["performance", "perf", "latency", "throughput", "speed", "performans"],
        "target_component": "performance_runtime",
        "anomaly_category": "performance_anomaly",
        "anomaly_status": "warning",
        "anomaly_score": 0.62,
        "anomaly_findings": [
            "response_latency_spikes_detected",
            "throughput_degradation_observed",
            "concurrent_request_bottleneck_possible",
        ],
        "anomaly_warnings": [
            "no_performance_baseline_established",
            "latency_threshold_not_configured",
            "long_running_queries_unmonitored",
        ],
        "anomaly_blockers": [],
        "anomaly_risk_level": "medium",
        "anomaly_recommendations": [
            "establish_performance_baseline",
            "configure_latency_thresholds",
            "implement_query_performance_monitoring",
        ],
        "anomaly_summary": "Performance anomaly detected — latency spikes and throughput degradation observed. No baseline established.",
        "required_actions": [
            "establish_performance_baseline",
            "configure_alert_thresholds",
        ],
        "recommended_next_action": "establish performance baseline and configure latency alert thresholds",
        "confidence_score": 0.70,
        "anomaly_signals": {
            "latency_p95_ms": 420,
            "throughput_rps": 85,
            "error_rate_pct": 2.3,
        },
    },
    "dependency_anomaly": {
        "aliases": ["dependency", "dep", "import", "module", "bagimlilik"],
        "target_component": "dependency_resolution_runtime",
        "anomaly_category": "dependency_anomaly",
        "anomaly_status": "degraded",
        "anomaly_score": 0.45,
        "anomaly_findings": [
            "circular_dependency_chain_detected",
            "unresolved_import_at_startup",
            "version_mismatch_in_dependency_graph",
        ],
        "anomaly_warnings": [
            "fallback_import_path_active",
            "optional_dependency_not_verified",
        ],
        "anomaly_blockers": [
            "circular_dependency_blocks_module_loading",
        ],
        "anomaly_risk_level": "high",
        "anomaly_recommendations": [
            "resolve_circular_dependency_chain",
            "verify_all_import_paths_at_boot",
            "pin_dependency_versions",
        ],
        "anomaly_summary": "Dependency anomaly — circular dependency chain detected. Module loading partially blocked.",
        "required_actions": [
            "break_circular_dependency_chain",
            "verify_import_paths",
        ],
        "recommended_next_action": "break circular dependency chain and verify all import paths",
        "confidence_score": 0.78,
        "anomaly_signals": {
            "circular_chain_length": 3,
            "unresolved_imports": 2,
            "fallback_imports_active": 1,
        },
    },
    "configuration_anomaly": {
        "aliases": ["config", "configuration", "setting", "env", "yapilandirma"],
        "target_component": "configuration_loader_runtime",
        "anomaly_category": "configuration_anomaly",
        "anomaly_status": "warning",
        "anomaly_score": 0.55,
        "anomaly_findings": [
            "env_file_missing_required_keys",
            "fallback_values_active_for_critical_settings",
            "configuration_validation_not_enforced",
        ],
        "anomaly_warnings": [
            "sensitive_config_exposed_in_logs",
            "config_reload_not_supported",
        ],
        "anomaly_blockers": [],
        "anomaly_risk_level": "medium",
        "anomaly_recommendations": [
            "enforce_strict_configuration_validation",
            "mask_sensitive_values_in_logs",
            "implement_config_reload_without_restart",
        ],
        "anomaly_summary": "Configuration anomaly — required environment keys missing. Fallback values active for critical settings.",
        "required_actions": [
            "add_missing_environment_keys",
            "enforce_configuration_validation",
        ],
        "recommended_next_action": "add missing environment keys and enforce configuration validation",
        "confidence_score": 0.74,
        "anomaly_signals": {
            "missing_keys": 3,
            "fallback_values_active": 2,
            "validation_passed": False,
        },
    },
    "runtime_behavior_anomaly": {
        "aliases": ["runtime", "behavior", "execution", "flow", "calisma"],
        "target_component": "runtime_behavior_monitor",
        "anomaly_category": "runtime_behavior_anomaly",
        "anomaly_status": "degraded",
        "anomaly_score": 0.48,
        "anomaly_findings": [
            "unexpected_state_transition_sequence",
            "recovery_loop_exceeded_max_retries",
            "runtime_execution_path_divergence",
        ],
        "anomaly_warnings": [
            "state_transition_not_fully_documented",
            "execution_path_trace_incomplete",
        ],
        "anomaly_blockers": [
            "recovery_loop_stalls_normal_operation",
        ],
        "anomaly_risk_level": "high",
        "anomaly_recommendations": [
            "document_all_state_transitions",
            "implement_execution_path_tracing",
            "cap_recovery_loop_retries",
        ],
        "anomaly_summary": "Runtime behavior anomaly detected — unexpected state transitions and recovery loop stall observed.",
        "required_actions": [
            "document_and_validate_state_transitions",
            "cap_recovery_loop_retries",
        ],
        "recommended_next_action": "document state transitions and cap recovery loop retries",
        "confidence_score": 0.72,
        "anomaly_signals": {
            "unexpected_transitions": 4,
            "recovery_loop_retries": 7,
            "execution_divergence_count": 2,
        },
    },
    "endpoint_anomaly": {
        "aliases": ["endpoint", "route", "api", "endpoint", "uç nokta"],
        "target_component": "endpoint_runtime",
        "anomaly_category": "endpoint_anomaly",
        "anomaly_status": "warning",
        "anomaly_score": 0.58,
        "anomaly_findings": [
            "stale_endpoint_registration_detected",
            "unregistered_route_receiving_traffic",
            "endpoint_response_time_degraded",
        ],
        "anomaly_warnings": [
            "deprecated_routes_not_removed",
            "endpoint_versioning_not_implemented",
        ],
        "anomaly_blockers": [],
        "anomaly_risk_level": "medium",
        "anomaly_recommendations": [
            "remove_stale_endpoint_registrations",
            "implement_endpoint_versioning",
            "deprecate_unused_routes_formally",
        ],
        "anomaly_summary": "Endpoint anomaly — stale registrations and unregistered traffic detected. Response times degraded.",
        "required_actions": [
            "audit_and_clean_endpoint_registrations",
            "implement_endpoint_versioning_strategy",
        ],
        "recommended_next_action": "audit endpoint registrations and implement versioning strategy",
        "confidence_score": 0.69,
        "anomaly_signals": {
            "stale_endpoints": 3,
            "unregistered_traffic_routes": 1,
            "avg_response_time_ms": 650,
        },
    },
    "resource_usage_anomaly": {
        "aliases": ["resource", "memory", "cpu", "disk", "kaynak"],
        "target_component": "resource_monitoring_runtime",
        "anomaly_category": "resource_usage_anomaly",
        "anomaly_status": "warning",
        "anomaly_score": 0.52,
        "anomaly_findings": [
            "memory_usage_exceeds_expected_baseline",
            "cpu_spike_pattern_non_cyclic",
            "disk_io_latency_increased",
        ],
        "anomaly_warnings": [
            "no_resource_alert_thresholds_defined",
            "memory_leak_detection_not_active",
        ],
        "anomaly_blockers": [],
        "anomaly_risk_level": "medium",
        "anomaly_recommendations": [
            "define_resource_alert_thresholds",
            "enable_memory_leak_detection",
            "investigate_cpu_spike_patterns",
        ],
        "anomaly_summary": "Resource usage anomaly — memory and CPU patterns deviate from baseline. No thresholds configured.",
        "required_actions": [
            "define_resource_thresholds",
            "enable_memory_leak_detection",
        ],
        "recommended_next_action": "define resource thresholds and enable memory leak detection",
        "confidence_score": 0.71,
        "anomaly_signals": {
            "memory_mb": 1850,
            "cpu_pct": 78,
            "disk_io_latency_ms": 45,
        },
    },
    "session_anomaly": {
        "aliases": ["session", "user_session", "auth", "oturum"],
        "target_component": "session_management_runtime",
        "anomaly_category": "session_anomaly",
        "anomaly_status": "pass",
        "anomaly_score": 0.80,
        "anomaly_findings": [
            "session_isolation_verified",
            "user_state_persistence_consistent",
            "concurrent_session_limit_enforced",
        ],
        "anomaly_warnings": [
            "session_timeout_not_tuned",
            "session_audit_log_not_active",
        ],
        "anomaly_blockers": [],
        "anomaly_risk_level": "low",
        "anomaly_recommendations": [
            "tune_session_timeout_for_production",
            "enable_session_audit_logging",
        ],
        "anomaly_summary": "Session anomaly check passed. Session isolation and state persistence verified.",
        "required_actions": [],
        "recommended_next_action": "tune session timeout and enable audit logging",
        "confidence_score": 0.83,
        "anomaly_signals": {
            "active_sessions": 12,
            "session_timeout_minutes": 30,
            "concurrent_limit_per_user": 5,
        },
    },
    "recovery_anomaly": {
        "aliases": ["recovery", "failover", "retry", "kurtarma"],
        "target_component": "recovery_mechanism_runtime",
        "anomaly_category": "recovery_anomaly",
        "anomaly_status": "degraded",
        "anomaly_score": 0.38,
        "anomaly_findings": [
            "recovery_attempts_exceeding_threshold",
            "failover_not_triggered_on_timeout",
            "retry_exhaustion_without_escalation",
        ],
        "anomaly_warnings": [
            "recovery_strategy_not_documented",
            "failover_test_not_performed",
        ],
        "anomaly_blockers": [
            "failover_misconfiguration_blocks_recovery",
        ],
        "anomaly_risk_level": "high",
        "anomaly_recommendations": [
            "fix_failover_configuration",
            "document_and_test_recovery_strategies",
            "implement_retry_escalation_path",
        ],
        "anomaly_summary": "Recovery anomaly — recovery attempts exceed threshold. Failover misconfiguration blocks recovery.",
        "required_actions": [
            "fix_failover_configuration",
            "test_recovery_strategies",
        ],
        "recommended_next_action": "fix failover configuration and test recovery strategies immediately",
        "confidence_score": 0.65,
        "anomaly_signals": {
            "recovery_attempts": 12,
            "failover_triggered": False,
            "retry_exhaustion_count": 3,
        },
    },
}


def _select_anomaly_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in ANOMALY_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "runtime_behavior_anomaly"


def _compute_overall_anomaly_status(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    statuses = [i.get("anomaly_status", "") for i in items]
    if any(s == "blocked" for s in statuses):
        return "blocked"
    if any(s == "degraded" for s in statuses):
        return "degraded"
    if any(s == "warning" for s in statuses):
        return "warning"
    if all(s == "pass" for s in statuses):
        return "pass"
    return "warning"


def runtime_anomaly_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "32.1",
        "name": "Runtime Anomaly Intelligence Preview",
        "status": "runtime_anomaly_intelligence_ready",
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
            "/debug/runtime-anomaly-status",
            "/debug/runtime-anomaly-registry",
            "/debug/runtime-anomaly-preview",
        ],
        "connected_layers": [
            "31.5", "31.4", "31.3", "31.2", "31.1",
            "31", "30", "30.5", "30.4", "30.3", "30.2", "30.1",
            "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
        ],
        "safety_note": "Read-only runtime anomaly intelligence preview. No actual anomaly remediation actions performed.",
    }


def runtime_anomaly_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for aid, a in ANOMALY_PROFILES.items():
        items.append(
            {
                "anomaly_id": aid,
                "target_component": a["target_component"],
                "anomaly_category": a["anomaly_category"],
                "anomaly_status": a["anomaly_status"],
                "anomaly_score": a["anomaly_score"],
                "anomaly_risk_level": a["anomaly_risk_level"],
                "blocker_count": len(a.get("anomaly_blockers", [])),
                "warning_count": len(a.get("anomaly_warnings", [])),
                "confidence_score": a["confidence_score"],
            }
        )
    return {
        "layer": "32.1",
        "name": "Runtime Anomaly Intelligence Registry",
        "status": "runtime_anomaly_intelligence_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "anomaly_count": len(items),
        "anomaly_items": items,
        "pass_count": sum(1 for i in items if i["anomaly_status"] == "pass"),
        "warning_count": sum(1 for i in items if i["anomaly_status"] == "warning"),
        "degraded_count": sum(1 for i in items if i["anomaly_status"] == "degraded"),
        "blocked_count": sum(1 for i in items if i["anomaly_status"] == "blocked"),
        "overall_anomaly_score": round(
            sum(i["anomaly_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "overall_anomaly_status": _compute_overall_anomaly_status(items),
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


def _build_integration_signals(
    target: str, command: str, project_area: str, related_layer: str
) -> Dict[str, Any]:
    L = related_layer or "Layer 32.1"
    layer31 = layer31_full_status()
    layer30 = layer30_full_status()
    layer29 = layer29_status_snapshot()
    system_health = system_health_intelligence_status()
    stability = runtime_stability_intelligence_status()
    risk = runtime_risk_intelligence_status()
    drift = runtime_drift_intelligence_status()
    recovery = runtime_recovery_intelligence_status()

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
        "layer31_status_snapshot": {
            "snapshot_status": layer31.get("snapshot_status"),
            "layer_31_complete": layer31.get("layer_31_complete"),
            "overall_runtime_score": layer31.get("overall_runtime_score"),
        },
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
        "system_health_intelligence": {
            "status": system_health.get("status"),
            "health_score": system_health.get("health_score"),
        },
        "runtime_stability_intelligence": {
            "status": stability.get("status"),
        },
        "runtime_risk_intelligence": {
            "status": risk.get("status"),
        },
        "runtime_drift_intelligence": {
            "status": drift.get("status"),
        },
        "runtime_recovery_intelligence": {
            "status": recovery.get("status"),
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


def build_runtime_anomaly_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    aid = _select_anomaly_profile(target_issue, command, project_area)
    a = ANOMALY_PROFILES[aid]
    detected = target_issue or project_area or aid
    cmd = command or detected
    L = related_layer or "Layer 32.1"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "anomaly_id": aid,
        "target_component": a["target_component"],
        "anomaly_category": a["anomaly_category"],
        "anomaly_status": a["anomaly_status"],
        "anomaly_score": a["anomaly_score"],
        "anomaly_findings": a.get("anomaly_findings", []),
        "anomaly_warnings": a.get("anomaly_warnings", []),
        "anomaly_blockers": a.get("anomaly_blockers", []),
        "anomaly_risk_level": a.get("anomaly_risk_level"),
        "anomaly_recommendations": a.get("anomaly_recommendations", []),
        "anomaly_summary": a.get("anomaly_summary"),
        "required_actions": a.get("required_actions", []),
        "recommended_next_action": a.get("recommended_next_action"),
        "confidence_score": a["confidence_score"],
        "anomaly_signals": a.get("anomaly_signals", {}),
        "runtime_signals": integration,
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
        "safety_note": "Read-only runtime anomaly intelligence preview. No actual anomaly remediation actions performed.",
    }
