from __future__ import annotations
from typing import Any, Dict, List, Optional

from operational_readiness_preview import build_operational_readiness_preview, operational_readiness_registry
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


SYSTEM_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "system_category": "flow_safety",
        "system_status": "pass",
        "system_score": 0.82,
        "system_requirements": [
            "operational_score_above_0.8",
            "production_score_above_0.8",
            "full_stack_integration_verified",
        ],
        "system_findings": [
            "ops_and_prod_readiness_satisfactory",
            "full_stack_trace_complete",
        ],
        "system_blockers": [],
        "system_risk_level": "low",
        "system_recommendations": [
            "prepare_system_go_live_checklist",
        ],
        "system_readiness": False,
        "required_actions": [],
        "recommended_next_action": "system readiness is satisfactory; create go-live checklist",
        "confidence_score": 0.86,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "system_category": "stream_integrity",
        "system_status": "violation",
        "system_score": 0.18,
        "system_requirements": [
            "ops_and_prod_score_above_0.7",
            "all_blockers_resolved_at_all_layers",
        ],
        "system_findings": [
            "ops_blockers_propagate_to_system_level",
            "prod_blockers_also_active",
        ],
        "system_blockers": [
            "full_stack_blocker_cascade_from_layer_29",
            "no_deployment_path_available",
        ],
        "system_risk_level": "high",
        "system_recommendations": [
            "resolve_layer_29_cascade_before_system_readiness",
        ],
        "system_readiness": False,
        "required_actions": [
            "resolve_tab_switch_at_source",
            "clear_all_production_and_ops_blockers",
        ],
        "recommended_next_action": "system readiness blocked by cascade from lower layers",
        "confidence_score": 0.84,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "system_category": "export_safety",
        "system_status": "pass",
        "system_score": 0.81,
        "system_requirements": [
            "export_pipeline_ops_ready",
            "prod_readiness_above_threshold",
        ],
        "system_findings": [
            "ops_and_prod_readiness_clear",
            "system_trace_complete",
        ],
        "system_blockers": [],
        "system_risk_level": "low",
        "system_recommendations": [
            "include_export_in_go_live_scope",
        ],
        "system_readiness": False,
        "required_actions": [],
        "recommended_next_action": "system readiness acceptable; include in deployment plan",
        "confidence_score": 0.85,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "system_category": "platform_privacy",
        "system_status": "violation",
        "system_score": 0.12,
        "system_requirements": [
            "ops_and_prod_readiness_cleared",
            "privacy_audit_system_ready",
        ],
        "system_findings": [
            "ops_and_prod_blockers_cascade_to_system",
            "no_system_level_path_available",
        ],
        "system_blockers": [
            "full_stack_blocker_cascade_every_layer",
            "system_readiness_impossible_until_permission_tests_exist",
        ],
        "system_risk_level": "high",
        "system_recommendations": [
            "full_remediation_chain_required",
        ],
        "system_readiness": False,
        "required_actions": [
            "build_test_suites",
            "complete_audit",
            "clear_all_downstream_blockers",
        ],
        "recommended_next_action": "system readiness gated behind full remediation chain",
        "confidence_score": 0.83,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "system", "test"],
        "target_component": "preview_schema",
        "system_category": "scaffold_safety",
        "system_status": "pass",
        "system_score": 0.88,
        "system_requirements": [
            "ops_handoff_complete",
            "prod_readiness_confirmed",
        ],
        "system_findings": [
            "highest_ops_and_prod_scores",
            "system_trace_green_across_all_integrations",
        ],
        "system_blockers": [],
        "system_risk_level": "low",
        "system_recommendations": [
            "first_candidate_for_system_go_live",
        ],
        "system_readiness": False,
        "required_actions": [],
        "recommended_next_action": "best system readiness candidate; schedule go-live review",
        "confidence_score": 0.90,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(
    target_issue: Optional[str], command: str, project_area: Optional[str]
) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for pid, p in SYSTEM_PROFILES.items():
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


def system_readiness_status() -> Dict[str, Any]:
    return {
        "layer": "30.3",
        "name": "System Readiness Preview",
        "status": "system_readiness_ready",
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
            "/debug/system-readiness-status",
            "/debug/system-readiness-registry",
            "/debug/system-readiness-preview",
        ],
        "connected_layers": [
            "30.2", "30.1", "29", "29.8", "29.7", "29.6", "29.5", "29.4", "29.3", "29.2", "29.1",
            "28.6", "28.5", "28.4", "28.3", "28.2", "28.1",
            "27.6", "27.5", "27.4",
            "26.7",
            "25.6", "25.5", "25.4",
        ],
        "safety_note": "Read-only system readiness preview. No actual deployment actions performed.",
    }


def system_readiness_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in SYSTEM_PROFILES.items():
        items.append(
            {
                "id": pid,
                "target_component": p["target_component"],
                "system_category": p["system_category"],
                "system_status": p["system_status"],
                "system_score": p["system_score"],
                "system_risk_level": p["system_risk_level"],
                "system_readiness": p["system_readiness"],
                "blocker_count": len(p.get("system_blockers", [])),
                "confidence_score": p["confidence_score"],
            }
        )
    return {
        "layer": "30.3",
        "name": "System Readiness Registry",
        "status": "system_readiness_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "system_count": len(items),
        "system_items": items,
        "ready_count": sum(1 for i in items if i["system_readiness"] is True),
        "blocked_count": sum(1 for i in items if i["system_readiness"] is False),
        "pass_count": sum(1 for i in items if i.get("system_status") == "pass"),
        "violation_count": sum(
            1 for i in items if i.get("system_status") == "violation"
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


def build_system_readiness_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_profile(target_issue, command, project_area)
    p = SYSTEM_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 30.3"

    ops_readiness = build_operational_readiness_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L
    )
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
            + float(ops_readiness.get("confidence_score", 0.0))
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
        / 20,
        2,
    )

    return {
        "system_id": pid,
        "target_issue": detected,
        "target_component": p["target_component"],
        "system_category": p["system_category"],
        "system_status": p["system_status"],
        "system_score": p["system_score"],
        "system_requirements": list(p["system_requirements"]),
        "system_findings": list(p["system_findings"]),
        "system_blockers": list(p["system_blockers"]),
        "system_risk_level": p["system_risk_level"],
        "system_recommendations": list(p["system_recommendations"]),
        "system_readiness": p["system_readiness"],
        "required_actions": list(p["required_actions"]),
        "recommended_next_action": p["recommended_next_action"],
        "confidence_score": conf,
        "integration_signals": {
            "operational_readiness": {
                "operational_score": ops_readiness.get("operational_score"),
                "operational_readiness": ops_readiness.get("operational_readiness"),
            },
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
        "safety_note": "Read-only system readiness preview. No actual deployment actions performed.",
    }