from __future__ import annotations

from typing import Any, Dict, List, Optional

from dev_agent_explorer_preview import build_dev_agent_explorer_preview


DEPENDENCY_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "related_behaviors": ["resume_flow", "stream_flow", "typewriter_flow", "stop_guard"],
        "dependency_risk": "medium",
        "complexity_score": "medium",
        "extra_components": ["visible text state", "continuation buffer"],
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "related_behaviors": ["stream_flow", "delta_handling", "background_tab_typing", "late_done_guard"],
        "dependency_risk": "high",
        "complexity_score": "high",
        "extra_components": ["stream event router", "background tab timer"],
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "related_behaviors": ["export_clean_flow", "block_filtering", "copy_preview", "file_write_guard"],
        "dependency_risk": "medium",
        "complexity_score": "medium",
        "extra_components": ["exportable block rules", "non-exportable command guard"],
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "related_behaviors": ["permission_flow", "confirmation_flow", "private_data_preview", "device_safety_guard"],
        "dependency_risk": "high",
        "complexity_score": "high",
        "extra_components": ["permission model", "device safety boundary"],
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "investigation", "planner", "priority", "explorer", "dependency"],
        "related_behaviors": ["fault_report_flow", "investigation_planning", "priority_scoring", "dependency_mapping"],
        "dependency_risk": "medium",
        "complexity_score": "medium",
        "extra_components": ["Layer 23 analysis previews", "Layer 24 investigation previews"],
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(component_name: Optional[str], command: str) -> str:
    haystack = _normalize(f"{component_name or ''} {command or ''}")
    for profile_id, profile in DEPENDENCY_PROFILES.items():
        if any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def dependency_mapper_status() -> Dict[str, Any]:
    return {
        "layer": "25.2",
        "name": "Dependency Mapper Preview",
        "status": "dependency_mapper_preview_ready",
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
        "real_file_scan_enabled": False,
        "repo_scan_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "available_endpoints": [
            "/debug/dependency-mapper-status",
            "/debug/dependency-mapper-registry",
            "/debug/dependency-mapper-preview",
        ],
        "connected_layers": [
            "23 Debug Intelligence",
            "24 Investigation System",
            "25.1 Dev Agent Explorer",
        ],
        "future_direction": ["Impact Analyzer", "Safe Patch Planner", "Dev Agent"],
        "safety_note": "Dependency mapper uses static preview maps and Explorer output only; it does not scan files or execute subprocesses.",
    }


def dependency_mapper_registry() -> Dict[str, Any]:
    mappings: List[Dict[str, Any]] = []
    for profile_id, profile in DEPENDENCY_PROFILES.items():
        explorer = build_dev_agent_explorer_preview(project_area=profile_id, command=profile_id)
        mappings.append(
            {
                "id": profile_id,
                "related_components": _unique(explorer.get("known_components", []) + profile["extra_components"]),
                "related_layers": explorer.get("known_layers", []),
                "related_endpoints": explorer.get("known_endpoints", []),
                "related_behaviors": profile["related_behaviors"],
                "dependency_risk": profile["dependency_risk"],
                "complexity_score": profile["complexity_score"],
            }
        )

    return {
        "layer": "25.2",
        "name": "Dependency Mapper Registry",
        "status": "dependency_mapper_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "mapping_count": len(mappings),
        "dependency_mappings": mappings,
        "connected_endpoints": [
            "/debug/dev-agent-explorer-preview",
            "/debug/task-planner-preview",
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
            "real_file_scan": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_dependency_mapper_preview(
    component_name: Optional[str] = None,
    command: str = "",
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(component_name, command)
    profile = DEPENDENCY_PROFILES[profile_id]
    detected_component = component_name or profile_id
    explorer = build_dev_agent_explorer_preview(
        project_area=detected_component,
        command=command or detected_component,
        related_layer=related_layer,
    )
    related_layers = list(explorer.get("known_layers", []))
    if related_layer and related_layer not in related_layers:
        related_layers.append(related_layer)

    return {
        "component_name": detected_component,
        "related_components": _unique(list(explorer.get("known_components", [])) + list(profile["extra_components"])),
        "related_layers": related_layers,
        "related_endpoints": list(explorer.get("known_endpoints", [])),
        "related_behaviors": list(profile["related_behaviors"]),
        "dependency_risk": profile["dependency_risk"],
        "complexity_score": profile["complexity_score"],
        "confidence_score": 0.88,
        "explorer_signal": {
            "project_area": explorer.get("project_area"),
            "known_relationships": explorer.get("known_relationships", []),
            "suggested_entry_points": explorer.get("suggested_entry_points", []),
        },
        "impact_question_preview": "Bu alanda degisiklik yapilirsa related_components, related_endpoints ve related_behaviors etkilenebilir.",
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
        "real_file_scan_performed": False,
        "repo_scan_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "This is a strict read-only dependency map preview. It performs no repo scan, subprocess execution, patch, commit, push, deploy, or runtime change.",
    }
