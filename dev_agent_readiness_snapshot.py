from __future__ import annotations

from typing import Any, Dict, List

from dependency_mapper_preview import dependency_mapper_status
from dev_agent_explorer_preview import dev_agent_explorer_status
from impact_analyzer_preview import impact_analyzer_status
from safe_change_boundary_preview import change_boundary_status
from safe_patch_planner_preview import patch_planner_status
from safe_verification_planner_preview import verification_planner_status


COMPLETED_LAYERS: List[str] = ["25.1", "25.2", "25.3", "25.4", "25.5", "25.6"]

AVAILABLE_CAPABILITIES: List[str] = [
    "exploration",
    "dependency_mapping",
    "impact_analysis",
    "boundary_analysis",
    "patch_planning",
    "verification_planning",
]

MISSING_CAPABILITIES: List[str] = [
    "constitution_engine",
    "project_rules_loader",
    "multi_agent_roles",
    "real_patch_application",
    "write_permission_engine",
    "automated_regression_runner",
]


def _component_statuses() -> List[Dict[str, Any]]:
    status_builders = [
        dev_agent_explorer_status,
        dependency_mapper_status,
        impact_analyzer_status,
        change_boundary_status,
        patch_planner_status,
        verification_planner_status,
    ]
    output: List[Dict[str, Any]] = []
    for builder in status_builders:
        status = builder()
        output.append(
            {
                "layer": status.get("layer"),
                "name": status.get("name"),
                "status": status.get("status"),
                "read_only": status.get("read_only"),
                "strict_read_only": status.get("strict_read_only"),
                "analysis_only": status.get("analysis_only"),
                "chat_stream_touched": status.get("chat_stream_touched"),
                "typewriter_runtime_touched": status.get("typewriter_runtime_touched"),
            }
        )
    return output


def dev_agent_readiness_status() -> Dict[str, Any]:
    return {
        "layer": "25.7",
        "name": "Dev Agent Readiness Snapshot",
        "status": "dev_agent_foundation_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "completed_layers": COMPLETED_LAYERS,
        "available_capabilities": AVAILABLE_CAPABILITIES,
        "missing_capabilities": MISSING_CAPABILITIES,
        "readiness_score": 78,
        "safe_for_patch_planning": True,
        "safe_for_write_operations": False,
        "recommended_next_layer": "layer_26_multi_agent_system",
        "confidence_score": 0.91,
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
            "/debug/dev-agent-readiness-status",
            "/debug/dev-agent-readiness-registry",
            "/debug/layer25-status",
        ],
        "safety_note": "Layer 25 is ready for read-only Dev Agent planning, but not for write operations, patch application, commits, pushes, deploys, or subprocess execution.",
    }


def dev_agent_readiness_registry() -> Dict[str, Any]:
    return {
        "layer": "25.7",
        "name": "Dev Agent Readiness Registry",
        "status": "dev_agent_readiness_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "completed_layers": COMPLETED_LAYERS,
        "component_statuses": _component_statuses(),
        "available_capabilities": AVAILABLE_CAPABILITIES,
        "missing_capabilities": MISSING_CAPABILITIES,
        "foundation_endpoints": [
            "/debug/dev-agent-explorer-status",
            "/debug/dependency-mapper-status",
            "/debug/impact-analyzer-status",
            "/debug/change-boundary-status",
            "/debug/patch-planner-status",
            "/debug/verification-planner-status",
        ],
        "readiness_gates": {
            "exploration_ready": True,
            "dependency_mapping_ready": True,
            "impact_analysis_ready": True,
            "boundary_analysis_ready": True,
            "patch_planning_ready": True,
            "verification_planning_ready": True,
            "write_operations_ready": False,
            "real_patch_application_ready": False,
            "multi_agent_roles_ready": False,
        },
        "future_layer_26_inputs": [
            "constitution_engine",
            "project_rules_loader",
            "multi_agent_roles",
            "permissioned_write_boundary",
            "verification_execution_guard",
        ],
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


def layer25_status_snapshot() -> Dict[str, Any]:
    status = dev_agent_readiness_status()
    registry = dev_agent_readiness_registry()
    return {
        **status,
        "layer25_status": "foundation_complete",
        "foundation_summary": {
            "completed_layer_count": len(COMPLETED_LAYERS),
            "available_capability_count": len(AVAILABLE_CAPABILITIES),
            "missing_capability_count": len(MISSING_CAPABILITIES),
            "component_statuses": registry.get("component_statuses", []),
        },
        "can_plan_patches": True,
        "can_apply_patches": False,
        "can_modify_code": False,
        "can_commit": False,
        "can_push": False,
        "can_deploy": False,
        "next_recommended_layer": "layer_26_multi_agent_system",
        "future_direction": [
            "Layer 26 Multi Agent System",
            "Constitution Engine",
            "Project Rules Loader",
            "Permissioned Dev Agent Roles",
        ],
    }
