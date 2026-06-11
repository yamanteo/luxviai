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


RISK_PROFILES: Dict[str, Dict[str, Any]] = {
    "data_loss_risk": {
        "aliases": ["data", "loss", "corruption", "kayıp", "veri"],
        "target_component": "data_persistence_runtime",
        "risk_category": "data_integrity",
        "risk_status": "warning",
        "risk_score": 0.62,
        "risk_findings": [
            "concurrent_write_contention_not_tested",
            "file_lock_mechanism_working_but_limited",
        ],
        "risk_warnings": [
            "no_user_storage_quota",
            "large_file_handling_not_tested",
        ],
        "risk_blockers": [],
        "risk_level": "medium",
        "risk_recommendations": [
            "add_user_storage_quota",
            "test_concurrent_write_scenarios",
            "implement_periodic_data_integrity_check",
        ],
        "risk_summary": "Data persistence carries medium risk. Concurrent writes and storage limits need attention.",
        "required_actions": [],
        "recommended_next_action": "test concurrent write contention and add storage quota",
        "confidence_score": 0.70,
    },
    "api_failure_risk": {
        "aliases": ["api", "external", "deepseek", "openai", "timeout", "dış"],
        "target_component": "external_api_runtime",
        "risk_category": "integration_reliability",
        "risk_status": "degraded",
        "risk_score": 0.45,
        "risk_findings": [
            "deepseek_api_single_point_of_failure",
            "retry_logic_not_implemented",
            "timeout_configuration_not_tuned",
        ],
        "risk_warnings": [
            "api_key_not_rotated",
            "fallback_mode_untested_under_load",
        ],
        "risk_blockers": [
            "no_circuit_breaker_pattern",
        ],
        "risk_level": "high",
        "risk_recommendations": [
            "implement_retry_logic_with_exponential_backoff",
            "add_circuit_breaker_pattern",
            "tune_timeout_configuration_per_endpoint",
            "schedule_api_key_rotation",
        ],
        "risk_summary": "External API dependency carries high risk. No retry logic, circuit breaker, or tuned timeouts.",
        "required_actions": [
            "implement_retry_logic",
            "add_circuit_breaker_pattern",
        ],
        "recommended_next_action": "implement retry logic and circuit breaker for all external API calls",
        "confidence_score": 0.82,
    },
    "security_exposure_risk": {
        "aliases": ["security", "auth", "token", "cors", "güvenlik", "yetki"],
        "target_component": "security_boundary_runtime",
        "risk_category": "security_posture",
        "risk_status": "warning",
        "risk_score": 0.55,
        "risk_findings": [
            "cors_policy_permissive_all_origins",
            "auth_token_stored_in_env_variable",
            "no_rate_limiting_implemented",
        ],
        "risk_warnings": [
            "no_request_validation_middleware",
            "no_security_headers_on_responses",
        ],
        "risk_blockers": [],
        "risk_level": "medium",
        "risk_recommendations": [
            "tighten_cors_policy_for_production",
            "add_rate_limiting_middleware",
            "add_security_headers",
            "implement_request_validation_middleware",
        ],
        "risk_summary": "Security posture carries medium risk. CORS is permissive and rate limiting is absent.",
        "required_actions": [],
        "recommended_next_action": "tighten CORS policy and add rate limiting middleware",
        "confidence_score": 0.75,
    },
    "performance_degradation_risk": {
        "aliases": ["performance", "speed", "latency", "slow", "yavaş", "performans"],
        "target_component": "performance_runtime",
        "risk_category": "performance_health",
        "risk_status": "warning",
        "risk_score": 0.60,
        "risk_findings": [
            "load_testing_not_executed",
            "no_performance_budget_defined",
        ],
        "risk_warnings": [
            "typewriter_queue_backpressure_untested",
            "websocket_stream_latency_not_monitored",
        ],
        "risk_blockers": [],
        "risk_level": "medium",
        "risk_recommendations": [
            "execute_load_testing",
            "define_performance_budget",
            "monitor_websocket_latency",
            "test_typewriter_queue_backpressure",
        ],
        "risk_summary": "Performance carries medium risk. No load testing performed and no performance budget defined.",
        "required_actions": [],
        "recommended_next_action": "execute load testing and define performance budget",
        "confidence_score": 0.72,
    },
    "state_corruption_risk": {
        "aliases": ["state", "session", "memory", "file", "durum", "oturum"],
        "target_component": "state_management_runtime",
        "risk_category": "state_integrity",
        "risk_status": "pass",
        "risk_score": 0.78,
        "risk_findings": [
            "user_state_persistence_verified",
            "file_lock_mechanism_working",
            "session_isolation_active",
        ],
        "risk_warnings": [
            "concurrent_write_not_tested",
            "no_state_rollback_capability",
        ],
        "risk_blockers": [],
        "risk_level": "low",
        "risk_recommendations": [
            "test_concurrent_write_scenarios",
            "implement_state_snapshot_for_rollback",
        ],
        "risk_summary": "State management risk is low. Persistence verified but concurrent writes untested.",
        "required_actions": [],
        "recommended_next_action": "test concurrent writes and add state snapshot capability",
        "confidence_score": 0.76,
    },
    "deployment_risk": {
        "aliases": ["deploy", "deployment", "release", "production", "go-live", "dağıtım"],
        "target_component": "deployment_pipeline_runtime",
        "risk_category": "deployment_safety",
        "risk_status": "warning",
        "risk_score": 0.58,
        "risk_findings": [
            "no_automated_deployment_pipeline",
            "deployment_runbook_not_documented",
        ],
        "risk_warnings": [
            "production_review_not_scheduled",
            "rollback_procedure_not_defined",
            "health_check_endpoint_exists_but_not_integrated",
        ],
        "risk_blockers": [],
        "risk_level": "medium",
        "risk_recommendations": [
            "document_deployment_runbook",
            "define_rollback_procedure",
            "schedule_production_review",
            "automate_deployment_pipeline",
        ],
        "risk_summary": "Deployment carries medium risk. No automated pipeline, runbook, or rollback procedure.",
        "required_actions": [],
        "recommended_next_action": "document deployment runbook and define rollback procedure",
        "confidence_score": 0.74,
    },
    "dependency_failure_risk": {
        "aliases": ["dependency", "module", "import", "package", "bağımlılık"],
        "target_component": "dependency_graph_runtime",
        "risk_category": "dependency_health",
        "risk_status": "pass",
        "risk_score": 0.80,
        "risk_findings": [
            "all_modules_load_without_error",
            "dependency_graph_verified",
        ],
        "risk_warnings": [
            "no_dependency_version_pinning_for_all_packages",
            "no_automated_dependency_audit",
        ],
        "risk_blockers": [],
        "risk_level": "low",
        "risk_recommendations": [
            "pin_all_dependency_versions",
            "add_automated_dependency_audit_to_pipeline",
        ],
        "risk_summary": "Dependency failure risk is low. All modules load correctly, version pinning needs attention.",
        "required_actions": [],
        "recommended_next_action": "pin all dependency versions and add automated audit",
        "confidence_score": 0.78,
    },
    "concurrency_risk": {
        "aliases": ["concurrency", "async", "thread", "race", "lock", "eşzamanlı"],
        "target_component": "concurrency_runtime",
        "risk_category": "concurrency_safety",
        "risk_status": "pass",
        "risk_score": 0.76,
        "risk_findings": [
            "file_lock_mechanism_working",
            "async_routes_defined_correctly",
        ],
        "risk_warnings": [
            "thread_safety_not_fully_audited",
            "race_condition_testing_not_performed",
        ],
        "risk_blockers": [],
        "risk_level": "low",
        "risk_recommendations": [
            "audit_thread_safety_across_modules",
            "perform_race_condition_testing",
        ],
        "risk_summary": "Concurrency risk is low. File locks and async patterns verified, thread safety audit pending.",
        "required_actions": [],
        "recommended_next_action": "audit thread safety and perform race condition testing",
        "confidence_score": 0.74,
    },
    "configuration_drift_risk": {
        "aliases": ["config", "configuration", "env", "setting", "ayar", "yapılandırma"],
        "target_component": "configuration_runtime",
        "risk_category": "configuration_integrity",
        "risk_status": "warning",
        "risk_score": 0.52,
        "risk_findings": [
            "env_file_check_not_strict",
            "no_configuration_validation_schema",
        ],
        "risk_warnings": [
            "fallback_mode_disables_critical_features",
            "configuration_not_documented",
        ],
        "risk_blockers": [],
        "risk_level": "medium",
        "risk_recommendations": [
            "add_strict_env_validation_on_boot",
            "create_configuration_validation_schema",
            "document_all_configuration_parameters",
        ],
        "risk_summary": "Configuration drift carries medium risk. No strict validation or documented parameters.",
        "required_actions": [],
        "recommended_next_action": "add strict environment validation and configuration schema",
        "confidence_score": 0.68,
    },
}


def _select_risk_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    for key, profile in RISK_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(t.lower() in aliases or t.lower() == key for t in targets for t2 in [t]):
            for target in targets:
                tl = target.lower().strip()
                if tl in aliases or tl == key:
                    return key
    return "api_failure_risk"


def runtime_risk_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "31.3",
        "name": "Runtime Risk Intelligence Preview",
        "status": "runtime_risk_intelligence_ready",
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
            "/debug/runtime-risk-status",
            "/debug/runtime-risk-registry",
            "/debug/runtime-risk-preview",
        ],
        "connected_layers": [
            "31.2", "31.1", "30", "30.1", "30.2", "30.3", "30.4", "30.5",
            "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
        ],
        "safety_note": "Read-only runtime risk intelligence preview. No actual risk remediation actions performed.",
    }


def runtime_risk_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for rid, r in RISK_PROFILES.items():
        items.append(
            {
                "risk_id": rid,
                "target_component": r["target_component"],
                "risk_category": r["risk_category"],
                "risk_status": r["risk_status"],
                "risk_score": r["risk_score"],
                "risk_level": r["risk_level"],
                "blocker_count": len(r.get("risk_blockers", [])),
                "warning_count": len(r.get("risk_warnings", [])),
                "confidence_score": r["confidence_score"],
            }
        )
    return {
        "layer": "31.3",
        "name": "Runtime Risk Intelligence Registry",
        "status": "runtime_risk_intelligence_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "risk_count": len(items),
        "risk_items": items,
        "pass_count": sum(1 for i in items if i["risk_status"] == "pass"),
        "warning_count": sum(1 for i in items if i["risk_status"] == "warning"),
        "degraded_count": sum(1 for i in items if i["risk_status"] == "degraded"),
        "blocked_count": sum(1 for i in items if i["risk_status"] == "blocked"),
        "overall_risk_score": round(
            sum(i["risk_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "overall_risk_status": _compute_overall_risk_status(items),
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


def _compute_overall_risk_status(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    statuses = [i.get("risk_status", "") for i in items]
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
    L = related_layer or "Layer 31.3"
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


def build_runtime_risk_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    rid = _select_risk_profile(target_issue, command, project_area)
    r = RISK_PROFILES[rid]
    detected = target_issue or project_area or rid
    cmd = command or detected
    L = related_layer or "Layer 31.3"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "risk_id": rid,
        "target_component": r["target_component"],
        "risk_category": r["risk_category"],
        "risk_status": r["risk_status"],
        "risk_score": r["risk_score"],
        "risk_findings": r.get("risk_findings", []),
        "risk_warnings": r.get("risk_warnings", []),
        "risk_blockers": r.get("risk_blockers", []),
        "risk_level": r.get("risk_level"),
        "risk_recommendations": r.get("risk_recommendations", []),
        "risk_summary": r.get("risk_summary"),
        "required_actions": r.get("required_actions", []),
        "recommended_next_action": r.get("recommended_next_action"),
        "confidence_score": r["confidence_score"],
        "risk_signals": integration,
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
        "safety_note": "Read-only runtime risk intelligence preview. No actual risk remediation actions performed.",
    }
