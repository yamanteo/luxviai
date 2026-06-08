from __future__ import annotations

from typing import Any, Dict, List, Optional

from investigation_timeline_preview import build_investigation_timeline_preview
from knowledge_extractor_preview import build_knowledge_extractor_preview


SUPPORTED_PATTERNS = [
    "duplicate_branch",
    "state_source_conflict",
    "duplicate_owner",
    "stale_fallback",
    "missing_helper",
    "undefined_variable",
    "event_leak",
    "route_regression",
    "endpoint_regression",
    "permission_conflict",
]


PATTERN_REGISTRY: Dict[str, Dict[str, Any]] = {
    "duplicate_branch": {
        "occurrence_count": 4,
        "related_issues": ["stop_continue", "workspace_export", "route_preview"],
        "related_layers": ["Layer 23", "Layer 24", "ARM", "Workspace"],
        "risk_trend": "increasing",
        "recommended_attention_level": "high",
        "aliases": ["duplicate", "branch", "resume", "devam", "dur", "stop", "continue"],
    },
    "state_source_conflict": {
        "occurrence_count": 3,
        "related_issues": ["stop_continue", "visual_scene_continuity"],
        "related_layers": ["ARM", "Typewriter", "Scene Lock", "Layer 23"],
        "risk_trend": "stable_watch",
        "recommended_attention_level": "high",
        "aliases": ["state", "source", "conflict", "arm", "visible", "buffer"],
    },
    "duplicate_owner": {
        "occurrence_count": 2,
        "related_issues": ["stop_continue", "model_routing"],
        "related_layers": ["Layer 23", "Router Core", "ARM"],
        "risk_trend": "stable_watch",
        "recommended_attention_level": "medium",
        "aliases": ["owner", "duplicate owner", "behavior owner"],
    },
    "stale_fallback": {
        "occurrence_count": 2,
        "related_issues": ["stream", "endpoint_regression"],
        "related_layers": ["Chat Runtime", "Layer 20", "Layer 23"],
        "risk_trend": "watch",
        "recommended_attention_level": "medium",
        "aliases": ["fallback", "stale", "old branch"],
    },
    "missing_helper": {
        "occurrence_count": 1,
        "related_issues": ["debug_preview"],
        "related_layers": ["Layer 23", "Layer 24"],
        "risk_trend": "low",
        "recommended_attention_level": "low",
        "aliases": ["helper", "missing"],
    },
    "undefined_variable": {
        "occurrence_count": 1,
        "related_issues": ["debug_preview"],
        "related_layers": ["Layer 23", "Layer 24"],
        "risk_trend": "low",
        "recommended_attention_level": "low",
        "aliases": ["undefined", "variable", "nameerror"],
    },
    "event_leak": {
        "occurrence_count": 3,
        "related_issues": ["websocket_stream", "tab_background_typing"],
        "related_layers": ["stream", "websocket", "typewriter"],
        "risk_trend": "increasing",
        "recommended_attention_level": "high",
        "aliases": ["event", "leak", "websocket", "stream", "delta", "done"],
    },
    "route_regression": {
        "occurrence_count": 2,
        "related_issues": ["debug_panel", "router_preview"],
        "related_layers": ["Layer 19", "Layer 20", "Layer 24"],
        "risk_trend": "watch",
        "recommended_attention_level": "medium",
        "aliases": ["route", "router", "path"],
    },
    "endpoint_regression": {
        "occurrence_count": 2,
        "related_issues": ["endpoint_coverage", "debug_panel"],
        "related_layers": ["Layer 20", "Layer 24"],
        "risk_trend": "watch",
        "recommended_attention_level": "medium",
        "aliases": ["endpoint", "coverage", "status"],
    },
    "permission_conflict": {
        "occurrence_count": 2,
        "related_issues": ["luxway_action", "audio_privacy"],
        "related_layers": ["Luxway", "Voice/Audio", "Permission Boundary"],
        "risk_trend": "stable_watch",
        "recommended_attention_level": "medium",
        "aliases": ["permission", "consent", "confirm", "luxway", "audio"],
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_pattern(pattern_name: Optional[str], command: str) -> str:
    normalized_pattern = _normalize(pattern_name)
    normalized_command = _normalize(command)
    if normalized_pattern in PATTERN_REGISTRY:
        return normalized_pattern

    haystack = f"{normalized_pattern} {normalized_command}"
    for key, payload in PATTERN_REGISTRY.items():
        aliases = payload.get("aliases", [])
        if any(str(alias).lower() in haystack for alias in aliases):
            return key
    return "duplicate_branch"


def repeated_pattern_status() -> Dict[str, Any]:
    return {
        "layer": "24.5",
        "name": "Repeated Pattern Detector Preview",
        "status": "repeated_pattern_preview_ready",
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
        "supported_patterns": SUPPORTED_PATTERNS,
        "available_endpoints": [
            "/debug/repeated-pattern-status",
            "/debug/repeated-pattern-registry",
            "/debug/repeated-pattern-preview",
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
        ],
        "future_direction": [
            "Suggested Investigation Starter",
            "Dev Agent Explorer",
            "Lux Dev Agent",
        ],
        "safety_note": "Repeated pattern detection is read-only and does not inspect or mutate runtime chat/stream/typewriter state.",
    }


def repeated_pattern_registry() -> Dict[str, Any]:
    patterns: List[Dict[str, Any]] = []
    for pattern_name, payload in PATTERN_REGISTRY.items():
        patterns.append(
            {
                "pattern_name": pattern_name,
                "occurrence_count": payload["occurrence_count"],
                "related_issues": payload["related_issues"],
                "related_layers": payload["related_layers"],
                "risk_trend": payload["risk_trend"],
                "recommended_attention_level": payload["recommended_attention_level"],
            }
        )

    return {
        "layer": "24.5",
        "name": "Repeated Pattern Detector Registry",
        "status": "repeated_pattern_registry_ready",
        "read_only": True,
        "analysis_only": True,
        "pattern_count": len(patterns),
        "supported_patterns": SUPPORTED_PATTERNS,
        "patterns": patterns,
        "connected_endpoints": [
            "/debug/investigation-timeline-preview",
            "/debug/knowledge-extractor-preview",
            "/debug/fault-report-preview",
            "/debug/intelligence-preview",
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


def build_repeated_pattern_preview(
    pattern_name: Optional[str] = None,
    command: str = "",
    issue_title: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    selected = _select_pattern(pattern_name, command)
    payload = PATTERN_REGISTRY[selected]
    timeline = build_investigation_timeline_preview(
        issue_title=issue_title or "Dur/Devam sistemi",
        command=command or selected,
        command_behavior="stop_continue" if selected in {"duplicate_branch", "state_source_conflict"} else selected,
    )
    knowledge = build_knowledge_extractor_preview(
        issue_title=issue_title or "ARM Stop Continue",
        command=command or selected,
        related_layer=related_layer,
    )

    related_layers = list(payload["related_layers"])
    if related_layer and related_layer not in related_layers:
        related_layers.append(related_layer)

    return {
        "pattern_name": selected,
        "occurrence_count": payload["occurrence_count"],
        "related_issues": list(payload["related_issues"]),
        "related_layers": related_layers,
        "risk_trend": payload["risk_trend"],
        "recommended_attention_level": payload["recommended_attention_level"],
        "confidence_score": 0.87,
        "timeline_signal_preview": {
            "issue_title": timeline.get("issue_title"),
            "latest_finding": timeline.get("latest_finding"),
            "timeline_entry_count": len(timeline.get("timeline_entries", [])),
        },
        "knowledge_signal_preview": {
            "issue_title": knowledge.get("issue_title"),
            "related_patterns": knowledge.get("related_patterns", []),
            "recommended_future_checks": knowledge.get("recommended_future_checks", []),
        },
        "recommended_next_step": "open suggested investigation starter for the repeated pattern",
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
        "safety_note": "This is a read-only repeated pattern preview; it does not run fixes or write persistent knowledge.",
    }
