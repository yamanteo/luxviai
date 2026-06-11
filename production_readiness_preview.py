from __future__ import annotations
from typing import Any, Dict, List, Optional

from layer29_status_snapshot import layer29_status_snapshot
from patch_confidence_preview import build_patch_confidence_preview, patch_confidence_registry
from patch_assurance_preview import build_patch_assurance_preview, patch_assurance_registry
from patch_accountability_preview import build_patch_accountability_preview, patch_accountability_registry
from patch_oversight_preview import build_patch_oversight_preview, patch_oversight_registry
from patch_governance_preview import build_patch_governance_preview, patch_governance_registry
from patch_compliance_preview import build_patch_compliance_preview, patch_compliance_registry
from patch_policy_evaluation_preview import build_patch_policy_preview, patch_policy_registry
from patch_permission_enforcement_preview import build_patch_permission_preview, patch_permission_registry
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
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


READINESS_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "readiness_category": "flow_safety",
        "readiness_status": "pass",
        "readiness_score": 0.88,
        "readiness_requirements": [
            "all_layer_29_sub_layers_must_report_ready",
            "confidence_score_above_0.8",
            "no_open_blockers_in_integration_chain",
        ],
        "readiness_findings": [
            "all_downstream_layers_report_green",
            "confidence_assessment_favorable",
        ],
        "readiness_blockers": [],
        "readiness_risk_level": "low",
        "readiness_recommendations": [
            "schedule_production_review",
            "document_runtime_behavior_for_ops",
        ],
        "production_ready": False,
        "required_actions": [],
        "recommended_next_action": "proceed to production review; readiness is satisfactory",
        "confidence_score": 0.89,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "readiness_category": "stream_integrity",
        "readiness_status": "violation",
        "readiness_score": 0.25,
        "readiness_requirements": [
            "confidence_score_above_0.7",
            "all_accountability_owners_assigned",
            "oversight_findings_cleared",
        ],
        "readiness_findings": [
            "confidence_cascade_failure_detected",
            "accountability_gaps_block_readiness",
            "oversight_violations_remain_open",
        ],
        "readiness_blockers": [
            "tab_switch_regression_blocks_production",
            "typewriter_queue_ownership_unassigned",
            "privacy_audit_not_completed",
        ],
        "readiness_risk_level": "high",
        "readiness_recommendations": [
            "resolve_all_blockers_before_production",
            "re-run_readiness_assessment_after_fixes",
        ],
        "production_ready": False,
        "required_actions": [
            "fix_tab_switch_regression_at_source",
            "assign_typewriter_queue_ownership",
            "complete_privacy_audit",
        ],
        "recommended_next_action": "resolve 3 production blockers before deployment",
        "confidence_score": 0.87,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "readiness_category": "export_safety",
        "readiness_status": "pass",
        "readiness_score": 0.87,
        "readiness_requirements": [
            "export_pipeline_must_be_documented",
            "write_guard_must_be_production_tested",
        ],
        "readiness_findings": [
            "export_pipeline_documented",
            "write_guard_verified",
        ],
        "readiness_blockers": [],
        "readiness_risk_level": "low",
        "readiness_recommendations": [
            "run_production_load_test_on_export",
        ],
        "production_ready": False,
        "required_actions": [],
        "recommended_next_action": "run production load test; readiness is satisfactory",
        "confidence_score": 0.88,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "readiness_category": "platform_privacy",
        "readiness_status": "violation",
        "readiness_score": 0.18,
        "readiness_requirements": [
            "confidence_score_above_0.7",
            "all_permission_tests_passing",
            "privacy_audit_cleared",
        ],
        "readiness_findings": [
            "confidence_cascade_below_threshold",
            "permission_tests_not_configured_at_any_layer",
            "privacy_audit_blocking_production_readiness",
        ],
        "readiness_blockers": [
            "android_permission_tests_missing",
            "ios_permission_tests_missing",
            "privacy_boundary_audit_not_signed",
        ],
        "readiness_risk_level": "high",
        "readiness_recommendations": [
            "implement_permission_test_suites_as_prerequisite",
            "finalize_privacy_audit_with_external_review",
        ],
        "production_ready": False,
        "required_actions": [
            "build_android_permission_test_suite",
            "build_ios_permission_test_suite",
            "complete_and_sign_privacy_audit",
        ],
        "recommended_next_action": "critical blockers prevent production readiness",
        "confidence_score": 0.86,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "readiness", "test"],
        "target_component": "preview_schema",
        "readiness_category": "scaffold_safety",
        "readiness_status": "pass",
        "readiness_score": 0.92,
        "readiness_requirements": [
            "all_endpoints_must_be_read_only",
            "no_write_capability_may_exist",
        ],
        "readiness_findings": [
            "read_only_policy_confirmed_across_all_layers",
            "safety_flags_all_false_verified",
        ],
        "readiness_blockers": [],
        "readiness_risk_level": "low",
        "readiness_recommendations": [
            "elevate_to_production_review_shortlist",
        ],
        "production_ready": False,
        "required_actions": [],
        "recommended_next_action": "highest readiness score; candidate for first production review",
        "confidence_score": 0.92,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(
    target_issue: Optional[str], command: str, project_area: Optional[str]
) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for pid, p in READINESS_PROFILES.items():
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


def production_readiness_status() -> Dict[str, Any]:
    return {
        "layer": "30.1",
        "name": "Production Readiness Preview",
        "status": "production_readiness_ready",
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
            "/debug/production-readiness-status",
            "/debug/production-readiness-registry",
            "/debug/production-readiness-preview",
        ],
        "connected_layers": [
            "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
            "28.6", "28.5", "28.4", "28.3", "28.2", "28.1",
            "27.6", "27.5", "27.4",
            "26.7",
            "25.6", "25.5", "25.4",
        ],
        "safety_note": "Read-only production readiness preview. No actual deployment actions performed.",
    }


def production_readiness_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in READINESS_PROFILES.items():
        items.append(
            {
                "id": pid,
                "target_component": p["target_component"],
                "readiness_category": p["readiness_category"],
                "readiness_status": p["readiness_status"],
                "readiness_score": p["readiness_score"],
                "readiness_risk_level": p["readiness_risk_level"],
                "production_ready": p["production_ready"],
                "blocker_count": len(p.get("readiness_blockers", [])),
                "confidence_score": p["confidence_score"],
            }
        )
    return {
        "layer": "30.1",
        "name": "Production Readiness Registry",
        "status": "production_readiness_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "readiness_count": len(items),
        "readiness_items": items,
        "ready_count": sum(1 for i in items if i["production_ready"] is True),
        "blocked_count": sum(1 for i in items if i["production_ready"] is False),
        "pass_count": sum(1 for i in items if i.get("readiness_status") == "pass"),
        "violation_count": sum(
            1 for i in items if i.get("readiness_status") == "violation"
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


def build_production_readiness_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_profile(target_issue, command, project_area)
    p = READINESS_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 30.1"

    layer29_snapshot = layer29_status_snapshot()
    confidence = build_patch_confidence_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
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
            + float(confidence.get("confidence_score", 0.0))
            + float(assurance.get("confidence_score", 0.0))
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
        )
        / 18,
        2,
    )

    return {
        "readiness_id": pid,
        "target_issue": detected,
        "target_component": p["target_component"],
        "readiness_category": p["readiness_category"],
        "readiness_status": p["readiness_status"],
        "readiness_score": p["readiness_score"],
        "readiness_requirements": list(p["readiness_requirements"]),
        "readiness_findings": list(p["readiness_findings"]),
        "readiness_blockers": list(p["readiness_blockers"]),
        "readiness_risk_level": p["readiness_risk_level"],
        "readiness_recommendations": list(p["readiness_recommendations"]),
        "production_ready": p["production_ready"],
        "required_actions": list(p["required_actions"]),
        "recommended_next_action": p["recommended_next_action"],
        "confidence_score": conf,
        "integration_signals": {
            "layer29_status_snapshot": {
                "snapshot_status": layer29_snapshot.get("snapshot_status"),
                "layer_29_complete": layer29_snapshot.get("layer_29_complete"),
                "all_read_only": layer29_snapshot.get("all_read_only"),
            },
            "patch_confidence": {
                "confidence_score": confidence.get("confidence_score"),
                "confidence_readiness": confidence.get("confidence_readiness"),
            },
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
        "safety_note": "Read-only production readiness preview. No actual deployment actions performed.",
    }