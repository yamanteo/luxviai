from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set


ROUTER_POLICY_VERSION = "zero_cost_router_policy_v1"
MAX_ROUTER_CHECKS = 120


def _stable_json(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "zero-cost-" + sha256(_stable_json(value).encode("utf-8")).hexdigest()[:24]


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _to_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


TIER_LEVELS: List[Dict[str, Any]] = [
    {
        "tier_id": "deterministic_local_tools",
        "tier_number": 0,
        "display_name": "Deterministic Local Tools",
        "engine_class": "deterministic_tooling",
        "cost_class": "free",
        "default_enabled": True,
        "requires_network": False,
        "requires_external_provider": False,
        "supports_real_execution": False,
        "supports_code_generation": False,
        "supports_repo_analysis": True,
        "supports_multifile_analysis": True,
        "supports_visual_input": False,
        "supports_terminal": False,
        "supports_browser": False,
        "supports_patch_apply": False,
        "supports_test_execution": False,
        "supports_long_context": False,
        "supports_structured_output": True,
        "supports_tool_calling": False,
        "privacy_class": "local_first",
        "expected_latency_class": "low",
        "resource_class": "cpu_light",
        "paid": False,
        "emergency_only": False,
        "capability_matrix": [
            "path_search",
            "symbol_search",
            "file_diff",
            "repo_health_scan",
            "adjacent_issue_scan",
            "selection_pack",
            "safe_route_planning",
        ],
        "cost_hint": 0,
        "cost_rank": 0,
    },
    {
        "tier_id": "lightweight_local_coding_model",
        "tier_number": 1,
        "display_name": "Lightweight Local Coding Model",
        "engine_class": "local_light_model",
        "cost_class": "free",
        "default_enabled": True,
        "requires_network": False,
        "requires_external_provider": False,
        "supports_real_execution": False,
        "supports_code_generation": True,
        "supports_repo_analysis": True,
        "supports_multifile_analysis": True,
        "supports_visual_input": False,
        "supports_terminal": False,
        "supports_browser": False,
        "supports_patch_apply": True,
        "supports_test_execution": False,
        "supports_long_context": False,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "privacy_class": "local_first",
        "expected_latency_class": "low",
        "resource_class": "cpu_light",
        "paid": False,
        "emergency_only": False,
        "capability_matrix": [
            "code_generation",
            "repair_plan",
            "small_diff_planning",
            "change_classification",
            "patch_candidate_draft",
            "safe_edit_recommendation",
        ],
        "cost_hint": 0,
        "cost_rank": 1,
    },
    {
        "tier_id": "free_cloud_open_coding_model",
        "tier_number": 2,
        "display_name": "Free Cloud Open Coding Model",
        "engine_class": "cloud_open_model",
        "cost_class": "free",
        "default_enabled": True,
        "requires_network": True,
        "requires_external_provider": True,
        "supports_real_execution": False,
        "supports_code_generation": True,
        "supports_repo_analysis": True,
        "supports_multifile_analysis": True,
        "supports_visual_input": False,
        "supports_terminal": False,
        "supports_browser": False,
        "supports_patch_apply": True,
        "supports_test_execution": True,
        "supports_long_context": True,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "privacy_class": "network_restricted",
        "expected_latency_class": "medium",
        "resource_class": "network_light",
        "paid": False,
        "emergency_only": False,
        "capability_matrix": [
            "multifile_planning",
            "patch_drafting",
            "test_plan",
            "large_context_summary",
            "risk_aware_reasoning",
        ],
        "cost_hint": 0,
        "cost_rank": 2,
    },
    {
        "tier_id": "gemini_ai_studio_free",
        "tier_number": 3,
        "display_name": "Gemini AI Studio Free",
        "engine_class": "gemini_studio",
        "cost_class": "free",
        "default_enabled": True,
        "requires_network": True,
        "requires_external_provider": True,
        "supports_real_execution": False,
        "supports_code_generation": True,
        "supports_repo_analysis": True,
        "supports_multifile_analysis": True,
        "supports_visual_input": True,
        "supports_terminal": False,
        "supports_browser": True,
        "supports_patch_apply": True,
        "supports_test_execution": True,
        "supports_long_context": True,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "privacy_class": "network_restricted",
        "expected_latency_class": "medium",
        "resource_class": "network_light",
        "paid": False,
        "emergency_only": False,
        "capability_matrix": [
            "visual_analysis",
            "ui_analysis",
            "ux_diff_reasoning",
            "structured_reporting",
            "large_context_reasoning",
        ],
        "cost_hint": 0,
        "cost_rank": 3,
    },
    {
        "tier_id": "direct_deepseek_api",
        "tier_number": 4,
        "display_name": "Direct DeepSeek API",
        "engine_class": "deepseek_api",
        "cost_class": "low_cost_paid",
        "default_enabled": True,
        "requires_network": True,
        "requires_external_provider": True,
        "supports_real_execution": False,
        "supports_code_generation": True,
        "supports_repo_analysis": True,
        "supports_multifile_analysis": True,
        "supports_visual_input": True,
        "supports_terminal": False,
        "supports_browser": True,
        "supports_patch_apply": True,
        "supports_test_execution": True,
        "supports_long_context": True,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "privacy_class": "network_required",
        "expected_latency_class": "medium",
        "resource_class": "network_medium",
        "paid": True,
        "emergency_only": False,
        "capability_matrix": [
            "reasoning",
            "complex_planning",
            "high_context_tasking",
            "large_refactor_draft",
            "runtime_explanation",
        ],
        "cost_hint": 1,
        "cost_rank": 4,
    },
    {
        "tier_id": "whale_agent_execution",
        "tier_number": 5,
        "display_name": "Whale Agent Execution",
        "engine_class": "whale_agent",
        "cost_class": "agent_hours",
        "default_enabled": True,
        "requires_network": True,
        "requires_external_provider": False,
        "supports_real_execution": True,
        "supports_code_generation": True,
        "supports_repo_analysis": True,
        "supports_multifile_analysis": True,
        "supports_visual_input": True,
        "supports_terminal": True,
        "supports_browser": True,
        "supports_patch_apply": True,
        "supports_test_execution": True,
        "supports_long_context": True,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "privacy_class": "agent_runtime",
        "expected_latency_class": "high",
        "resource_class": "high",
        "paid": True,
        "emergency_only": False,
        "capability_matrix": [
            "terminal_execution",
            "browser_interaction",
            "live_network_check",
            "repo_refactor",
            "deployment_assessment",
        ],
        "cost_hint": 4,
        "cost_rank": 5,
    },
    {
        "tier_id": "codex_emergency_escalation",
        "tier_number": 6,
        "display_name": "Codex Emergency Escalation",
        "engine_class": "codex_escalation",
        "cost_class": "agent_hours_high",
        "default_enabled": False,
        "requires_network": True,
        "requires_external_provider": True,
        "supports_real_execution": True,
        "supports_code_generation": True,
        "supports_repo_analysis": True,
        "supports_multifile_analysis": True,
        "supports_visual_input": True,
        "supports_terminal": True,
        "supports_browser": True,
        "supports_patch_apply": True,
        "supports_test_execution": True,
        "supports_long_context": True,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "privacy_class": "network_required",
        "expected_latency_class": "high",
        "resource_class": "highest",
        "paid": True,
        "emergency_only": True,
        "capability_matrix": [
            "critical_recovery",
            "deep_reasoning",
            "production_incident",
            "security_recovery",
            "final_continuity_decision",
        ],
        "cost_hint": 8,
        "cost_rank": 6,
    },
]


TASK_CLASSES: List[str] = [
    "deterministic_lookup",
    "file_path_analysis",
    "dependency_analysis",
    "small_code_fix",
    "medium_code_fix",
    "large_multifile_change",
    "repo_architecture_analysis",
    "test_generation",
    "test_failure_analysis",
    "visual_ui_analysis",
    "browser_interaction",
    "terminal_execution",
    "deployment_analysis",
    "deployment_execution",
    "security_sensitive_change",
    "critical_production_change",
    "documentation",
    "summarization",
    "unknown",
]


DEFAULT_POLICY: Dict[str, Any] = {
    "billing_allowed": False,
    "automatic_upgrade": False,
    "automatic_credit_purchase": False,
    "hard_cost_cap_usd": 0,
    "paid_escalation_allowed": False,
    "policy_version": ROUTER_POLICY_VERSION,
    "max_fallback_depth": 4,
    "network_allowed": False,
    "quota_retry_enabled": False,
}


AVAILABILITY_STATES: Set[str] = {
    "available",
    "degraded",
    "slow",
    "cold_starting",
    "rate_limited",
    "quota_exhausted",
    "authentication_failed",
    "temporarily_unavailable",
    "resource_pressure",
    "disabled",
    "stalled",
    "unknown",
}


SKIP_REASON_MAP = {
    "missing_capability",
    "network_not_allowed",
    "paid_not_allowed",
    "privacy_conflict",
    "resource_limit",
    "execution_not_supported",
    "tier_disabled",
    "provider_unavailable",
    "quota_exhausted",
    "authentication_failed",
    "emergency_only",
}


CLASS_CAPABILITY_MAP: Dict[str, List[str]] = {
    "deterministic_lookup": ["file_search", "selection_pack", "safe_route_planning"],
    "file_path_analysis": ["path_search", "selection_pack"],
    "dependency_analysis": ["symbol_search", "repo_health_scan"],
    "small_code_fix": ["code_generation", "safe_edit_recommendation", "file_diff"],
    "medium_code_fix": ["code_generation", "patch_drafting", "code_generation", "safe_edit_recommendation"],
    "large_multifile_change": ["multifile_planning", "repo_health_scan", "patch_drafting", "test_plan"],
    "repo_architecture_analysis": ["repo_health_scan", "large_context_summary", "symbol_search"],
    "test_generation": ["test_plan", "safe_route_planning", "patch_candidate_draft"],
    "test_failure_analysis": ["repo_health_scan", "verification_plan", "safe_route_planning"],
    "visual_ui_analysis": ["visual_analysis", "ui_analysis", "structured_reporting"],
    "browser_interaction": ["browser_interaction", "ui_analysis", "safe_route_planning"],
    "terminal_execution": ["terminal_execution", "verification_plan", "patch_candidate_draft"],
    "deployment_analysis": ["deployment_assessment", "safe_route_planning", "repo_health_scan"],
    "deployment_execution": ["deployment_assessment", "terminal_execution", "test_plan", "browser_interaction"],
    "security_sensitive_change": ["security_policy_analysis", "verification_plan", "terminal_execution"],
    "critical_production_change": ["critical_recovery", "security_policy_analysis", "risk_assessment"],
    "documentation": ["documentation", "structured_reporting", "summary_generation"],
    "summarization": ["summary_generation", "safe_route_planning", "selection_pack"],
    "unknown": ["safe_route_planning", "symbol_search", "repo_health_scan"],
}


CLASS_HINTS = {
    "deterministic_lookup": ["lookup", "bul", "ara", "tanÄ±", "ne yapt", "what is", "hangi dosya", "hangi fonksiyon"],
    "file_path_analysis": ["file_path", "path analysis", "where is the", "which file", "file search", "directory", "path hint", "dosya yolu"],
    "dependency_analysis": ["dependency", "bag\u0131ml\u0131l\u0131k", "dependency graph", "import", "kullan\u0131m", "dependent", "module"],
    "unknown": ["unclear", "unknown", "determine", "need more context", "ne yaptığını bilmiyorum", "unknown intent"],
    "small_code_fix": ["fix", "dÃ¼zelt", "bug", "hata", "yanlÄ±ÅŸ", "wrong", "error", "dÃ¼zel", "hatasÄ±nÄ±", "patch"],
    "medium_code_fix": ["refactor", "refaktÃ¶", "Ã¶zelleÅŸtir", "geliÅŸtir", "optimize et", "clean"],
    "large_multifile_change": ["Ã§ok dosya", "Ã§oklu", "scaffold", "yeniden yaz", "geniÅŸ", "bÃ¼yÃ¼k", "architecture", "refactor architecture"],
    "repo_architecture_analysis": ["katman", "yapÄ±", "architecture", "flow", "dizayn", "mimari"],
    "test_generation": ["test", "deneme", "pytest", "unit test", "integration"],
    "test_failure_analysis": ["test baÅŸarÄ±sÄ±z", "test failed", "hata analizi", "ci", "fail"],
    "visual_ui_analysis": ["ui", "arayÃ¼z", "ekran", "gÃ¶rsel", "screenshot", "layout", "css", "design"],
    "browser_interaction": ["tarayÄ±cÄ±", "browser", "sayfa", "playwright", "selenium"],
    "terminal_execution": ["terminal", "komut", "komut Ã§alÄ±ÅŸtÄ±r", "run", "shell", "cmd", "python"],
    "deployment_analysis": ["deploy", "yayÄ±n", "deployment", "release", "pipeline"],
    "deployment_execution": ["deploy et", "canlÄ±ya al", "release et", "production"],
    "security_sensitive_change": ["secret", "anahtar", "sifre", "password", "api key", "credential", "authorization", "private"],
    "critical_production_change": ["kritik", "acil", "prod", "canlÄ±", "production", "Ã¶zel eriÅŸim", "outage", "kesin"],
    "documentation": ["dokÃ¼mantasyon", "readme", "doc", " aÃ§Ä±klama", "documentation"],
    "summarization": ["Ã¶zet", "summary", "Ã¶zetle", "sum up", "short"],
}


def _tier_lookup(tier_id: str) -> Dict[str, Any]:
    for tier in TIER_LEVELS:
        if tier["tier_id"] == tier_id:
            return tier
    raise KeyError(f"unknown tier {tier_id}")


def _clamp_text(value: str, max_len: int) -> str:
    text = _normalize(value)
    if len(text) <= max_len:
        return text
    return text[:max_len]


def get_zero_cost_router_schema() -> Dict[str, Any]:
    return {
        "name": "LuxCode Zero-Cost Execution Router",
        "status": "local_first_read_only_planner",
        "version": ROUTER_POLICY_VERSION,
        "supported_layers": 7,
        "supported_task_classes": sorted(TASK_CLASSES),
        "supported_capabilities": sorted({cap for caps in CLASS_CAPABILITY_MAP.values() for cap in caps}),
        "policy_fields": sorted(DEFAULT_POLICY.keys()),
        "safety_boundaries": {
            "supports_real_execution": False,
            "supports_external_api_call": False,
            "supports_direct_provider_call": False,
            "supports_shell_execution": False,
            "supports_file_write": False,
            "supports_deploy": False,
        },
        "required_endpoints": [
            "/luxcode-zero-cost-router/schema",
            "/luxcode-zero-cost-router/registry",
            "/luxcode-zero-cost-router/policy",
            "/luxcode-zero-cost-router/classify",
            "/luxcode-zero-cost-router/score",
            "/luxcode-zero-cost-router/capability-match",
            "/luxcode-zero-cost-router/availability",
            "/luxcode-zero-cost-router/route",
            "/luxcode-zero-cost-router/validate-decision",
            "/debug/luxcode-zero-cost-router-status",
        ],
    }


def _safe_flag_snapshot() -> Dict[str, Any]:
    return {
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def get_zero_cost_router_registry() -> Dict[str, Any]:
    return {
        "name": "Zero-Cost Router Tier Registry",
        "policy_version": ROUTER_POLICY_VERSION,
        "tier_count": len(TIER_LEVELS),
        "tiers": [_clean_tier(tier) for tier in _ordered_tiers()],
        **_safe_flag_snapshot(),
    }


def get_zero_cost_router_policy() -> Dict[str, Any]:
    policy = deepcopy(DEFAULT_POLICY)
    policy["policy_version"] = ROUTER_POLICY_VERSION
    return policy


def _ordered_tiers() -> List[Dict[str, Any]]:
    return sorted((deepcopy(tier) for tier in TIER_LEVELS), key=lambda item: (item["cost_rank"], item["tier_number"], item["tier_id"]))


def _clean_tier(tier: Dict[str, Any]) -> Dict[str, Any]:
    copy = deepcopy(tier)
    copy["capability_count"] = len(copy.get("capability_matrix", []))
    return copy


def _build_capability_set(*parts: Iterable[str]) -> Set[str]:
    capabilities: Set[str] = set()
    for part in parts:
        capabilities.update(item.strip() for item in part if item and str(item).strip())
    return {value.replace("-", "_") for value in capabilities}


def _keyword_signal(text: str, keywords: Sequence[str]) -> bool:
    value = _normalize(text)
    return any(keyword.lower() in value for keyword in keywords)


def _detect_task_class(title: str, description: str, requested_capabilities: Iterable[str], selected_files: Iterable[str]) -> str:
    combined = f"{title} {description}"
    caps = _build_capability_set(requested_capabilities)
    if selected_files and any("test" in _normalize(path) for path in selected_files):
        caps.add("test_plan")
    normalized = _normalize(combined)
    for task_class, hints in CLASS_HINTS.items():
        if any(hint in normalized for hint in hints):
            return task_class
    if any(cap in {"path_search", "symbol_search"} for cap in caps):
        return "dependency_analysis"
    if any(cap in {"terminal_execution", "command"} for cap in caps):
        return "terminal_execution"
    if any(cap in {"browser_interaction"} for cap in caps):
        return "browser_interaction"
    return "unknown"


def _risk_level(task_class: str, user_risk_hint: Optional[str]) -> str:
    hint = _normalize(user_risk_hint or "")
    if task_class in {"critical_production_change", "security_sensitive_change", "deployment_execution", "terminal_execution", "browser_interaction"}:
        return "high"
    if hint in {"critical", "high"}:
        return "high"
    if task_class in {"medium_code_fix", "large_multifile_change", "test_failure_analysis"}:
        return "medium"
    return "low"


def classify_zero_cost_task(
    task_id: str = "",
    title: str = "",
    description: str = "",
    requested_capabilities: Optional[Iterable[str]] = None,
    selected_files: Optional[Iterable[str]] = None,
    risk_hint: Optional[str] = None,
    user_requires_free_only: bool = True,
    selected_tier_ids: Optional[Iterable[str]] = None,
    prior_failures: int = 0,
    retry_count: int = 0,
) -> Dict[str, Any]:
    requested = _to_list(requested_capabilities)
    files = _to_list(selected_files)
    task_class = _detect_task_class(title, description, requested, files)
    secondary_classes = sorted({task_class, _secondary_class(task_class), "unknown"} - {"unknown"}) if task_class != "unknown" else []
    capabilities = sorted(_build_capability_set(requested, CLASS_CAPABILITY_MAP.get(task_class, []), CLASS_CAPABILITY_MAP.get("unknown", [])))
    forbidden_capabilities = sorted({"external_network_write", "shell_exec", "commit", "push", "deploy"} if user_requires_free_only else {})
    reasons = [
        "local-first policy selected",
        f"classified as {task_class}",
        "deterministic keyword and capability heuristic",
    ]
    confidence = _determine_confidence(task_class, requested, files, title, description)
    if _normalize(risk_hint) in {"critical", "high"}:
        reasons.append("risk_hint elevated")
    if selected_tier_ids:
        reasons.append("requested_tier_constraints_present")
    return {
        "task_id": task_id,
        "title": _clamp_text(title, 800),
        "description": _clamp_text(description, 3000),
        "task_class": task_class,
        "secondary_classes": secondary_classes,
        "required_capabilities": capabilities,
        "forbidden_capabilities": forbidden_capabilities,
        "risk_level": _risk_level(task_class, risk_hint),
        "confidence": round(float(confidence), 2),
        "classification_reasons": reasons,
        "user_requires_free_only": bool(user_requires_free_only),
        "selected_tier_ids": _to_list(selected_tier_ids),
        "prior_failures": int(prior_failures),
        "retry_count": int(retry_count),
        "policy_version": ROUTER_POLICY_VERSION,
        "decision_hint": "lowest-cost capable route preferred; paid escalation blocked without explicit allowance",
        **_safe_flag_snapshot(),
    }


def _secondary_class(task_class: str) -> str:
    if task_class in {"small_code_fix", "medium_code_fix"}:
        return "file_path_analysis"
    if task_class in {"large_multifile_change", "repo_architecture_analysis", "deployment_execution"}:
        return "deployment_analysis"
    if task_class in {"test_failure_analysis", "test_generation"}:
        return "test_failure_analysis"
    if task_class in {"visual_ui_analysis", "browser_interaction"}:
        return "visual_ui_analysis"
    if task_class in {"security_sensitive_change", "critical_production_change"}:
        return "security_sensitive_change"
    return "unknown"


def _feature_score(value: str, keywords: Sequence[str], weight: int) -> int:
    return sum(weight for word in keywords if word in _normalize(value))


def _determine_confidence(
    task_class: str,
    requested_capabilities: Iterable[str],
    selected_files: Iterable[str],
    title: str,
    description: str,
) -> float:
    score = 0.2
    requested = _to_list(requested_capabilities)
    files = _to_list(selected_files)
    flat = _normalize(f"{title} {description}")
    if task_class != "unknown":
        score += 0.35
    if len(requested) > 2:
        score += 0.12
    if files:
        score += min(len(files), 3) * 0.06
    if len(flat) > 25:
        score += 0.08
    if len(flat) > 140:
        score += 0.08
    if " " in flat and len(flat) > 0:
        score += 0.15
    return max(0.05, min(0.99, score))


def score_zero_cost_task(
    task_id: str = "",
    task_class: str = "unknown",
    title: str = "",
    description: str = "",
    required_capabilities: Optional[Iterable[str]] = None,
    selected_files: Optional[Iterable[str]] = None,
    risk_level: Optional[str] = None,
    failed_attempts: int = 0,
    unknown_root_causes: int = 0,
    user_rejections: int = 0,
) -> Dict[str, Any]:
    requested = _to_list(required_capabilities)
    files = _to_list(selected_files)
    normalized_class = task_class if task_class in TASK_CLASSES else "unknown"
    difficulty = _difficulty_from_inputs(normalized_class, title, description, requested, files, failed_attempts, unknown_root_causes, user_rejections)
    difficulty_reasons = _difficulty_reasons(normalized_class, title, description, requested, files, failed_attempts, unknown_root_causes, user_rejections)
    risk = _risk_level(normalized_class, risk_level)
    return {
        "task_id": task_id,
        "task_class": normalized_class,
        "difficulty_score": difficulty,
        "risk_level": risk,
        "required_capabilities": requested,
        "selected_files_count": len(files),
        "failed_attempts": int(failed_attempts),
        "unknown_root_causes": int(unknown_root_causes),
        "user_rejections": int(user_rejections),
        "difficulty_reasons": difficulty_reasons,
        "estimated_retry_impact": "increased" if failed_attempts else "none",
        "policy_version": ROUTER_POLICY_VERSION,
        **_safe_flag_snapshot(),
    }


def _difficulty_from_inputs(
    task_class: str,
    title: str,
    description: str,
    required_capabilities: List[str],
    selected_files: List[str],
    failed_attempts: int,
    unknown_root_causes: int,
    user_rejections: int,
) -> int:
    difficulty = 1
    normalized = _normalize(f"{title} {description}")
    file_count = len(selected_files) + len(_to_list([s for s in selected_files if "/" in s or "\\" in s]))
    difficulty += min(3, file_count)
    difficulty += min(2, len(required_capabilities))
    difficulty += _feature_score(normalized, ("class", "fonksiyon", "modÃ¼l", "dosya", "class ", "api"), 1)
    if task_class == "large_multifile_change":
        difficulty += 3
    if task_class == "repo_architecture_analysis":
        difficulty += 2
    if task_class == "deployment_execution":
        difficulty += 4
    if task_class == "terminal_execution":
        difficulty += 2
    if task_class in {"critical_production_change", "security_sensitive_change"}:
        difficulty += 2
    difficulty += min(2, failed_attempts)
    difficulty += min(2, unknown_root_causes)
    difficulty += min(1, user_rejections)
    return max(1, min(10, difficulty))


def _difficulty_reasons(
    task_class: str,
    title: str,
    description: str,
    required_capabilities: List[str],
    selected_files: List[str],
    failed_attempts: int,
    unknown_root_causes: int,
    user_rejections: int,
) -> List[str]:
    reasons: List[str] = []
    norm = _normalize(f"{title} {description}")
    if selected_files:
        reasons.append("selected files provided")
    if len(required_capabilities) > 2:
        reasons.append("multiple required capabilities")
    if "Ã§oklu" in norm or "multiple" in norm:
        reasons.append("multifile or multi-target intent")
    if failed_attempts:
        reasons.append("previous failed attempts detected")
    if unknown_root_causes:
        reasons.append("unknown root cause count increased")
    if user_rejections:
        reasons.append("user rejections observed")
    if task_class in {"critical_production_change", "security_sensitive_change", "deployment_execution"}:
        reasons.append("risk-sensitive class elevated")
    if task_class in {"visual_ui_analysis", "browser_interaction"}:
        reasons.append("visual/ui complexity considered")
    return reasons or ["general task complexity baseline"]


def capability_match_zero_cost_engine(
    task_id: str = "",
    task_class: str = "unknown",
    required_capabilities: Optional[Iterable[str]] = None,
    forbidden_capabilities: Optional[Iterable[str]] = None,
    risk_level: str = "low",
    requested_tiers: Optional[Iterable[str]] = None,
    user_requires_free_only: bool = True,
) -> Dict[str, Any]:
    class_name = task_class if task_class in TASK_CLASSES else "unknown"
    required = _build_capability_set(required_capabilities or [])
    required.update(CLASS_CAPABILITY_MAP.get(class_name, []))
    forbidden = _build_capability_set(forbidden_capabilities or [])
    requested_ids = _to_list(requested_tiers)
    matched_tiers: List[Dict[str, Any]] = []
    for tier in _ordered_tiers():
        if requested_ids and tier["tier_id"] not in requested_ids:
            continue
        if bool(user_requires_free_only) and tier["paid"] and not tier["emergency_only"]:
            continue
        if tier["emergency_only"] and risk_level != "high":
            continue
        tier_caps = set(tier["capability_matrix"])
        missing = sorted(required - tier_caps)
        matched = len(required - set(missing)) / max(1, len(required or ["default"]))
        score = min(100, int(round(matched * 100)))
        matched_tiers.append(
            {
                "tier_id": tier["tier_id"],
                "tier_number": tier["tier_number"],
                "match_percent": score,
                "missing_capabilities": missing,
                "supports_class": score >= 50,
            }
        )
    matched_tiers.sort(key=lambda item: (item["supports_class"] is False, -item["match_percent"], item["tier_number"]))
    return {
        "task_id": task_id,
        "task_class": class_name,
        "risk_level": risk_level or "low",
        "required_capabilities": sorted(required),
        "forbidden_capabilities": sorted(forbidden),
        "matched_tiers": matched_tiers,
        "policy_version": ROUTER_POLICY_VERSION,
        **_safe_flag_snapshot(),
    }


def evaluate_zero_cost_availability(
    task_id: str = "",
    engine_health_overrides: Optional[Dict[str, Any]] = None,
    user_requires_network: bool = False,
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    provided_policy = deepcopy(policy or {})
    requested_network = bool(user_requires_network)
    engine_health_overrides = engine_health_overrides or {}
    evals: List[Dict[str, Any]] = []
    for tier in _ordered_tiers():
        override = engine_health_overrides.get(tier["tier_id"], {})
        state = str(override.get("state", "available")).strip().lower()
        if state not in AVAILABILITY_STATES:
            state = "unknown"
        if tier["requires_network"] and not requested_network and state not in {"available", "degraded", "slow"}:
            state = "stalled"
        evals.append(
            {
                "engine_id": tier["tier_id"],
                "state": state,
                "retry_after_seconds": int(override.get("retry_after_seconds", 0)) if isinstance(override.get("retry_after_seconds", 0), int) else 0,
                "remaining_quota": int(override.get("remaining_quota", -1)) if isinstance(override.get("remaining_quota", -1), int) else None,
                "provider": "fixture",
            }
        )
    policy_snapshot = get_zero_cost_router_policy()
    policy_snapshot.update(provided_policy)
    policy_snapshot["local_first"] = True
    return {
        "task_id": task_id,
        "policy_version": ROUTER_POLICY_VERSION,
        "network_required": bool(requested_network),
        "total_tiers": len(TIER_LEVELS),
        "availability": evals,
        "policy": policy_snapshot,
        **_safe_flag_snapshot(),
    }


def _is_tier_usable(tier: Dict[str, Any], required_caps: Set[str], forbidden_caps: Set[str], availability: str, policy: Dict[str, Any]) -> tuple[bool, str]:
    if tier["emergency_only"] and not policy.get("emergency_approval", False):
        return False, "emergency_only"
    if tier["tier_id"] in set(policy.get("disabled_tiers", [])):
        return False, "tier_disabled"
    if tier["paid"] and not bool(policy.get("paid_escalation_allowed", False)):
        return False, "paid_not_allowed"
    if not tier["supports_structured_output"]:
        return False, "execution_not_supported"
    if tier["requires_network"] and availability in {"temporarily_unavailable", "authentication_failed", "disabled"}:
        return False, "network_not_allowed"
    if availability == "quota_exhausted":
        return False, "quota_exhausted"
    if availability == "authentication_failed":
        return False, "authentication_failed"
    if availability in {"resource_pressure", "stalled"}:
        return False, "resource_limit"
    if availability == "rate_limited":
        return False, "provider_unavailable"
    tier_caps = set(tier["capability_matrix"])
    if required_caps and not required_caps.issubset(tier_caps | set(["file_search"])):
        return False, "missing_capability"
    if forbidden_caps and forbidden_caps & tier_caps:
        return False, "privacy_conflict"
    return True, ""


def _select_paid_candidates(tiers: List[Dict[str, Any]], policy: Dict[str, Any], budget_blocked: bool = True) -> List[str]:
    paid_ids: List[str] = []
    for tier in tiers:
        if tier["paid"]:
            if tier["emergency_only"] and not budget_blocked:
                paid_ids.append(tier["tier_id"])
            elif not tier["emergency_only"]:
                paid_ids.append(tier["tier_id"])
    return paid_ids


def route_zero_cost_task(
    task_id: str = "",
    title: str = "",
    description: str = "",
    task_class: Optional[str] = None,
    required_capabilities: Optional[Iterable[str]] = None,
    forbidden_capabilities: Optional[Iterable[str]] = None,
    risk_level: str = "low",
    selected_files: Optional[Iterable[str]] = None,
    difficulty_score: int = 5,
    failure_history: Optional[Dict[str, int]] = None,
    availability: Optional[Dict[str, Any]] = None,
    policy: Optional[Dict[str, Any]] = None,
    resource_pressure: bool = False,
    user_requires_free_only: bool = True,
    previous_attempts: int = 0,
    user_rejection_count: int = 0,
    direct_user_constraints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result_class = task_class if task_class in TASK_CLASSES else _detect_task_class(title, description, required_capabilities or [], selected_files or [])
    difficulty = int(difficulty_score or 1)
    difficulty = max(1, min(10, difficulty))
    required = _build_capability_set(required_capabilities or [])
    if not required:
        required.update(CLASS_CAPABILITY_MAP.get(result_class, CLASS_CAPABILITY_MAP["unknown"]))
    forbidden = _build_capability_set(forbidden_capabilities or [])
    fallback_chain: List[str] = []
    skipped_engines: List[str] = []
    skip_reasons: List[str] = []
    paid_allowed = bool((policy or {}).get("paid_escalation_allowed", False))
    if not isinstance(policy, dict):
        policy = {}
    policy_snapshot = deepcopy(get_zero_cost_router_policy())
    policy_snapshot.update(policy or {})
    if not isinstance(policy_snapshot.get("network_allowed", False), bool):
        policy_snapshot["network_allowed"] = bool(availability or {}).get("network_required") if isinstance(availability, dict) else False
    if resource_pressure:
        policy_snapshot["resource_pressure"] = True
    availability_payload = availability or {}
    availability_items = _normalize_availability(availability_payload, policy_snapshot)
    free_tiers: List[str] = []
    paid_candidates: List[str] = []
    for tier in _ordered_tiers():
        state = availability_items.get(tier["tier_id"], "available")
        if tier["tier_id"] in {"deterministic_local_tools", "lightweight_local_coding_model", "free_cloud_open_coding_model", "gemini_ai_studio_free"}:
            usable, reason = _is_tier_usable(tier, required, forbidden, state, policy_snapshot)
            if usable and not (resource_pressure and tier["tier_id"] in {"deterministic_local_tools", "lightweight_local_coding_model"}):
                free_tiers.append(tier["tier_id"])
            elif state != "available":
                skipped_engines.append(tier["tier_id"])
                skip_reasons.append(f"{tier['tier_id']}:{reason or 'provider_unavailable'}")
            else:
                skipped_engines.append(tier["tier_id"])
                skip_reasons.append(f"{tier['tier_id']}:{reason}")
        else:
            paid_candidates.append(tier["tier_id"])
    paid_escalation_required = False
    paid_escalation_blocked = False
    selected_tier: Optional[str] = None
    selected_engine = None
    fast_path_used = False
    fast_path_reason = ""
    if result_class == "deterministic_lookup" and _is_tier_eligible_by_rules(result_class, difficulty, availability_items):
        fast_path_used = True
        fast_path_reason = "deterministic_fast_path"
    elif result_class == "small_code_fix" and "lightweight_local_coding_model" in free_tiers:
        selected_tier = "lightweight_local_coding_model"
        fast_path_used = True
        fast_path_reason = "small_code_fix_fast_path"
    elif result_class == "large_multifile_change" and "free_cloud_open_coding_model" in free_tiers:
        selected_tier = "free_cloud_open_coding_model"
        fast_path_used = True
        fast_path_reason = "multifile_fast_path"
    elif result_class == "visual_ui_analysis" and "gemini_ai_studio_free" in free_tiers:
        selected_tier = "gemini_ai_studio_free"
        fast_path_used = True
        fast_path_reason = "visual_fast_path"
    if not selected_tier:
        if result_class in {"terminal_execution", "browser_interaction", "deployment_execution", "critical_production_change", "security_sensitive_change"}:
            if "free_cloud_open_coding_model" in free_tiers and not resource_pressure:
                selected_tier = "free_cloud_open_coding_model"
                free_tiers = [t for t in free_tiers if t != selected_tier] + [selected_tier]
        if not selected_tier and free_tiers:
            selected_tier = free_tiers[0]
    if not selected_tier:
        paid_escalation_required = not paid_allowed or bool(policy_snapshot.get("paid_escalation_allowed") is False)
        paid_escalation_blocked = paid_escalation_required
    if selected_tier:
        for extra_tier in free_tiers:
            if extra_tier == selected_tier:
                continue
            fallback_chain.append(extra_tier)
        ordered_fallback = free_tiers[: policy_snapshot.get("max_fallback_depth", 4)]
        if selected_tier and selected_tier in ordered_fallback:
            ordered_fallback.remove(selected_tier)
        fallback_chain = [selected_tier] + ordered_fallback
        selected_tier_meta = _tier_lookup(selected_tier)
        selected_engine = selected_tier_meta["engine_class"]
        routing_state = "free_engine_selected"
    else:
        fallback_candidates = []
        paid_only = [tid for tid in paid_candidates if tid in paid_candidates]
        for paid_tier in paid_only[:3]:
            fallback_candidates.append(paid_tier)
        fallback_chain = fallback_candidates
        routing_state = "free_fallback_required" if paid_allowed else "paid_escalation_blocked"
        for paid_tier in fallback_candidates:
            skipped_engines.append(paid_tier)
            skip_reasons.append(f"{paid_tier}:paid_not_allowed")
    if direct_user_constraints and isinstance(direct_user_constraints, dict):
        selected_tier_override = str(direct_user_constraints.get("selected_tier", "") or "")
        if selected_tier_override:
            try:
                override_meta = _tier_lookup(selected_tier_override)
            except KeyError:
                skipped_engines.append(selected_tier_override)
                skip_reasons.append(f"{selected_tier_override}:unknown_tier")
            else:
                override_state = availability_items.get(selected_tier_override, "available")
                override_usable, reason = _is_tier_usable(
                    override_meta,
                    required,
                    forbidden,
                    override_state,
                    policy_snapshot,
                )
                if override_usable:
                    selected_tier = selected_tier_override
                    selected_engine = override_meta["engine_class"]
                    routing_state = "route_planned"
                    if selected_tier not in free_tiers:
                        paid_escalation_required = not paid_allowed
                        paid_escalation_blocked = paid_escalation_required
                    fallback_chain = [selected_tier]
                else:
                    skipped_engines.append(selected_tier_override)
                    skip_reasons.append(f"{selected_tier_override}:{reason}")
    recommended_paid = _select_paid_candidates(_ordered_tiers(), {"paid_escalation_allowed": paid_allowed}, budget_blocked=not paid_allowed)
    if not paid_allowed:
        paid_candidates = [item for item in recommended_paid if item in paid_candidates]
        paid_escalation_required = True
    decision = {
        "task_id": task_id,
        "task_class": result_class,
        "secondary_classes": [item for item in {_secondary_class(result_class), "unknown"} if item and item != result_class],
        "difficulty_score": difficulty,
        "required_capabilities": sorted(required),
        "required_engine_capabilities": sorted(required),
        "forbidden_capabilities": sorted(forbidden),
        "risk_level": risk_level or _risk_level(result_class, None),
        "selected_primary_engine": selected_engine,
        "selected_primary_tier": selected_tier,
        "fallback_chain": fallback_chain,
        "skipped_engines": sorted(set(skipped_engines)),
        "skip_reasons": sorted(set(skip_reasons)),
        "paid_escalation_required": paid_escalation_required,
        "paid_escalation_allowed": paid_allowed,
        "recommended_paid_engine": recommended_paid[0] if recommended_paid else None,
        "estimated_cost_class": (
            _tier_lookup(selected_tier)["cost_class"] if selected_tier else "paid_when_needed"
        ),
        "estimated_latency_class": _tier_lookup(selected_tier)["expected_latency_class"] if selected_tier else "high",
        "resource_impact_class": _tier_lookup(selected_tier)["resource_class"] if selected_tier else "high",
        "privacy_class": _tier_lookup(selected_tier)["privacy_class"] if selected_tier else "network_required",
        "decision_reasons": [
            f"policy={policy_snapshot['policy_version']}",
            f"free_tier_candidates={','.join(free_tiers) or 'none'}",
            f"routing_mode={'free' if selected_tier and not _tier_lookup(selected_tier).get('paid') else 'paid_candidate'}",
            f"routing_state={routing_state}",
        ],
        "policy_version": policy_snapshot["policy_version"],
        "fast_path_used": bool(fast_path_used),
        "fast_path_reason": fast_path_reason,
        "tiers_skipped": sorted(set([item for item in skipped_engines if item])),
        "engine_health_snapshot": availability_items,
        "routing_state": "routing_complete" if selected_tier else ("paid_escalation_blocked" if paid_escalation_required else "routing_failed"),
        "route_decision_digest": "",
        "decision_timestamp": "",
        "decision_source": "deterministic_local_planner",
        "title_digest": _digest(title),
        "description_digest": _digest(description),
        "policy_flags": {
            "user_requires_free_only": bool(user_requires_free_only),
            "resource_pressure": bool(resource_pressure),
            "network_allowed": bool(availability_payload.get("network_allowed", False)) if isinstance(availability_payload, dict) else False,
            "max_fallback_depth": int(policy_snapshot.get("max_fallback_depth", 4)),
            "prior_failure_bias": int(previous_attempts) + int(user_rejection_count),
        },
        "required_engine_plan": free_tiers[: max(0, int(policy_snapshot.get("max_fallback_depth", 4)))],
        "paid_engine_candidates": paid_candidates,
        "free_engine_candidates": free_tiers,
        "fallback_depth": len(fallback_chain),
        "decision_digest_meta": {
            "free_budget_available": bool(len(free_tiers)),
            "quota_retry_enabled": bool(policy_snapshot.get("quota_retry_enabled")),
            "hard_cost_cap": float(policy_snapshot.get("hard_cost_cap_usd", 0)),
        },
        "routing_state_reason": "emergency_only_blocked" if selected_tier and _tier_lookup(selected_tier).get("emergency_only") else "normal",
        "policy_version": ROUTER_POLICY_VERSION,
        **_safe_flag_snapshot(),
    }
    route_json = _clean_route_decision(decision)
    decision = deepcopy(route_json)
    decision["route_decision_digest"] = _digest(route_json)
    decision["decision_digest"] = decision["route_decision_digest"]
    decision["route_chain"] = decision["fallback_chain"][:]
    decision["decision_digest_meta"] = {
        "digest_source": "stable_json",
        "decision_keys": len(route_json),
    }
    return decision


def _normalize_availability(availability_payload: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, str]:
    snapshots = availability_payload.get("availability", {})
    values: Dict[str, str] = {}
    for tier in _ordered_tiers():
        value = "available"
        if isinstance(snapshots, dict):
            state = snapshots.get(tier["tier_id"], snapshots.get(tier["engine_class"], "available"))
            value = str(state).lower() if isinstance(state, str) else "available"
        if tier["requires_network"] and not bool(availability_payload.get("network_allowed", policy.get("network_allowed", False))):
            value = "network_not_allowed"
        values[tier["tier_id"]] = value
    return values


def _is_tier_eligible_by_rules(task_class: str, difficulty: int, availability: Dict[str, str]) -> bool:
    if task_class == "visual_ui_analysis":
        return availability.get("gemini_ai_studio_free") != "authentication_failed"
    if difficulty > 8:
        return availability.get("gemini_ai_studio_free") != "quota_exhausted"
    return True


def validate_zero_cost_route_decision(
    task_id: str,
    decision: Dict[str, Any],
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    policy = policy or {}
    if not isinstance(decision, dict):
        return {"ok": False, "task_id": task_id, "policy_version": ROUTER_POLICY_VERSION, "errors": ["decision must be dict"]}
    required_fields = {
        "task_id",
        "task_class",
        "required_capabilities",
        "difficulty_score",
        "selected_primary_tier",
        "selected_primary_engine",
        "fallback_chain",
        "paid_escalation_required",
        "paid_escalation_allowed",
        "skip_reasons",
        "route_decision_digest",
        "policy_version",
        "routing_state",
    }
    errors: List[str] = []
    missing = sorted(required_fields - decision.keys())
    if missing:
        errors.append(f"missing_fields={missing}")
    score = decision.get("difficulty_score")
    if not isinstance(score, int) or score < 1 or score > 10:
        errors.append("difficulty_score_not_1_to_10")
    if _safe_flag_snapshot().get("external_api_used") not in {False, None}:
        errors.append("external_api_used_in_decision")
    if decision.get("decision_digest") != _digest(_clean_route_decision(decision)):
        errors.append("decision_digest_not_stable")
    if decision.get("policy_version") != ROUTER_POLICY_VERSION:
        errors.append("policy_version_mismatch")
    if decision.get("routing_state") == "paid_escalation_blocked" and not decision.get("paid_escalation_required"):
        errors.append("routing_state_mismatch")
    if not _coerce_bool(decision.get("paid_escalation_allowed"), default=False) and decision.get("selected_primary_tier") in {"direct_deepseek_api", "whale_agent_execution", "codex_emergency_escalation"}:
        errors.append("paid_selected_when_disallowed")
    if decision.get("task_id") != task_id:
        errors.append("task_id_mismatch")
    if errors:
        return {
            "ok": False,
            "task_id": task_id,
            "errors": errors,
            "policy_version": ROUTER_POLICY_VERSION,
        }
    return {
        "ok": True,
        "task_id": task_id,
        "decision_digest": decision.get("decision_digest", ""),
        "routing_state": decision.get("routing_state"),
        "policy_version": ROUTER_POLICY_VERSION,
        "validation_reason_count": len(errors),
        "decision_reason_codes": decision.get("skip_reasons", []),
        **_safe_flag_snapshot(),
    }


def _clean_route_decision(decision: Dict[str, Any]) -> Dict[str, Any]:
    safe = deepcopy(decision)
    safe.pop("route_decision_digest", None)
    safe.pop("decision_timestamp", None)
    safe.pop("title_digest", None)
    safe.pop("description_digest", None)
    safe.pop("decision_digest_meta", None)
    safe.pop("engine_health_snapshot", None)
    return {
        key: safe[key]
        for key in sorted(safe.keys())
        if key not in {
            "external_api_used",
            "network_access_used",
            "shell_execution_used",
            "local_first",
            "route_chain",
            "decision_digest_meta",
            "decision_digest",
            "route_decision_digest",
        }
    }


def get_zero_cost_router_status() -> Dict[str, Any]:
    policy = get_zero_cost_router_policy()
    return {
        "status": "ready",
        "name": "LuxCode Zero-Cost Execution Router",
        "policy_version": ROUTER_POLICY_VERSION,
        "registry_loaded": len(TIER_LEVELS),
        "policy": policy,
        "supported_routes": len(TASK_CLASSES),
        "route_check_count": MAX_ROUTER_CHECKS,
        "safe_defaults": _safe_flag_snapshot(),
        "recently_available_tiers": [tier["tier_id"] for tier in TIER_LEVELS if tier["default_enabled"]],
        "policy_default": {
            "billing_allowed": policy["billing_allowed"],
            "automatic_upgrade": policy["automatic_upgrade"],
            "automatic_credit_purchase": policy["automatic_credit_purchase"],
            "hard_cost_cap_usd": policy["hard_cost_cap_usd"],
            "paid_escalation_allowed": policy["paid_escalation_allowed"],
        },
    }
