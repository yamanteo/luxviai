from __future__ import annotations
from typing import Any, Dict, List, Optional

from validation_readiness_preview import build_validation_readiness_preview, validation_readiness_registry
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


RELEASE_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "release_category": "flow_safety",
        "release_status": "pass",
        "release_score": 0.78,
        "release_requirements": [
            "validation_readiness_score_above_0.75",
            "system_readiness_score_above_0.75",
            "operational_readiness_score_above_0.75",
            "production_readiness_score_above_0.75",
            "all_release_gates_passing",
        ],
        "release_findings": [
            "validation_readiness_satisfactory",
            "system_readiness_clear",
            "operational_and_production_acceptable",
        ],
        "release_blockers": [],
        "release_risk_level": "low",
        "release_recommendations": [
            "schedule_release_review",
            "prepare_release_notes",
        ],
        "release_readiness": False,
        "required_actions": [],
        "recommended_next_action": "release readiness is satisfactory; proceed to release review",
        "confidence_score": 0.85,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "release_category": "stream_integrity",
        "release_status": "violation",
        "release_score": 0.12,
        "release_requirements": [
            "validation_readiness_score_above_0.7",
            "all_layer_30_readiness_signals_green",
            "no_release_gaps_across_integration_chain",
        ],
        "release_findings": [
            "validation_readiness_blocked_cascades_to_release",
            "system_readiness_not_achievable",
            "operational_and_production_blockers_persist",
        ],
        "release_blockers": [
            "tab_switch_regression_blocks_all_upstream_readiness",
            "typewriter_queue_ownership_unassigned",
            "privacy_audit_not_completed",
        ],
        "release_risk_level": "high",
        "release_recommendations": [
            "resolve_all_upstream_readiness_blockers_first",
            "re-run_release_readiness_after_upstream_fixes",
        ],
        "release_readiness": False,
        "required_actions": [
            "fix_tab_switch_regression_at_source",
            "assign_typewriter_queue_ownership",
            "complete_privacy_audit",
        ],
        "recommended_next_action": "release readiness gated behind all upstream readiness layers",
        "confidence_score": 0.83,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "release_category": "export_safety",
        "release_status": "pass",
        "release_score": 0.75,
        "release_requirements": [
            "validation_readiness_for_export_confirmed",
            "system_readiness_acceptable",
        ],
        "release_findings": [
            "all_upstream_readiness_clear_for_export",
            "release_gaps_none",
        ],
        "release_blockers": [],
        "release_risk_level": "low",
        "release_recommendations": [
            "perform_release_dry_run_on_export_pipeline",
        ],
        "release_readiness": False,
        "required_actions": [],
        "recommended_next_action": "release readiness acceptable; schedule dry run",
        "confidence_score": 0.84,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "release_category": "platform_privacy",
        "release_status": "violation",
        "release_score": 0.08,
        "release_requirements": [
            "validation_readiness_cleared",
            "system_readiness_cleared",
            "operational_readiness_cleared",
            "production_readiness_cleared",
            "privacy_audit_release_ready",
        ],
        "release_findings": [
            "all_upstream_readiness_blockers_cascade_to_release",
            "no_release_path_available_until_upstream_clear",
        ],
        "release_blockers": [
            "full_stack_blocker_cascade_every_layer",
            "release_readiness_impossible_until_permission_tests_exist",
            "privacy_audit_not_signed",
        ],
        "release_risk_level": "high",
        "release_recommendations": [
            "full_remediation_chain_required_before_release",
        ],
        "release_readiness": False,
        "required_actions": [
            "build_test_suites",
            "complete_audit",
            "clear_all_upstream_readiness_blockers",
        ],
        "recommended_next_action": "release readiness gated behind full upstream remediation chain",
        "confidence_score": 0.82,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "release", "test"],
        "target_component": "preview_schema",
        "release_category": "scaffold_safety",
        "release_status": "pass",
        "release_score": 0.82,
        "release_requirements": [
            "validation_readiness_confirmed",
            "system_readiness_confirmed",
            "operational_readiness_confirmed",
            "production_readiness_confirmed",
        ],
        "release_findings": [
            "highest_upstream_readiness_scores",
            "release_green_across_all_integrations",
        ],
        "release_blockers": [],
        "release_risk_level": "low",
        "release_recommendations": [
            "first_candidate_for_release_go_live",
        ],
        "release_readiness": False,
        "required_actions": [],
        "recommended_next_action": "best release readiness candidate; schedule release review",
        "confidence_score": 0.87,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(
    target_issue: Optional[str], command: str, project_area: Optional[str]
) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for pid, p in RELEASE_PROFILES.items():
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


def release_readiness_status() -> Dict[str, Any]:
    return {
        "layer": "30.5",
        "name": "Release Readiness Preview",
        "status": "release_readiness_ready",
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
            "/debug/release-readiness-status",
            "/debug/release-readiness-registry",
            "/debug/release-readiness-preview",
        ],
        "connected_layers": [
            "30.4", "30.3", "30.2", "30.1", "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
            "28.6", "28.5", "28.4", "28.3", "28.2", "28.1",
            "27.6", "27.5", "27.4",
            "26.7",
            "25.6", "25.5", "25.4",
        ],
        "safety_note": "Read-only release readiness preview. No actual deployment actions performed.",
    }


def release_readiness_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in RELEASE_PROFILES.items():
        items.append(
            {
                "id": pid,
                "target_component": p["target_component"],
                "release_category": p["release_category"],
                "release_status": p["release_status"],
                "release_score": p["release_score"],
                "release_risk_level": p["release_risk_level"],
                "release_readiness": p["release_readiness"],
                "blocker_count": len(p.get("release_blockers", [])),
                "confidence_score": p["confidence_score"],
            }
        )
    return {
        "layer": "30.5",
        "name": "Release Readiness Registry",
        "status": "release_readiness_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "release_count": len(items),
        "release_items": items,
        "ready_count": sum(1 for i in items if i["release_readiness"] is True),
        "blocked_count": sum(1 for i in items if i["release_readiness"] is False),
        "pass_count": sum(1 for i in items if i.get("release_status") == "pass"),
        "violation_count": sum(
            1 for i in items if i.get("release_status") == "violation"
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


def build_release_readiness_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_profile(target_issue, command, project_area)
    p = RELEASE_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 30.5"

    validation_rd = build_validation_readiness_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
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
            + float(validation_rd.get("confidence_score", 0.0))
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
        / 22,
        2,
    )

    return {
        "release_id": pid,
        "target_issue": detected,
        "target_component": p["target_component"],
        "release_category": p["release_category"],
        "release_status": p["release_status"],
        "release_score": p["release_score"],
        "release_requirements": list(p["release_requirements"]),
        "release_findings": list(p["release_findings"]),
        "release_blockers": list(p["release_blockers"]),
        "release_risk_level": p["release_risk_level"],
        "release_recommendations": list(p["release_recommendations"]),
        "release_readiness": p["release_readiness"],
        "required_actions": list(p["required_actions"]),
        "recommended_next_action": p["recommended_next_action"],
        "confidence_score": conf,
        "integration_signals": {
            "validation_readiness": {
                "validation_readiness": validation_rd.get("validation_readiness"),
                "validation_score": validation_rd.get("validation_score"),
            },
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
        "safety_note": "Read-only release readiness preview. No actual deployment actions performed.",
    }
