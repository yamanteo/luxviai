from __future__ import annotations
from typing import Any, Dict, List, Optional


TERMINAL_INTELLIGENCE_CAPABILITIES = [
    "command_intent_classification",
    "command_risk_analysis",
    "sandbox_requirement_detection",
    "command_category_identification",
    "safe_alternative_suggestion",
    "command_readiness_scoring",
    "terminal_context_assembly",
    "environment_awareness",
]

NOT_ALLOWED_OPERATIONS = [
    "execute_command", "run_script", "install_package", "delete_file",
    "modify_file", "restart_system", "shutdown_system", "deploy",
]

RISK_LEVELS = ["safe", "warning", "high_risk", "critical"]
COMMAND_CATEGORIES = ["build", "test", "install", "analyze", "inspect", "clean", "run", "debug"]

TERMINAL_INTELLIGENCE_PROFILES: Dict[str, Dict[str, Any]] = {
    "safe_command": {
        "aliases": ["safe", "guvenli", "inspect", "check", "status"],
        "command_status": "safe",
        "command_health": "pass",
        "command_summary": "Command is safe to analyze. Read-only inspection command with no side effects. Suitable for preview.",
        "risk_assessment": "safe",
        "risk_score": 0.05,
        "sandbox_required": False,
        "command_category": "inspect",
        "safe_alternatives": [],
        "recommended_next_action": "safe command — proceed with preview analysis",
        "read_only": True,
        "preview_only": True,
    },
    "warning_command": {
        "aliases": ["warning", "uyari", "modify", "write", "change"],
        "command_status": "warning",
        "command_health": "warning",
        "command_summary": "Command has write or modify intent. Requires sandbox isolation. Read-only preview available.",
        "risk_assessment": "warning",
        "risk_score": 0.45,
        "sandbox_required": True,
        "command_category": "modify",
        "safe_alternatives": [
            "add --dry-run flag",
            "use sandbox workspace instead of real system",
        ],
        "recommended_next_action": "command requires sandbox — do not execute directly",
        "read_only": True,
        "preview_only": True,
    },
}

INTEGRATION_POINTS = [
    "34.2_terminal_bridge_intelligence",
    "33.8_luxcode_core_status",
    "33.5_sandbox_repair_intelligence",
    "37.8_agent_core",
]


def _select_terminal_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in TERMINAL_INTELLIGENCE_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "safe_command"


def _detect_command_category(command: str) -> str:
    cmd_lower = command.lower()
    for cat in COMMAND_CATEGORIES:
        if cat in cmd_lower:
            return cat
    return "inspect"


def terminal_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "37.1",
        "series": "Agent Architecture",
        "name": "Terminal Intelligence Preview",
        "status": "terminal_intelligence_ready",
        "architecture_version": "1.0",
        "capabilities": TERMINAL_INTELLIGENCE_CAPABILITIES,
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "risk_model": RISK_LEVELS,
        "command_categories": COMMAND_CATEGORIES,
        "operation_mode": "read_only_preview_only",
        "execution_rule": "all_command_execution_must_go_through_luxcode_sandbox",
        "connected_layers": ["34.2", "33.8", "33.5", "37.8"],
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
            "/terminal-intelligence/status",
            "/terminal-intelligence/capabilities",
            "/terminal-intelligence/preview",
        ],
        "safety_note": "Read-only terminal intelligence preview. No actual terminal commands executed.",
    }


def terminal_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "37.1",
        "series": "Agent Architecture",
        "name": "Terminal Intelligence Capabilities",
        "status": "terminal_intelligence_capabilities_ready",
        "capabilities": [
            {"name": "command_intent_classification", "description": "Classify command intent from natural language input", "read_only": True},
            {"name": "command_risk_analysis", "description": "Analyze command risk level before any execution", "read_only": True},
            {"name": "sandbox_requirement_detection", "description": "Detect whether command requires sandbox isolation", "read_only": True},
            {"name": "command_category_identification", "description": "Identify command category (build, test, install, inspect)", "read_only": True},
            {"name": "safe_alternative_suggestion", "description": "Suggest safer alternatives for risky commands", "read_only": True},
            {"name": "command_readiness_scoring", "description": "Score command readiness for safe execution", "read_only": True},
            {"name": "terminal_context_assembly", "description": "Assemble terminal context including OS, shell, paths", "read_only": True},
            {"name": "environment_awareness", "description": "Maintain awareness of toolchain and dependency state", "read_only": True},
        ],
        "read_only": True,
        "preview_only": True,
        "real_action_enabled": False,
        "safety_note": "Capabilities are read-only. No terminal execution available.",
    }


def terminal_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    repo_name: Optional[str] = None,
    task_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    context: str = "",
) -> Dict[str, Any]:
    pid = _select_terminal_profile(target_issue, command, project_area)
    p = TERMINAL_INTELLIGENCE_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    category = _detect_command_category(cmd)

    return {
        "layer": "37.1",
        "series": "Agent Architecture",
        "module": "terminal_intelligence",
        "status": "preview_ready",
        "input_summary": {
            "target_issue": target_issue,
            "command": command[:100] if command else "",
            "project_area": project_area,
            "task_type": task_type,
            "risk_level": risk_level,
        },
        "detected_intent": pid,
        "command_category": category,
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
        "safety_note": "Read-only preview. No terminal commands executed.",
    }
