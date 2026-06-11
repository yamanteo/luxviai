from __future__ import annotations

from typing import Any, Dict, List, Optional

from autonomous_engineering_coordinator_preview import (
    autonomous_engineering_coordinator_registry,
)
from deployment_verification_intelligence_preview import (
    deployment_verification_intelligence_registry,
)
# clone_workspace_intelligence_registry not used in this file
from verification_intelligence_preview import (
    verification_intelligence_registry,
)
from autonomous_repair_intelligence_preview import (
    autonomous_repair_intelligence_registry,
)
from luxcode_core_status_snapshot import (
    luxcode_core_status_snapshot,
)


ENGINEERING_MEMORY_CAPABILITIES = [
    "failure_pattern_tracking",
    "success_pattern_tracking",
    "repair_history_analysis",
    "strategy_memory_analysis",
    "repeated_failure_detection",
    "recovery_history_analysis",
    "solution_ranking",
    "engineering_experience_scoring",
    "similar_issue_matching",
    "strategy_recommendation_engine",
    "failure_summary_generation",
    "memory_health_analysis",
]

MEMORY_PIPELINE = [
    "problem_detection",
    "similar_issue_search",
    "successful_solution_search",
    "failed_solution_review",
    "alternative_strategy_selection",
    "new_strategy_generation",
    "verification",
    "memory_summary",
]

MEMORY_PROFILES: Dict[str, Dict[str, Any]] = {
    "no_history": {
        "aliases": ["no history", "yeni", "new", "fresh", "first_time"],
        "memory_status": "no_history",
        "memory_health": "pass",
        "memory_summary": "No engineering history found for this issue type. No prior failures or successes recorded. First attempt — proceed with standard strategy generation.",
        "health_score": 0.90,
        "risk_score": 0.10,
        "attempt_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "loop_risk": "none",
        "recommended_actions": ["collect_experience", "apply_default_strategy"],
        "recommended_next_action": "no prior history — proceed with standard repair strategy",
        "memory_signals": {
            "has_successful_history": False,
            "has_failed_history": False,
            "repeated_failures_detected": False,
            "loop_detected": False,
        },
    },
    "successful_history": {
        "aliases": ["success", "basarili", "solved", "cozulmus", "known_fix"],
        "memory_status": "successful_history",
        "memory_health": "pass",
        "memory_summary": "Successful repair history found. Prior solution resolved the same issue type. Reuse recommended with verification.",
        "health_score": 0.95,
        "risk_score": 0.05,
        "attempt_count": 3,
        "success_count": 2,
        "failure_count": 1,
        "loop_risk": "none",
        "recommended_actions": ["reuse_successful_strategy", "verify_known_solution"],
        "recommended_next_action": "known successful solution — reuse and verify",
        "memory_signals": {
            "has_successful_history": True,
            "has_failed_history": True,
            "repeated_failures_detected": False,
            "loop_detected": False,
            "known_solution": "targeted_fix",
        },
    },
    "mixed_history": {
        "aliases": ["mixed", "karma", "partial", "inconsistent"],
        "memory_status": "mixed_history",
        "memory_health": "warning",
        "memory_summary": "Mixed engineering history. Both successes and failures recorded for this issue type. Review prior attempts before selecting strategy.",
        "health_score": 0.75,
        "risk_score": 0.30,
        "attempt_count": 6,
        "success_count": 3,
        "failure_count": 3,
        "loop_risk": "low",
        "recommended_actions": ["review_prior_attempts", "compare_strategies"],
        "recommended_next_action": "mixed history — review prior successes and failures before proceeding",
        "memory_signals": {
            "has_successful_history": True,
            "has_failed_history": True,
            "repeated_failures_detected": False,
            "loop_detected": False,
        },
    },
    "repeated_failure": {
        "aliases": ["repeated failure", "tekrarlayan hata", "stuck", "persistent"],
        "memory_status": "repeated_failure",
        "memory_health": "degraded",
        "memory_summary": "Repeated failures detected for this issue type. Same or similar strategies attempted without success. Alternative strategy required.",
        "health_score": 0.45,
        "risk_score": 0.75,
        "attempt_count": 8,
        "success_count": 1,
        "failure_count": 7,
        "loop_risk": "medium",
        "recommended_actions": [
            "alternative_strategy_required",
            "run_root_cause_analysis",
            "escalate_to_engineering_review",
        ],
        "recommended_next_action": "repeated failures — alternative strategy required",
        "memory_signals": {
            "has_successful_history": True,
            "has_failed_history": True,
            "repeated_failures_detected": True,
            "repeated_strategies": ["targeted_fix", "minimal_patch"],
            "loop_detected": False,
        },
    },
    "loop_risk": {
        "aliases": ["loop", "dongu", "endless", "infinite", "cycle"],
        "memory_status": "loop_risk",
        "memory_health": "critical",
        "memory_summary": "Loop risk detected. Same strategy attempted multiple times with identical failure patterns. Repeated attempt must be blocked. New approach required.",
        "health_score": 0.25,
        "risk_score": 0.90,
        "attempt_count": 12,
        "success_count": 1,
        "failure_count": 11,
        "loop_risk": "high",
        "recommended_actions": [
            "block_repeated_attempt",
            "force_alternative_strategy",
            "escalate_to_engineering_review",
        ],
        "recommended_next_action": "loop risk — block repeated attempt and force new strategy",
        "memory_signals": {
            "has_successful_history": True,
            "has_failed_history": True,
            "repeated_failures_detected": True,
            "repeated_strategies": ["targeted_fix", "minimal_patch", "safe_rebuild"],
            "loop_detected": True,
            "loop_type": "same_strategy_repetition",
            "loop_count": 4,
        },
    },
}

# ---------- internal helpers ----------


def _select_memory_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in MEMORY_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "no_history"


def _compute_failure_analysis(pid: str) -> Dict[str, Any]:
    p = MEMORY_PROFILES.get(pid, {})
    signals = p.get("memory_signals", {})
    health = p.get("health_score", 0.50)
    failures = p.get("failure_count", 0)

    failure_risk = "low" if health > 0.70 else ("medium" if health > 0.40 else "high")
    return {
        "failure_patterns": [
            "repair_strategy_mismatch" if failures > 2 else "insufficient_data",
            "verification_gap" if failures > 4 else None,
            "root_cause_misidentified" if failures > 6 else None,
        ],
        "failure_frequency": "rare" if failures < 3 else (
            "occasional" if failures < 6 else "frequent"
        ),
        "failure_risk": failure_risk,
        "failed_repairs": max(0, failures - 2),
        "failed_deployments": max(0, failures - 4),
        "failed_verifications": max(0, failures - 3),
        "failed_transfers": max(0, failures - 5),
        "failed_workflows": max(0, failures - 6),
        "repeated_strategies_detected": signals.get("repeated_strategies", []),
        "read_only": True,
        "preview_only": True,
    }


def _compute_success_analysis(pid: str) -> Dict[str, Any]:
    p = MEMORY_PROFILES.get(pid, {})
    signals = p.get("memory_signals", {})
    health = p.get("health_score", 0.50)
    successes = p.get("success_count", 0)

    success_score = round(health * 0.85, 2)
    return {
        "success_patterns": (
            ["known_fix_applied"] if successes > 0
            else ["no_prior_success"]
        ),
        "success_score": success_score,
        "recommended_strategy": signals.get("known_solution", "default_strategy"),
        "successful_repairs": max(0, successes - 2),
        "successful_deployments": max(0, successes - 1),
        "successful_verifications": max(0, successes - 2),
        "successful_recoveries": max(0, successes - 3),
        "confidence_in_success": "high" if success_score > 0.70 else (
            "medium" if success_score > 0.40 else "low"
        ),
        "read_only": True,
        "preview_only": True,
    }


def _compute_similar_issues(pid: str) -> Dict[str, Any]:
    p = MEMORY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    attempts = p.get("attempt_count", 0)

    similarity = round(min(1.0, health * 0.7 + 0.2), 2)
    return {
        "similarity_score": similarity,
        "matched_cases": (
            [
                {"case_id": "CASE-001", "similarity": 0.92, "strategy": "targeted_fix", "outcome": "success"},
                {"case_id": "CASE-002", "similarity": 0.78, "strategy": "minimal_patch", "outcome": "failure"},
            ] if attempts > 0 else []
        ),
        "recommended_actions": (
            ["apply_known_strategy", "verify_outcome"] if similarity > 0.70
            else ["gather_more_data", "run_root_cause_analysis"]
        ),
        "error_patterns": ["logic_error", "dependency_conflict"] if health < 0.60 else [],
        "workflow_patterns": ["verification_loop"] if health < 0.40 else [],
        "dependency_patterns": ["version_mismatch"] if health < 0.50 else [],
        "verification_patterns": ["regression_detected"] if health < 0.50 else [],
        "read_only": True,
        "preview_only": True,
    }


def _compute_loop_analysis(pid: str) -> Dict[str, Any]:
    p = MEMORY_PROFILES.get(pid, {})
    signals = p.get("memory_signals", {})
    health = p.get("health_score", 0.50)

    loop_risk = p.get("loop_risk", "none")
    loop_detected = signals.get("loop_detected", False)
    loop_count = signals.get("loop_count", 0)

    return {
        "loop_risk": loop_risk,
        "loop_reason": (
            "no_loop_detected" if not loop_detected
            else f"same_strategy_repeated_{loop_count}_times"
        ),
        "recommended_exit_strategy": (
            "none_required" if not loop_detected
            else "force_hybrid_strategy" if loop_risk in ("low", "medium")
            else "escalate_and_block_repeated_attempts"
        ),
        "same_strategy_repetition": loop_detected,
        "same_failure_repetition": signals.get("repeated_failures_detected", False),
        "verification_loops": health < 0.40,
        "repair_loops": health < 0.30,
        "deployment_loops": health < 0.20,
        "loop_count": loop_count,
        "repeated_strategies": signals.get("repeated_strategies", []),
        "read_only": True,
        "preview_only": True,
    }


def _compute_experience_score(pid: str) -> Dict[str, float]:
    p = MEMORY_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    repair_exp = round(health * 0.80, 2)
    ver_exp = round(health * 0.75, 2)
    deploy_exp = round(health * 0.70, 2)
    recovery_exp = round(health * 0.65, 2)
    overall = round(
        (repair_exp * 0.3 + ver_exp * 0.25 + deploy_exp * 0.25 + recovery_exp * 0.20), 2
    )
    return {
        "repair_experience": repair_exp,
        "verification_experience": ver_exp,
        "deployment_experience": deploy_exp,
        "recovery_experience": recovery_exp,
        "overall_experience_score": overall,
    }


# ---------- public entry points ----------


def engineering_memory_intelligence_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "35.2",
        "name": "Engineering Memory & Failure Intelligence Preview",
        "status": "engineering_memory_ready",
        "version": "1.0",
        "capabilities": ENGINEERING_MEMORY_CAPABILITIES,
        "pipeline": MEMORY_PIPELINE,
        "memory_profile_count": len(MEMORY_PROFILES),
        "operation_mode": "read_only_preview_only",
        "core_rule": "no_endless_loops_allowed",
        "connected_layers": ["35.1", "35.0", "34.9", "34.8", "34.7"],
        "available_endpoints": [
            "/engineering-memory/status",
            "/engineering-memory/capabilities",
            "/engineering-memory/preview",
            "/engineering-memory/similar-issues",
            "/engineering-memory/failure-analysis",
            "/engineering-memory/success-analysis",
            "/engineering-memory/loop-analysis",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "memory_write": False,
        "repair_execution": False,
        "deployment_execution": False,
        "verification_execution": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only engineering memory intelligence preview. No actual memory writes or engineering actions performed.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def engineering_memory_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "35.2",
        "name": "Engineering Memory & Failure Intelligence Capabilities",
        "status": "memory_capabilities_ready",
        "capabilities": [
            {"name": "failure_pattern_tracking", "description": "Track failure patterns across repairs, deployments, verifications, transfers, workflows", "read_only": True},
            {"name": "success_pattern_tracking", "description": "Track successful patterns across repairs, deployments, verifications, recoveries", "read_only": True},
            {"name": "repair_history_analysis", "description": "Analyze repair history for patterns and trends", "read_only": True},
            {"name": "strategy_memory_analysis", "description": "Analyze strategy memory for known solutions", "read_only": True},
            {"name": "repeated_failure_detection", "description": "Detect repeated failures with same or similar strategies", "read_only": True},
            {"name": "recovery_history_analysis", "description": "Analyze recovery history for patterns", "read_only": True},
            {"name": "solution_ranking", "description": "Rank known solutions by success rate", "read_only": True},
            {"name": "engineering_experience_scoring", "description": "Score engineering experience across repair, verification, deployment, recovery", "read_only": True},
            {"name": "similar_issue_matching", "description": "Match current issue against prior engineering memory", "read_only": True},
            {"name": "strategy_recommendation_engine", "description": "Recommend strategies based on engineering memory", "read_only": True},
            {"name": "failure_summary_generation", "description": "Generate comprehensive failure summary", "read_only": True},
            {"name": "memory_health_analysis", "description": "Analyze memory health and completeness", "read_only": True},
        ],
        "pipeline": MEMORY_PIPELINE,
        "memory_profiles": list(MEMORY_PROFILES.keys()),
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def engineering_memory_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_memory_profile(target_issue, command, project_area)
    p = MEMORY_PROFILES[pid]
    experience = _compute_experience_score(pid)

    return {
        "memory_id": pid,
        "memory_status": p["memory_status"],
        "memory_health": p["memory_health"],
        "memory_summary": p.get("memory_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "attempt_count": p.get("attempt_count"),
        "success_count": p.get("success_count"),
        "failure_count": p.get("failure_count"),
        "loop_risk": p.get("loop_risk"),
        "experience_score": experience,
        "memory_signals": p.get("memory_signals", {}),
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_stage": "problem_detection",
        "pipeline_progress": {
            "completed": [],
            "current": "problem_detection",
            "remaining": MEMORY_PIPELINE[1:],
        },
        "read_only": True,
        "preview_only": True,
    }


def engineering_memory_similar_issues(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_memory_profile(target_issue)
    similar = _compute_similar_issues(pid)
    experience = _compute_experience_score(pid)

    return {
        "similar_issues": similar,
        "experience_score": experience,
        "pipeline_stage": "similar_issue_search",
        "read_only": True,
        "preview_only": True,
    }


def engineering_memory_failure_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_memory_profile(target_issue)
    failure = _compute_failure_analysis(pid)

    return {
        "failure_analysis": failure,
        "pipeline_stage": "failed_solution_review",
        "read_only": True,
        "preview_only": True,
    }


def engineering_memory_success_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_memory_profile(target_issue)
    success = _compute_success_analysis(pid)

    return {
        "success_analysis": success,
        "pipeline_stage": "successful_solution_search",
        "read_only": True,
        "preview_only": True,
    }


def engineering_memory_loop_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_memory_profile(target_issue)
    loop = _compute_loop_analysis(pid)

    return {
        "loop_analysis": loop,
        "pipeline_stage": "alternative_strategy_selection",
        "read_only": True,
        "preview_only": True,
    }


def engineering_memory_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for mid, m in MEMORY_PROFILES.items():
        items.append({
            "memory_id": mid,
            "memory_status": m["memory_status"],
            "memory_health": m["memory_health"],
            "health_score": m.get("health_score"),
            "risk_score": m.get("risk_score"),
            "attempt_count": m.get("attempt_count"),
            "success_count": m.get("success_count"),
            "failure_count": m.get("failure_count"),
            "loop_risk": m.get("loop_risk"),
        })
    return {
        "layer": "35.2",
        "name": "Engineering Memory & Failure Intelligence Registry",
        "status": "memory_registry_ready",
        "read_only": True,
        "preview_only": True,
        "memory_profile_count": len(items),
        "memory_profiles": items,
        "pass_count": sum(1 for i in items if i["memory_health"] == "pass"),
        "warning_count": sum(1 for i in items if i["memory_health"] == "warning"),
        "degraded_count": sum(1 for i in items if i["memory_health"] == "degraded"),
        "critical_count": sum(1 for i in items if i["memory_health"] == "critical"),
        "total_attempts": sum(i.get("attempt_count", 0) for i in items),
        "total_successes": sum(i.get("success_count", 0) for i in items),
        "total_failures": sum(i.get("failure_count", 0) for i in items),
    }
