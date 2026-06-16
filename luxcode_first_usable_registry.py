from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from typing import Any, Dict, Iterable, List, Sequence

from luxcode_direct_deepseek_transport import DEFAULT_MODEL_ID, OFFICIAL_ENDPOINT, evaluate_deepseek_gates, get_deepseek_pricing_snapshot


CONFIG_VERSION = "luxcode_first_usable_v0_1_safe_config"
ENGINE_ORDER = [
    "tier0_deterministic",
    "tier1_local_worker",
    "free_gemini",
    "free_32b",
    "direct_deepseek",
    "whale",
    "codex",
]
ALL_ENGINE_IDS = ENGINE_ORDER + ["disabled", "unknown"]


@dataclass(frozen=True)
class UnifiedEngine:
    engine_id: str
    tier: int | None
    engine_type: str
    enabled: bool
    verified: bool
    availability: str
    cost_class: str
    local_only: bool
    external_provider: bool
    agent_execution: bool
    requires_api_key: bool
    requires_runtime: bool
    requires_user_approval: bool
    manual_only: bool
    emergency_only: bool
    supports_structured_patch: bool
    supports_validation: bool


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any, prefix: str = "first-usable") -> str:
    return f"{prefix}-{sha256(_stable_json(value).encode('utf-8')).hexdigest()[:24]}"


def _base_registry() -> Dict[str, UnifiedEngine]:
    return {
        "tier0_deterministic": UnifiedEngine("tier0_deterministic", 0, "deterministic_local_tools", True, True, "available", "zero", True, False, False, False, False, False, False, False, True, True),
        "tier1_local_worker": UnifiedEngine("tier1_local_worker", 1, "local_light_model", True, True, "available", "zero", True, False, False, False, True, False, False, False, True, True),
        "free_gemini": UnifiedEngine("free_gemini", 2, "future_free_cloud_placeholder", False, False, "disabled", "free", False, True, False, True, False, False, False, False, True, True),
        "free_32b": UnifiedEngine("free_32b", 3, "future_free_cloud_placeholder", False, False, "disabled", "free", False, True, False, True, False, False, False, False, True, True),
        "direct_deepseek": UnifiedEngine("direct_deepseek", 4, "paid_direct_transport", False, True, "disabled", "paid", False, True, False, True, False, True, False, False, True, True),
        "whale": UnifiedEngine("whale", 5, "manual_agent_execution", False, False, "manual_only", "manual", False, True, True, False, True, True, True, False, True, True),
        "codex": UnifiedEngine("codex", 6, "emergency_agent_execution", False, False, "emergency_only", "manual", False, True, True, False, True, True, True, True, True, True),
        "disabled": UnifiedEngine("disabled", None, "disabled", False, False, "disabled", "none", True, False, False, False, False, False, True, False, False, False),
        "unknown": UnifiedEngine("unknown", None, "unknown", False, False, "unknown", "unknown", False, False, False, False, False, True, True, False, False, False),
    }


def get_unified_engine_registry(overrides: Dict[str, Dict[str, Any]] | None = None) -> Dict[str, Dict[str, Any]]:
    registry = _base_registry()
    for engine_id, patch in (overrides or {}).items():
        if engine_id in registry and isinstance(patch, dict):
            allowed = {field for field in UnifiedEngine.__dataclass_fields__}
            registry[engine_id] = replace(registry[engine_id], **{key: value for key, value in patch.items() if key in allowed})
    return {engine_id: asdict(registry[engine_id]) for engine_id in ALL_ENGINE_IDS}


def build_safe_config(overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    config = {
        "config_version": CONFIG_VERSION,
        "engine_order": list(ENGINE_ORDER),
        "maximum_context_tokens": 12000,
        "maximum_output_tokens": 4000,
        "maximum_cost_per_request": 0.0,
        "network_allowed": False,
        "billing_allowed": False,
        "paid_escalation_allowed": False,
        "approval_required": True,
        "auto_apply_allowed": False,
        "runtime_start_allowed": False,
        "model_download_allowed": False,
    }
    if isinstance(overrides, dict):
        for key in config:
            if key in overrides:
                config[key] = overrides[key]
    if not isinstance(config.get("engine_order"), list) or not set(config["engine_order"]).issubset(set(ENGINE_ORDER)):
        config["engine_order"] = []
    for key in ("network_allowed", "billing_allowed", "paid_escalation_allowed", "approval_required", "auto_apply_allowed", "runtime_start_allowed", "model_download_allowed"):
        config[key] = bool(config.get(key)) if isinstance(config.get(key), bool) else (True if key == "approval_required" else False)
    for key in ("maximum_context_tokens", "maximum_output_tokens"):
        try:
            config[key] = max(0, int(config.get(key) or 0))
        except (TypeError, ValueError):
            config[key] = 0
    try:
        config["maximum_cost_per_request"] = max(0.0, float(config.get("maximum_cost_per_request") or 0.0))
    except (TypeError, ValueError):
        config["maximum_cost_per_request"] = 0.0
    config["config_digest"] = _digest({key: value for key, value in config.items() if key != "config_digest"}, prefix="first-usable-config")
    return config


def engine_failure_fingerprint(engine_id: str, remaining_gap: Any) -> str:
    return _digest({"engine_id": engine_id, "remaining_gap": remaining_gap}, prefix="engine-failure")


def _health_state(engine_id: str, runtime_health: Dict[str, Any], provider_health: Dict[str, Any]) -> str:
    state = runtime_health.get(engine_id, provider_health.get(engine_id, "available"))
    if isinstance(state, dict):
        state = state.get("state") or state.get("availability") or state.get("status") or "unknown"
    return str(state or "unknown").lower()


def _reject(rejected: List[Dict[str, Any]], engine_id: str, reason: str) -> None:
    rejected.append({"engine_id": engine_id, "reason": reason})


def _ok_health(state: str) -> bool:
    return state in {"available", "healthy", "ok", "ready"}


def select_engine_preview(
    *,
    completed: bool,
    completed_scope: Sequence[str] | None = None,
    remaining_gap: Any = None,
    task_class: str = "small_code_fix",
    risk_level: str = "low",
    required_capabilities: Sequence[str] | None = None,
    failed_engine_fingerprints: Sequence[str] | None = None,
    runtime_health: Dict[str, Any] | None = None,
    provider_health: Dict[str, Any] | None = None,
    free_tier_exhaustion_confirmed: bool = False,
    paid_escalation_approved: bool = False,
    cost_budget: float | None = None,
    manual_request: bool = False,
    emergency_request: bool = False,
    registry_overrides: Dict[str, Dict[str, Any]] | None = None,
    config_overrides: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    registry = get_unified_engine_registry(registry_overrides)
    config = build_safe_config(config_overrides)
    rejected: List[Dict[str, Any]] = []
    risk_flags: List[str] = []
    runtime_health = runtime_health or {}
    provider_health = provider_health or {}
    failed = set(failed_engine_fingerprints or [])
    scope = set(completed_scope or [])
    context = {
        "remaining_gap": remaining_gap,
        "task_class": task_class,
        "risk_level": risk_level,
        "required_capabilities": list(required_capabilities or []),
    }

    if completed:
        decision = {
            "selected_engine": None,
            "selected_tier": None,
            "reason": "completed_no_engine_selected",
            "rejected_candidates": [],
            "fallback_chain": [],
            "required_approval": False,
            "risk_flags": [],
            "decision_context": context,
        }
        return {**decision, "decision_digest": _digest(decision, prefix="engine-decision")}

    selected_engine = None
    selected_tier = None
    reason = "no_eligible_engine"
    fallback_chain: List[str] = []

    for engine_id in config["engine_order"]:
        engine = registry.get(engine_id, registry["unknown"])
        state = _health_state(engine_id, runtime_health, provider_health)
        failure_key = engine_failure_fingerprint(engine_id, remaining_gap)
        fallback_chain.append(engine_id)
        if failure_key in failed:
            _reject(rejected, engine_id, "repeated_failure_fingerprint")
            continue
        if state in {"cooldown", "degraded", "blocked", "unavailable", "disabled", "stalled", "not_installed", "not_running", "rate_limited", "quota_exhausted", "authentication_failed", "unknown"}:
            _reject(rejected, engine_id, f"health_{state}")
            continue
        if engine_id == "whale" and not manual_request:
            _reject(rejected, engine_id, "manual_request_required")
            continue
        if engine_id == "codex" and not (manual_request and emergency_request):
            _reject(rejected, engine_id, "emergency_manual_request_required")
            continue
        if not engine["enabled"]:
            _reject(rejected, engine_id, "engine_disabled")
            if engine_id in {"free_gemini", "free_32b"}:
                risk_flags.append(f"{engine_id}_placeholder_disabled")
            continue
        if not engine["verified"]:
            _reject(rejected, engine_id, "engine_unverified")
            continue
        if engine_id == "tier0_deterministic" and "tier0_deterministic" not in scope:
            selected_engine, selected_tier, reason = engine_id, engine["tier"], "tier0_first_eligible"
            break
        if engine_id == "tier0_deterministic":
            _reject(rejected, engine_id, "completed_scope_excluded")
            continue
        if engine_id == "tier1_local_worker":
            if "tier1_local_worker" in scope:
                _reject(rejected, engine_id, "completed_scope_excluded")
                continue
            if not _ok_health(state):
                _reject(rejected, engine_id, f"health_{state}")
                continue
            selected_engine, selected_tier, reason = engine_id, engine["tier"], "tier1_runtime_healthy"
            break
        if engine_id in {"free_gemini", "free_32b"}:
            if engine_id == "free_gemini":
                selected_engine, selected_tier, reason = engine_id, engine["tier"], "verified_free_gemini_before_32b"
                break
            selected_engine, selected_tier, reason = engine_id, engine["tier"], "verified_free_32b_before_paid"
            break
        if engine_id == "direct_deepseek":
            if not free_tier_exhaustion_confirmed:
                _reject(rejected, engine_id, "free_tiers_not_exhausted")
                continue
            if not paid_escalation_approved:
                _reject(rejected, engine_id, "paid_escalation_not_approved")
                continue
            if not (config["network_allowed"] and config["billing_allowed"] and config["paid_escalation_allowed"]):
                _reject(rejected, engine_id, "paid_network_or_billing_gate_closed")
                continue
            from luxcode_direct_deepseek_transport import DeepSeekTransportPolicy

            gate = evaluate_deepseek_gates(
                endpoint_url=OFFICIAL_ENDPOINT,
                policy=DeepSeekTransportPolicy(transport_enabled=True, real_requests_allowed=True, billing_allowed=True, explicit_user_approval=True),
                pricing=get_deepseek_pricing_snapshot(DEFAULT_MODEL_ID),
                input_tokens=64,
                output_tokens=16,
                hard_cost_cap=cost_budget if cost_budget is not None else config["maximum_cost_per_request"],
            )
            if not gate.get("allowed"):
                _reject(rejected, engine_id, "direct_deepseek_gate_blocked:" + ",".join(gate.get("blockers", [])))
                continue
            selected_engine, selected_tier, reason = engine_id, engine["tier"], "direct_deepseek_paid_gates_open"
            break
        if engine_id == "whale":
            selected_engine, selected_tier, reason = engine_id, engine["tier"], "manual_whale_candidate"
            break
        if engine_id == "codex":
            selected_engine, selected_tier, reason = engine_id, engine["tier"], "emergency_codex_candidate"
            break

    decision = {
        "selected_engine": selected_engine,
        "selected_tier": selected_tier,
        "reason": reason,
        "rejected_candidates": rejected,
        "fallback_chain": fallback_chain,
        "required_approval": bool(selected_engine and registry[selected_engine]["requires_user_approval"]),
        "risk_flags": sorted(set(risk_flags)),
        "decision_context": context,
    }
    return {**decision, "decision_digest": _digest(decision, prefix="engine-decision")}
