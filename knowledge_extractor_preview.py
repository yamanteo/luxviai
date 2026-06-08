from __future__ import annotations

from typing import Any, Dict, List, Optional

from investigation_timeline_preview import build_investigation_timeline_preview


KNOWLEDGE_PATTERNS: Dict[str, Dict[str, Any]] = {
    "arm_stop_continue": {
        "issue_title": "ARM Stop Continue",
        "aliases": ["arm", "stop", "continue", "dur", "devam", "resume"],
        "resolution_summary": "Duplicate resume ownership was narrowed and ARM became the single continuation source.",
        "lessons_learned": [
            "duplicate owner control should happen early",
            "resume state source should stay singular",
            "visible text and generated answer buffer must not compete",
            "manual multi-cycle stop/continue scenarios should be part of regression checks",
        ],
        "recommended_future_checks": [
            "duplicate_branch_check",
            "state_source_conflict_check",
            "manual_scenario_check",
            "behavior_owner_check",
        ],
        "related_patterns": ["resume_flow", "runtime_state", "arm_buffer", "typewriter_continuation"],
        "recommended_layers": ["ARM", "Layer 23", "Layer 24", "Stop/Continue"],
    },
    "layer24_fault_report": {
        "issue_title": "Layer 24 Fault Report",
        "aliases": ["fault", "report", "timeline", "investigation", "layer 24"],
        "resolution_summary": "Read-only issue tracking, intelligence linking, active context, and timeline previews were connected.",
        "lessons_learned": [
            "debug intelligence should expose status without mutating runtime state",
            "issue cards become more useful when analysis, timeline, and next steps are visible together",
            "developer-only panels should keep safety flags explicit",
        ],
        "recommended_future_checks": [
            "endpoint_health_check",
            "route_existence_check",
            "read_only_flag_check",
            "smoke_check",
        ],
        "related_patterns": ["debug_visibility", "issue_lifecycle", "timeline_trace", "read_only_panel"],
        "recommended_layers": ["Layer 23", "Layer 24", "Debug Intelligence", "Fault Report"],
    },
    "workspace_export": {
        "issue_title": "Workspace Export",
        "aliases": ["workspace", "export", "file", "pdf", "word"],
        "resolution_summary": "Workspace export remains preview-only until real file integration is deliberately enabled.",
        "lessons_learned": [
            "export-clean preview should stay separate from real file writes",
            "command blocks and AI notes should stay out of exportable output",
            "future export integration needs confirmation and regression coverage",
        ],
        "recommended_future_checks": [
            "export_clean_check",
            "non_exportable_block_check",
            "file_write_guard_check",
            "confirmation_boundary_check",
        ],
        "related_patterns": ["export_clean", "file_write_boundary", "workspace_blocks"],
        "recommended_layers": ["Workspace", "Layer 15", "Layer 20"],
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_pattern(issue_title: Optional[str], command: str) -> Dict[str, Any]:
    text = f"{issue_title or ''} {command or ''}".lower()
    for pattern in KNOWLEDGE_PATTERNS.values():
        aliases = pattern.get("aliases", [])
        if any(str(alias).lower() in text for alias in aliases):
            return pattern
    return KNOWLEDGE_PATTERNS["arm_stop_continue"]


def knowledge_extractor_status() -> Dict[str, Any]:
    return {
        "layer": "24.4",
        "name": "Knowledge Extractor Preview",
        "status": "knowledge_extractor_preview_ready",
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
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "available_endpoints": [
            "/debug/knowledge-extractor-status",
            "/debug/knowledge-extractor-registry",
            "/debug/knowledge-extractor-preview",
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
        ],
        "future_direction": [
            "Repeated Pattern Detector",
            "Suggested Investigation Starter",
            "Lux Dev Agent knowledge base",
        ],
        "safety_note": "Knowledge extraction is read-only. No memory, file, db, git, commit, push, deploy, or auto-fix is performed.",
    }


def knowledge_extractor_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pattern_id, pattern in KNOWLEDGE_PATTERNS.items():
        items.append(
            {
                "id": pattern_id,
                "issue_title": pattern["issue_title"],
                "resolution_summary": pattern["resolution_summary"],
                "recommended_future_checks": pattern["recommended_future_checks"],
                "related_patterns": pattern["related_patterns"],
                "recommended_layers": pattern["recommended_layers"],
            }
        )

    return {
        "layer": "24.4",
        "name": "Knowledge Extractor Registry",
        "status": "knowledge_registry_ready",
        "read_only": True,
        "analysis_only": True,
        "knowledge_item_count": len(items),
        "knowledge_items": items,
        "connected_endpoints": [
            "/debug/fault-report-registry",
            "/debug/investigation-timeline-preview",
            "/debug/intelligence-preview",
            "/debug/codex-handoff-preview",
        ],
        "safety_flags": {
            "file_write": False,
            "memory_write": False,
            "db_write": False,
            "git_write": False,
            "auto_fix": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_knowledge_extractor_preview(
    issue_title: Optional[str] = None,
    resolution_summary: str = "",
    command: str = "",
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pattern = _select_pattern(issue_title, command)
    detected_title = issue_title or pattern["issue_title"]
    timeline = build_investigation_timeline_preview(
        issue_title=detected_title,
        command=command or detected_title,
        current_status="resolved" if "resolved" in _normalize(resolution_summary) else None,
    )

    summary = resolution_summary.strip() or pattern["resolution_summary"]
    recommended_layers = list(pattern["recommended_layers"])
    if related_layer and related_layer not in recommended_layers:
        recommended_layers.append(related_layer)

    return {
        "issue_title": detected_title,
        "resolution_summary": summary,
        "lessons_learned": list(pattern["lessons_learned"]),
        "recommended_future_checks": list(pattern["recommended_future_checks"]),
        "related_patterns": list(pattern["related_patterns"]),
        "recommended_layers": recommended_layers,
        "confidence_score": 0.88,
        "timeline_source_preview": {
            "issue_title": timeline.get("issue_title"),
            "latest_finding": timeline.get("latest_finding"),
            "recommended_next_step": timeline.get("recommended_next_step"),
            "timeline_entry_count": len(timeline.get("timeline_entries", [])),
        },
        "future_use": [
            "repeated_pattern_detector",
            "suggested_investigation_starter",
            "lux_dev_agent_context",
        ],
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
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "This is a read-only lesson extraction preview from resolved issue patterns.",
    }
