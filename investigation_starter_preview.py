from __future__ import annotations

from typing import Any, Dict, List, Optional

from investigation_timeline_preview import build_investigation_timeline_preview
from knowledge_extractor_preview import build_knowledge_extractor_preview
from repeated_pattern_detector_preview import build_repeated_pattern_preview


STARTER_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "recommended_starting_checks": [
            "root_flow_audit",
            "duplicate_branch_check",
            "state_source_conflict_check",
            "behavior_owner_check",
            "manual_scenario_check",
        ],
        "similar_previous_issues": ["ARM Stop Continue", "Resume Flow Issue", "Dur/Devam sistemi"],
        "recommended_layers": ["Layer 23", "Layer 24", "ARM", "Typewriter"],
        "recommended_patterns_to_check": ["duplicate_branch", "state_source_conflict", "duplicate_owner"],
        "recommended_files": ["app.py", "lux_arm.py", "static/index.html"],
        "recommended_tests": [
            "10 maddelik liste",
            "3. maddede dur",
            "devam et",
            "tekrar dur",
            "tekrar devam et",
        ],
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "recommended_starting_checks": [
            "export_clean_check",
            "non_exportable_block_check",
            "file_write_guard_check",
            "confirmation_boundary_check",
        ],
        "similar_previous_issues": ["Workspace Export", "Export Clean Preview"],
        "recommended_layers": ["Layer 15", "Layer 20", "Workspace"],
        "recommended_patterns_to_check": ["permission_conflict", "endpoint_regression", "stale_fallback"],
        "recommended_files": ["workspace_export_preview.py", "workspace_scaffold.py", "app.py"],
        "recommended_tests": [
            "export preview",
            "command block excluded",
            "file_written false",
            "clean_text_preview command-free",
        ],
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "recommended_starting_checks": [
            "event_leak_check",
            "stale_fallback_check",
            "typewriter_queue_check",
            "manual_tab_background_check",
        ],
        "similar_previous_issues": ["Websocket canlilik drift", "Tab background typing"],
        "recommended_layers": ["stream", "websocket", "typewriter", "Layer 23"],
        "recommended_patterns_to_check": ["event_leak", "stale_fallback", "state_source_conflict"],
        "recommended_files": ["app.py", "index.html"],
        "recommended_tests": [
            "long answer starts",
            "switch tab",
            "return to tab",
            "verify typewriter continues without bulk dump",
        ],
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "recommended_starting_checks": [
            "permission_boundary_check",
            "confirmation_boundary_check",
            "real_access_false_check",
            "data_read_false_check",
        ],
        "similar_previous_issues": ["Luxway permission boundary", "Device safety boundary"],
        "recommended_layers": ["Layer 18", "Luxway", "Permission Boundary"],
        "recommended_patterns_to_check": ["permission_conflict", "endpoint_regression"],
        "recommended_files": ["luxway_permission_model.py", "luxway_device_safety.py", "app.py"],
        "recommended_tests": [
            "mail summary preview",
            "message send blocked",
            "device delete blocked",
            "real_access_enabled false",
        ],
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(issue_title: Optional[str], symptom: str, command: str) -> str:
    haystack = _normalize(f"{issue_title or ''} {symptom or ''} {command or ''}")
    for profile_id, profile in STARTER_PROFILES.items():
        if any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "stop_continue"


def investigation_starter_status() -> Dict[str, Any]:
    return {
        "layer": "24.6",
        "name": "Suggested Investigation Starter Preview",
        "status": "investigation_starter_preview_ready",
        "read_only": True,
        "analysis_only": True,
        "real_action_performed": False,
        "real_file_write_performed": False,
        "real_db_write_performed": False,
        "real_memory_write_performed": False,
        "file_write_enabled": False,
        "memory_write_enabled": False,
        "db_write_enabled": False,
        "git_write_enabled": False,
        "auto_fix_enabled": False,
        "patch_apply_enabled": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "available_endpoints": [
            "/debug/investigation-starter-status",
            "/debug/investigation-starter-registry",
            "/debug/investigation-starter-preview",
        ],
        "connected_layers": [
            "23.1 Root Flow Auditor",
            "23.2 Safe Self Check Runner",
            "23.3 Codex Handoff Builder",
            "23.4 Bug Intake Planner",
            "23.5 Credit Saver Engine",
            "23.6 Debug Intelligence Core",
            "24.0 Lux Fault Report",
            "24.1 Fault Report Intelligence Link",
            "24.2 Active Investigation Context",
            "24.3 Investigation Timeline",
            "24.4 Knowledge Extractor",
            "24.5 Repeated Pattern Detector",
        ],
        "future_direction": [
            "Dev Agent Explorer",
            "Lux Dev Agent",
            "Automatic Investigation Planner",
        ],
        "safety_note": "Suggested investigation starter is read-only and creates no fix, patch, commit, deploy, memory, file, or db write.",
    }


def investigation_starter_registry() -> Dict[str, Any]:
    starters: List[Dict[str, Any]] = []
    for profile_id, profile in STARTER_PROFILES.items():
        starters.append(
            {
                "id": profile_id,
                "recommended_starting_checks": profile["recommended_starting_checks"],
                "similar_previous_issues": profile["similar_previous_issues"],
                "recommended_layers": profile["recommended_layers"],
                "recommended_patterns_to_check": profile["recommended_patterns_to_check"],
                "recommended_files": profile["recommended_files"],
                "recommended_tests": profile["recommended_tests"],
            }
        )

    return {
        "layer": "24.6",
        "name": "Suggested Investigation Starter Registry",
        "status": "investigation_starter_registry_ready",
        "read_only": True,
        "analysis_only": True,
        "starter_count": len(starters),
        "starters": starters,
        "connected_endpoints": [
            "/debug/repeated-pattern-preview",
            "/debug/knowledge-extractor-preview",
            "/debug/investigation-timeline-preview",
            "/debug/fault-report-preview",
        ],
        "safety_flags": {
            "file_write": False,
            "memory_write": False,
            "db_write": False,
            "git_write": False,
            "auto_fix": False,
            "patch_apply": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_investigation_starter_preview(
    issue_title: Optional[str] = None,
    symptom: str = "",
    command: str = "",
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(issue_title, symptom, command)
    profile = STARTER_PROFILES[profile_id]
    detected_title = issue_title or profile_id
    first_pattern = profile["recommended_patterns_to_check"][0]
    pattern_preview = build_repeated_pattern_preview(
        pattern_name=first_pattern,
        command=command or detected_title,
        issue_title=detected_title,
        related_layer=related_layer,
    )
    knowledge = build_knowledge_extractor_preview(
        issue_title=profile["similar_previous_issues"][0],
        command=command or detected_title,
        related_layer=related_layer,
    )
    timeline = build_investigation_timeline_preview(
        issue_title=profile["similar_previous_issues"][0],
        command=command or detected_title,
        command_behavior=profile_id,
    )

    recommended_layers = list(profile["recommended_layers"])
    if related_layer and related_layer not in recommended_layers:
        recommended_layers.append(related_layer)

    return {
        "issue_title": detected_title,
        "recommended_starting_checks": list(profile["recommended_starting_checks"]),
        "similar_previous_issues": list(profile["similar_previous_issues"]),
        "recommended_layers": recommended_layers,
        "recommended_patterns_to_check": list(profile["recommended_patterns_to_check"]),
        "recommended_files": list(profile["recommended_files"]),
        "recommended_tests": list(profile["recommended_tests"]),
        "confidence_score": 0.86,
        "pattern_signal_preview": {
            "pattern_name": pattern_preview.get("pattern_name"),
            "risk_trend": pattern_preview.get("risk_trend"),
            "recommended_attention_level": pattern_preview.get("recommended_attention_level"),
        },
        "knowledge_signal_preview": {
            "lessons_learned": knowledge.get("lessons_learned", [])[:3],
            "recommended_future_checks": knowledge.get("recommended_future_checks", [])[:4],
        },
        "timeline_signal_preview": {
            "issue_title": timeline.get("issue_title"),
            "latest_finding": timeline.get("latest_finding"),
            "timeline_entry_count": len(timeline.get("timeline_entries", [])),
        },
        "recommended_next_step": "run read-only root flow audit and manual scenario before any code changes",
        "read_only": True,
        "analysis_only": True,
        "real_action_performed": False,
        "real_file_write_performed": False,
        "real_memory_write_performed": False,
        "real_db_write_performed": False,
        "git_write_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "auto_fix_performed": False,
        "patch_apply_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "This output is an investigation starter preview only. It does not inspect files or apply fixes.",
    }
