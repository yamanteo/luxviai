from __future__ import annotations
from typing import Any, Dict, List, Optional

from runtime_anomaly_intelligence_preview import (
    build_runtime_anomaly_intelligence_preview,
    runtime_anomaly_intelligence_registry,
    runtime_anomaly_intelligence_status,
)
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


REGRESSION_PROFILES: Dict[str, Dict[str, Any]] = {
    "behavior_regression": {
        "aliases": ["behavior", "behaviour", "davranis", "behavioral"],
        "target_component": "behavior_regression_runtime",
        "regression_category": "behavior_regression",
        "regression_status": "degraded",
        "regression_score": 0.42,
        "regression_findings": [
            "typewriter_queue_behavior_changed_from_expected",
            "tab_switch_response_inconsistent",
            "stream_done_signal_timing_regression",
        ],
        "regression_warnings": [
            "behavioral_drift_not_tracked",
            "no_behavioral_baseline_recorded",
        ],
        "regression_blockers": [
            "tab_switch_regression_blocks_production",
        ],
        "regression_risk_level": "high",
        "regression_recommendations": [
            "establish_behavioral_baseline",
            "track_all_queue_behavior_changes",
            "resolve_tab_switch_response",
        ],
        "regression_summary": "Behavior regression detected — typewriter queue and tab switch behavior deviated from expected baseline.",
        "required_actions": [
            "establish_behavioral_baseline",
            "resolve_tab_switch_regression",
        ],
        "recommended_next_action": "establish behavioral baseline and resolve tab switch regression",
        "confidence_score": 0.71,
        "regression_signals": {
            "deviation_score": 0.58,
            "affected_components": ["typewriter_queue", "tab_switch", "stream_done"],
            "regression_scope": "production_blocking",
        },
    },
    "endpoint_regression": {
        "aliases": ["endpoint", "route", "api", "uç nokta"],
        "target_component": "endpoint_regression_runtime",
        "regression_category": "endpoint_regression",
        "regression_status": "warning",
        "regression_score": 0.55,
        "regression_findings": [
            "response_time_increased_20pct",
            "endpoint_coverage_gap_detected",
            "new_endpoint_missing_from_registry",
        ],
        "regression_warnings": [
            "endpoint_regression_test_not_active",
            "no_automated_endpoint_monitoring",
        ],
        "regression_blockers": [],
        "regression_risk_level": "medium",
        "regression_recommendations": [
            "implement_endpoint_regression_test_suite",
            "add_automated_response_time_monitoring",
            "update_endpoint_coverage_matrix",
        ],
        "regression_summary": "Endpoint regression — response time increased 20%. New endpoints missing from registry.",
        "required_actions": [
            "add_endpoint_regression_tests",
            "update_coverage_matrix",
        ],
        "recommended_next_action": "implement endpoint regression test suite and update coverage matrix",
        "confidence_score": 0.74,
        "regression_signals": {
            "response_time_degradation_pct": 20,
            "missing_endpoints": 2,
            "coverage_gap_pct": 8.5,
        },
    },
    "dependency_regression": {
        "aliases": ["dependency", "dep", "import", "module", "bagimlilik"],
        "target_component": "dependency_regression_runtime",
        "regression_category": "dependency_regression",
        "regression_status": "warning",
        "regression_score": 0.60,
        "regression_findings": [
            "new_dependency_introduced_without_review",
            "version_bump_caused_import_warning",
            "dependency_graph_increased_complexity",
        ],
        "regression_warnings": [
            "dependency_lock_not_updated",
            "no_dependency_regression_gate",
        ],
        "regression_blockers": [],
        "regression_risk_level": "medium",
        "regression_recommendations": [
            "enforce_dependency_review_process",
            "add_dependency_regression_gate",
            "update_dependency_lock_file",
        ],
        "regression_summary": "Dependency regression — new dependency introduced without review. Import warning from version bump.",
        "required_actions": [
            "review_new_dependency",
            "update_dependency_lock",
        ],
        "recommended_next_action": "enforce dependency review process and add regression gate",
        "confidence_score": 0.76,
        "regression_signals": {
            "new_dependencies": 1,
            "import_warnings": 1,
            "complexity_increase_pct": 5,
        },
    },
    "configuration_regression": {
        "aliases": ["config", "configuration", "setting", "env", "yapilandirma"],
        "target_component": "configuration_regression_runtime",
        "regression_category": "configuration_regression",
        "regression_status": "pass",
        "regression_score": 0.82,
        "regression_findings": [
            "all_config_keys_validated",
            "env_file_structure_intact",
            "fallback_values_unchanged",
        ],
        "regression_warnings": [
            "config_change_audit_not_enabled",
            "no_config_versioning",
        ],
        "regression_blockers": [],
        "regression_risk_level": "low",
        "regression_recommendations": [
            "enable_config_change_audit",
            "implement_config_versioning",
        ],
        "regression_summary": "Configuration regression check passed. All config keys validated and file structure intact.",
        "required_actions": [],
        "recommended_next_action": "enable config change audit trail",
        "confidence_score": 0.85,
        "regression_signals": {
            "validated_keys": 42,
            "changed_keys": 0,
            "fallback_values_active": 2,
        },
    },
    "runtime_regression": {
        "aliases": ["runtime", "execution", "flow", "calisma"],
        "target_component": "runtime_regression_monitor",
        "regression_category": "runtime_regression",
        "regression_status": "degraded",
        "regression_score": 0.48,
        "regression_findings": [
            "execution_path_divergence_detected",
            "event_ordering_changed_since_last_deploy",
            "runtime_behavior_not_matching_spec",
        ],
        "regression_warnings": [
            "runtime_regression_test_not_active",
            "no_execution_trace_comparison",
        ],
        "regression_blockers": [
            "execution_path_divergence_blocks_flow",
        ],
        "regression_risk_level": "high",
        "regression_recommendations": [
            "implement_runtime_regression_test_suite",
            "add_execution_trace_comparison",
            "document_expected_runtime_behavior",
        ],
        "regression_summary": "Runtime regression — execution path divergence detected. Event ordering changed since last deploy.",
        "required_actions": [
            "fix_execution_path_divergence",
            "add_runtime_regression_tests",
        ],
        "recommended_next_action": "fix execution path divergence and implement regression test suite",
        "confidence_score": 0.68,
        "regression_signals": {
            "divergence_points": 3,
            "event_reorderings": 2,
            "affected_flows": ["stream", "queue", "resume"],
        },
    },
    "stability_regression": {
        "aliases": ["stability", "stable", "kararli", "stabil"],
        "target_component": "stability_regression_runtime",
        "regression_category": "stability_regression",
        "regression_status": "warning",
        "regression_score": 0.58,
        "regression_findings": [
            "stability_score_decreased_since_layer_31_2",
            "new_stability_warnings_introduced",
            "blocker_count_unchanged",
        ],
        "regression_warnings": [
            "stability_threshold_not_configured",
            "no_automated_stability_regression_check",
        ],
        "regression_blockers": [],
        "regression_risk_level": "medium",
        "regression_recommendations": [
            "configure_stability_thresholds",
            "add_automated_stability_regression_gate",
            "investigate_new_stability_warnings",
        ],
        "regression_summary": "Stability regression — stability score decreased. New warnings introduced since Layer 31.2 assessment.",
        "required_actions": [
            "investigate_new_warnings",
            "configure_stability_thresholds",
        ],
        "recommended_next_action": "investigate new stability warnings and configure regression thresholds",
        "confidence_score": 0.72,
        "regression_signals": {
            "score_change": -0.12,
            "new_warnings": 2,
            "current_stability_score": 0.58,
        },
    },
    "recovery_regression": {
        "aliases": ["recovery", "failover", "retry", "kurtarma"],
        "target_component": "recovery_regression_runtime",
        "regression_category": "recovery_regression",
        "regression_status": "degraded",
        "regression_score": 0.40,
        "regression_findings": [
            "recovery_success_rate_decreased",
            "failover_response_time_increased",
            "retry_strategy_regression_from_layer_31_5",
        ],
        "regression_warnings": [
            "recovery_baseline_not_documented",
            "no_recovery_regression_test",
        ],
        "regression_blockers": [
            "failover_lag_exceeds_acceptable_threshold",
        ],
        "regression_risk_level": "high",
        "regression_recommendations": [
            "document_recovery_baseline",
            "implement_recovery_regression_tests",
            "optimize_failover_response_time",
        ],
        "regression_summary": "Recovery regression — recovery success rate decreased. Failover lag exceeds threshold.",
        "required_actions": [
            "document_recovery_baseline",
            "optimize_failover_response",
        ],
        "recommended_next_action": "document recovery baseline and optimize failover response time",
        "confidence_score": 0.64,
        "regression_signals": {
            "success_rate_change_pct": -15,
            "failover_lag_ms": 3200,
            "retry_failures": 4,
        },
    },
}


def _select_regression_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in REGRESSION_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "behavior_regression"


def _compute_overall_regression_status(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    statuses = [i.get("regression_status", "") for i in items]
    if any(s == "blocked" for s in statuses):
        return "blocked"
    if any(s == "degraded" for s in statuses):
        return "degraded"
    if any(s == "warning" for s in statuses):
        return "warning"
    if all(s == "pass" for s in statuses):
        return "pass"
    return "warning"


def regression_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "32.2",
        "name": "Regression Intelligence Preview",
        "status": "regression_intelligence_ready",
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
            "/debug/regression-status",
            "/debug/regression-registry",
            "/debug/regression-preview",
        ],
        "connected_layers": [
            "32.1", "31.5", "31.4", "31.3", "31.2", "31.1",
            "31", "30", "30.5", "30.4", "30.3", "30.2", "30.1",
            "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
        ],
        "safety_note": "Read-only regression intelligence preview. No actual regression remediation actions performed.",
    }


def regression_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for rid, r in REGRESSION_PROFILES.items():
        items.append(
            {
                "regression_id": rid,
                "target_component": r["target_component"],
                "regression_category": r["regression_category"],
                "regression_status": r["regression_status"],
                "regression_score": r["regression_score"],
                "regression_risk_level": r["regression_risk_level"],
                "blocker_count": len(r.get("regression_blockers", [])),
                "warning_count": len(r.get("regression_warnings", [])),
                "confidence_score": r["confidence_score"],
            }
        )
    return {
        "layer": "32.2",
        "name": "Regression Intelligence Registry",
        "status": "regression_intelligence_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "regression_count": len(items),
        "regression_items": items,
        "pass_count": sum(1 for i in items if i["regression_status"] == "pass"),
        "warning_count": sum(1 for i in items if i["regression_status"] == "warning"),
        "degraded_count": sum(1 for i in items if i["regression_status"] == "degraded"),
        "blocked_count": sum(1 for i in items if i["regression_status"] == "blocked"),
        "overall_regression_score": round(
            sum(i["regression_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "overall_regression_status": _compute_overall_regression_status(items),
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
    L = related_layer or "Layer 32.2"
    layer31 = layer31_full_status()
    layer30 = layer30_full_status()
    layer29 = layer29_status_snapshot()
    system_health = system_health_intelligence_status()
    stability = runtime_stability_intelligence_status()
    risk = runtime_risk_intelligence_status()
    drift = runtime_drift_intelligence_status()
    recovery = runtime_recovery_intelligence_status()
    anomaly_status = runtime_anomaly_intelligence_status()
    anomaly_registry = runtime_anomaly_intelligence_registry()

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
        "layer32_1_anomaly_intelligence": {
            "status": anomaly_status.get("status"),
            "anomaly_count": anomaly_registry.get("anomaly_count"),
            "overall_anomaly_score": anomaly_registry.get("overall_anomaly_score"),
        },
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


def build_regression_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    rid = _select_regression_profile(target_issue, command, project_area)
    r = REGRESSION_PROFILES[rid]
    detected = target_issue or project_area or rid
    cmd = command or detected
    L = related_layer or "Layer 32.2"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "regression_id": rid,
        "target_component": r["target_component"],
        "regression_category": r["regression_category"],
        "regression_status": r["regression_status"],
        "regression_score": r["regression_score"],
        "regression_findings": r.get("regression_findings", []),
        "regression_warnings": r.get("regression_warnings", []),
        "regression_blockers": r.get("regression_blockers", []),
        "regression_risk_level": r.get("regression_risk_level"),
        "regression_recommendations": r.get("regression_recommendations", []),
        "regression_summary": r.get("regression_summary"),
        "required_actions": r.get("required_actions", []),
        "recommended_next_action": r.get("recommended_next_action"),
        "confidence_score": r["confidence_score"],
        "regression_signals": r.get("regression_signals", {}),
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
        "safety_note": "Read-only regression intelligence preview. No actual regression remediation actions performed.",
    }
