from __future__ import annotations
from typing import Any, Dict, List, Optional

# lazy import: clone_workspace_intelligence_registry imported inside function
from change_planning_intelligence_preview import (
    change_planning_intelligence_registry,
)
from failed_change_intelligence_preview import (
    failed_change_intelligence_registry,
)
from change_memory_intelligence_preview import (
    change_memory_intelligence_registry,
)
from dependency_intelligence_preview import (
    dependency_intelligence_registry,
)
from root_cause_intelligence_preview import (
    root_cause_intelligence_registry,
)


SANDBOX_REPAIR_PROFILES: Dict[str, Dict[str, Any]] = {
    "repair_change": {
        "aliases": ["repair", "onarim", "fix", "bugfix", "duzeltme"],
        "repair_type": "repair_change",
        "repair_status": "degraded",
        "repair_score": 0.48,
        "repair_summary": "Sandbox repair for recurring failures. Working clone created from master clone. Repair applied in sandbox. Validation detected recurrence risk. Loop protection flagged 3 prior failed attempts with identical strategy.",
        "repair_strategy": "Repair in working clone. Test in sandbox. Validate across all components. Discard working clone on completion. Regenerate from master clone for next repair.",
        "repair_steps": [
            "create_working_clone_from_master",
            "apply_repair_in_working_clone",
            "deploy_to_sandbox",
            "run_sandbox_validation",
            "run_dependency_validation",
            "run_regression_validation",
            "mark_as_delivery_candidate",
            "discard_working_clone",
            "regenerate_from_master",
        ],
        "working_clone_status": "discarded_after_repair",
        "sandbox_status": "validated",
        "sandbox_integrity_score": 0.78,
        "sandbox_health_score": 0.75,
        "repair_validation_score": 0.68,
        "repair_confidence": 0.62,
        "repair_risk_level": "high",
        "required_actions": [
            "verify_loop_protection_before_repair",
            "check_prior_failed_repairs_in_33_2",
            "validate_across_all_components_in_sandbox",
        ],
        "recommended_next_action": "check prior failed repairs in Layer 33.2 before proceeding with sandbox repair",
        "repair_signals": {
            "loop_protection_triggered": True,
            "prior_failed_repairs": 3,
            "prior_successful_repairs": 2,
            "working_clone_created": True,
            "sandbox_deployed": True,
            "validation_passed": True,
            "delivery_candidate": True,
        },
    },
    "maintenance_change": {
        "aliases": ["maintenance", "bakim", "update", "guncelleme", "upgrade"],
        "repair_type": "maintenance_change",
        "repair_status": "pass",
        "repair_score": 0.80,
        "repair_summary": "Sandbox maintenance change executed cleanly. Working clone created. Dependency updated in sandbox. Validation passed. Delivery candidate generated. Working clone discarded.",
        "repair_strategy": "Create working clone. Apply maintenance change. Validate in sandbox. Run dependency and regression validation. Deliver candidate.",
        "repair_steps": [
            "create_working_clone_from_master",
            "apply_maintenance_change_in_working_clone",
            "deploy_to_sandbox",
            "run_sandbox_validation",
            "run_dependency_validation",
            "run_regression_validation",
            "mark_as_delivery_candidate",
            "discard_working_clone",
        ],
        "working_clone_status": "discarded_after_maintenance",
        "sandbox_status": "validated",
        "sandbox_integrity_score": 0.92,
        "sandbox_health_score": 0.90,
        "repair_validation_score": 0.88,
        "repair_confidence": 0.82,
        "repair_risk_level": "low",
        "required_actions": [],
        "recommended_next_action": "maintenance change validated — ready for delivery",
        "repair_signals": {
            "loop_protection_triggered": False,
            "prior_failed_repairs": 0,
            "working_clone_created": True,
            "sandbox_deployed": True,
            "validation_passed": True,
            "delivery_candidate": True,
        },
    },
    "feature_change": {
        "aliases": ["feature", "ozellik", "new", "yeni", "addition"],
        "repair_type": "feature_change",
        "repair_status": "pass",
        "repair_score": 0.76,
        "repair_summary": "Sandbox feature change completed. Working clone created. Feature scaffolded in sandbox. Integration validation confirmed compatibility. Delivery candidate ready.",
        "repair_strategy": "Create working clone. Implement feature. Test in sandbox. Validate integration and regression. Deliver candidate.",
        "repair_steps": [
            "create_working_clone_from_master",
            "implement_feature_in_working_clone",
            "deploy_to_sandbox",
            "run_sandbox_validation",
            "run_integration_validation",
            "run_regression_validation",
            "mark_as_delivery_candidate",
            "discard_working_clone",
        ],
        "working_clone_status": "discarded_after_feature",
        "sandbox_status": "validated",
        "sandbox_integrity_score": 0.88,
        "sandbox_health_score": 0.85,
        "repair_validation_score": 0.82,
        "repair_confidence": 0.78,
        "repair_risk_level": "low",
        "required_actions": [],
        "recommended_next_action": "feature change validated — ready for delivery",
        "repair_signals": {
            "loop_protection_triggered": False,
            "prior_failed_repairs": 0,
            "working_clone_created": True,
            "sandbox_deployed": True,
            "validation_passed": True,
            "delivery_candidate": True,
        },
    },
    "optimization_change": {
        "aliases": ["optimization", "optimizasyon", "performance", "performans", "speed"],
        "repair_type": "optimization_change",
        "repair_status": "warning",
        "repair_score": 0.62,
        "repair_summary": "Sandbox optimization change applied. Performance baseline established. Optimization validated in sandbox. Minor regression detected and corrected before delivery candidate.",
        "repair_strategy": "Create working clone. Measure baseline. Apply optimization incrementally. Validate each step in sandbox. Correct regressions before delivery.",
        "repair_steps": [
            "create_working_clone_from_master",
            "measure_performance_baseline",
            "apply_optimization_in_working_clone",
            "deploy_to_sandbox",
            "run_sandbox_validation",
            "run_performance_validation",
            "correct_regression_if_detected",
            "mark_as_delivery_candidate",
            "discard_working_clone",
        ],
        "working_clone_status": "discarded_after_optimization",
        "sandbox_status": "validated",
        "sandbox_integrity_score": 0.82,
        "sandbox_health_score": 0.78,
        "repair_validation_score": 0.72,
        "repair_confidence": 0.68,
        "repair_risk_level": "medium",
        "required_actions": [
            "verify_performance_baseline_accuracy",
            "confirm_regression_correction",
        ],
        "recommended_next_action": "verify performance baseline and confirm regression correction before delivery",
        "repair_signals": {
            "loop_protection_triggered": False,
            "prior_failed_repairs": 1,
            "working_clone_created": True,
            "sandbox_deployed": True,
            "validation_passed": True,
            "regression_corrected": True,
            "delivery_candidate": True,
        },
    },
    "refactor_change": {
        "aliases": ["refactor", "refactoring", "yeniden", "duzenleme", "restructure"],
        "repair_type": "refactor_change",
        "repair_status": "degraded",
        "repair_score": 0.45,
        "repair_summary": "Sandbox refactor change in progress. Loop protection triggered: 2 prior refactor failures found in Layer 33.2. Contract tests added before refactor. Validation gated between phases.",
        "repair_strategy": "Create working clone. Add contract tests first. Analyze import graph. Refactor in phased steps. Validate each phase in sandbox. Reject on integrity failure.",
        "repair_steps": [
            "create_working_clone_from_master",
            "add_contract_tests",
            "analyze_import_graph",
            "apply_refactor_phase_1",
            "validate_phase_1_in_sandbox",
            "apply_refactor_phase_2",
            "validate_phase_2_in_sandbox",
            "run_full_regression_validation",
            "mark_as_delivery_candidate_or_reject",
            "discard_working_clone",
        ],
        "working_clone_status": "active_phased_refactor",
        "sandbox_status": "validating",
        "sandbox_integrity_score": 0.68,
        "sandbox_health_score": 0.65,
        "repair_validation_score": 0.55,
        "repair_confidence": 0.52,
        "repair_risk_level": "high",
        "required_actions": [
            "complete_phased_refactor",
            "validate_each_phase_in_sandbox",
            "reject_if_integrity_fails",
        ],
        "recommended_next_action": "continue phased refactor with sandbox validation at each phase",
        "repair_signals": {
            "loop_protection_triggered": True,
            "prior_failed_refactors": 2,
            "contract_tests_added": True,
            "import_graph_analyzed": True,
            "phases_completed": 1,
            "phases_remaining": 1,
            "delivery_candidate": False,
        },
    },
    "integration_change": {
        "aliases": ["integration", "entegrasyon", "api", "service", "servis"],
        "repair_type": "integration_change",
        "repair_status": "degraded",
        "repair_score": 0.38,
        "repair_summary": "Sandbox integration change with loop protection. Integration_contract_drift_loop from Layer 33.2 detected. Contract versioning enforced. Circuit breaker implemented in sandbox before delivery.",
        "repair_strategy": "Create working clone. Version integration contract. Implement circuit breaker. Deploy to sandbox. Test with contract tests. Validate fallback path. Deliver only if all validations pass.",
        "repair_steps": [
            "create_working_clone_from_master",
            "version_integration_contract",
            "implement_circuit_breaker",
            "deploy_to_sandbox",
            "run_contract_tests",
            "test_fallback_path",
            "run_integration_validation",
            "run_regression_validation",
            "mark_as_delivery_candidate_or_reject",
            "discard_working_clone",
        ],
        "working_clone_status": "validating_integration",
        "sandbox_status": "testing",
        "sandbox_integrity_score": 0.58,
        "sandbox_health_score": 0.55,
        "repair_validation_score": 0.48,
        "repair_confidence": 0.52,
        "repair_risk_level": "critical",
        "required_actions": [
            "complete_contract_tests",
            "verify_circuit_breaker",
            "validate_fallback_path",
        ],
        "recommended_next_action": "complete integration contract tests and verify circuit breaker before delivery",
        "repair_signals": {
            "loop_protection_triggered": True,
            "prior_failed_integrations": 3,
            "contract_versioned": True,
            "circuit_breaker_implemented": True,
            "contract_tests_pending": True,
            "delivery_candidate": False,
        },
    },
    "configuration_change": {
        "aliases": ["config", "configuration", "yapilandirma", "setting", "env"],
        "repair_type": "configuration_change",
        "repair_status": "warning",
        "repair_score": 0.64,
        "repair_summary": "Sandbox configuration change validated. Schema validation added. Fallback alerting implemented. Configuration tested in sandbox with missing key scenarios.",
        "repair_strategy": "Create working clone. Add config schema validation. Implement fallback alerting. Deploy to sandbox. Test missing key scenarios. Validate no silent fallbacks.",
        "repair_steps": [
            "create_working_clone_from_master",
            "add_config_schema_validation",
            "implement_fallback_alerting",
            "deploy_to_sandbox",
            "test_missing_key_scenarios",
            "verify_no_silent_fallbacks",
            "mark_as_delivery_candidate",
            "discard_working_clone",
        ],
        "working_clone_status": "discarded_after_config",
        "sandbox_status": "validated",
        "sandbox_integrity_score": 0.85,
        "sandbox_health_score": 0.82,
        "repair_validation_score": 0.78,
        "repair_confidence": 0.72,
        "repair_risk_level": "medium",
        "required_actions": [],
        "recommended_next_action": "configuration change validated — ready for delivery",
        "repair_signals": {
            "loop_protection_triggered": False,
            "prior_failed_configs": 1,
            "schema_validation_added": True,
            "fallback_alerting_added": True,
            "delivery_candidate": True,
        },
    },
    "security_change": {
        "aliases": ["security", "guvenlik", "auth", "authn", "authz", "permission"],
        "repair_type": "security_change",
        "repair_status": "pass",
        "repair_score": 0.82,
        "repair_summary": "Sandbox security change executed. Automated security scanning added to CI. Permission boundary enforced. Least privilege verified in sandbox. Delivery candidate generated.",
        "repair_strategy": "Create working clone. Implement security changes. Deploy to sandbox. Run automated security scan. Verify permission boundaries. Validate least privilege.",
        "repair_steps": [
            "create_working_clone_from_master",
            "implement_security_changes",
            "deploy_to_sandbox",
            "run_automated_security_scan",
            "verify_permission_boundaries",
            "validate_least_privilege",
            "mark_as_delivery_candidate",
            "discard_working_clone",
        ],
        "working_clone_status": "discarded_after_security",
        "sandbox_status": "validated",
        "sandbox_integrity_score": 0.94,
        "sandbox_health_score": 0.92,
        "repair_validation_score": 0.90,
        "repair_confidence": 0.84,
        "repair_risk_level": "low",
        "required_actions": [],
        "recommended_next_action": "security change validated — ready for delivery",
        "repair_signals": {
            "loop_protection_triggered": False,
            "prior_failed_security": 0,
            "automated_scan_added": True,
            "permission_boundary_enforced": True,
            "delivery_candidate": True,
        },
    },
    "documentation_change": {
        "aliases": ["documentation", "dokumantasyon", "docs", "readme", "help"],
        "repair_type": "documentation_change",
        "repair_status": "warning",
        "repair_score": 0.66,
        "repair_summary": "Sandbox documentation change applied. Automated generation implemented. CI sync check added. Documentation validated against generated output. Delivery candidate ready.",
        "repair_strategy": "Create working clone. Implement doc generation. Add CI sync check. Deploy to sandbox. Validate generated docs accuracy. Verify sync check enforcement.",
        "repair_steps": [
            "create_working_clone_from_master",
            "implement_doc_generation",
            "add_ci_sync_check",
            "deploy_to_sandbox",
            "validate_generated_docs_accuracy",
            "verify_sync_check_enforcement",
            "mark_as_delivery_candidate",
            "discard_working_clone",
        ],
        "working_clone_status": "discarded_after_docs",
        "sandbox_status": "validated",
        "sandbox_integrity_score": 0.84,
        "sandbox_health_score": 0.80,
        "repair_validation_score": 0.76,
        "repair_confidence": 0.70,
        "repair_risk_level": "low",
        "required_actions": [],
        "recommended_next_action": "documentation change validated — ready for delivery",
        "repair_signals": {
            "loop_protection_triggered": False,
            "prior_failed_docs": 1,
            "doc_generation_automated": True,
            "ci_sync_check_added": True,
            "delivery_candidate": True,
        },
    },
    "workflow_change": {
        "aliases": ["workflow", "is_akisi", "pipeline", "process", "surec"],
        "repair_type": "workflow_change",
        "repair_status": "warning",
        "repair_score": 0.58,
        "repair_summary": "Sandbox workflow change in progress. Workflow dependency graph formalized. Validation gates added between stages. Pipeline tested in sandbox with dry run.",
        "repair_strategy": "Create working clone. Formalize workflow graph. Add validation gates. Deploy to sandbox. Run pipeline dry run. Verify gate enforcement. Deliver candidate.",
        "repair_steps": [
            "create_working_clone_from_master",
            "formalize_workflow_dependency_graph",
            "add_validation_gates",
            "deploy_to_sandbox",
            "run_pipeline_dry_run",
            "verify_gate_enforcement",
            "mark_as_delivery_candidate",
            "discard_working_clone",
        ],
        "working_clone_status": "discarded_after_workflow",
        "sandbox_status": "validated",
        "sandbox_integrity_score": 0.76,
        "sandbox_health_score": 0.72,
        "repair_validation_score": 0.66,
        "repair_confidence": 0.64,
        "repair_risk_level": "medium",
        "required_actions": [],
        "recommended_next_action": "workflow change validated — ready for delivery",
        "repair_signals": {
            "loop_protection_triggered": False,
            "prior_failed_workflows": 1,
            "workflow_graph_formalized": True,
            "validation_gates_added": True,
            "pipeline_dry_run_passed": True,
            "delivery_candidate": True,
        },
    },
}


def _select_repair_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in SANDBOX_REPAIR_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "repair_change"


def _compute_overall_repair_status(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    statuses = [i.get("repair_status", "") for i in items]
    if any(s == "blocked" for s in statuses):
        return "blocked"
    if any(s == "degraded" for s in statuses):
        return "degraded"
    if any(s == "warning" for s in statuses):
        return "warning"
    if all(s == "pass" for s in statuses):
        return "pass"
    return "warning"


def sandbox_repair_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "33.5",
        "name": "Sandbox Repair Intelligence Preview",
        "status": "sandbox_repair_intelligence_ready",
        "sandbox_execution_model": {
            "real_system": "source_of_truth",
            "master_clone": "reference_only",
            "working_clone": "repairs_here",
            "sandbox": "testing_here",
            "validation": "all_validations",
            "delivery_candidate": "ready_for_delivery",
        },
        "repair_rules": [
            "no_repair_in_real_system",
            "no_repair_in_master_clone",
            "all_repairs_in_working_clone",
            "all_testing_in_sandbox",
        ],
        "validation_model": [
            "sandbox_validation",
            "dependency_validation",
            "integration_validation",
            "workflow_validation",
            "regression_validation",
            "repair_validation",
        ],
        "cancellation_model": [
            "user_cancellation_supported",
            "system_cancellation_supported",
            "discard_working_clone_on_cancellation",
            "discard_sandbox_state_on_cancellation",
            "regenerate_from_master_clone",
            "restore_clean_state",
            "no_rollback_required",
            "no_production_impact",
        ],
        "loop_protection": {
            "detect_repeated_repair_loops": True,
            "detect_repeated_failed_repairs": True,
            "detect_repeated_temporary_fixes": True,
            "detect_recurring_symptom_only_fixes": True,
            "use_33_1_change_memory": True,
            "use_33_2_failed_change_memory": True,
            "use_33_3_planning_intelligence": True,
        },
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
            "/debug/sandbox-repair-status",
            "/debug/sandbox-repair-registry",
            "/debug/sandbox-repair-preview",
        ],
        "connected_layers": [
            "33.4", "33.3", "33.2", "33.1", "32.5", "32.4",
            "31", "30", "29",
        ],
        "technology_support": [
            "Python", "HTML", "CSS", "JavaScript", "TypeScript",
            "JSON", "YAML", "Database", "Infrastructure", "API",
            "Workflow", "Documentation",
        ],
        "safety_note": "Read-only sandbox repair intelligence preview. No actual repair actions performed.",
    }


def sandbox_repair_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for rid, r in SANDBOX_REPAIR_PROFILES.items():
        items.append(
            {
                "repair_id": rid,
                "repair_type": r["repair_type"],
                "repair_status": r["repair_status"],
                "repair_score": r["repair_score"],
                "repair_risk_level": r.get("repair_risk_level"),
                "working_clone_status": r.get("working_clone_status"),
                "sandbox_status": r.get("sandbox_status"),
                "sandbox_integrity_score": r.get("sandbox_integrity_score"),
                "sandbox_health_score": r.get("sandbox_health_score"),
                "repair_validation_score": r.get("repair_validation_score"),
                "repair_confidence": r.get("repair_confidence"),
                "loop_protection_triggered": r.get("repair_signals", {}).get("loop_protection_triggered", False),
                "delivery_candidate": r.get("repair_signals", {}).get("delivery_candidate", False),
                "step_count": len(r.get("repair_steps", [])),
            }
        )
    return {
        "layer": "33.5",
        "name": "Sandbox Repair Intelligence Registry",
        "status": "sandbox_repair_intelligence_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "repair_count": len(items),
        "repair_items": items,
        "pass_count": sum(1 for i in items if i["repair_status"] == "pass"),
        "warning_count": sum(1 for i in items if i["repair_status"] == "warning"),
        "degraded_count": sum(1 for i in items if i["repair_status"] == "degraded"),
        "blocked_count": sum(1 for i in items if i["repair_status"] == "blocked"),
        "overall_repair_score": round(
            sum(i["repair_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "overall_repair_status": _compute_overall_repair_status(items),
        "avg_sandbox_integrity": round(
            sum(i["sandbox_integrity_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "avg_sandbox_health": round(
            sum(i["sandbox_health_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "loop_protection_summary": {
            "total_loops_triggered": sum(1 for i in items if i.get("loop_protection_triggered")),
            "delivery_candidates_ready": sum(1 for i in items if i.get("delivery_candidate")),
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
    L = related_layer or "Layer 33.5"
    from clone_workspace_intelligence_preview import clone_workspace_intelligence_registry
    clone_reg = clone_workspace_intelligence_registry()
    planning_reg = change_planning_intelligence_registry()
    failed_change_reg = failed_change_intelligence_registry()
    change_reg = change_memory_intelligence_registry()
    dependency_reg = dependency_intelligence_registry()
    root_cause_reg = root_cause_intelligence_registry()

    return {
        "layer33_4_clone_workspace_intelligence": {
            "workspace_count": clone_reg.get("workspace_count"),
            "avg_sync_score": clone_reg.get("avg_sync_score"),
        },
        "layer33_3_change_planning_intelligence": {
            "plan_count": planning_reg.get("plan_count"),
            "overall_plan_score": planning_reg.get("overall_plan_score"),
        },
        "layer33_2_failed_change_intelligence": {
            "failed_change_count": failed_change_reg.get("failed_change_count"),
            "overall_failed_change_score": failed_change_reg.get("overall_failed_change_score"),
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
    }


def build_sandbox_repair_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    rid = _select_repair_profile(target_issue, command, project_area)
    r = SANDBOX_REPAIR_PROFILES[rid]
    detected = target_issue or project_area or rid
    cmd = command or detected
    L = related_layer or "Layer 33.5"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "repair_id": rid,
        "repair_type": r["repair_type"],
        "repair_status": r["repair_status"],
        "repair_score": r["repair_score"],
        "repair_summary": r.get("repair_summary"),
        "repair_strategy": r.get("repair_strategy"),
        "repair_steps": r.get("repair_steps", []),
        "repair_signals": r.get("repair_signals", {}),
        "working_clone_status": r.get("working_clone_status"),
        "sandbox_status": r.get("sandbox_status"),
        "sandbox_integrity_score": r.get("sandbox_integrity_score"),
        "sandbox_health_score": r.get("sandbox_health_score"),
        "repair_validation_score": r.get("repair_validation_score"),
        "repair_confidence": r.get("repair_confidence"),
        "repair_risk_level": r.get("repair_risk_level"),
        "required_actions": r.get("required_actions", []),
        "recommended_next_action": r.get("recommended_next_action"),
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
        "safety_note": "Read-only sandbox repair intelligence preview. No actual repair actions performed.",
    }
