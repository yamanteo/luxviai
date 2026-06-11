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
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


SAFE_PATCH_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "patch_plan_id": "SP-001",
        "application_ready": True,
        "application_steps": [
            "1. Identify resume_owner paths in app.py",
            "2. Consolidate duplicate owner logic into single flow",
            "3. Add guard validation at consolidation point",
            "4. Verify stop/continue endpoint behavior",
        ],
        "affected_files": ["app.py"],
        "affected_functions": ["resume_owner", "stop_flow", "continue_flow"],
        "pre_checks": ["all existing stop/continue tests pass", "no active stream during patch"],
        "post_checks": ["resume after stop via /chat", "websocket reconnect after stop", "double-stop guard"],
        "rollback_plan": "git revert the consolidation commit; re-run smoke tests",
        "approval_required": True,
        "verification_required": True,
        "risk_level": "medium",
        "confidence_score": 0.87,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "patch_plan_id": "SP-002",
        "application_ready": False,
        "application_steps": [
            "1. Map stream event ownership in app.py",
            "2. Draft typewriter guard placement",
            "3. Define manual tab regression scope",
            "4. Apply staged merge with canary",
        ],
        "affected_files": ["app.py", "static/index.html"],
        "affected_functions": ["ws_chat", "typewriter_queue", "stream_delta", "stream_done"],
        "pre_checks": ["manual tab switch regression completed", "typewriter state audit done"],
        "post_checks": ["manual tab switch", "long answer stream", "stop during stream", "done after disconnect"],
        "rollback_plan": "git revert + full stream regression re-run; canary rollback first",
        "approval_required": True,
        "verification_required": True,
        "risk_level": "high",
        "confidence_score": 0.83,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "patch_plan_id": "SP-003",
        "application_ready": True,
        "application_steps": [
            "1. Locate export preview schema in workspace_export_preview.py",
            "2. Add write guard assertion",
            "3. Add preview validation",
            "4. Verify export preview endpoint",
        ],
        "affected_files": ["workspace_export_preview.py", "app.py"],
        "affected_functions": ["build_workspace_export_preview", "export_preview_endpoint"],
        "pre_checks": ["export format validation suite passes", "write guard not yet active"],
        "post_checks": ["export format validation", "write guard assertion active"],
        "rollback_plan": "git revert single commit — low risk",
        "approval_required": False,
        "verification_required": True,
        "risk_level": "low",
        "confidence_score": 0.86,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "patch_plan_id": "SP-004",
        "application_ready": False,
        "application_steps": [
            "1. Review protected data surface",
            "2. Draft confirmation boundary",
            "3. Add false real-access guard",
            "4. Validate Android + iOS permission flows",
        ],
        "affected_files": ["luxway_permission_model.py", "luxway_device_safety.py", "app.py"],
        "affected_functions": ["preview_luxway_permission", "preview_luxway_device_safety"],
        "pre_checks": ["Android platform test results", "iOS platform test results", "private data boundary audit"],
        "post_checks": ["Android permission flow", "iOS permission flow", "private data guard active"],
        "rollback_plan": "git revert + platform re-validation; staged merge with canary",
        "approval_required": True,
        "verification_required": True,
        "risk_level": "high",
        "confidence_score": 0.85,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "investigation", "planner", "patch", "draft", "change", "diff", "risk", "approval", "execution", "safe", "apply"],
        "target_component": "preview_schema",
        "patch_plan_id": "SP-005",
        "application_ready": True,
        "application_steps": [
            "1. Add safe patch preview schema",
            "2. Connect debug endpoints",
            "3. Surface fault report section",
            "4. Smoke test all endpoints",
        ],
        "affected_files": ["safe_patch_application_preview.py", "app.py", "lux_fault_report.py", "scripts/smoke_check.py"],
        "affected_functions": ["safe_patch_status", "build_safe_patch_preview"],
        "pre_checks": ["all existing smoke tests pass", "no active patches in flight"],
        "post_checks": ["status endpoint smoke", "registry smoke", "preview response shape"],
        "rollback_plan": "git revert — read-only scaffold, no runtime impact",
        "approval_required": False,
        "verification_required": False,
        "risk_level": "low",
        "confidence_score": 0.9,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_issue: Optional[str], command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for profile_id, profile in SAFE_PATCH_PROFILES.items():
        if profile_id in haystack or any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def safe_patch_status() -> Dict[str, Any]:
    return {
        "layer": "28.1",
        "name": "Safe Patch Application Preview",
        "status": "safe_patch_application_ready",
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
            "/debug/safe-patch-status",
            "/debug/safe-patch-registry",
            "/debug/safe-patch-preview",
        ],
        "connected_layers": [
            "27.1 Patch Draft Engine",
            "27.2 Change Preview Engine",
            "27.3 Diff Preview Engine",
            "27.4 Patch Risk Matrix",
            "27.5 Patch Approval Engine",
            "27.6 Patch Execution Readiness",
            "26.7 Multi-Agent Coordinator",
            "26.6 Evidence Store",
            "25.6 Verification Planner",
            "25.5 Safe Patch Planner",
            "25.4 Safe Change Boundary",
        ],
        "safety_note": "Safe Patch Application Preview only describes how a patch would be applied. It never writes files, executes subprocesses, applies actual patches, commits, pushes, or deploys.",
    }


def safe_patch_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for profile_id, profile in SAFE_PATCH_PROFILES.items():
        boundary = build_change_boundary_preview(target_area=profile_id, command=profile_id, related_layer="Layer 28.1")
        items.append(
            {
                "id": profile_id,
                "target_component": profile["target_component"],
                "patch_plan_id": profile["patch_plan_id"],
                "application_ready": profile["application_ready"],
                "application_steps": list(profile["application_steps"]),
                "affected_files": list(profile["affected_files"]),
                "affected_functions": list(profile["affected_functions"]),
                "risk_level": profile["risk_level"],
                "approval_required": profile["approval_required"],
                "confidence_score": profile["confidence_score"],
            }
        )

    return {
        "layer": "28.1",
        "name": "Safe Patch Application Registry",
        "status": "safe_patch_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "patch_count": len(items),
        "patches": items,
        "ready_count": sum(1 for item in items if item["application_ready"]),
        "blocked_count": sum(1 for item in items if not item["application_ready"]),
        "connected_endpoints": [
            "/debug/patch-draft-preview",
            "/debug/change-preview",
            "/debug/diff-preview",
            "/debug/patch-risk-preview",
            "/debug/patch-approval-preview",
            "/debug/patch-execution-preview",
            "/debug/coordinator-preview",
            "/debug/evidence-store-preview",
            "/debug/verification-planner-preview",
            "/debug/patch-planner-preview",
            "/debug/change-boundary-preview",
            "/debug/fault-report-preview",
        ],
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
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_safe_patch_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(target_issue, command, project_area)
    profile = SAFE_PATCH_PROFILES[profile_id]
    detected_issue = target_issue or project_area or profile_id
    command_or_issue = command or detected_issue

    patch_draft = build_patch_draft_preview(
        target_issue=detected_issue, command=command_or_issue,
        project_area=project_area or detected_issue, related_layer=related_layer or "Layer 28.1",
    )
    change_preview = build_change_preview(
        target_issue=detected_issue, command=command_or_issue,
        project_area=project_area or detected_issue, related_layer=related_layer or "Layer 28.1",
    )
    diff_preview = build_diff_preview(
        target_issue=detected_issue, command=command_or_issue,
        project_area=project_area or detected_issue, related_layer=related_layer or "Layer 28.1",
    )
    risk_matrix = build_patch_risk_preview(
        target_issue=detected_issue, command=command_or_issue,
        project_area=project_area or detected_issue, related_layer=related_layer or "Layer 28.1",
    )
    approval = build_patch_approval_preview(
        target_issue=detected_issue, command=command_or_issue,
        project_area=project_area or detected_issue, related_layer=related_layer or "Layer 28.1",
    )
    execution = build_patch_execution_preview(
        target_issue=detected_issue, command=command_or_issue,
        project_area=project_area or detected_issue, related_layer=related_layer or "Layer 28.1",
    )
    coordinator = build_coordinator_preview(
        command=command_or_issue, project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 28.1",
    )
    evidence = build_evidence_store_preview(
        finding=None, command=command_or_issue,
        project_area=project_area or detected_issue, related_layer=related_layer or "Layer 28.1",
    )
    verification_planner = build_verification_planner_preview(
        target_issue=detected_issue, command=command_or_issue,
        related_layer=related_layer or "Layer 28.1",
    )
    patch_planner = build_patch_planner_preview(
        target_issue=detected_issue, command=command_or_issue,
        related_layer=related_layer or "Layer 28.1",
    )
    boundary = build_change_boundary_preview(
        target_area=detected_issue, command=command_or_issue,
        related_layer=related_layer or "Layer 28.1",
    )

    confidence_score = round(
        (float(profile["confidence_score"]) + float(patch_draft.get("confidence_score", 0.0))
         + float(change_preview.get("confidence_score", 0.0)) + float(diff_preview.get("confidence_score", 0.0))
         + float(risk_matrix.get("confidence_score", 0.0)) + float(approval.get("confidence_score", 0.0))
         + float(execution.get("confidence_score", 0.0)) + float(coordinator.get("overall_confidence", 0.0))
         + float(evidence.get("confidence_score", 0.0))) / 9, 2)

    return {
        "target_issue": detected_issue,
        "target_component": profile["target_component"],
        "patch_plan_id": profile["patch_plan_id"],
        "application_ready": profile["application_ready"],
        "application_steps": list(profile["application_steps"]),
        "affected_files": _unique(list(profile["affected_files"]) + list(patch_draft.get("recommended_files", []))[:2]),
        "affected_functions": list(profile["affected_functions"]),
        "pre_checks": _unique(list(profile["pre_checks"]) + list(verification_planner.get("required_tests", []))[:2]),
        "post_checks": _unique(list(profile["post_checks"]) + list(verification_planner.get("recommended_validation_steps", []))[:2]),
        "rollback_plan": profile["rollback_plan"],
        "approval_required": profile["approval_required"] or approval.get("approval_required"),
        "verification_required": profile["verification_required"],
        "risk_level": profile["risk_level"],
        "confidence_score": confidence_score,
        "integration_signals": {
            "patch_draft": {"recommended_files": patch_draft.get("recommended_files", []), "draft_change_summary": patch_draft.get("draft_change_summary")},
            "change_preview": {"before_summary": change_preview.get("before_summary"), "after_summary": change_preview.get("after_summary")},
            "diff_preview": {"affected_files": diff_preview.get("affected_files", []), "diff_hunks_expected": diff_preview.get("diff_hunks_expected")},
            "patch_risk_matrix": {"risk_score": risk_matrix.get("risk_score"), "risk_level": risk_matrix.get("risk_level")},
            "patch_approval": {"approval_required": approval.get("approval_required"), "blocked_by_boundary": approval.get("blocked_by_boundary")},
            "patch_execution_readiness": {"execution_ready": execution.get("execution_ready"), "go_no_go_status": execution.get("go_no_go_status")},
            "multi_agent_coordinator": {"combined_findings": coordinator.get("combined_findings", []), "overall_confidence": coordinator.get("overall_confidence")},
            "evidence_store": {"finding": evidence.get("finding"), "risk_reasoning": evidence.get("risk_reasoning")},
            "verification_planner": {"required_tests": verification_planner.get("required_tests", [])},
            "safe_patch_planner": {"estimated_complexity": patch_planner.get("estimated_complexity")},
            "safe_change_boundary": {"allowed_actions": boundary.get("allowed_actions", []), "blocked_actions": boundary.get("blocked_actions", [])},
        },
        "read_only": True, "strict_read_only": True, "analysis_only": True, "preview_only": True,
        "real_action_performed": False,
        "file_write_performed": False, "memory_write_performed": False, "db_write_performed": False,
        "git_write_performed": False, "commit_performed": False, "push_performed": False,
        "deploy_performed": False, "auto_fix_performed": False, "patch_apply_performed": False,
        "subprocess_execution_performed": False, "repo_scan_performed": False,
        "chat_stream_touched": False, "typewriter_runtime_touched": False,
        "safety_note": "This is only a read-only safe patch application preview. It does not write files, execute subprocesses, apply actual patches, commit, push, or deploy.",
    }
