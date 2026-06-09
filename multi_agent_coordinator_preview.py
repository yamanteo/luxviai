from __future__ import annotations

from typing import Any, Dict, List, Optional

from agent_constitution_engine_preview import build_constitution_preview
from evidence_store_preview import build_evidence_store_preview
from explorer_agent_preview import explorer_agent_status
from planner_agent_preview import planner_agent_status
from project_rules_loader_preview import build_project_rules_preview
from verifier_agent_preview import verifier_agent_status


COORDINATOR_ALLOWED_CAPABILITIES: List[str] = [
    "agent_output_collection",
    "coordination_flow_preview",
    "contribution_summary",
    "combined_risk_summary",
    "read_only_coordination",
]

COORDINATOR_BLOCKED_CAPABILITIES: List[str] = [
    "code_generation",
    "patch_execution",
    "patch_application",
    "test_execution",
    "file_write",
    "memory_write",
    "db_write",
    "git_write",
    "commit",
    "push",
    "deploy",
    "subprocess_execution",
    "auto_fix",
]


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_finding(command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{project_area or ''} {command or ''}")
    if any(term in haystack for term in ["stop", "continue", "dur", "devam", "arm", "state"]):
        return "state_source_conflict"
    if any(term in haystack for term in ["duplicate", "branch", "fallback"]):
        return "duplicate_branch"
    if any(term in haystack for term in ["permission", "izin", "luxway", "phone", "telefon"]):
        return "permission_boundary"
    if any(term in haystack for term in ["test", "verify", "validation", "regression"]):
        return "validation_gap"
    return "debug_intelligence_trace"


def coordinator_status() -> Dict[str, Any]:
    return {
        "layer": "26.7",
        "name": "Multi-Agent Coordinator Preview",
        "status": "coordinator_preview_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
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
        "test_execution_enabled": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "allowed_capabilities": COORDINATOR_ALLOWED_CAPABILITIES,
        "blocked_capabilities": COORDINATOR_BLOCKED_CAPABILITIES,
        "available_endpoints": [
            "/debug/coordinator-status",
            "/debug/coordinator-registry",
            "/debug/coordinator-preview",
        ],
        "connected_layers": [
            "26.1 Agent Constitution Engine",
            "26.2 Project Rules Loader",
            "26.3 Explorer Agent",
            "26.4 Planner Agent",
            "26.5 Verifier Agent",
            "26.6 Evidence Store",
        ],
        "future_direction": ["Coordinator Agent", "Dev Agent reports", "multi-agent handoff"],
        "safety_note": "Coordinator is strict read-only. It combines agent outputs but does not decide, patch, run tests, write files, commit, push, deploy, or change runtime behavior.",
    }


def coordinator_registry() -> Dict[str, Any]:
    return {
        "layer": "26.7",
        "name": "Multi-Agent Coordinator Registry",
        "status": "coordinator_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "participating_agents": ["explorer", "planner", "verifier"],
        "supporting_systems": ["constitution_engine", "project_rules_loader", "evidence_store"],
        "coordination_flow": ["constitution", "project_rules", "explorer", "planner", "verifier", "evidence_store", "coordinator_summary"],
        "agent_contribution_templates": {
            "explorer": "entry points and related systems",
            "planner": "solution plan and task order",
            "verifier": "validation strategy and regression checks",
            "evidence_store": "evidence and confidence reasoning",
        },
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
            "test_execution": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_coordinator_preview(
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    finding = _select_finding(command, project_area)
    explorer = explorer_agent_status()
    planner = planner_agent_status()
    verifier = verifier_agent_status()
    constitution = build_constitution_preview(
        command=command or "multi agent coordination read only",
        rule_source="project_rules",
        conflicting_rules=["coordinate_agents", "read_only_mode"],
        target_area=project_area or finding,
    )
    project_rules = build_project_rules_preview(
        command=command or finding,
        project_rule_category="safety_rules",
        target_area=project_area or finding,
    )
    evidence = build_evidence_store_preview(
        finding=finding,
        command=command or finding,
        project_area=project_area or finding,
        related_layer=related_layer,
    )

    return {
        "participating_agents": ["explorer", "planner", "verifier"],
        "agent_contributions": {
            "explorer": "entry points and related systems",
            "planner": "solution plan and task order",
            "verifier": "validation strategy and regression checks",
            "evidence_store": "evidence and confidence reasoning",
        },
        "coordination_flow": ["constitution", "project_rules", "explorer", "planner", "verifier", "evidence_store", "coordinator_summary"],
        "combined_findings": [evidence.get("finding")],
        "combined_risks": [evidence.get("risk_reasoning"), "runtime_regression" if finding == "state_source_conflict" else "preview_boundary_risk"],
        "combined_recommendations": [
            "keep coordination read-only",
            "use explorer before planner",
            "use verifier before any future write-capable step",
            "preserve evidence reasoning for handoff",
        ],
        "overall_confidence": round(
            (
                float(evidence.get("confidence_score", 0.0))
                + 0.9
                + 0.9
                + 0.91
            )
            / 4,
            2,
        ),
        "constitution_signal": {
            "selected_rule": constitution.get("selected_rule"),
            "resolution_reason": constitution.get("resolution_reason"),
            "rule_priority": constitution.get("rule_priority"),
        },
        "project_rules_signal": {
            "project_rule_category": project_rules.get("project_rule_category"),
            "protected_areas": project_rules.get("protected_areas", []),
            "blocked_actions": project_rules.get("blocked_actions", []),
        },
        "agent_status_signals": {
            "explorer": {
                "status": explorer.get("status"),
                "allowed_capabilities": explorer.get("allowed_capabilities", []),
            },
            "planner": {
                "status": planner.get("status"),
                "allowed_capabilities": planner.get("allowed_capabilities", []),
            },
            "verifier": {
                "status": verifier.get("status"),
                "allowed_capabilities": verifier.get("allowed_capabilities", []),
            },
        },
        "evidence_signal": {
            "finding": evidence.get("finding"),
            "evidence_items": evidence.get("evidence_items", []),
            "supporting_signals": evidence.get("supporting_signals", []),
            "confidence_reasoning": evidence.get("confidence_reasoning"),
            "risk_reasoning": evidence.get("risk_reasoning"),
        },
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
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
        "test_execution_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Coordinator only combines read-only agent outputs. It does not decide, patch, test, write files, commit, push, deploy, or change runtime behavior.",
    }
