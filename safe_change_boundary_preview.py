from __future__ import annotations

from typing import Any, Dict, List, Optional

from impact_analyzer_preview import build_impact_analyzer_preview, impact_analyzer_registry


BOUNDARY_LEVELS = ["open", "protected", "critical", "restricted"]

CRITICAL_AREAS = [
    "chat",
    "stream",
    "websocket",
    "typewriter",
    "stop_continue",
    "authentication",
    "payment",
    "memory",
    "router",
    "core_runtime",
]


BOUNDARY_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "boundary_level": "protected",
        "user_approval_required": True,
        "criticality_level": "high",
        "allowed_actions": ["analysis", "planning", "manual_test_plan", "read_only_preview"],
        "blocked_actions": ["auto_patch", "auto_commit", "auto_push", "auto_deploy", "runtime_change_without_approval"],
        "risk_reason": "core runtime behavior and visible answer continuation can affect user trust",
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "boundary_level": "critical",
        "user_approval_required": True,
        "criticality_level": "critical",
        "allowed_actions": ["analysis", "planning", "manual_test_plan", "read_only_preview"],
        "blocked_actions": ["auto_patch", "auto_commit", "auto_push", "auto_deploy", "stream_refactor_without_approval"],
        "risk_reason": "live chat delivery, websocket stream, and typewriter runtime are protected surfaces",
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "boundary_level": "protected",
        "user_approval_required": True,
        "criticality_level": "medium",
        "allowed_actions": ["analysis", "planning", "preview_schema_change", "read_only_preview"],
        "blocked_actions": ["real_file_write", "auto_export", "auto_commit", "auto_push", "auto_deploy"],
        "risk_reason": "future export/file write path must remain preview-only until explicitly approved",
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "boundary_level": "critical",
        "user_approval_required": True,
        "criticality_level": "critical",
        "allowed_actions": ["analysis", "planning", "permission_preview", "read_only_preview"],
        "blocked_actions": ["real_phone_access", "real_private_data_read", "auto_send", "auto_delete", "auto_patch"],
        "risk_reason": "private device data, permission flow, and action boundaries require strict protection",
    },
    "memory": {
        "aliases": ["memory", "hafiza", "hatirla", "retrieval"],
        "boundary_level": "restricted",
        "user_approval_required": True,
        "criticality_level": "critical",
        "allowed_actions": ["analysis", "planning", "safe_summary_preview"],
        "blocked_actions": ["raw_sensitive_memory_read", "memory_write", "db_write", "auto_patch", "auto_commit"],
        "risk_reason": "raw sensitive memory retrieval and persistence are restricted",
    },
    "router": {
        "aliases": ["router", "model", "routing", "billing", "cost"],
        "boundary_level": "protected",
        "user_approval_required": True,
        "criticality_level": "high",
        "allowed_actions": ["analysis", "planning", "routing_preview"],
        "blocked_actions": ["real_model_switch", "billing_write", "auto_patch", "auto_commit", "auto_push"],
        "risk_reason": "model routing and billing behavior must not change automatically",
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "investigation", "planner", "priority", "explorer", "dependency", "impact", "boundary"],
        "boundary_level": "open",
        "user_approval_required": False,
        "criticality_level": "low",
        "allowed_actions": ["analysis", "planning", "preview_schema_change", "read_only_preview"],
        "blocked_actions": ["auto_patch", "auto_commit", "auto_push", "auto_deploy"],
        "risk_reason": "developer preview metadata is lower risk but still read-only in this layer",
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_area: Optional[str], command: str) -> str:
    haystack = _normalize(f"{target_area or ''} {command or ''}")
    for profile_id, profile in BOUNDARY_PROFILES.items():
        if any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "debug_intelligence"


def change_boundary_status() -> Dict[str, Any]:
    return {
        "layer": "25.4",
        "name": "Safe Change Boundary Preview",
        "status": "change_boundary_preview_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
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
        "boundary_levels": BOUNDARY_LEVELS,
        "critical_areas": CRITICAL_AREAS,
        "available_endpoints": [
            "/debug/change-boundary-status",
            "/debug/change-boundary-registry",
            "/debug/change-boundary-preview",
        ],
        "connected_layers": [
            "23 Debug Intelligence",
            "24 Investigation System",
            "25.1 Dev Agent Explorer",
            "25.2 Dependency Mapper",
            "25.3 Impact Analyzer",
        ],
        "future_direction": ["Safe Patch Planner", "Permission Engine", "Lux Dev Agent"],
        "safety_note": "Safe Change Boundary is strict read-only and only describes allowed/blocked actions before future Dev Agent changes.",
    }


def change_boundary_registry() -> Dict[str, Any]:
    boundaries: List[Dict[str, Any]] = []
    for profile_id, profile in BOUNDARY_PROFILES.items():
        boundaries.append(
            {
                "id": profile_id,
                "boundary_level": profile["boundary_level"],
                "user_approval_required": profile["user_approval_required"],
                "criticality_level": profile["criticality_level"],
                "allowed_actions": profile["allowed_actions"],
                "blocked_actions": profile["blocked_actions"],
                "risk_reason": profile["risk_reason"],
            }
        )

    return {
        "layer": "25.4",
        "name": "Safe Change Boundary Registry",
        "status": "change_boundary_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "boundary_count": len(boundaries),
        "boundary_levels": BOUNDARY_LEVELS,
        "critical_areas": CRITICAL_AREAS,
        "boundaries": boundaries,
        "connected_endpoints": [
            "/debug/impact-analyzer-preview",
            "/debug/dependency-mapper-preview",
            "/debug/dev-agent-explorer-preview",
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
            "patch": False,
            "subprocess_execution": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_change_boundary_preview(
    target_area: Optional[str] = None,
    command: str = "",
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(target_area, command)
    profile = BOUNDARY_PROFILES[profile_id]
    detected_area = target_area or profile_id
    impact = build_impact_analyzer_preview(
        target_component=detected_area,
        command=command or detected_area,
        related_layer=related_layer,
    )
    impact_registry = impact_analyzer_registry()

    return {
        "target_area": detected_area,
        "boundary_level": profile["boundary_level"],
        "user_approval_required": profile["user_approval_required"],
        "criticality_level": profile["criticality_level"],
        "allowed_actions": list(profile["allowed_actions"]),
        "blocked_actions": list(profile["blocked_actions"]),
        "risk_reason": profile["risk_reason"],
        "confidence_score": 0.89,
        "impact_signal": {
            "impact_risk": impact.get("impact_risk"),
            "recommended_caution_level": impact.get("recommended_caution_level"),
            "potentially_affected_components": impact.get("potentially_affected_components", []),
            "potentially_affected_layers": impact.get("potentially_affected_layers", []),
            "potentially_affected_endpoints": impact.get("potentially_affected_endpoints", []),
            "potentially_affected_behaviors": impact.get("potentially_affected_behaviors", []),
        },
        "registry_signal": {
            "impact_item_count": impact_registry.get("impact_item_count"),
            "boundary_levels": BOUNDARY_LEVELS,
            "critical_areas": CRITICAL_AREAS,
        },
        "approval_note": "Korumali veya kritik alanlarda gercek degisiklik icin acik kullanici onayi gerekir.",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
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
        "safety_note": "This is a strict read-only boundary preview. It performs no patch, file write, subprocess, commit, push, deploy, or runtime change.",
    }
