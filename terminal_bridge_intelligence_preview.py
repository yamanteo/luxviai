from __future__ import annotations
from typing import Any, Dict, List, Optional

from github_bridge_intelligence_preview import (
    github_bridge_intelligence_registry,
)
from luxcode_core_status_snapshot import (
    luxcode_core_status_snapshot,
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


TERMINAL_BRIDGE_CAPABILITIES = [
    "environment_inspection",
    "dependency_inspection",
    "toolchain_analysis",
    "command_planning",
    "command_validation",
    "build_planning",
    "test_planning",
    "installation_planning",
]

SUPPORTED_DOMAINS = [
    "Python", "NodeJS", "npm", "pip",
    "Docker", "Git",
    "Linux", "Windows", "macOS",
    "Build Systems", "Package Managers",
]

NOT_ALLOWED_OPERATIONS = [
    "execute_command", "install_package", "delete_file",
    "modify_file", "restart_system", "shutdown_system",
    "sleep_system", "deploy",
]

RISK_LEVELS = ["safe", "warning", "high_risk", "critical"]

TERMINAL_BRIDGE_PROFILES: Dict[str, Dict[str, Any]] = {
    "clean_environment": {
        "aliases": ["clean", "temiz", "healthy", "ready", "hazir"],
        "environment_status": "healthy",
        "environment_health": "pass",
        "environment_summary": "Terminal environment is healthy. Python, NodeJS, Git, Docker toolchains all available. Dependencies up to date. No security issues detected. Ready for command planning.",
        "toolchain_status": "available",
        "toolchain_readiness": "ready",
        "dependency_status": "healthy",
        "dependency_summary": {
            "python_version": "3.13",
            "node_version": "24.16",
            "git_version": "2.54",
            "docker_available": True,
            "pip_available": True,
            "npm_available": True,
            "outdated_packages": 2,
            "missing_packages": 0,
        },
        "command_risk_score": 0.05,
        "command_readiness": "ready",
        "command_preview": {
            "suggested_commands": [
                "python -m pip install --upgrade pip",
                "npm audit fix",
            ],
            "risk_assessment": "safe",
        },
        "recommended_commands": [
            "python -m pip install --upgrade pip",
            "npm audit fix",
        ],
        "recommended_next_action": "environment clean — proceed with command planning for target task",
        "read_only": True,
        "preview_only": True,
    },
    "missing_dependencies": {
        "aliases": ["missing", "eksik", "dependency", "bagimlilik"],
        "environment_status": "warning",
        "environment_health": "warning",
        "environment_summary": "Environment has missing dependencies. 3 packages required but not installed. 2 packages outdated. Command planning limited until dependencies resolved.",
        "toolchain_status": "available",
        "toolchain_readiness": "conditional",
        "dependency_status": "degraded",
        "dependency_summary": {
            "python_version": "3.13",
            "node_version": "24.16",
            "git_version": "2.54",
            "docker_available": True,
            "pip_available": True,
            "npm_available": True,
            "outdated_packages": 2,
            "missing_packages": 3,
            "missing_packages_list": ["pytest>=7.0", "black", "ruff"],
        },
        "command_risk_score": 0.35,
        "command_readiness": "conditional",
        "command_preview": {
            "suggested_commands": [
                "pip install pytest black ruff",
            ],
            "risk_assessment": "warning",
            "risk_factors": ["network_required_for_install", "version_pinning_recommended"],
        },
        "recommended_commands": [
            "pip install pytest black ruff",
        ],
        "recommended_next_action": "install missing dependencies via pip before proceeding with command planning",
        "read_only": True,
        "preview_only": True,
    },
    "outdated_toolchain": {
        "aliases": ["outdated", "eski", "old", "guncel degil"],
        "environment_status": "warning",
        "environment_health": "warning",
        "environment_summary": "Environment has outdated toolchain components. Python version behind latest. NodeJS LTS available but not installed. Git version adequate. Docker Engine update available.",
        "toolchain_status": "outdated",
        "toolchain_readiness": "conditional",
        "dependency_status": "warning",
        "dependency_summary": {
            "python_version": "3.11",
            "python_latest": "3.13",
            "node_version": "22.0",
            "node_lts": "24.16",
            "git_version": "2.50",
            "docker_available": True,
            "docker_update_available": True,
            "pip_available": True,
            "npm_available": True,
            "outdated_packages": 5,
            "missing_packages": 1,
        },
        "command_risk_score": 0.42,
        "command_readiness": "conditional",
        "command_preview": {
            "suggested_commands": [
                "python -m pip install --upgrade pip setuptools wheel",
                "npm update -g",
            ],
            "risk_assessment": "warning",
            "risk_factors": ["version_mismatch_risk", "major_version_upgrade"],
        },
        "recommended_commands": [
            "python -m pip install --upgrade pip",
            "npm update -g",
        ],
        "recommended_next_action": "update toolchain components before critical command execution",
        "read_only": True,
        "preview_only": True,
    },
    "high_risk_command_detected": {
        "aliases": ["high risk", "riskli", "dangerous", "tehlikeli"],
        "environment_status": "degraded",
        "environment_health": "degraded",
        "environment_summary": "High risk command pattern detected. Command attempts to modify system configuration. Requires confirmation. Environment ready but command blocked until verification.",
        "toolchain_status": "available",
        "toolchain_readiness": "ready",
        "dependency_status": "healthy",
        "dependency_summary": {
            "python_version": "3.13",
            "node_version": "24.16",
            "git_version": "2.54",
            "docker_available": True,
            "pip_available": True,
            "npm_available": True,
            "outdated_packages": 1,
            "missing_packages": 0,
        },
        "command_risk_score": 0.85,
        "command_readiness": "blocked",
        "command_preview": {
            "suggested_commands": [
                "sudo rm -rf /var/log — BLOCKED: destructive",
                "docker system prune -af — BLOCKED: destructive",
            ],
            "risk_assessment": "critical",
            "risk_factors": ["destructive_operation", "system_modification", "no_rollback"],
        },
        "recommended_commands": [
            "use sandbox repair engine for destructive operations",
            "run destructive commands only inside sandbox",
        ],
        "recommended_next_action": "high risk command blocked — use Sandbox Repair engine for destructive operations",
        "read_only": True,
        "preview_only": True,
    },
    "build_environment_ready": {
        "aliases": ["build", "derleme", "compile", "install", "yukleme"],
        "environment_status": "healthy",
        "environment_health": "pass",
        "environment_summary": "Build environment ready. All build toolchains available. Dependencies resolved. Build cache populated. Test runners available. Ready for build and test command planning.",
        "toolchain_status": "available",
        "toolchain_readiness": "ready",
        "dependency_status": "healthy",
        "dependency_summary": {
            "python_version": "3.13",
            "node_version": "24.16",
            "git_version": "2.54",
            "build_tools": ["setuptools", "wheel", "build"],
            "test_runners": ["pytest", "unittest"],
            "docker_available": True,
            "pip_available": True,
            "npm_available": True,
            "outdated_packages": 0,
            "missing_packages": 0,
        },
        "command_risk_score": 0.08,
        "command_readiness": "ready",
        "command_preview": {
            "suggested_commands": [
                "python -m build",
                "pytest tests/",
                "npm run build",
            ],
            "risk_assessment": "safe",
        },
        "recommended_commands": [
            "python -m build && pytest tests/",
            "npm run build",
        ],
        "recommended_next_action": "build environment ready — proceed with build and test commands",
        "read_only": True,
        "preview_only": True,
    },
}


def _select_terminal_bridge_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in TERMINAL_BRIDGE_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "clean_environment"


def terminal_bridge_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "34.2",
        "name": "Terminal Bridge Intelligence Preview",
        "status": "terminal_bridge_intelligence_ready",
        "bridge_version": "1.0",
        "capabilities": TERMINAL_BRIDGE_CAPABILITIES,
        "supported_domains": SUPPORTED_DOMAINS,
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "risk_model": RISK_LEVELS,
        "operation_mode": "read_only_preview_only",
        "execution_rule": "all_command_execution_must_go_through_luxcode_sandbox",
        "connected_layers": ["34.1", "33.8", "33.7", "33.6", "33.5"],
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
            "/terminal-bridge/status",
            "/terminal-bridge/capabilities",
            "/terminal-bridge/preview",
        ],
        "safety_note": "Read-only terminal bridge intelligence preview. No actual terminal commands executed.",
    }


def terminal_bridge_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "34.2",
        "name": "Terminal Bridge Intelligence Capabilities",
        "status": "terminal_bridge_capabilities_ready",
        "capabilities": [
            {
                "name": "environment_inspection",
                "description": "Inspect terminal environment including OS, shell, paths, and config",
                "read_only": True,
            },
            {
                "name": "dependency_inspection",
                "description": "Inspect installed packages, versions, and dependencies across all domains",
                "read_only": True,
            },
            {
                "name": "toolchain_analysis",
                "description": "Analyze available toolchains, versions, and update status",
                "read_only": True,
            },
            {
                "name": "command_planning",
                "description": "Plan terminal commands based on task requirements and environment state",
                "read_only": True,
            },
            {
                "name": "command_validation",
                "description": "Validate commands against risk model before execution",
                "read_only": True,
            },
            {
                "name": "build_planning",
                "description": "Plan build commands based on project structure and toolchain availability",
                "read_only": True,
            },
            {
                "name": "test_planning",
                "description": "Plan test commands based on test framework availability and project config",
                "read_only": True,
            },
            {
                "name": "installation_planning",
                "description": "Plan installation commands with dependency resolution preview",
                "read_only": True,
            },
        ],
        "supported_domains": SUPPORTED_DOMAINS,
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "risk_model": RISK_LEVELS,
        "operation_mode": "read_only_preview_only",
        "integration_layers": ["34.1", "33.8", "33.7", "33.6", "33.5"],
        "read_only": True,
        "preview_only": True,
    }


def terminal_bridge_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in TERMINAL_BRIDGE_PROFILES.items():
        items.append(
            {
                "profile_id": pid,
                "environment_status": p["environment_status"],
                "environment_health": p["environment_health"],
                "toolchain_readiness": p.get("toolchain_readiness"),
                "dependency_status": p.get("dependency_status"),
                "command_risk_score": p.get("command_risk_score"),
                "command_readiness": p.get("command_readiness"),
                "risk_assessment": p.get("command_preview", {}).get("risk_assessment"),
            }
        )
    return {
        "layer": "34.2",
        "name": "Terminal Bridge Intelligence Registry",
        "status": "terminal_bridge_intelligence_registry_ready",
        "profile_count": len(items),
        "profiles": items,
        "aggregate": {
            "min_risk_score": min(i["command_risk_score"] for i in items) if items else 0.0,
            "max_risk_score": max(i["command_risk_score"] for i in items) if items else 0.0,
            "avg_risk_score": round(
                sum(i["command_risk_score"] for i in items) / len(items), 2
            ) if items else 0.0,
        },
        "read_only": True,
        "preview_only": True,
    }


def _build_integration_signals(
    target: str, command: str, project_area: str, related_layer: str
) -> Dict[str, Any]:
    L = related_layer or "Layer 34.2"
    github_reg = github_bridge_intelligence_registry()
    core_status = luxcode_core_status_snapshot()
    delivery_reg = delivery_readiness_intelligence_registry()
    verification_reg = verification_intelligence_registry()
    sandbox_reg = sandbox_repair_intelligence_registry()

    return {
        "layer34_1_github_bridge": {
            "profile_count": github_reg.get("profile_count"),
            "avg_risk_score": github_reg.get("aggregate", {}).get("avg_risk_score"),
        },
        "luxcode_core_status": {
            "core_version": core_status.get("core_version"),
            "core_health_score": core_status.get("core_health_score"),
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


def build_terminal_bridge_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_terminal_bridge_profile(target_issue, command, project_area)
    p = TERMINAL_BRIDGE_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 34.2"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "environment_status": p["environment_status"],
        "environment_health": p["environment_health"],
        "environment_summary": p.get("environment_summary"),
        "toolchain_status": p.get("toolchain_status"),
        "toolchain_readiness": p.get("toolchain_readiness"),
        "dependency_status": p.get("dependency_status"),
        "dependency_summary": p.get("dependency_summary", {}),
        "command_risk_score": p.get("command_risk_score"),
        "command_readiness": p.get("command_readiness"),
        "command_preview": p.get("command_preview", {}),
        "recommended_commands": p.get("recommended_commands", []),
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
        "safety_note": "Read-only terminal bridge intelligence preview. No actual terminal commands executed.",
    }
