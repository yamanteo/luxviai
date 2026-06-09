from __future__ import annotations

from typing import Any, Dict, List, Optional

from investigation_priority_engine_preview import build_investigation_priority_preview
from investigation_starter_preview import build_investigation_starter_preview
from knowledge_extractor_preview import build_knowledge_extractor_preview
from repeated_pattern_detector_preview import build_repeated_pattern_preview


TASK_PLANNER_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "estimated_complexity": "medium",
        "recommended_codex_usage": "only_if_manual_tests_fail",
        "task_order": [
            "root_flow_audit",
            "state_source_check",
            "duplicate_owner_check",
            "manual_scenario_test",
            "smoke_validation",
        ],
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "estimated_complexity": "high",
        "recommended_codex_usage": "codex_after_read_only_audit",
        "task_order": [
            "root_flow_audit",
            "event_leak_check",
            "stale_fallback_check",
            "manual_background_tab_test",
            "smoke_validation",
        ],
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "estimated_complexity": "medium",
        "recommended_codex_usage": "only_if_real_export_scope_opens",
        "task_order": [
            "export_boundary_audit",
            "non_exportable_block_check",
            "file_write_guard_check",
            "preview_endpoint_smoke",
        ],
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "estimated_complexity": "high",
        "recommended_codex_usage": "codex_for_platform_integration_only",
        "task_order": [
            "permission_boundary_audit",
            "confirmation_boundary_check",
            "real_access_false_check",
            "manual_private_data_scenario",
            "smoke_validation",
        ],
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(issue_title: Optional[str], symptom: str, command: str) -> str:
    haystack = _normalize(f"{issue_title or ''} {symptom or ''} {command or ''}")
    for profile_id, profile in TASK_PLANNER_PROFILES.items():
        if any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "stop_continue"


def _unique(items: List[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def task_planner_status() -> Dict[str, Any]:
    return {
        "layer": "24.8",
        "name": "Investigation Task Planner Preview",
        "status": "task_planner_preview_ready",
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
            "/debug/task-planner-status",
            "/debug/task-planner-registry",
            "/debug/task-planner-preview",
        ],
        "connected_layers": [
            "23.1 Root Flow Auditor",
            "23.2 Safe Self Check Runner",
            "23.3 Codex Handoff Builder",
            "23.4 Bug Intake Planner",
            "23.5 Credit Saver Engine",
            "23.6 Debug Intelligence Core",
            "24.0 Lux Fault Report",
            "24.4 Knowledge Extractor",
            "24.5 Repeated Pattern Detector",
            "24.6 Suggested Investigation Starter",
            "24.7 Investigation Priority Engine",
        ],
        "future_direction": ["Layer 25 Dev Agent", "Automatic Investigation Planner", "Task Planner"],
        "safety_note": "Task planner is read-only and only composes investigation steps; it does not inspect files or apply fixes.",
    }


def task_planner_registry() -> Dict[str, Any]:
    plans: List[Dict[str, Any]] = []
    for profile_id, profile in TASK_PLANNER_PROFILES.items():
        plans.append(
            {
                "id": profile_id,
                "estimated_complexity": profile["estimated_complexity"],
                "recommended_codex_usage": profile["recommended_codex_usage"],
                "recommended_task_order": profile["task_order"],
            }
        )

    return {
        "layer": "24.8",
        "name": "Investigation Task Planner Registry",
        "status": "task_planner_registry_ready",
        "read_only": True,
        "analysis_only": True,
        "plan_count": len(plans),
        "plans": plans,
        "connected_endpoints": [
            "/debug/investigation-priority-preview",
            "/debug/investigation-starter-preview",
            "/debug/knowledge-extractor-preview",
            "/debug/repeated-pattern-preview",
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


def build_task_planner_preview(
    issue_title: Optional[str] = None,
    symptom: str = "",
    command: str = "",
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(issue_title, symptom, command)
    profile = TASK_PLANNER_PROFILES[profile_id]
    detected_title = issue_title or profile_id
    priority = build_investigation_priority_preview(
        issue_title=detected_title,
        symptom=symptom,
        command=command or detected_title,
        related_layer=related_layer,
    )
    starter = build_investigation_starter_preview(
        issue_title=detected_title,
        symptom=symptom,
        command=command or detected_title,
        related_layer=related_layer,
    )
    pattern_name = (starter.get("recommended_patterns_to_check") or ["duplicate_branch"])[0]
    pattern = build_repeated_pattern_preview(
        pattern_name=pattern_name,
        command=command or detected_title,
        issue_title=detected_title,
        related_layer=related_layer,
    )
    knowledge = build_knowledge_extractor_preview(
        issue_title=detected_title,
        command=command or detected_title,
        related_layer=related_layer,
    )

    priority_level = str(priority.get("priority_level", "medium"))
    task_order = list(profile["task_order"])
    if priority_level == "critical":
        task_order = _unique(["root_flow_audit", "manual_scenario_test"] + task_order)
    elif priority_level == "high":
        task_order = _unique(["root_flow_audit"] + task_order)

    recommended_checks = _unique(
        list(starter.get("recommended_starting_checks", []))
        + list(knowledge.get("recommended_future_checks", []))
        + list(starter.get("recommended_patterns_to_check", []))
    )
    recommended_tests = _unique(list(starter.get("recommended_tests", [])))
    recommended_layers = _unique(
        list(starter.get("recommended_layers", []))
        + list(priority.get("related_layers", []))
        + list(knowledge.get("recommended_layers", []))
    )

    return {
        "issue_title": detected_title,
        "priority_level": priority_level,
        "recommended_task_order": task_order,
        "recommended_checks": recommended_checks,
        "recommended_tests": recommended_tests,
        "recommended_layers": recommended_layers,
        "estimated_complexity": profile["estimated_complexity"],
        "recommended_codex_usage": profile["recommended_codex_usage"],
        "confidence_score": 0.88,
        "priority_signal": {
            "priority_score": priority.get("priority_score"),
            "recommended_order": priority.get("recommended_order"),
            "reasoning_summary": priority.get("reasoning_summary"),
        },
        "starter_signal": {
            "similar_previous_issues": starter.get("similar_previous_issues", []),
            "recommended_files": starter.get("recommended_files", []),
        },
        "knowledge_signal": {
            "lessons_learned": knowledge.get("lessons_learned", [])[:3],
            "related_patterns": knowledge.get("related_patterns", []),
        },
        "pattern_signal": {
            "pattern_name": pattern.get("pattern_name"),
            "risk_trend": pattern.get("risk_trend"),
            "recommended_attention_level": pattern.get("recommended_attention_level"),
        },
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
        "safety_note": "This is a read-only task plan preview. It does not modify code, state, files, or runtime behavior.",
    }
