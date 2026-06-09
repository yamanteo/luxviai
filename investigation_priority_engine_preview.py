from __future__ import annotations

from typing import Any, Dict, List, Optional

from investigation_starter_preview import build_investigation_starter_preview
from repeated_pattern_detector_preview import build_repeated_pattern_preview


PRIORITY_CATEGORIES = ["critical", "high", "medium", "low"]

SUPPORTED_CRITERIA = [
    "core_flow_impact",
    "user_experience_impact",
    "repeated_pattern_risk",
    "technical_complexity",
    "regression_risk",
    "frequency",
    "open_duration",
    "related_layer_count",
]


PRIORITY_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "priority_score": 95,
        "priority_level": "critical",
        "reasoning_summary": "core user flow affected; repeated continuation behavior can break trust quickly",
        "risk_score": 90,
        "impact_score": 100,
        "frequency_score": 85,
        "recommended_order": 1,
        "patterns": ["duplicate_branch", "state_source_conflict", "duplicate_owner"],
        "related_layers": ["ARM", "Layer 23", "Layer 24", "Typewriter"],
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "priority_score": 88,
        "priority_level": "high",
        "reasoning_summary": "live answer delivery and background tab behavior can affect core UX",
        "risk_score": 85,
        "impact_score": 90,
        "frequency_score": 76,
        "recommended_order": 2,
        "patterns": ["event_leak", "stale_fallback", "state_source_conflict"],
        "related_layers": ["stream", "websocket", "typewriter", "Layer 23"],
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "priority_score": 72,
        "priority_level": "medium",
        "reasoning_summary": "important future integration, but current preview-only guard prevents real file risk",
        "risk_score": 70,
        "impact_score": 72,
        "frequency_score": 61,
        "recommended_order": 3,
        "patterns": ["permission_conflict", "endpoint_regression", "stale_fallback"],
        "related_layers": ["Workspace", "Layer 15", "Layer 20"],
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "priority_score": 78,
        "priority_level": "high",
        "reasoning_summary": "private device and permission boundaries are high sensitivity even while preview-only",
        "risk_score": 88,
        "impact_score": 76,
        "frequency_score": 58,
        "recommended_order": 3,
        "patterns": ["permission_conflict", "endpoint_regression"],
        "related_layers": ["Luxway", "Layer 18", "Permission Boundary"],
    },
    "debug_panel": {
        "aliases": ["debug", "panel", "fault", "report", "endpoint"],
        "priority_score": 54,
        "priority_level": "medium",
        "reasoning_summary": "developer visibility issue; useful but does not block core user chat",
        "risk_score": 45,
        "impact_score": 55,
        "frequency_score": 50,
        "recommended_order": 4,
        "patterns": ["endpoint_regression", "route_regression"],
        "related_layers": ["Layer 20", "Layer 24", "Debug Intelligence"],
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(issue_title: Optional[str], symptom: str, command: str) -> str:
    haystack = _normalize(f"{issue_title or ''} {symptom or ''} {command or ''}")
    for profile_id, profile in PRIORITY_PROFILES.items():
        if any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "stop_continue"


def investigation_priority_status() -> Dict[str, Any]:
    return {
        "layer": "24.7",
        "name": "Investigation Priority Engine Preview",
        "status": "investigation_priority_preview_ready",
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
        "priority_categories": PRIORITY_CATEGORIES,
        "supported_criteria": SUPPORTED_CRITERIA,
        "available_endpoints": [
            "/debug/investigation-priority-status",
            "/debug/investigation-priority-registry",
            "/debug/investigation-priority-preview",
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
            "24.6 Suggested Investigation Starter",
        ],
        "future_direction": ["Dev Agent Explorer", "Task Planner", "Lux Dev Agent"],
        "safety_note": "Priority engine is read-only and does not inspect files, apply patches, or change runtime behavior.",
    }


def investigation_priority_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for profile_id, profile in PRIORITY_PROFILES.items():
        items.append(
            {
                "id": profile_id,
                "priority_score": profile["priority_score"],
                "priority_level": profile["priority_level"],
                "reasoning_summary": profile["reasoning_summary"],
                "risk_score": profile["risk_score"],
                "impact_score": profile["impact_score"],
                "frequency_score": profile["frequency_score"],
                "recommended_order": profile["recommended_order"],
                "related_layers": profile["related_layers"],
            }
        )

    return {
        "layer": "24.7",
        "name": "Investigation Priority Registry",
        "status": "investigation_priority_registry_ready",
        "read_only": True,
        "analysis_only": True,
        "priority_item_count": len(items),
        "priority_categories": PRIORITY_CATEGORIES,
        "supported_criteria": SUPPORTED_CRITERIA,
        "priority_items": sorted(items, key=lambda item: item["priority_score"], reverse=True),
        "connected_endpoints": [
            "/debug/repeated-pattern-preview",
            "/debug/investigation-starter-preview",
            "/debug/fault-report-preview",
            "/debug/intelligence-preview",
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


def build_investigation_priority_preview(
    issue_title: Optional[str] = None,
    symptom: str = "",
    command: str = "",
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(issue_title, symptom, command)
    profile = PRIORITY_PROFILES[profile_id]
    detected_title = issue_title or profile_id
    first_pattern = profile["patterns"][0]
    pattern = build_repeated_pattern_preview(
        pattern_name=first_pattern,
        command=command or detected_title,
        issue_title=detected_title,
        related_layer=related_layer,
    )
    starter = build_investigation_starter_preview(
        issue_title=detected_title,
        symptom=symptom,
        command=command or detected_title,
        related_layer=related_layer,
    )
    related_layers = list(profile["related_layers"])
    if related_layer and related_layer not in related_layers:
        related_layers.append(related_layer)

    return {
        "issue_title": detected_title,
        "priority_score": profile["priority_score"],
        "priority_level": profile["priority_level"],
        "reasoning_summary": profile["reasoning_summary"],
        "recommended_order": profile["recommended_order"],
        "risk_score": profile["risk_score"],
        "impact_score": profile["impact_score"],
        "frequency_score": profile["frequency_score"],
        "confidence_score": 0.89,
        "criteria_scores": {
            "core_flow_impact": min(100, profile["impact_score"] + 4),
            "user_experience_impact": profile["impact_score"],
            "repeated_pattern_risk": profile["risk_score"],
            "technical_complexity": max(35, profile["risk_score"] - 12),
            "regression_risk": max(profile["risk_score"], profile["frequency_score"]),
            "frequency": profile["frequency_score"],
            "open_duration": 65 if profile["priority_level"] in {"critical", "high"} else 42,
            "related_layer_count": len(related_layers),
        },
        "related_layers": related_layers,
        "repeated_pattern_signal": {
            "pattern_name": pattern.get("pattern_name"),
            "occurrence_count": pattern.get("occurrence_count"),
            "risk_trend": pattern.get("risk_trend"),
            "recommended_attention_level": pattern.get("recommended_attention_level"),
        },
        "investigation_starter_signal": {
            "recommended_starting_checks": starter.get("recommended_starting_checks", []),
            "recommended_patterns_to_check": starter.get("recommended_patterns_to_check", []),
            "recommended_tests": starter.get("recommended_tests", []),
        },
        "recommended_next_step": "prioritize this issue according to score, then run read-only starter checks before code changes",
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
        "safety_note": "This is a read-only priority preview. It does not inspect files or modify runtime behavior.",
    }
