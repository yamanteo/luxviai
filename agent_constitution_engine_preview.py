from __future__ import annotations

from typing import Any, Dict, List, Optional

from dev_agent_readiness_snapshot import layer25_status_snapshot
from safe_change_boundary_preview import build_change_boundary_preview


CONSTITUTION_HIERARCHY: List[Dict[str, Any]] = [
    {"source": "constitution_rules", "priority": 1, "description": "Strict safety, read-only, and no destructive action boundaries."},
    {"source": "user_request", "priority": 2, "description": "Explicit user intent inside current task boundaries."},
    {"source": "active_mode", "priority": 3, "description": "Current collaboration/runtime mode instructions."},
    {"source": "project_rules", "priority": 4, "description": "Luxviai repository and layer-specific guardrails."},
    {"source": "memory_preferences", "priority": 5, "description": "Safe derived preferences only; no raw sensitive retrieval."},
    {"source": "historical_context", "priority": 6, "description": "Prior context summaries when allowed and non-sensitive."},
]


RULE_PROFILES: Dict[str, Dict[str, Any]] = {
    "read_only_mode": {
        "source": "constitution_rules",
        "priority": 1,
        "aliases": ["read only", "read_only", "preview", "no write", "strict"],
        "resolution_reason": "constitution_read_only_boundary",
    },
    "protect_runtime": {
        "source": "constitution_rules",
        "priority": 1,
        "aliases": ["chat", "stream", "websocket", "typewriter", "stop", "continue", "runtime"],
        "resolution_reason": "protected_runtime_boundary",
    },
    "user_requested_change": {
        "source": "user_request",
        "priority": 2,
        "aliases": ["change", "fix", "implement", "modify", "update"],
        "resolution_reason": "user_request_applies_within_higher_priority_boundaries",
    },
    "project_layer_rule": {
        "source": "project_rules",
        "priority": 4,
        "aliases": ["layer", "luxviai", "fault report", "dev agent", "workspace"],
        "resolution_reason": "project_rule_applies_after_constitution_and_user_request",
    },
    "safe_preference": {
        "source": "memory_preferences",
        "priority": 5,
        "aliases": ["preference", "memory", "remember", "style"],
        "resolution_reason": "safe_derived_preference_only",
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _unique(items: List[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def _detect_rules(command: str, conflicting_rules: Optional[List[str]]) -> List[str]:
    detected = list(conflicting_rules or [])
    haystack = _normalize(command)
    for rule_id, profile in RULE_PROFILES.items():
        if any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            detected.append(rule_id)
    if not detected:
        detected.extend(["read_only_mode", "project_layer_rule"])
    return _unique(detected)


def _select_rule(rule_ids: List[str]) -> str:
    known = [rule_id for rule_id in rule_ids if rule_id in RULE_PROFILES]
    if not known:
        return "read_only_mode"
    return sorted(known, key=lambda item: int(RULE_PROFILES[item]["priority"]))[0]


def constitution_status() -> Dict[str, Any]:
    return {
        "layer": "26.1",
        "name": "Agent Constitution Engine Preview",
        "status": "constitution_engine_preview_ready",
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
        "hierarchy": CONSTITUTION_HIERARCHY,
        "available_endpoints": [
            "/debug/constitution-status",
            "/debug/constitution-registry",
            "/debug/constitution-preview",
        ],
        "connected_layers": [
            "25.4 Safe Change Boundary",
            "25.7 Dev Agent Readiness Snapshot",
        ],
        "future_direction": ["Explorer Agent", "Planner Agent", "Verifier Agent", "Coordinator Agent"],
        "safety_note": "Constitution Engine only resolves rule priority in preview mode. It never writes files, applies patches, commits, pushes, deploys, or changes runtime behavior.",
    }


def constitution_registry() -> Dict[str, Any]:
    return {
        "layer": "26.1",
        "name": "Agent Constitution Registry",
        "status": "constitution_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "hierarchy": CONSTITUTION_HIERARCHY,
        "rules": [
            {
                "id": rule_id,
                "rule_source": profile["source"],
                "rule_priority": profile["priority"],
                "resolution_reason": profile["resolution_reason"],
                "aliases": profile["aliases"],
            }
            for rule_id, profile in RULE_PROFILES.items()
        ],
        "default_resolution": {
            "selected_rule": "read_only_mode",
            "resolution_reason": "constitution_rules outrank lower-priority project, memory, and historical context rules",
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
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_constitution_preview(
    command: str = "",
    rule_source: Optional[str] = None,
    conflicting_rules: Optional[List[str]] = None,
    target_area: Optional[str] = None,
) -> Dict[str, Any]:
    detected_rules = _detect_rules(command, conflicting_rules)
    if rule_source:
        for rule_id, profile in RULE_PROFILES.items():
            if _normalize(profile.get("source")) == _normalize(rule_source):
                detected_rules.append(rule_id)
                break
    detected_rules = _unique(detected_rules)
    selected_rule = _select_rule(detected_rules)
    selected_profile = RULE_PROFILES.get(selected_rule, RULE_PROFILES["read_only_mode"])
    boundary = build_change_boundary_preview(
        target_area=target_area or command or selected_rule,
        command=command or selected_rule,
    )
    readiness = layer25_status_snapshot()
    lower_priority_rules = [
        rule_id
        for rule_id in detected_rules
        if rule_id in RULE_PROFILES and int(RULE_PROFILES[rule_id]["priority"]) > int(selected_profile["priority"])
    ]

    return {
        "rule_source": selected_profile["source"],
        "rule_priority": selected_profile["priority"],
        "conflicting_rules": detected_rules,
        "selected_rule": selected_rule,
        "resolution_reason": selected_profile["resolution_reason"],
        "confidence_score": 0.92,
        "discarded_lower_priority_rules": lower_priority_rules,
        "hierarchy": CONSTITUTION_HIERARCHY,
        "boundary_signal": {
            "target_area": boundary.get("target_area"),
            "boundary_level": boundary.get("boundary_level"),
            "criticality_level": boundary.get("criticality_level"),
            "user_approval_required": boundary.get("user_approval_required"),
            "blocked_actions": boundary.get("blocked_actions", []),
        },
        "readiness_signal": {
            "readiness_score": readiness.get("readiness_score"),
            "safe_for_patch_planning": readiness.get("safe_for_patch_planning"),
            "safe_for_write_operations": readiness.get("safe_for_write_operations"),
            "recommended_next_layer": readiness.get("recommended_next_layer"),
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
        "safety_note": "This is a strict read-only constitution preview. It resolves rule priority but does not modify code, run tools, apply patches, or change runtime behavior.",
    }
