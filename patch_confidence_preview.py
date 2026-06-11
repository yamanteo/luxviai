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
from patch_assurance_preview import build_patch_assurance_preview
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


CONFIDENCE_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "confidence_category": "flow_safety",
        "confidence_status": "pass",
        "confidence_score": 0.93,
        "confidence_factors": [
            "assurance_score_0.92",
            "accountability_ownership_verified",
            "oversight_findings_clear",
            "governance_compliance_green",
        ],
        "confidence_findings": [
            "all_lower_layers_report_pass",
            "no_blocking_gaps_identified",
        ],
        "confidence_requirements": [
            "all_integrated_layers_must_report_ready",
            "no_open_violations_in_chain",
        ],
        "confidence_exceptions": [],
        "confidence_risk_level": "low",
        "confidence_readiness": True,
        "confidence_reasoning": "All integrated layers report pass. Assurance score 0.92, accountability owned, oversight clear. No residual risk.",
        "required_actions": [],
        "recommended_next_action": "confidence clear; proceed with merge",
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "confidence_category": "stream_integrity",
        "confidence_status": "violation",
        "confidence_score": 0.38,
        "confidence_factors": [
            "assurance_score_0.42",
            "accountability_gaps_unresolved",
            "oversight_findings_open",
            "governance_violations_active",
            "compliance_violations_unresolved",
        ],
        "confidence_findings": [
            "tab_switch_regression_unresolved_at_all_layers",
            "typewriter_queue_ownership_gap_propagates_up",
            "cumulative_risk_exceeds_confidence_threshold",
        ],
        "confidence_requirements": [
            "all_layers_must_resolve_stream_related_violations",
            "cumulative_confidence_must_exceed_0.7",
        ],
        "confidence_exceptions": [
            "canary_deployment_allowed_with_confidence_waiver",
        ],
        "confidence_risk_level": "high",
        "confidence_readiness": False,
        "confidence_reasoning": "Low assurance score (0.42), unresolved accountability gaps, and cascade of violations across 6 upstream layers. Confidence insufficient for safe deployment.",
        "required_actions": [
            "resolve_tab_switch_regression_at_source",
            "close_typewriter_queue_ownership_gap",
            "re-run_confidence_assessment_after_fixes",
        ],
        "recommended_next_action": "resolve lower-layer violations before confidence can improve",
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "confidence_category": "export_safety",
        "confidence_status": "pass",
        "confidence_score": 0.91,
        "confidence_factors": [
            "assurance_score_0.91",
            "accountability_ownership_confirmed",
            "oversight_compliance_clear",
        ],
        "confidence_findings": [
            "all_layer_reports_green",
            "export_pipeline_assured",
        ],
        "confidence_requirements": [
            "export_format_must_match_spec",
            "write_guard_must_pass",
        ],
        "confidence_exceptions": [],
        "confidence_risk_level": "low",
        "confidence_readiness": True,
        "confidence_reasoning": "High assurance score (0.91), owned by export_team, all upstream layers report pass. Confidence is strong.",
        "required_actions": [],
        "recommended_next_action": "confidence clear; run validation before merge",
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "confidence_category": "platform_privacy",
        "confidence_status": "violation",
        "confidence_score": 0.30,
        "confidence_factors": [
            "assurance_score_0.35",
            "accountability_owners_unassigned",
            "oversight_violations_active",
            "governance_exceptions_not_cleared",
            "compliance_violations_persist",
        ],
        "confidence_findings": [
            "android_permission_gap_propagates_through_all_layers",
            "ios_permission_gap_propagates_through_all_layers",
            "privacy_audit_gap_blocks_confidence",
            "cumulative_risk_score_critical",
        ],
        "confidence_requirements": [
            "android_tests_must_pass_all_layers",
            "ios_tests_must_pass_all_layers",
            "privacy_audit_must_be_signed_off",
        ],
        "confidence_exceptions": [
            "platform_bypass_requires_full_confidence_signoff",
        ],
        "confidence_risk_level": "high",
        "confidence_readiness": False,
        "confidence_reasoning": "Critical gaps cascade from compliance through governance, oversight, accountability, and assurance. The cumulative confidence deficit makes deployment inadvisable without full remediation.",
        "required_actions": [
            "remediate_android_permission_tests",
            "remediate_ios_permission_tests",
            "complete_privacy_audit",
            "propagate_fixes_through_all_layers",
        ],
        "recommended_next_action": "full remediation chain required before confidence assessment",
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "confidence", "test"],
        "target_component": "preview_schema",
        "confidence_category": "scaffold_safety",
        "confidence_status": "pass",
        "confidence_score": 0.96,
        "confidence_factors": [
            "assurance_score_0.95",
            "accountability_ownership_verified",
            "all_upstream_layers_green",
        ],
        "confidence_findings": [
            "all_debug_endpoints_read_only_confirmed",
            "all_safety_flags_false_confirmed",
        ],
        "confidence_requirements": [
            "all_endpoints_must_remain_read_only",
            "no_write_capability_may_be_introduced",
        ],
        "confidence_exceptions": [],
        "confidence_risk_level": "low",
        "confidence_readiness": True,
        "confidence_reasoning": "Highest assurance score (0.95), full ownership, all upstream layers green. Confidence is excellent for scaffold operations.",
        "required_actions": [],
        "recommended_next_action": "run smoke tests before merge; confidence is green",
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(
    target_issue: Optional[str], command: str, project_area: Optional[str]
) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for pid, p in CONFIDENCE_PROFILES.items():
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


def patch_confidence_status() -> Dict[str, Any]:
    return {
        "layer": "29.8",
        "name": "Patch Confidence Preview",
        "status": "patch_confidence_ready",
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
            "/debug/patch-confidence-status",
            "/debug/patch-confidence-registry",
            "/debug/patch-confidence-preview",
        ],
        "connected_layers": [
            "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1", "28", "28.6", "28.5", "28.4", "28.3",
            "28.2", "28.1", "27.6", "27.5", "27.4", "27.3", "27.2",
            "27.1", "26.7", "26.6", "25.6", "25.5", "25.4",
        ],
        "safety_note": "Read-only confidence preview. No actual confidence enforcement.",
    }


def patch_confidence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in CONFIDENCE_PROFILES.items():
        items.append(
            {
                "id": pid,
                "target_component": p["target_component"],
                "confidence_category": p["confidence_category"],
                "confidence_status": p["confidence_status"],
                "confidence_score": p["confidence_score"],
                "confidence_risk_level": p["confidence_risk_level"],
                "confidence_readiness": p["confidence_readiness"],
                "finding_count": len(p.get("confidence_findings", [])),
            }
        )
    return {
        "layer": "29.8",
        "name": "Patch Confidence Registry",
        "status": "patch_confidence_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "confidence_count": len(items),
        "confidences": items,
        "ready_count": sum(1 for i in items if i["confidence_readiness"] is True),
        "blocked_count": sum(1 for i in items if i["confidence_readiness"] is False),
        "pending_count": sum(1 for i in items if i["confidence_readiness"] is None),
        "pass_count": sum(1 for i in items if i.get("confidence_status") == "pass"),
        "violation_count": sum(
            1 for i in items if i.get("confidence_status") == "violation"
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


def build_patch_confidence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_profile(target_issue, command, project_area)
    p = CONFIDENCE_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 29.8"

    assurance = build_patch_assurance_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
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

    return {
        "confidence_id": pid,
        "target_issue": detected,
        "target_component": p["target_component"],
        "confidence_category": p["confidence_category"],
        "confidence_status": p["confidence_status"],
        "confidence_score": p["confidence_score"],
        "confidence_factors": list(p["confidence_factors"]),
        "confidence_findings": list(p["confidence_findings"]),
        "confidence_requirements": list(p["confidence_requirements"]),
        "confidence_exceptions": list(p["confidence_exceptions"]),
        "confidence_risk_level": p["confidence_risk_level"],
        "confidence_readiness": p["confidence_readiness"],
        "confidence_reasoning": p["confidence_reasoning"],
        "required_actions": list(p["required_actions"]),
        "recommended_next_action": p["recommended_next_action"],
        "integration_signals": {
            "patch_assurance": {
                "assurance_score": assurance.get("assurance_score"),
                "assurance_readiness": assurance.get("assurance_readiness"),
            },
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
        "safety_note": "Read-only confidence preview. No actual confidence enforcement.",
    }