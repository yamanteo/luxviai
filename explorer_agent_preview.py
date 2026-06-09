from __future__ import annotations

from typing import Any, Dict, List, Optional

from agent_constitution_engine_preview import build_constitution_preview
from dev_agent_explorer_preview import build_dev_agent_explorer_preview, dev_agent_explorer_registry
from project_rules_loader_preview import build_project_rules_preview


EXPLORER_ALLOWED_CAPABILITIES: List[str] = [
    "exploration",
    "relationship_mapping",
    "entry_point_suggestion",
    "investigation_focus_selection",
    "read_only_context_mapping",
]

EXPLORER_BLOCKED_CAPABILITIES: List[str] = [
    "patch_generation",
    "patch_application",
    "test_execution",
    "file_write",
    "memory_write",
    "db_write",
    "commit",
    "push",
    "deploy",
    "subprocess_execution",
    "real_repo_scan",
]


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_focus(command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{project_area or ''} {command or ''}")
    if any(term in haystack for term in ["stop", "continue", "dur", "devam", "arm"]):
        return "resume_flow_dependency_analysis"
    if any(term in haystack for term in ["websocket", "stream", "typewriter"]):
        return "stream_relationship_mapping"
    if any(term in haystack for term in ["workspace", "export", "file", "dosya"]):
        return "workspace_export_boundary_mapping"
    if any(term in haystack for term in ["luxway", "permission", "phone", "telefon"]):
        return "permission_flow_mapping"
    return "dependency_analysis"


def explorer_agent_status() -> Dict[str, Any]:
    return {
        "layer": "26.3",
        "name": "Explorer Agent Preview",
        "status": "explorer_agent_preview_ready",
        "agent_role": "explorer",
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
        "test_execution_enabled": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "allowed_capabilities": EXPLORER_ALLOWED_CAPABILITIES,
        "blocked_capabilities": EXPLORER_BLOCKED_CAPABILITIES,
        "available_endpoints": [
            "/debug/explorer-agent-status",
            "/debug/explorer-agent-registry",
            "/debug/explorer-agent-preview",
        ],
        "connected_layers": [
            "25.1 Dev Agent Explorer",
            "26.1 Agent Constitution Engine",
            "26.2 Project Rules Loader",
        ],
        "future_direction": ["Planner Agent", "Verifier Agent", "Coordinator Agent"],
        "safety_note": "Explorer Agent is strict read-only. It maps systems and entry points but does not scan files, write code, generate patches, run tests, commit, push, or deploy.",
    }


def explorer_agent_registry() -> Dict[str, Any]:
    explorer_registry = dev_agent_explorer_registry()
    return {
        "layer": "26.3",
        "name": "Explorer Agent Registry",
        "status": "explorer_agent_registry_ready",
        "agent_role": "explorer",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "allowed_capabilities": EXPLORER_ALLOWED_CAPABILITIES,
        "blocked_capabilities": EXPLORER_BLOCKED_CAPABILITIES,
        "known_project_areas": explorer_registry.get("project_areas", []),
        "role_contract": {
            "can_explore": True,
            "can_map_relationships": True,
            "can_suggest_entry_points": True,
            "can_start_investigation": True,
            "can_write_code": False,
            "can_generate_patch": False,
            "can_run_tests": False,
            "can_commit": False,
            "can_push": False,
            "can_deploy": False,
        },
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
            "real_repo_scan": False,
            "test_execution": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_explorer_agent_preview(
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    explorer = build_dev_agent_explorer_preview(
        project_area=project_area,
        command=command,
        related_layer=related_layer,
    )
    constitution = build_constitution_preview(
        command=command or project_area or "explorer agent read only mapping",
        rule_source="project_rules",
        conflicting_rules=["project_layer_rule", "read_only_mode"],
        target_area=project_area or "debug_intelligence",
    )
    project_rules = build_project_rules_preview(
        command=command or project_area or "protected runtime exploration",
        project_rule_category="protected_runtime" if _select_focus(command, project_area).startswith("resume") else None,
        target_area=project_area or "debug_intelligence",
    )
    recommended_entry_points = list(explorer.get("suggested_entry_points", []))
    recommended_related_systems = list(explorer.get("known_components", []))

    return {
        "agent_role": "explorer",
        "allowed_capabilities": EXPLORER_ALLOWED_CAPABILITIES,
        "blocked_capabilities": EXPLORER_BLOCKED_CAPABILITIES,
        "recommended_entry_points": recommended_entry_points,
        "recommended_related_systems": recommended_related_systems,
        "investigation_focus": _select_focus(command, project_area),
        "confidence_score": 0.9,
        "explorer_signal": {
            "project_area": explorer.get("project_area"),
            "known_layers": explorer.get("known_layers", []),
            "known_endpoints": explorer.get("known_endpoints", []),
            "known_relationships": explorer.get("known_relationships", []),
            "complexity_score": explorer.get("complexity_score"),
        },
        "constitution_signal": {
            "selected_rule": constitution.get("selected_rule"),
            "rule_source": constitution.get("rule_source"),
            "rule_priority": constitution.get("rule_priority"),
            "resolution_reason": constitution.get("resolution_reason"),
        },
        "project_rules_signal": {
            "project_rule_category": project_rules.get("project_rule_category"),
            "protected_areas": project_rules.get("protected_areas", []),
            "required_checks": project_rules.get("required_checks", []),
            "blocked_actions": project_rules.get("blocked_actions", []),
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
        "test_execution_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Explorer Agent only maps relationships and entry points in preview mode. It does not scan real files, write code, generate patches, run tests, commit, push, or deploy.",
    }
