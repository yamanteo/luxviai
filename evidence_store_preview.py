from __future__ import annotations

from typing import Any, Dict, List, Optional

from agent_constitution_engine_preview import build_constitution_preview
from explorer_agent_preview import explorer_agent_status
from planner_agent_preview import planner_agent_status
from project_rules_loader_preview import build_project_rules_preview
from verifier_agent_preview import verifier_agent_status


EVIDENCE_FINDING_PROFILES: Dict[str, Dict[str, Any]] = {
    "state_source_conflict": {
        "aliases": ["state", "source", "conflict", "arm", "continue", "devam"],
        "evidence_items": ["multiple_owner_detected", "runtime_state_boundary", "resume_flow_signal"],
        "supporting_signals": ["root_flow_audit", "explorer_agent", "planner_agent", "verifier_agent"],
        "risk_reasoning": "core runtime state can affect stop/continue behavior",
        "confidence_score": 0.9,
    },
    "duplicate_branch": {
        "aliases": ["duplicate", "branch", "fallback", "stale"],
        "evidence_items": ["duplicate_flow_detected", "stale_branch_risk", "fallback_path_signal"],
        "supporting_signals": ["root_flow_audit", "dependency_mapper", "planner_agent"],
        "risk_reasoning": "duplicate behavior owners can create inconsistent runtime outcomes",
        "confidence_score": 0.88,
    },
    "permission_boundary": {
        "aliases": ["permission", "izin", "luxway", "phone", "telefon", "mail", "calendar"],
        "evidence_items": ["protected_private_data_area", "confirmation_required_signal", "real_access_false_guard"],
        "supporting_signals": ["project_rules_loader", "safe_change_boundary", "verifier_agent"],
        "risk_reasoning": "private data and device actions require permission and confirmation boundaries",
        "confidence_score": 0.91,
    },
    "validation_gap": {
        "aliases": ["test", "validation", "verify", "coverage", "regression"],
        "evidence_items": ["manual_scenario_needed", "regression_check_needed", "success_criteria_signal"],
        "supporting_signals": ["verification_planner", "verifier_agent", "smoke_coverage"],
        "risk_reasoning": "missing validation can let endpoint or behavior regressions escape",
        "confidence_score": 0.87,
    },
    "debug_intelligence_trace": {
        "aliases": ["debug", "fault", "report", "evidence", "agent"],
        "evidence_items": ["agent_signal_preview", "read_only_boundary", "fault_report_link"],
        "supporting_signals": ["constitution_engine", "project_rules_loader", "multi_agent_preview"],
        "risk_reasoning": "debug intelligence must remain analysis-only until explicit write permissions exist",
        "confidence_score": 0.86,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_finding(finding: Optional[str], command: str) -> str:
    haystack = _normalize(f"{finding or ''} {command or ''}")
    for finding_id, profile in EVIDENCE_FINDING_PROFILES.items():
        if finding_id in haystack or any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return finding_id
    return "debug_intelligence_trace"


def evidence_store_status() -> Dict[str, Any]:
    return {
        "layer": "26.6",
        "name": "Evidence Store Preview",
        "status": "evidence_store_preview_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "real_storage_performed": False,
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
        "real_data_stored": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "available_endpoints": [
            "/debug/evidence-store-status",
            "/debug/evidence-store-registry",
            "/debug/evidence-store-preview",
        ],
        "connected_layers": [
            "26.1 Agent Constitution Engine",
            "26.2 Project Rules Loader",
            "26.3 Explorer Agent",
            "26.4 Planner Agent",
            "26.5 Verifier Agent",
        ],
        "future_direction": ["Coordinator Agent", "Patch Planner evidence", "Dev Agent reports"],
        "safety_note": "Evidence Store is strict read-only. It explains supporting signals but does not persist evidence, write files, access memory, commit, push, deploy, or modify runtime behavior.",
    }


def evidence_store_registry() -> Dict[str, Any]:
    findings = []
    for finding_id, profile in EVIDENCE_FINDING_PROFILES.items():
        findings.append(
            {
                "id": finding_id,
                "evidence_items": profile["evidence_items"],
                "supporting_signals": profile["supporting_signals"],
                "risk_reasoning": profile["risk_reasoning"],
                "confidence_score": profile["confidence_score"],
            }
        )
    return {
        "layer": "26.6",
        "name": "Evidence Store Registry",
        "status": "evidence_store_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "finding_count": len(findings),
        "findings": findings,
        "related_agents": ["explorer", "planner", "verifier"],
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
            "real_data_storage": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_evidence_store_preview(
    finding: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    detected_finding = _select_finding(finding, command)
    profile = EVIDENCE_FINDING_PROFILES[detected_finding]
    command_or_finding = command or detected_finding
    area = project_area or detected_finding

    constitution = build_constitution_preview(
        command=command_or_finding,
        rule_source="project_rules",
        conflicting_rules=["store_evidence", "read_only_mode"],
        target_area=area,
    )
    project_rules = build_project_rules_preview(
        command=command_or_finding,
        project_rule_category="safety_rules",
        target_area=area,
    )
    explorer = explorer_agent_status()
    planner = planner_agent_status()
    verifier = verifier_agent_status()

    related_agents = ["explorer", "planner", "verifier"]
    supporting_signals = list(profile["supporting_signals"]) + [
        "constitution_engine",
        "project_rules_loader",
    ]

    return {
        "finding": detected_finding,
        "evidence_items": profile["evidence_items"],
        "supporting_signals": supporting_signals,
        "related_agents": related_agents,
        "confidence_reasoning": "multiple supporting preview signals agree" if profile["confidence_score"] >= 0.88 else "supporting preview signals are present but require future validation",
        "risk_reasoning": profile["risk_reasoning"],
        "confidence_score": profile["confidence_score"],
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
        "explorer_signal": {
            "agent_role": explorer.get("agent_role"),
            "allowed_capabilities": explorer.get("allowed_capabilities", []),
            "connected_layers": explorer.get("connected_layers", []),
        },
        "planner_signal": {
            "agent_role": planner.get("agent_role"),
            "allowed_capabilities": planner.get("allowed_capabilities", []),
            "connected_layers": planner.get("connected_layers", []),
        },
        "verifier_signal": {
            "agent_role": verifier.get("agent_role"),
            "allowed_capabilities": verifier.get("allowed_capabilities", []),
            "connected_layers": verifier.get("connected_layers", []),
        },
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "real_action_performed": False,
        "real_storage_performed": False,
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
        "real_data_stored": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Evidence Store returns a read-only explanation of supporting signals. It does not persist evidence, write files, use memory, commit, push, deploy, or change runtime behavior.",
    }
