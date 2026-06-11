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
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


RECOVERY_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "failure_type": "runtime_flow_regression",
        "failure_scope": "stop_continue_resume",
        "recovery_required": False,
        "recovery_strategy": "git revert — single commit rollback, no data migration needed",
        "recovery_steps": [
            "1. Revert consolidation commit via git revert",
            "2. Re-run stop/continue smoke tests",
            "3. Verify websocket reconnect behavior",
            "4. Confirm no side effects in other flows",
        ],
        "recovery_dependencies": ["smoke_test_suite"],
        "recovery_risk_level": "low",
        "recovery_risk_reasons": ["single commit revert", "no data migration", "no schema change"],
        "rollback_dependency": "patch_rollback_preview",
        "validation_dependency": "patch_validation_preview",
        "recovery_readiness": True,
        "recommended_next_action": "no recovery action needed; monitor post-merge",
        "confidence_score": 0.87,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "failure_type": "runtime_stream_corruption",
        "failure_scope": "websocket_typewriter_tab",
        "recovery_required": True,
        "recovery_strategy": "canary-first rollback with full stream regression — high blast radius requires atomic revert",
        "recovery_steps": [
            "1. Canary rollback the stream change commit",
            "2. Full git revert of stream patch",
            "3. Re-run complete stream regression suite",
            "4. Verify production stream health metrics",
            "5. Re-deploy stable stream version",
        ],
        "recovery_dependencies": ["canary_deployment", "regression_suite", "production_monitoring"],
        "recovery_risk_level": "high",
        "recovery_risk_reasons": ["multi-hunk patch", "typewriter runtime change", "websocket state mutation", "large blast radius"],
        "rollback_dependency": "patch_rollback_preview",
        "validation_dependency": "patch_validation_preview",
        "recovery_readiness": False,
        "recommended_next_action": "establish canary deployment pipeline before attempting stream patch recovery",
        "confidence_score": 0.83,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "failure_type": "export_schema_mismatch",
        "failure_scope": "export_format_pipeline",
        "recovery_required": False,
        "recovery_strategy": "automated format revert — export pipeline is preview-only, no production impact",
        "recovery_steps": [
            "1. Revert export preview changes",
            "2. Re-run export format validation suite",
            "3. Verify write guard assertion remains active",
        ],
        "recovery_dependencies": ["smoke_test_suite"],
        "recovery_risk_level": "low",
        "recovery_risk_reasons": ["preview-only", "no production export", "no data migration"],
        "rollback_dependency": "patch_rollback_preview",
        "validation_dependency": "patch_validation_preview",
        "recovery_readiness": True,
        "recommended_next_action": "run export validation suite before merge",
        "confidence_score": 0.86,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "failure_type": "platform_permission_regression",
        "failure_scope": "android_ios_permission",
        "recovery_required": True,
        "recovery_strategy": "platform-specific — recover independently on Android and iOS; revert platform layer only",
        "recovery_steps": [
            "1. Identify which platform(s) regressed",
            "2. Revert affected platform permission changes",
            "3. Re-run platform permission validation suite",
            "4. Re-run privacy boundary audit",
            "5. Coordinate cross-platform re-deploy",
        ],
        "recovery_dependencies": ["platform_validation_suite", "privacy_audit_tooling"],
        "recovery_risk_level": "high",
        "recovery_risk_reasons": ["platform-specific behavior", "user-facing permission UX", "private data surface"],
        "rollback_dependency": "patch_rollback_preview",
        "validation_dependency": "patch_validation_preview",
        "recovery_readiness": False,
        "recommended_next_action": "complete platform validation before attempting patch recovery",
        "confidence_score": 0.85,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "recovery"],
        "target_component": "preview_schema",
        "failure_type": "endpoint_smoke_failure",
        "failure_scope": "debug_preview_endpoints",
        "recovery_required": False,
        "recovery_strategy": "automated — smoke tests detect endpoint drift; rollback is immediate git revert",
        "recovery_steps": [
            "1. Smoke test failure identifies failing endpoint",
            "2. Git revert the preview change",
            "3. Re-run smoke tests to confirm recovery",
            "4. Verify fault report section shows recovery status",
        ],
        "recovery_dependencies": ["smoke_test_suite"],
        "recovery_risk_level": "low",
        "recovery_risk_reasons": ["read-only addition", "no runtime impact", "immediate revert possible"],
        "rollback_dependency": "patch_rollback_preview",
        "validation_dependency": "patch_validation_preview",
        "recovery_readiness": True,
        "recommended_next_action": "run smoke tests before merge",
        "confidence_score": 0.9,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_issue: Optional[str], command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for pid, p in RECOVERY_PROFILES.items():
        if pid in haystack or any(a.lower() in haystack for a in p.get("aliases", [])):
            return pid
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    out: List[Any] = []
    for i in items:
        if i and i not in out:
            out.append(i)
    return out


def patch_recovery_status() -> Dict[str, Any]:
    return {"layer": "28.4", "name": "Patch Recovery Preview", "status": "patch_recovery_ready",
            "read_only": True, "strict_read_only": True, "analysis_only": True, "preview_only": True,
            "real_action_performed": False,
            "file_write_enabled": False, "memory_write_enabled": False, "db_write_enabled": False,
            "git_write_enabled": False, "commit_enabled": False, "push_enabled": False,
            "deploy_enabled": False, "auto_fix_enabled": False, "patch_apply_enabled": False,
            "subprocess_execution_enabled": False, "repo_scan_performed": False,
            "chat_stream_touched": False, "typewriter_runtime_touched": False,
            "available_endpoints": [
                "/debug/patch-recovery-status",
                "/debug/patch-recovery-registry",
                "/debug/patch-recovery-preview",
            ],
            "connected_layers": [
                "28.3", "28.2", "28.1", "27.6", "27.5", "27.4",
                "27.3", "27.2", "27.1", "26.7", "26.6",
                "25.6", "25.5", "25.4",
            ],
            "safety_note": "Read-only recovery preview. No actual recovery execution."}


def patch_recovery_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in RECOVERY_PROFILES.items():
        items.append({
            "id": pid,
            "target_component": p["target_component"],
            "failure_type": p["failure_type"],
            "failure_scope": p["failure_scope"],
            "recovery_required": p["recovery_required"],
            "recovery_risk_level": p["recovery_risk_level"],
            "recovery_readiness": p["recovery_readiness"],
            "confidence_score": p["confidence_score"],
        })
    return {
        "layer": "28.4", "name": "Patch Recovery Registry", "status": "patch_recovery_registry_ready",
        "read_only": True, "strict_read_only": True, "analysis_only": True,
        "recovery_count": len(items), "recoveries": items,
        "ready_count": sum(1 for i in items if i["recovery_readiness"] is True),
        "blocked_count": sum(1 for i in items if i["recovery_readiness"] is False),
        "pending_count": sum(1 for i in items if i["recovery_readiness"] is None),
        "safety_flags": {
            "file_write": False, "memory_write": False, "db_write": False, "git_write": False,
            "commit": False, "push": False, "deploy": False, "auto_fix": False,
            "patch_apply": False, "subprocess_execution": False,
        },
    }


def build_patch_recovery_preview(
    target_issue: Optional[str] = None, command: str = "",
    project_area: Optional[str] = None, related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_profile(target_issue, command, project_area)
    p = RECOVERY_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 28.4"

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
    ) / 12, 2)

    return {
        "target_issue": detected,
        "target_component": p["target_component"],
        "failure_type": p["failure_type"],
        "failure_scope": p["failure_scope"],
        "recovery_required": p["recovery_required"],
        "recovery_strategy": p["recovery_strategy"],
        "recovery_steps": list(p["recovery_steps"]),
        "recovery_dependencies": _unique(
            list(p["recovery_dependencies"])
            + list(verification.get("required_tests", []))[:2]
        ),
        "recovery_risk_level": p["recovery_risk_level"],
        "recovery_risk_reasons": _unique(
            list(p["recovery_risk_reasons"])
            + list(risk.get("risk_reasons", []))[:2]
        ),
        "rollback_dependency": p["rollback_dependency"],
        "validation_dependency": p["validation_dependency"],
        "recovery_readiness": p["recovery_readiness"],
        "recommended_next_action": p["recommended_next_action"],
        "confidence_score": conf,
        "integration_signals": {
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
        "safety_note": "Read-only recovery preview. No actual recovery execution.",
    }
