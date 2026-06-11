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
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


POLICY_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "policy_category": "flow_consolidation",
        "policy_result": "pass",
        "policy_reason": "low-risk consolidation with single-commit revert path",
        "policy_requirements": [
            "all_stop_continue_tests_pass",
            "no_active_stream_during_patch",
        ],
        "policy_restrictions": [
            "no concurrent resume flows",
            "websocket reconnect must complete within 2s",
        ],
        "policy_exceptions": [],
        "policy_risk_level": "low",
        "policy_readiness": True,
        "recommended_next_action": "no policy exceptions needed; monitor post-merge",
        "confidence_score": 0.87,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "policy_category": "runtime_stream_mutation",
        "policy_result": "block",
        "policy_reason": "high blast radius — multi-hunk patch with websocket state mutation; policy requires canary and manual regression",
        "policy_requirements": [
            "canary_deployment_pipeline_established",
            "full_stream_regression_passed",
            "typewriter_state_audit_completed",
        ],
        "policy_restrictions": [
            "no direct stream apply without canary",
            "manual tab switch regression required",
            "typewriter queue ownership must not change",
        ],
        "policy_exceptions": [
            "canary_permitted_if_regression_suite_ready",
        ],
        "policy_risk_level": "high",
        "policy_readiness": False,
        "recommended_next_action": "establish canary deployment and complete manual regression before policy can pass",
        "confidence_score": 0.83,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "policy_category": "preview_export",
        "policy_result": "pass",
        "policy_reason": "preview-only component with no production export path",
        "policy_requirements": [
            "export_format_validation_suite_passes",
            "write_guard_assertion_active",
        ],
        "policy_restrictions": [
            "no real file export permitted from preview layer",
        ],
        "policy_exceptions": [],
        "policy_risk_level": "low",
        "policy_readiness": True,
        "recommended_next_action": "run export validation suite before merge; policy is green",
        "confidence_score": 0.86,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "policy_category": "platform_permission",
        "policy_result": "block",
        "policy_reason": "platform-specific behavior with user-facing permission UX; requires platform validation tooling",
        "policy_requirements": [
            "android_platform_tests_present",
            "ios_platform_tests_present",
            "privacy_boundary_audit_completed",
        ],
        "policy_restrictions": [
            "no cross-platform permission apply without independent validation",
            "private data surface must remain guarded",
        ],
        "policy_exceptions": [
            "platform_bypass_allowed_if_audited",
        ],
        "policy_risk_level": "high",
        "policy_readiness": False,
        "recommended_next_action": "set up platform validation tooling before policy can pass",
        "confidence_score": 0.85,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "policy", "test"],
        "target_component": "preview_schema",
        "policy_category": "scaffold_preview",
        "policy_result": "pass",
        "policy_reason": "read-only scaffold addition with zero runtime impact",
        "policy_requirements": [
            "all_existing_smoke_tests_pass",
        ],
        "policy_restrictions": [
            "no debug endpoint may write files or execute subprocesses",
        ],
        "policy_exceptions": [],
        "policy_risk_level": "low",
        "policy_readiness": True,
        "recommended_next_action": "run smoke tests before merge; policy is green",
        "confidence_score": 0.9,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_issue: Optional[str], command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for pid, p in POLICY_PROFILES.items():
        if pid in haystack or any(a.lower() in haystack for a in p.get("aliases", [])):
            return pid
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    out: List[Any] = []
    for i in items:
        if i and i not in out:
            out.append(i)
    return out


def patch_policy_status() -> Dict[str, Any]:
    return {"layer": "29.2", "name": "Patch Policy Evaluation Preview",
            "status": "patch_policy_ready",
            "read_only": True, "strict_read_only": True, "analysis_only": True, "preview_only": True,
            "real_action_performed": False,
            "file_write_enabled": False, "memory_write_enabled": False, "db_write_enabled": False,
            "git_write_enabled": False, "commit_enabled": False, "push_enabled": False,
            "deploy_enabled": False, "auto_fix_enabled": False, "patch_apply_enabled": False,
            "subprocess_execution_enabled": False, "repo_scan_performed": False,
            "chat_stream_touched": False, "typewriter_runtime_touched": False,
            "available_endpoints": [
                "/debug/patch-policy-status",
                "/debug/patch-policy-registry",
                "/debug/patch-policy-preview",
            ],
            "connected_layers": [
                "29.1", "28", "28.6", "28.5", "28.4", "28.3", "28.2", "28.1",
                "27.6", "27.5", "27.4", "27.3", "27.2", "27.1",
                "26.7", "26.6", "25.6", "25.5", "25.4",
            ],
            "safety_note": "Read-only policy evaluation preview. No actual policy enforcement."}


def patch_policy_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in POLICY_PROFILES.items():
        items.append({
            "id": pid,
            "target_component": p["target_component"],
            "policy_category": p["policy_category"],
            "policy_result": p["policy_result"],
            "policy_risk_level": p["policy_risk_level"],
            "policy_readiness": p["policy_readiness"],
            "confidence_score": p["confidence_score"],
        })
    return {
        "layer": "29.2", "name": "Patch Policy Registry",
        "status": "patch_policy_registry_ready",
        "read_only": True, "strict_read_only": True, "analysis_only": True,
        "policy_count": len(items), "policies": items,
        "ready_count": sum(1 for i in items if i["policy_readiness"] is True),
        "blocked_count": sum(1 for i in items if i["policy_readiness"] is False),
        "pending_count": sum(1 for i in items if i["policy_readiness"] is None),
        "safety_flags": {
            "file_write": False, "memory_write": False, "db_write": False, "git_write": False,
            "commit": False, "push": False, "deploy": False, "auto_fix": False,
            "patch_apply": False, "subprocess_execution": False,
        },
    }


def build_patch_policy_preview(
    target_issue: Optional[str] = None, command: str = "",
    project_area: Optional[str] = None, related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_profile(target_issue, command, project_area)
    p = POLICY_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 29.2"

    permission = build_patch_permission_preview(
        target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
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
    ) / 16, 2)

    return {
        "policy_id": pid,
        "policy_category": p["policy_category"],
        "policy_result": p["policy_result"],
        "policy_reason": p["policy_reason"],
        "policy_requirements": list(p["policy_requirements"]),
        "policy_restrictions": list(p["policy_restrictions"]),
        "policy_exceptions": list(p["policy_exceptions"]),
        "policy_risk_level": p["policy_risk_level"],
        "policy_readiness": p["policy_readiness"],
        "recommended_next_action": p["recommended_next_action"],
        "confidence_score": conf,
        "integration_signals": {
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
        "read_only": True, "strict_read_only": True, "analysis_only": True, "preview_only": True,
        "real_action_performed": False,
        "file_write_performed": False, "memory_write_performed": False, "db_write_performed": False,
        "git_write_performed": False, "commit_performed": False, "push_performed": False,
        "deploy_performed": False, "auto_fix_performed": False, "patch_apply_performed": False,
        "subprocess_execution_performed": False, "repo_scan_performed": False,
        "chat_stream_touched": False, "typewriter_runtime_touched": False,
        "safety_note": "Read-only policy evaluation preview. No actual policy enforcement.",
    }
