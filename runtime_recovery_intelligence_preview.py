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


RECOVERY_PROFILES: Dict[str, Dict[str, Any]] = {
    "crash_recovery": {
        "aliases": ["crash", "failure", "restart", "reboot", "cökme"],
        "target_component": "application_crash_runtime",
        "recovery_category": "crash_resilience",
        "recovery_status": "warning",
        "recovery_score": 0.48,
        "recovery_findings": [
            "no_auto_restart_mechanism_implemented",
            "crash_logging_active_but_limited",
        ],
        "recovery_warnings": [
            "graceful_shutdown_not_configured",
            "no_health_check_based_auto_recovery",
        ],
        "recovery_blockers": [],
        "recovery_risk_level": "medium",
        "recovery_recommendations": [
            "implement_auto_restart_on_crash",
            "configure_graceful_shutdown",
            "add_health_check_based_auto_recovery",
        ],
        "recovery_summary": "Crash recovery is at medium risk. No auto-restart or graceful shutdown configured.",
        "required_actions": [],
        "recommended_next_action": "implement auto-restart and graceful shutdown mechanisms",
        "confidence_score": 0.62,
    },
    "state_recovery": {
        "aliases": ["state", "user_state", "persistence", "durum", "kurtarma"],
        "target_component": "state_persistence_runtime",
        "recovery_category": "state_resilience",
        "recovery_status": "pass",
        "recovery_score": 0.76,
        "recovery_findings": [
            "user_state_persisted_to_disk",
            "file_lock_mechanism_prevents_corruption",
        ],
        "recovery_warnings": [
            "state_recovery_not_tested_after_crash",
            "no_state_backup_before_write",
        ],
        "recovery_blockers": [],
        "recovery_risk_level": "low",
        "recovery_recommendations": [
            "test_state_recovery_after_crash",
            "implement_state_backup_before_write",
        ],
        "recovery_summary": "State recovery is low risk. Persistence verified but crash recovery untested.",
        "required_actions": [],
        "recommended_next_action": "test state recovery after application crash",
        "confidence_score": 0.70,
    },
    "connection_recovery": {
        "aliases": ["connection", "websocket", "reconnect", "network", "baglanti"],
        "target_component": "websocket_connection_runtime",
        "recovery_category": "connection_resilience",
        "recovery_status": "warning",
        "recovery_score": 0.42,
        "recovery_findings": [
            "websocket_reconnect_not_implemented",
            "connection_drop_handling_manual",
        ],
        "recovery_warnings": [
            "no_automatic_reconnect_with_backoff",
            "session_resume_after_disconnect_untested",
        ],
        "recovery_blockers": [],
        "recovery_risk_level": "medium",
        "recovery_recommendations": [
            "implement_websocket_auto_reconnect",
            "add_exponential_backoff_to_reconnect",
            "test_session_resume_after_disconnect",
        ],
        "recovery_summary": "Connection recovery is at medium risk. No auto-reconnect on websocket drop.",
        "required_actions": [],
        "recommended_next_action": "implement websocket auto-reconnect with exponential backoff",
        "confidence_score": 0.65,
    },
    "file_recovery": {
        "aliases": ["file", "corruption", "disk", "io", "dosya"],
        "target_component": "file_io_runtime",
        "recovery_category": "file_resilience",
        "recovery_status": "warning",
        "recovery_score": 0.54,
        "recovery_findings": [
            "no_file_integrity_checksum_before_read",
            "corruption_detection_not_implemented",
        ],
        "recovery_warnings": [
            "backup_files_not_maintained",
            "no_rollback_for_failed_writes",
        ],
        "recovery_blockers": [],
        "recovery_risk_level": "medium",
        "recovery_recommendations": [
            "add_file_integrity_checksums",
            "implement_corruption_detection",
            "maintain_backup_copies_of_critical_files",
        ],
        "recovery_summary": "File recovery is at medium risk. No integrity checks or corruption detection.",
        "required_actions": [],
        "recommended_next_action": "add file integrity checksums and corruption detection",
        "confidence_score": 0.60,
    },
    "session_recovery": {
        "aliases": ["session", "chat", "resume", "continue", "oturum"],
        "target_component": "session_resume_runtime",
        "recovery_category": "session_resilience",
        "recovery_status": "pass",
        "recovery_score": 0.80,
        "recovery_findings": [
            "stop_continue_flow_verified",
            "session_isolation_active",
        ],
        "recovery_warnings": [
            "session_resume_after_long_disconnect_untested",
            "no_session_snapshot_before_critical_ops",
        ],
        "recovery_blockers": [],
        "recovery_risk_level": "low",
        "recovery_recommendations": [
            "test_session_resume_after_extended_disconnect",
            "add_session_snapshot_before_critical_operations",
        ],
        "recovery_summary": "Session recovery is low risk. Stop/continue flow verified but extended disconnect untested.",
        "required_actions": [],
        "recommended_next_action": "test session resume after extended disconnect",
        "confidence_score": 0.76,
    },
    "dependency_recovery": {
        "aliases": ["dependency", "api", "external", "timeout", "bagimlilik"],
        "target_component": "external_dependency_runtime",
        "recovery_category": "dependency_resilience",
        "recovery_status": "degraded",
        "recovery_score": 0.38,
        "recovery_findings": [
            "no_retry_logic_on_api_failure",
            "no_circuit_breaker_pattern",
            "fallback_mode_available_but_limited",
        ],
        "recovery_warnings": [
            "api_timeout_recovers_to_fallback_untested",
            "dependency_outage_detection_not_implemented",
        ],
        "recovery_blockers": [
            "no_graceful_degradation_path_for_critical_api",
        ],
        "recovery_risk_level": "high",
        "recovery_recommendations": [
            "implement_retry_logic_with_exponential_backoff",
            "add_circuit_breaker_pattern",
            "define_graceful_degradation_paths",
        ],
        "recovery_summary": "Dependency recovery is at high risk. No retry logic or circuit breaker for external APIs.",
        "required_actions": [
            "implement_retry_logic",
            "add_circuit_breaker",
        ],
        "recommended_next_action": "implement retry logic and circuit breaker for all external dependencies",
        "confidence_score": 0.78,
    },
    "configuration_recovery": {
        "aliases": ["config", "env", "setting", "default", "ayar"],
        "target_component": "configuration_recovery_runtime",
        "recovery_category": "config_resilience",
        "recovery_status": "pass",
        "recovery_score": 0.72,
        "recovery_findings": [
            "default_configuration_fallback_available",
            "env_file_loaded_on_startup",
        ],
        "recovery_warnings": [
            "config_recovery_not_tested_after_corruption",
            "no_config_backup_before_overwrite",
        ],
        "recovery_blockers": [],
        "recovery_risk_level": "low",
        "recovery_recommendations": [
            "test_configuration_recovery_after_corruption",
            "backup_configuration_before_modification",
        ],
        "recovery_summary": "Configuration recovery is low risk. Fallback available but corruption recovery untested.",
        "required_actions": [],
        "recommended_next_action": "test configuration recovery after corruption scenario",
        "confidence_score": 0.68,
    },
    "data_recovery": {
        "aliases": ["data", "backup", "restore", "integrity", "veri"],
        "target_component": "data_recovery_runtime",
        "recovery_category": "data_resilience",
        "recovery_status": "warning",
        "recovery_score": 0.46,
        "recovery_findings": [
            "backup_and_restore_not_tested",
            "no_automated_backup_mechanism",
        ],
        "recovery_warnings": [
            "user_data_not_backed_up",
            "no_data_retention_policy",
        ],
        "recovery_blockers": [],
        "recovery_risk_level": "medium",
        "recovery_recommendations": [
            "implement_automated_backup_mechanism",
            "test_restore_procedure",
            "define_data_retention_policy",
        ],
        "recovery_summary": "Data recovery is at medium risk. No automated backup or tested restore procedure.",
        "required_actions": [],
        "recommended_next_action": "implement automated backup and test restore procedure",
        "confidence_score": 0.64,
    },
    "deployment_recovery": {
        "aliases": ["deploy", "rollback", "release", "production", "dağıtım"],
        "target_component": "deployment_rollback_runtime",
        "recovery_category": "deployment_resilience",
        "recovery_status": "degraded",
        "recovery_score": 0.36,
        "recovery_findings": [
            "rollback_procedure_not_defined",
            "no_automated_deployment_pipeline",
        ],
        "recovery_warnings": [
            "production_revert_plan_not_documented",
            "no_version_tagging_on_deployments",
        ],
        "recovery_blockers": [
            "no_rollback_mechanism_implemented",
        ],
        "recovery_risk_level": "high",
        "recovery_recommendations": [
            "define_rollback_procedure",
            "implement_automated_rollback",
            "add_version_tagging_to_all_deployments",
        ],
        "recovery_summary": "Deployment recovery is at high risk. No rollback procedure or mechanism defined.",
        "required_actions": [
            "define_rollback_procedure",
        ],
        "recommended_next_action": "define and implement deployment rollback procedure",
        "confidence_score": 0.74,
    },
}


def _select_recovery_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    for key, profile in RECOVERY_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(t.lower() in aliases or t.lower() == key for t in targets for t2 in [t]):
            for target in targets:
                tl = target.lower().strip()
                if tl in aliases or tl == key:
                    return key
    return "dependency_recovery"


def runtime_recovery_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "31.5",
        "name": "Runtime Recovery Intelligence Preview",
        "status": "runtime_recovery_intelligence_ready",
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
            "/debug/runtime-recovery-status",
            "/debug/runtime-recovery-registry",
            "/debug/runtime-recovery-preview",
        ],
        "connected_layers": [
            "31.4", "31.3", "31.2", "31.1", "30", "30.1", "30.2", "30.3", "30.4", "30.5",
            "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
        ],
        "safety_note": "Read-only runtime recovery intelligence preview. No actual recovery remediation actions performed.",
    }


def runtime_recovery_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for rid, r in RECOVERY_PROFILES.items():
        items.append(
            {
                "recovery_id": rid,
                "target_component": r["target_component"],
                "recovery_category": r["recovery_category"],
                "recovery_status": r["recovery_status"],
                "recovery_score": r["recovery_score"],
                "recovery_risk_level": r["recovery_risk_level"],
                "blocker_count": len(r.get("recovery_blockers", [])),
                "warning_count": len(r.get("recovery_warnings", [])),
                "confidence_score": r["confidence_score"],
            }
        )
    return {
        "layer": "31.5",
        "name": "Runtime Recovery Intelligence Registry",
        "status": "runtime_recovery_intelligence_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "recovery_count": len(items),
        "recovery_items": items,
        "pass_count": sum(1 for i in items if i["recovery_status"] == "pass"),
        "warning_count": sum(1 for i in items if i["recovery_status"] == "warning"),
        "degraded_count": sum(1 for i in items if i["recovery_status"] == "degraded"),
        "blocked_count": sum(1 for i in items if i["recovery_status"] == "blocked"),
        "overall_recovery_score": round(
            sum(i["recovery_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "overall_recovery_status": _compute_overall_recovery_status(items),
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


def _compute_overall_recovery_status(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    statuses = [i.get("recovery_status", "") for i in items]
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
    L = related_layer or "Layer 31.5"
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


def build_runtime_recovery_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    rid = _select_recovery_profile(target_issue, command, project_area)
    r = RECOVERY_PROFILES[rid]
    detected = target_issue or project_area or rid
    cmd = command or detected
    L = related_layer or "Layer 31.5"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "recovery_id": rid,
        "target_component": r["target_component"],
        "recovery_category": r["recovery_category"],
        "recovery_status": r["recovery_status"],
        "recovery_score": r["recovery_score"],
        "recovery_findings": r.get("recovery_findings", []),
        "recovery_warnings": r.get("recovery_warnings", []),
        "recovery_blockers": r.get("recovery_blockers", []),
        "recovery_risk_level": r.get("recovery_risk_level"),
        "recovery_recommendations": r.get("recovery_recommendations", []),
        "recovery_summary": r.get("recovery_summary"),
        "required_actions": r.get("required_actions", []),
        "recommended_next_action": r.get("recommended_next_action"),
        "confidence_score": r["confidence_score"],
        "recovery_signals": integration,
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
        "safety_note": "Read-only runtime recovery intelligence preview. No actual recovery remediation actions performed.",
    }
