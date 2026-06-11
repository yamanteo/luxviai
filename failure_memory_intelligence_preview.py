from __future__ import annotations
from typing import Any, Dict, List, Optional

from regression_intelligence_preview import (
    build_regression_intelligence_preview,
    regression_intelligence_registry,
)
from runtime_anomaly_intelligence_preview import (
    build_runtime_anomaly_intelligence_preview,
    runtime_anomaly_intelligence_registry,
)
from layer31_status_snapshot import layer31_full_status, layer31_status_snapshot
from layer30_status_snapshot import layer30_full_status, layer30_status_snapshot
from layer29_status_snapshot import layer29_status_snapshot


FAILURE_MEMORY_PROFILES: Dict[str, Dict[str, Any]] = {
    "connection_failure": {
        "aliases": ["connection", "connect", "baglanti", "socket"],
        "target_component": "connection_runtime",
        "failure_category": "connection_failure",
        "failure_status": "degraded",
        "failure_score": 0.38,
        "failure_findings": [
            "connection_timeout_recurring_across_sessions",
            "socket_exhaustion_observed_under_load",
            "reconnect_attempts_failing_consistently",
        ],
        "failure_patterns": [
            "pattern: connection_reset_after_30s_idle",
            "pattern: exponential_backoff_not_triggering",
            "pattern: reconnect_loop_exceeds_max_attempts",
        ],
        "failure_recurrence_level": "high",
        "similar_failures": [
            "runtime_drift_intelligence: socket_failure_drift",
            "runtime_recovery_intelligence: connection_recovery_failure",
        ],
        "successful_resolutions": [
            "implemented_connection_pool_202605",
            "timeout_increased_to_60s_may_patch",
        ],
        "failed_resolutions": [
            "retry_interval_reduction_made_worse",
            "single_thread_reconnect_blocked_other_ops",
        ],
        "failure_risk_level": "high",
        "failure_summary": "Connection failures recurring across sessions. Socket exhaustion under load. Reconnect attempts failing consistently.",
        "required_actions": [
            "audit_connection_pool_implementation",
            "fix_reconnect_backoff_strategy",
            "add_connection_leak_detection",
        ],
        "recommended_next_action": "audit connection pool and fix reconnect backoff strategy",
        "confidence_score": 0.68,
        "failure_signals": {
            "recurrence_rate_pct": 72,
            "affected_sessions": 14,
            "avg_timeout_ms": 30000,
        },
    },
    "timeout_failure": {
        "aliases": ["timeout", "time_out", "zaman_asimi"],
        "target_component": "timeout_runtime",
        "failure_category": "timeout_failure",
        "failure_status": "degraded",
        "failure_score": 0.42,
        "failure_findings": [
            "api_timeout_exceeded_on_retry_attempts",
            "stream_response_delayed_beyond_threshold",
            "websocket_keepalive_timeout_triggered",
        ],
        "failure_patterns": [
            "pattern: consistent_timeout_at_25s_mark",
            "pattern: timeout_chain_cascading_to_downstream",
            "pattern: timeout_on_first_attempt_always_fast",
        ],
        "failure_recurrence_level": "high",
        "similar_failures": [
            "runtime_stability_intelligence: timeout_related_degradation",
            "regression_intelligence: endpoint_response_time_regression",
        ],
        "successful_resolutions": [
            "stream_timeout_adjusted_from_20s_to_45s",
            "retry_delay_increased_reduced_cascade",
        ],
        "failed_resolutions": [
            "reducing_timeout_caused_premature_termination",
            "removing_timeout_entirely_caused_hung_connections",
        ],
        "failure_risk_level": "high",
        "failure_summary": "Timeout failures recurring at consistent intervals. Cascade effect observed across downstream components.",
        "required_actions": [
            "implement_adaptive_timeout_strategy",
            "add_timeout_cascade_breaker",
            "monitor_timeout_patterns_per_endpoint",
        ],
        "recommended_next_action": "implement adaptive timeout strategy and cascade breaker",
        "confidence_score": 0.72,
        "failure_signals": {
            "avg_timeout_seconds": 25,
            "cascade_failures": 6,
            "endpoints_affected": 4,
        },
    },
    "dependency_failure": {
        "aliases": ["dependency", "dep", "import", "module", "bagimlilik"],
        "target_component": "dependency_runtime",
        "failure_category": "dependency_failure",
        "failure_status": "warning",
        "failure_score": 0.55,
        "failure_findings": [
            "external_api_dependency_failure_during_peak",
            "fallback_activated_on_primary_dependency_loss",
            "dependency_version_mismatch_causing_import_errors",
        ],
        "failure_patterns": [
            "pattern: dependency_failure_during_high_concurrency",
            "pattern: fallback_fails_silently_no_alert",
            "pattern: stale_dependency_version_cached",
        ],
        "failure_recurrence_level": "medium",
        "similar_failures": [
            "anomaly_intelligence: dependency_anomaly_detected",
            "regression_intelligence: dependency_regression_warning",
        ],
        "successful_resolutions": [
            "fallback_provider_added_for_external_api",
            "dependency_cache_cleared_on_boot",
        ],
        "failed_resolutions": [
            "version_pin_removed_caused_regression",
            "direct_import_bypass_skipped_validation",
        ],
        "failure_risk_level": "medium",
        "failure_summary": "External dependency failures during peak load. Fallback activated but no alert on fallback failure.",
        "required_actions": [
            "add_dependency_failure_alerting",
            "test_fallback_paths_regularly",
            "implement_circuit_breaker_for_external_deps",
        ],
        "recommended_next_action": "add dependency failure alerting and test fallback paths",
        "confidence_score": 0.76,
        "failure_signals": {
            "downtime_minutes": 45,
            "dependencies_affected": 2,
            "fallback_activated_count": 8,
        },
    },
    "recovery_failure": {
        "aliases": ["recovery", "failover", "retry", "kurtarma"],
        "target_component": "recovery_runtime",
        "failure_category": "recovery_failure",
        "failure_status": "degraded",
        "failure_score": 0.35,
        "failure_findings": [
            "auto_recovery_attempts_unsuccessful_across_restarts",
            "failover_not_triggered_during_critical_failure",
            "recovery_strategy_not_persisting_after_restart",
        ],
        "failure_patterns": [
            "pattern: recovery_attempt_fails_then_no_escalation",
            "pattern: failover_triggered_too_late_after_timeout",
            "pattern: recovery_state_lost_on_process_restart",
        ],
        "failure_recurrence_level": "critical",
        "similar_failures": [
            "recovery_anomaly: failover_misconfiguration",
            "recovery_regression: failover_response_time_increased",
            "runtime_recovery_intelligence: recovery_loop_stall",
        ],
        "successful_resolutions": [
            "manual_recovery_procedure_documented",
            "recovery_checkpoint_added_to_persistent_store",
        ],
        "failed_resolutions": [
            "auto_recovery_without_state_check_caused_loop",
            "failover_test_scheduled_but_not_executed",
        ],
        "failure_risk_level": "critical",
        "failure_summary": "Auto-recovery failing across restarts. Failover not triggering during critical failures. Recovery state lost.",
        "required_actions": [
            "implement_persistent_recovery_state",
            "fix_failover_trigger_conditions",
            "schedule_and_execute_failover_test",
        ],
        "recommended_next_action": "implement persistent recovery state and fix failover trigger conditions",
        "confidence_score": 0.60,
        "failure_signals": {
            "recovery_attempts": 15,
            "successful_recoveries": 2,
            "failover_triggered": False,
        },
    },
    "configuration_failure": {
        "aliases": ["config", "configuration", "setting", "env", "yapilandirma"],
        "target_component": "configuration_runtime",
        "failure_category": "configuration_failure",
        "failure_status": "warning",
        "failure_score": 0.58,
        "failure_findings": [
            "env_config_mismatch_caused_deployment_failure",
            "missing_config_key_triggered_fallback_degradation",
            "config_reload_failed_without_error_log",
        ],
        "failure_patterns": [
            "pattern: config_failure_on_first_deploy_after_change",
            "pattern: missing_key_reported_as_warning_not_error",
            "pattern: stale_config_cached_after_reload_failure",
        ],
        "failure_recurrence_level": "medium",
        "similar_failures": [
            "configuration_anomaly: missing_env_keys",
            "configuration_regression: config_regression_pass",
        ],
        "successful_resolutions": [
            "config_validation_hook_added_to_deploy_pipeline",
            "required_keys_documented_in_readme",
        ],
        "failed_resolutions": [
            "silent_fallback_extended_critical_keys",
            "config_change_without_test_caused_outage",
        ],
        "failure_risk_level": "medium",
        "failure_summary": "Configuration failures during deployment. Missing keys trigger fallback without clear error.",
        "required_actions": [
            "enforce_config_validation_at_startup",
            "add_config_reload_error_logging",
            "implement_config_diff_in_deploy_pipeline",
        ],
        "recommended_next_action": "enforce config validation at startup and add reload error logging",
        "confidence_score": 0.78,
        "failure_signals": {
            "deployment_failures": 3,
            "fallback_activations": 7,
            "silent_failures": 2,
        },
    },
    "runtime_failure": {
        "aliases": ["runtime", "execution", "crash", "panic", "calisma"],
        "target_component": "runtime_crash_monitor",
        "failure_category": "runtime_failure",
        "failure_status": "degraded",
        "failure_score": 0.40,
        "failure_findings": [
            "unexpected_crash_on_concurrent_session_limit",
            "runtime_state_corruption_after_forced_stop",
            "execution_flow_interrupted_by_unhandled_exception",
        ],
        "failure_patterns": [
            "pattern: crash_on_third_concurrent_session",
            "pattern: state_corruption_on_SIGTERM_during_write",
            "pattern: exception_not_caught_in_async_handler",
        ],
        "failure_recurrence_level": "high",
        "similar_failures": [
            "runtime_behavior_anomaly: state_transition_divergence",
            "runtime_regression: execution_path_divergence",
        ],
        "successful_resolutions": [
            "concurrency_limit_added_to_session_handler",
            "crash_recovery_added_to_boot_sequence",
        ],
        "failed_resolutions": [
            "removing_concurrency_limit_increased_crashes",
            "logging_exception_without_handler_didnt_resolve",
        ],
        "failure_risk_level": "high",
        "failure_summary": "Runtime crashes on concurrent session limit. State corruption after forced stop. Unhandled exceptions in async handlers.",
        "required_actions": [
            "implement_graceful_shutdown_handler",
            "add_crash_recovery_with_state_validation",
            "audit_async_exception_handling",
        ],
        "recommended_next_action": "implement graceful shutdown and add crash recovery with state validation",
        "confidence_score": 0.65,
        "failure_signals": {
            "crash_count": 8,
            "state_corruption_events": 3,
            "unhandled_exceptions": 5,
        },
    },
    "endpoint_failure": {
        "aliases": ["endpoint", "route", "api", "uç nokta"],
        "target_component": "endpoint_failure_runtime",
        "failure_category": "endpoint_failure",
        "failure_status": "pass",
        "failure_score": 0.78,
        "failure_findings": [
            "no_recent_endpoint_failures_recorded",
            "all_routes_responding_within_threshold",
            "error_rate_below_acceptable_limit",
        ],
        "failure_patterns": [
            "pattern: historical_endpoint_failure_at_high_load",
            "pattern: memory_leak_after_repeated_calls",
        ],
        "failure_recurrence_level": "low",
        "similar_failures": [
            "endpoint_anomaly: stale_endpoint_registration",
            "endpoint_regression: response_time_increased",
        ],
        "successful_resolutions": [
            "rate_limiting_added_to_high_traffic_endpoints",
            "load_testing_implemented_before_deploy",
        ],
        "failed_resolutions": [],
        "failure_risk_level": "low",
        "failure_summary": "No recent endpoint failures. Error rate within limits. Historical patterns documented for load scenarios.",
        "required_actions": [],
        "recommended_next_action": "continue monitoring endpoint health with automated alerting",
        "confidence_score": 0.82,
        "failure_signals": {
            "recent_failures": 0,
            "error_rate_pct": 0.5,
            "routes_healthy": 42,
        },
    },
}


def _select_failure_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in FAILURE_MEMORY_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "connection_failure"


def _compute_overall_failure_status(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    statuses = [i.get("failure_status", "") for i in items]
    if any(s == "blocked" for s in statuses):
        return "blocked"
    if any(s == "degraded" for s in statuses):
        return "degraded"
    if any(s == "warning" for s in statuses):
        return "warning"
    if all(s == "pass" for s in statuses):
        return "pass"
    return "warning"


def _compute_risk_score(items: List[Dict[str, Any]]) -> str:
    levels = [i.get("failure_risk_level", "low") for i in items]
    if any(l == "critical" for l in levels):
        return "critical"
    if any(l == "high" for l in levels):
        return "high"
    if any(l == "medium" for l in levels):
        return "medium"
    return "low"


def failure_memory_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "32.3",
        "name": "Failure Memory Intelligence Preview",
        "status": "failure_memory_intelligence_ready",
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
            "/debug/failure-memory-status",
            "/debug/failure-memory-registry",
            "/debug/failure-memory-preview",
        ],
        "connected_layers": [
            "32.2", "32.1", "31.5", "31.4", "31.3", "31.2", "31.1",
            "31", "30", "30.5", "30.4", "30.3", "30.2", "30.1",
            "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
        ],
        "safety_note": "Read-only failure memory intelligence preview. No actual failure remediation actions performed.",
    }


def failure_memory_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for fid, f in FAILURE_MEMORY_PROFILES.items():
        items.append(
            {
                "failure_id": fid,
                "target_component": f["target_component"],
                "failure_category": f["failure_category"],
                "failure_status": f["failure_status"],
                "failure_score": f["failure_score"],
                "failure_recurrence_level": f["failure_recurrence_level"],
                "failure_risk_level": f["failure_risk_level"],
                "pattern_count": len(f.get("failure_patterns", [])),
                "similar_failure_count": len(f.get("similar_failures", [])),
                "confidence_score": f["confidence_score"],
            }
        )
    return {
        "layer": "32.3",
        "name": "Failure Memory Intelligence Registry",
        "status": "failure_memory_intelligence_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "failure_count": len(items),
        "failure_items": items,
        "pass_count": sum(1 for i in items if i["failure_status"] == "pass"),
        "warning_count": sum(1 for i in items if i["failure_status"] == "warning"),
        "degraded_count": sum(1 for i in items if i["failure_status"] == "degraded"),
        "blocked_count": sum(1 for i in items if i["failure_status"] == "blocked"),
        "overall_failure_score": round(
            sum(i["failure_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "overall_failure_status": _compute_overall_failure_status(items),
        "overall_failure_risk_level": _compute_risk_score(items),
        "recurrence_breakdown": {
            "critical": sum(1 for i in items if i["failure_recurrence_level"] == "critical"),
            "high": sum(1 for i in items if i["failure_recurrence_level"] == "high"),
            "medium": sum(1 for i in items if i["failure_recurrence_level"] == "medium"),
            "low": sum(1 for i in items if i["failure_recurrence_level"] == "low"),
        },
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
    L = related_layer or "Layer 32.3"
    layer31 = layer31_full_status()
    layer30 = layer30_full_status()
    layer29 = layer29_status_snapshot()
    regression_reg = regression_intelligence_registry()
    anomaly_reg = runtime_anomaly_intelligence_registry()

    return {
        "layer32_2_regression_intelligence": {
            "regression_count": regression_reg.get("regression_count"),
            "overall_regression_score": regression_reg.get("overall_regression_score"),
            "overall_regression_status": regression_reg.get("overall_regression_status"),
        },
        "layer32_1_anomaly_intelligence": {
            "anomaly_count": anomaly_reg.get("anomaly_count"),
            "overall_anomaly_score": anomaly_reg.get("overall_anomaly_score"),
            "overall_anomaly_status": anomaly_reg.get("overall_anomaly_status"),
        },
        "layer31_status_snapshot": {
            "snapshot_status": layer31.get("snapshot_status"),
            "layer_31_complete": layer31.get("layer_31_complete"),
            "overall_runtime_score": layer31.get("overall_runtime_score"),
        },
        "layer30_status_snapshot": {
            "snapshot_status": layer30.get("snapshot_status"),
            "layer_30_complete": layer30.get("layer_30_complete"),
        },
        "layer29_status_snapshot": {
            "snapshot_status": layer29.get("snapshot_status"),
            "layer_29_complete": layer29.get("layer_29_complete"),
        },
    }


def build_failure_memory_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    fid = _select_failure_profile(target_issue, command, project_area)
    f = FAILURE_MEMORY_PROFILES[fid]
    detected = target_issue or project_area or fid
    cmd = command or detected
    L = related_layer or "Layer 32.3"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "failure_id": fid,
        "target_component": f["target_component"],
        "failure_category": f["failure_category"],
        "failure_status": f["failure_status"],
        "failure_score": f["failure_score"],
        "failure_findings": f.get("failure_findings", []),
        "failure_patterns": f.get("failure_patterns", []),
        "failure_recurrence_level": f.get("failure_recurrence_level"),
        "similar_failures": f.get("similar_failures", []),
        "successful_resolutions": f.get("successful_resolutions", []),
        "failed_resolutions": f.get("failed_resolutions", []),
        "failure_risk_level": f.get("failure_risk_level"),
        "failure_summary": f.get("failure_summary"),
        "required_actions": f.get("required_actions", []),
        "recommended_next_action": f.get("recommended_next_action"),
        "confidence_score": f["confidence_score"],
        "failure_signals": f.get("failure_signals", {}),
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
        "safety_note": "Read-only failure memory intelligence preview. No actual failure remediation actions performed.",
    }
