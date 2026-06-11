from __future__ import annotations

from typing import Any, Dict, List, Optional

from evidence_store_preview import build_evidence_store_preview
from multi_agent_coordinator_preview import build_coordinator_preview
from patch_draft_engine_preview import build_patch_draft_preview, patch_draft_registry
from safe_change_boundary_preview import build_change_boundary_preview


CHANGE_PREVIEW_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "affected_areas": ["resume_flow", "runtime_state"],
        "before_summary": "multiple resume paths",
        "after_summary": "single owner flow",
        "predicted_effects": ["reduced duplication", "simplified validation"],
        "risk_areas": ["stream_runtime"],
        "confidence_score": 0.88,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "affected_areas": ["stream_flow", "event_guard", "typewriter_queue"],
        "before_summary": "stream state can drift across tab and done events",
        "after_summary": "guarded stream events with clearer queue ownership",
        "predicted_effects": ["clearer event boundaries", "lower stale event risk", "more explicit manual regression scope"],
        "risk_areas": ["chat_stream", "websocket_runtime", "typewriter_runtime"],
        "confidence_score": 0.84,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "affected_areas": ["export_preview", "file_write_guard", "workspace_blocks"],
        "before_summary": "export preview and future file write boundary are described separately",
        "after_summary": "export preview shows write boundary and validation impact together",
        "predicted_effects": ["clearer preview-only behavior", "stronger future export guard visibility"],
        "risk_areas": ["future_file_export"],
        "confidence_score": 0.87,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "affected_areas": ["permission_flow", "private_data_boundary", "device_safety"],
        "before_summary": "permission and device safety previews are reviewed independently",
        "after_summary": "permission preview explains expected change impact and private data boundary",
        "predicted_effects": ["clearer approval boundary", "reduced accidental real-access ambiguity"],
        "risk_areas": ["private_data", "device_action_boundary"],
        "confidence_score": 0.86,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "investigation", "planner", "patch", "draft", "change"],
        "affected_areas": ["preview_schema", "fault_report_section", "smoke_coverage"],
        "before_summary": "draft recommendations exist without a separate before-after view",
        "after_summary": "change impact is visible before any real patch work",
        "predicted_effects": ["better review readiness", "clearer approval discussion", "stronger read-only traceability"],
        "risk_areas": ["preview_schema_drift"],
        "confidence_score": 0.9,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_issue: Optional[str], command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for profile_id, profile in CHANGE_PREVIEW_PROFILES.items():
        if profile_id in haystack or any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def change_preview_status() -> Dict[str, Any]:
    return {
        "layer": "27.2",
        "name": "Change Preview Engine",
        "status": "change_preview_ready",
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
            "/debug/change-preview-status",
            "/debug/change-preview-registry",
            "/debug/change-preview",
        ],
        "connected_layers": [
            "27.1 Patch Draft Engine",
            "26.7 Multi-Agent Coordinator",
            "26.6 Evidence Store",
            "25.4 Safe Change Boundary",
        ],
        "safety_note": "Change Preview Engine only explains expected change impact. It never writes files, stores memory, applies patches, runs subprocesses, commits, pushes, deploys, or changes runtime behavior.",
    }


def change_preview_registry() -> Dict[str, Any]:
    previews: List[Dict[str, Any]] = []
    for profile_id, profile in CHANGE_PREVIEW_PROFILES.items():
        boundary = build_change_boundary_preview(target_area=profile_id, command=profile_id, related_layer="Layer 27.2")
        previews.append(
            {
                "id": profile_id,
                "affected_areas": list(profile["affected_areas"]),
                "before_summary": profile["before_summary"],
                "after_summary": profile["after_summary"],
                "predicted_effects": list(profile["predicted_effects"]),
                "risk_areas": list(profile["risk_areas"]),
                "approval_required": bool(boundary.get("user_approval_required")),
                "confidence_score": profile["confidence_score"],
            }
        )

    return {
        "layer": "27.2",
        "name": "Change Preview Registry",
        "status": "change_preview_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "preview_count": len(previews),
        "previews": previews,
        "connected_endpoints": [
            "/debug/patch-draft-preview",
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


def build_change_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(target_issue, command, project_area)
    profile = CHANGE_PREVIEW_PROFILES[profile_id]
    detected_issue = target_issue or project_area or profile_id
    command_or_issue = command or detected_issue

    patch_draft = build_patch_draft_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.2",
    )
    coordinator = build_coordinator_preview(
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.2",
    )
    evidence = build_evidence_store_preview(
        finding=None,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.2",
    )
    boundary = build_change_boundary_preview(
        target_area=detected_issue,
        command=command_or_issue,
        related_layer=related_layer or "Layer 27.2",
    )

    approval_required = bool(
        boundary.get("user_approval_required")
        or patch_draft.get("approval_required")
        or profile["risk_areas"]
    )
    confidence_score = round(
        (
            float(profile["confidence_score"])
            + float(patch_draft.get("confidence_score", 0.0))
            + float(coordinator.get("overall_confidence", 0.0))
            + float(evidence.get("confidence_score", 0.0))
        )
        / 4,
        2,
    )

    return {
        "target_issue": detected_issue,
        "affected_areas": _unique(
            list(profile["affected_areas"])
            + list(patch_draft.get("change_scope", {}).get("recommended_change_areas", []))[:2]
        ),
        "before_summary": profile["before_summary"],
        "after_summary": profile["after_summary"],
        "predicted_effects": _unique(
            list(profile["predicted_effects"])
            + list(coordinator.get("combined_recommendations", []))[:2]
        ),
        "risk_areas": _unique(list(profile["risk_areas"]) + list(coordinator.get("combined_risks", []))[:2]),
        "approval_required": approval_required,
        "confidence_score": confidence_score,
        "integration_signals": {
            "patch_draft": {
                "recommended_files": patch_draft.get("recommended_files", []),
                "draft_change_summary": patch_draft.get("draft_change_summary"),
                "draft_patch_steps": patch_draft.get("draft_patch_steps", []),
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
        "safety_note": "This is only a read-only change preview. It does not write files, execute subprocesses, apply patches, commit, push, deploy, or modify chat/stream/websocket/typewriter behavior.",
    }
