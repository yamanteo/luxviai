from __future__ import annotations
from typing import Any, Dict, List, Optional

from evidence_store_preview import build_evidence_store_preview
from multi_agent_coordinator_preview import build_coordinator_preview
from patch_draft_engine_preview import build_patch_draft_preview
from change_preview_engine_preview import build_change_preview
from diff_preview_engine_preview import build_diff_preview
from patch_risk_matrix_preview import build_patch_risk_preview
from patch_approval_engine_preview import build_patch_approval_preview
from patch_execution_readiness_preview import build_patch_execution_preview
from safe_patch_application_preview import build_safe_patch_preview
from patch_rollback_preview import build_patch_rollback_preview
from patch_validation_preview import build_patch_validation_preview
from patch_recovery_preview import build_patch_recovery_preview
from patch_audit_trail_preview import build_patch_audit_preview
from patch_lifecycle_preview import build_patch_lifecycle_preview
from patch_permission_enforcement_preview import build_patch_permission_preview
from patch_policy_evaluation_preview import build_patch_policy_preview
from patch_compliance_preview import build_patch_compliance_preview
from patch_governance_preview import build_patch_governance_preview
from patch_oversight_preview import build_patch_oversight_preview
from patch_accountability_preview import build_patch_accountability_preview
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


ASSURANCE_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "assurance_category": "flow_safety",
        "assurance_status": "pass",
        "assurance_scope": "complete resume flow lifecycle with ws reconnect",
        "assurance_findings": [
            "deadlock_risk_mitigated_and_verified",
            "websocket_reconnect_confirmed_under_2s",
            "double_stop_handling_confirmed",
            "accountability_ownership_verified",
        ],
        "assurance_controls": [
            "assurance_resume_flow_gate_passed",
            "assurance_ws_reconnect_timing_monitored",
        ],
        "assurance_requirements": [
            "resume_flow_must_pass_all_assurance_gates",
            "ws_reconnect_must_complete_within_assurance_bound",
        ],
        "assurance_exceptions": [],
        "assurance_risk_level": "low",
        "assurance_readiness": True,
        "assurance_score": 0.92,
        "required_actions": [],
        "recommended_next_action": "assurance clear; proceed with confidence",
        "confidence_score": 0.90,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "assurance_category": "stream_integrity",
        "assurance_status": "violation",
        "assurance_scope": "websocket stream, typewriter queue, tab transitions",
        "assurance_findings": [
            "stream_delta_loss_assurance_not_met",
            "typewriter_queue_ownership_not_assured",
            "tab_switch_regression_assurance_failed",
            "accountability_gaps_not_assured",
        ],
        "assurance_controls": [
            "assurance_requires_stream_mutation_signoff",
            "assurance_tab_switch_regression_pending",
        ],
        "assurance_requirements": [
            "tab_switch_regression_must_pass_assurance",
            "typewriter_queue_audit_must_be_assured",
        ],
        "assurance_exceptions": [
            "canary_deployment_exception_grants_temporary_assurance_wavier",
        ],
        "assurance_risk_level": "high",
        "assurance_readiness": False,
        "assurance_score": 0.42,
        "required_actions": [
            "achieve_assurance_for_tab_switch_regression",
            "achieve_assurance_for_typewriter_queue_audit",
        ],
        "recommended_next_action": "resolve 2 assurance failures before proceeding",
        "confidence_score": 0.86,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "assurance_category": "export_safety",
        "assurance_status": "pass",
        "assurance_scope": "export pipelines, format validation, write guard",
        "assurance_findings": [
            "export_format_assurance_confirmed",
            "write_guard_assurance_verified",
            "accountability_ownership_assured",
        ],
        "assurance_controls": [
            "assurance_export_gate_passed",
        ],
        "assurance_requirements": [
            "export_format_must_match_assurance_schema",
            "write_guard_must_pass_assurance_check",
        ],
        "assurance_exceptions": [],
        "assurance_risk_level": "low",
        "assurance_readiness": True,
        "assurance_score": 0.91,
        "required_actions": [],
        "recommended_next_action": "assurance clear; run validation before merge",
        "confidence_score": 0.89,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "assurance_category": "platform_privacy",
        "assurance_status": "violation",
        "assurance_scope": "Android/iOS permissions, privacy boundary",
        "assurance_findings": [
            "android_permission_tests_not_assured",
            "ios_permission_tests_not_assured",
            "privacy_boundary_audit_not_assured",
            "accountability_owners_not_assured",
        ],
        "assurance_controls": [
            "android_permission_not_assurance_approved",
            "ios_permission_not_assurance_approved",
            "privacy_audit_not_assurance_signed",
        ],
        "assurance_requirements": [
            "android_permission_suite_must_pass_assurance",
            "ios_permission_suite_must_pass_assurance",
            "privacy_audit_must_be_assurance_signed",
        ],
        "assurance_exceptions": [
            "platform_bypass_requires_assurance_signoff",
        ],
        "assurance_risk_level": "high",
        "assurance_readiness": False,
        "assurance_score": 0.35,
        "required_actions": [
            "achieve_assurance_for_android_tests",
            "achieve_assurance_for_ios_tests",
            "achieve_assurance_for_privacy_audit",
        ],
        "recommended_next_action": "achieve assurance coverage for all platform items",
        "confidence_score": 0.88,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "assurance", "test"],
        "target_component": "preview_schema",
        "assurance_category": "scaffold_safety",
        "assurance_status": "pass",
        "assurance_scope": "debug endpoints, read-only gates, preview schemas",
        "assurance_findings": [
            "no_debug_endpoint_writes_files_assured",
            "no_debug_endpoint_executes_subprocesses_assured",
            "assurance_preview_passes_all_gates",
        ],
        "assurance_controls": [
            "assurance_read_only_gate_active",
        ],
        "assurance_requirements": [
            "all_debug_endpoints_must_pass_assurance_gate",
            "read_only_policy_must_be_assured",
        ],
        "assurance_exceptions": [],
        "assurance_risk_level": "low",
        "assurance_readiness": True,
        "assurance_score": 0.95,
        "required_actions": [],
        "recommended_next_action": "run smoke tests before merge; assurance is green",
        "confidence_score": 0.93,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(
    target_issue: Optional[str], command: str, project_area: Optional[str]
) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for pid, p in ASSURANCE_PROFILES.items():
        if pid in haystack or any(
            a.lower() in haystack for a in p.get("aliases", [])
        ):
            return pid
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    out: List[Any] = []
    for i in items:
        if i and i not in out:
            out.append(i)
    return out


def patch_assurance_status() -> Dict[str, Any]:
    return {
        "layer": "29.7",
        "name": "Patch Assurance Preview",
        "status": "patch_assurance_ready",
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
            "/debug/patch-assurance-status",
            "/debug/patch-assurance-registry",
            "/debug/patch-assurance-preview",
        ],
        "connected_layers": [
            "29.6", "29.5", "29.4", "29.3", "29.2", "29.1", "28", "28.6", "28.5", "28.4", "28.3",
            "28.2", "28.1", "27.6", "27.5", "27.4", "27.3", "27.2",
            "27.1", "26.7", "26.6", "25.6", "25.5", "25.4",
        ],
        "safety_note": "Read-only assurance preview. No actual assurance enforcement.",
    }


def patch_assurance_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in ASSURANCE_PROFILES.items():
        items.append(
            {
                "id": pid,
                "target_component": p["target_component"],
                "assurance_category": p["assurance_category"],
                "assurance_status": p["assurance_status"],
                "assurance_risk_level": p["assurance_risk_level"],
                "assurance_readiness": p["assurance_readiness"],
                "assurance_score": p["assurance_score"],
                "finding_count": len(p.get("assurance_findings", [])),
                "confidence_score": p["confidence_score"],
            }
        )
    return {
        "layer": "29.7",
        "name": "Patch Assurance Registry",
        "status": "patch_assurance_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "assurance_count": len(items),
        "assurances": items,
        "ready_count": sum(1 for i in items if i["assurance_readiness"] is True),
        "blocked_count": sum(1 for i in items if i["assurance_readiness"] is False),
        "pending_count": sum(1 for i in items if i["assurance_readiness"] is None),
        "pass_count": sum(1 for i in items if i.get("assurance_status") == "pass"),
        "violation_count": sum(
            1 for i in items if i.get("assurance_status") == "violation"
        ),
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


def build_patch_assurance_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_profile(target_issue, command, project_area)
    p = ASSURANCE_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 29.7"

    accountability = build_patch_accountability_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    oversight = build_patch_oversight_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    governance = build_patch_governance_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    compliance = build_patch_compliance_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    policy = build_patch_policy_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    permission = build_patch_permission_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    lifecycle = build_patch_lifecycle_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    audit = build_patch_audit_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    recovery = build_patch_recovery_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    validation = build_patch_validation_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    rollback = build_patch_rollback_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    safe_patch = build_safe_patch_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    execution = build_patch_execution_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    approval = build_patch_approval_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    risk = build_patch_risk_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    diff = build_diff_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    change = build_change_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    draft = build_patch_draft_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    coordinator = build_coordinator_preview(
        command=cmd, project_area=project_area or detected, related_layer=L
    )
    evidence = build_evidence_store_preview(
        finding=None, command=cmd, project_area=project_area or detected, related_layer=L
    )
    verification = build_verification_planner_preview(
        target_issue=detected, command=cmd, related_layer=L
    )
    planner = build_patch_planner_preview(
        target_issue=detected, command=cmd, related_layer=L
    )
    boundary = build_change_boundary_preview(
        target_area=detected, command=cmd, related_layer=L
    )

    conf = round(
        (
            float(p["confidence_score"])
            + float(accountability.get("confidence_score", 0.0))
            + float(oversight.get("confidence_score", 0.0))
            + float(governance.get("confidence_score", 0.0))
            + float(compliance.get("confidence_score", 0.0))
            + float(policy.get("confidence_score", 0.0))
            + float(permission.get("confidence_score", 0.0))
            + float(lifecycle.get("confidence_score", 0.0))
            + float(audit.get("confidence_score", 0.0))
            + float(recovery.get("confidence_score", 0.0))
            + float(validation.get("confidence_score", 0.0))
            + float(rollback.get("confidence_score", 0.0))
            + float(safe_patch.get("confidence_score", 0.0))
            + float(execution.get("confidence_score", 0.0))
            + float(approval.get("confidence_score", 0.0))
            + float(risk.get("confidence_score", 0.0))
            + float(diff.get("confidence_score", 0.0))
            + float(change.get("confidence_score", 0.0))
            + float(draft.get("confidence_score", 0.0))
            + float(coordinator.get("overall_confidence", 0.0))
            + float(evidence.get("confidence_score", 0.0))
        )
        / 21,
        2,
    )

    return {
        "assurance_id": pid,
        "target_issue": detected,
        "target_component": p["target_component"],
        "assurance_category": p["assurance_category"],
        "assurance_status": p["assurance_status"],
        "assurance_scope": p["assurance_scope"],
        "assurance_findings": list(p["assurance_findings"]),
        "assurance_controls": list(p["assurance_controls"]),
        "assurance_requirements": list(p["assurance_requirements"]),
        "assurance_exceptions": list(p["assurance_exceptions"]),
        "assurance_risk_level": p["assurance_risk_level"],
        "assurance_readiness": p["assurance_readiness"],
        "assurance_score": p["assurance_score"],
        "required_actions": list(p["required_actions"]),
        "recommended_next_action": p["recommended_next_action"],
        "confidence_score": conf,
        "integration_signals": {
            "patch_accountability": {
                "accountability_status": accountability.get("accountability_status"),
                "accountability_readiness": accountability.get("accountability_readiness"),
            },
            "patch_oversight": {
                "oversight_status": oversight.get("oversight_status"),
                "oversight_readiness": oversight.get("oversight_readiness"),
            },
            "patch_governance": {
                "governance_status": governance.get("governance_status"),
                "governance_readiness": governance.get("governance_readiness"),
            },
            "patch_compliance": {
                "compliance_status": compliance.get("compliance_status"),
                "compliance_readiness": compliance.get("compliance_readiness"),
            },
            "patch_policy_evaluation": {
                "policy_result": policy.get("policy_result"),
                "policy_readiness": policy.get("policy_readiness"),
            },
            "patch_permission_enforcement": {
                "permission_level": permission.get("permission_level"),
                "permission_readiness": permission.get("permission_readiness"),
            },
            "patch_lifecycle": {
                "lifecycle_readiness": lifecycle.get("lifecycle_readiness"),
                "completion_score": lifecycle.get("completion_score"),
            },
            "patch_audit_trail": {
                "audit_readiness": audit.get("audit_readiness"),
                "audit_completeness": audit.get("audit_completeness"),
            },
            "patch_recovery": {
                "recovery_required": recovery.get("recovery_required"),
                "recovery_readiness": recovery.get("recovery_readiness"),
            },
            "patch_validation": {
                "validation_status": validation.get("validation_status"),
                "validation_risk_level": validation.get("validation_risk_level"),
            },
            "patch_rollback": {
                "rollback_required": rollback.get("rollback_required"),
                "rollback_readiness": rollback.get("rollback_readiness"),
            },
            "safe_patch_application": {
                "application_ready": safe_patch.get("application_ready"),
            },
            "patch_execution_readiness": {
                "execution_ready": execution.get("execution_ready"),
                "go_no_go_status": execution.get("go_no_go_status"),
            },
            "patch_approval": {
                "approval_required": approval.get("approval_required"),
            },
            "patch_risk_matrix": {
                "risk_score": risk.get("risk_score"),
                "risk_level": risk.get("risk_level"),
            },
            "diff_preview": {
                "affected_files": diff.get("affected_files", []),
            },
            "change_preview": {
                "risk_areas": change.get("risk_areas", []),
            },
            "patch_draft": {
                "recommended_files": draft.get("recommended_files", []),
            },
            "multi_agent_coordinator": {
                "combined_risks": coordinator.get("combined_risks", []),
                "overall_confidence": coordinator.get("overall_confidence"),
            },
            "evidence_store": {
                "risk_reasoning": evidence.get("risk_reasoning"),
            },
            "verification_planner": {
                "required_tests": verification.get("required_tests", []),
            },
            "safe_patch_planner": {
                "estimated_complexity": planner.get("estimated_complexity"),
            },
            "safe_change_boundary": {
                "blocked_actions": boundary.get("blocked_actions", []),
            },
        },
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
        "safety_note": "Read-only assurance preview. No actual assurance enforcement.",
    }