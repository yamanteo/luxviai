from __future__ import annotations

from typing import Any, Dict, List, Optional

from dependency_mapper_preview import build_dependency_mapper_preview, dependency_mapper_registry


CAUTION_BY_RISK = {
    "low": "normal",
    "medium": "high",
    "high": "critical",
    "critical": "critical",
}


IMPACT_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "impact_risk": "medium",
        "recommended_caution_level": "high",
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "impact_risk": "high",
        "recommended_caution_level": "critical",
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "impact_risk": "medium",
        "recommended_caution_level": "high",
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "impact_risk": "high",
        "recommended_caution_level": "critical",
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "investigation", "planner", "priority", "explorer", "dependency", "impact"],
        "impact_risk": "medium",
        "recommended_caution_level": "high",
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_component: Optional[str], command: str) -> str:
    haystack = _normalize(f"{target_component or ''} {command or ''}")
    for profile_id, profile in IMPACT_PROFILES.items():
        if any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "debug_intelligence"


def impact_analyzer_status() -> Dict[str, Any]:
    return {
        "layer": "25.3",
        "name": "Impact Analyzer Preview",
        "status": "impact_analyzer_preview_ready",
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
            "/debug/impact-analyzer-status",
            "/debug/impact-analyzer-registry",
            "/debug/impact-analyzer-preview",
        ],
        "connected_layers": [
            "23 Debug Intelligence",
            "24 Investigation System",
            "25.1 Dev Agent Explorer",
            "25.2 Dependency Mapper",
        ],
        "future_direction": ["Safe Patch Planner", "Patch Risk Estimator", "Lux Dev Agent"],
        "safety_note": "Impact analyzer composes dependency map previews only; it does not scan files, execute subprocesses, or modify runtime behavior.",
    }


def impact_analyzer_registry() -> Dict[str, Any]:
    dependency_registry = dependency_mapper_registry()
    impact_items: List[Dict[str, Any]] = []
    for mapping in dependency_registry.get("dependency_mappings", []):
        target = str(mapping.get("id", ""))
        profile = IMPACT_PROFILES.get(target, IMPACT_PROFILES["debug_intelligence"])
        impact_items.append(
            {
                "id": target,
                "potentially_affected_components": mapping.get("related_components", []),
                "potentially_affected_layers": mapping.get("related_layers", []),
                "potentially_affected_endpoints": mapping.get("related_endpoints", []),
                "potentially_affected_behaviors": mapping.get("related_behaviors", []),
                "impact_risk": profile["impact_risk"],
                "recommended_caution_level": profile["recommended_caution_level"],
            }
        )

    return {
        "layer": "25.3",
        "name": "Impact Analyzer Registry",
        "status": "impact_analyzer_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "impact_item_count": len(impact_items),
        "impact_items": impact_items,
        "connected_endpoints": [
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
            "real_file_scan": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_impact_analyzer_preview(
    target_component: Optional[str] = None,
    command: str = "",
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(target_component, command)
    profile = IMPACT_PROFILES[profile_id]
    detected_target = target_component or profile_id
    dependency = build_dependency_mapper_preview(
        component_name=detected_target,
        command=command or detected_target,
        related_layer=related_layer,
    )
    impact_risk = profile["impact_risk"] or dependency.get("dependency_risk", "medium")
    caution = profile.get("recommended_caution_level") or CAUTION_BY_RISK.get(str(impact_risk), "high")

    return {
        "target_component": detected_target,
        "potentially_affected_components": dependency.get("related_components", []),
        "potentially_affected_layers": dependency.get("related_layers", []),
        "potentially_affected_endpoints": dependency.get("related_endpoints", []),
        "potentially_affected_behaviors": dependency.get("related_behaviors", []),
        "impact_risk": impact_risk,
        "recommended_caution_level": caution,
        "confidence_score": 0.88,
        "dependency_signal": {
            "component_name": dependency.get("component_name"),
            "dependency_risk": dependency.get("dependency_risk"),
            "complexity_score": dependency.get("complexity_score"),
            "explorer_signal": dependency.get("explorer_signal", {}),
        },
        "change_impact_note": "Bu hedefte gercek degisiklik yapilmadan once etkilenen sistem, endpoint ve davranislar manuel olarak dogrulanmali.",
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
        "safety_note": "This is a strict read-only impact preview. It performs no repo scan, subprocess execution, patch, commit, push, deploy, or runtime change.",
    }
