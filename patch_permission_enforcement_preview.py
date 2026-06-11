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
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


PERMISSION_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "permission_level": "normal",
        "permission_source": "patch_lifecycle_approval_gate",
        "allowed_actions": [
            "read_all_endpoints",
            "preview_patch_draft",
            "preview_change",
            "preview_diff",
            "view_risk_matrix",
            "view_approval_status",
            "view_execution_readiness",
            "view_safe_patch_status",
            "view_rollback_status",
            "view_validation_status",
            "view_recovery_status",
            "view_audit_status",
            "view_lifecycle_status",
        ],
        "blocked_actions": [
            "apply_patch",
            "execute_rollback",
            "write_files",
            "git_commit",
            "git_push",
            "subprocess_execution",
        ],
        "required_approvals": ["auto_approval_sufficient"],
        "required_validations": ["basic_smoke_tests"],
        "required_boundaries": ["stop_continue_resume_boundary"],
        "permission_risk_level": "low",
        "permission_readiness": True,
        "recommended_next_action": "no additional permissions required; monitor post-merge",
        "confidence_score": 0.87,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "permission_level": "elevated",
        "permission_source": "patch_lifecycle_approval_gate + boundary_check",
        "allowed_actions": [
            "read_all_endpoints",
            "preview_patch_draft",
            "preview_change",
            "preview_diff",
            "view_risk_matrix",
            "view_approval_status",
        ],
        "blocked_actions": [
            "apply_patch",
            "execute_rollback",
            "write_files",
            "git_commit",
            "git_push",
            "subprocess_execution",
            "view_execution_readiness",
            "view_safe_patch_status",
            "view_rollback_status",
            "view_validation_status",
            "view_recovery_status",
            "view_audit_status",
            "view_lifecycle_status",
        ],
        "required_approvals": ["manual_approval_required", "boundary_check_pass"],
        "required_validations": ["full_regression_suite", "canary_deployment"],
        "required_boundaries": ["safe_change_boundary_ok", "no_chat_stream_mutation"],
        "permission_risk_level": "high",
        "permission_readiness": False,
        "recommended_next_action": "resolve boundary blocks before elevated permissions can be granted",
        "confidence_score": 0.83,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "permission_level": "normal",
        "permission_source": "patch_lifecycle_approval_gate",
        "allowed_actions": [
            "read_all_endpoints",
            "preview_patch_draft",
            "preview_change",
            "preview_diff",
            "view_risk_matrix",
            "view_approval_status",
            "view_execution_readiness",
            "view_safe_patch_status",
            "view_rollback_status",
            "view_validation_status",
            "view_recovery_status",
            "view_audit_status",
            "view_lifecycle_status",
        ],
        "blocked_actions": [
            "apply_patch",
            "execute_rollback",
            "write_files",
            "git_commit",
            "git_push",
            "subprocess_execution",
        ],
        "required_approvals": ["auto_approval_sufficient"],
        "required_validations": ["export_format_validation"],
        "required_boundaries": ["export_preview_write_guard"],
        "permission_risk_level": "low",
        "permission_readiness": True,
        "recommended_next_action": "run export validation suite before merge; permissions are ready",
        "confidence_score": 0.86,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "permission_level": "elevated",
        "permission_source": "patch_lifecycle_approval_gate + platform_boundary",
        "allowed_actions": [
            "read_all_endpoints",
            "preview_patch_draft",
            "preview_change",
            "preview_diff",
            "view_risk_matrix",
            "view_approval_status",
        ],
        "blocked_actions": [
            "apply_patch",
            "execute_rollback",
            "write_files",
            "git_commit",
            "git_push",
            "subprocess_execution",
            "view_execution_readiness",
            "view_safe_patch_status",
            "view_rollback_status",
            "view_validation_status",
            "view_recovery_status",
            "view_audit_status",
            "view_lifecycle_status",
        ],
        "required_approvals": ["platform_specific_approval", "privacy_boundary_check"],
        "required_validations": ["platform_validation_suite", "privacy_audit"],
        "required_boundaries": ["android_permission_boundary", "ios_permission_boundary"],
        "permission_risk_level": "high",
        "permission_readiness": False,
        "recommended_next_action": "set up platform validation tooling; elevated permissions not yet grantable",
        "confidence_score": 0.85,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "permission", "test"],
        "target_component": "preview_schema",
        "permission_level": "normal",
        "permission_source": "patch_lifecycle_approval_gate",
        "allowed_actions": [
            "read_all_endpoints",
            "preview_patch_draft",
            "preview_change",
            "preview_diff",
            "view_risk_matrix",
            "view_approval_status",
            "view_execution_readiness",
            "view_safe_patch_status",
            "view_rollback_status",
            "view_validation_status",
            "view_recovery_status",
            "view_audit_status",
            "view_lifecycle_status",
        ],
        "blocked_actions": [
            "apply_patch",
            "execute_rollback",
            "write_files",
            "git_commit",
            "git_push",
            "subprocess_execution",
        ],
        "required_approvals": ["auto_approval_sufficient"],
        "required_validations": ["smoke_tests_pass"],
        "required_boundaries": ["preview_only_boundary"],
        "permission_risk_level": "low",
        "permission_readiness": True,
        "recommended_next_action": "run smoke tests before merge; permissions are ready",
        "confidence_score": 0.9,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_issue: Optional[str], command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for pid, p in PERMISSION_PROFILES.items():
        if pid in haystack or any(a.lower() in haystack for a in p.get("aliases", [])):
            return pid
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    out: List[Any] = []
    for i in items:
        if i and i not in out:
            out.append(i)
    return out


def patch_permission_status() -> Dict[str, Any]:
    return {"layer": "29.1", "name": "Patch Permission Enforcement Preview",
            "status": "patch_permission_ready",
            "read_only": True, "strict_read_only": True, "analysis_only": True, "preview_only": True,
            "real_action_performed": False,
            "file_write_enabled": False, "memory_write_enabled": False, "db_write_enabled": False,
            "git_write_enabled": False, "commit_enabled": False, "push_enabled": False,
            "deploy_enabled": False, "auto_fix_enabled": False, "patch_apply_enabled": False,
            "subprocess_execution_enabled": False, "repo_scan_performed": False,
            "chat_stream_touched": False, "typewriter_runtime_touched": False,
            "available_endpoints": [
                "/debug/patch-permission-status",
                "/debug/patch-permission-registry",
                "/debug/patch-permission-preview",
            ],
            "connected_layers": [
                "28", "28.6", "28.5", "28.4", "28.3", "28.2", "28.1",
                "27.6", "27.5", "27.4", "27.3", "27.2", "27.1",
                "26.7", "26.6", "25.6", "25.5", "25.4",
            ],
            "safety_note": "Read-only permission preview. No actual permission enforcement."}


def patch_permission_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in PERMISSION_PROFILES.items():
        items.append({
            "id": pid,
            "target_component": p["target_component"],
            "permission_level": p["permission_level"],
            "permission_source": p["permission_source"],
            "permission_risk_level": p["permission_risk_level"],
            "permission_readiness": p["permission_readiness"],
            "confidence_score": p["confidence_score"],
        })
    return {
        "layer": "29.1", "name": "Patch Permission Registry",
        "status": "patch_permission_registry_ready",
        "read_only": True, "strict_read_only": True, "analysis_only": True,
        "permission_count": len(items), "permissions": items,
        "ready_count": sum(1 for i in items if i["permission_readiness"] is True),
        "blocked_count": sum(1 for i in items if i["permission_readiness"] is False),
        "pending_count": sum(1 for i in items if i["permission_readiness"] is None),
        "safety_flags": {
            "file_write": False, "memory_write": False, "db_write": False, "git_write": False,
            "commit": False, "push": False, "deploy": False, "auto_fix": False,
            "patch_apply": False, "subprocess_execution": False,
        },
    }


def build_patch_permission_preview(
    target_issue: Optional[str] = None, command: str = "",
    project_area: Optional[str] = None, related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_profile(target_issue, command, project_area)
    p = PERMISSION_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 29.1"

    lifecycle = build_patch_lifecycle_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    audit = build_patch_audit_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    recovery = build_patch_recovery_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    validation = build_patch_validation_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    rollback = build_patch_rollback_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    safe_patch = build_safe_patch_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    execution = build_patch_execution_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    approval = build_patch_approval_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    risk = build_patch_risk_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    diff = build_diff_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    change = build_change_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    draft = build_patch_draft_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    coordinator = build_coordinator_preview(
        command=cmd, project_area=project_area or detected, related_layer=L)
    evidence = build_evidence_store_preview(
        finding=None, command=cmd, project_area=project_area or detected, related_layer=L)
    verification = build_verification_planner_preview(
        target_issue=detected, command=cmd, related_layer=L)
    planner = build_patch_planner_preview(
        target_issue=detected, command=cmd, related_layer=L)
    boundary = build_change_boundary_preview(
        target_area=detected, command=cmd, related_layer=L)

    conf = round((
        float(p["confidence_score"])
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
    ) / 15, 2)

    return {
        "permission_level": p["permission_level"],
        "permission_source": p["permission_source"],
        "allowed_actions": list(p["allowed_actions"]),
        "blocked_actions": list(p["blocked_actions"]),
        "required_approvals": list(p["required_approvals"]),
        "required_validations": list(p["required_validations"]),
        "required_boundaries": list(p["required_boundaries"]),
        "permission_risk_level": p["permission_risk_level"],
        "permission_readiness": p["permission_readiness"],
        "recommended_next_action": p["recommended_next_action"],
        "confidence_score": conf,
        "integration_signals": {
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
        "read_only": True, "strict_read_only": True, "analysis_only": True, "preview_only": True,
        "real_action_performed": False,
        "file_write_performed": False, "memory_write_performed": False, "db_write_performed": False,
        "git_write_performed": False, "commit_performed": False, "push_performed": False,
        "deploy_performed": False, "auto_fix_performed": False, "patch_apply_performed": False,
        "subprocess_execution_performed": False, "repo_scan_performed": False,
        "chat_stream_touched": False, "typewriter_runtime_touched": False,
        "safety_note": "Read-only permission preview. No actual permission enforcement.",
    }
