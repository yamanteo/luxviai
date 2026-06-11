from __future__ import annotations
from typing import Any, Dict, List, Optional

from luxcode_core_status_snapshot import (
    luxcode_core_status_snapshot,
    luxcode_core_health,
    luxcode_core_readiness,
)
from delivery_readiness_intelligence_preview import (
    delivery_readiness_intelligence_registry,
)
from verification_intelligence_preview import (
    verification_intelligence_registry,
)
from sandbox_repair_intelligence_preview import (
    sandbox_repair_intelligence_registry,
)


GITHUB_BRIDGE_CAPABILITIES = [
    "repository_inspection",
    "repository_health_analysis",
    "branch_analysis",
    "pull_request_planning",
    "commit_planning",
    "repository_dependency_mapping",
    "repository_risk_analysis",
    "repository_readiness_analysis",
]

NOT_ALLOWED_OPERATIONS = [
    "commit", "push", "merge", "delete", "write", "deploy",
]

GITHUB_BRIDGE_PROFILES: Dict[str, Dict[str, Any]] = {
    "healthy_repository": {
        "aliases": ["healthy", "saglikli", "stable", "stable", "clean"],
        "repository_status": "healthy",
        "repository_health": "pass",
        "repository_summary": "Repository is healthy. All branches are in sync. No open critical issues. Dependencies are up to date. CI/CD pipeline green. Ready for change planning.",
        "branch_analysis": {
            "default_branch": "main",
            "branch_count": 3,
            "active_branches": 1,
            "stale_branches": 1,
            "diverged_branches": 0,
            "protected_branches": ["main"],
        },
        "branch_recommendations": [
            "clean_up_stale_branch_feature_old",
        ],
        "pull_request_readiness": "ready",
        "commit_readiness": "ready",
        "repository_risk_score": 0.15,
        "repository_dependency_summary": {
            "dependencies": 42,
            "outdated": 2,
            "vulnerable": 0,
            "dev_dependencies": 18,
        },
        "repository_change_summary": {
            "recent_commits_7d": 14,
            "open_prs": 2,
            "recently_merged": 3,
            "uncommitted_changes": 0,
        },
        "recommended_next_action": "repository healthy — proceed with change planning from LuxCode Core",
        "read_only": True,
        "preview_only": True,
    },
    "repository_with_unmerged_changes": {
        "aliases": ["unmerged", "uncommitted", "bekleyen", "dirty", "changes"],
        "repository_status": "warning",
        "repository_health": "warning",
        "repository_summary": "Repository has uncommitted changes. Working tree is not clean. Changes pending in 2 files. Recommending commit or stash before bridge operations.",
        "branch_analysis": {
            "default_branch": "main",
            "branch_count": 4,
            "active_branches": 2,
            "stale_branches": 1,
            "diverged_branches": 1,
            "protected_branches": ["main"],
        },
        "branch_recommendations": [
            "commit_or_stash_uncommitted_changes",
            "rebase_diverged_feature_branch",
        ],
        "pull_request_readiness": "not_ready",
        "commit_readiness": "pending_changes",
        "repository_risk_score": 0.45,
        "repository_dependency_summary": {
            "dependencies": 42,
            "outdated": 3,
            "vulnerable": 1,
            "dev_dependencies": 18,
        },
        "repository_change_summary": {
            "recent_commits_7d": 10,
            "open_prs": 3,
            "recently_merged": 2,
            "uncommitted_changes": 2,
        },
        "recommended_next_action": "commit or stash uncommitted changes before proceeding with bridge operations",
        "read_only": True,
        "preview_only": True,
    },
    "repository_with_diverged_branches": {
        "aliases": ["diverged", "ayrilmis", "conflict", "conflict", "merge"],
        "repository_status": "degraded",
        "repository_health": "degraded",
        "repository_summary": "Repository has diverged branches. Feature branch behind main by 8 commits with 1 potential merge conflict. Automated rebase not recommended without verification gate.",
        "branch_analysis": {
            "default_branch": "main",
            "branch_count": 5,
            "active_branches": 3,
            "stale_branches": 2,
            "diverged_branches": 2,
            "protected_branches": ["main", "develop"],
        },
        "branch_recommendations": [
            "rebase_feature_branch_via_sandbox_not_directly",
            "resolve_merge_conflict_in_working_clone",
            "clean_up_stale_branches",
        ],
        "pull_request_readiness": "conditional",
        "commit_readiness": "ready",
        "repository_risk_score": 0.62,
        "repository_dependency_summary": {
            "dependencies": 44,
            "outdated": 4,
            "vulnerable": 1,
            "dev_dependencies": 19,
        },
        "repository_change_summary": {
            "recent_commits_7d": 18,
            "open_prs": 4,
            "recently_merged": 5,
            "uncommitted_changes": 0,
        },
        "recommended_next_action": "rebase diverged branches via Sandbox Repair engine — never directly on production branches",
        "read_only": True,
        "preview_only": True,
    },
    "repository_with_vulnerable_dependencies": {
        "aliases": ["vulnerable", "guvenlik", "security", "cve", "risk"],
        "repository_status": "degraded",
        "repository_health": "degraded",
        "repository_summary": "Repository has vulnerable dependencies. 2 CVEs detected in production dependencies. 1 high severity. Urgent remediation recommended via Sandbox Repair before any bridge operations.",
        "branch_analysis": {
            "default_branch": "main",
            "branch_count": 4,
            "active_branches": 2,
            "stale_branches": 1,
            "diverged_branches": 1,
            "protected_branches": ["main"],
        },
        "branch_recommendations": [
            "remediate_vulnerable_dependencies_via_sandbox",
            "run_dependency_verification_gate",
            "do_not_merge_until_dependencies_cleared",
        ],
        "pull_request_readiness": "blocked",
        "commit_readiness": "blocked",
        "repository_risk_score": 0.78,
        "repository_dependency_summary": {
            "dependencies": 42,
            "outdated": 6,
            "vulnerable": 2,
            "high_severity_vulnerabilities": 1,
            "dev_dependencies": 18,
        },
        "repository_change_summary": {
            "recent_commits_7d": 8,
            "open_prs": 1,
            "recently_merged": 1,
            "uncommitted_changes": 0,
        },
        "recommended_next_action": "remediate vulnerable dependencies via Sandbox Repair before any pull request or commit planning",
        "read_only": True,
        "preview_only": True,
    },
    "repository_ready_for_release": {
        "aliases": ["release", "surum", "delivery", "ready", "approved"],
        "repository_status": "ready",
        "repository_health": "pass",
        "repository_summary": "Repository ready for release. All branches in sync. Dependencies up to date. CI/CD green. Pull requests reviewed and approved. Ready for Delivery Readiness engine handoff.",
        "branch_analysis": {
            "default_branch": "main",
            "branch_count": 3,
            "active_branches": 1,
            "stale_branches": 0,
            "diverged_branches": 0,
            "protected_branches": ["main", "develop", "release"],
        },
        "branch_recommendations": [],
        "pull_request_readiness": "ready",
        "commit_readiness": "ready",
        "repository_risk_score": 0.08,
        "repository_dependency_summary": {
            "dependencies": 42,
            "outdated": 0,
            "vulnerable": 0,
            "dev_dependencies": 18,
        },
        "repository_change_summary": {
            "recent_commits_7d": 6,
            "open_prs": 0,
            "recently_merged": 2,
            "uncommitted_changes": 0,
        },
        "recommended_next_action": "repository ready for release — handoff to Delivery Readiness engine",
        "read_only": True,
        "preview_only": True,
    },
}


def _select_github_bridge_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in GITHUB_BRIDGE_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "healthy_repository"


def github_bridge_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "34.1",
        "name": "GitHub Bridge Intelligence Preview",
        "status": "github_bridge_intelligence_ready",
        "bridge_version": "1.0",
        "capabilities": GITHUB_BRIDGE_CAPABILITIES,
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "operation_mode": "read_only_preview_only",
        "execution_rule": "all_changes_must_go_through_luxcode_sandbox",
        "connected_layers": ["33.8", "33.7", "33.6", "33.5"],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
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
        "available_endpoints": [
            "/github-bridge/status",
            "/github-bridge/capabilities",
            "/github-bridge/preview",
        ],
        "safety_note": "Read-only GitHub bridge intelligence preview. No actual GitHub operations performed.",
    }


def github_bridge_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "34.1",
        "name": "GitHub Bridge Intelligence Capabilities",
        "status": "github_bridge_capabilities_ready",
        "capabilities": [
            {
                "name": "repository_inspection",
                "description": "Inspect repository structure, branches, and commit history",
                "read_only": True,
            },
            {
                "name": "repository_health_analysis",
                "description": "Analyze repository health including branch sync, dependency status, and CI/CD state",
                "read_only": True,
            },
            {
                "name": "branch_analysis",
                "description": "Analyze branch structure, divergence, and protection rules",
                "read_only": True,
            },
            {
                "name": "pull_request_planning",
                "description": "Plan pull requests based on Change Planning Intelligence recommendations",
                "read_only": True,
            },
            {
                "name": "commit_planning",
                "description": "Plan commit strategy based on Change Memory Intelligence patterns",
                "read_only": True,
            },
            {
                "name": "repository_dependency_mapping",
                "description": "Map repository dependencies from Dependency Intelligence",
                "read_only": True,
            },
            {
                "name": "repository_risk_analysis",
                "description": "Analyze repository-level risks from combined intelligence layers",
                "read_only": True,
            },
            {
                "name": "repository_readiness_analysis",
                "description": "Analyze repository readiness using Delivery Readiness Intelligence",
                "read_only": True,
            },
        ],
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "operation_mode": "read_only_preview_only",
        "integration_layers": ["33.8", "33.7", "33.6", "33.5"],
        "read_only": True,
        "preview_only": True,
    }


def github_bridge_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in GITHUB_BRIDGE_PROFILES.items():
        items.append(
            {
                "profile_id": pid,
                "repository_status": p["repository_status"],
                "repository_health": p["repository_health"],
                "branch_count": p.get("branch_analysis", {}).get("branch_count"),
                "pull_request_readiness": p.get("pull_request_readiness"),
                "commit_readiness": p.get("commit_readiness"),
                "repository_risk_score": p.get("repository_risk_score"),
                "dependency_count": p.get("repository_dependency_summary", {}).get("dependencies"),
                "vulnerable_count": p.get("repository_dependency_summary", {}).get("vulnerable", 0),
                "uncommitted_changes": p.get("repository_change_summary", {}).get("uncommitted_changes", 0),
            }
        )
    return {
        "layer": "34.1",
        "name": "GitHub Bridge Intelligence Registry",
        "status": "github_bridge_intelligence_registry_ready",
        "profile_count": len(items),
        "profiles": items,
        "aggregate": {
            "min_risk_score": min(i["repository_risk_score"] for i in items) if items else 0.0,
            "max_risk_score": max(i["repository_risk_score"] for i in items) if items else 0.0,
            "avg_risk_score": round(
                sum(i["repository_risk_score"] for i in items) / len(items), 2
            ) if items else 0.0,
            "total_vulnerabilities": sum(i["vulnerable_count"] for i in items),
        },
        "read_only": True,
        "preview_only": True,
    }


def _build_integration_signals(
    target: str, command: str, project_area: str, related_layer: str
) -> Dict[str, Any]:
    L = related_layer or "Layer 34.1"
    core_status = luxcode_core_status_snapshot()
    delivery_reg = delivery_readiness_intelligence_registry()
    verification_reg = verification_intelligence_registry()
    sandbox_reg = sandbox_repair_intelligence_registry()

    return {
        "luxcode_core_status": {
            "core_version": core_status.get("core_version"),
            "core_health_score": core_status.get("core_health_score"),
            "core_readiness_score": core_status.get("core_readiness_score"),
            "endpoint_count": core_status.get("endpoint_count"),
        },
        "layer33_7_delivery_readiness": {
            "delivery_count": delivery_reg.get("delivery_count"),
            "overall_delivery_score": delivery_reg.get("overall_delivery_score"),
        },
        "layer33_6_verification_intelligence": {
            "verification_count": verification_reg.get("verification_count"),
            "overall_verification_score": verification_reg.get("overall_verification_score"),
        },
        "layer33_5_sandbox_repair_intelligence": {
            "repair_count": sandbox_reg.get("repair_count"),
            "overall_repair_score": sandbox_reg.get("overall_repair_score"),
        },
    }


def build_github_bridge_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_github_bridge_profile(target_issue, command, project_area)
    p = GITHUB_BRIDGE_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 34.1"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "repository_status": p["repository_status"],
        "repository_health": p["repository_health"],
        "repository_summary": p.get("repository_summary"),
        "branch_analysis": p.get("branch_analysis", {}),
        "branch_recommendations": p.get("branch_recommendations", []),
        "pull_request_readiness": p.get("pull_request_readiness"),
        "commit_readiness": p.get("commit_readiness"),
        "repository_risk_score": p.get("repository_risk_score"),
        "repository_dependency_summary": p.get("repository_dependency_summary", {}),
        "repository_change_summary": p.get("repository_change_summary", {}),
        "recommended_next_action": p.get("recommended_next_action"),
        "runtime_signals": integration,
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
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
        "safety_note": "Read-only GitHub bridge intelligence preview. No actual GitHub operations performed.",
    }
