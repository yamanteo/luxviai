from __future__ import annotations
from typing import Any, Dict, List, Optional

from failure_memory_intelligence_preview import (
    build_failure_memory_intelligence_preview,
    failure_memory_intelligence_registry,
)
from dependency_intelligence_preview import (
    build_dependency_intelligence_preview,
    dependency_intelligence_registry,
)
from regression_intelligence_preview import (
    regression_intelligence_registry,
)
from runtime_anomaly_intelligence_preview import (
    runtime_anomaly_intelligence_registry,
)
from layer31_status_snapshot import layer31_full_status, layer31_status_snapshot
from layer30_status_snapshot import layer30_full_status, layer30_status_snapshot
from layer29_status_snapshot import layer29_status_snapshot


ROOT_CAUSE_PROFILES: Dict[str, Dict[str, Any]] = {
    "dependency_root_cause": {
        "aliases": ["dependency", "bagimlilik", "import", "module", "dep"],
        "root_cause_category": "dependency_root_cause",
        "root_cause_status": "degraded",
        "root_cause_score": 0.38,
        "root_cause_findings": [
            "circular_import_chain_between_app_and_fault_report",
            "missing_dependency_version_pinning",
            "external_api_single_point_of_failure",
            "fallback_path_not_fully_integrated",
        ],
        "probable_causes": [
            "import_graph_not_audited_during_development",
            "external_api_considered_always_available",
            "dependency_version_bump_without_regression_check",
        ],
        "contributing_factors": [
            "no_import_boundary_tests",
            "dependency_lock_not_enforced",
            "multiple_teams_touching_shared_modules",
        ],
        "dependency_links": [
            "dependency_intelligence: circular_import_detected",
            "anomaly_intelligence: dependency_anomaly_detected",
            "regression_intelligence: dependency_regression_warning",
        ],
        "trigger_chain": [
            "module_a_imports_module_b",
            "module_b_imports_module_c",
            "module_c_imports_module_a",
            "circular_import_blocks_loading",
        ],
        "cause_confidence": 0.72,
        "root_cause_risk_level": "high",
        "root_cause_summary": "Dependency root cause identified — circular import chain between app.py and lux_fault_report.py. External API dependency is a single point of failure with incomplete fallback.",
        "required_actions": [
            "break_circular_import_chain",
            "pin_all_dependency_versions",
            "implement_multi_provider_failover",
        ],
        "recommended_next_action": "break circular import chain between app.py and lux_fault_report.py",
        "confidence_score": 0.72,
        "root_cause_signals": {
            "circular_paths": 1,
            "external_spof_count": 1,
            "unpinned_deps": 4,
        },
    },
    "configuration_root_cause": {
        "aliases": ["config", "configuration", "setting", "env", "yapilandirma"],
        "root_cause_category": "configuration_root_cause",
        "root_cause_status": "warning",
        "root_cause_score": 0.55,
        "root_cause_findings": [
            "env_file_missing_required_keys",
            "fallback_values_active_for_critical_settings",
            "configuration_validation_not_enforced",
            "sensitive_config_exposed_in_logs",
        ],
        "probable_causes": [
            "configuration_loaded_without_schema_validation",
            "env_template_not_kept_in_sync",
            "fallback_values_used_as_defaults_without_warning",
        ],
        "contributing_factors": [
            "no_config_schema_definition",
            "deployment_pipeline_does_not_validate_config",
            "multiple_config_sources_without_override_documentation",
        ],
        "dependency_links": [
            "anomaly_intelligence: configuration_anomaly_detected",
            "regression_intelligence: configuration_regression_warning",
        ],
        "trigger_chain": [
            "app_boot_loads_env_file",
            "missing_key_triggers_fallback",
            "fallback_value_is_stale_or_incorrect",
            "runtime_behavior_deviates_from_expected",
        ],
        "cause_confidence": 0.74,
        "root_cause_risk_level": "medium",
        "root_cause_summary": "Configuration root cause — missing required environment keys trigger fallback values. Configuration validation not enforced at boot time.",
        "required_actions": [
            "add_config_schema_validation",
            "mask_sensitive_config_in_logs",
            "enforce_env_template_sync",
        ],
        "recommended_next_action": "add configuration schema validation and enforce env template sync",
        "confidence_score": 0.74,
        "root_cause_signals": {
            "missing_keys": 3,
            "fallback_values_active": 2,
            "validation_enabled": False,
        },
    },
    "runtime_root_cause": {
        "aliases": ["runtime", "execution", "flow", "calisma", "run"],
        "root_cause_category": "runtime_root_cause",
        "root_cause_status": "degraded",
        "root_cause_score": 0.42,
        "root_cause_findings": [
            "unexpected_state_transition_sequence",
            "runtime_execution_path_divergence",
            "recovery_loop_exceeded_max_retries",
            "typewriter_queue_desync_observed",
        ],
        "probable_causes": [
            "state_machine_not_fully_documented",
            "execution_path_trace_incomplete",
            "concurrent_state_modification_without_locking",
        ],
        "contributing_factors": [
            "no_runtime_state_invariants_defined",
            "state_transition_logging_insufficient",
            "async_event_ordering_not_guaranteed",
        ],
        "dependency_links": [
            "anomaly_intelligence: runtime_behavior_anomaly",
            "failure_memory: execution_path_failure",
            "runtime_stability_intelligence: state_machine_risk",
        ],
        "trigger_chain": [
            "async_event_received_out_of_order",
            "state_transition_applied_on_stale_state",
            "invariant_violation_not_detected",
            "runtime_path_divergence_propagates",
        ],
        "cause_confidence": 0.68,
        "root_cause_risk_level": "high",
        "root_cause_summary": "Runtime root cause — unexpected state transitions and execution path divergence. Asynchronous event ordering not guaranteed. Typewriter queue desynchronization observed.",
        "required_actions": [
            "document_state_machine_completely",
            "add_state_invariant_checks",
            "implement_async_event_ordering",
        ],
        "recommended_next_action": "document state machine and add runtime invariant checks",
        "confidence_score": 0.68,
        "root_cause_signals": {
            "state_transition_anomalies": 3,
            "recovery_loop_exceeded": 2,
            "desync_events": 1,
        },
    },
    "integration_root_cause": {
        "aliases": ["integration", "entegrasyon", "interface", "arayuz", "api"],
        "root_cause_category": "integration_root_cause",
        "root_cause_status": "warning",
        "root_cause_score": 0.52,
        "root_cause_findings": [
            "api_contract_mismatch_between_services",
            "integration_test_coverage_below_threshold",
            "interface_version_mismatch_on_deploy",
            "cross_service_timeout_not_configured",
        ],
        "probable_causes": [
            "api_contract_not_versioned",
            "integration_tests_not_run_in_ci",
            "interface_changes_communicated_asynchronously",
        ],
        "contributing_factors": [
            "service_boundaries_not_clearly_defined",
            "no_contract_testing_framework",
            "deploy_order_dependency_between_services",
        ],
        "dependency_links": [
            "dependency_intelligence: integration_dependency_risk",
            "runtime_stability_intelligence: cross_service_timeout",
            "regression_intelligence: endpoint_regression",
        ],
        "trigger_chain": [
            "service_a_updates_interface",
            "service_b_still_uses_old_contract",
            "integration_test_does_not_catch_mismatch",
            "runtime_error_on_cross_service_call",
        ],
        "cause_confidence": 0.70,
        "root_cause_risk_level": "medium",
        "root_cause_summary": "Integration root cause — API contract mismatch between services. Integration test coverage below threshold. Interface version not tracked during deploy.",
        "required_actions": [
            "implement_contract_testing",
            "version_all_api_interfaces",
            "add_integration_test_gate_to_ci",
        ],
        "recommended_next_action": "implement contract testing and version all API interfaces",
        "confidence_score": 0.70,
        "root_cause_signals": {
            "contract_mismatches": 2,
            "test_coverage_pct": 35,
            "unversioned_interfaces": 3,
        },
    },
    "logic_root_cause": {
        "aliases": ["logic", "mantik", "algorithm", "algoritma", "business", "is"],
        "root_cause_category": "logic_root_cause",
        "root_cause_status": "warning",
        "root_cause_score": 0.58,
        "root_cause_findings": [
            "business_logic_edge_case_not_handled",
            "conditional_branch_always_evaluates_to_false",
            "loop_termination_condition_never_met",
            "incorrect_default_value_in_switch_case",
        ],
        "probable_causes": [
            "requirement_misunderstood_during_implementation",
            "edge_case_not_identified_in_design_review",
            "defensive_programming_not_practiced",
        ],
        "contributing_factors": [
            "code_review_skipped_for_tight_deadline",
            "unit_test_coverage_gap_on_logic_paths",
            "no_fuzz_testing_on_input_handling",
        ],
        "dependency_links": [
            "regression_intelligence: behavior_regression",
            "failure_memory: logic_failure_pattern",
        ],
        "trigger_chain": [
            "unexpected_input_reaches_function",
            "edge_case_not_handled_in_conditional",
            "incorrect_result_produced",
            "downstream_depends_on_correct_result_fails",
        ],
        "cause_confidence": 0.76,
        "root_cause_risk_level": "medium",
        "root_cause_summary": "Logic root cause — business logic edge case not handled. Conditional branch always evaluates to uncovered path. Unit test coverage gap on critical logic paths.",
        "required_actions": [
            "add_unit_tests_for_missing_edge_cases",
            "enforce_code_review_for_logic_changes",
            "implement_fuzz_testing_on_input_handling",
        ],
        "recommended_next_action": "add unit tests for uncovered edge cases and enforce code review",
        "confidence_score": 0.76,
        "root_cause_signals": {
            "uncovered_branches": 2,
            "edge_cases_missing": 3,
            "review_skipped_count": 1,
        },
    },
    "workflow_root_cause": {
        "aliases": ["workflow", "work_flow", "process", "is_akis", "pipeline"],
        "root_cause_category": "workflow_root_cause",
        "root_cause_status": "warning",
        "root_cause_score": 0.60,
        "root_cause_findings": [
            "workflow_step_executed_out_of_order",
            "missing_validation_gate_between_steps",
            "workflow_rollback_not_implemented",
            "pipeline_state_persistence_inconsistent",
        ],
        "probable_causes": [
            "workflow_dependency_not_formally_defined",
            "parallel_step_coordination_missing",
            "state_persistence_not_transactional",
        ],
        "contributing_factors": [
            "workflow_engine_does_not_enforce_ordering",
            "no_workflow_validation_gate_framework",
            "rollback_strategy_not_documented",
        ],
        "dependency_links": [
            "runtime_recovery_intelligence: workflow_recovery_failure",
            "runtime_drift_intelligence: pipeline_drift",
        ],
        "trigger_chain": [
            "step_a_completes_with_warning",
            "step_b_depends_on_step_a_success",
            "step_b_starts_before_step_a_validated",
            "inconsistent_state_propagates",
        ],
        "cause_confidence": 0.66,
        "root_cause_risk_level": "medium",
        "root_cause_summary": "Workflow root cause — step execution order not enforced. Missing validation gates between pipeline stages. Rollback path not implemented.",
        "required_actions": [
            "formalize_workflow_dependency_graph",
            "add_validation_gates_between_steps",
            "implement_workflow_rollback",
        ],
        "recommended_next_action": "formalize workflow dependency graph and add validation gates",
        "confidence_score": 0.66,
        "root_cause_signals": {
            "ordering_violations": 2,
            "missing_gates": 3,
            "rollback_readiness_pct": 20,
        },
    },
    "recovery_root_cause": {
        "aliases": ["recovery", "kurtarma", "retry", "yeniden", "failover"],
        "root_cause_category": "recovery_root_cause",
        "root_cause_status": "degraded",
        "root_cause_score": 0.45,
        "root_cause_findings": [
            "recovery_mechanism_not_triggering_on_failure",
            "retry_strategy_causes_thundering_herd",
            "failover_path_not_tested_recently",
            "recovery_time_exceeds_sla_threshold",
        ],
        "probable_causes": [
            "recovery_path_not_included_in_regular_tests",
            "retry_backoff_strategy_not_tuned",
            "failover_assumed_to_work_without_verification",
        ],
        "contributing_factors": [
            "no_recovery_drill_scheduled",
            "recovery_metrics_not_monitored",
            "failover_documentation_outdated",
        ],
        "dependency_links": [
            "runtime_recovery_intelligence: recovery_path_failure",
            "failure_memory: recovery_failure_pattern",
            "runtime_stability_intelligence: failover_readiness",
        ],
        "trigger_chain": [
            "primary_component_fails",
            "recovery_mechanism_activated",
            "recovery_itself_fails_due_to_stale_path",
            "degraded_state_becomes_permanent",
        ],
        "cause_confidence": 0.70,
        "root_cause_risk_level": "high",
        "root_cause_summary": "Recovery root cause — recovery mechanism not triggering correctly. Failover path not tested. Retry strategy causes cascading load on dependent systems.",
        "required_actions": [
            "test_recovery_path_regularly",
            "tune_retry_backoff_strategy",
            "implement_recovery_drill_schedule",
        ],
        "recommended_next_action": "test recovery paths regularly and tune retry backoff strategy",
        "confidence_score": 0.70,
        "root_cause_signals": {
            "recovery_failures": 2,
            "failover_last_tested_days": 90,
            "sla_exceeded_count": 3,
        },
    },
    "regression_root_cause": {
        "aliases": ["regression", "gerileme", "behavior", "davranis"],
        "root_cause_category": "regression_root_cause",
        "root_cause_status": "degraded",
        "root_cause_score": 0.40,
        "root_cause_findings": [
            "behavior_change_not_caught_by_tests",
            "regression_introduced_by_unrelated_change",
            "test_suite_did_not_cover_affected_behavior",
            "behavioral_baseline_not_established",
        ],
        "probable_causes": [
            "regression_test_suite_not_comprehensive",
            "behavioral_baseline_not_recorded",
            "test_gap_in_affected_component_area",
        ],
        "contributing_factors": [
            "no_automated_regression_detection",
            "behavioral_monitoring_not_deployed",
            "change_impact_analysis_not_performed",
        ],
        "dependency_links": [
            "regression_intelligence: behavior_regression",
            "regression_intelligence: endpoint_regression",
            "failure_memory: regression_failure_pattern",
        ],
        "trigger_chain": [
            "code_change_applied_to_unrelated_area",
            "behavioral_drift_in_adjacent_component",
            "regression_not_caught_by_test_suite",
            "production_behavior_deviates_from_expected",
        ],
        "cause_confidence": 0.66,
        "root_cause_risk_level": "high",
        "root_cause_summary": "Regression root cause — behavior change not caught by test suite. Behavioral baseline not established. Regression detection not automated.",
        "required_actions": [
            "establish_behavioral_baseline",
            "expand_regression_test_coverage",
            "implement_automated_regression_detection",
        ],
        "recommended_next_action": "establish behavioral baseline and expand regression test coverage",
        "confidence_score": 0.66,
        "root_cause_signals": {
            "behavior_regressions": 2,
            "endpoint_regressions": 1,
            "baseline_gap_pct": 60,
        },
    },
}


def _select_root_cause_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in ROOT_CAUSE_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "dependency_root_cause"


def _compute_overall_root_cause_status(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    statuses = [i.get("root_cause_status", "") for i in items]
    if any(s == "blocked" for s in statuses):
        return "blocked"
    if any(s == "degraded" for s in statuses):
        return "degraded"
    if any(s == "warning" for s in statuses):
        return "warning"
    if all(s == "pass" for s in statuses):
        return "pass"
    return "warning"


def _compute_root_cause_risk_score(items: List[Dict[str, Any]]) -> str:
    levels = [i.get("root_cause_risk_level", "low") for i in items]
    if any(l == "critical" for l in levels):
        return "critical"
    if any(l == "high" for l in levels):
        return "high"
    if any(l == "medium" for l in levels):
        return "medium"
    return "low"


def root_cause_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "32.4",
        "name": "Root Cause Intelligence Preview",
        "status": "root_cause_intelligence_ready",
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
            "/debug/root-cause-status",
            "/debug/root-cause-registry",
            "/debug/root-cause-preview",
        ],
        "connected_layers": [
            "32.5", "32.3", "32.2", "32.1", "31.5", "31.4", "31.3", "31.2", "31.1",
            "31", "30", "30.5", "30.4", "30.3", "30.2", "30.1",
            "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
        ],
        "safety_note": "Read-only root cause intelligence preview. No actual root cause remediation actions performed.",
    }


def root_cause_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for rid, r in ROOT_CAUSE_PROFILES.items():
        items.append(
            {
                "root_cause_id": rid,
                "root_cause_category": r["root_cause_category"],
                "root_cause_status": r["root_cause_status"],
                "root_cause_score": r["root_cause_score"],
                "cause_confidence": r.get("cause_confidence", 0.0),
                "root_cause_risk_level": r.get("root_cause_risk_level"),
                "finding_count": len(r.get("root_cause_findings", [])),
                "trigger_chain_length": len(r.get("trigger_chain", [])),
                "confidence_score": r["confidence_score"],
            }
        )
    return {
        "layer": "32.4",
        "name": "Root Cause Intelligence Registry",
        "status": "root_cause_intelligence_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "root_cause_count": len(items),
        "root_cause_items": items,
        "pass_count": sum(1 for i in items if i["root_cause_status"] == "pass"),
        "warning_count": sum(1 for i in items if i["root_cause_status"] == "warning"),
        "degraded_count": sum(1 for i in items if i["root_cause_status"] == "degraded"),
        "blocked_count": sum(1 for i in items if i["root_cause_status"] == "blocked"),
        "overall_root_cause_score": round(
            sum(i["root_cause_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "overall_root_cause_status": _compute_overall_root_cause_status(items),
        "overall_root_cause_risk_level": _compute_root_cause_risk_score(items),
        "cause_confidence_breakdown": {
            "high_confidence": sum(1 for i in items if i.get("cause_confidence", 0) >= 0.7),
            "medium_confidence": sum(1 for i in items if 0.4 <= i.get("cause_confidence", 0) < 0.7),
            "low_confidence": sum(1 for i in items if i.get("cause_confidence", 0) < 0.4),
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
    L = related_layer or "Layer 32.4"
    layer31 = layer31_full_status()
    layer30 = layer30_full_status()
    layer29 = layer29_status_snapshot()
    dependency_reg = dependency_intelligence_registry()
    failure_reg = failure_memory_intelligence_registry()
    regression_reg = regression_intelligence_registry()
    anomaly_reg = runtime_anomaly_intelligence_registry()

    return {
        "layer32_5_dependency_intelligence": {
            "dependency_count": dependency_reg.get("dependency_count"),
            "overall_dependency_score": dependency_reg.get("overall_dependency_score"),
            "overall_dependency_status": dependency_reg.get("overall_dependency_status"),
        },
        "layer32_3_failure_memory_intelligence": {
            "failure_count": failure_reg.get("failure_count"),
            "overall_failure_score": failure_reg.get("overall_failure_score"),
            "overall_failure_status": failure_reg.get("overall_failure_status"),
        },
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


def build_root_cause_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    rid = _select_root_cause_profile(target_issue, command, project_area)
    r = ROOT_CAUSE_PROFILES[rid]
    detected = target_issue or project_area or rid
    cmd = command or detected
    L = related_layer or "Layer 32.4"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "root_cause_id": rid,
        "root_cause_category": r["root_cause_category"],
        "root_cause_status": r["root_cause_status"],
        "root_cause_score": r["root_cause_score"],
        "root_cause_findings": r.get("root_cause_findings", []),
        "probable_causes": r.get("probable_causes", []),
        "contributing_factors": r.get("contributing_factors", []),
        "dependency_links": r.get("dependency_links", []),
        "trigger_chain": r.get("trigger_chain", []),
        "cause_confidence": r.get("cause_confidence", 0.0),
        "root_cause_risk_level": r.get("root_cause_risk_level"),
        "root_cause_summary": r.get("root_cause_summary"),
        "required_actions": r.get("required_actions", []),
        "recommended_next_action": r.get("recommended_next_action"),
        "confidence_score": r["confidence_score"],
        "root_cause_signals": r.get("root_cause_signals", {}),
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
        "safety_note": "Read-only root cause intelligence preview. No actual root cause remediation actions performed.",
    }
