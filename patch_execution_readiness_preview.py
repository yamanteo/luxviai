from __future__ import annotations

from typing import Any, Dict, List, Optional

from evidence_store_preview import build_evidence_store_preview
from multi_agent_coordinator_preview import build_coordinator_preview
from patch_draft_engine_preview import build_patch_draft_preview, patch_draft_registry
from change_preview_engine_preview import build_change_preview, change_preview_registry
from diff_preview_engine_preview import build_diff_preview, diff_preview_registry
from patch_risk_matrix_preview import build_patch_risk_preview, patch_risk_registry
from patch_approval_engine_preview import build_patch_approval_preview, patch_approval_registry
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


PATCH_EXECUTION_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "execution_ready": True,
        "readiness_score": 78,
        "go_no_go_status": "go",
        "blockers": [],
        "blocking_reasons": [],
        "missing_requirements": [],
        "required_approvals": ["dev_review"],
        "required_validations": ["resume after stop", "websocket reconnect after stop", "double-stop guard"],
        "required_tests": ["unit: resume flow", "integration: stop/continue via chat"],
        "verification_ready": True,
        "rollback_required": False,
        "rollback_strategy": "git revert single commit — low risk",
        "execution_path": "apply_patch → smoke_test → merge",
        "recommended_next_action": "proceed with resume_flow consolidation",
        "confidence_score": 0.87,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "execution_ready": False,
        "readiness_score": 22,
        "go_no_go_status": "no_go",
        "blockers": ["chat_stream boundary", "typewriter_runtime boundary", "high regression_risk"],
        "blocking_reasons": ["manual tab switch regression not performed", "typewriter queue ownership unresolved", "high runtime blast radius"],
        "missing_requirements": ["manual regression sign-off", "tab boundary test results", "typewriter state audit"],
        "required_approvals": ["dev_review", "manual_regression_sign_off", "staged_merge_approval"],
        "required_validations": ["tab boundary test", "typewriter queue ownership", "done event timing"],
        "required_tests": ["manual: tab switch", "manual: long answer stream", "manual: stop during stream"],
        "verification_ready": False,
        "rollback_required": True,
        "rollback_strategy": "git revert + full stream regression re-run; staged merge with canary",
        "execution_path": "BLOCKED — resolve blockers first",
        "recommended_next_action": "complete manual regression before re-evaluating",
        "confidence_score": 0.83,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "execution_ready": True,
        "readiness_score": 85,
        "go_no_go_status": "go",
        "blockers": [],
        "blocking_reasons": [],
        "missing_requirements": [],
        "required_approvals": ["dev_review"],
        "required_validations": ["export format validation", "write guard assertion"],
        "required_tests": ["unit: export preview shape"],
        "verification_ready": True,
        "rollback_required": False,
        "rollback_strategy": "git revert single commit — low risk",
        "execution_path": "apply_patch → smoke_test → merge",
        "recommended_next_action": "proceed with export guard tightening",
        "confidence_score": 0.86,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "execution_ready": False,
        "readiness_score": 30,
        "go_no_go_status": "no_go",
        "blockers": ["private_data boundary", "platform_validation_missing"],
        "blocking_reasons": ["Android permission flow not validated", "iOS permission flow not validated", "private data guard not confirmed"],
        "missing_requirements": ["Android platform test results", "iOS platform test results", "private data boundary audit"],
        "required_approvals": ["dev_review", "platform_validation", "privacy_review"],
        "required_validations": ["Android permission flow", "iOS permission flow", "private data guard"],
        "required_tests": ["platform: Android permissions", "platform: iOS permissions", "unit: device action boundary"],
        "verification_ready": False,
        "rollback_required": True,
        "rollback_strategy": "git revert + platform re-validation; staged merge with canary",
        "execution_path": "BLOCKED — resolve blockers first",
        "recommended_next_action": "complete platform validation before re-evaluating",
        "confidence_score": 0.85,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "investigation", "planner", "patch", "draft", "change", "diff", "risk", "approval", "execution", "readiness"],
        "target_component": "preview_schema",
        "execution_ready": True,
        "readiness_score": 92,
        "go_no_go_status": "go",
        "blockers": [],
        "blocking_reasons": [],
        "missing_requirements": [],
        "required_approvals": ["smoke_test_pass"],
        "required_validations": ["status endpoint smoke", "registry smoke", "preview response shape"],
        "required_tests": ["unit: execution status", "unit: execution registry", "unit: execution preview"],
        "verification_ready": True,
        "rollback_required": False,
        "rollback_strategy": "git revert — read-only scaffold, no runtime impact",
        "execution_path": "smoke_test → merge",
        "recommended_next_action": "merge after smoke test passes",
        "confidence_score": 0.9,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_issue: Optional[str], command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for profile_id, profile in PATCH_EXECUTION_PROFILES.items():
        if profile_id in haystack or any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def patch_execution_status() -> Dict[str, Any]:
    return {
        "layer": "27.6",
        "name": "Patch Execution Readiness Preview",
        "status": "patch_execution_readiness_ready",
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
            "/debug/patch-execution-status",
            "/debug/patch-execution-registry",
            "/debug/patch-execution-preview",
        ],
        "connected_layers": [
            "27.1 Patch Draft Engine",
            "27.2 Change Preview Engine",
            "27.3 Diff Preview Engine",
            "27.4 Patch Risk Matrix",
            "27.5 Patch Approval Engine",
            "26.7 Multi-Agent Coordinator",
            "26.6 Evidence Store",
            "25.6 Verification Planner",
            "25.5 Safe Patch Planner",
            "25.4 Safe Change Boundary",
        ],
        "safety_note": "Patch Execution Readiness only evaluates readiness. It never writes files, stores memory, applies patches, runs subprocesses, commits, pushes, deploys, or changes runtime behavior.",
    }


def patch_execution_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for profile_id, profile in PATCH_EXECUTION_PROFILES.items():
        boundary = build_change_boundary_preview(target_area=profile_id, command=profile_id, related_layer="Layer 27.6")
        items.append(
            {
                "id": profile_id,
                "target_component": profile["target_component"],
                "execution_ready": profile["execution_ready"],
                "readiness_score": profile["readiness_score"],
                "go_no_go_status": profile["go_no_go_status"],
                "blockers": list(profile["blockers"]),
                "blocking_reasons": list(profile["blocking_reasons"]),
                "missing_requirements": list(profile["missing_requirements"]),
                "required_approvals": list(profile["required_approvals"]),
                "verification_ready": profile["verification_ready"],
                "rollback_required": profile["rollback_required"],
                "confidence_score": profile["confidence_score"],
            }
        )

    return {
        "layer": "27.6",
        "name": "Patch Execution Readiness Registry",
        "status": "patch_execution_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "execution_count": len(items),
        "executions": items,
        "go_no_go_summary": {
            "go": sum(1 for item in items if item["go_no_go_status"] == "go"),
            "no_go": sum(1 for item in items if item["go_no_go_status"] == "no_go"),
        },
        "ready_count": sum(1 for item in items if item["execution_ready"]),
        "blocked_count": sum(1 for item in items if len(item["blockers"]) > 0),
        "rollback_required_count": sum(1 for item in items if item["rollback_required"]),
        "connected_endpoints": [
            "/debug/patch-draft-preview",
            "/debug/change-preview",
            "/debug/diff-preview",
            "/debug/patch-risk-preview",
            "/debug/patch-approval-preview",
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


def build_patch_execution_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(target_issue, command, project_area)
    profile = PATCH_EXECUTION_PROFILES[profile_id]
    detected_issue = target_issue or project_area or profile_id
    command_or_issue = command or detected_issue

    patch_draft = build_patch_draft_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.6",
    )
    change_preview = build_change_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.6",
    )
    diff_preview = build_diff_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.6",
    )
    risk_matrix = build_patch_risk_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.6",
    )
    approval = build_patch_approval_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.6",
    )
    coordinator = build_coordinator_preview(
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.6",
    )
    evidence = build_evidence_store_preview(
        finding=None,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.6",
    )
    verification_planner = build_verification_planner_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        related_layer=related_layer or "Layer 27.6",
    )
    patch_planner = build_patch_planner_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        related_layer=related_layer or "Layer 27.6",
    )
    boundary = build_change_boundary_preview(
        target_area=detected_issue,
        command=command_or_issue,
        related_layer=related_layer or "Layer 27.6",
    )

    confidence_score = round(
        (
            float(profile["confidence_score"])
            + float(patch_draft.get("confidence_score", 0.0))
            + float(change_preview.get("confidence_score", 0.0))
            + float(diff_preview.get("confidence_score", 0.0))
            + float(risk_matrix.get("confidence_score", 0.0))
            + float(approval.get("confidence_score", 0.0))
            + float(coordinator.get("overall_confidence", 0.0))
            + float(evidence.get("confidence_score", 0.0))
        )
        / 8,
        2,
    )

    return {
        "target_issue": detected_issue,
        "target_component": profile["target_component"],
        "execution_ready": profile["execution_ready"],
        "readiness_score": profile["readiness_score"],
        "go_no_go_status": profile["go_no_go_status"],
        "blockers": _unique(
            list(profile["blockers"])
            + list(approval.get("blocked_reasons", []))[:2]
        ),
        "blocking_reasons": _unique(
            list(profile["blocking_reasons"])
            + list(approval.get("blocked_reasons", []))[:2]
        ),
        "missing_requirements": _unique(
            list(profile["missing_requirements"])
            + [str(item) for item in risk_matrix.get("risk_reasons", []) if "missing" in str(item).lower() or "not" in str(item).lower()][:2]
        ),
        "required_approvals": _unique(
            list(profile["required_approvals"])
            + ([approval.get("recommended_approval_path", "")] if approval.get("approval_required") else [])
        ),
        "required_validations": _unique(
            list(profile["required_validations"])
            + list(verification_planner.get("recommended_validation_steps", []))[:2]
        ),
        "required_tests": _unique(
            list(profile["required_tests"])
            + list(verification_planner.get("required_tests", []))[:2]
            + list(patch_planner.get("required_tests", []))[:2]
        ),
        "verification_ready": profile["verification_ready"],
        "rollback_required": profile["rollback_required"],
        "rollback_strategy": profile["rollback_strategy"],
        "execution_path": profile["execution_path"],
        "recommended_next_action": profile["recommended_next_action"],
        "confidence_score": confidence_score,
        "integration_signals": {
            "patch_draft": {
                "recommended_files": patch_draft.get("recommended_files", []),
                "draft_change_summary": patch_draft.get("draft_change_summary"),
                "risk_assessment": patch_draft.get("risk_assessment"),
            },
            "change_preview": {
                "affected_areas": change_preview.get("affected_areas", []),
                "before_summary": change_preview.get("before_summary"),
                "after_summary": change_preview.get("after_summary"),
            },
            "diff_preview": {
                "affected_files": diff_preview.get("affected_files", []),
                "diff_hunks_expected": diff_preview.get("diff_hunks_expected"),
            },
            "patch_risk_matrix": {
                "risk_score": risk_matrix.get("risk_score"),
                "risk_level": risk_matrix.get("risk_level"),
                "risk_reasons": risk_matrix.get("risk_reasons", []),
                "dependency_risk": risk_matrix.get("dependency_risk"),
                "runtime_risk": risk_matrix.get("runtime_risk"),
            },
            "patch_approval": {
                "approval_required": approval.get("approval_required"),
                "approval_level": approval.get("approval_level"),
                "blocked_by_boundary": approval.get("blocked_by_boundary"),
                "safe_to_continue": approval.get("safe_to_continue"),
            },
            "multi_agent_coordinator": {
                "combined_findings": coordinator.get("combined_findings", []),
                "combined_risks": coordinator.get("combined_risks", []),
                "overall_confidence": coordinator.get("overall_confidence"),
            },
            "evidence_store": {
                "finding": evidence.get("finding"),
                "evidence_items": evidence.get("evidence_items", []),
                "risk_reasoning": evidence.get("risk_reasoning"),
            },
            "verification_planner": {
                "required_tests": verification_planner.get("required_tests", []),
                "verification_approach": verification_planner.get("verification_approach"),
            },
            "safe_patch_planner": {
                "recommended_change_areas": patch_planner.get("recommended_change_areas", []),
                "estimated_complexity": patch_planner.get("estimated_complexity"),
            },
            "safe_change_boundary": {
                "boundary_level": boundary.get("boundary_level"),
                "allowed_actions": boundary.get("allowed_actions", []),
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
        "safety_note": "This is only a read-only execution readiness assessment. It does not write files, execute subprocesses, apply patches, commit, push, deploy, or modify chat/stream/websocket/typewriter behavior.",
    }
