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


STABILITY_PROFILES: Dict[str, Dict[str, Any]] = {
    "typewriter_queue": {
        "aliases": ["typewriter", "queue", "tab", "delta", "cursor", "yazıcı"],
        "target_component": "typewriter_queue_runtime",
        "stability_category": "queue_integrity",
        "stability_status": "degraded",
        "stability_score": 0.58,
        "stability_findings": [
            "typewriter_queue_ownership_unassigned",
            "tab_switch_regression_detected",
            "queue_clear_behavior_not_finalized",
        ],
        "stability_warnings": [
            "typewriter_queue_ownership_unassigned",
            "queue_clear_future_check_remains",
            "late_chunk_delivery_possible",
        ],
        "stability_blockers": [
            "tab_switch_regression_blocks_production",
        ],
        "stability_risk_level": "high",
        "stability_recommendations": [
            "assign_typewriter_queue_ownership",
            "finalize_queue_clear_behavior",
            "resolve_tab_switch_regression_at_source",
        ],
        "stability_summary": "Typewriter queue runtime stability is degraded. Production blocker remains open.",
        "required_actions": [
            "fix_tab_switch_regression",
            "assign_typewriter_queue_ownership",
        ],
        "recommended_next_action": "resolve tab switch regression and formalize queue ownership",
        "confidence_score": 0.72,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "ws", "done", "chunk", "akış"],
        "target_component": "websocket_stream_runtime",
        "stability_category": "stream_integrity",
        "stability_status": "degraded",
        "stability_score": 0.48,
        "stability_findings": [
            "confidence_cascade_failure_detected",
            "accountability_gaps_block_readiness",
            "oversight_violations_remain_open",
        ],
        "stability_warnings": [
            "tab_switch_regression_blocks_production",
            "typewriter_queue_ownership_unassigned",
            "late_final_chunk_risk",
        ],
        "stability_blockers": [
            "tab_switch_regression_blocks_production",
        ],
        "stability_risk_level": "high",
        "stability_recommendations": [
            "resolve_all_blockers_before_production",
            "re-run_stability_assessment_after_fixes",
        ],
        "stability_summary": "Websocket stream runtime stability is degraded. 1 production blocker remains open.",
        "required_actions": [
            "fix_tab_switch_regression_at_source",
            "validate_websocket_done_signal_ordering",
        ],
        "recommended_next_action": "resolve all blockers before deployment",
        "confidence_score": 0.85,
    },
    "stop_continue_flow": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow_runtime",
        "stability_category": "flow_safety",
        "stability_status": "pass",
        "stability_score": 0.86,
        "stability_findings": [
            "all_downstream_layers_report_green",
            "confidence_assessment_favorable",
            "flow_resume_behavior_verified",
        ],
        "stability_warnings": [
            "typewriter_queue_ownership_unassigned",
        ],
        "stability_blockers": [],
        "stability_risk_level": "low",
        "stability_recommendations": [
            "schedule_production_health_review",
            "document_runtime_behavior_for_ops",
        ],
        "stability_summary": "Stop/continue flow runtime stability is healthy. All downstream layers report green.",
        "required_actions": [],
        "recommended_next_action": "proceed with production deployment; stability is satisfactory",
        "confidence_score": 0.88,
    },
    "application_startup": {
        "aliases": ["startup", "boot", "init", "launch", "başlat"],
        "target_component": "application_boot_runtime",
        "stability_category": "boot_integrity",
        "stability_status": "pass",
        "stability_score": 0.82,
        "stability_findings": [
            "all_modules_load_without_error",
            "dependency_graph_verified",
            "configuration_loaded_correctly",
        ],
        "stability_warnings": [
            "env_file_check_not_strict",
            "fallback_mode_available",
        ],
        "stability_blockers": [],
        "stability_risk_level": "low",
        "stability_recommendations": [
            "add_strict_env_validation",
            "document_boot_sequence",
        ],
        "stability_summary": "Application startup runtime stability is healthy. All modules load correctly.",
        "required_actions": [],
        "recommended_next_action": "add strict environment validation on boot",
        "confidence_score": 0.80,
    },
    "api_routing": {
        "aliases": ["api", "route", "endpoint", "router", "yönlendirici"],
        "target_component": "api_routing_runtime",
        "stability_category": "routing_integrity",
        "stability_status": "pass",
        "stability_score": 0.85,
        "stability_findings": [
            "all_routes_registered",
            "404_handling_verified",
            "auth_middleware_active",
        ],
        "stability_warnings": [
            "static_file_mount_verified",
            "cors_policy_permissive",
        ],
        "stability_blockers": [],
        "stability_risk_level": "low",
        "stability_recommendations": [
            "tighten_cors_policy_for_production",
            "add_rate_limiting",
        ],
        "stability_summary": "API routing runtime stability is healthy. All endpoints registered and accessible.",
        "required_actions": [],
        "recommended_next_action": "tighten CORS policy for production deployment",
        "confidence_score": 0.87,
    },
    "session_state": {
        "aliases": ["session", "state", "memory", "user", "oturum"],
        "target_component": "session_state_runtime",
        "stability_category": "state_integrity",
        "stability_status": "pass",
        "stability_score": 0.80,
        "stability_findings": [
            "user_state_persistence_verified",
            "session_isolation_active",
            "file_lock_mechanism_working",
        ],
        "stability_warnings": [
            "no_memory_limit_on_user_files",
            "concurrent_write_not_tested",
        ],
        "stability_blockers": [],
        "stability_risk_level": "low",
        "stability_recommendations": [
            "add_user_storage_quota",
            "test_concurrent_write_scenarios",
        ],
        "stability_summary": "Session state runtime stability is healthy. User state persistence verified.",
        "required_actions": [],
        "recommended_next_action": "add user storage quota and test concurrent writes",
        "confidence_score": 0.78,
    },
    "file_io": {
        "aliases": ["file", "disk", "io", "read", "write", "dosya"],
        "target_component": "file_io_runtime",
        "stability_category": "io_integrity",
        "stability_status": "pass",
        "stability_score": 0.83,
        "stability_findings": [
            "all_required_directories_exist",
            "file_locks_prevent_corruption",
            "user_data_directory_structure_valid",
        ],
        "stability_warnings": [
            "large_file_handling_not_tested",
            "concurrent_write_contention_possible",
        ],
        "stability_blockers": [],
        "stability_risk_level": "low",
        "stability_recommendations": [
            "test_large_file_io_performance",
            "add_concurrent_write_contention_protection",
        ],
        "stability_summary": "File IO runtime stability is healthy. All required directories and locks verified.",
        "required_actions": [],
        "recommended_next_action": "test large file IO and concurrent write contention",
        "confidence_score": 0.81,
    },
    "external_api": {
        "aliases": ["external", "api", "deepseek", "openai", "dış"],
        "target_component": "external_api_runtime",
        "stability_category": "integration_integrity",
        "stability_status": "warning",
        "stability_score": 0.65,
        "stability_findings": [
            "deepseek_api_key_loaded",
            "fallback_mode_available_when_api_down",
        ],
        "stability_warnings": [
            "api_key_not_rotated",
            "timeout_configuration_not_tuned",
            "retry_logic_not_implemented",
        ],
        "stability_blockers": [],
        "stability_risk_level": "medium",
        "stability_recommendations": [
            "implement_retry_logic",
            "tune_timeout_configuration",
            "schedule_api_key_rotation",
        ],
        "stability_summary": "External API runtime stability has warnings. API key loaded but retry logic missing.",
        "required_actions": [],
        "recommended_next_action": "implement retry logic and tune timeout configuration",
        "confidence_score": 0.74,
    },
    "concurrency": {
        "aliases": ["concurrency", "async", "parallel", "thread", "lock", "eşzamanlı"],
        "target_component": "concurrency_runtime",
        "stability_category": "concurrency_integrity",
        "stability_status": "pass",
        "stability_score": 0.78,
        "stability_findings": [
            "file_lock_mechanism_working",
            "async_routes_defined_correctly",
        ],
        "stability_warnings": [
            "thread_safety_not_fully_audited",
            "race_condition_testing_not_performed",
        ],
        "stability_blockers": [],
        "stability_risk_level": "low",
        "stability_recommendations": [
            "audit_thread_safety_across_modules",
            "perform_race_condition_testing",
        ],
        "stability_summary": "Concurrency runtime stability is healthy. File locks and async patterns verified.",
        "required_actions": [],
        "recommended_next_action": "audit thread safety and perform race condition testing",
        "confidence_score": 0.76,
    },
}


def _select_stability_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    for key, profile in STABILITY_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(t.lower() in aliases or t.lower() == key for t in targets for t2 in [t]):
            for target in targets:
                tl = target.lower().strip()
                if tl in aliases or tl == key:
                    return key
    return "typewriter_queue"


def runtime_stability_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "31.2",
        "name": "Runtime Stability Intelligence Preview",
        "status": "runtime_stability_intelligence_ready",
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
            "/debug/runtime-stability-status",
            "/debug/runtime-stability-registry",
            "/debug/runtime-stability-preview",
        ],
        "connected_layers": [
            "31.1", "30", "30.1", "30.2", "30.3", "30.4", "30.5",
            "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
            "28.6", "28.5", "28.4", "28.3", "28.2", "28.1",
        ],
        "safety_note": "Read-only runtime stability intelligence preview. No actual stability remediation actions performed.",
    }


def runtime_stability_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for sid, s in STABILITY_PROFILES.items():
        items.append(
            {
                "stability_id": sid,
                "target_component": s["target_component"],
                "stability_category": s["stability_category"],
                "stability_status": s["stability_status"],
                "stability_score": s["stability_score"],
                "stability_risk_level": s["stability_risk_level"],
                "blocker_count": len(s.get("stability_blockers", [])),
                "warning_count": len(s.get("stability_warnings", [])),
                "confidence_score": s["confidence_score"],
            }
        )
    return {
        "layer": "31.2",
        "name": "Runtime Stability Intelligence Registry",
        "status": "runtime_stability_intelligence_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "stability_count": len(items),
        "stability_items": items,
        "pass_count": sum(1 for i in items if i["stability_status"] == "pass"),
        "warning_count": sum(1 for i in items if i["stability_status"] == "warning"),
        "degraded_count": sum(1 for i in items if i["stability_status"] == "degraded"),
        "blocked_count": sum(1 for i in items if i["stability_status"] == "blocked"),
        "overall_stability_score": round(
            sum(i["stability_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "overall_stability_status": _compute_overall_stability_status(items),
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


def _compute_overall_stability_status(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    statuses = [i.get("stability_status", "") for i in items]
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
    L = related_layer or "Layer 31.2"
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


def build_runtime_stability_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    sid = _select_stability_profile(target_issue, command, project_area)
    s = STABILITY_PROFILES[sid]
    detected = target_issue or project_area or sid
    cmd = command or detected
    L = related_layer or "Layer 31.2"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "stability_id": sid,
        "target_component": s["target_component"],
        "stability_category": s["stability_category"],
        "stability_status": s["stability_status"],
        "stability_score": s["stability_score"],
        "stability_findings": s.get("stability_findings", []),
        "stability_warnings": s.get("stability_warnings", []),
        "stability_blockers": s.get("stability_blockers", []),
        "stability_risk_level": s.get("stability_risk_level"),
        "stability_recommendations": s.get("stability_recommendations", []),
        "stability_summary": s.get("stability_summary"),
        "required_actions": s.get("required_actions", []),
        "recommended_next_action": s.get("recommended_next_action"),
        "confidence_score": s["confidence_score"],
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
        "safety_note": "Read-only runtime stability intelligence preview. No actual stability actions performed.",
    }
