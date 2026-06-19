from __future__ import annotations
from typing import Any, Dict, List, Optional

from change_memory_intelligence_preview import (
    change_memory_intelligence_registry,
)
from dependency_intelligence_preview import (
    dependency_intelligence_registry,
)
from root_cause_intelligence_preview import (
    root_cause_intelligence_registry,
)
from failure_memory_intelligence_preview import (
    failure_memory_intelligence_registry,
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


FAILED_CHANGE_PROFILES: Dict[str, Dict[str, Any]] = {
    "repair_failure": {
        "aliases": ["repair", "onarim", "fix", "bugfix", "duzeltme"],
        "failed_change_category": "repair_failure",
        "failed_change_type": "corrective_failure",
        "failed_change_status": "degraded",
        "failed_change_score": 0.38,
        "failed_change_summary": "Repair changes frequently fail to resolve root causes. Symptom-level repairs lead to recurrence within days. Typewriter queue repair had partial success only.",
        "failed_change_patterns": [
            "pattern: repair_applied_to_symptom_instead_of_root_cause",
            "pattern: same_repair_attempted_multiple_times_with_same_outcome",
            "pattern: repair_introduces_side_effect_requiring_another_repair",
        ],
        "similar_failed_changes": [
            "failed_change: typewriter_queue_repair_loop_202606",
            "failed_change: stop_continue_flow_repair_recurrence",
        ],
        "repeated_failures": [
            "retry_interval_reduction_made_timeout_worse",
            "single_thread_reconnect_blocked_other_operations",
            "timeout_reduction_caused_premature_termination",
        ],
        "failure_recurrence_level": "high",
        "failure_risk_level": "high",
        "failure_confidence": 0.66,
        "failure_recommendations": [
            "identify_root_cause_before_attempting_repair",
            "add_regression_gate_after_every_repair",
            "validate_repair_across_all_affected_components",
        ],
        "avoidance_recommendations": [
            "do_not_apply_same_repair_if_it_failed_before",
            "avoid_symptom_only_repairs",
            "do_not_reduce_timeout_as_first_response",
        ],
        "required_actions": [
            "audit_repair_history_before_new_repair",
            "implement_repair_effectiveness_tracking",
        ],
        "recommended_next_action": "audit repair history before applying new repair — check for prior failed attempts",
        "failure_signals": {
            "failed_repair_count": 6,
            "recurrence_rate_pct": 62,
            "symptom_only_repairs": 4,
            "loop_detected": True,
            "loop_type": "symptom_repair_loop",
        },
    },
    "maintenance_failure": {
        "aliases": ["maintenance", "bakim", "update", "guncelleme", "upgrade"],
        "failed_change_category": "maintenance_failure",
        "failed_change_type": "preventive_failure",
        "failed_change_status": "warning",
        "failed_change_score": 0.55,
        "failed_change_summary": "Maintenance failures are rare but impactful. Dependency version bumps occasionally introduce breaking changes. Upgrade rollback procedures not fully tested.",
        "failed_change_patterns": [
            "pattern: maintenance_update_breaks_downstream_dependency",
            "pattern: rollback_not_tested_before_maintenance_window",
        ],
        "similar_failed_changes": [
            "failed_change: fastapi_upgrade_import_breakage",
            "failed_change: python_version_migration_script_failure",
        ],
        "repeated_failures": [
            "dependency_lock_not_updated_causing_import_error",
            "rollback_script_had_stale_reference",
        ],
        "failure_recurrence_level": "low",
        "failure_risk_level": "medium",
        "failure_confidence": 0.72,
        "failure_recommendations": [
            "test_rollback_procedure_before_maintenance",
            "staged_rollout_for_dependency_upgrades",
            "automate_dependency_regression_testing",
        ],
        "avoidance_recommendations": [
            "do_not_skip_rollback_testing",
            "avoid_upgrading_multiple_dependencies_simultaneously",
        ],
        "required_actions": [
            "test_rollback_before_maintenance",
            "add_staged_rollout_policy",
        ],
        "recommended_next_action": "test rollback procedure before every maintenance window",
        "failure_signals": {
            "failed_maintenance_count": 2,
            "rollback_test_coverage_pct": 30,
            "loop_detected": False,
        },
    },
    "feature_failure": {
        "aliases": ["feature", "ozellik", "new", "yeni", "addition"],
        "failed_change_category": "feature_failure",
        "failed_change_type": "additive_failure",
        "failed_change_status": "warning",
        "failed_change_score": 0.62,
        "failed_change_summary": "Feature failures occur when scaffolding lacks downstream integration planning. Edge cases missed during initial design. Feature flag not used for complex rollouts.",
        "failed_change_patterns": [
            "pattern: feature_scaffold_misses_downstream_dependencies",
            "pattern: feature_incomplete_due_to_missing_edge_case_handling",
        ],
        "similar_failed_changes": [
            "failed_change: layer22_scoring_missed_edge_cases",
            "failed_change: multimodal_memory_scaffold_partial",
        ],
        "repeated_failures": [
            "scoring_model_had_to_be_revised_twice",
            "memory_schema_changed_after_initial_scaffold",
        ],
        "failure_recurrence_level": "low",
        "failure_risk_level": "medium",
        "failure_confidence": 0.68,
        "failure_recommendations": [
            "document_downstream_dependencies_before_feature_start",
            "use_feature_flags_for_complex_rollouts",
            "add_edge_case_review_in_design_phase",
        ],
        "avoidance_recommendations": [
            "do_not_start_feature_without_dependency_map",
            "avoid_scaffolding_without_edge_case_analysis",
        ],
        "required_actions": [
            "add_dependency_map_to_feature_templates",
            "enforce_edge_case_review",
        ],
        "recommended_next_action": "add dependency mapping to feature design templates",
        "failure_signals": {
            "failed_feature_count": 3,
            "edge_cases_missed": 4,
            "loop_detected": False,
        },
    },
    "optimization_failure": {
        "aliases": ["optimization", "optimizasyon", "performance", "performans", "speed"],
        "failed_change_category": "optimization_failure",
        "failed_change_type": "performance_failure",
        "failed_change_status": "warning",
        "failed_change_score": 0.58,
        "failed_change_summary": "Optimization failures typically involve caching strategies or premature optimization. Aggressive caching caused stale data serving. Performance regression not caught.",
        "failed_change_patterns": [
            "pattern: optimization_without_baseline_causes_unnoticed_regression",
            "pattern: caching_optimization_leads_to_stale_data",
        ],
        "similar_failed_changes": [
            "failed_change: aggressive_caching_stale_data_202605",
            "failed_change: premature_query_optimization_regression",
        ],
        "repeated_failures": [
            "cache_invalidation_strategy_failed_twice",
            "optimization_reverted_due_to_side_effects",
        ],
        "failure_recurrence_level": "medium",
        "failure_risk_level": "medium",
        "failure_confidence": 0.64,
        "failure_recommendations": [
            "establish_performance_baseline_before_optimization",
            "add_performance_regression_gate",
            "incremental_optimization_with_validation_at_each_step",
        ],
        "avoidance_recommendations": [
            "do_not_optimize_without_baseline_measurements",
            "avoid_aggressive_caching_without_invalidation_strategy",
        ],
        "required_actions": [
            "establish_performance_baseline",
            "implement_cache_invalidation_strategy",
        ],
        "recommended_next_action": "establish performance baseline before further optimization attempts",
        "failure_signals": {
            "failed_optimization_count": 3,
            "regression_cases": 2,
            "loop_detected": False,
        },
    },
    "refactor_failure": {
        "aliases": ["refactor", "refactoring", "yeniden", "duzenleme", "restructure"],
        "failed_change_category": "refactor_failure",
        "failed_change_type": "restructuring_failure",
        "failed_change_status": "degraded",
        "failed_change_score": 0.42,
        "failed_change_summary": "Refactor failures occur when boundary contracts are not clearly defined before restructuring. Import changes cause cascading side effects. Module extraction reverted due to import issues.",
        "failed_change_patterns": [
            "pattern: refactor_without_contract_tests_causes_side_effects",
            "pattern: refactor_reverted_due_to_import_chain_disruption",
        ],
        "similar_failed_changes": [
            "failed_change: config_extraction_reverted_import_chain",
            "failed_change: module_split_caused_circular_import",
        ],
        "repeated_failures": [
            "import_chain_broke_again_after_second_refactor_attempt",
            "circular_dependency_reappeared_after_restructuring",
        ],
        "failure_recurrence_level": "high",
        "failure_risk_level": "high",
        "failure_confidence": 0.60,
        "failure_recommendations": [
            "define_clear_boundary_contracts_before_refactor",
            "add_contract_tests_before_refactoring",
            "refactor_in_small_phases_with_validation_gates",
        ],
        "avoidance_recommendations": [
            "do_not_refactor_without_contract_tests",
            "avoid_large_batch_refactors",
            "do_not_skip_import_graph_analysis",
        ],
        "required_actions": [
            "add_contract_tests_before_refactor",
            "analyze_import_graph_before_restructuring",
        ],
        "recommended_next_action": "add contract tests and analyze import graph before attempting refactor",
        "failure_signals": {
            "failed_refactor_count": 4,
            "reverted_changes": 2,
            "loop_detected": True,
            "loop_type": "refactor_revert_loop",
        },
    },
    "integration_failure": {
        "aliases": ["integration", "entegrasyon", "api", "service", "servis"],
        "failed_change_category": "integration_failure",
        "failed_change_type": "connective_failure",
        "failed_change_status": "degraded",
        "failed_change_score": 0.35,
        "failed_change_summary": "Integration failures are the most impactful. External API contract changes cause cascading failures. Fallback integration incomplete. Contract mismatch causes silent failures.",
        "failed_change_patterns": [
            "pattern: external_api_contract_change_breaks_integration",
            "pattern: fallback_not_integrated_before_primary_fails",
            "pattern: integration_failure_silent_no_alert_raised",
        ],
        "similar_failed_changes": [
            "failed_change: openai_fallback_contract_mismatch",
            "failed_change: deepseek_api_version_drift",
        ],
        "repeated_failures": [
            "api_version_mismatch_recurred_across_two_releases",
            "fallback_path_failed_silently_multiple_times",
        ],
        "failure_recurrence_level": "high",
        "failure_risk_level": "critical",
        "failure_confidence": 0.58,
        "failure_recommendations": [
            "version_all_integration_contracts",
            "implement_circuit_breaker_for_external_integrations",
            "add_integration_health_monitoring_with_alerts",
        ],
        "avoidance_recommendations": [
            "do_not_deploy_integration_without_contract_tests",
            "avoid_single_provider_dependency",
            "do_not_skip_fallback_integration_testing",
        ],
        "required_actions": [
            "version_integration_contracts",
            "implement_circuit_breaker",
            "add_integration_alerting",
        ],
        "recommended_next_action": "version all integration contracts and implement circuit breaker",
        "failure_signals": {
            "failed_integration_count": 5,
            "silent_failures": 3,
            "contract_mismatches": 2,
            "loop_detected": True,
            "loop_type": "integration_contract_drift_loop",
        },
    },
    "configuration_failure": {
        "aliases": ["config", "configuration", "yapilandirma", "setting", "env"],
        "failed_change_category": "configuration_failure",
        "failed_change_type": "environmental_failure",
        "failed_change_status": "warning",
        "failed_change_score": 0.52,
        "failed_change_summary": "Configuration failures are subtle and often silent. Missing keys trigger fallback values without warning. Config validation not enforced. Changes deployed without schema check.",
        "failed_change_patterns": [
            "pattern: configuration_change_deployed_without_validation",
            "pattern: missing_env_key_causes_silent_fallback_to_stale_value",
        ],
        "similar_failed_changes": [
            "failed_change: missing_log_level_key_fallback",
            "failed_change: api_key_misconfiguration_outage",
        ],
        "repeated_failures": [
            "same_env_key_missing_across_two_deployments",
            "fallback_value_used_repeatedly_without_alert",
        ],
        "failure_recurrence_level": "medium",
        "failure_risk_level": "medium",
        "failure_confidence": 0.70,
        "failure_recommendations": [
            "add_config_schema_validation_at_boot",
            "implement_config_change_audit_log",
            "alert_on_fallback_value_activation",
        ],
        "avoidance_recommendations": [
            "do_not_deploy_config_changes_without_schema_validation",
            "avoid_silent_fallback_values_for_critical_settings",
        ],
        "required_actions": [
            "add_config_schema_validation",
            "add_fallback_alerting",
        ],
        "recommended_next_action": "add configuration schema validation and fallback alerting",
        "failure_signals": {
            "failed_config_count": 4,
            "silent_fallbacks": 3,
            "loop_detected": False,
        },
    },
    "security_failure": {
        "aliases": ["security", "guvenlik", "auth", "authn", "authz", "permission"],
        "failed_change_category": "security_failure",
        "failed_change_type": "protective_failure",
        "failed_change_status": "warning",
        "failed_change_score": 0.60,
        "failed_change_summary": "Security failures are rare but critical. Permission boundary exceptions discovered after deployment. API key exposure in logs caught by audit. Most security changes succeed.",
        "failed_change_patterns": [
            "pattern: security_change_not_reviewed_before_deploy",
            "pattern: permission_boundary_too_permissive_by_default",
        ],
        "similar_failed_changes": [
            "failed_change: debug_endpoint_permission_gap",
            "failed_change: api_key_exposure_in_logs",
        ],
        "repeated_failures": [
            "permission_gap_reappeared_in_new_endpoint",
        ],
        "failure_recurrence_level": "low",
        "failure_risk_level": "high",
        "failure_confidence": 0.74,
        "failure_recommendations": [
            "add_automated_security_scanning_to_ci",
            "enforce_security_review_before_deploy",
            "implement_least_privilege_by_default",
        ],
        "avoidance_recommendations": [
            "do_not_skip_security_review",
            "avoid_permissive_default_permissions",
        ],
        "required_actions": [
            "add_security_scanning_to_ci",
            "enforce_security_review_gate",
        ],
        "recommended_next_action": "add automated security scanning to CI pipeline",
        "failure_signals": {
            "failed_security_count": 2,
            "vulnerabilities_found": 2,
            "loop_detected": False,
        },
    },
    "workflow_failure": {
        "aliases": ["workflow", "is_akisi", "pipeline", "process", "surec"],
        "failed_change_category": "workflow_failure",
        "failed_change_type": "process_failure",
        "failed_change_status": "warning",
        "failed_change_score": 0.55,
        "failed_change_summary": "Workflow failures occur when pipeline steps are not properly ordered or validated. Missing gates between stages allow inconsistent state to propagate. Rollback paths not exercised.",
        "failed_change_patterns": [
            "pattern: workflow_step_executed_before_prerequisite_validated",
            "pattern: pipeline_state_inconsistent_after_partial_failure",
        ],
        "similar_failed_changes": [
            "failed_change: deploy_pipeline_state_corruption",
            "failed_change: test_gate_skipped_in_workflow",
        ],
        "repeated_failures": [
            "deploy_pipeline_skipped_validation_twice",
            "state_inconsistency_recurred_in_release_workflow",
        ],
        "failure_recurrence_level": "medium",
        "failure_risk_level": "medium",
        "failure_confidence": 0.66,
        "failure_recommendations": [
            "formalize_workflow_dependency_graph",
            "add_validation_gates_between_all_steps",
            "implement_workflow_state_validation",
        ],
        "avoidance_recommendations": [
            "do_not_skip_validation_gates",
            "avoid_parallel_steps_with_shared_state",
        ],
        "required_actions": [
            "formalize_workflow_dependencies",
            "add_validation_gates",
        ],
        "recommended_next_action": "formalize workflow dependency graph and add validation gates between all steps",
        "failure_signals": {
            "failed_workflow_count": 3,
            "skipped_gates": 3,
            "loop_detected": False,
        },
    },
    "documentation_failure": {
        "aliases": ["documentation", "dokumantasyon", "docs", "readme", "help"],
        "failed_change_category": "documentation_failure",
        "failed_change_type": "informational_failure",
        "failed_change_status": "warning",
        "failed_change_score": 0.58,
        "failed_change_summary": "Documentation failures are non-functional but impact productivity. Docs fall out of sync with implementation. API references outdated. Runbooks not updated after process changes.",
        "failed_change_patterns": [
            "pattern: documentation_out_of_sync_with_implementation",
            "pattern: api_reference_not_updated_after_change",
        ],
        "similar_failed_changes": [
            "failed_change: api_reference_outdated_by_2_weeks",
            "failed_change: runbook_not_updated_after_rollback_procedure_change",
        ],
        "repeated_failures": [
            "same_endpoint_missing_from_docs_across_two_releases",
        ],
        "failure_recurrence_level": "medium",
        "failure_risk_level": "low",
        "failure_confidence": 0.70,
        "failure_recommendations": [
            "automate_documentation_generation",
            "add_documentation_sync_check_in_ci",
            "document_architecture_decisions_as_adrs",
        ],
        "avoidance_recommendations": [
            "do_not_merge_code_without_doc_update_check",
            "avoid_manual_doc_sync_processes",
        ],
        "required_actions": [
            "automate_docs_generation",
            "add_docs_sync_check_to_ci",
        ],
        "recommended_next_action": "automate documentation generation and add sync check to CI",
        "failure_signals": {
            "failed_doc_count": 5,
            "sync_gap_days_avg": 14,
            "loop_detected": False,
        },
    },
}


def _select_failed_change_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in FAILED_CHANGE_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "repair_failure"


def _compute_overall_failed_change_status(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    statuses = [i.get("failed_change_status", "") for i in items]
    if any(s == "blocked" for s in statuses):
        return "blocked"
    if any(s == "degraded" for s in statuses):
        return "degraded"
    if any(s == "warning" for s in statuses):
        return "warning"
    if all(s == "pass" for s in statuses):
        return "pass"
    return "warning"


def _compute_failed_change_risk_score(items: List[Dict[str, Any]]) -> str:
    levels = [i.get("failure_risk_level", "low") for i in items]
    if any(l == "critical" for l in levels):
        return "critical"
    if any(l == "high" for l in levels):
        return "high"
    if any(l == "medium" for l in levels):
        return "medium"
    return "low"


def _count_loop_detections(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    detected = [i for i in items if i.get("failure_signals", {}).get("loop_detected")]
    return {
        "total_loops": len(detected),
        "loop_types": list(set(
            i["failure_signals"]["loop_type"]
            for i in detected if i["failure_signals"].get("loop_type")
        )),
    }


def failed_change_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "33.2",
        "name": "Failed Change Intelligence Preview",
        "status": "failed_change_intelligence_ready",
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
            "/debug/failed-change-status",
            "/debug/failed-change-registry",
            "/debug/failed-change-preview",
        ],
        "connected_layers": [
            "33.1", "32.5", "32.4", "32.3", "32.2", "32.1",
            "31.5", "31.4", "31.3", "31.2", "31.1",
            "31", "30", "30.5", "30.4", "30.3", "30.2", "30.1",
            "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
        ],
        "technology_support": [
            "Python", "HTML", "CSS", "JavaScript", "TypeScript",
            "JSON", "YAML", "Database", "Infrastructure", "API",
            "Workflow", "Documentation",
        ],
        "safety_note": "Read-only failed change intelligence preview. No actual failure remediation actions performed.",
    }


def failed_change_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for fid, f in FAILED_CHANGE_PROFILES.items():
        items.append(
            {
                "failed_change_id": fid,
                "failed_change_category": f["failed_change_category"],
                "failed_change_type": f["failed_change_type"],
                "failed_change_status": f["failed_change_status"],
                "failed_change_score": f["failed_change_score"],
                "failure_recurrence_level": f.get("failure_recurrence_level"),
                "failure_risk_level": f.get("failure_risk_level"),
                "pattern_count": len(f.get("failed_change_patterns", [])),
                "repeated_failure_count": len(f.get("repeated_failures", [])),
                "failure_confidence": f.get("failure_confidence", 0.0),
                "failure_signals": f.get("failure_signals", {}),
                "loop_detected": f.get("failure_signals", {}).get("loop_detected", False),
            }
        )
    loop_info = _count_loop_detections(items)
    return {
        "layer": "33.2",
        "name": "Failed Change Intelligence Registry",
        "status": "failed_change_intelligence_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "failed_change_count": len(items),
        "failed_change_items": items,
        "pass_count": sum(1 for i in items if i["failed_change_status"] == "pass"),
        "warning_count": sum(1 for i in items if i["failed_change_status"] == "warning"),
        "degraded_count": sum(1 for i in items if i["failed_change_status"] == "degraded"),
        "blocked_count": sum(1 for i in items if i["failed_change_status"] == "blocked"),
        "overall_failed_change_score": round(
            sum(i["failed_change_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "overall_failed_change_status": _compute_overall_failed_change_status(items),
        "overall_failure_risk_level": _compute_failed_change_risk_score(items),
        "recurrence_breakdown": {
            "critical": sum(1 for i in items if i["failure_recurrence_level"] == "critical"),
            "high": sum(1 for i in items if i["failure_recurrence_level"] == "high"),
            "medium": sum(1 for i in items if i["failure_recurrence_level"] == "medium"),
            "low": sum(1 for i in items if i["failure_recurrence_level"] == "low"),
        },
        "loop_detection_summary": {
            "total_loops": loop_info["total_loops"],
            "loop_types": loop_info["loop_types"],
            "loop_details": [
                {
                    "failed_change_id": i["failed_change_id"],
                    "loop_type": i["failure_signals"].get("loop_type"),
                    "repeated_failures": len(
                        FAILED_CHANGE_PROFILES.get(i["failed_change_id"], {}).get("repeated_failures", [])
                    ),
                }
                for i in items if i.get("loop_detected")
            ],
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
    L = related_layer or "Layer 33.2"
    layer31 = layer31_full_status()
    layer30 = layer30_full_status()
    layer29 = layer29_status_snapshot()
    change_reg = change_memory_intelligence_registry()
    dependency_reg = dependency_intelligence_registry()
    root_cause_reg = root_cause_intelligence_registry()
    failure_reg = failure_memory_intelligence_registry()
    regression_reg = regression_intelligence_registry()
    anomaly_reg = runtime_anomaly_intelligence_registry()

    return {
        "layer33_1_change_memory_intelligence": {
            "change_count": change_reg.get("change_count"),
            "overall_change_score": change_reg.get("overall_change_score"),
        },
        "layer32_5_dependency_intelligence": {
            "dependency_count": dependency_reg.get("dependency_count"),
            "overall_dependency_score": dependency_reg.get("overall_dependency_score"),
        },
        "layer32_4_root_cause_intelligence": {
            "root_cause_count": root_cause_reg.get("root_cause_count"),
            "overall_root_cause_score": root_cause_reg.get("overall_root_cause_score"),
        },
        "layer32_3_failure_memory_intelligence": {
            "failure_count": failure_reg.get("failure_count"),
            "overall_failure_score": failure_reg.get("overall_failure_score"),
        },
        "layer32_2_regression_intelligence": {
            "regression_count": regression_reg.get("regression_count"),
            "overall_regression_score": regression_reg.get("overall_regression_score"),
        },
        "layer32_1_anomaly_intelligence": {
            "anomaly_count": anomaly_reg.get("anomaly_count"),
            "overall_anomaly_score": anomaly_reg.get("overall_anomaly_score"),
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


def build_failed_change_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    fid = _select_failed_change_profile(target_issue, command, project_area)
    f = FAILED_CHANGE_PROFILES[fid]
    detected = target_issue or project_area or fid
    cmd = command or detected
    L = related_layer or "Layer 33.2"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "failed_change_id": fid,
        "failed_change_category": f["failed_change_category"],
        "failed_change_type": f["failed_change_type"],
        "failed_change_status": f["failed_change_status"],
        "failed_change_score": f["failed_change_score"],
        "failed_change_summary": f.get("failed_change_summary"),
        "failed_change_patterns": f.get("failed_change_patterns", []),
        "similar_failed_changes": f.get("similar_failed_changes", []),
        "repeated_failures": f.get("repeated_failures", []),
        "failure_recurrence_level": f.get("failure_recurrence_level"),
        "failure_risk_level": f.get("failure_risk_level"),
        "failure_confidence": f.get("failure_confidence", 0.0),
        "failure_recommendations": f.get("failure_recommendations", []),
        "avoidance_recommendations": f.get("avoidance_recommendations", []),
        "required_actions": f.get("required_actions", []),
        "recommended_next_action": f.get("recommended_next_action"),
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
        "safety_note": "Read-only failed change intelligence preview. No actual failure remediation actions performed.",
    }
