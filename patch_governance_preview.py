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
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


GOVERNANCE_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "governance_category": "flow_safety",
        "governance_status": "pass",
        "governance_requirements": [
            "resume_flow_must_not_deadlock",
            "websocket_reconnect_must_complete_2s",
            "double_stop_must_not_crash",
            "governance_override_must_be_logged",
        ],
        "governance_controls": [
            "stop_continue_audit_trail_active",
            "governance_decision_boundary_documented",
        ],
        "governance_exceptions": [],
        "governance_risk_level": "low",
        "governance_readiness": True,
        "required_actions": [],
        "recommended_next_action": "no governance gaps; monitor post-merge",
        "confidence_score": 0.87,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "governance_category": "stream_integrity",
        "governance_status": "violation",
        "governance_requirements": [
            "stream_must_not_lose_deltas",
            "typewriter_queue_ownership_must_be_stable",
            "tab_switch_regression_zero",
            "done_event_must_fire_after_disconnect",
            "governance_approval_required_before_stream_mutation",
        ],
        "governance_controls": [
            "stream_mutation_requires_governance_approval",
            "tab_switch_not_governance_audited",
        ],
        "governance_exceptions": [
            "canary_deployment_can_bypass_until_governance_ready",
        ],
        "governance_risk_level": "high",
        "governance_readiness": False,
        "required_actions": [
            "complete_manual_tab_switch_regression",
            "audit_typewriter_queue_ownership",
            "establish_governance_approval_gate_for_stream_mutations",
        ],
        "recommended_next_action": "resolve 2 governance violations before proceeding",
        "confidence_score": 0.83,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "governance_category": "export_safety",
        "governance_status": "pass",
        "governance_requirements": [
            "export_format_must_match_schema",
            "write_guard_must_be_active",
            "governance_export_policy_must_be_consulted",
        ],
        "governance_controls": [
            "export_governance_check_passed",
        ],
        "governance_exceptions": [],
        "governance_risk_level": "low",
        "governance_readiness": True,
        "required_actions": [],
        "recommended_next_action": "run export validation before merge; governance is green",
        "confidence_score": 0.86,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "governance_category": "platform_privacy",
        "governance_status": "violation",
        "governance_requirements": [
            "android_permission_flow_must_pass_all_cases",
            "ios_permission_flow_must_pass_all_cases",
            "private_data_must_not_leak",
            "governance_review_required_for_platform_access",
        ],
        "governance_controls": [
            "android_permission_tests_not_configured",
            "ios_permission_tests_not_configured",
            "privacy_audit_not_completed",
        ],
        "governance_exceptions": [
            "platform_bypass_permitted_if_governance_audited",
        ],
        "governance_risk_level": "high",
        "governance_readiness": False,
        "required_actions": [
            "configure_android_permission_test_suite",
            "configure_ios_permission_test_suite",
            "complete_privacy_boundary_audit",
        ],
        "recommended_next_action": "set up platform test suites and complete privacy audit",
        "confidence_score": 0.85,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "governance", "test"],
        "target_component": "preview_schema",
        "governance_category": "scaffold_safety",
        "governance_status": "pass",
        "governance_requirements": [
            "no_debug_endpoint_may_write_files",
            "no_debug_endpoint_may_execute_subprocesses",
            "governance_preview_must_be_read_only",
        ],
        "governance_controls": [
            "governance_read_only_check_passed",
        ],
        "governance_exceptions": [],
        "governance_risk_level": "low",
        "governance_readiness": True,
        "required_actions": [],
        "recommended_next_action": "run smoke tests before merge; governance is green",
        "confidence_score": 0.9,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(
    target_issue: Optional[str], command: str, project_area: Optional[str]
) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for pid, p in GOVERNANCE_PROFILES.items():
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


def patch_governance_status() -> Dict[str, Any]:
    return {
        "layer": "29.4",
        "name": "Patch Governance Preview",
        "status": "patch_governance_ready",
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
            "/debug/patch-governance-status",
            "/debug/patch-governance-registry",
            "/debug/patch-governance-preview",
        ],
        "connected_layers": [
            "29.3", "29.2", "29.1", "28", "28.6", "28.5", "28.4", "28.3",
            "28.2", "28.1", "27.6", "27.5", "27.4", "27.3", "27.2",
            "27.1", "26.7", "26.6", "25.6", "25.5", "25.4",
        ],
        "safety_note": "Read-only governance preview. No actual governance enforcement.",
    }


def patch_governance_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in GOVERNANCE_PROFILES.items():
        items.append(
            {
                "id": pid,
                "target_component": p["target_component"],
                "governance_category": p["governance_category"],
                "governance_status": p["governance_status"],
                "governance_risk_level": p["governance_risk_level"],
                "governance_readiness": p["governance_readiness"],
                "violation_count": len(p.get("governance_controls", [])),
                "confidence_score": p["confidence_score"],
            }
        )
    return {
        "layer": "29.4",
        "name": "Patch Governance Registry",
        "status": "patch_governance_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "governance_count": len(items),
        "governances": items,
        "ready_count": sum(1 for i in items if i["governance_readiness"] is True),
        "blocked_count": sum(1 for i in items if i["governance_readiness"] is False),
        "pending_count": sum(1 for i in items if i["governance_readiness"] is None),
        "pass_count": sum(1 for i in items if i.get("governance_status") == "pass"),
        "violation_count": sum(
            1 for i in items if i.get("governance_status") == "violation"
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


def build_patch_governance_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_profile(target_issue, command, project_area)
    p = GOVERNANCE_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 29.4"

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
        / 18,
        2,
    )

    return {
        "governance_id": pid,
        "target_issue": detected,
        "target_component": p["target_component"],
        "governance_category": p["governance_category"],
        "governance_status": p["governance_status"],
        "governance_requirements": list(p["governance_requirements"]),
        "governance_controls": list(p["governance_controls"]),
        "governance_exceptions": list(p["governance_exceptions"]),
        "governance_risk_level": p["governance_risk_level"],
        "governance_readiness": p["governance_readiness"],
        "required_actions": list(p["required_actions"]),
        "recommended_next_action": p["recommended_next_action"],
        "confidence_score": conf,
        "integration_signals": {
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
        "safety_note": "Read-only governance preview. No actual governance enforcement.",
    }
