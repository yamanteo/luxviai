from __future__ import annotations
from typing import Any, Dict, List, Optional


GITHUB_PROJECT_INTELLIGENCE_CAPABILITIES = [
    "repository_structure_analysis",
    "branch_intent_detection",
    "pull_request_context_assembly",
    "issue_context_understanding",
    "commit_history_analysis",
    "project_health_assessment",
    "github_risk_evaluation",
    "project_readiness_scoring",
]

NOT_ALLOWED_OPERATIONS = [
    "commit", "push", "merge", "delete", "write", "deploy", "clone", "fork",
]

RISK_LEVELS = ["safe", "warning", "high_risk", "critical"]

GITHUB_PROJECT_PROFILES: Dict[str, Dict[str, Any]] = {
    "healthy_project": {
        "aliases": ["healthy", "saglikli", "stable", "clean", "ready"],
        "project_status": "healthy",
        "project_health": "pass",
        "project_summary": "GitHub project is healthy. Repository structure is clean. Branches are in sync. No critical issues open. CI/CD pipeline green.",
        "repository_analysis": {
            "default_branch": "main",
            "branch_count": 4,
            "active_branches": 2,
            "stale_branches": 1,
            "protected_branches": ["main", "develop"],
            "open_prs": 1,
            "recent_commits_7d": 12,
        },
        "branch_intent": {
            "primary_intent": "feature_development",
            "active_intent": "implement_new_api_endpoint",
            "detected_pattern": "feature_branch_workflow",
        },
        "project_readiness": "ready",
        "project_risk_score": 0.12,
        "recommended_next_action": "project healthy — proceed with change planning",
        "read_only": True,
        "preview_only": True,
    },
    "project_with_conflicts": {
        "aliases": ["conflict", "conflicts", "merge conflict", "celiski", "diverged"],
        "project_status": "warning",
        "project_health": "warning",
        "project_summary": "Project has merge conflicts between feature and main branch. CI failing on feature branch. Requires conflict resolution before further planning.",
        "repository_analysis": {
            "default_branch": "main",
            "branch_count": 5,
            "active_branches": 3,
            "stale_branches": 1,
            "diverged_branches": 1,
            "protected_branches": ["main", "develop"],
            "open_prs": 2,
            "recent_commits_7d": 8,
        },
        "branch_intent": {
            "primary_intent": "conflict_resolution",
            "active_intent": "resolve_feature_main_divergence",
            "detected_pattern": "conflict_detected",
        },
        "project_readiness": "blocked",
        "project_risk_score": 0.68,
        "recommended_next_action": "resolve merge conflicts before proceeding with change planning",
        "read_only": True,
        "preview_only": True,
    },
}

INTEGRATION_POINTS = [
    "34.1_github_bridge_intelligence",
    "33.8_luxcode_core_status",
    "33.7_delivery_readiness",
    "33.6_verification_intelligence",
    "37.7_github_bridge_consolidation",
    "37.8_agent_core",
]


def _select_project_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in GITHUB_PROJECT_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "healthy_project"


def github_project_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "37.0",
        "series": "Agent Architecture",
        "name": "GitHub Project Intelligence Preview",
        "status": "github_project_intelligence_ready",
        "architecture_version": "1.0",
        "capabilities": GITHUB_PROJECT_INTELLIGENCE_CAPABILITIES,
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "risk_model": RISK_LEVELS,
        "operation_mode": "read_only_preview_only",
        "execution_rule": "all_github_write_operations_must_go_through_luxcode_sandbox",
        "connected_layers": ["34.1", "33.8", "37.7", "37.8"],
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
            "/github-project-intelligence/status",
            "/github-project-intelligence/capabilities",
            "/github-project-intelligence/preview",
        ],
        "safety_note": "Read-only GitHub project intelligence preview. No actual GitHub write operations performed.",
    }


def github_project_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "37.0",
        "series": "Agent Architecture",
        "name": "GitHub Project Intelligence Capabilities",
        "status": "github_project_intelligence_capabilities_ready",
        "capabilities": [
            {
                "name": "repository_structure_analysis",
                "description": "Analyze repository structure, branch topology, and file organization",
                "read_only": True,
            },
            {
                "name": "branch_intent_detection",
                "description": "Detect branch purpose and development intent from naming and history",
                "read_only": True,
            },
            {
                "name": "pull_request_context_assembly",
                "description": "Assemble full context for an open or planned pull request",
                "read_only": True,
            },
            {
                "name": "issue_context_understanding",
                "description": "Understand issue context, linked PRs, and resolution path",
                "read_only": True,
            },
            {
                "name": "commit_history_analysis",
                "description": "Analyze recent commit history for patterns, risk, and intent",
                "read_only": True,
            },
            {
                "name": "project_health_assessment",
                "description": "Assess overall GitHub project health from multiple signals",
                "read_only": True,
            },
            {
                "name": "github_risk_evaluation",
                "description": "Evaluate risk factors in GitHub project state",
                "read_only": True,
            },
            {
                "name": "project_readiness_scoring",
                "description": "Score project readiness for change operations",
                "read_only": True,
            },
        ],
        "read_only": True,
        "preview_only": True,
        "real_action_enabled": False,
        "safety_note": "Capabilities are read-only. No GitHub write operations available.",
    }


def github_project_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    repo_name: Optional[str] = None,
    task_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    context: str = "",
) -> Dict[str, Any]:
    pid = _select_project_profile(target_issue, command, project_area)
    p = GITHUB_PROJECT_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected

    return {
        "layer": "37.0",
        "series": "Agent Architecture",
        "module": "github_project_intelligence",
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
        "capability_match": _detect_capability_match(cmd, pid),
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
        "safety_note": "Read-only preview. No GitHub write operations performed.",
    }


def _detect_capability_match(command: str, profile_id: str) -> List[str]:
    matched = []
    cmd_lower = command.lower()
    for cap in GITHUB_PROJECT_INTELLIGENCE_CAPABILITIES:
        words = cap.replace("_", " ")
        if any(w in cmd_lower for w in words.split()):
            matched.append(cap)
    if not matched:
        matched = ["repository_structure_analysis"]
    return matched
