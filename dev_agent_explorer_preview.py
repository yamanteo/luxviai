from __future__ import annotations

from typing import Any, Dict, List, Optional

from investigation_task_planner_preview import build_task_planner_preview


EXPLORER_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "known_components": ["ARM", "Typewriter", "Stop button", "Resume button", "stream guard"],
        "known_layers": ["Layer 23", "Layer 24", "Layer 25"],
        "known_endpoints": [
            "/debug/root-flow-audit",
            "/debug/task-planner-preview",
            "/debug/dev-agent-explorer-preview",
        ],
        "known_relationships": [
            "stop_continue behavior owner is Lux ARM",
            "typewriter renders ARM continuation to the visible chat surface",
            "Layer 24 task planner decides the read-only investigation order",
        ],
        "suggested_entry_points": ["app.py", "lux_arm.py", "static/index.html"],
        "complexity_score": "medium",
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "known_components": ["WebSocket stream", "delta event flow", "typewriter queue", "done/final event guard"],
        "known_layers": ["Layer 14", "Layer 23", "Layer 24", "Layer 25"],
        "known_endpoints": [
            "/ws",
            "/debug/root-flow-audit",
            "/debug/task-planner-preview",
            "/debug/dev-agent-explorer-preview",
        ],
        "known_relationships": [
            "stream events feed the typewriter surface",
            "late done/final events can affect visible answer state",
            "background tab behavior is a manual scenario, not a preview endpoint action",
        ],
        "suggested_entry_points": ["app.py", "static/index.html"],
        "complexity_score": "high",
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "known_components": ["Workspace blocks", "Export preview", "Command/content separation", "Export-clean guard"],
        "known_layers": ["Layer 15", "Layer 20", "Layer 24", "Layer 25"],
        "known_endpoints": [
            "/workspace/export-preview",
            "/workspace/separation-preview",
            "/debug/task-planner-preview",
            "/debug/dev-agent-explorer-preview",
        ],
        "known_relationships": [
            "command blocks remain excluded from clean export preview",
            "export/file integration is future-only",
            "Layer 24 plans checks before any real export scope opens",
        ],
        "suggested_entry_points": ["workspace_export_preview.py", "workspace_scaffold.py", "app.py"],
        "complexity_score": "medium",
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "known_components": ["Permission Boundary", "Device Safety", "Luxway capabilities", "Data preview"],
        "known_layers": ["Layer 18", "Layer 20", "Layer 24", "Layer 25"],
        "known_endpoints": [
            "/luxway/permission-preview",
            "/luxway/device-safety-preview",
            "/luxway/data-preview",
            "/debug/task-planner-preview",
            "/debug/dev-agent-explorer-preview",
        ],
        "known_relationships": [
            "private device data requires permission",
            "send/delete/call/settings actions require confirmation",
            "real platform access is disabled in scaffold mode",
        ],
        "suggested_entry_points": ["luxway_permission_model.py", "luxway_device_safety.py", "luxway_data_preview.py", "app.py"],
        "complexity_score": "high",
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "investigation", "planner", "priority", "explorer"],
        "known_components": ["Fault Report", "Root Flow Auditor", "Task Planner", "Priority Engine", "Explorer"],
        "known_layers": ["Layer 23", "Layer 24", "Layer 25"],
        "known_endpoints": [
            "/debug/fault-report-preview",
            "/debug/intelligence-preview",
            "/debug/task-planner-preview",
            "/debug/dev-agent-explorer-preview",
        ],
        "known_relationships": [
            "Fault Report displays issue state",
            "Layer 23 provides read-only analysis primitives",
            "Layer 24 composes investigation plans",
            "Layer 25 maps where to start in the system",
        ],
        "suggested_entry_points": ["lux_fault_report.py", "debug_intelligence_core.py", "investigation_task_planner_preview.py", "app.py"],
        "complexity_score": "medium",
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(project_area: Optional[str], command: str) -> str:
    haystack = _normalize(f"{project_area or ''} {command or ''}")
    for profile_id, profile in EXPLORER_PROFILES.items():
        if any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def dev_agent_explorer_status() -> Dict[str, Any]:
    return {
        "layer": "25.1",
        "name": "Dev Agent Explorer Preview",
        "status": "dev_agent_explorer_preview_ready",
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
        "available_endpoints": [
            "/debug/dev-agent-explorer-status",
            "/debug/dev-agent-explorer-registry",
            "/debug/dev-agent-explorer-preview",
        ],
        "connected_layers": [
            "24.0 Lux Fault Report",
            "24.5 Repeated Pattern Detector",
            "24.6 Suggested Investigation Starter",
            "24.7 Investigation Priority Engine",
            "24.8 Investigation Task Planner",
        ],
        "future_direction": ["Layer 25 Dev Agent", "Repo Explorer", "Safe Investigation Runner"],
        "safety_note": "Explorer uses static known system maps only; it does not scan files, execute subprocesses, patch code, commit, push, or deploy.",
    }


def dev_agent_explorer_registry() -> Dict[str, Any]:
    areas: List[Dict[str, Any]] = []
    for profile_id, profile in EXPLORER_PROFILES.items():
        areas.append(
            {
                "id": profile_id,
                "known_components": profile["known_components"],
                "known_layers": profile["known_layers"],
                "known_endpoints": profile["known_endpoints"],
                "suggested_entry_points": profile["suggested_entry_points"],
                "complexity_score": profile["complexity_score"],
            }
        )

    return {
        "layer": "25.1",
        "name": "Dev Agent Explorer Registry",
        "status": "dev_agent_explorer_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "area_count": len(areas),
        "project_areas": areas,
        "connected_endpoints": [
            "/debug/task-planner-preview",
            "/debug/fault-report-preview",
            "/debug/investigation-priority-preview",
            "/debug/investigation-starter-preview",
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


def build_dev_agent_explorer_preview(
    project_area: Optional[str] = None,
    command: str = "",
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(project_area, command)
    profile = EXPLORER_PROFILES[profile_id]
    detected_area = project_area or profile_id
    task_plan = build_task_planner_preview(
        issue_title=detected_area,
        symptom=command,
        command=command or detected_area,
        related_layer=related_layer,
    )
    known_layers = list(profile["known_layers"])
    if related_layer and related_layer not in known_layers:
        known_layers.append(related_layer)

    return {
        "project_area": detected_area,
        "known_components": list(profile["known_components"]),
        "known_layers": known_layers,
        "known_endpoints": list(profile["known_endpoints"]),
        "known_relationships": list(profile["known_relationships"]),
        "suggested_entry_points": _unique(
            list(profile["suggested_entry_points"])
            + list(task_plan.get("starter_signal", {}).get("recommended_files", []))
        ),
        "complexity_score": profile["complexity_score"],
        "confidence_score": 0.87,
        "task_planner_signal": {
            "priority_level": task_plan.get("priority_level"),
            "recommended_task_order": task_plan.get("recommended_task_order", []),
            "recommended_checks": task_plan.get("recommended_checks", []),
            "recommended_tests": task_plan.get("recommended_tests", []),
            "recommended_codex_usage": task_plan.get("recommended_codex_usage"),
        },
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
        "safety_note": "This is a static read-only explorer preview. It does not scan the repo, run commands, or modify any runtime behavior.",
    }
