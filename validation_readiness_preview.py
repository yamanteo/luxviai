from __future__ import annotations
from typing import Any, Dict, List, Optional

from system_readiness_preview import build_system_readiness_preview, system_readiness_registry
from operational_readiness_preview import build_operational_readiness_preview, operational_readiness_registry
from production_readiness_preview import build_production_readiness_preview, production_readiness_registry
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


VALIDATION_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "validation_category": "flow_safety",
        "validation_status": "pass",
        "validation_score": 0.80,
        "validation_requirements": [
            "system_readiness_score_above_0.75",
            "operational_readiness_score_above_0.75",
            "production_readiness_score_above_0.75",
            "all_downstream_validation_gates_passing",
        ],
        "validation_findings": [
            "system_readiness_satisfactory",
            "operational_readiness_clear",
            "production_readiness_acceptable",
        ],
        "validation_blockers": [],
        "validation_risk_level": "low",
        "validation_recommendations": [
            "schedule_validation_review",
            "document_validation_criteria_for_ops",
        ],
        "validation_readiness": False,
        "required_actions": [],
        "recommended_next_action": "validation readiness is satisfactory; proceed to final review",
        "confidence_score": 0.86,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "validation_category": "stream_integrity",
        "validation_status": "violation",
        "validation_score": 0.15,
        "validation_requirements": [
            "system_readiness_score_above_0.7",
            "all_layer_30_readiness_signals_green",
            "no_validation_gaps_across_integration_chain",
        ],
        "validation_findings": [
            "system_readiness_blocked_cascades_to_validation",
            "operational_readiness_not_achievable",
            "production_readiness_blockers_persist",
        ],
        "validation_blockers": [
            "tab_switch_regression_blocks_all_upstream_readiness",
            "typewriter_queue_ownership_unassigned",
            "privacy_audit_not_completed",
        ],
        "validation_risk_level": "high",
        "validation_recommendations": [
            "resolve_all_upstream_readiness_blockers_first",
            "re-run_validation_readiness_after_upstream_fixes",
        ],
        "validation_readiness": False,
        "required_actions": [
            "fix_tab_switch_regression_at_source",
            "assign_typewriter_queue_ownership",
            "complete_privacy_audit",
        ],
        "recommended_next_action": "validation readiness gated behind all upstream readiness layers",
        "confidence_score": 0.84,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "validation_category": "export_safety",
        "validation_status": "pass",
        "validation_score": 0.78,
        "validation_requirements": [
            "system_readiness_for_export_confirmed",
            "operational_readiness_acceptable",
        ],
        "validation_findings": [
            "system_and_ops_readiness_clear_for_export",
            "validation_gaps_none",
        ],
        "validation_blockers": [],
        "validation_risk_level": "low",
        "validation_recommendations": [
            "perform_validation_dry_run_on_export_pipeline",
        ],
        "validation_readiness": False,
        "required_actions": [],
        "recommended_next_action": "validation readiness acceptable; schedule dry run",
        "confidence_score": 0.85,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "validation_category": "platform_privacy",
        "validation_status": "violation",
        "validation_score": 0.10,
        "validation_requirements": [
            "system_readiness_cleared",
            "operational_readiness_cleared",
            "production_readiness_cleared",
            "privacy_audit_system_ready",
        ],
        "validation_findings": [
            "all_upstream_readiness_blockers_cascade_to_validation",
            "no_validation_path_available_until_upstream_clear",
        ],
        "validation_blockers": [
            "full_stack_blocker_cascade_every_layer",
            "validation_readiness_impossible_until_permission_tests_exist",
            "privacy_audit_not_signed",
        ],
        "validation_risk_level": "high",
        "validation_recommendations": [
            "full_remediation_chain_required_before_validation",
        ],
        "validation_readiness": False,
        "required_actions": [
            "build_test_suites",
            "complete_audit",
            "clear_all_upstream_readiness_blockers",
        ],
        "recommended_next_action": "validation readiness gated behind full upstream remediation chain",
        "confidence_score": 0.83,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "validation", "test"],
        "target_component": "preview_schema",
        "validation_category": "scaffold_safety",
        "validation_status": "pass",
        "validation_score": 0.85,
        "validation_requirements": [
            "system_readiness_confirmed",
            "operational_readiness_confirmed",
            "production_readiness_confirmed",
        ],
        "validation_findings": [
            "highest_upstream_readiness_scores",
            "validation_green_across_all_integrations",
        ],
        "validation_blockers": [],
        "validation_risk_level": "low",
        "validation_recommendations": [
            "first_candidate_for_validation_go_live",
        ],
        "validation_readiness": False,
        "required_actions": [],
        "recommended_next_action": "best validation readiness candidate; schedule validation review",
        "confidence_score": 0.88,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(
    target_issue: Optional[str], command: str, project_area: Optional[str]
) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for pid, p in VALIDATION_PROFILES.items():
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


def validation_readiness_status() -> Dict[str, Any]:
    return {
        "layer": "30.4",
        "name": "Validation Readiness Preview",
        "status": "validation_readiness_ready",
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
            "/debug/validation-readiness-status",
            "/debug/validation-readiness-registry",
            "/debug/validation-readiness-preview",
        ],
        "connected_layers": [
            "30.3", "30.2", "30.1", "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
            "28.6", "28.5", "28.4", "28.3", "28.2", "28.1",
            "27.6", "27.5", "27.4",
            "26.7",
            "25.6", "25.5", "25.4",
        ],
        "safety_note": "Read-only validation readiness preview. No actual deployment actions performed.",
    }


def validation_readiness_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in VALIDATION_PROFILES.items():
        items.append(
            {
                "id": pid,
                "target_component": p["target_component"],
                "validation_category": p["validation_category"],
                "validation_status": p["validation_status"],
                "validation_score": p["validation_score"],
                "validation_risk_level": p["validation_risk_level"],
                "validation_readiness": p["validation_readiness"],
                "blocker_count": len(p.get("validation_blockers", [])),
                "confidence_score": p["confidence_score"],
            }
        )
    return {
        "layer": "30.4",
        "name": "Validation Readiness Registry",
        "status": "validation_readiness_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "validation_count": len(items),
        "validation_items": items,
        "ready_count": sum(1 for i in items if i["validation_readiness"] is True),
        "blocked_count": sum(1 for i in items if i["validation_readiness"] is False),
        "pass_count": sum(1 for i in items if i.get("validation_status") == "pass"),
        "violation_count": sum(
            1 for i in items if i.get("validation_status") == "violation"
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


def build_validation_readiness_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_profile(target_issue, command, project_area)
    p = VALIDATION_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 30.4"

    system_rd = build_system_readiness_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    ops_rd = build_operational_readiness_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
    prod_rd = build_production_readiness_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
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
            + float(system_rd.get("confidence_score", 0.0))
            + float(ops_rd.get("confidence_score", 0.0))
            + float(prod_rd.get("confidence_score", 0.0))
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
        / 21,
        2,
    )

    return {
        "validation_id": pid,
        "target_issue": detected,
        "target_component": p["target_component"],
        "validation_category": p["validation_category"],
        "validation_status": p["validation_status"],
        "validation_score": p["validation_score"],
        "validation_requirements": list(p["validation_requirements"]),
        "validation_findings": list(p["validation_findings"]),
        "validation_blockers": list(p["validation_blockers"]),
        "validation_risk_level": p["validation_risk_level"],
        "validation_recommendations": list(p["validation_recommendations"]),
        "validation_readiness": p["validation_readiness"],
        "required_actions": list(p["required_actions"]),
        "recommended_next_action": p["recommended_next_action"],
        "confidence_score": conf,
        "integration_signals": {
            "system_readiness": {
                "system_readiness": system_rd.get("system_readiness"),
                "system_score": system_rd.get("system_score"),
            },
            "operational_readiness": {
                "operational_readiness": ops_rd.get("operational_readiness"),
                "operational_score": ops_rd.get("operational_score"),
            },
            "production_readiness": {
                "production_ready": prod_rd.get("production_ready"),
                "readiness_score": prod_rd.get("readiness_score"),
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
        "safety_note": "Read-only validation readiness preview. No actual deployment actions performed.",
    }
