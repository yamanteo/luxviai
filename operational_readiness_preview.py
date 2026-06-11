from __future__ import annotations
from typing import Any, Dict, List, Optional

from production_readiness_preview import build_production_readiness_preview, production_readiness_registry
from layer29_status_snapshot import layer29_status_snapshot
from patch_confidence_preview import build_patch_confidence_preview
from patch_assurance_preview import build_patch_assurance_preview
from patch_accountability_preview import build_patch_accountability_preview
from patch_oversight_preview import build_patch_oversight_preview
from patch_governance_preview import build_patch_governance_preview
from patch_compliance_preview import build_patch_compliance_preview
from patch_policy_evaluation_preview import build_patch_policy_preview
from patch_permission_enforcement_preview import build_patch_permission_preview
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


OPERATIONAL_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "operational_category": "flow_safety",
        "operational_status": "pass",
        "operational_score": 0.85,
        "operational_requirements": [
            "production_readiness_score_above_0.8",
            "deployment_runbook_documented",
            "monitoring_alerts_configured",
        ],
        "operational_findings": [
            "production_readiness_satisfactory",
            "runbook_partially_documented",
        ],
        "operational_blockers": [],
        "operational_risk_level": "low",
        "operational_recommendations": [
            "finalize_deployment_runbook",
            "configure_alert_thresholds",
        ],
        "operational_readiness": False,
        "required_actions": [],
        "recommended_next_action": "document deployment runbook and set up monitoring",
        "confidence_score": 0.87,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "operational_category": "stream_integrity",
        "operational_status": "violation",
        "operational_score": 0.20,
        "operational_requirements": [
            "production_readiness_score_above_0.7",
            "all_blockers_resolved_for_deployment",
            "incident_response_plan_in_place",
        ],
        "operational_findings": [
            "production_readiness_blocked",
            "no_deployment_path_available",
            "incident_response_not_prepared",
        ],
        "operational_blockers": [
            "production_blockers_propagate_to_ops",
            "deployment_runbook_not_creatable_until_blockers_resolved",
        ],
        "operational_risk_level": "high",
        "operational_recommendations": [
            "resolve_production_blockers_first",
            "prepare_incident_response_plan_after_blockers_cleared",
        ],
        "operational_readiness": False,
        "required_actions": [
            "resolve_tab_switch_production_blocker",
            "assign_ownership_for_ops_runbook",
        ],
        "recommended_next_action": "production blockers must be resolved before operational readiness",
        "confidence_score": 0.85,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "operational_category": "export_safety",
        "operational_status": "pass",
        "operational_score": 0.84,
        "operational_requirements": [
            "export_pipeline_documented_for_ops",
            "rollback_procedure_available",
        ],
        "operational_findings": [
            "production_readiness_clear",
            "rollback_procedure_documented",
        ],
        "operational_blockers": [],
        "operational_risk_level": "low",
        "operational_recommendations": [
            "schedule_ops_handoff_session",
        ],
        "operational_readiness": False,
        "required_actions": [],
        "recommended_next_action": "ops handoff recommended; operational readiness is satisfactory",
        "confidence_score": 0.86,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "operational_category": "platform_privacy",
        "operational_status": "violation",
        "operational_score": 0.15,
        "operational_requirements": [
            "production_blockers_cleared",
            "privacy_audit_ops_ready",
        ],
        "operational_findings": [
            "three_production_blockers_unresolved",
            "no_ops_path_defined",
        ],
        "operational_blockers": [
            "production_readiness_blocked_at_all_levels",
            "deployment_impossible_until_test_suites_exist",
        ],
        "operational_risk_level": "high",
        "operational_recommendations": [
            "treat_production_readiness_as_ops_prerequisite",
        ],
        "operational_readiness": False,
        "required_actions": [
            "build_permission_test_suites",
            "complete_privacy_audit",
            "create_deployment_runbook_post_blockers",
        ],
        "recommended_next_action": "operational readiness gated behind production readiness",
        "confidence_score": 0.84,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "operational", "test"],
        "target_component": "preview_schema",
        "operational_category": "scaffold_safety",
        "operational_status": "pass",
        "operational_score": 0.90,
        "operational_requirements": [
            "ops_handoff_documentation_available",
            "read_only_policy_ops_verified",
        ],
        "operational_findings": [
            "production_readiness_score_highest",
            "read_only_policy_documented_for_ops",
        ],
        "operational_blockers": [],
        "operational_risk_level": "low",
        "operational_recommendations": [
            "priority_candidate_for_first_ops_deployment",
        ],
        "operational_readiness": False,
        "required_actions": [],
        "recommended_next_action": "best ops readiness candidate; schedule deployment review",
        "confidence_score": 0.91,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(
    target_issue: Optional[str], command: str, project_area: Optional[str]
) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for pid, p in OPERATIONAL_PROFILES.items():
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


def operational_readiness_status() -> Dict[str, Any]:
    return {
        "layer": "30.2",
        "name": "Operational Readiness Preview",
        "status": "operational_readiness_ready",
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
            "/debug/operational-readiness-status",
            "/debug/operational-readiness-registry",
            "/debug/operational-readiness-preview",
        ],
        "connected_layers": [
            "30.1", "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
            "28.6", "28.5", "28.4", "28.3", "28.2", "28.1",
            "27.6", "27.5", "27.4",
            "26.7",
            "25.6", "25.5", "25.4",
        ],
        "safety_note": "Read-only operational readiness preview. No actual deployment actions performed.",
    }


def operational_readiness_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in OPERATIONAL_PROFILES.items():
        items.append(
            {
                "id": pid,
                "target_component": p["target_component"],
                "operational_category": p["operational_category"],
                "operational_status": p["operational_status"],
                "operational_score": p["operational_score"],
                "operational_risk_level": p["operational_risk_level"],
                "operational_readiness": p["operational_readiness"],
                "blocker_count": len(p.get("operational_blockers", [])),
                "confidence_score": p["confidence_score"],
            }
        )
    return {
        "layer": "30.2",
        "name": "Operational Readiness Registry",
        "status": "operational_readiness_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "operational_count": len(items),
        "operational_items": items,
        "ready_count": sum(1 for i in items if i["operational_readiness"] is True),
        "blocked_count": sum(1 for i in items if i["operational_readiness"] is False),
        "pass_count": sum(1 for i in items if i.get("operational_status") == "pass"),
        "violation_count": sum(
            1 for i in items if i.get("operational_status") == "violation"
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


def build_operational_readiness_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_profile(target_issue, command, project_area)
    p = OPERATIONAL_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 30.2"

    prod_readiness = build_production_readiness_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
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
            + float(prod_readiness.get("confidence_score", 0.0))
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
        / 19,
        2,
    )

    return {
        "operational_id": pid,
        "target_issue": detected,
        "target_component": p["target_component"],
        "operational_category": p["operational_category"],
        "operational_status": p["operational_status"],
        "operational_score": p["operational_score"],
        "operational_requirements": list(p["operational_requirements"]),
        "operational_findings": list(p["operational_findings"]),
        "operational_blockers": list(p["operational_blockers"]),
        "operational_risk_level": p["operational_risk_level"],
        "operational_recommendations": list(p["operational_recommendations"]),
        "operational_readiness": p["operational_readiness"],
        "required_actions": list(p["required_actions"]),
        "recommended_next_action": p["recommended_next_action"],
        "confidence_score": conf,
        "integration_signals": {
            "production_readiness": {
                "production_ready": prod_readiness.get("production_ready"),
                "readiness_score": prod_readiness.get("readiness_score"),
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
        "safety_note": "Read-only operational readiness preview. No actual deployment actions performed.",
    }