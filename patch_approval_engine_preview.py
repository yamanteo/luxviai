from __future__ import annotations

from typing import Any, Dict, List, Optional

from evidence_store_preview import build_evidence_store_preview
from multi_agent_coordinator_preview import build_coordinator_preview
from patch_draft_engine_preview import build_patch_draft_preview, patch_draft_registry
from change_preview_engine_preview import build_change_preview, change_preview_registry
from diff_preview_engine_preview import build_diff_preview, diff_preview_registry
from patch_risk_matrix_preview import build_patch_risk_preview, patch_risk_registry
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


PATCH_APPROVAL_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "approval_level": "standard",
        "approval_reason": "consolidated resume_owner path with single validation point reduces runtime risk",
        "approval_source": "patch_risk_matrix",
        "human_review_required": True,
        "blocked_by_boundary": False,
        "blocked_reasons": [],
        "safe_to_continue": True,
        "recommended_next_action": "apply resume_flow consolidation to app.py with guarded validation",
        "recommended_approval_path": "dev_review → smoke_test → merge",
        "required_validations": ["resume after stop", "websocket reconnect after stop", "double-stop guard"],
        "required_tests": ["unit: resume flow", "integration: stop/continue via chat"],
        "confidence_score": 0.87,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "approval_level": "strict",
        "approval_reason": "high runtime risk — stream state drift and typewriter queue ownership changes require manual regression",
        "approval_source": "patch_risk_matrix",
        "human_review_required": True,
        "blocked_by_boundary": True,
        "blocked_reasons": ["chat_stream boundary", "typewriter_runtime boundary", "high regression_risk"],
        "safe_to_continue": False,
        "recommended_next_action": "manual tab switch regression test first; do not auto-apply",
        "recommended_approval_path": "dev_review → manual_regression → smoke_test → staged_merge",
        "required_validations": ["tab boundary test", "typewriter queue ownership", "done event timing"],
        "required_tests": ["manual: tab switch", "manual: long answer stream", "manual: stop during stream", "manual: done after disconnect"],
        "confidence_score": 0.83,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "approval_level": "low",
        "approval_reason": "low risk — export preview guard tightening only affects future real file integration",
        "approval_source": "patch_risk_matrix",
        "human_review_required": False,
        "blocked_by_boundary": False,
        "blocked_reasons": [],
        "safe_to_continue": True,
        "recommended_next_action": "apply export guard tightening to workspace_export_preview.py",
        "recommended_approval_path": "dev_review → smoke_test → merge",
        "required_validations": ["export format validation", "write guard assertion"],
        "required_tests": ["unit: export preview shape"],
        "confidence_score": 0.86,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "approval_level": "standard",
        "approval_reason": "medium risk — permission boundary explanation with private data guard needs platform-specific validation",
        "approval_source": "patch_risk_matrix",
        "human_review_required": True,
        "blocked_by_boundary": True,
        "blocked_reasons": ["private_data boundary"],
        "safe_to_continue": False,
        "recommended_next_action": "validate Android and iOS permission flows before applying",
        "recommended_approval_path": "dev_review → platform_validation → smoke_test → merge",
        "required_validations": ["Android permission flow", "iOS permission flow", "private data guard"],
        "required_tests": ["platform: Android permissions", "platform: iOS permissions", "unit: device action boundary"],
        "confidence_score": 0.85,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "investigation", "planner", "patch", "draft", "change", "diff", "risk", "approval"],
        "target_component": "preview_schema",
        "approval_level": "low",
        "approval_reason": "low risk — read-only scaffold extension with no runtime impact",
        "approval_source": "patch_risk_matrix",
        "human_review_required": False,
        "blocked_by_boundary": False,
        "blocked_reasons": [],
        "safe_to_continue": True,
        "recommended_next_action": "merge after smoke test passes",
        "recommended_approval_path": "smoke_test → merge",
        "required_validations": ["status endpoint smoke", "registry smoke", "preview response shape"],
        "required_tests": ["unit: approval status", "unit: approval registry", "unit: approval preview"],
        "confidence_score": 0.9,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_issue: Optional[str], command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for profile_id, profile in PATCH_APPROVAL_PROFILES.items():
        if profile_id in haystack or any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def patch_approval_status() -> Dict[str, Any]:
    return {
        "layer": "27.5",
        "name": "Patch Approval Engine Preview",
        "status": "patch_approval_ready",
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
            "/debug/patch-approval-status",
            "/debug/patch-approval-registry",
            "/debug/patch-approval-preview",
        ],
        "connected_layers": [
            "27.1 Patch Draft Engine",
            "27.2 Change Preview Engine",
            "27.3 Diff Preview Engine",
            "27.4 Patch Risk Matrix",
            "26.7 Multi-Agent Coordinator",
            "26.6 Evidence Store",
            "25.6 Verification Planner",
            "25.5 Safe Patch Planner",
            "25.4 Safe Change Boundary",
        ],
        "safety_note": "Patch Approval Engine only evaluates approval status. It never writes files, stores memory, applies patches, runs subprocesses, commits, pushes, deploys, or changes runtime behavior.",
    }


def patch_approval_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for profile_id, profile in PATCH_APPROVAL_PROFILES.items():
        boundary = build_change_boundary_preview(target_area=profile_id, command=profile_id, related_layer="Layer 27.5")
        items.append(
            {
                "id": profile_id,
                "target_component": profile["target_component"],
                "approval_level": profile["approval_level"],
                "approval_reason": profile["approval_reason"],
                "approval_source": profile["approval_source"],
                "human_review_required": profile["human_review_required"],
                "blocked_by_boundary": profile["blocked_by_boundary"],
                "blocked_reasons": list(profile["blocked_reasons"]),
                "safe_to_continue": profile["safe_to_continue"],
                "recommended_approval_path": profile["recommended_approval_path"],
                "confidence_score": profile["confidence_score"],
            }
        )

    return {
        "layer": "27.5",
        "name": "Patch Approval Registry",
        "status": "patch_approval_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "approval_count": len(items),
        "approvals": items,
        "approval_level_summary": {
            "strict": sum(1 for item in items if item["approval_level"] == "strict"),
            "standard": sum(1 for item in items if item["approval_level"] == "standard"),
            "low": sum(1 for item in items if item["approval_level"] == "low"),
        },
        "blocked_count": sum(1 for item in items if item["blocked_by_boundary"]),
        "human_review_count": sum(1 for item in items if item["human_review_required"]),
        "safe_to_continue_count": sum(1 for item in items if item["safe_to_continue"]),
        "connected_endpoints": [
            "/debug/patch-draft-preview",
            "/debug/change-preview",
            "/debug/diff-preview",
            "/debug/patch-risk-preview",
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


def build_patch_approval_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(target_issue, command, project_area)
    profile = PATCH_APPROVAL_PROFILES[profile_id]
    detected_issue = target_issue or project_area or profile_id
    command_or_issue = command or detected_issue

    patch_draft = build_patch_draft_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.5",
    )
    change_preview = build_change_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.5",
    )
    diff_preview = build_diff_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.5",
    )
    risk_matrix = build_patch_risk_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.5",
    )
    coordinator = build_coordinator_preview(
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.5",
    )
    evidence = build_evidence_store_preview(
        finding=None,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.5",
    )
    verification_planner = build_verification_planner_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        related_layer=related_layer or "Layer 27.5",
    )
    patch_planner = build_patch_planner_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        related_layer=related_layer or "Layer 27.5",
    )
    boundary = build_change_boundary_preview(
        target_area=detected_issue,
        command=command_or_issue,
        related_layer=related_layer or "Layer 27.5",
    )

    approval_required = bool(
        profile["human_review_required"]
        or profile["blocked_by_boundary"]
        or risk_matrix.get("approval_required")
    )
    confidence_score = round(
        (
            float(profile["confidence_score"])
            + float(patch_draft.get("confidence_score", 0.0))
            + float(change_preview.get("confidence_score", 0.0))
            + float(diff_preview.get("confidence_score", 0.0))
            + float(risk_matrix.get("confidence_score", 0.0))
            + float(coordinator.get("overall_confidence", 0.0))
            + float(evidence.get("confidence_score", 0.0))
        )
        / 7,
        2,
    )

    return {
        "target_issue": detected_issue,
        "target_component": profile["target_component"],
        "approval_required": approval_required,
        "approval_level": profile["approval_level"],
        "approval_reason": profile["approval_reason"],
        "approval_source": profile["approval_source"],
        "human_review_required": profile["human_review_required"],
        "blocked_by_boundary": profile["blocked_by_boundary"],
        "blocked_reasons": _unique(
            list(profile["blocked_reasons"])
            + list(boundary.get("blocked_actions", []))[:2]
        ),
        "safe_to_continue": profile["safe_to_continue"],
        "recommended_next_action": profile["recommended_next_action"],
        "recommended_approval_path": profile["recommended_approval_path"],
        "required_validations": _unique(
            list(profile["required_validations"])
            + list(verification_planner.get("recommended_validation_steps", []))[:2]
        ),
        "required_tests": _unique(
            list(profile["required_tests"])
            + list(verification_planner.get("required_tests", []))[:2]
            + list(patch_planner.get("required_tests", []))[:2]
        ),
        "confidence_score": confidence_score,
        "integration_signals": {
            "patch_draft": {
                "recommended_files": patch_draft.get("recommended_files", []),
                "draft_change_summary": patch_draft.get("draft_change_summary"),
                "draft_patch_steps": patch_draft.get("draft_patch_steps", []),
                "risk_assessment": patch_draft.get("risk_assessment"),
            },
            "change_preview": {
                "affected_areas": change_preview.get("affected_areas", []),
                "before_summary": change_preview.get("before_summary"),
                "after_summary": change_preview.get("after_summary"),
                "predicted_effects": change_preview.get("predicted_effects", []),
            },
            "diff_preview": {
                "affected_files": diff_preview.get("affected_files", []),
                "before_code_summary": diff_preview.get("before_code_summary"),
                "after_code_summary": diff_preview.get("after_code_summary"),
                "diff_hunks_expected": diff_preview.get("diff_hunks_expected"),
            },
            "patch_risk_matrix": {
                "risk_score": risk_matrix.get("risk_score"),
                "risk_level": risk_matrix.get("risk_level"),
                "risk_reasons": risk_matrix.get("risk_reasons", []),
                "dependency_risk": risk_matrix.get("dependency_risk"),
                "runtime_risk": risk_matrix.get("runtime_risk"),
                "regression_risk": risk_matrix.get("regression_risk"),
                "boundary_risk": risk_matrix.get("boundary_risk"),
            },
            "multi_agent_coordinator": {
                "combined_findings": coordinator.get("combined_findings", []),
                "combined_risks": coordinator.get("combined_risks", []),
                "combined_recommendations": coordinator.get("combined_recommendations", []),
                "overall_confidence": coordinator.get("overall_confidence"),
            },
            "evidence_store": {
                "finding": evidence.get("finding"),
                "evidence_items": evidence.get("evidence_items", []),
                "risk_reasoning": evidence.get("risk_reasoning"),
                "supporting_signals": evidence.get("supporting_signals", []),
            },
            "verification_planner": {
                "required_tests": verification_planner.get("required_tests", []),
                "recommended_validation_steps": verification_planner.get("recommended_validation_steps", []),
                "verification_approach": verification_planner.get("verification_approach"),
            },
            "safe_patch_planner": {
                "recommended_change_areas": patch_planner.get("recommended_change_areas", []),
                "recommended_patch_scope": patch_planner.get("recommended_patch_scope"),
                "estimated_complexity": patch_planner.get("estimated_complexity"),
                "required_tests": patch_planner.get("required_tests", []),
            },
            "safe_change_boundary": {
                "boundary_level": boundary.get("boundary_level"),
                "criticality_level": boundary.get("criticality_level"),
                "allowed_actions": boundary.get("allowed_actions", []),
                "blocked_actions": boundary.get("blocked_actions", []),
                "risk_reason": boundary.get("risk_reason"),
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
        "safety_note": "This is only a read-only patch approval assessment. It does not write files, execute subprocesses, apply patches, commit, push, deploy, or modify chat/stream/websocket/typewriter behavior.",
    }
