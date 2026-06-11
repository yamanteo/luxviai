from __future__ import annotations
from typing import Any, Dict, List, Optional


DEPLOYMENT_AGENT_CAPABILITIES = [
    "pre_deploy_checklist_assembly",
    "deploy_risk_scoring",
    "staging_production_boundary_detection",
    "deployment_verification_planning",
    "rollback_plan_assembly",
    "deployment_readiness_scoring",
    "post_deploy_verification_preview",
    "deployment_confidence_assessment",
]

NOT_ALLOWED_OPERATIONS = [
    "deploy", "redeploy", "restart", "shutdown", "delete",
    "modify_production", "trigger_deploy", "rollback_execute",
]

RISK_LEVELS = ["safe", "warning", "high_risk", "critical"]

DEPLOYMENT_AGENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "ready_to_deploy": {
        "aliases": ["ready", "hazir", "deploy ready", "approved"],
        "deployment_status": "ready",
        "deployment_health": "pass",
        "deployment_summary": "Pre-deploy checklist complete. All gates pass. Staging verified. Rollback plan ready. Deployment confidence high.",
        "pre_deploy_checklist": [
            "verification_gates_all_pass",
            "delivery_readiness_confirmed",
            "staging_deployment_verified",
            "rollback_plan_ready",
            "environment_configuration_complete",
        ],
        "risk_assessment": "safe",
        "risk_score": 0.12,
        "rollback_plan_status": "ready",
        "verification_plan_status": "ready",
        "recommended_next_action": "ready to deploy — proceed with deploy after user approval",
        "read_only": True,
        "preview_only": True,
    },
    "needs_preparation": {
        "aliases": ["not ready", "hazir degil", "preparation", "blocked"],
        "deployment_status": "not_ready",
        "deployment_health": "degraded",
        "deployment_summary": "Pre-deploy checklist incomplete. Verification gates not all passed. Rollback plan not verified. Environment configuration pending.",
        "pre_deploy_checklist": [
            "verification_gates_all_pass: pending",
            "delivery_readiness_confirmed: pending",
            "staging_deployment_verified: pending",
            "rollback_plan_ready: pending",
            "environment_configuration_complete: pending",
        ],
        "risk_assessment": "high_risk",
        "risk_score": 0.78,
        "rollback_plan_status": "not_ready",
        "verification_plan_status": "not_ready",
        "recommended_next_action": "complete pre-deploy checklist before proceeding",
        "read_only": True,
        "preview_only": True,
    },
}

INTEGRATION_POINTS = [
    "37.2_render_deployment_intelligence",
    "34.3_deployment_bridge_intelligence",
    "33.8_luxcode_core_status",
    "33.7_delivery_readiness",
    "33.6_verification_intelligence",
    "37.8_agent_core",
]


def _select_deployment_agent_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in DEPLOYMENT_AGENT_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "ready_to_deploy"


def deployment_agent_status() -> Dict[str, Any]:
    return {
        "layer": "37.6",
        "series": "Agent Architecture",
        "name": "Deployment Agent Preview",
        "status": "deployment_agent_ready",
        "architecture_version": "1.0",
        "capabilities": DEPLOYMENT_AGENT_CAPABILITIES,
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "risk_model": RISK_LEVELS,
        "operation_mode": "read_only_preview_only",
        "execution_rule": "all_deployments_must_go_through_luxcode_pipeline_with_user_approval",
        "connected_layers": ["37.2", "34.3", "33.8", "33.7", "33.6", "37.8"],
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
            "/deployment-agent/status",
            "/deployment-agent/capabilities",
            "/deployment-agent/preview",
        ],
        "safety_note": "Read-only deployment agent preview. No deployment actions performed.",
    }


def deployment_agent_capabilities() -> Dict[str, Any]:
    return {
        "layer": "37.6",
        "series": "Agent Architecture",
        "name": "Deployment Agent Capabilities",
        "status": "deployment_agent_capabilities_ready",
        "capabilities": [
            {"name": "pre_deploy_checklist_assembly", "description": "Assemble pre-deploy checklist from verification gates", "read_only": True},
            {"name": "deploy_risk_scoring", "description": "Score deployment risk from multiple signals", "read_only": True},
            {"name": "staging_production_boundary_detection", "description": "Detect staging vs production boundary", "read_only": True},
            {"name": "deployment_verification_planning", "description": "Plan deployment verification steps", "read_only": True},
            {"name": "rollback_plan_assembly", "description": "Assemble rollback plan from deployment context", "read_only": True},
            {"name": "deployment_readiness_scoring", "description": "Score overall deployment readiness", "read_only": True},
            {"name": "post_deploy_verification_preview", "description": "Preview post-deploy verification results", "read_only": True},
            {"name": "deployment_confidence_assessment", "description": "Assess deployment confidence", "read_only": True},
        ],
        "read_only": True,
        "preview_only": True,
        "real_action_enabled": False,
        "safety_note": "Capabilities are read-only. No deployment actions available.",
    }


def deployment_agent_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    repo_name: Optional[str] = None,
    task_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    context: str = "",
) -> Dict[str, Any]:
    pid = _select_deployment_agent_profile(target_issue, command, project_area)
    p = DEPLOYMENT_AGENT_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected

    return {
        "layer": "37.6",
        "series": "Agent Architecture",
        "module": "deployment_agent",
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
        "safety_note": "Read-only preview. No deployment actions performed.",
    }
