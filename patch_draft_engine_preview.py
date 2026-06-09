from __future__ import annotations

from typing import Any, Dict, List, Optional

from evidence_store_preview import build_evidence_store_preview
from multi_agent_coordinator_preview import build_coordinator_preview
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview


PATCH_DRAFT_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "recommended_files": ["app.py", "runtime_memory.py"],
        "draft_change_summary": "resume flow consolidation",
        "draft_patch_steps": ["identify duplicate owner", "merge flow", "add validation"],
        "risk_assessment": "medium",
        "confidence_score": 0.88,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "recommended_files": ["app.py", "static/index.html"],
        "draft_change_summary": "stream event guard and typewriter state review",
        "draft_patch_steps": ["map stream event ownership", "draft guard placement", "define manual tab regression"],
        "risk_assessment": "high",
        "confidence_score": 0.84,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "recommended_files": ["workspace_export_preview.py", "app.py"],
        "draft_change_summary": "export preview guard tightening",
        "draft_patch_steps": ["locate export preview schema", "draft write guard assertion", "add preview validation"],
        "risk_assessment": "medium",
        "confidence_score": 0.87,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "recommended_files": ["luxway_permission_model.py", "luxway_device_safety.py", "app.py"],
        "draft_change_summary": "permission boundary explanation and confirmation path draft",
        "draft_patch_steps": ["review protected data surface", "draft confirmation boundary", "add false real-access guard"],
        "risk_assessment": "high",
        "confidence_score": 0.86,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "investigation", "planner", "patch", "draft"],
        "recommended_files": ["patch_draft_engine_preview.py", "app.py", "lux_fault_report.py", "scripts/smoke_check.py"],
        "draft_change_summary": "read-only patch draft visibility",
        "draft_patch_steps": ["add preview schema", "connect debug endpoints", "surface fault report section"],
        "risk_assessment": "low",
        "confidence_score": 0.9,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_issue: Optional[str], command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for profile_id, profile in PATCH_DRAFT_PROFILES.items():
        if profile_id in haystack or any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def patch_draft_status() -> Dict[str, Any]:
    return {
        "layer": "27.1",
        "name": "Patch Draft Engine Preview",
        "status": "patch_draft_preview_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "draft_only": True,
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
            "/debug/patch-draft-status",
            "/debug/patch-draft-registry",
            "/debug/patch-draft-preview",
        ],
        "connected_layers": [
            "25.4 Safe Change Boundary",
            "25.5 Safe Patch Planner",
            "26.6 Evidence Store",
            "26.7 Multi-Agent Coordinator",
        ],
        "safety_note": "Patch Draft Engine only creates a read-only draft. It never writes files, stores memory, applies patches, runs subprocesses, commits, pushes, deploys, or changes runtime behavior.",
    }


def patch_draft_registry() -> Dict[str, Any]:
    drafts: List[Dict[str, Any]] = []
    for profile_id, profile in PATCH_DRAFT_PROFILES.items():
        boundary = build_change_boundary_preview(target_area=profile_id, command=profile_id, related_layer="Layer 27.1")
        drafts.append(
            {
                "id": profile_id,
                "recommended_files": list(profile["recommended_files"]),
                "draft_change_summary": profile["draft_change_summary"],
                "draft_patch_steps": list(profile["draft_patch_steps"]),
                "risk_assessment": profile["risk_assessment"],
                "approval_required": bool(boundary.get("user_approval_required")),
                "confidence_score": profile["confidence_score"],
            }
        )

    return {
        "layer": "27.1",
        "name": "Patch Draft Registry",
        "status": "patch_draft_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "draft_count": len(drafts),
        "drafts": drafts,
        "connected_endpoints": [
            "/debug/patch-planner-preview",
            "/debug/change-boundary-preview",
            "/debug/evidence-store-preview",
            "/debug/coordinator-preview",
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


def build_patch_draft_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(target_issue, command, project_area)
    profile = PATCH_DRAFT_PROFILES[profile_id]
    detected_issue = target_issue or project_area or profile_id
    command_or_issue = command or detected_issue

    planner = build_patch_planner_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        related_layer=related_layer or "Layer 27.1",
    )
    boundary = build_change_boundary_preview(
        target_area=detected_issue,
        command=command_or_issue,
        related_layer=related_layer or "Layer 27.1",
    )
    evidence = build_evidence_store_preview(
        finding=None,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.1",
    )
    coordinator = build_coordinator_preview(
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.1",
    )

    approval_required = bool(
        boundary.get("user_approval_required")
        or planner.get("approval_required")
        or profile["risk_assessment"] in {"medium", "high"}
    )
    confidence_score = round(
        (
            float(profile["confidence_score"])
            + float(planner.get("confidence_score", 0.0))
            + float(evidence.get("confidence_score", 0.0))
            + float(coordinator.get("overall_confidence", 0.0))
        )
        / 4,
        2,
    )

    return {
        "target_issue": detected_issue,
        "recommended_files": _unique(
            list(profile["recommended_files"]) + [str(item) for item in planner.get("recommended_files", [])]
        ),
        "draft_change_summary": profile["draft_change_summary"],
        "draft_patch_steps": _unique(list(profile["draft_patch_steps"]) + list(planner.get("recommended_validation_steps", []))[:2]),
        "risk_assessment": profile["risk_assessment"],
        "approval_required": approval_required,
        "confidence_score": confidence_score,
        "change_scope": {
            "recommended_change_areas": planner.get("recommended_change_areas", []),
            "recommended_patch_scope": planner.get("recommended_patch_scope"),
            "estimated_complexity": planner.get("estimated_complexity"),
        },
        "risk_and_rationale": {
            "boundary_level": boundary.get("boundary_level"),
            "criticality_level": boundary.get("criticality_level"),
            "risk_reason": boundary.get("risk_reason"),
            "evidence_reasoning": evidence.get("risk_reasoning"),
            "combined_risks": coordinator.get("combined_risks", []),
        },
        "integration_signals": {
            "patch_planner": {
                "required_tests": planner.get("required_tests", []),
                "recommended_validation_steps": planner.get("recommended_validation_steps", []),
            },
            "safe_change_boundary": {
                "allowed_actions": boundary.get("allowed_actions", []),
                "blocked_actions": boundary.get("blocked_actions", []),
            },
            "evidence_store": {
                "finding": evidence.get("finding"),
                "evidence_items": evidence.get("evidence_items", []),
                "supporting_signals": evidence.get("supporting_signals", []),
            },
            "multi_agent_coordinator": {
                "combined_findings": coordinator.get("combined_findings", []),
                "combined_recommendations": coordinator.get("combined_recommendations", []),
                "overall_confidence": coordinator.get("overall_confidence"),
            },
        },
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "draft_only": True,
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
        "safety_note": "This is only a proposed patch draft. It does not write files, execute subprocesses, apply patches, commit, push, deploy, or modify chat/stream/websocket/typewriter behavior.",
    }
