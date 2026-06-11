from __future__ import annotations
from typing import Any, Dict, List, Optional

from failure_memory_intelligence_preview import (
    build_failure_memory_intelligence_preview,
    failure_memory_intelligence_registry,
)
from regression_intelligence_preview import (
    regression_intelligence_registry,
)
from runtime_anomaly_intelligence_preview import (
    runtime_anomaly_intelligence_registry,
)
from layer31_status_snapshot import layer31_full_status
from layer30_status_snapshot import layer30_full_status


DEPENDENCY_PROFILES: Dict[str, Dict[str, Any]] = {
    "file_dependency": {
        "aliases": ["file", "dosya", "source", "kaynak"],
        "dependency_category": "file_dependency",
        "dependency_type": "source_level",
        "dependency_status": "warning",
        "dependency_score": 0.58,
        "affected_files": [
            "app.py",
            "lux_fault_report.py",
            "endpoint_coverage_matrix.py",
            "scripts/smoke_check.py",
        ],
        "affected_modules": [
            "luxviai.app.core",
            "luxviai.fault.reporting",
            "luxviai.coverage.tracking",
        ],
        "affected_systems": [
            "fault_report_system",
            "endpoint_registration",
            "smoke_test_runner",
        ],
        "triggered_systems": [
            "layer_build_pipeline",
            "runtime_intelligence_chain",
        ],
        "impacted_by_systems": [
            "module_import_graph",
            "file_watch_service",
        ],
        "dependency_findings": [
            "circular_import_across_app_and_lux_fault_report",
            "endpoint_coverage_matrix_exports_used_by_app",
            "smoke_check_depends_on_app_import_path",
        ],
        "dependency_risk_level": "medium",
        "dependency_recommendations": [
            "break_circular_import_between_app_and_fault_report",
            "extract_coverage_matrix_as_standalone_service",
            "add_import_boundary_tests",
        ],
        "dependency_summary": "File-level dependency chain detected. Circular import between app.py and lux_fault_report.py. Coverage matrix acts as shared export hub.",
        "required_actions": [
            "break_circular_import_chain",
            "add_import_warning_gate",
        ],
        "recommended_next_action": "break circular import between app.py and lux_fault_report.py",
        "confidence_score": 0.76,
        "dependency_signals": {
            "file_count": 4,
            "circular_paths": 1,
            "shared_exports": 3,
        },
    },
    "module_dependency": {
        "aliases": ["module", "modul", "package", "paket", "import"],
        "dependency_category": "module_dependency",
        "dependency_type": "import_graph",
        "dependency_status": "degraded",
        "dependency_score": 0.45,
        "affected_files": [
            "layer31_status_snapshot.py",
            "system_health_intelligence_preview.py",
            "runtime_stability_intelligence_preview.py",
        ],
        "affected_modules": [
            "luxviai.layer31.snapshot",
            "luxviai.intelligence.system_health",
            "luxviai.intelligence.runtime_stability",
        ],
        "affected_systems": [
            "layer_snapshot_system",
            "intelligence_status_aggregator",
        ],
        "triggered_systems": [
            "runtime_intelligence_preview_chain",
            "fault_report_section_builder",
        ],
        "impacted_by_systems": [
            "layer_migration_pipeline",
            "module_registration_service",
        ],
        "dependency_findings": [
            "module_cross_import_across_intelligence_layers",
            "snapshot_module_imports_all_sub_intelligence_modules",
            "dependency_depth_exceeds_recommended_limit",
        ],
        "dependency_risk_level": "high",
        "dependency_recommendations": [
            "flatten_import_dependency_graph",
            "introduce_abstraction_layer_between_snapshots_and_intelligence",
            "limit_import_depth_to_2_levels",
        ],
        "dependency_summary": "Module dependency chain exceeds recommended depth. Snapshot module imports all sub-intelligence modules creating tight coupling.",
        "required_actions": [
            "reduce_import_depth",
            "add_abstraction_layer",
        ],
        "recommended_next_action": "flatten import dependency graph and introduce abstraction layer",
        "confidence_score": 0.70,
        "dependency_signals": {
            "max_import_depth": 4,
            "cross_imports": 3,
            "module_count": 8,
        },
    },
    "system_trigger_dependency": {
        "aliases": ["trigger", "tetikleyici", "chain", "zincir"],
        "dependency_category": "system_trigger_dependency",
        "dependency_type": "propagation",
        "dependency_status": "degraded",
        "dependency_score": 0.42,
        "affected_files": [
            "app.py",
            "layer_build_pipeline.py",
        ],
        "affected_modules": [
            "luxviai.system.trigger",
            "luxviai.layer.builder",
        ],
        "affected_systems": [
            "layer_build_pipeline",
            "runtime_intelligence_chain",
            "fault_report_aggregator",
        ],
        "triggered_systems": [
            "status_snapshot_refresh",
            "fault_report_section_rebuild",
            "endpoint_coverage_recalculation",
        ],
        "impacted_by_systems": [
            "module_import_chain",
            "file_change_detector",
        ],
        "dependency_findings": [
            "single_trigger_cascades_to_3_downstream_systems",
            "fault_report_full_rebuild_on_every_trigger",
            "no_circuit_breaker_on_cascade_failure",
        ],
        "dependency_risk_level": "high",
        "dependency_recommendations": [
            "add_cascade_breaker_between_trigger_and_downstream",
            "implement_incremental_fault_report_update",
            "add_circuit_breaker_on_cascade_failure",
        ],
        "dependency_summary": "System trigger cascade detected. Single trigger propagates to 3 downstream systems without circuit breaker.",
        "required_actions": [
            "implement_cascade_breaker",
            "add_incremental_update_path",
        ],
        "recommended_next_action": "implement cascade breaker between trigger and downstream systems",
        "confidence_score": 0.68,
        "dependency_signals": {
            "cascade_depth": 3,
            "downstream_systems": 3,
            "trigger_frequency_per_hour": 12,
        },
    },
    "system_impact_dependency": {
        "aliases": ["impact", "etki", "affected", "downstream"],
        "dependency_category": "system_impact_dependency",
        "dependency_type": "reverse_propagation",
        "dependency_status": "warning",
        "dependency_score": 0.52,
        "affected_files": [
            "runtime_stability_intelligence_preview.py",
            "runtime_risk_intelligence_preview.py",
            "runtime_drift_intelligence_preview.py",
            "runtime_recovery_intelligence_preview.py",
        ],
        "affected_modules": [
            "luxviai.intelligence.runtime_stability",
            "luxviai.intelligence.runtime_risk",
            "luxviai.intelligence.runtime_drift",
            "luxviai.intelligence.runtime_recovery",
        ],
        "affected_systems": [
            "layer31_intelligence_suite",
            "runtime_intelligence_preview_chain",
        ],
        "triggered_systems": [
            "fault_report_section_builder",
            "intelligence_status_aggregator",
        ],
        "impacted_by_systems": [
            "layer32_anomaly_intelligence",
            "layer32_regression_intelligence",
            "layer32_failure_memory_intelligence",
            "config_change_service",
        ],
        "dependency_findings": [
            "layer31_intelligence_modules_impacted_by_layer32_anomaly_detection",
            "fault_report_section_order_creates_hidden_dependency",
            "config_change_propagates_to_all_intelligence_layers",
        ],
        "dependency_risk_level": "medium",
        "dependency_recommendations": [
            "document_section_dependency_order_in_fault_report",
            "add_config_change_notification_to_intelligence_layers",
            "decouple_layer31_from_layer32_direct_imports",
        ],
        "dependency_summary": "System impact propagation detected. Layer 31 intelligence layers are impacted by Layer 32 anomaly detection and config changes.",
        "required_actions": [
            "document_impact_dependency_order",
            "add_config_change_broadcast",
        ],
        "recommended_next_action": "document impact dependency order and add config change broadcast to intelligence layers",
        "confidence_score": 0.73,
        "dependency_signals": {
            "impacted_system_count": 5,
            "propagation_paths": 3,
            "config_dependency_count": 4,
        },
    },
    "cross_layer_dependency": {
        "aliases": ["cross", "catilarasi", "layer", "interlayer"],
        "dependency_category": "cross_layer_dependency",
        "dependency_type": "inter_layer",
        "dependency_status": "degraded",
        "dependency_score": 0.48,
        "affected_files": [
            "layer29_status_snapshot.py",
            "layer30_status_snapshot.py",
            "layer31_status_snapshot.py",
        ],
        "affected_modules": [
            "luxviai.layer29.snapshot",
            "luxviai.layer30.snapshot",
            "luxviai.layer31.snapshot",
        ],
        "affected_systems": [
            "layer_snapshot_aggregator",
            "intelligence_core",
        ],
        "triggered_systems": [
            "fault_report_preview_builder",
            "master_status_summary",
        ],
        "impacted_by_systems": [
            "layer32_intelligence_family",
            "layer28_patch_lifecycle",
            "layer27_status_snapshot",
        ],
        "dependency_findings": [
            "cross_layer_import_between_layer29_and_layer30_snapshots",
            "layer_status_snapshots_form_vertical_dependency_chain",
            "new_layer_additions_require_updates_to_multiple_snapshots",
        ],
        "dependency_risk_level": "high",
        "dependency_recommendations": [
            "introduce_layer_abstraction_registry",
            "remove_direct_cross_layer_imports",
            "implement_event_based_layer_communication",
        ],
        "dependency_summary": "Cross-layer dependency chain. Layer 29-30-31 snapshots form vertical dependency. New layers require multi-snapshot updates.",
        "required_actions": [
            "introduce_layer_registry_abstraction",
            "remove_direct_cross_layer_imports",
        ],
        "recommended_next_action": "introduce layer abstraction registry to decouple snapshot dependencies",
        "confidence_score": 0.66,
        "dependency_signals": {
            "direct_cross_imports": 4,
            "layer_chain_depth": 3,
            "affected_snapshots": 5,
        },
    },
    "external_dependency": {
        "aliases": ["external", "dis", "third_party", "api"],
        "dependency_category": "external_dependency",
        "dependency_type": "third_party",
        "dependency_status": "warning",
        "dependency_score": 0.55,
        "affected_files": [
            "app.py",
            "requirements.txt",
        ],
        "affected_modules": [
            "luxviai.external.api",
            "luxviai.dependencies.external",
        ],
        "affected_systems": [
            "external_api_gateway",
            "dependency_resolver",
        ],
        "triggered_systems": [
            "deepseek_api",
            "openai_fallback",
        ],
        "impacted_by_systems": [
            "api_version_changes",
            "rate_limit_policies",
            "deprecation_cycles",
        ],
        "dependency_findings": [
            "external_deepseek_api_is_critical_path_single_point_of_failure",
            "fallback_to_openai_not_fully_integrated",
            "no_api_version_pinning_in_requirements",
        ],
        "dependency_risk_level": "high",
        "dependency_recommendations": [
            "implement_multi_provider_failover",
            "pin_external_api_versions",
            "add_api_deprecation_monitoring",
        ],
        "dependency_summary": "External dependency on DeepSeek API is a single point of failure. OpenAI fallback not fully integrated. No version pinning.",
        "required_actions": [
            "add_multi_provider_failover",
            "pin_dependency_versions",
        ],
        "recommended_next_action": "implement multi-provider failover and pin external API versions",
        "confidence_score": 0.64,
        "dependency_signals": {
            "external_deps": 2,
            "critical_spof": 1,
            "fallback_readiness_pct": 40,
        },
    },
    "configuration_dependency": {
        "aliases": ["config", "env", "setting", "yapilandirma"],
        "dependency_category": "configuration_dependency",
        "dependency_type": "environment",
        "dependency_status": "pass",
        "dependency_score": 0.80,
        "affected_files": [
            ".env",
            "app.py",
        ],
        "affected_modules": [
            "luxviai.config.loader",
            "luxviai.env.resolver",
        ],
        "affected_systems": [
            "config_loader",
            "env_resolver",
        ],
        "triggered_systems": [
            "api_key_authentication",
            "feature_flag_evaluation",
        ],
        "impacted_by_systems": [
            "deployment_pipeline",
            "secrets_manager",
        ],
        "dependency_findings": [
            "config_loading_centralized_in_app.py_init",
            "fallback_config_active_for_non_critical_keys",
            "env_file_structure_documented",
        ],
        "dependency_risk_level": "low",
        "dependency_recommendations": [
            "extract_config_loader_as_independent_module",
            "add_config_schema_validation",
            "implement_hierarchical_config_override",
        ],
        "dependency_summary": "Configuration dependency chain healthy. Config loading centralized in app.py. Fallback config active for non-critical keys.",
        "required_actions": [],
        "recommended_next_action": "extract config loader as independent module with schema validation",
        "confidence_score": 0.82,
        "dependency_signals": {
            "config_sources": 2,
            "fallback_keys": 3,
            "validation_enabled": False,
        },
    },
}


def _select_dependency_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in DEPENDENCY_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "file_dependency"


def _compute_overall_dependency_status(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    statuses = [i.get("dependency_status", "") for i in items]
    if any(s == "blocked" for s in statuses):
        return "blocked"
    if any(s == "degraded" for s in statuses):
        return "degraded"
    if any(s == "warning" for s in statuses):
        return "warning"
    if all(s == "pass" for s in statuses):
        return "pass"
    return "warning"


def dependency_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "32.5",
        "name": "Dependency Intelligence Preview",
        "status": "dependency_intelligence_ready",
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
            "/debug/dependency-status",
            "/debug/dependency-registry",
            "/debug/dependency-preview",
        ],
        "connected_layers": [
            "32.3", "32.2", "32.1", "31", "30", "29",
        ],
        "safety_note": "Read-only dependency intelligence preview. No actual dependency remediation actions performed.",
    }


def dependency_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for did, d in DEPENDENCY_PROFILES.items():
        items.append(
            {
                "dependency_id": did,
                "dependency_category": d["dependency_category"],
                "dependency_type": d["dependency_type"],
                "dependency_status": d["dependency_status"],
                "dependency_score": d["dependency_score"],
                "dependency_risk_level": d["dependency_risk_level"],
                "affected_file_count": len(d.get("affected_files", [])),
                "affected_system_count": len(d.get("affected_systems", [])),
                "confidence_score": d["confidence_score"],
            }
        )
    return {
        "layer": "32.5",
        "name": "Dependency Intelligence Registry",
        "status": "dependency_intelligence_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "dependency_count": len(items),
        "dependency_items": items,
        "pass_count": sum(1 for i in items if i["dependency_status"] == "pass"),
        "warning_count": sum(1 for i in items if i["dependency_status"] == "warning"),
        "degraded_count": sum(1 for i in items if i["dependency_status"] == "degraded"),
        "blocked_count": sum(1 for i in items if i["dependency_status"] == "blocked"),
        "overall_dependency_score": round(
            sum(i["dependency_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "overall_dependency_status": _compute_overall_dependency_status(items),
        "dependency_type_breakdown": {
            "source_level": sum(1 for i in items if i["dependency_type"] == "source_level"),
            "import_graph": sum(1 for i in items if i["dependency_type"] == "import_graph"),
            "propagation": sum(1 for i in items if i["dependency_type"] == "propagation"),
            "reverse_propagation": sum(1 for i in items if i["dependency_type"] == "reverse_propagation"),
            "inter_layer": sum(1 for i in items if i["dependency_type"] == "inter_layer"),
            "third_party": sum(1 for i in items if i["dependency_type"] == "third_party"),
            "environment": sum(1 for i in items if i["dependency_type"] == "environment"),
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
    L = related_layer or "Layer 32.5"
    layer31 = layer31_full_status()
    layer30 = layer30_full_status()
    failure_reg = failure_memory_intelligence_registry()
    regression_reg = regression_intelligence_registry()
    anomaly_reg = runtime_anomaly_intelligence_registry()

    return {
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
    }


def build_dependency_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    did = _select_dependency_profile(target_issue, command, project_area)
    d = DEPENDENCY_PROFILES[did]
    detected = target_issue or project_area or did
    cmd = command or detected
    L = related_layer or "Layer 32.5"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "dependency_id": did,
        "dependency_category": d["dependency_category"],
        "dependency_type": d["dependency_type"],
        "dependency_status": d["dependency_status"],
        "dependency_score": d["dependency_score"],
        "affected_files": d.get("affected_files", []),
        "affected_modules": d.get("affected_modules", []),
        "affected_systems": d.get("affected_systems", []),
        "triggered_systems": d.get("triggered_systems", []),
        "impacted_by_systems": d.get("impacted_by_systems", []),
        "dependency_findings": d.get("dependency_findings", []),
        "dependency_risk_level": d.get("dependency_risk_level"),
        "dependency_recommendations": d.get("dependency_recommendations", []),
        "dependency_summary": d.get("dependency_summary"),
        "required_actions": d.get("required_actions", []),
        "recommended_next_action": d.get("recommended_next_action"),
        "confidence_score": d["confidence_score"],
        "dependency_signals": d.get("dependency_signals", {}),
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
        "safety_note": "Read-only dependency intelligence preview. No actual dependency remediation actions performed.",
    }
