from __future__ import annotations
from typing import Any, Dict, List, Optional


RENDER_DEPLOYMENT_INTELLIGENCE_CAPABILITIES = [
    "deployment_context_assembly",
    "deploy_risk_analysis",
    "environment_readiness_scoring",
    "rollback_need_detection",
    "post_deploy_verification_planning",
    "deployment_readiness_assessment",
    "staging_production_boundary_analysis",
    "release_confidence_scoring",
]

NOT_ALLOWED_OPERATIONS = [
    "deploy", "redeploy", "restart", "shutdown", "delete", "modify_production",
    "trigger_deploy", "rollback_execute",
]

RISK_LEVELS = ["safe", "warning", "high_risk", "critical"]
DEPLOYMENT_PHASES = ["pre_deploy", "deploy", "post_deploy", "verify", "rollback"]

RENDER_DEPLOYMENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "ready_for_deploy": {
        "aliases": ["ready", "hazir", "deploy ready", "production ready"],
        "deployment_status": "ready",
        "deployment_health": "pass",
        "deployment_summary": "Deployment is ready. All verification gates pass. Environment configured. Rollback plan verified. Safe to proceed.",
        "risk_assessment": "safe",
        "risk_score": 0.15,
        "environment_readiness": "ready",
        "rollback_required": False,
        "current_phase": "pre_deploy",
        "recommended_next_action": "deployment ready — proceed with deploy when approved",
        "read_only": True,
        "preview_only": True,
    },
    "deploy_requires_verification": {
        "aliases": ["verify", "test", "check", "validate", "control"],
        "deployment_status": "conditional",
        "deployment_health": "warning",
        "deployment_summary": "Deployment requires post-deploy verification. Environment configured. Rollback plan ready. Verification plan needs review.",
        "risk_assessment": "warning",
        "risk_score": 0.45,
        "environment_readiness": "conditional",
        "rollback_required": True,
        "current_phase": "pre_deploy",
        "recommended_next_action": "review verification plan before deployment",
        "read_only": True,
        "preview_only": True,
    },
}

INTEGRATION_POINTS = [
    "34.3_deployment_bridge_intelligence",
    "34.2_terminal_bridge_intelligence",
    "33.8_luxcode_core_status",
    "33.7_delivery_readiness",
    "33.6_verification_intelligence",
    "37.8_agent_core",
]


def _select_deployment_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in RENDER_DEPLOYMENT_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "ready_for_deploy"


def render_deployment_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "37.2",
        "series": "Agent Architecture",
        "name": "Render Deployment Intelligence Preview",
        "status": "render_deployment_intelligence_ready",
        "architecture_version": "1.0",
        "capabilities": RENDER_DEPLOYMENT_INTELLIGENCE_CAPABILITIES,
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "risk_model": RISK_LEVELS,
        "deployment_phases": DEPLOYMENT_PHASES,
        "operation_mode": "read_only_preview_only",
        "execution_rule": "all_deployments_must_go_through_luxcode_pipeline",
        "connected_layers": ["34.3", "34.2", "33.8", "33.7", "33.6", "37.8"],
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
            "/render-deployment-intelligence/status",
            "/render-deployment-intelligence/capabilities",
            "/render-deployment-intelligence/preview",
        ],
        "safety_note": "Read-only Render deployment intelligence preview. No actual deployment actions performed.",
    }


def render_deployment_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "37.2",
        "series": "Agent Architecture",
        "name": "Render Deployment Intelligence Capabilities",
        "status": "render_deployment_intelligence_capabilities_ready",
        "capabilities": [
            {"name": "deployment_context_assembly", "description": "Assemble full deployment context across environments", "read_only": True},
            {"name": "deploy_risk_analysis", "description": "Analyze deployment risk from environment and code state", "read_only": True},
            {"name": "environment_readiness_scoring", "description": "Score environment readiness for deployment", "read_only": True},
            {"name": "rollback_need_detection", "description": "Detect whether rollback plan is required before deploy", "read_only": True},
            {"name": "post_deploy_verification_planning", "description": "Plan post-deploy verification steps", "read_only": True},
            {"name": "deployment_readiness_assessment", "description": "Assess overall deployment readiness", "read_only": True},
            {"name": "staging_production_boundary_analysis", "description": "Analyze staging/production boundary safety", "read_only": True},
            {"name": "release_confidence_scoring", "description": "Score release confidence from multiple signals", "read_only": True},
        ],
        "read_only": True,
        "preview_only": True,
        "real_action_enabled": False,
        "safety_note": "Capabilities are read-only. No deployment actions available.",
    }


def render_deployment_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    repo_name: Optional[str] = None,
    task_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    context: str = "",
) -> Dict[str, Any]:
    pid = _select_deployment_profile(target_issue, command, project_area)
    p = RENDER_DEPLOYMENT_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected

    return {
        "layer": "37.2",
        "series": "Agent Architecture",
        "module": "render_deployment_intelligence",
        "status": "preview_ready",
        "input_summary": {
            "target_issue": target_issue,
            "command": command[:100] if command else "",
            "project_area": project_area,
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
        "safety_note": "Read-only preview. No deployment actions performed.",
    }
