from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from luxcode_low_cost_worker import build_safe_patch_contract_from_response, safe_patch_preview
from luxcode_low_cost_worker_contracts import (
    WorkerRequest,
    WorkerResponse,
    build_worker_request,
    parse_worker_response,
    validate_worker_response,
)


PROVIDER_ID = "direct_deepseek"
DEFAULT_MODEL_ID = "deepseek-v4-flash"
PRICING_SNAPSHOT_VERSION = "2026-06-16"
OFFICIAL_ENDPOINT = "https://api.deepseek.com/chat/completions"
SECRET_MASK = "sk-********************************"
MAX_RESPONSE_BYTES = 1_000_000
MAX_DEFAULT_TIMEOUT_SECONDS = 10
MAX_LIVE_SMOKE_COST_USD = 0.001


@dataclass(frozen=True)
class DeepSeekTransportPolicy:
    transport_enabled: bool = False
    real_requests_allowed: bool = False
    billing_allowed: bool = False
    paid_escalation_allowed: bool = False
    automatic_purchase_allowed: bool = False
    automatic_upgrade_allowed: bool = False
    explicit_user_approval: bool = False


@dataclass(frozen=True)
class DeepSeekPricingSnapshot:
    model_id: str
    cache_hit_input_per_1m: float | None = None
    cache_miss_input_per_1m: float | None = None
    output_per_1m: float | None = None
    input_per_million: float | None = None
    output_per_million: float | None = None
    version: str = PRICING_SNAPSHOT_VERSION
    currency: str = "USD"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        raise HTTPError(req.full_url, code, "redirect blocked", headers, fp)


@dataclass(frozen=True)
class DeepSeekEvidence:
    evidence_id: str
    task_id: str
    provider_id: str
    model_id: str
    status: str
    summary: str
    response_digest: str
    patch_digest: str
    pricing_snapshot_version: str
    estimated_maximum_cost: float | None
    health_state: str
    retry_state: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    created_at: str


def _digest(value: Any, *, prefix: str) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:24]}"


def redact_secret(value: Any) -> Any:
    patterns = [
        re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)([^\s,;]+)"),
        re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._~+/-]{8,})"),
        re.compile(r"(?i)((?:api[_-]?key|token|secret|password|cookie)\s*[:=]\s*[\"']?)([^\"'\s,;]+)"),
        re.compile(r"(?i)([?&](?:api[_-]?key|token|secret|password)=)([^&#]+)"),
        re.compile(r"(?i)()(sk-[A-Za-z0-9._~+/-]{8,})"),
    ]
    if isinstance(value, str):
        result = value
        for pattern in patterns:
            result = pattern.sub(lambda match: match.group(1) + SECRET_MASK, result)
        return result
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if str(key).lower() in {"authorization", "cookie", "set-cookie", "x-api-key", "api_key"}:
                cleaned[key] = SECRET_MASK
            else:
                cleaned[key] = redact_secret(item)
        return cleaned
    if isinstance(value, list):
        return [redact_secret(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secret(item) for item in value)
    return value


def validate_deepseek_endpoint(url: str) -> Dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "api.deepseek.com":
        return {"ok": False, "reason": "non_official_endpoint", "endpoint": redact_secret(url)}
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return {"ok": False, "reason": "credential_or_query_forbidden", "endpoint": redact_secret(url)}
    if not url.rstrip("/").startswith("https://api.deepseek.com"):
        return {"ok": False, "reason": "profile_url_mismatch", "endpoint": redact_secret(url)}
    return {"ok": True, "reason": "official_endpoint", "endpoint": url.rstrip("/")}


def get_deepseek_pricing_snapshot(model_id: str = DEFAULT_MODEL_ID) -> DeepSeekPricingSnapshot:
    snapshots = {
        "deepseek-v4-flash": DeepSeekPricingSnapshot(
            model_id="deepseek-v4-flash",
            cache_hit_input_per_1m=0.0028,
            cache_miss_input_per_1m=0.14,
            output_per_1m=0.28,
        ),
        "deepseek-v4-pro": DeepSeekPricingSnapshot(
            model_id="deepseek-v4-pro",
            cache_hit_input_per_1m=0.003625,
            cache_miss_input_per_1m=0.435,
            output_per_1m=0.87,
        ),
    }
    if model_id not in snapshots:
        return DeepSeekPricingSnapshot(model_id=model_id)
    return snapshots[model_id]


def estimate_deepseek_cost(input_tokens: int, output_tokens: int, pricing: DeepSeekPricingSnapshot) -> float | None:
    if input_tokens < 0 or output_tokens < 0:
        return None
    input_rate = pricing.cache_miss_input_per_1m if pricing.cache_miss_input_per_1m is not None else pricing.input_per_million
    output_rate = pricing.output_per_1m if pricing.output_per_1m is not None else pricing.output_per_million
    if input_rate is None or output_rate is None:
        return None
    return (input_tokens / 1_000_000 * input_rate) + (output_tokens / 1_000_000 * output_rate)


def evaluate_deepseek_gates(
    *,
    endpoint_url: str,
    policy: DeepSeekTransportPolicy,
    pricing: DeepSeekPricingSnapshot,
    input_tokens: int,
    output_tokens: int,
    hard_cost_cap: float | None,
) -> Dict[str, Any]:
    endpoint = validate_deepseek_endpoint(endpoint_url)
    estimate = estimate_deepseek_cost(input_tokens, output_tokens, pricing)
    blockers = []
    if not endpoint.get("ok"):
        blockers.append(str(endpoint.get("reason")))
    if estimate is None:
        blockers.append("unknown_pricing")
    if hard_cost_cap is None:
        blockers.append("missing_cost_cap")
    elif estimate is not None and estimate > hard_cost_cap:
        blockers.append("hard_cost_cap_exceeded")
    if not policy.transport_enabled:
        blockers.append("transport_disabled")
    if not policy.real_requests_allowed:
        blockers.append("real_requests_disabled")
    if not policy.billing_allowed:
        blockers.append("billing_disabled")
    if policy.automatic_purchase_allowed or policy.automatic_upgrade_allowed or policy.paid_escalation_allowed:
        blockers.append("paid_escalation_policy_rejected")
    return {
        "allowed": not blockers,
        "blockers": sorted(set(blockers)),
        "endpoint": endpoint,
        "pricing_snapshot_version": pricing.version,
        "estimated_maximum_cost": estimate,
        "billing_allowed": policy.billing_allowed,
        "real_transport_enabled": policy.real_requests_allowed,
    }


def build_deepseek_chat_payload(
    *,
    prompt: str,
    model_id: str = DEFAULT_MODEL_ID,
    max_tokens: int = 16,
) -> Dict[str, Any]:
    if max_tokens <= 0 or max_tokens > 16:
        raise ValueError("max_tokens must be between 1 and 16 for controlled smoke")
    return {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
    }


def _request_without_redirects(url: str, payload: Dict[str, Any], api_key: str, *, timeout_seconds: int) -> Dict[str, Any]:
    timeout = max(1, min(int(timeout_seconds or MAX_DEFAULT_TIMEOUT_SECONDS), MAX_DEFAULT_TIMEOUT_SECONDS))
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    opener = build_opener(_NoRedirect)
    try:
        started = time.perf_counter()
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            latency_ms = int((time.perf_counter() - started) * 1000)
            status_code = int(getattr(response, "status", 200))
            request_id = response.headers.get("x-request-id", "")
    except TimeoutError:
        return {"ok": False, "status": "timeout", "retryable": False, "latency_ms": timeout * 1000}
    except HTTPError as exc:
        return {"ok": False, "status": "http_error", "http_status": exc.code, "retryable": exc.code == 429 or 500 <= exc.code <= 599, "error": redact_secret(str(exc))}
    except URLError as exc:
        return {"ok": False, "status": "network_error", "retryable": False, "error": redact_secret(str(exc.reason))}
    if len(raw) > MAX_RESPONSE_BYTES:
        return {"ok": False, "status": "response_too_large", "retryable": False}
    if not raw:
        return {"ok": False, "status": "empty_response", "retryable": False}
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "status": "invalid_json", "retryable": False, "error": str(exc)}
    return {"ok": True, "status": "success", "http_status": status_code, "response": data, "latency_ms": latency_ms, "provider_request_id": request_id}


def _extract_chat_content(response: Dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(first.get("text") or "")


def _usage_cost(response: Dict[str, Any], pricing: DeepSeekPricingSnapshot) -> Dict[str, Any]:
    usage = response.get("usage") if isinstance(response, dict) else {}
    if not isinstance(usage, dict):
        usage = {}
    input_tokens = int(usage.get("prompt_tokens", 0) or 0)
    output_tokens = int(usage.get("completion_tokens", 0) or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "actual_estimated_cost": estimate_deepseek_cost(input_tokens, output_tokens, pricing),
    }


def execute_deepseek_chat_completion(
    *,
    prompt: str,
    api_key: str | None,
    policy: DeepSeekTransportPolicy,
    endpoint_url: str = OFFICIAL_ENDPOINT,
    model_id: str = DEFAULT_MODEL_ID,
    max_tokens: int = 16,
    maximum_estimated_cost_usd: float = MAX_LIVE_SMOKE_COST_USD,
    timeout_seconds: int = MAX_DEFAULT_TIMEOUT_SECONDS,
    http_call: Callable[..., Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    pricing = get_deepseek_pricing_snapshot(model_id)
    estimated_input_tokens = max(1, len(prompt.split()) + 8)
    gates = evaluate_deepseek_gates(
        endpoint_url=endpoint_url,
        policy=policy,
        pricing=pricing,
        input_tokens=estimated_input_tokens,
        output_tokens=max_tokens,
        hard_cost_cap=maximum_estimated_cost_usd,
    )
    if not api_key:
        gates["blockers"] = sorted(set(list(gates.get("blockers", [])) + ["missing_api_key"]))
    if not gates.get("allowed") or not api_key:
        return {"ok": False, "status": "blocked_by_policy", "gate": gates, "retry_decision": "no_http_call"}
    payload = build_deepseek_chat_payload(prompt=prompt, model_id=model_id, max_tokens=max_tokens)
    transport_call = http_call or _request_without_redirects
    first = transport_call(endpoint_url, payload, api_key, timeout_seconds=timeout_seconds)
    retry_decision = "no_retry"
    result = first
    http_status = int(first.get("http_status", 0) or 0)
    retryable_http_status = http_status == 429 or 500 <= http_status <= 599
    if not first.get("ok") and first.get("retryable") and retryable_http_status:
        retry_decision = "bounded_retry_once"
        time.sleep(0.25)
        result = transport_call(endpoint_url, payload, api_key, timeout_seconds=timeout_seconds)
    elif not first.get("ok") and first.get("http_status") in {400, 401, 403}:
        retry_decision = "no_retry_permanent_http_status"
    if not result.get("ok"):
        return {"ok": False, "status": result.get("status", "transport_failed"), "gate": gates, "transport": redact_secret(result), "retry_decision": retry_decision}
    response = result.get("response", {})
    content = _extract_chat_content(response)
    if not content:
        return {"ok": False, "status": "missing_content", "gate": gates, "transport": redact_secret(result), "retry_decision": retry_decision}
    usage = _usage_cost(response, pricing)
    return {
        "ok": True,
        "status": "success",
        "content": content,
        "provider_request_id": result.get("provider_request_id", ""),
        "latency_ms": result.get("latency_ms", 0),
        "estimated_maximum_cost": gates.get("estimated_maximum_cost"),
        **usage,
        "model_id": model_id,
        "pricing_snapshot_version": pricing.version,
        "retry_decision": retry_decision,
    }


def live_smoke_policy_from_env() -> tuple[DeepSeekTransportPolicy, str | None, Dict[str, Any]]:
    enabled = os.environ.get("LUXCODE_DEEPSEEK_TRANSPORT_ENABLED") == "1"
    billing = os.environ.get("LUXCODE_DEEPSEEK_BILLING_ENABLED") == "1"
    real = os.environ.get("LUXCODE_DEEPSEEK_REAL_REQUESTS_ENABLED") == "1"
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    policy = DeepSeekTransportPolicy(
        transport_enabled=enabled,
        real_requests_allowed=real,
        billing_allowed=billing,
        explicit_user_approval=enabled and real and billing,
    )
    return policy, api_key, {"transport_enabled": enabled, "billing_enabled": billing, "real_requests_enabled": real, "api_key_present": bool(api_key)}


def build_deepseek_request_from_remaining_gap(
    *,
    request_id: str,
    task_id: str,
    task_summary: str,
    remaining_gap: str,
    target_files: Sequence[str],
    target_symbols: Sequence[str],
    minimum_context: Dict[str, str],
    failed_attempt_fingerprints: Sequence[str] | None = None,
    model_id: str = DEFAULT_MODEL_ID,
) -> WorkerRequest:
    return build_worker_request(
        request_id=request_id,
        task_id=task_id,
        provider_id=PROVIDER_ID,
        model_id=model_id,
        task_class="small_code_fix",
        task_summary=task_summary,
        remaining_gap=remaining_gap,
        target_files=list(target_files),
        target_symbols=list(target_symbols),
        minimum_context=minimum_context,
        completed_scope=["low_cost_worker_remaining_gap"],
        failed_attempt_fingerprints=list(failed_attempt_fingerprints or []),
        acceptance_criteria=["structured-json", "safe-patch-preview", "approval-required", "no-live-api-call"],
        required_output_format="structured_json_v1",
        risk_level="low",
        permission_mode="preview_only",
        maximum_input_tokens=12000,
        maximum_output_tokens=4000,
        maximum_cost=0.0,
        timeout_seconds=60,
    )


def parse_deepseek_fixture_response(raw: str, *, request: WorkerRequest) -> WorkerResponse:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_json") from exc
    if not isinstance(data, dict):
        raise ValueError("response must be object")
    data.setdefault("provider_id", request.provider_id)
    data.setdefault("model_id", request.model_id)
    data.setdefault("scope_violations", [])
    usage = data.setdefault("usage_metadata", {})
    usage.setdefault("estimated_cost", 0.0)
    return parse_worker_response(json.dumps(data, sort_keys=True, separators=(",", ":")))


def validate_deepseek_response(
    *,
    request: WorkerRequest,
    response: WorkerResponse,
    known_files: set[str],
    known_symbols: set[str],
    protected_files: set[str],
    file_contents: Dict[str, str],
    failed_patch_fingerprints: set[str] | None = None,
) -> Dict[str, Any]:
    result = validate_worker_response(
        request=request,
        response=response,
        known_files=known_files,
        known_symbols=known_symbols,
        protected_files=protected_files,
        file_contents=file_contents,
        failed_patch_fingerprints=failed_patch_fingerprints,
    )
    return {
        "valid": result.valid,
        "status": result.status.value,
        "issues": [asdict(issue) for issue in result.issues],
        "response_digest": result.response_digest,
    }


def build_deepseek_safe_patch_contract(
    *,
    request: WorkerRequest,
    response: WorkerResponse,
    repository_root: str,
    file_contents: Dict[str, str],
    protected_files: Sequence[str] | None = None,
) -> Dict[str, Any]:
    contract = build_safe_patch_contract_from_response(
        request=request,
        response=response,
        repository_root=repository_root,
        protected_files=protected_files or [],
        file_contents=file_contents,
    )
    contract["source"] = "direct_deepseek_fixture"
    contract["provider_id"] = request.provider_id
    contract["pricing_snapshot_version"] = PRICING_SNAPSHOT_VERSION
    return contract


def build_deepseek_evidence(
    *,
    request: WorkerRequest,
    response: WorkerResponse | None,
    patch_contract: Dict[str, Any] | None,
    gate_result: Dict[str, Any],
    status: str,
    summary: str,
    retry_state: str = "not_started",
    health_state: str = "fixture_only",
    latency_ms: int = 0,
) -> Dict[str, Any]:
    usage = response.usage_metadata if response else {}
    payload = {
        "task_id": request.task_id,
        "provider_id": request.provider_id,
        "model_id": request.model_id,
        "status": status,
        "summary": redact_secret(summary),
        "response_digest": response.response_digest if response else "",
        "patch_digest": (patch_contract or {}).get("patch_digest", ""),
        "pricing_snapshot_version": str(gate_result.get("pricing_snapshot_version") or PRICING_SNAPSHOT_VERSION),
        "estimated_maximum_cost": gate_result.get("estimated_maximum_cost"),
        "health_state": health_state,
        "retry_state": retry_state,
        "latency_ms": int(latency_ms),
        "input_tokens": int(usage.get("input_tokens", 0) or 0),
        "output_tokens": int(usage.get("output_tokens", 0) or 0),
    }
    return asdict(
        DeepSeekEvidence(
            evidence_id=_digest(payload, prefix="deepseek-evidence"),
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **payload,
        )
    )


def build_deepseek_remaining_gap(
    *,
    request: WorkerRequest,
    reason: str,
    evidence: Dict[str, Any],
    retry_state: str = "blocked",
) -> Dict[str, Any]:
    payload = {
        "remaining_gap": reason,
        "target_files": list(request.target_files),
        "target_symbols": list(request.target_symbols),
        "failed_attempt_fingerprints": list(request.failed_attempt_fingerprints),
        "evidence_id": evidence.get("evidence_id", ""),
        "retry_state": retry_state,
        "provider_id": request.provider_id,
        "model_id": request.model_id,
    }
    return {**payload, "digest": _digest(payload, prefix="deepseek-gap")}


def preview_deepseek_safe_patch(contract: Dict[str, Any]) -> Dict[str, Any]:
    return safe_patch_preview(contract)


DIRECT_DEEPSEEK_CHAIN_ORDER = [
    "tier0_deterministic",
    "tier1_local_worker",
    "free_cloud_tiers",
    "direct_deepseek",
    "whale",
    "codex",
]


def _handoff_request_id(task_id: str, remaining_gap: Any, model_id: str) -> str:
    return _digest({"task_id": task_id, "remaining_gap": remaining_gap, "model_id": model_id}, prefix="deepseek-req")


def _remaining_gap_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("remaining_gap") or value.get("reason") or json.dumps(value, sort_keys=True, default=str))
    return str(value or "")


def _direct_handoff_evidence(
    *,
    request: WorkerRequest,
    response: WorkerResponse | None,
    patch_contract: Dict[str, Any] | None,
    gate_result: Dict[str, Any],
    status: str,
    summary: str,
    previous_tier: str,
    remaining_gap_before: Any,
    remaining_gap_after: Any,
    validation_status: str,
    safe_patch_preview_status: str,
    completed: bool,
    stop_reason: str,
    retry_state: str,
    health_state: str,
    latency_ms: int = 0,
    actual_cost_if_available: float | None = None,
) -> Dict[str, Any]:
    evidence = build_deepseek_evidence(
        request=request,
        response=response,
        patch_contract=patch_contract,
        gate_result=gate_result,
        status=status,
        summary=summary,
        retry_state=retry_state,
        health_state=health_state,
        latency_ms=latency_ms,
    )
    evidence.update(
        redact_secret(
            {
                "tier_id": "direct_deepseek",
                "previous_tier": previous_tier,
                "handoff_reason": "structured_remaining_gap_escalation",
                "remaining_gap_before": remaining_gap_before,
                "remaining_gap_after": remaining_gap_after,
                "validation_status": validation_status,
                "safe_patch_preview_status": safe_patch_preview_status,
                "completed": bool(completed),
                "stop_reason": stop_reason,
                "estimated_cost": gate_result.get("estimated_maximum_cost"),
                "actual_cost_if_available": actual_cost_if_available,
            }
        )
    )
    return evidence


def build_deepseek_restore_policy(restored_task: Dict[str, Any]) -> Dict[str, Any]:
    metadata = restored_task.get("direct_deepseek_metadata", {}) if isinstance(restored_task, dict) else {}
    return {
        "provider_id": PROVIDER_ID,
        "restore_auto_execute": False,
        "paid_call_restarted": False,
        "requires_gate_revalidation": True,
        "required_gates": [
            "free_tier_exhaustion_confirmed",
            "paid_escalation_approved",
            "transport_enabled",
            "billing_enabled",
            "real_requests_enabled",
            "official_endpoint",
            "known_pricing_snapshot",
            "hard_budget",
            "health_state",
        ],
        "previous_evidence_id": str(metadata.get("evidence_id") or ""),
        "secrets_persisted": False,
    }


def execute_direct_deepseek_handoff(
    *,
    task_id: str,
    task_summary: str,
    previous_tier: str,
    previous_result: Dict[str, Any],
    repository_root: str,
    target_files: Sequence[str],
    target_symbols: Sequence[str],
    minimum_context: Dict[str, str],
    free_tier_exhaustion_confirmed: bool,
    paid_escalation_approved: bool,
    policy: DeepSeekTransportPolicy,
    endpoint_url: str = OFFICIAL_ENDPOINT,
    model_id: str = DEFAULT_MODEL_ID,
    hard_cost_cap: float = MAX_LIVE_SMOKE_COST_USD,
    health_state: str = "healthy",
    http_call: Callable[..., Dict[str, Any]] | None = None,
    persist: bool = False,
    persistence_mode: str = "memory_only",
) -> Dict[str, Any]:
    if previous_result.get("completed") is True:
        return {
            "ok": True,
            "completed": True,
            "state": "completed_by_lower_tier",
            "stop_reason": "completed_by_lower_tier",
            "direct_deepseek_called": False,
            "chain_order": DIRECT_DEEPSEEK_CHAIN_ORDER,
        }

    remaining_gap = previous_result.get("remaining_gap") or previous_result.get("next_remaining_gap")
    request = build_deepseek_request_from_remaining_gap(
        request_id=_handoff_request_id(task_id, remaining_gap, model_id),
        task_id=task_id,
        task_summary=task_summary,
        remaining_gap=_remaining_gap_text(remaining_gap),
        target_files=target_files,
        target_symbols=target_symbols,
        minimum_context=minimum_context,
        failed_attempt_fingerprints=previous_result.get("failed_attempt_fingerprints") or [],
        model_id=model_id,
    )
    pricing = get_deepseek_pricing_snapshot(model_id)
    gate_result = evaluate_deepseek_gates(
        endpoint_url=endpoint_url,
        policy=policy,
        pricing=pricing,
        input_tokens=max(1, len(task_summary.split()) + len(_remaining_gap_text(remaining_gap).split()) + 8),
        output_tokens=16,
        hard_cost_cap=hard_cost_cap,
    )
    blockers = set(gate_result.get("blockers", []))
    if not remaining_gap:
        blockers.add("missing_structured_remaining_gap")
    if free_tier_exhaustion_confirmed is not True:
        blockers.add("free_tiers_not_exhausted")
    if paid_escalation_approved is not True:
        blockers.add("paid_escalation_not_approved")
    if health_state not in {"healthy", "available"}:
        blockers.add("health_state_blocked")
    gate_result["blockers"] = sorted(blockers)
    gate_result["allowed"] = not blockers

    if blockers:
        evidence = _direct_handoff_evidence(
            request=request,
            response=None,
            patch_contract=None,
            gate_result=gate_result,
            status="blocked_by_policy",
            summary=f"Direct DeepSeek handoff blocked: {', '.join(sorted(blockers))}",
            previous_tier=previous_tier,
            remaining_gap_before=remaining_gap,
            remaining_gap_after=remaining_gap,
            validation_status="not_started",
            safe_patch_preview_status="not_started",
            completed=False,
            stop_reason="blocked_by_policy",
            retry_state="not_started",
            health_state=health_state,
        )
        return {
            "ok": False,
            "completed": False,
            "state": "direct_deepseek_blocked",
            "stop_reason": "blocked_by_policy",
            "blockers": sorted(blockers),
            "direct_deepseek_called": False,
            "gate": gate_result,
            "evidence": evidence,
            "remaining_gap": build_deepseek_remaining_gap(request=request, reason="direct_deepseek_blocked", evidence=evidence),
            "chain_order": DIRECT_DEEPSEEK_CHAIN_ORDER,
        }

    prompt = json.dumps(
        {
            "request_id": request.request_id,
            "task_summary": task_summary,
            "remaining_gap": remaining_gap,
            "target_files": list(target_files),
            "target_symbols": list(target_symbols),
            "minimum_context": minimum_context,
            "required_output_format": "structured_json_v1",
        },
        sort_keys=True,
    )
    transport = execute_deepseek_chat_completion(
        prompt=prompt,
        api_key="sk-live-placeholder" if http_call else None,
        policy=policy,
        endpoint_url=endpoint_url,
        model_id=model_id,
        max_tokens=16,
        maximum_estimated_cost_usd=hard_cost_cap,
        timeout_seconds=MAX_DEFAULT_TIMEOUT_SECONDS,
        http_call=http_call,
    )
    if not transport.get("ok"):
        evidence = _direct_handoff_evidence(
            request=request,
            response=None,
            patch_contract=None,
            gate_result=gate_result,
            status="transport_failed",
            summary=json.dumps(redact_secret(transport), sort_keys=True, default=str),
            previous_tier=previous_tier,
            remaining_gap_before=remaining_gap,
            remaining_gap_after=remaining_gap,
            validation_status="not_started",
            safe_patch_preview_status="not_started",
            completed=False,
            stop_reason="transport_failed",
            retry_state=str(transport.get("retry_decision") or "unknown"),
            health_state=health_state,
            latency_ms=int(transport.get("latency_ms", 0) or 0),
        )
        return {
            "ok": False,
            "completed": False,
            "state": "direct_deepseek_transport_failed",
            "stop_reason": "transport_failed",
            "direct_deepseek_called": True,
            "transport": redact_secret(transport),
            "evidence": evidence,
            "remaining_gap": build_deepseek_remaining_gap(request=request, reason="direct_deepseek_transport_failed", evidence=evidence),
            "chain_order": DIRECT_DEEPSEEK_CHAIN_ORDER,
        }

    try:
        response = parse_deepseek_fixture_response(str(transport.get("content") or ""), request=request)
    except ValueError:
        response = None
    validation = (
        validate_deepseek_response(
            request=request,
            response=response,
            known_files=set(target_files),
            known_symbols=set(target_symbols),
            protected_files=set(),
            file_contents=minimum_context,
        )
        if response
        else {"valid": False, "status": "invalid_json", "issues": [{"code": "invalid_json"}]}
    )
    if not validation.get("valid"):
        evidence = _direct_handoff_evidence(
            request=request,
            response=response,
            patch_contract=None,
            gate_result=gate_result,
            status="validation_failed",
            summary="Direct DeepSeek response failed validation",
            previous_tier=previous_tier,
            remaining_gap_before=remaining_gap,
            remaining_gap_after="direct_deepseek_validation_failed",
            validation_status=str(validation.get("status") or "invalid"),
            safe_patch_preview_status="not_started",
            completed=False,
            stop_reason="validation_failed",
            retry_state=str(transport.get("retry_decision") or "no_retry"),
            health_state=health_state,
            latency_ms=int(transport.get("latency_ms", 0) or 0),
            actual_cost_if_available=transport.get("actual_estimated_cost"),
        )
        return {
            "ok": False,
            "completed": False,
            "state": "direct_deepseek_validation_failed",
            "stop_reason": "validation_failed",
            "direct_deepseek_called": True,
            "validation": validation,
            "evidence": evidence,
            "remaining_gap": build_deepseek_remaining_gap(request=request, reason="direct_deepseek_validation_failed", evidence=evidence),
            "chain_order": DIRECT_DEEPSEEK_CHAIN_ORDER,
        }

    contract = build_deepseek_safe_patch_contract(
        request=request,
        response=response,
        repository_root=repository_root,
        file_contents=minimum_context,
    )
    preview = preview_deepseek_safe_patch(contract)
    completed = bool(preview.get("valid") and preview.get("operation_count", 0) >= 1 and preview.get("approval_required") is True)
    stop_reason = "safe_patch_preview_ready" if completed else "safe_patch_preview_incomplete"
    evidence = _direct_handoff_evidence(
        request=request,
        response=response,
        patch_contract=contract,
        gate_result=gate_result,
        status=stop_reason,
        summary="Direct DeepSeek produced validated Safe Patch preview",
        previous_tier=previous_tier,
        remaining_gap_before=remaining_gap,
        remaining_gap_after="" if completed else response.remaining_gap,
        validation_status=str(validation.get("status") or "valid"),
        safe_patch_preview_status=str(preview.get("status") or "preview_ready"),
        completed=completed,
        stop_reason=stop_reason,
        retry_state=str(transport.get("retry_decision") or "no_retry"),
        health_state=health_state,
        latency_ms=int(transport.get("latency_ms", 0) or 0),
        actual_cost_if_available=transport.get("actual_estimated_cost"),
    )
    persistence = {"saved": False, "reason": "disabled"}
    if persist:
        from luxcode_task_persistence import save_task_state

        persistence = save_task_state(
            {
                "task_id": task_id,
                "current_state": "direct_deepseek_safe_patch_preview_ready" if completed else "direct_deepseek_remaining_gap",
                "repository_root": repository_root,
                "original_request": task_summary,
                "selected_files": list(target_files),
                "direct_deepseek_metadata": {
                    "provider_id": PROVIDER_ID,
                    "model_id": model_id,
                    "request_id": request.request_id,
                    "pricing_snapshot_version": PRICING_SNAPSHOT_VERSION,
                    "estimated_maximum_cost": gate_result.get("estimated_maximum_cost"),
                    "actual_cost_if_available": transport.get("actual_estimated_cost"),
                    "evidence_id": evidence.get("evidence_id", ""),
                    "retry_state": transport.get("retry_decision", "no_retry"),
                    "health_state": health_state,
                    "restore_auto_execute": False,
                    "requires_gate_revalidation": True,
                },
            },
            mode=persistence_mode,
            event_type="direct_deepseek_preview",
        )
    return {
        "ok": completed,
        "completed": completed,
        "state": stop_reason,
        "stop_reason": stop_reason,
        "direct_deepseek_called": True,
        "request": {"request_id": request.request_id, "request_digest": request.request_digest},
        "validation": validation,
        "safe_patch_contract": contract,
        "safe_patch_preview": preview,
        "evidence": evidence,
        "remaining_gap": None if completed else build_deepseek_remaining_gap(request=request, reason=response.remaining_gap, evidence=evidence),
        "persistence": persistence,
        "chain_order": DIRECT_DEEPSEEK_CHAIN_ORDER,
    }
