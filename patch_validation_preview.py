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
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


VALIDATION_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "validation_required": True, "validation_status": "pending",
        "validation_strategy": "incremental — validate after each consolidation step",
        "validation_steps": ["unit-test resume_owner", "integration-test stop/continue", "e2e websocket reconnect"],
        "validation_scope": ["resume_flow", "stop_flow", "continue_flow"],
        "validation_dependencies": ["smoke_test_suite"],
        "validation_risk_level": "medium", "validation_risk_reasons": ["runtime flow change", "chat state mutation"],
        "required_checks": ["all existing stop/continue tests pass", "no active stream during patch"],
        "required_tests": ["unit: resume flow", "integration: stop/continue via chat"],
        "success_criteria": ["stop/continue cycle completes < 500ms", "websocket reconnect succeeds > 99%"],
        "failure_criteria": ["double-stop hang", "resume timeout > 2s", "websocket reconnect fails"],
        "rollback_trigger": "if any failure_criteria met, trigger rollback immediately",
        "recommended_next_action": "run unit and integration tests before patch application",
        "confidence_score": 0.87,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "validation_required": True, "validation_status": "blocked",
        "validation_strategy": "manual-first — full regression suite required; cannot auto-validate",
        "validation_steps": ["manual tab switch regression", "typewriter queue ownership test", "done event timing test", "full stream regression suite"],
        "validation_scope": ["tab_boundary", "typewriter_queue", "stream_events", "websocket_runtime"],
        "validation_dependencies": ["manual_regression_suite", "canary_deployment"],
        "validation_risk_level": "high", "validation_risk_reasons": ["high blast radius", "manual steps required", "no automated coverage for tab edge cases"],
        "required_checks": ["manual tab switch regression completed", "typewriter state audit done", "canary deployment passes"],
        "required_tests": ["manual: tab switch", "manual: long answer stream", "manual: stop during stream", "manual: done after disconnect"],
        "success_criteria": ["all manual regression steps pass", "canary health check > 99.9%", "no stream errors in 24h canary"],
        "failure_criteria": ["any tab switch regression", "typewriter queue stall", "done event missing", "stream data loss"],
        "rollback_trigger": "rollback immediately on any stream regression in canary",
        "recommended_next_action": "complete manual regression before any validation attempt",
        "confidence_score": 0.83,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "validation_required": True, "validation_status": "ready",
        "validation_strategy": "automated — export validation suite covers all edge cases",
        "validation_steps": ["run export format validation suite", "verify write guard assertion active", "check export preview shape"],
        "validation_scope": ["export_preview", "write_guard"],
        "validation_dependencies": ["smoke_test_suite"],
        "validation_risk_level": "low", "validation_risk_reasons": ["preview-only", "no production export"],
        "required_checks": ["export format validation suite passes"],
        "required_tests": ["unit: export preview shape"],
        "success_criteria": ["all format validations pass", "write guard assertion active"],
        "failure_criteria": ["export schema mismatch", "write guard missing"],
        "rollback_trigger": "revert if write guard breaks existing preview behavior",
        "recommended_next_action": "run export validation suite before merge",
        "confidence_score": 0.86,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "validation_required": True, "validation_status": "blocked",
        "validation_strategy": "platform-specific — validate independently on Android and iOS",
        "validation_steps": ["run Android permission flow validation", "run iOS permission flow validation", "verify private data guard", "privacy boundary audit"],
        "validation_scope": ["android_permissions", "ios_permissions", "private_data_boundary"],
        "validation_dependencies": ["platform_validation_suite", "privacy_audit_tooling"],
        "validation_risk_level": "high", "validation_risk_reasons": ["platform-specific behavior", "user-facing permission UX", "private data surface"],
        "required_checks": ["Android platform test results", "iOS platform test results", "private data boundary audit"],
        "required_tests": ["platform: Android permissions", "platform: iOS permissions", "unit: device action boundary"],
        "success_criteria": ["Android permission flow passes all cases", "iOS permission flow passes all cases", "private data guard verified"],
        "failure_criteria": ["any platform permission regression", "private data leak detected"],
        "rollback_trigger": "rollback immediately on platform permission regression or data leak",
        "recommended_next_action": "complete platform validation before any patch attempt",
        "confidence_score": 0.85,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "validation"],
        "target_component": "preview_schema",
        "validation_required": True, "validation_status": "ready",
        "validation_strategy": "automated — smoke tests cover all endpoints",
        "validation_steps": ["smoke test status endpoint", "smoke test registry endpoint", "smoke test preview endpoint", "verify fault report section"],
        "validation_scope": ["endpoint_smoke", "fault_report_integration"],
        "validation_dependencies": ["smoke_test_suite"],
        "validation_risk_level": "low", "validation_risk_reasons": ["read-only addition", "no runtime impact"],
        "required_checks": ["all existing smoke tests pass"],
        "required_tests": ["unit: validation status", "unit: validation registry", "unit: validation preview"],
        "success_criteria": ["all smoke tests pass", "fault report section present"],
        "failure_criteria": ["any smoke test fails", "fault report section missing"],
        "rollback_trigger": "revert if smoke tests fail",
        "recommended_next_action": "run smoke tests before merge",
        "confidence_score": 0.9,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_issue: Optional[str], command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for pid, p in VALIDATION_PROFILES.items():
        if pid in haystack or any(a.lower() in haystack for a in p.get("aliases", [])):
            return pid
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    out: List[Any] = []
    for i in items:
        if i and i not in out:
            out.append(i)
    return out


def patch_validation_status() -> Dict[str, Any]:
    return {"layer": "28.3", "name": "Patch Validation Preview", "status": "patch_validation_ready",
            "read_only": True, "strict_read_only": True, "analysis_only": True, "preview_only": True,
            "real_action_performed": False,
            "file_write_enabled": False, "memory_write_enabled": False, "db_write_enabled": False,
            "git_write_enabled": False, "commit_enabled": False, "push_enabled": False,
            "deploy_enabled": False, "auto_fix_enabled": False, "patch_apply_enabled": False,
            "subprocess_execution_enabled": False, "repo_scan_performed": False,
            "chat_stream_touched": False, "typewriter_runtime_touched": False,
            "available_endpoints": ["/debug/patch-validation-status", "/debug/patch-validation-registry", "/debug/patch-validation-preview"],
            "connected_layers": ["28.2", "28.1", "27.6", "27.5", "27.4", "27.3", "27.2", "27.1", "26.7", "26.6", "25.6", "25.5", "25.4"],
            "safety_note": "Read-only validation preview. No actual validation execution."}


def patch_validation_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in VALIDATION_PROFILES.items():
        items.append({"id": pid, "target_component": p["target_component"],
                      "validation_required": p["validation_required"], "validation_status": p["validation_status"],
                      "validation_risk_level": p["validation_risk_level"], "confidence_score": p["confidence_score"]})
    return {"layer": "28.3", "name": "Patch Validation Registry", "status": "patch_validation_registry_ready",
            "read_only": True, "strict_read_only": True, "analysis_only": True,
            "validation_count": len(items), "validations": items,
            "ready_count": sum(1 for i in items if i["validation_status"] == "ready"),
            "blocked_count": sum(1 for i in items if i["validation_status"] == "blocked"),
            "pending_count": sum(1 for i in items if i["validation_status"] == "pending"),
            "safety_flags": {"file_write": False, "memory_write": False, "db_write": False, "git_write": False,
                             "commit": False, "push": False, "deploy": False, "auto_fix": False,
                             "patch_apply": False, "subprocess_execution": False}}


def build_patch_validation_preview(
    target_issue: Optional[str] = None, command: str = "",
    project_area: Optional[str] = None, related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_profile(target_issue, command, project_area)
    p = VALIDATION_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 28.3"

    safe = build_safe_patch_preview(target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    rollback = build_patch_rollback_preview(target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    execution = build_patch_execution_preview(target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    approval = build_patch_approval_preview(target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    risk = build_patch_risk_preview(target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    diff = build_diff_preview(target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    change = build_change_preview(target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    draft = build_patch_draft_preview(target_issue=detected, command=cmd, project_area=project_area or detected, related_layer=L)
    coord = build_coordinator_preview(command=cmd, project_area=project_area or detected, related_layer=L)
    ev = build_evidence_store_preview(finding=None, command=cmd, project_area=project_area or detected, related_layer=L)
    ver = build_verification_planner_preview(target_issue=detected, command=cmd, related_layer=L)
    planner = build_patch_planner_preview(target_issue=detected, command=cmd, related_layer=L)
    boundary = build_change_boundary_preview(target_area=detected, command=cmd, related_layer=L)

    conf = round((float(p["confidence_score"]) + float(safe.get("confidence_score", 0.0))
                  + float(rollback.get("confidence_score", 0.0)) + float(execution.get("confidence_score", 0.0))
                  + float(approval.get("confidence_score", 0.0)) + float(risk.get("confidence_score", 0.0))
                  + float(diff.get("confidence_score", 0.0)) + float(change.get("confidence_score", 0.0))
                  + float(draft.get("confidence_score", 0.0)) + float(coord.get("overall_confidence", 0.0))
                  + float(ev.get("confidence_score", 0.0))) / 11, 2)

    return {"target_issue": detected, "target_component": p["target_component"],
            "validation_required": p["validation_required"], "validation_status": p["validation_status"],
            "validation_strategy": p["validation_strategy"],
            "validation_steps": list(p["validation_steps"]),
            "validation_scope": list(p["validation_scope"]),
            "validation_dependencies": _unique(list(p["validation_dependencies"]) + list(ver.get("required_tests", []))[:2]),
            "validation_risk_level": p["validation_risk_level"],
            "validation_risk_reasons": _unique(list(p["validation_risk_reasons"]) + list(risk.get("risk_reasons", []))[:2]),
            "required_checks": _unique(list(p["required_checks"]) + list(ver.get("recommended_validation_steps", []))[:2]),
            "required_tests": _unique(list(p["required_tests"]) + list(ver.get("required_tests", []))[:2] + list(planner.get("required_tests", []))[:2]),
            "success_criteria": list(p["success_criteria"]),
            "failure_criteria": list(p["failure_criteria"]),
            "rollback_trigger": p["rollback_trigger"],
            "recommended_next_action": p["recommended_next_action"],
            "confidence_score": conf,
            "integration_signals": {
                "patch_rollback": {"rollback_required": rollback.get("rollback_required"), "rollback_trigger_conditions": rollback.get("rollback_trigger_conditions", [])},
                "safe_patch_application": {"application_ready": safe.get("application_ready")},
                "patch_execution_readiness": {"execution_ready": execution.get("execution_ready"), "go_no_go_status": execution.get("go_no_go_status")},
                "patch_approval": {"approval_required": approval.get("approval_required")},
                "patch_risk_matrix": {"risk_level": risk.get("risk_level"), "risk_reasons": risk.get("risk_reasons", [])},
                "diff_preview": {"affected_files": diff.get("affected_files", [])},
                "change_preview": {"risk_areas": change.get("risk_areas", [])},
                "patch_draft": {"recommended_files": draft.get("recommended_files", [])},
                "multi_agent_coordinator": {"combined_risks": coord.get("combined_risks", [])},
                "evidence_store": {"risk_reasoning": ev.get("risk_reasoning")},
                "verification_planner": {"required_tests": ver.get("required_tests", [])},
                "safe_patch_planner": {"estimated_complexity": planner.get("estimated_complexity")},
                "safe_change_boundary": {"blocked_actions": boundary.get("blocked_actions", [])},
            },
            "read_only": True, "strict_read_only": True, "analysis_only": True, "preview_only": True,
            "real_action_performed": False,
            "file_write_performed": False, "memory_write_performed": False, "db_write_performed": False,
            "git_write_performed": False, "commit_performed": False, "push_performed": False,
            "deploy_performed": False, "auto_fix_performed": False, "patch_apply_performed": False,
            "subprocess_execution_performed": False, "repo_scan_performed": False,
            "chat_stream_touched": False, "typewriter_runtime_touched": False,
            "safety_note": "Read-only validation preview. No actual validation execution."}
