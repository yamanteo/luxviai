from __future__ import annotations
from typing import Any, Dict, List, Optional

from terminal_bridge_intelligence_preview import (
    terminal_bridge_intelligence_registry,
)
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


DEPLOYMENT_BRIDGE_CAPABILITIES = [
    "deployment_inspection",
    "environment_analysis",
    "deployment_readiness",
    "rollback_planning",
    "release_planning",
    "deployment_risk_analysis",
    "environment_validation",
]

SUPPORTED_PLATFORMS = [
    "Render", "Vercel", "Railway", "Docker",
    "Cloud Run", "AWS", "Azure", "VPS", "Self Hosted",
]

NOT_ALLOWED_OPERATIONS = [
    "deploy", "redeploy", "restart", "shutdown", "delete", "modify_production",
]

DEPLOYMENT_LEVELS = ["not_ready", "partially_ready", "conditional", "ready", "deployment_ready"]
RISK_LEVELS = ["safe", "warning", "high_risk", "critical"]

DEPLOYMENT_BRIDGE_PROFILES: Dict[str, Dict[str, Any]] = {
    "deployment_not_ready": {
        "aliases": ["not ready", "hazir degil", "blocked", "incomplete"],
        "deployment_status": "not_ready",
        "deployment_health": "degraded",
        "deployment_summary": "Deployment not ready. Verification gates not all passed. Delivery readiness incomplete. Rollback plan not verified. Environment configuration pending.",
        "deployment_readiness": "not_ready",
        "deployment_risk_score": 0.82,
        "deployment_environment": {
            "target_platform": "Render",
            "environment_configured": False,
            "env_variables_set": False,
            "build_config_ready": False,
        },
        "deployment_requirements": [
            "complete_all_verification_gates",
            "verify_delivery_readiness",
            "prepare_rollback_plan",
            "configure_deployment_environment",
        ],
        "deployment_blockers": [
            "verification_gates_not_all_passed",
            "delivery_readiness_not_confirmed",
            "rollback_plan_not_verified",
        ],
        "deployment_warnings": [
            "environment_not_configured",
            "env_variables_not_set",
        ],
        "rollback_readiness": "not_verified",
        "release_candidate_status": "blocked",
        "recommended_next_action": "complete verification gates and configure deployment environment first",
        "read_only": True,
        "preview_only": True,
    },
    "deployment_partially_ready": {
        "aliases": ["partial", "kismen", "in progress", "devam"],
        "deployment_status": "partially_ready",
        "deployment_health": "warning",
        "deployment_summary": "Deployment partially ready. Verification gates pass. Delivery readiness confirmed. Environment configured. Rollback plan needs final review. Deployment can proceed with caution.",
        "deployment_readiness": "partially_ready",
        "deployment_risk_score": 0.48,
        "deployment_environment": {
            "target_platform": "Render",
            "environment_configured": True,
            "env_variables_set": True,
            "build_config_ready": True,
            "health_check_endpoint": "/health",
        },
        "deployment_requirements": [
            "finalize_rollback_plan_review",
        ],
        "deployment_blockers": [],
        "deployment_warnings": [
            "rollback_plan_review_pending",
        ],
        "rollback_readiness": "conditional",
        "release_candidate_status": "conditional",
        "recommended_next_action": "finalize rollback plan review before proceeding with deployment",
        "read_only": True,
        "preview_only": True,
    },
    "deployment_conditional": {
        "aliases": ["conditional", "sartli", "almost", "neredeyse"],
        "deployment_status": "conditional",
        "deployment_health": "warning",
        "deployment_summary": "Deployment conditionally ready. All verification gates pass. Delivery readiness confirmed. Rollback plan verified. One environment variable not configured for staging. Conditional approval granted.",
        "deployment_readiness": "conditional",
        "deployment_risk_score": 0.32,
        "deployment_environment": {
            "target_platform": "Render",
            "environment_configured": True,
            "env_variables_set": True,
            "staging_env_complete": False,
            "production_env_ready": True,
            "health_check_endpoint": "/health",
        },
        "deployment_requirements": [
            "complete_staging_environment_config",
        ],
        "deployment_blockers": [],
        "deployment_warnings": [
            "staging_environment_config_pending",
        ],
        "rollback_readiness": "verified",
        "release_candidate_status": "conditional",
        "recommended_next_action": "complete staging environment configuration before production deployment",
        "read_only": True,
        "preview_only": True,
    },
    "deployment_ready": {
        "aliases": ["ready", "hazir", "approved", "deploy"],
        "deployment_status": "ready",
        "deployment_health": "pass",
        "deployment_summary": "Deployment ready. All verification gates pass. Delivery readiness confirmed. Rollback plan verified. Environment fully configured. Deployment can proceed.",
        "deployment_readiness": "ready",
        "deployment_risk_score": 0.18,
        "deployment_environment": {
            "target_platform": "Render",
            "environment_configured": True,
            "env_variables_set": True,
            "build_config_ready": True,
            "health_check_endpoint": "/health",
            "staging_env_complete": True,
            "production_env_ready": True,
        },
        "deployment_requirements": [],
        "deployment_blockers": [],
        "deployment_warnings": [],
        "rollback_readiness": "verified",
        "release_candidate_status": "approved",
        "recommended_next_action": "deployment ready — proceed with deployment",
        "read_only": True,
        "preview_only": True,
    },
    "deployment_ready_advanced": {
        "aliases": ["advanced", "gelismis", "delivery", "teslim", "go"],
        "deployment_status": "deployment_ready",
        "deployment_health": "pass",
        "deployment_summary": "Full deployment readiness confirmed. All verification gates pass. Delivery readiness confirmed. Rollback plan verified with automated rollback. Multi-platform deployment supported. Health check monitoring active. Ready for production delivery.",
        "deployment_readiness": "deployment_ready",
        "deployment_risk_score": 0.08,
        "deployment_environment": {
            "target_platform": "Render",
            "alternative_platforms": ["Vercel", "Railway"],
            "environment_configured": True,
            "env_variables_set": True,
            "build_config_ready": True,
            "health_check_endpoint": "/health",
            "staging_env_complete": True,
            "production_env_ready": True,
            "monitoring_active": True,
            "automated_rollback": True,
        },
        "deployment_requirements": [],
        "deployment_blockers": [],
        "deployment_warnings": [],
        "rollback_readiness": "verified_with_automated_rollback",
        "release_candidate_status": "approved",
        "recommended_next_action": "full deployment readiness confirmed — proceed with production delivery",
        "read_only": True,
        "preview_only": True,
    },
}


def _select_deployment_bridge_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in DEPLOYMENT_BRIDGE_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "deployment_not_ready"


def deployment_bridge_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "34.3",
        "name": "Deployment Bridge Intelligence Preview",
        "status": "deployment_bridge_intelligence_ready",
        "bridge_version": "1.0",
        "capabilities": DEPLOYMENT_BRIDGE_CAPABILITIES,
        "supported_platforms": SUPPORTED_PLATFORMS,
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "deployment_levels": DEPLOYMENT_LEVELS,
        "risk_model": RISK_LEVELS,
        "operation_mode": "read_only_preview_only",
        "execution_rule": "all_deployments_must_go_through_luxcode_pipeline",
        "connected_layers": ["34.2", "34.1", "33.8", "33.7", "33.6"],
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
            "/deployment-bridge/status",
            "/deployment-bridge/capabilities",
            "/deployment-bridge/preview",
        ],
        "safety_note": "Read-only deployment bridge intelligence preview. No actual deployment actions performed.",
    }


def deployment_bridge_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "34.3",
        "name": "Deployment Bridge Intelligence Capabilities",
        "status": "deployment_bridge_capabilities_ready",
        "capabilities": [
            {
                "name": "deployment_inspection",
                "description": "Inspect current deployment status across environments",
                "read_only": True,
            },
            {
                "name": "environment_analysis",
                "description": "Analyze deployment environment configuration and readiness",
                "read_only": True,
            },
            {
                "name": "deployment_readiness",
                "description": "Assess deployment readiness using Delivery Readiness Intelligence",
                "read_only": True,
            },
            {
                "name": "rollback_planning",
                "description": "Plan rollback strategy based on environment and deployment type",
                "read_only": True,
            },
            {
                "name": "release_planning",
                "description": "Plan release sequence across environments and platforms",
                "read_only": True,
            },
            {
                "name": "deployment_risk_analysis",
                "description": "Analyze deployment risks using combined intelligence layers",
                "read_only": True,
            },
            {
                "name": "environment_validation",
                "description": "Validate deployment environment configuration and dependencies",
                "read_only": True,
            },
        ],
        "supported_platforms": SUPPORTED_PLATFORMS,
        "not_allowed_operations": NOT_ALLOWED_OPERATIONS,
        "deployment_levels": DEPLOYMENT_LEVELS,
        "risk_model": RISK_LEVELS,
        "operation_mode": "read_only_preview_only",
        "integration_layers": ["34.2", "34.1", "33.8", "33.7", "33.6"],
        "read_only": True,
        "preview_only": True,
    }


def deployment_bridge_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for pid, p in DEPLOYMENT_BRIDGE_PROFILES.items():
        items.append(
            {
                "profile_id": pid,
                "deployment_status": p["deployment_status"],
                "deployment_health": p["deployment_health"],
                "deployment_readiness": p.get("deployment_readiness"),
                "deployment_risk_score": p.get("deployment_risk_score"),
                "rollback_readiness": p.get("rollback_readiness"),
                "release_candidate_status": p.get("release_candidate_status"),
                "blocker_count": len(p.get("deployment_blockers", [])),
                "warning_count": len(p.get("deployment_warnings", [])),
            }
        )
    return {
        "layer": "34.3",
        "name": "Deployment Bridge Intelligence Registry",
        "status": "deployment_bridge_intelligence_registry_ready",
        "profile_count": len(items),
        "profiles": items,
        "deployment_levels_defined": DEPLOYMENT_LEVELS,
        "aggregate": {
            "min_risk_score": min(i["deployment_risk_score"] for i in items) if items else 0.0,
            "max_risk_score": max(i["deployment_risk_score"] for i in items) if items else 0.0,
            "avg_risk_score": round(
                sum(i["deployment_risk_score"] for i in items) / len(items), 2
            ) if items else 0.0,
        },
        "read_only": True,
        "preview_only": True,
    }


def _build_integration_signals(
    target: str, command: str, project_area: str, related_layer: str
) -> Dict[str, Any]:
    L = related_layer or "Layer 34.3"
    terminal_reg = terminal_bridge_intelligence_registry()
    github_reg = github_bridge_intelligence_registry()
    core_status = luxcode_core_status_snapshot()
    delivery_reg = delivery_readiness_intelligence_registry()
    verification_reg = verification_intelligence_registry()

    return {
        "layer34_2_terminal_bridge": {
            "profile_count": terminal_reg.get("profile_count"),
            "avg_risk_score": terminal_reg.get("aggregate", {}).get("avg_risk_score"),
        },
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
    }


def build_deployment_bridge_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_deployment_bridge_profile(target_issue, command, project_area)
    p = DEPLOYMENT_BRIDGE_PROFILES[pid]
    detected = target_issue or project_area or pid
    cmd = command or detected
    L = related_layer or "Layer 34.3"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "deployment_status": p["deployment_status"],
        "deployment_health": p["deployment_health"],
        "deployment_summary": p.get("deployment_summary"),
        "deployment_readiness": p.get("deployment_readiness"),
        "deployment_risk_score": p.get("deployment_risk_score"),
        "deployment_environment": p.get("deployment_environment", {}),
        "deployment_requirements": p.get("deployment_requirements", []),
        "deployment_blockers": p.get("deployment_blockers", []),
        "deployment_warnings": p.get("deployment_warnings", []),
        "rollback_readiness": p.get("rollback_readiness"),
        "release_candidate_status": p.get("release_candidate_status"),
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
        "safety_note": "Read-only deployment bridge intelligence preview. No actual deployment actions performed.",
    }
