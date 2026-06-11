from __future__ import annotations
from typing import Any, Dict, List, Optional

# lazy import: luxcode_core_status_snapshot imported inside function

WORKSPACE_CAPABILITIES = [
    "workspace_overview",
    "workspace_health",
    "workspace_structure_analysis",
    "workspace_suggestion_engine",
    "workspace_item_classification",
    "workspace_summary_generation",
    "workspace_project_mapping",
    "workspace_context_grouping",
    "workspace_priority_detection",
    "workspace_pin_recommendations",
]

WORKSPACE_CATEGORIES = [
    "project", "note", "report", "draft", "generated_document",
    "analysis", "summary", "asset", "pinned", "archived",
]

WORKSPACE_PROFILES: Dict[str, Dict[str, Any]] = {
    "workspace_empty": {
        "aliases": ["empty", "bos", "new", "yeni"],
        "workspace_status": "empty",
        "workspace_health": "pass",
        "workspace_summary": "Workspace is empty. No items detected. Ready for initial project setup.",
        "health_score": 0.95,
        "organization_score": 0.00,
        "priority_score": 0.10,
        "item_count": 0,
        "active_threads": 0,
        "pending_outputs": 0,
        "workspace_risk": "low",
        "recommended_actions": [
            "create_initial_project_structure",
            "add_first_notes_and_reports",
        ],
    },
    "workspace_small": {
        "aliases": ["small", "kucuk", "few", "az"],
        "workspace_status": "active",
        "workspace_health": "pass",
        "workspace_summary": "Small workspace with basic structure. Notes and reports present. Good organization foundation established.",
        "health_score": 0.85,
        "organization_score": 0.60,
        "priority_score": 0.30,
        "item_count": 15,
        "active_threads": 2,
        "pending_outputs": 1,
        "workspace_risk": "low",
        "recommended_actions": [
            "group_related_notes",
            "create_project_summary",
        ],
    },
    "workspace_active": {
        "aliases": ["active", "aktif", "busy", "calisiyor"],
        "workspace_status": "active",
        "workspace_health": "warning",
        "workspace_summary": "Active workspace with significant activity. Multiple projects, notes, and reports. Organization score moderate. Some items need consolidation.",
        "health_score": 0.70,
        "organization_score": 0.55,
        "priority_score": 0.65,
        "item_count": 85,
        "active_threads": 7,
        "pending_outputs": 4,
        "workspace_risk": "medium",
        "recommended_actions": [
            "group_related_notes",
            "pin_important_report",
            "archive_inactive_items",
            "merge_duplicate_drafts",
        ],
    },
    "workspace_large": {
        "aliases": ["large", "buyuk", "many", "cok"],
        "workspace_status": "active",
        "workspace_health": "warning",
        "workspace_summary": "Large workspace with many items. Organization score needs improvement. Multiple duplicate drafts detected. Archive recommended for inactive threads.",
        "health_score": 0.55,
        "organization_score": 0.40,
        "priority_score": 0.78,
        "item_count": 240,
        "active_threads": 15,
        "pending_outputs": 8,
        "workspace_risk": "medium",
        "recommended_actions": [
            "archive_inactive_items",
            "merge_duplicate_drafts",
            "create_workspace_overview",
            "create_weekly_summary",
            "pin_critical_reports",
        ],
    },
    "workspace_enterprise": {
        "aliases": ["enterprise", "kurumsal", "complex", "karmasik"],
        "workspace_status": "active",
        "workspace_health": "degraded",
        "workspace_summary": "Enterprise workspace with high complexity. Multiple projects and teams. Organization score degraded. Prioritization needed. Consolidation and archiving strongly recommended.",
        "health_score": 0.40,
        "organization_score": 0.30,
        "priority_score": 0.90,
        "item_count": 850,
        "active_threads": 35,
        "pending_outputs": 22,
        "workspace_risk": "high",
        "recommended_actions": [
            "archive_inactive_items",
            "merge_duplicate_drafts",
            "create_workspace_overview",
            "create_weekly_summary",
            "generate_project_roadmap",
            "pin_critical_reports",
            "assign_priority_levels",
            "create_team_workspace_summary",
        ],
    },
}

WORKSPACE_SUGGESTIONS = [
    {
        "suggestion_id": "group_related_notes",
        "suggestion": "Group related notes into project folders",
        "priority": "high",
        "category": "organization",
        "impact": "Improves navigation and reduces search time",
    },
    {
        "suggestion_id": "create_project_summary",
        "suggestion": "Create project summary from active notes and reports",
        "priority": "high",
        "category": "summary",
        "impact": "Provides quick project overview for stakeholders",
    },
    {
        "suggestion_id": "pin_important_report",
        "suggestion": "Pin important report to workspace header",
        "priority": "medium",
        "category": "organization",
        "impact": "Ensures critical information is immediately accessible",
    },
    {
        "suggestion_id": "archive_inactive_items",
        "suggestion": "Archive items with no activity for 30+ days",
        "priority": "medium",
        "category": "maintenance",
        "impact": "Reduces clutter and improves workspace performance",
    },
    {
        "suggestion_id": "merge_duplicate_drafts",
        "suggestion": "Merge duplicate drafts into single documents",
        "priority": "medium",
        "category": "maintenance",
        "impact": "Eliminates confusion and version conflicts",
    },
    {
        "suggestion_id": "create_workspace_overview",
        "suggestion": "Create workspace overview document",
        "priority": "low",
        "category": "summary",
        "impact": "Provides high-level workspace map",
    },
    {
        "suggestion_id": "create_weekly_summary",
        "suggestion": "Create weekly workspace activity summary",
        "priority": "low",
        "category": "report",
        "impact": "Tracks progress and identifies bottlenecks",
    },
    {
        "suggestion_id": "generate_project_roadmap",
        "suggestion": "Generate project roadmap from task outputs",
        "priority": "low",
        "category": "planning",
        "impact": "Visualizes project timeline and milestones",
    },
]

CONTEXT_GROUPS = [
    {
        "group_id": "luxcode_core_v1",
        "group_name": "LuxCode Core v1",
        "description": "Items related to LuxCode Core v1 implementation",
        "items": [
            "Layer 31 Runtime Intelligence Suite",
            "Layer 32 Failure Intelligence Suite",
            "Layer 33 LuxCode Foundation",
            "luxcode_core_status_snapshot.py",
        ],
        "item_count": 4,
        "context_type": "project",
    },
    {
        "group_id": "execution_bridges",
        "group_name": "Execution Bridges",
        "description": "Execution Bridge Suite components",
        "items": [
            "Layer 34.1 GitHub Bridge",
            "Layer 34.2 Terminal Bridge",
            "Layer 34.3 Deployment Bridge",
            "Layer 34.4 Device Action Bridge",
        ],
        "item_count": 4,
        "context_type": "feature",
    },
    {
        "group_id": "layer_reports",
        "group_name": "Layer Reports",
        "description": "All generated layer reports",
        "items": [
            "Layer29-33 reports",
            "Layer34 bridge reports",
        ],
        "item_count": 18,
        "context_type": "report_chain",
    },
]

PIN_RECOMMENDATIONS = [
    {
        "item_id": "luxcode_core_status",
        "item_name": "LuxCode Core Status Snapshot",
        "pin_score": 0.92,
        "pin_reason": "high_dependency",
        "pin_priority": "critical",
    },
    {
        "item_id": "delivery_readiness",
        "item_name": "Delivery Readiness Intelligence",
        "pin_score": 0.85,
        "pin_reason": "high_activity",
        "pin_priority": "high",
    },
    {
        "item_id": "verification_status",
        "item_name": "Verification Intelligence Status",
        "pin_score": 0.78,
        "pin_reason": "recently_updated",
        "pin_priority": "high",
    },
    {
        "item_id": "layer34_overview",
        "item_name": "Layer 34 Bridge Suite Status",
        "pin_score": 0.72,
        "pin_reason": "important_task_output",
        "pin_priority": "medium",
    },
]

PROJECT_MAPS = [
    {
        "project_name": "LuxCode Core",
        "workspace_items": 9,
        "active_threads": 3,
        "active_tasks": 2,
        "pending_outputs": 1,
        "recent_activity": "Layer 34.4 Device Action Bridge completed",
    },
    {
        "project_name": "Execution Bridges",
        "workspace_items": 4,
        "active_threads": 2,
        "active_tasks": 1,
        "pending_outputs": 1,
        "recent_activity": "Layer 34.4 Device Action Bridge completed",
    },
    {
        "project_name": "LuxCode Reports",
        "workspace_items": 18,
        "active_threads": 1,
        "active_tasks": 0,
        "pending_outputs": 0,
        "recent_activity": "Layer 34.4 report generated",
    },
]


def _select_workspace_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in WORKSPACE_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "workspace_active"


def workspace_intelligence_status() -> Dict[str, Any]:
    from luxcode_core_status_snapshot import luxcode_core_status_snapshot
    core = luxcode_core_status_snapshot()
    return {
        "layer": "34.6",
        "name": "Workspace Intelligence Preview",
        "status": "workspace_intelligence_ready",
        "workspace_version": "1.0",
        "capabilities": WORKSPACE_CAPABILITIES,
        "workspace_categories": WORKSPACE_CATEGORIES,
        "operation_mode": "read_only_preview_only",
        "profile_count": len(WORKSPACE_PROFILES),
        "suggestion_count": len(WORKSPACE_SUGGESTIONS),
        "context_group_count": len(CONTEXT_GROUPS),
        "pin_recommendation_count": len(PIN_RECOMMENDATIONS),
        "project_map_count": len(PROJECT_MAPS),
        "connected_layers": ["33.8", "34.1", "34.2", "34.3", "34.4"],
        "available_endpoints": [
            "/workspace-intelligence/status",
            "/workspace-intelligence/capabilities",
            "/workspace-intelligence/preview",
            "/workspace-intelligence/group-preview",
            "/workspace-intelligence/suggestion-preview",
            "/workspace-intelligence/project-map",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "workspace_write": False,
        "database_write": False,
        "cloud_write": False,
        "delete_operation": False,
        "rename_operation": False,
        "file_modification": False,
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
        "safety_note": "Read-only workspace intelligence preview. No actual workspace modifications performed.",
    }


def workspace_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "34.6",
        "name": "Workspace Intelligence Capabilities",
        "status": "workspace_capabilities_ready",
        "capabilities": [
            {"name": "workspace_overview", "description": "Generate comprehensive workspace overview", "read_only": True},
            {"name": "workspace_health", "description": "Assess workspace health and organization score", "read_only": True},
            {"name": "workspace_structure_analysis", "description": "Analyze workspace structure and category distribution", "read_only": True},
            {"name": "workspace_suggestion_engine", "description": "Generate workspace improvement suggestions", "read_only": True},
            {"name": "workspace_item_classification", "description": "Classify workspace items by category", "read_only": True},
            {"name": "workspace_summary_generation", "description": "Generate workspace summaries", "read_only": True},
            {"name": "workspace_project_mapping", "description": "Map workspace items to projects", "read_only": True},
            {"name": "workspace_context_grouping", "description": "Group related workspace items by context", "read_only": True},
            {"name": "workspace_priority_detection", "description": "Detect priority levels of workspace items", "read_only": True},
            {"name": "workspace_pin_recommendations", "description": "Recommend items to pin for quick access", "read_only": True},
        ],
        "workspace_categories": WORKSPACE_CATEGORIES,
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def workspace_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_workspace_profile(target_issue, command, project_area)
    p = WORKSPACE_PROFILES[pid]
    return {
        "workspace_id": pid,
        "workspace_status": p["workspace_status"],
        "workspace_health": p["workspace_health"],
        "workspace_summary": p.get("workspace_summary"),
        "health_score": p.get("health_score"),
        "organization_score": p.get("organization_score"),
        "priority_score": p.get("priority_score"),
        "item_count": p.get("item_count"),
        "active_threads": p.get("active_threads"),
        "pending_outputs": p.get("pending_outputs"),
        "workspace_risk": p.get("workspace_risk"),
        "recommended_actions": p.get("recommended_actions", []),
        "read_only": True,
        "preview_only": True,
    }


def workspace_intelligence_group_preview(
    context_type: Optional[str] = None,
) -> Dict[str, Any]:
    if context_type:
        groups = [g for g in CONTEXT_GROUPS if g.get("context_type") == context_type]
    else:
        groups = CONTEXT_GROUPS
    return {
        "context_groups": groups,
        "group_count": len(groups),
        "context_types_available": list(set(g.get("context_type") for g in CONTEXT_GROUPS)),
        "read_only": True,
        "preview_only": True,
    }


def workspace_intelligence_suggestion_preview(
    priority: Optional[str] = None,
) -> Dict[str, Any]:
    if priority:
        suggestions = [s for s in WORKSPACE_SUGGESTIONS if s.get("priority") == priority]
    else:
        suggestions = WORKSPACE_SUGGESTIONS
    return {
        "suggestions": suggestions,
        "suggestion_count": len(suggestions),
        "priority_levels_available": list(set(s.get("priority") for s in WORKSPACE_SUGGESTIONS)),
        "categories_available": list(set(s.get("category") for s in WORKSPACE_SUGGESTIONS)),
        "read_only": True,
        "preview_only": True,
    }


def workspace_intelligence_project_map() -> Dict[str, Any]:
    return {
        "project_maps": PROJECT_MAPS,
        "project_count": len(PROJECT_MAPS),
        "total_active_threads": sum(p.get("active_threads", 0) for p in PROJECT_MAPS),
        "total_active_tasks": sum(p.get("active_tasks", 0) for p in PROJECT_MAPS),
        "total_pending_outputs": sum(p.get("pending_outputs", 0) for p in PROJECT_MAPS),
        "read_only": True,
        "preview_only": True,
    }
