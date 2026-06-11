from __future__ import annotations
from typing import Any, Dict, List, Optional

from change_memory_intelligence_preview import (
    change_memory_intelligence_registry,
)
from failed_change_intelligence_preview import (
    failed_change_intelligence_registry,
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


CHANGE_PLANNING_PROFILES: Dict[str, Dict[str, Any]] = {
    "repair_plan": {
        "aliases": ["repair", "onarim", "fix", "bugfix", "duzeltme"],
        "plan_type": "repair_plan",
        "plan_status": "degraded",
        "plan_score": 0.52,
        "recommended_strategy": "Identify root cause before applying repair. Use dependency chain analysis to locate origin. Apply repair at root cause level, not symptom level.",
        "alternative_strategies": [
            "strategy: apply_symptom_repair_as_short_term_workaround",
            "strategy: isolate_component_and_repair_in_isolation",
        ],
        "avoided_strategies": [
            "avoided: symptom_only_repair — previously failed in change_memory: repair_change_stream_timeout",
            "avoided: timeout_reduction — caused premature termination per failed_change: repair_failure",
            "avoided: retry_interval_reduction — made timeout worse per failed_change: repair_failure",
        ],
        "required_files": [
            "app.py",
            "lux_fault_report.py",
            "root_cause_intelligence_preview.py",
        ],
        "affected_files": [
            "runtime_anomaly_intelligence_preview.py",
            "failure_memory_intelligence_preview.py",
            "regression_intelligence_preview.py",
        ],
        "dependency_chain": [
            "root_cause_intelligence → failure_memory_intelligence",
            "failure_memory_intelligence → regression_intelligence",
            "regression_intelligence → runtime_anomaly_intelligence",
        ],
        "estimated_risk": "high",
        "estimated_complexity": "high",
        "estimated_effort": "medium",
        "validation_steps": [
            "verify_root_cause_before_repair",
            "add_regression_gate_after_repair",
            "validate_across_all_affected_components",
            "run_full_smoke_suite",
        ],
        "rollback_strategy": "revert_repair_at_file_level_if_regression_detected",
        "plan_summary": "Repair plan generated from failed change intelligence. Three strategies explicitly avoided due to prior failures. Recommended approach is root-cause-level repair with full validation gate.",
        "required_actions": [
            "identify_root_cause_before_repair",
            "add_post_repair_validation",
            "audit_repair_history_before_applying",
        ],
        "recommended_next_action": "run root cause analysis before attempting any repair",
        "confidence_score": 0.62,
        "plan_signals": {
            "successful_changes_referenced": 2,
            "failed_changes_referenced": 3,
            "strategies_avoided": 3,
            "strategies_recommended": 1,
            "strategies_alternative": 2,
        },
    },
    "maintenance_plan": {
        "aliases": ["maintenance", "bakim", "update", "guncelleme", "upgrade"],
        "plan_type": "maintenance_plan",
        "plan_status": "pass",
        "plan_score": 0.78,
        "recommended_strategy": "Schedule maintenance in regular cadence with automated upgrade testing. Stage dependency upgrades individually to isolate breaking changes.",
        "alternative_strategies": [
            "strategy: batch_all_dependency_upgrades_together",
            "strategy: skip_dependency_upgrades_and_pin_versions",
        ],
        "avoided_strategies": [
            "avoided: upgrading_multiple_dependencies_simultaneously — caused cascading failures",
            "avoided: skipping_rollback_testing — rollback script had stale reference",
        ],
        "required_files": [
            "requirements.txt",
            ".env",
            "app.py",
        ],
        "affected_files": [
            "all_dependency_imports_across_project",
        ],
        "dependency_chain": [
            "maintenance_dependency_bump → import_verification",
            "import_verification → smoke_test_suite",
        ],
        "estimated_risk": "low",
        "estimated_complexity": "low",
        "estimated_effort": "low",
        "validation_steps": [
            "run_dependency_regression_suite",
            "verify_rollback_procedure_before_maintenance",
            "test_import_paths_after_upgrade",
        ],
        "rollback_strategy": "revert_dependency_version_and_rerun_smoke_tests",
        "plan_summary": "Maintenance plan built from successful change memory. Staged rollout recommended. Rollback procedure must be verified before maintenance window.",
        "required_actions": [
            "test_rollback_before_maintenance",
            "upgrade_dependencies_individually",
        ],
        "recommended_next_action": "test rollback procedure and upgrade dependencies one at a time",
        "confidence_score": 0.80,
        "plan_signals": {
            "successful_changes_referenced": 2,
            "failed_changes_referenced": 1,
            "strategies_avoided": 2,
            "strategies_recommended": 1,
            "strategies_alternative": 2,
        },
    },
    "feature_plan": {
        "aliases": ["feature", "ozellik", "new", "yeni", "addition"],
        "plan_type": "feature_plan",
        "plan_status": "pass",
        "plan_score": 0.74,
        "recommended_strategy": "Scaffold feature with complete dependency map first. Document downstream dependencies before implementation. Use feature flags for complex rollouts.",
        "alternative_strategies": [
            "strategy: direct_implementation_without_scaffold",
            "strategy: incremental_feature_rollout_without_flag",
        ],
        "avoided_strategies": [
            "avoided: scaffolding_without_downstream_dependency_map — caused layer22 scoring revision",
            "avoided: starting_feature_without_edge_case_analysis — caused memory schema revision",
        ],
        "required_files": [
            "feature_scaffold_template.py",
            "endpoint_coverage_matrix.py",
        ],
        "affected_files": [
            "new_feature_module.py",
            "app.py",
            "lux_fault_report.py",
        ],
        "dependency_chain": [
            "feature_design → dependency_mapping",
            "dependency_mapping → scaffold_implementation",
            "scaffold_implementation → integration_testing",
        ],
        "estimated_risk": "low",
        "estimated_complexity": "medium",
        "estimated_effort": "medium",
        "validation_steps": [
            "verify_dependency_map_completeness",
            "run_edge_case_review",
            "validate_feature_flag_isolation",
            "run_integration_tests",
        ],
        "rollback_strategy": "disable_feature_flag_and_revert_scaffold_module",
        "plan_summary": "Feature plan generated from change memory. Dependency mapping and edge case analysis enforced to prevent prior failure patterns.",
        "required_actions": [
            "create_dependency_map",
            "enforce_edge_case_review",
        ],
        "recommended_next_action": "create dependency map before starting feature implementation",
        "confidence_score": 0.76,
        "plan_signals": {
            "successful_changes_referenced": 2,
            "failed_changes_referenced": 2,
            "strategies_avoided": 2,
            "strategies_recommended": 1,
            "strategies_alternative": 2,
        },
    },
    "optimization_plan": {
        "aliases": ["optimization", "optimizasyon", "performance", "performans", "speed"],
        "plan_type": "optimization_plan",
        "plan_status": "warning",
        "plan_score": 0.60,
        "recommended_strategy": "Establish performance baseline before any optimization. Apply incremental optimizations with validation at each step. Implement cache invalidation strategy before enabling caching.",
        "alternative_strategies": [
            "strategy: apply_all_optimizations_and_measure_after",
            "strategy: caching_only_optimization",
        ],
        "avoided_strategies": [
            "avoided: aggressive_caching_without_invalidation_strategy — caused stale data serving",
            "avoided: optimization_without_baseline — caused unnoticed regression",
        ],
        "required_files": [
            "app.py",
            "performance_baseline_config.py",
        ],
        "affected_files": [
            "stream_handlers.py",
            "response_compressors.py",
            "cache_layer.py",
        ],
        "dependency_chain": [
            "baseline_measurement → optimization_target_selection",
            "optimization → regression_verification",
            "cache_enablement → invalidation_strategy",
        ],
        "estimated_risk": "medium",
        "estimated_complexity": "medium",
        "estimated_effort": "medium",
        "validation_steps": [
            "measure_performance_baseline",
            "apply_optimization_incrementally",
            "verify_no_regression_after_each_step",
            "test_cache_invalidation",
        ],
        "rollback_strategy": "revert_optimization_changes_and_restore_baseline_config",
        "plan_summary": "Optimization plan built from failed change intelligence. Baseline measurement and cache invalidation enforced. Incremental application with per-step validation.",
        "required_actions": [
            "establish_performance_baseline",
            "implement_cache_invalidation",
            "apply_optimizations_incrementally",
        ],
        "recommended_next_action": "measure performance baseline before applying any optimization",
        "confidence_score": 0.68,
        "plan_signals": {
            "successful_changes_referenced": 1,
            "failed_changes_referenced": 2,
            "strategies_avoided": 2,
            "strategies_recommended": 1,
            "strategies_alternative": 2,
        },
    },
    "refactor_plan": {
        "aliases": ["refactor", "refactoring", "yeniden", "duzenleme", "restructure"],
        "plan_type": "refactor_plan",
        "plan_status": "degraded",
        "plan_score": 0.48,
        "recommended_strategy": "Define clear boundary contracts before any refactoring. Add contract tests first. Analyze import graph completely. Refactor in small phases with validation gates between each phase.",
        "alternative_strategies": [
            "strategy: refactor_in_single_large_batch",
            "strategy: direct_module_merge_without_contracts",
        ],
        "avoided_strategies": [
            "avoided: refactoring_without_contract_tests — caused side effects per failed_change: refactor_failure",
            "avoided: large_batch_refactor — caused reversion per refactor_revert_loop",
            "avoided: skipping_import_graph_analysis — caused circular import",
        ],
        "required_files": [
            "app.py",
            "lux_fault_report.py",
            "endpoint_coverage_matrix.py",
        ],
        "affected_files": [
            "import_graph_across_all_modules",
            "module_boundaries_test_suite",
        ],
        "dependency_chain": [
            "contract_test_definition → import_graph_analysis",
            "import_graph_analysis → phased_refactor_plan",
            "phased_plan → validation_gates",
        ],
        "estimated_risk": "high",
        "estimated_complexity": "high",
        "estimated_effort": "high",
        "validation_steps": [
            "define_boundary_contracts",
            "add_contract_tests",
            "analyze_import_graph",
            "refactor_in_small_phases",
            "run_full_smoke_after_each_phase",
        ],
        "rollback_strategy": "phase_level_revert — revert last refactor phase and restore contracts",
        "plan_summary": "Refactor plan generated from failed change intelligence. Three strategies avoided due to prior failures including refactor_revert_loop. Contract-first approach enforced.",
        "required_actions": [
            "add_contract_tests_before_refactor",
            "analyze_import_graph",
            "phase_refactor_with_validation",
        ],
        "recommended_next_action": "define boundary contracts and add contract tests before any refactoring",
        "confidence_score": 0.58,
        "plan_signals": {
            "successful_changes_referenced": 1,
            "failed_changes_referenced": 3,
            "strategies_avoided": 3,
            "strategies_recommended": 1,
            "strategies_alternative": 2,
        },
    },
    "integration_plan": {
        "aliases": ["integration", "entegrasyon", "api", "service", "servis"],
        "plan_type": "integration_plan",
        "plan_status": "degraded",
        "plan_score": 0.40,
        "recommended_strategy": "Version all integration contracts before connecting. Implement circuit breaker pattern for external dependencies. Test fallback path before primary integration goes live.",
        "alternative_strategies": [
            "strategy: integrate_without_contract_versioning",
            "strategy: single_provider_dependency",
        ],
        "avoided_strategies": [
            "avoided: deploying_integration_without_contract_tests — caused drift per integration_contract_drift_loop",
            "avoided: single_provider_dependency — external API SPOF",
            "avoided: skipping_fallback_testing — fallback failed silently",
        ],
        "required_files": [
            "app.py",
            "integration_contracts.yaml",
            "circuit_breaker_config.py",
        ],
        "affected_files": [
            "external_api_handlers.py",
            "fallback_providers.py",
            "integration_test_suite.py",
        ],
        "dependency_chain": [
            "contract_versioning → integration_implementation",
            "integration_implementation → circuit_breaker_setup",
            "circuit_breaker → fallback_path_testing",
        ],
        "estimated_risk": "critical",
        "estimated_complexity": "high",
        "estimated_effort": "high",
        "validation_steps": [
            "define_integration_contract_version",
            "implement_circuit_breaker",
            "test_fallback_path",
            "run_contract_tests",
            "deploy_with_monitoring",
        ],
        "rollback_strategy": "switch_to_fallback_provider_and_revert_contract_version",
        "plan_summary": "Integration plan generated from failed change intelligence. Three strategies avoided. Contract versioning and circuit breaker are mandatory. Integration_contract_drift_loop informs all contract decisions.",
        "required_actions": [
            "version_integration_contracts",
            "implement_circuit_breaker",
            "test_fallback_path",
        ],
        "recommended_next_action": "version all integration contracts and implement circuit breaker before connecting",
        "confidence_score": 0.56,
        "plan_signals": {
            "successful_changes_referenced": 1,
            "failed_changes_referenced": 3,
            "strategies_avoided": 3,
            "strategies_recommended": 1,
            "strategies_alternative": 2,
        },
    },
    "configuration_plan": {
        "aliases": ["config", "configuration", "yapilandirma", "setting", "env"],
        "plan_type": "configuration_plan",
        "plan_status": "warning",
        "plan_score": 0.62,
        "recommended_strategy": "Add configuration schema validation at boot time. Implement config change audit log. Alert on fallback value activation. Never deploy config changes without schema validation.",
        "alternative_strategies": [
            "strategy: deploy_config_without_schema_validation",
            "strategy: manual_config_verification_only",
        ],
        "avoided_strategies": [
            "avoided: deploying_config_without_schema_validation — caused silent fallback per failed_change: configuration_failure",
            "avoided: silent_fallback_for_critical_settings — stale values used without alert",
        ],
        "required_files": [
            ".env",
            "config_schema.yaml",
            "app.py",
        ],
        "affected_files": [
            "config_loader.py",
            "config_validator.py",
            "logging_config.py",
        ],
        "dependency_chain": [
            "schema_definition → validation_implementation",
            "validation → boot_time_config_check",
            "fallback_detection → alerting_pipeline",
        ],
        "estimated_risk": "medium",
        "estimated_complexity": "low",
        "estimated_effort": "low",
        "validation_steps": [
            "define_config_schema",
            "implement_boot_time_validation",
            "add_fallback_alerting",
            "test_missing_key_scenarios",
        ],
        "rollback_strategy": "revert_config_change_and_restore_previous_env_file",
        "plan_summary": "Configuration plan built from failed change intelligence. Schema validation and fallback alerting prevent silent configuration failures that recurred across deployments.",
        "required_actions": [
            "add_config_schema_validation",
            "add_fallback_alerting",
        ],
        "recommended_next_action": "define configuration schema and implement boot-time validation",
        "confidence_score": 0.72,
        "plan_signals": {
            "successful_changes_referenced": 1,
            "failed_changes_referenced": 2,
            "strategies_avoided": 2,
            "strategies_recommended": 1,
            "strategies_alternative": 2,
        },
    },
    "security_plan": {
        "aliases": ["security", "guvenlik", "auth", "authn", "authz", "permission"],
        "plan_type": "security_plan",
        "plan_status": "pass",
        "plan_score": 0.80,
        "recommended_strategy": "Enforce security review gate before every deploy. Add automated security scanning to CI pipeline. Implement least privilege by default for all new endpoints.",
        "alternative_strategies": [
            "strategy: deploy_first_review_after",
            "strategy: permissive_default_permissions",
        ],
        "avoided_strategies": [
            "avoided: skipping_security_review_before_deploy — caused permission gap in debug endpoints",
            "avoided: permissive_default_permissions — permission boundary too broad",
        ],
        "required_files": [
            "permission_boundary.py",
            "security_scan_config.yaml",
        ],
        "affected_files": [
            "all_endpoint_definitions_in_app.py",
            "authentication_middleware.py",
        ],
        "dependency_chain": [
            "security_review → permission_boundary_check",
            "permission_check → deploy_gate",
            "automated_scan → vulnerability_report",
        ],
        "estimated_risk": "low",
        "estimated_complexity": "low",
        "estimated_effort": "low",
        "validation_steps": [
            "automated_security_scan",
            "permission_boundary_review",
            "least_privilege_verification",
        ],
        "rollback_strategy": "revert_permission_change_and_review_boundaries",
        "plan_summary": "Security plan generated from change memory and failed change intelligence. Security review gate and automated scanning prevent permission gaps.",
        "required_actions": [
            "add_security_scanning_to_ci",
            "enforce_security_review_gate",
        ],
        "recommended_next_action": "add automated security scanning to CI pipeline",
        "confidence_score": 0.82,
        "plan_signals": {
            "successful_changes_referenced": 1,
            "failed_changes_referenced": 1,
            "strategies_avoided": 2,
            "strategies_recommended": 1,
            "strategies_alternative": 2,
        },
    },
    "workflow_plan": {
        "aliases": ["workflow", "is_akisi", "pipeline", "process", "surec"],
        "plan_type": "workflow_plan",
        "plan_status": "warning",
        "plan_score": 0.58,
        "recommended_strategy": "Formalize workflow dependency graph before making changes. Add validation gates between all pipeline stages. Never skip validation gates even for hotfixes.",
        "alternative_strategies": [
            "strategy: run_pipeline_without_validation_gates",
            "strategy: manual_verification_at_each_step",
        ],
        "avoided_strategies": [
            "avoided: running_pipeline_without_validation_gates — caused state inconsistency",
            "avoided: parallel_steps_with_shared_state — caused workflow corruption",
        ],
        "required_files": [
            "pipeline_definition.yaml",
            "workflow_config.py",
        ],
        "affected_files": [
            "deploy_pipeline.py",
            "test_gate_handlers.py",
            "state_persistence.py",
        ],
        "dependency_chain": [
            "workflow_graph_definition → gate_placement",
            "gate_placement → pipeline_reconfiguration",
            "reconfiguration → validation_testing",
        ],
        "estimated_risk": "medium",
        "estimated_complexity": "medium",
        "estimated_effort": "medium",
        "validation_steps": [
            "formalize_workflow_dependency_graph",
            "add_validation_gates",
            "test_gate_enforcement",
            "run_pipeline_dry_run",
        ],
        "rollback_strategy": "revert_pipeline_config_and_restore_previous_workflow",
        "plan_summary": "Workflow plan built from failed change intelligence. Validation gates enforced at all stages to prevent state inconsistency that recurred in releases.",
        "required_actions": [
            "formalize_workflow_dependencies",
            "add_validation_gates",
        ],
        "recommended_next_action": "formalize workflow dependency graph and add validation gates between all stages",
        "confidence_score": 0.66,
        "plan_signals": {
            "successful_changes_referenced": 1,
            "failed_changes_referenced": 2,
            "strategies_avoided": 2,
            "strategies_recommended": 1,
            "strategies_alternative": 2,
        },
    },
    "documentation_plan": {
        "aliases": ["documentation", "dokumantasyon", "docs", "readme", "help"],
        "plan_type": "documentation_plan",
        "plan_status": "warning",
        "plan_score": 0.64,
        "recommended_strategy": "Automate documentation generation from code. Add documentation sync check to CI pipeline. Never merge code without doc update verification.",
        "alternative_strategies": [
            "strategy: manual_documentation_updates_only",
            "strategy: document_after_release",
        ],
        "avoided_strategies": [
            "avoided: manual_doc_sync_process — caused documentation to fall out of sync",
            "avoided: documenting_after_release — caused 2-week documentation gap",
        ],
        "required_files": [
            "docs_generation_script.py",
            "ci_pipeline_config.yaml",
        ],
        "affected_files": [
            "all_documentation_files",
            "api_reference_templates",
        ],
        "dependency_chain": [
            "doc_generation_automation → ci_sync_check",
            "ci_sync_check → merge_gate",
        ],
        "estimated_risk": "low",
        "estimated_complexity": "low",
        "estimated_effort": "low",
        "validation_steps": [
            "implement_doc_generation",
            "add_sync_check_to_ci",
            "verify_generated_docs_accuracy",
        ],
        "rollback_strategy": "revert_doc_changes_and_regenerate_from_code",
        "plan_summary": "Documentation plan built from failed change intelligence. Automated generation and CI sync check prevent documentation drift that previously averaged 14 days.",
        "required_actions": [
            "automate_docs_generation",
            "add_docs_sync_check_to_ci",
        ],
        "recommended_next_action": "automate documentation generation and add sync check to CI pipeline",
        "confidence_score": 0.70,
        "plan_signals": {
            "successful_changes_referenced": 1,
            "failed_changes_referenced": 2,
            "strategies_avoided": 2,
            "strategies_recommended": 1,
            "strategies_alternative": 2,
        },
    },
}


def _select_plan_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in CHANGE_PLANNING_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "repair_plan"


def _compute_overall_plan_status(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    statuses = [i.get("plan_status", "") for i in items]
    if any(s == "blocked" for s in statuses):
        return "blocked"
    if any(s == "degraded" for s in statuses):
        return "degraded"
    if any(s == "warning" for s in statuses):
        return "warning"
    if all(s == "pass" for s in statuses):
        return "pass"
    return "warning"


def _compute_plan_risk_score(items: List[Dict[str, Any]]) -> str:
    levels = [i.get("estimated_risk", "low") for i in items]
    if any(l == "critical" for l in levels):
        return "critical"
    if any(l == "high" for l in levels):
        return "high"
    if any(l == "medium" for l in levels):
        return "medium"
    return "low"


def change_planning_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "33.3",
        "name": "Change Planning Intelligence Preview",
        "status": "change_planning_intelligence_ready",
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
            "/debug/change-planning-status",
            "/debug/change-planning-registry",
            "/debug/change-planning-preview",
        ],
        "connected_layers": [
            "33.2", "33.1", "32.5", "32.4", "32.3", "32.2", "32.1",
            "31.5", "31.4", "31.3", "31.2", "31.1",
            "31", "30", "30.5", "30.4", "30.3", "30.2", "30.1",
            "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
        ],
        "technology_support": [
            "Python", "HTML", "CSS", "JavaScript", "TypeScript",
            "JSON", "YAML", "Database", "Infrastructure", "API",
            "Workflow", "Documentation",
        ],
        "safety_note": "Read-only change planning intelligence preview. No actual plan execution actions performed.",
    }


def change_planning_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in CHANGE_PLANNING_PROFILES.items():
        items.append(
            {
                "plan_id": pid,
                "plan_type": p["plan_type"],
                "plan_status": p["plan_status"],
                "plan_score": p["plan_score"],
                "estimated_risk": p.get("estimated_risk"),
                "estimated_complexity": p.get("estimated_complexity"),
                "estimated_effort": p.get("estimated_effort"),
                "strategy_count": 1,
                "alternative_count": len(p.get("alternative_strategies", [])),
                "avoided_count": len(p.get("avoided_strategies", [])),
                "validation_step_count": len(p.get("validation_steps", [])),
                "confidence_score": p["confidence_score"],
            }
        )
    return {
        "layer": "33.3",
        "name": "Change Planning Intelligence Registry",
        "status": "change_planning_intelligence_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "plan_count": len(items),
        "plan_items": items,
        "pass_count": sum(1 for i in items if i["plan_status"] == "pass"),
        "warning_count": sum(1 for i in items if i["plan_status"] == "warning"),
        "degraded_count": sum(1 for i in items if i["plan_status"] == "degraded"),
        "blocked_count": sum(1 for i in items if i["plan_status"] == "blocked"),
        "overall_plan_score": round(
            sum(i["plan_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "overall_plan_status": _compute_overall_plan_status(items),
        "overall_plan_risk_level": _compute_plan_risk_score(items),
        "intelligence_referenced": {
            "change_memory_33_1": True,
            "failed_change_33_2": True,
            "dependency_intelligence_32_5": True,
            "root_cause_intelligence_32_4": True,
            "failure_memory_32_3": True,
            "regression_intelligence_32_2": True,
            "anomaly_intelligence_32_1": True,
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
    L = related_layer or "Layer 33.3"
    layer31 = layer31_full_status()
    layer30 = layer30_full_status()
    layer29 = layer29_status_snapshot()
    change_reg = change_memory_intelligence_registry()
    failed_change_reg = failed_change_intelligence_registry()
    dependency_reg = dependency_intelligence_registry()
    root_cause_reg = root_cause_intelligence_registry()
    failure_reg = failure_memory_intelligence_registry()
    regression_reg = regression_intelligence_registry()
    anomaly_reg = runtime_anomaly_intelligence_registry()

    return {
        "layer33_2_failed_change_intelligence": {
            "failed_change_count": failed_change_reg.get("failed_change_count"),
            "overall_failed_change_score": failed_change_reg.get("overall_failed_change_score"),
            "loop_count": failed_change_reg.get("loop_detection_summary", {}).get("total_loops"),
        },
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


def build_change_planning_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_plan_profile(target_issue, command, project_area)
    p = CHANGE_PLANNING_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 33.3"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "plan_id": pid,
        "plan_type": p["plan_type"],
        "plan_status": p["plan_status"],
        "plan_score": p["plan_score"],
        "recommended_strategy": p.get("recommended_strategy"),
        "alternative_strategies": p.get("alternative_strategies", []),
        "avoided_strategies": p.get("avoided_strategies", []),
        "required_files": p.get("required_files", []),
        "affected_files": p.get("affected_files", []),
        "dependency_chain": p.get("dependency_chain", []),
        "estimated_risk": p.get("estimated_risk"),
        "estimated_complexity": p.get("estimated_complexity"),
        "estimated_effort": p.get("estimated_effort"),
        "validation_steps": p.get("validation_steps", []),
        "rollback_strategy": p.get("rollback_strategy"),
        "plan_summary": p.get("plan_summary"),
        "required_actions": p.get("required_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "confidence_score": p["confidence_score"],
        "plan_signals": p.get("plan_signals", {}),
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
        "safety_note": "Read-only change planning intelligence preview. No actual plan execution actions performed.",
    }
