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
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


AUDIT_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "timeline_events": [
            "2026-06-01: Patch drafted — resume_flow consolidation",
            "2026-06-02: Change preview reviewed — 3 affected functions",
            "2026-06-03: Diff preview — 2 hunks in app.py",
            "2026-06-04: Risk assessment — medium, single-commit revert",
            "2026-06-05: Approval granted — safe to apply",
            "2026-06-06: Execution readiness — confirmed, smoke tests pass",
            "2026-06-07: Validation — incremental tests pass",
            "2026-06-08: Rollback — not required",
            "2026-06-09: Recovery — not required",
        ],
        "approval_events": ["2026-06-05: Auto-approved — risk_level=medium, rollback_plan=git revert"],
        "risk_events": ["2026-06-04: risk_level=medium — runtime flow change, chat state mutation"],
        "validation_events": [
            "2026-06-07: validation_status=pending — unit/integration tests queued",
        ],
        "rollback_events": ["2026-06-08: rollback_required=False — no rollback triggered"],
        "recovery_events": ["2026-06-09: recovery_required=False — no recovery action needed"],
        "affected_layers": [
            "28.5", "28.4", "28.3", "28.2", "28.1",
            "27.6", "27.5", "27.4", "27.3", "27.2", "27.1",
            "26.7", "26.6", "25.6", "25.5", "25.4",
        ],
        "affected_files": ["app.py"],
        "affected_endpoints": [
            "/chat", "/ws/chat", "/debug/patch-*",
        ],
        "decision_chain": [
            "draft -> change_preview -> diff_preview -> risk_matrix",
            "-> approval -> execution_readiness -> safe_patch_application",
            "-> validation -> rollback -> recovery -> audit_trail",
        ],
        "audit_completeness": "comprehensive",
        "audit_readiness": True,
        "recommended_next_action": "monitor post-merge; no gaps in audit trail",
        "confidence_score": 0.87,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "timeline_events": [
            "2026-06-01: Patch drafted — stream flow ownership refactor",
            "2026-06-02: Change preview — 5 affected functions, high risk",
            "2026-06-03: Diff preview — 4 hunks across app.py + index.html",
            "2026-06-04: Risk assessment — high, multi-hunk blast radius",
            "2026-06-05: Approval — blocked, boundary conditions not met",
            "2026-06-06: Execution readiness — not ready, canary missing",
            "2026-06-07: Validation — blocked, manual regression required",
            "2026-06-08: Rollback — mandatory, canary-first strategy",
            "2026-06-09: Recovery — required, canary-first rollback planned",
        ],
        "approval_events": [
            "2026-06-05: Blocked — safe_change_boundary detected unresolved conflicts",
        ],
        "risk_events": ["2026-06-04: risk_level=high — websocket state, typewriter runtime, large blast radius"],
        "validation_events": [
            "2026-06-07: validation_status=blocked — manual regression suite required",
        ],
        "rollback_events": ["2026-06-08: rollback_required=True — mandatory, canary-first"],
        "recovery_events": ["2026-06-09: recovery_required=True — canary-first rollback planned"],
        "affected_layers": [
            "28.5", "28.4", "28.3", "28.2", "28.1",
            "27.6", "27.5", "27.4", "27.3", "27.2", "27.1",
            "26.7", "26.6", "25.6", "25.5", "25.4",
        ],
        "affected_files": ["app.py", "static/index.html"],
        "affected_endpoints": [
            "/ws/chat", "/chat", "/debug/patch-*",
        ],
        "decision_chain": [
            "draft -> change_preview -> diff_preview -> risk_matrix",
            "-> approval [BLOCKED] -> execution_readiness [NOT_READY]",
            "-> validation [BLOCKED] -> rollback [MANDATORY] -> recovery [REQUIRED]",
            "-> audit_trail [ALL_EVENTS_CAPTURED]",
        ],
        "audit_completeness": "comprehensive — all stages captured despite blocks",
        "audit_readiness": True,
        "recommended_next_action": "resolve boundary blocks before stream patch; audit trail is complete",
        "confidence_score": 0.83,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "timeline_events": [
            "2026-06-01: Patch drafted — export format pipeline",
            "2026-06-02: Change preview — low risk, preview-only",
            "2026-06-03: Diff preview — 1 hunk, schema change",
            "2026-06-04: Risk assessment — low, no production export",
            "2026-06-05: Approval — auto-approved",
            "2026-06-06: Execution readiness — ready",
            "2026-06-07: Validation — ready, automated suite passes",
            "2026-06-08: Rollback — not required",
            "2026-06-09: Recovery — not required",
        ],
        "approval_events": ["2026-06-05: Auto-approved — risk_level=low, preview-only"],
        "risk_events": ["2026-06-04: risk_level=low — preview-only, no production impact"],
        "validation_events": ["2026-06-07: validation_status=ready — export format validation suite passes"],
        "rollback_events": ["2026-06-08: rollback_required=False"],
        "recovery_events": ["2026-06-09: recovery_required=False"],
        "affected_layers": [
            "28.5", "28.4", "28.3", "28.2", "28.1",
            "27.6", "27.5", "27.4", "27.3", "27.2", "27.1",
            "26.7", "26.6", "25.6", "25.5", "25.4",
        ],
        "affected_files": ["workspace_export_preview.py"],
        "affected_endpoints": ["/workspace/export-preview", "/debug/patch-*"],
        "decision_chain": [
            "draft -> change_preview -> diff_preview -> risk_matrix",
            "-> approval -> execution_readiness -> safe_patch_application",
            "-> validation -> rollback -> recovery -> audit_trail",
        ],
        "audit_completeness": "comprehensive",
        "audit_readiness": True,
        "recommended_next_action": "run export validation suite before merge; trail is complete",
        "confidence_score": 0.86,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "timeline_events": [
            "2026-06-01: Patch drafted — platform permission flow",
            "2026-06-02: Change preview — Android + iOS permission paths",
            "2026-06-03: Diff preview — 3 hunks, platform-specific",
            "2026-06-04: Risk assessment — high, user-facing UX",
            "2026-06-05: Approval — blocked, platform validation missing",
            "2026-06-06: Execution readiness — not ready",
            "2026-06-07: Validation — blocked, platform test suite required",
            "2026-06-08: Rollback — mandatory, platform-specific",
            "2026-06-09: Recovery — required, platform-specific recovery",
        ],
        "approval_events": [
            "2026-06-05: Blocked — platform validation suite not configured",
        ],
        "risk_events": ["2026-06-04: risk_level=high — platform-specific, private data, user-facing UX"],
        "validation_events": [
            "2026-06-07: validation_status=blocked — platform test tooling required",
        ],
        "rollback_events": ["2026-06-08: rollback_required=True — platform-specific revert"],
        "recovery_events": ["2026-06-09: recovery_required=True — platform-specific recovery"],
        "affected_layers": [
            "28.5", "28.4", "28.3", "28.2", "28.1",
            "27.6", "27.5", "27.4", "27.3", "27.2", "27.1",
            "26.7", "26.6", "25.6", "25.5", "25.4",
        ],
        "affected_files": ["luxway_permission_model.py", "permission_boundary.py"],
        "affected_endpoints": [
            "/luxway/permission-model", "/luxway/permission-preview", "/debug/patch-*",
        ],
        "decision_chain": [
            "draft -> change_preview -> diff_preview -> risk_matrix",
            "-> approval [BLOCKED] -> execution_readiness [NOT_READY]",
            "-> validation [BLOCKED] -> rollback [MANDATORY] -> recovery [REQUIRED]",
            "-> audit_trail [ALL_EVENTS_CAPTURED]",
        ],
        "audit_completeness": "comprehensive — all stages captured despite blocks",
        "audit_readiness": True,
        "recommended_next_action": "set up platform validation tooling; audit trail is ready",
        "confidence_score": 0.85,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "audit"],
        "target_component": "preview_schema",
        "timeline_events": [
            "2026-06-01: Patch drafted — preview schema scaffold",
            "2026-06-02: Change preview — read-only schema, no risk",
            "2026-06-03: Diff preview — 1 hunk, new endpoints",
            "2026-06-04: Risk assessment — low, read-only",
            "2026-06-05: Approval — auto-approved",
            "2026-06-06: Execution readiness — ready",
            "2026-06-07: Validation — ready, smoke tests pass",
            "2026-06-08: Rollback — not required",
            "2026-06-09: Recovery — not required",
        ],
        "approval_events": ["2026-06-05: Auto-approved — read-only scaffold, no runtime impact"],
        "risk_events": ["2026-06-04: risk_level=low — read-only addition, no runtime impact"],
        "validation_events": ["2026-06-07: validation_status=ready — smoke tests cover all endpoints"],
        "rollback_events": ["2026-06-08: rollback_required=False"],
        "recovery_events": ["2026-06-09: recovery_required=False"],
        "affected_layers": [
            "28.5", "28.4", "28.3", "28.2", "28.1",
            "27.6", "27.5", "27.4", "27.3", "27.2", "27.1",
            "26.7", "26.6", "25.6", "25.5", "25.4",
        ],
        "affected_files": ["patch_audit_trail_preview.py"],
        "affected_endpoints": [
            "/debug/patch-audit-status", "/debug/patch-audit-registry",
            "/debug/patch-audit-preview", "/debug/fault-report-preview",
        ],
        "decision_chain": [
            "draft -> change_preview -> diff_preview -> risk_matrix",
            "-> approval -> execution_readiness -> safe_patch_application",
            "-> validation -> rollback -> recovery -> audit_trail",
        ],
        "audit_completeness": "comprehensive",
        "audit_readiness": True,
        "recommended_next_action": "run smoke tests before merge; audit trail is complete",
        "confidence_score": 0.9,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_issue: Optional[str], command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for pid, p in AUDIT_PROFILES.items():
        if pid in haystack or any(a.lower() in haystack for a in p.get("aliases", [])):
            return pid
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    out: List[Any] = []
    for i in items:
        if i and i not in out:
            out.append(i)
    return out


def patch_audit_status() -> Dict[str, Any]:
    return {"layer": "28.5", "name": "Patch Audit Trail Preview", "status": "patch_audit_ready",
            "read_only": True, "strict_read_only": True, "analysis_only": True, "preview_only": True,
            "real_action_performed": False,
            "file_write_enabled": False, "memory_write_enabled": False, "db_write_enabled": False,
            "git_write_enabled": False, "commit_enabled": False, "push_enabled": False,
            "deploy_enabled": False, "auto_fix_enabled": False, "patch_apply_enabled": False,
            "subprocess_execution_enabled": False, "repo_scan_performed": False,
            "chat_stream_touched": False, "typewriter_runtime_touched": False,
            "available_endpoints": [
                "/debug/patch-audit-status",
                "/debug/patch-audit-registry",
                "/debug/patch-audit-preview",
            ],
            "connected_layers": [
                "28.4", "28.3", "28.2", "28.1",
                "27.6", "27.5", "27.4", "27.3", "27.2", "27.1",
                "26.7", "26.6", "25.6", "25.5", "25.4",
            ],
            "safety_note": "Read-only audit trail preview. No actual audit logging."}


def patch_audit_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in AUDIT_PROFILES.items():
        items.append({
            "id": pid,
            "target_component": p["target_component"],
            "audit_completeness": p["audit_completeness"],
            "audit_readiness": p["audit_readiness"],
            "confidence_score": p["confidence_score"],
            "event_count": (
                len(p.get("timeline_events", []))
                + len(p.get("approval_events", []))
                + len(p.get("risk_events", []))
                + len(p.get("validation_events", []))
                + len(p.get("rollback_events", []))
                + len(p.get("recovery_events", []))
            ),
        })
    return {
        "layer": "28.5", "name": "Patch Audit Registry", "status": "patch_audit_registry_ready",
        "read_only": True, "strict_read_only": True, "analysis_only": True,
        "audit_count": len(items), "audits": items,
        "ready_count": sum(1 for i in items if i["audit_readiness"] is True),
        "blocked_count": sum(1 for i in items if i["audit_readiness"] is False),
        "pending_count": sum(1 for i in items if i["audit_readiness"] is None),
        "safety_flags": {
            "file_write": False, "memory_write": False, "db_write": False, "git_write": False,
            "commit": False, "push": False, "deploy": False, "auto_fix": False,
            "patch_apply": False, "subprocess_execution": False,
        },
    }


def build_patch_audit_preview(
    target_issue: Optional[str] = None, command: str = "",
    project_area: Optional[str] = None, related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_profile(target_issue, command, project_area)
    p = AUDIT_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 28.5"

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
    ) / 13, 2)

    return {
        "audit_id": pid,
        "target_issue": detected,
        "target_component": p["target_component"],
        "timeline_events": list(p["timeline_events"]),
        "approval_events": list(p["approval_events"]),
        "risk_events": list(p["risk_events"]),
        "validation_events": list(p["validation_events"]),
        "rollback_events": list(p["rollback_events"]),
        "recovery_events": list(p["recovery_events"]),
        "affected_layers": list(p["affected_layers"]),
        "affected_files": _unique(
            list(p["affected_files"])
            + list(diff.get("affected_files", []))[:2]
        ),
        "affected_endpoints": list(p["affected_endpoints"]),
        "decision_chain": list(p["decision_chain"]),
        "audit_completeness": p["audit_completeness"],
        "audit_readiness": p["audit_readiness"],
        "recommended_next_action": p["recommended_next_action"],
        "confidence_score": conf,
        "integration_signals": {
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
        "safety_note": "Read-only audit trail preview. No actual audit logging.",
    }
