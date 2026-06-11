from __future__ import annotations

from typing import Any, Dict, List, Optional

from evidence_store_preview import build_evidence_store_preview
from multi_agent_coordinator_preview import build_coordinator_preview
from patch_draft_engine_preview import build_patch_draft_preview, patch_draft_registry
from change_preview_engine_preview import build_change_preview, change_preview_registry
from safe_change_boundary_preview import build_change_boundary_preview


DIFF_PREVIEW_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "affected_files": ["app.py"],
        "before_code_summary": "multiple resume_owner paths with scattered validation",
        "after_code_summary": "single resume_owner path with consolidated validation",
        "diff_hunks_expected": 2,
        "risk_areas": ["stream_runtime", "resume_flow"],
        "confidence_score": 0.87,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "affected_files": ["app.py", "static/index.html"],
        "before_code_summary": "stream state can drift across tab and done events",
        "after_code_summary": "guarded stream events with explicit queue ownership",
        "diff_hunks_expected": 3,
        "risk_areas": ["chat_stream", "websocket_runtime", "typewriter_runtime"],
        "confidence_score": 0.83,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "affected_files": ["workspace_export_preview.py", "app.py"],
        "before_code_summary": "export preview and file write guard are separate concerns",
        "after_code_summary": "export preview shows write boundary and validation together",
        "diff_hunks_expected": 2,
        "risk_areas": ["future_file_export"],
        "confidence_score": 0.86,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "affected_files": ["luxway_permission_model.py", "luxway_device_safety.py", "app.py"],
        "before_code_summary": "permission and device safety reviewed independently",
        "after_code_summary": "permission preview includes private data boundary explanation",
        "diff_hunks_expected": 3,
        "risk_areas": ["private_data", "device_action_boundary"],
        "confidence_score": 0.85,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "investigation", "planner", "patch", "draft", "change", "diff"],
        "affected_files": ["diff_preview_engine_preview.py", "app.py", "lux_fault_report.py", "scripts/smoke_check.py"],
        "before_code_summary": "patch draft and change preview exist without a unified diff view",
        "after_code_summary": "diff preview shows before/after comparison with integration signals",
        "diff_hunks_expected": 2,
        "risk_areas": ["preview_schema_drift"],
        "confidence_score": 0.9,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_issue: Optional[str], command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for profile_id, profile in DIFF_PREVIEW_PROFILES.items():
        if profile_id in haystack or any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def diff_preview_status() -> Dict[str, Any]:
    return {
        "layer": "27.3",
        "name": "Diff Preview Engine",
        "status": "diff_preview_ready",
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
            "/debug/diff-preview-status",
            "/debug/diff-preview-registry",
            "/debug/diff-preview",
        ],
        "connected_layers": [
            "27.1 Patch Draft Engine",
            "27.2 Change Preview Engine",
            "26.7 Multi-Agent Coordinator",
            "26.6 Evidence Store",
            "25.4 Safe Change Boundary",
        ],
        "safety_note": "Diff Preview Engine only visualizes expected diffs. It never writes files, stores memory, applies patches, runs subprocesses, commits, pushes, deploys, or changes runtime behavior.",
    }


def diff_preview_registry() -> Dict[str, Any]:
    diffs: List[Dict[str, Any]] = []
    for profile_id, profile in DIFF_PREVIEW_PROFILES.items():
        boundary = build_change_boundary_preview(target_area=profile_id, command=profile_id, related_layer="Layer 27.3")
        diffs.append(
            {
                "id": profile_id,
                "affected_files": list(profile["affected_files"]),
                "before_code_summary": profile["before_code_summary"],
                "after_code_summary": profile["after_code_summary"],
                "diff_hunks_expected": profile["diff_hunks_expected"],
                "risk_areas": list(profile["risk_areas"]),
                "approval_required": bool(boundary.get("user_approval_required")),
                "confidence_score": profile["confidence_score"],
            }
        )

    return {
        "layer": "27.3",
        "name": "Diff Preview Registry",
        "status": "diff_preview_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "diff_count": len(diffs),
        "diffs": diffs,
        "connected_endpoints": [
            "/debug/patch-draft-preview",
            "/debug/change-preview",
            "/debug/coordinator-preview",
            "/debug/evidence-store-preview",
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


def build_diff_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(target_issue, command, project_area)
    profile = DIFF_PREVIEW_PROFILES[profile_id]
    detected_issue = target_issue or project_area or profile_id
    command_or_issue = command or detected_issue

    patch_draft = build_patch_draft_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.3",
    )
    change_preview = build_change_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.3",
    )
    coordinator = build_coordinator_preview(
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.3",
    )
    evidence = build_evidence_store_preview(
        finding=None,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.3",
    )
    boundary = build_change_boundary_preview(
        target_area=detected_issue,
        command=command_or_issue,
        related_layer=related_layer or "Layer 27.3",
    )

    approval_required = bool(
        boundary.get("user_approval_required")
        or patch_draft.get("approval_required")
        or change_preview.get("approval_required")
        or profile["risk_areas"]
    )
    confidence_score = round(
        (
            float(profile["confidence_score"])
            + float(patch_draft.get("confidence_score", 0.0))
            + float(change_preview.get("confidence_score", 0.0))
            + float(coordinator.get("overall_confidence", 0.0))
            + float(evidence.get("confidence_score", 0.0))
        )
        / 5,
        2,
    )

    return {
        "target_issue": detected_issue,
        "affected_files": _unique(
            list(profile["affected_files"])
            + list(patch_draft.get("recommended_files", []))[:2]
        ),
        "before_code_summary": profile["before_code_summary"],
        "after_code_summary": profile["after_code_summary"],
        "diff_hunks_expected": profile["diff_hunks_expected"],
        "predicted_changes": _unique(
            list(change_preview.get("predicted_effects", []))
            + list(patch_draft.get("draft_patch_steps", []))[:2]
        ),
        "risk_areas": _unique(
            list(profile["risk_areas"])
            + list(change_preview.get("risk_areas", []))
            + list(coordinator.get("combined_risks", []))[:2]
        ),
        "approval_required": approval_required,
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
        "safety_note": "This is only a read-only diff preview. It does not write files, execute subprocesses, apply patches, commit, push, deploy, or modify chat/stream/websocket/typewriter behavior.",
    }
