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
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


ACCOUNTABILITY_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "accountability_category": "flow_safety",
        "accountability_status": "pass",
        "accountability_owner": "runtime_team",
        "accountability_scope": "resume flow lifecycle",
        "accountability_findings": [
            "deadlock_risk_mitigation_verified",
            "websocket_reconnect_policy_documented",
            "double_stop_handling_confirmed",
            "oversight_recommendations_applied",
        ],
        "accountability_requirements": [
            "owner_must_maintain_resume_flow_docs",
            "scope_must_cover_ws_reconnect_path",
        ],
        "accountability_exceptions": [],
        "accountability_risk_level": "low",
        "accountability_readiness": True,
        "required_actions": [],
        "recommended_next_action": "accountability clear; continue monitoring",
        "confidence_score": 0.89,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "accountability_category": "stream_integrity",
        "accountability_status": "violation",
        "accountability_owner": "stream_team",
        "accountability_scope": "websocket stream, typewriter queue, tab transitions",
        "accountability_findings": [
            "stream_delta_loss_no_accountable_owner_assigned",
            "typewriter_queue_ownership_gap_unresolved",
            "tab_switch_regression_not_assigned",
            "oversight_approval_gate_unowned",
        ],
        "accountability_requirements": [
            "owner_must_resolve_tab_switch_regression",
            "scope_must_include_typewriter_queue_audit",
        ],
        "accountability_exceptions": [
            "canary_deployment_exception_grants_temporary_ownership_wavier",
        ],
        "accountability_risk_level": "high",
        "accountability_readiness": False,
        "required_actions": [
            "assign_owner_for_tab_switch_regression",
            "assign_owner_for_typewriter_queue_audit",
            "establish_accountability_trail_for_stream_mutations",
        ],
        "recommended_next_action": "resolve 2 accountability gaps before proceeding",
        "confidence_score": 0.85,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "accountability_category": "export_safety",
        "accountability_status": "pass",
        "accountability_owner": "export_team",
        "accountability_scope": "export pipelines, format validation, write guard",
        "accountability_findings": [
            "export_format_compliance_owned",
            "write_guard_ownership_documented",
            "oversight_recommendations_adopted",
        ],
        "accountability_requirements": [
            "owner_must_maintain_export_format_spec",
            "scope_must_include_write_guard_audit",
        ],
        "accountability_exceptions": [],
        "accountability_risk_level": "low",
        "accountability_readiness": True,
        "required_actions": [],
        "recommended_next_action": "accountability clear; run validation before merge",
        "confidence_score": 0.88,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "accountability_category": "platform_privacy",
        "accountability_status": "violation",
        "accountability_owner": "platform_team",
        "accountability_scope": "Android/iOS permissions, privacy boundary",
        "accountability_findings": [
            "android_permission_tests_no_owner",
            "ios_permission_tests_no_owner",
            "privacy_boundary_audit_not_owned",
            "oversight_exception_not_assigned",
        ],
        "accountability_requirements": [
            "owner_must_assign_resources_for_permission_tests",
            "scope_must_cover_privacy_audit_completion",
        ],
        "accountability_exceptions": [
            "platform_bypass_requires_accountability_signoff",
        ],
        "accountability_risk_level": "high",
        "accountability_readiness": False,
        "required_actions": [
            "assign_owner_for_android_permission_tests",
            "assign_owner_for_ios_permission_tests",
            "assign_owner_for_privacy_boundary_audit",
        ],
        "recommended_next_action": "assign owners for all platform permission items with accountability clearance",
        "confidence_score": 0.87,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "accountability", "test"],
        "target_component": "preview_schema",
        "accountability_category": "scaffold_safety",
        "accountability_status": "pass",
        "accountability_owner": "scaffold_team",
        "accountability_scope": "debug endpoints, read-only gates, preview schemas",
        "accountability_findings": [
            "no_debug_endpoint_writes_files_confirmed",
            "no_debug_endpoint_executes_subprocesses_confirmed",
            "accountability_preview_passes_all_gates",
        ],
        "accountability_requirements": [
            "owner_must_maintain_read_only_policy",
            "scope_must_cover_all_debug_endpoints",
        ],
        "accountability_exceptions": [],
        "accountability_risk_level": "low",
        "accountability_readiness": True,
        "required_actions": [],
        "recommended_next_action": "run smoke tests before merge; accountability is green",
        "confidence_score": 0.92,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(
    target_issue: Optional[str], command: str, project_area: Optional[str]
) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for pid, p in ACCOUNTABILITY_PROFILES.items():
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


def patch_accountability_status() -> Dict[str, Any]:
    return {
        "layer": "29.6",
        "name": "Patch Accountability Preview",
        "status": "patch_accountability_ready",
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
            "/debug/patch-accountability-status",
            "/debug/patch-accountability-registry",
            "/debug/patch-accountability-preview",
        ],
        "connected_layers": [
            "29.5", "29.4", "29.3", "29.2", "29.1", "28", "28.6", "28.5", "28.4", "28.3",
            "28.2", "28.1", "27.6", "27.5", "27.4", "27.3", "27.2",
            "27.1", "26.7", "26.6", "25.6", "25.5", "25.4",
        ],
        "safety_note": "Read-only accountability preview. No actual accountability enforcement.",
    }


def patch_accountability_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in ACCOUNTABILITY_PROFILES.items():
        items.append(
            {
                "id": pid,
                "target_component": p["target_component"],
                "accountability_category": p["accountability_category"],
                "accountability_status": p["accountability_status"],
                "accountability_owner": p["accountability_owner"],
                "accountability_risk_level": p["accountability_risk_level"],
                "accountability_readiness": p["accountability_readiness"],
                "finding_count": len(p.get("accountability_findings", [])),
                "confidence_score": p["confidence_score"],
            }
        )
    return {
        "layer": "29.6",
        "name": "Patch Accountability Registry",
        "status": "patch_accountability_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "accountability_count": len(items),
        "accountabilities": items,
        "ready_count": sum(1 for i in items if i["accountability_readiness"] is True),
        "blocked_count": sum(1 for i in items if i["accountability_readiness"] is False),
        "pending_count": sum(1 for i in items if i["accountability_readiness"] is None),
        "pass_count": sum(1 for i in items if i.get("accountability_status") == "pass"),
        "violation_count": sum(
            1 for i in items if i.get("accountability_status") == "violation"
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


def build_patch_accountability_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_profile(target_issue, command, project_area)
    p = ACCOUNTABILITY_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 29.6"

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
        / 20,
        2,
    )

    return {
        "accountability_id": pid,
        "target_issue": detected,
        "target_component": p["target_component"],
        "accountability_category": p["accountability_category"],
        "accountability_status": p["accountability_status"],
        "accountability_owner": p["accountability_owner"],
        "accountability_scope": p["accountability_scope"],
        "accountability_findings": list(p["accountability_findings"]),
        "accountability_requirements": list(p["accountability_requirements"]),
        "accountability_exceptions": list(p["accountability_exceptions"]),
        "accountability_risk_level": p["accountability_risk_level"],
        "accountability_readiness": p["accountability_readiness"],
        "required_actions": list(p["required_actions"]),
        "recommended_next_action": p["recommended_next_action"],
        "confidence_score": conf,
        "integration_signals": {
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
        "safety_note": "Read-only accountability preview. No actual accountability enforcement.",
    }