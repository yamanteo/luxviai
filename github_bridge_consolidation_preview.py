from __future__ import annotations
from typing import Any, Dict, List, Optional


GITHUB_BRIDGE_CONSOLIDATION_CAPABILITIES = [
    "bridge_overlap_detection",
    "missing_field_identification",
    "safe_action_boundary_definition",
    "bridge_health_analysis",
    "capability_gap_analysis",
    "integration_consistency_check",
    "action_permission_mapping",
    "bridge_readiness_scoring",
]

NOT_ALLOWED_OPERATIONS = [
    "commit", "push", "merge", "delete", "write", "deploy",
    "clone", "fork", "create_pr", "merge_pr",
]

RISK_LEVELS = ["safe", "warning", "high_risk", "critical"]

GITHUB_BRIDGE_CONSOLIDATION_PROFILES: Dict[str, Dict[str, Any]] = {
    "bridge_healthy": {
        "aliases": ["healthy", "saglikli", "synced", "clean", "consistent"],
        "consolidation_status": "healthy",
        "consolidation_health": "pass",
        "consolidation_summary": "GitHub bridge and project intelligence are fully aligned. No overlap detected. All fields mapped. Safe action boundary defined.",
        "bridge_overlap_analysis": {
            "overlap_count": 0,
            "overlapping_capabilities": [],
            "unique_bridge_capabilities": ["repository_inspection", "branch_analysis", "pull_request_planning"],
            "unique_intelligence_capabilities": ["repository_structure_analysis", "branch_intent_detection", "issue_context_understanding"],
        },
        "missing_field_analysis": {
            "bridge_missing_fields": [],
            "intelligence_missing_fields": [],
            "recommended_merges": [],
        },
        "safe_action_boundary": {
            "allowed_read_actions": ["inspect", "analyze", "preview", "status", "capabilities"],
            "blocked_write_actions": NOT_ALLOWED_OPERATIONS,
        },
        "health_score": 0.94,
        "risk_score": 0.06,
        "recommended_next_action": "bridge healthy — no consolidation action required",
        "read_only": True,
        "preview_only": True,
    },
    "bridge_has_overlap": {
        "aliases": ["overlap", "tekrar", "duplicate", "conflict", "double"],
        "consolidation_status": "overlap_detected",
        "consolidation_health": "warning",
        "consolidation_summary": "Overlap detected between GitHub bridge and project intelligence. Some capabilities are duplicated. Safe action boundary defined but needs review.",
        "bridge_overlap_analysis": {
            "overlap_count": 2,
            "overlapping_capabilities": ["repository_inspection", "branch_analysis"],
            "unique_bridge_capabilities": ["pull_request_planning", "commit_planning"],
            "unique_intelligence_capabilities": ["issue_context_understanding", "project_health_assessment"],
        },
        "missing_field_analysis": {
            "bridge_missing_fields": ["issue_context", "project_health"],
            "intelligence_missing_fields": ["commit_planning", "pull_request_planning"],
            "recommended_merges": ["merge repository_inspection into repository_structure_analysis"],
        },
        "safe_action_boundary": {
            "allowed_read_actions": ["inspect", "analyze", "preview", "status", "capabilities"],
            "blocked_write_actions": NOT_ALLOWED_OPERATIONS,
        },
        "health_score": 0.65,
        "risk_score": 0.35,
        "recommended_next_action": "review overlap findings and consolidate bridge capabilities",
        "read_only": True,
        "preview_only": True,
    },
}

INTEGRATION_POINTS = [
    "34.1_github_bridge_intelligence",
    "37.0_github_project_intelligence",
    "37.3_project_intelligence_core",
    "33.8_luxcode_core_status",
    "37.8_agent_core",
]


def _select_consolidation_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in GITHUB_BRIDGE_CONSOLIDATION_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "bridge_healthy"


def github_bridge_consolidation_status() -> Dict[str, Any]:
    return {
        "layer": "37.7",
        "series": "Agent Architecture",
        "name": "GitHub Bridge Consolidation Preview",
        "status": "github_bridge_consolidation_ready",
        "architecture_version": "1.0",
        "capabilities": GITHUB_BRIDGE_CONSOLIDATION_CAPABILITIES,
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "risk_model": RISK_LEVELS,
        "operation_mode": "read_only_preview_only",
        "execution_rule": "all_bridge_write_must_go_through_luxcode_pipeline",
        "connected_layers": ["34.1", "37.0", "37.3", "33.8", "37.8"],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "real_action_enabled": False,
        "real_code_modified": False,
        "file_created": False,
        "file_deleted": False,
        "command_executed": False,
        "terminal_command_executed": False,
        "github_write_performed": False,
        "github_commit_created": False,
        "github_push_performed": False,
        "deployment_triggered": False,
        "render_action_performed": False,
        "network_action_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "secret_accessed": False,
        "available_endpoints": [
            "/github-bridge-consolidation/status",
            "/github-bridge-consolidation/capabilities",
            "/github-bridge-consolidation/preview",
        ],
        "safety_note": "Read-only GitHub bridge consolidation preview. No bridge writes performed.",
    }


def github_bridge_consolidation_capabilities() -> Dict[str, Any]:
    return {
        "layer": "37.7",
        "series": "Agent Architecture",
        "name": "GitHub Bridge Consolidation Capabilities",
        "status": "github_bridge_consolidation_capabilities_ready",
        "capabilities": [
            {"name": "bridge_overlap_detection", "description": "Detect overlapping capabilities between bridges", "read_only": True},
            {"name": "missing_field_identification", "description": "Identify missing fields across bridge layers", "read_only": True},
            {"name": "safe_action_boundary_definition", "description": "Define which actions are safe vs blocked", "read_only": True},
            {"name": "bridge_health_analysis", "description": "Analyze overall bridge health and consistency", "read_only": True},
            {"name": "capability_gap_analysis", "description": "Identify gaps in bridge capability coverage", "read_only": True},
            {"name": "integration_consistency_check", "description": "Check consistency across integrated layers", "read_only": True},
            {"name": "action_permission_mapping", "description": "Map actions to permission levels", "read_only": True},
            {"name": "bridge_readiness_scoring", "description": "Score bridge readiness for operations", "read_only": True},
        ],
        "read_only": True,
        "preview_only": True,
        "real_action_enabled": False,
        "safety_note": "Capabilities are read-only. No bridge writes available.",
    }


def github_bridge_consolidation_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    repo_name: Optional[str] = None,
    task_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    context: str = "",
) -> Dict[str, Any]:
    pid = _select_consolidation_profile(target_issue, command, project_area)
    p = GITHUB_BRIDGE_CONSOLIDATION_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected

    return {
        "layer": "37.7",
        "series": "Agent Architecture",
        "module": "github_bridge_consolidation",
        "status": "preview_ready",
        "input_summary": {
            "target_issue": target_issue,
            "command": command[:100] if command else "",
            "project_area": project_area,
            "repo_name": repo_name,
            "task_type": task_type,
            "risk_level": risk_level,
        },
        "detected_intent": pid,
        "profile": p,
        "recommended_next_step": p.get("recommended_next_action"),
        "integration_points": INTEGRATION_POINTS,
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "real_action_enabled": False,
        "real_code_modified": False,
        "file_created": False,
        "file_deleted": False,
        "command_executed": False,
        "terminal_command_executed": False,
        "github_write_performed": False,
        "github_commit_created": False,
        "github_push_performed": False,
        "deployment_triggered": False,
        "render_action_performed": False,
        "network_action_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "secret_accessed": False,
        "safety_note": "Read-only preview. No bridge writes performed.",
    }
