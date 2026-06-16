from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from luxcode_first_usable_registry import ENGINE_ORDER, engine_failure_fingerprint, select_engine_preview
from luxcode_first_usable_session_flow import build_request_envelope, build_result_envelope, build_session_state, digest, redact_secret


ENGINE_ID = "free_gemini"
PROVIDER_ID = "google_gemini"
DEFAULT_MODEL_ID = "gemini-3.5-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com"
GEMINI_API_VERSION = "v1beta"
GEMINI_METHOD_TEMPLATE = "models/{model}:generateContent"
MAX_RESPONSE_BYTES = 1_000_000
MAX_TIMEOUT_SECONDS = 10
SUPPORTED_QUOTA_STATES = {
    "available",
    "quota_low",
    "rate_limited",
    "quota_exhausted",
    "model_unavailable",
    "authentication_failed",
    "billing_status_unknown",
    "free_tier_unverified",
    "unknown",
}
SAFE_DEFAULTS = {
    "enabled": False,
    "verified": False,
    "transport_enabled": False,
    "real_requests_enabled": False,
    "free_tier_confirmed": False,
    "billing_allowed": False,
    "runtime_start_allowed": False,
    "model_download_allowed": False,
}


@dataclass(frozen=True)
class GeminiGatePolicy:
    enabled: bool = False
    verified: bool = False
    transport_enabled: bool = False
    real_requests_enabled: bool = False
    network_allowed: bool = False
    free_tier_confirmed: bool = False
    billing_disabled_confirmed: bool = False
    billing_allowed: bool = False
    quota_state: str = "unknown"
    quota_available: bool = False
    model_access_verified: bool = False
    auth_key_confirmed: bool = False
    key_type: str = "unknown"
    runtime_start_allowed: bool = False
    model_download_allowed: bool = False


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        raise HTTPError(req.full_url, code, "redirect blocked", headers, fp)


def official_gemini_endpoint(model_id: str = DEFAULT_MODEL_ID) -> Dict[str, str]:
    method = GEMINI_METHOD_TEMPLATE.format(model=model_id)
    return {
        "base_url": GEMINI_BASE_URL,
        "api_version": GEMINI_API_VERSION,
        "method": method,
        "url": f"{GEMINI_BASE_URL}/{GEMINI_API_VERSION}/{method}",
    }


def choose_gemini_key_reference(metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    data = metadata or {}
    google = bool(data.get("GOOGLE_API_KEY_present"))
    gemini = bool(data.get("GEMINI_API_KEY_present"))
    selected = "GOOGLE_API_KEY" if google else "GEMINI_API_KEY" if gemini else None
    key_type = str(data.get("key_type") or "unknown")
    blockers = []
    if not selected:
        blockers.append("auth_key_missing")
    if key_type in {"unknown", "unrestricted_standard"}:
        blockers.append("auth_key_type_not_safe")
    return {
        "selected_key_name": selected,
        "key_type": key_type,
        "auth_key_confirmed": bool(selected and not blockers),
        "blockers": blockers,
        "secret_value_persisted": False,
    }


def choose_gemini_api_key(environ: Dict[str, str] | None = None) -> Dict[str, Any]:
    data = environ or {}
    if data.get("GOOGLE_API_KEY"):
        return {"selected_key_name": "GOOGLE_API_KEY", "api_key": data.get("GOOGLE_API_KEY"), "api_key_present": True}
    if data.get("GEMINI_API_KEY"):
        return {"selected_key_name": "GEMINI_API_KEY", "api_key": data.get("GEMINI_API_KEY"), "api_key_present": True}
    return {"selected_key_name": None, "api_key": None, "api_key_present": False}


def evaluate_gemini_gates(policy: GeminiGatePolicy) -> Dict[str, Any]:
    quota_state = policy.quota_state if policy.quota_state in SUPPORTED_QUOTA_STATES else "unknown"
    blockers = []
    if not policy.enabled:
        blockers.append("engine_disabled")
    if not policy.verified:
        blockers.append("engine_unverified")
    if not policy.transport_enabled:
        blockers.append("transport_disabled")
    if not policy.real_requests_enabled:
        blockers.append("real_requests_disabled")
    if not policy.network_allowed:
        blockers.append("network_disabled")
    if not policy.free_tier_confirmed:
        blockers.append("free_tier_unverified")
    if policy.billing_allowed or not policy.billing_disabled_confirmed:
        blockers.append("billing_status_unknown")
    if not policy.auth_key_confirmed:
        blockers.append("auth_key_unconfirmed")
    if policy.key_type in {"unknown", "unrestricted_standard"}:
        blockers.append("auth_key_type_not_safe")
    if not policy.model_access_verified:
        blockers.append("model_access_unverified")
    if not policy.quota_available:
        blockers.append("quota_unavailable")
    if quota_state in {"rate_limited", "quota_exhausted", "model_unavailable", "authentication_failed", "billing_status_unknown", "free_tier_unverified", "unknown"}:
        blockers.append(f"quota_state_{quota_state}")
    if policy.runtime_start_allowed:
        blockers.append("runtime_start_forbidden")
    if policy.model_download_allowed:
        blockers.append("model_download_forbidden")
    return {
        "allowed": not blockers,
        "blockers": sorted(set(blockers)),
        "quota_state": quota_state,
        "free_tier_confirmed": policy.free_tier_confirmed,
        "billing_allowed": policy.billing_allowed,
        "auth_key_confirmed": policy.auth_key_confirmed,
        "model_access_verified": policy.model_access_verified,
        "real_http_call_permitted": False,
    }


def validate_gemini_endpoint(url: str) -> Dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return {"ok": False, "reason": "https_required", "url": redact_secret(url)}
    if parsed.hostname != "generativelanguage.googleapis.com":
        return {"ok": False, "reason": "non_official_host", "url": redact_secret(url)}
    expected_prefix = f"/{GEMINI_API_VERSION}/models/"
    if not parsed.path.startswith(expected_prefix) or not parsed.path.endswith(":generateContent"):
        return {"ok": False, "reason": "unsupported_method", "url": redact_secret(url)}
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return {"ok": False, "reason": "credential_or_query_forbidden", "url": redact_secret(url)}
    return {"ok": True, "reason": "official_endpoint", "url": url}


def _context_has_full_repository(minimum_context: Dict[str, str]) -> bool:
    if any(str(key).startswith("__FULL_REPOSITORY") or str(key).lower() in {"full_repository", "full_conversation"} for key in minimum_context):
        return True
    return sum(len(str(value)) for value in minimum_context.values()) > 12_000


def build_gemini_request_contract(
    *,
    task_id: str,
    session_id: str,
    task_summary: str,
    remaining_gap: Any,
    completed_scope: Sequence[str] | None,
    target_files: Sequence[str],
    target_symbols: Sequence[str],
    minimum_context: Dict[str, str],
    model_id: str = DEFAULT_MODEL_ID,
    seen_request_digests: set[str] | None = None,
) -> Dict[str, Any]:
    if not remaining_gap:
        return {"ok": False, "reason": "empty_remaining_gap", "request": None}
    if _context_has_full_repository(minimum_context):
        return {"ok": False, "reason": "full_repository_context_rejected", "request": None}
    request = build_request_envelope(
        task_id=task_id,
        session_id=session_id,
        engine_id=ENGINE_ID,
        tier=2,
        task_summary=task_summary,
        remaining_gap=remaining_gap,
        completed_scope=completed_scope,
        target_files=target_files,
        target_symbols=target_symbols,
        minimum_context=minimum_context,
        acceptance_criteria=["structured-json", "remaining-gap-only", "no-chain-of-thought"],
        required_output_schema="gemini_structured_result_v1",
        maximum_input_tokens=12000,
        maximum_output_tokens=4000,
        maximum_cost=0.0,
        timeout_seconds=60,
        seen_request_digests=seen_request_digests,
    )
    if request is None:
        return {"ok": False, "reason": "duplicate_or_empty_request", "request": None}
    request.update(
        {
            "provider_id": PROVIDER_ID,
            "model_id": model_id,
            "endpoint": official_gemini_endpoint(model_id),
            "streaming_enabled": False,
            "tools_enabled": False,
            "file_upload_enabled": False,
            "search_grounding_enabled": False,
            "code_execution_enabled": False,
            "raw_secret_included": False,
        }
    )
    request["request_digest"] = digest({key: value for key, value in request.items() if key not in {"request_id", "request_digest"}}, "gemini-request")
    request["request_id"] = request["request_digest"].replace("gemini-request-", "gemini-req-", 1)
    if seen_request_digests is not None:
        if request["request_digest"] in seen_request_digests:
            return {"ok": False, "reason": "duplicate_request_digest", "request": None}
        seen_request_digests.add(request["request_digest"])
    return {"ok": True, "reason": "request_ready", "request": request}


def parse_gemini_fixture_response(raw: str) -> Dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_json") from exc
    if not isinstance(data, dict):
        raise ValueError("invalid_shape")
    return redact_secret(data)


def validate_gemini_response(data: Dict[str, Any], *, request: Dict[str, Any]) -> Dict[str, Any]:
    issues = []
    status = str(data.get("status") or "")
    if status not in {"completed", "partial", "needs_more_context", "blocked", "invalid", "unsafe", "runtime_unavailable", "provider_error", "timeout", "fallback_required"}:
        issues.append("invalid_status")
    if "chain_of_thought" in data or "reasoning_trace" in data:
        issues.append("chain_of_thought_present")
    target_files = [str(item) for item in data.get("target_files", []) if str(item)]
    if not set(target_files).issubset(set(request.get("target_files", []))):
        issues.append("target_file_scope_violation")
    patch_operations = data.get("patch_operations", [])
    if not isinstance(patch_operations, list):
        issues.append("invalid_patch_operations")
    remaining_gap = str(data.get("remaining_gap") or "")
    if status == "completed" and remaining_gap:
        issues.append("completed_with_remaining_gap")
    if status == "partial" and not remaining_gap:
        issues.append("partial_without_remaining_gap")
    return {"valid": not issues, "status": "valid" if not issues else "invalid", "issues": issues}


def normalize_gemini_result_envelope(data: Dict[str, Any], *, request: Dict[str, Any]) -> Dict[str, Any]:
    validation = validate_gemini_response(data, request=request)
    status = str(data.get("status") or "invalid") if validation["valid"] else "invalid"
    result = build_result_envelope(
        request=request,
        status=status,
        analysis_summary=str(data.get("analysis_summary") or ""),
        completed_scope=data.get("completed_scope", []),
        remaining_gap=data.get("remaining_gap", ""),
        target_files=data.get("target_files", []),
        target_symbols=data.get("target_symbols", []),
        patch_operations=data.get("patch_operations", []),
        validation_recommendations=data.get("validation_recommendations", []),
        assumptions=data.get("assumptions", []),
        uncertainties=data.get("uncertainties", []),
        risk_flags=data.get("risk_flags", []),
        usage_metadata={"input_tokens": None, "output_tokens": None, "estimated_cost": None},
        failure_fingerprints=[] if validation["valid"] else [digest(validation, "gemini-validation-failure")],
    )
    result["provider_id"] = PROVIDER_ID
    result["model_id"] = request.get("model_id", DEFAULT_MODEL_ID)
    result["validation"] = validation
    result["result_digest"] = digest({key: value for key, value in result.items() if key not in {"result_id", "result_digest"}}, "gemini-result")
    result["result_id"] = result["result_digest"].replace("gemini-result-", "gemini-res-", 1)
    return result


def build_gemini_generate_content_payload(request: Dict[str, Any], *, maximum_output_tokens: int | None = None) -> Dict[str, Any]:
    max_tokens = int(maximum_output_tokens or min(int(request.get("maximum_output_tokens", 4000) or 4000), 4000))
    max_tokens = max(1, min(max_tokens, int(request.get("maximum_output_tokens", max_tokens) or max_tokens)))
    prompt_payload = {
        "remaining_gap": request.get("remaining_gap"),
        "minimum_context": request.get("minimum_context", {}),
        "target_files": request.get("target_files", []),
        "target_symbols": request.get("target_symbols", []),
        "acceptance_criteria": request.get("acceptance_criteria", []),
        "required_output_schema": request.get("required_output_schema"),
    }
    return {
        "contents": [{"role": "user", "parts": [{"text": json.dumps(prompt_payload, sort_keys=True, ensure_ascii=True)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0,
            "maxOutputTokens": max_tokens,
        },
        "safetySettings": [],
    }


def _request_without_redirects(url: str, payload: Dict[str, Any], api_key: str, *, timeout_seconds: int) -> Dict[str, Any]:
    endpoint = validate_gemini_endpoint(url)
    if not endpoint.get("ok"):
        return {"ok": False, "status": "blocked_endpoint", "retryable": False, "endpoint": endpoint}
    timeout = max(1, min(int(timeout_seconds or MAX_TIMEOUT_SECONDS), MAX_TIMEOUT_SECONDS))
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    opener = build_opener(_NoRedirect)
    try:
        started = time.perf_counter()
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            latency_ms = int((time.perf_counter() - started) * 1000)
            status_code = int(getattr(response, "status", 200))
            response_id = response.headers.get("x-request-id", "")
    except TimeoutError:
        return {"ok": False, "status": "timeout", "retryable": False, "latency_ms": timeout * 1000}
    except HTTPError as exc:
        return {"ok": False, "status": "http_error", "http_status": exc.code, "retryable": exc.code == 429 or 500 <= exc.code <= 599, "error": redact_secret(str(exc))}
    except URLError as exc:
        return {"ok": False, "status": "network_error", "retryable": False, "error": redact_secret(str(exc.reason))}
    if len(raw) > MAX_RESPONSE_BYTES:
        return {"ok": False, "status": "response_too_large", "retryable": False}
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "status": "invalid_json", "retryable": False, "error": str(exc)}
    return {"ok": True, "status": "success", "http_status": status_code, "response_id": response_id, "latency_ms": latency_ms, "response": data}


def _extract_candidate_json(response: Dict[str, Any]) -> Dict[str, Any]:
    candidates = response.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return {"ok": False, "status": "missing_candidate"}
    first = candidates[0]
    if not isinstance(first, dict):
        return {"ok": False, "status": "invalid_candidate"}
    finish_reason = str(first.get("finishReason") or first.get("finish_reason") or "")
    if finish_reason.upper() in {"SAFETY", "RECITATION", "BLOCKLIST"}:
        return {"ok": False, "status": "safety_blocked", "finish_reason": finish_reason}
    parts = first.get("content", {}).get("parts") if isinstance(first.get("content"), dict) else None
    if not isinstance(parts, list) or not parts:
        return {"ok": False, "status": "missing_content_parts", "finish_reason": finish_reason}
    text = ""
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            text += part["text"]
    if not text.strip():
        return {"ok": False, "status": "missing_candidate_text", "finish_reason": finish_reason}
    try:
        parsed = parse_gemini_fixture_response(text)
    except ValueError:
        return {"ok": False, "status": "invalid_candidate_json", "finish_reason": finish_reason}
    return {
        "ok": True,
        "candidate_text": text,
        "candidate_json": parsed,
        "finish_reason": finish_reason,
        "model_version": response.get("modelVersion") or response.get("model_version"),
        "usage_metadata": response.get("usageMetadata") or response.get("usage_metadata") or {},
    }


def execute_gemini_generate_content(
    *,
    request: Dict[str, Any],
    policy: GeminiGatePolicy,
    api_key: str | None,
    network_allowed: bool,
    http_call=None,
    timeout_seconds: int = MAX_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    effective_policy = GeminiGatePolicy(**{**asdict(policy), "network_allowed": bool(network_allowed)})
    gate = evaluate_gemini_gates(effective_policy)
    endpoint_url = request.get("endpoint", official_gemini_endpoint()).get("url") if isinstance(request.get("endpoint"), dict) else official_gemini_endpoint().get("url")
    endpoint = validate_gemini_endpoint(str(endpoint_url))
    if not endpoint.get("ok"):
        gate["blockers"] = sorted(set(gate.get("blockers", []) + [str(endpoint.get("reason"))]))
        gate["allowed"] = False
    if not api_key:
        gate["blockers"] = sorted(set(gate.get("blockers", []) + ["api_key_missing"]))
        gate["allowed"] = False
    if not gate.get("allowed"):
        return {"ok": False, "status": "blocked_by_policy", "gate": gate, "retry_state": "no_http_call"}
    payload = build_gemini_generate_content_payload(request)
    transport_call = http_call or _request_without_redirects
    first = transport_call(str(endpoint_url), payload, api_key, timeout_seconds=timeout_seconds)
    retry_state = "no_retry"
    result = first
    http_status = int(first.get("http_status", 0) or 0)
    if not first.get("ok") and first.get("retryable") and (http_status == 429 or 500 <= http_status <= 599):
        retry_state = "bounded_retry_once"
        result = transport_call(str(endpoint_url), payload, api_key, timeout_seconds=timeout_seconds)
    elif not first.get("ok") and http_status in {400, 401, 403}:
        retry_state = "no_retry_permanent_http_status"
    if not result.get("ok"):
        return {"ok": False, "status": result.get("status", "transport_failed"), "gate": gate, "transport": redact_secret(result), "retry_state": retry_state}
    extracted = _extract_candidate_json(result.get("response", {}))
    if not extracted.get("ok"):
        return {"ok": False, "status": extracted.get("status", "candidate_failed"), "gate": gate, "transport": redact_secret(result), "retry_state": retry_state, "candidate": redact_secret(extracted)}
    normalized = normalize_gemini_result_envelope(extracted["candidate_json"], request=request)
    return {
        "ok": bool(normalized.get("validation", {}).get("valid")),
        "status": "success" if normalized.get("validation", {}).get("valid") else "invalid_result",
        "response_id": result.get("response_id", ""),
        "model_version": extracted.get("model_version"),
        "candidate_text": extracted.get("candidate_text"),
        "finish_reason": extracted.get("finish_reason"),
        "usage_metadata": extracted.get("usage_metadata"),
        "retry_state": retry_state,
        "latency_ms": result.get("latency_ms"),
        "result": normalized,
        "gate": gate,
    }


def live_smoke_policy_from_env(environ: Dict[str, str] | None = None) -> tuple[GeminiGatePolicy, str | None, Dict[str, Any]]:
    data = environ if environ is not None else os.environ
    key = choose_gemini_api_key(data)
    policy = GeminiGatePolicy(
        enabled=data.get("LUXCODE_GEMINI_ENABLED") == "1",
        verified=data.get("LUXCODE_GEMINI_VERIFIED") == "1",
        transport_enabled=data.get("LUXCODE_GEMINI_TRANSPORT_ENABLED") == "1",
        real_requests_enabled=data.get("LUXCODE_GEMINI_REAL_REQUESTS_ENABLED") == "1",
        network_allowed=data.get("LUXCODE_GEMINI_NETWORK_ALLOWED") == "1",
        free_tier_confirmed=data.get("LUXCODE_GEMINI_FREE_TIER_CONFIRMED") == "1",
        billing_disabled_confirmed=data.get("LUXCODE_GEMINI_BILLING_DISABLED_CONFIRMED") == "1",
        billing_allowed=False,
        quota_state=data.get("LUXCODE_GEMINI_QUOTA_STATE", "unknown"),
        quota_available=data.get("LUXCODE_GEMINI_QUOTA_AVAILABLE") == "1",
        model_access_verified=data.get("LUXCODE_GEMINI_MODEL_ACCESS_VERIFIED") == "1",
        auth_key_confirmed=bool(key.get("api_key_present")) and data.get("LUXCODE_GEMINI_AUTH_KEY_CONFIRMED") == "1",
        key_type=data.get("LUXCODE_GEMINI_KEY_TYPE", "unknown"),
    )
    gates = {
        "enabled": policy.enabled,
        "verified": policy.verified,
        "transport_enabled": policy.transport_enabled,
        "real_requests_enabled": policy.real_requests_enabled,
        "network_allowed": policy.network_allowed,
        "free_tier_confirmed": policy.free_tier_confirmed,
        "billing_disabled_confirmed": policy.billing_disabled_confirmed,
        "quota_available": policy.quota_available,
        "quota_state_available": policy.quota_state == "available",
        "model_access_verified": policy.model_access_verified,
        "auth_key_confirmed": policy.auth_key_confirmed,
        "api_key_present": bool(key.get("api_key_present")),
    }
    return policy, key.get("api_key"), gates


def build_gemini_evidence(
    *,
    request: Dict[str, Any],
    gate: Dict[str, Any],
    result: Dict[str, Any] | None,
    stop_reason: str,
) -> Dict[str, Any]:
    payload = {
        "engine_id": ENGINE_ID,
        "provider_id": PROVIDER_ID,
        "model_id": request.get("model_id", DEFAULT_MODEL_ID),
        "free_tier_confirmed": gate.get("free_tier_confirmed", False),
        "billing_allowed": gate.get("billing_allowed", False),
        "quota_state": gate.get("quota_state", "unknown"),
        "model_access_verified": gate.get("model_access_verified", False),
        "auth_key_confirmed": gate.get("auth_key_confirmed", False),
        "request_id": request.get("request_id", ""),
        "validation_status": (result or {}).get("validation", {}).get("status", "not_started"),
        "completed": (result or {}).get("status") == "completed",
        "remaining_gap_digest": digest((result or {}).get("remaining_gap", request.get("remaining_gap")), "gemini-gap"),
        "blockers": list(gate.get("blockers", [])),
        "stop_reason": stop_reason,
        "estimated_cost": None,
        "latency_ms": None,
    }
    payload = redact_secret(payload)
    payload["event_digest"] = digest(payload, "gemini-event")
    return payload


def engine_order_compatible() -> bool:
    return ENGINE_ORDER.index("free_gemini") < ENGINE_ORDER.index("free_cloud_worker") < ENGINE_ORDER.index("direct_deepseek")


def build_gemini_restore_policy(restored_task: Dict[str, Any]) -> Dict[str, Any]:
    metadata = restored_task.get("free_gemini_metadata", {}) if isinstance(restored_task, dict) else {}
    return {
        "engine_id": ENGINE_ID,
        "provider_id": PROVIDER_ID,
        "http_auto_restart": False,
        "request_auto_resend": False,
        "requires_gate_revalidation": True,
        "requires_quota_revalidation": True,
        "requires_key_presence_revalidation": True,
        "duplicate_guard_required": True,
        "previous_request_digest": str(metadata.get("request_digest") or ""),
        "secrets_persisted": False,
    }


def execute_free_gemini_handoff(
    *,
    task_id: str,
    session_id: str,
    task_summary: str,
    previous_result: Dict[str, Any],
    completed_scope: Sequence[str],
    target_files: Sequence[str],
    target_symbols: Sequence[str],
    minimum_context: Dict[str, str],
    policy: GeminiGatePolicy,
    api_key: str | None = None,
    provider_health: str = "healthy",
    registry_overrides: Dict[str, Dict[str, Any]] | None = None,
    seen_request_digests: set[str] | None = None,
    failed_engine_fingerprints: Sequence[str] | None = None,
    http_call=None,
    persist: bool = False,
) -> Dict[str, Any]:
    if previous_result.get("completed") is True:
        session = build_session_state(
            session_id=session_id,
            task_id=task_id,
            current_stage="completed",
            completed_scope=completed_scope,
            remaining_gap=previous_result.get("remaining_gap", ""),
            final_status="completed",
            stop_reason="completed_by_lower_tier",
        )
        return {"ok": True, "completed": True, "selected_engine": None, "transport_called": False, "stop_reason": "completed_by_lower_tier", "session_state": session, "evidence": None, "next_candidate": None}

    remaining_gap = previous_result.get("remaining_gap") or previous_result.get("next_remaining_gap")
    selection = select_engine_preview(
        completed=False,
        completed_scope=completed_scope,
        remaining_gap=remaining_gap,
        failed_engine_fingerprints=failed_engine_fingerprints,
        provider_health={"free_gemini": provider_health},
        registry_overrides=registry_overrides or {"free_gemini": {"enabled": policy.enabled, "verified": policy.verified, "availability": "available"}},
    )
    if selection.get("selected_engine") != ENGINE_ID:
        blockers = [item.get("reason", "") for item in selection.get("rejected_candidates", []) if item.get("engine_id") == ENGINE_ID]
        next_candidate = "free_cloud_worker" if selection.get("selected_engine") == "free_cloud_worker" or any(reason.startswith("health_quota_exhausted") or reason.startswith("health_rate_limited") or reason.startswith("health_authentication_failed") or reason == "engine_disabled" or reason == "engine_unverified" for reason in blockers) else selection.get("selected_engine")
        request_stub = {"request_id": "", "remaining_gap": remaining_gap, "model_id": DEFAULT_MODEL_ID}
        gate = evaluate_gemini_gates(policy)
        evidence = build_gemini_evidence(request=request_stub, gate={**gate, "blockers": sorted(set(gate.get("blockers", []) + blockers))}, result=None, stop_reason="gemini_skipped")
        session = build_session_state(
            session_id=session_id,
            task_id=task_id,
            current_stage="handoff_required",
            selected_engine=next_candidate,
            selected_tier=3 if next_candidate == "free_cloud_worker" else selection.get("selected_tier"),
            completed_scope=completed_scope,
            remaining_gap=remaining_gap,
            target_files=target_files,
            target_symbols=target_symbols,
            stop_reason="gemini_skipped",
            final_status="partial",
            evidence_ids=[evidence["event_digest"]],
        )
        return {"ok": False, "completed": False, "selected_engine": selection.get("selected_engine"), "transport_called": False, "stop_reason": "gemini_skipped", "blockers": evidence["blockers"], "next_candidate": next_candidate, "session_state": session, "evidence": evidence}

    request_result = build_gemini_request_contract(
        task_id=task_id,
        session_id=session_id,
        task_summary=task_summary,
        remaining_gap=remaining_gap,
        completed_scope=completed_scope,
        target_files=target_files,
        target_symbols=target_symbols,
        minimum_context=minimum_context,
        seen_request_digests=seen_request_digests,
    )
    if not request_result.get("ok"):
        request_stub = {"request_id": "", "remaining_gap": remaining_gap, "model_id": DEFAULT_MODEL_ID}
        gate = evaluate_gemini_gates(policy)
        evidence = build_gemini_evidence(request=request_stub, gate={**gate, "blockers": sorted(set(gate.get("blockers", []) + [str(request_result.get("reason"))]))}, result=None, stop_reason="request_blocked")
        session = build_session_state(session_id=session_id, task_id=task_id, current_stage="blocked", completed_scope=completed_scope, remaining_gap=remaining_gap, target_files=target_files, target_symbols=target_symbols, stop_reason="request_blocked", final_status="blocked", evidence_ids=[evidence["event_digest"]])
        return {"ok": False, "completed": False, "transport_called": False, "stop_reason": "request_blocked", "blockers": evidence["blockers"], "session_state": session, "evidence": evidence}

    request = request_result["request"]
    transport = execute_gemini_generate_content(request=request, policy=policy, api_key=api_key, network_allowed=policy.network_allowed, http_call=http_call)
    transport_called = transport.get("retry_state") != "no_http_call"
    if not transport.get("ok"):
        gate = transport.get("gate") or evaluate_gemini_gates(policy)
        evidence = build_gemini_evidence(request=request, gate=gate, result=None, stop_reason=str(transport.get("status") or "transport_failed"))
        session = build_session_state(session_id=session_id, task_id=task_id, current_stage="handoff_required", selected_engine="free_cloud_worker", selected_tier=3, completed_scope=completed_scope, remaining_gap=remaining_gap, target_files=target_files, target_symbols=target_symbols, failed_attempt_fingerprints=[engine_failure_fingerprint(ENGINE_ID, transport)], request_id=request.get("request_id"), final_status="partial", stop_reason=str(transport.get("status") or "transport_failed"), evidence_ids=[evidence["event_digest"]])
        return {"ok": False, "completed": False, "selected_engine": ENGINE_ID, "transport_called": transport_called, "stop_reason": session["stop_reason"], "transport": redact_secret(transport), "next_candidate": "free_cloud_worker", "session_state": session, "evidence": evidence}

    result = transport["result"]
    completed = result.get("status") == "completed" and not result.get("remaining_gap")
    next_candidate = None if completed else "free_cloud_worker"
    stop_reason = "gemini_completed" if completed else "gemini_partial_handoff"
    gate = transport.get("gate") or evaluate_gemini_gates(policy)
    evidence = build_gemini_evidence(request=request, gate=gate, result=result, stop_reason=stop_reason)
    session = build_session_state(
        session_id=session_id,
        task_id=task_id,
        current_stage="completed" if completed else "handoff_required",
        selected_engine=ENGINE_ID,
        selected_tier=2,
        completed_scope=list(completed_scope) + list(result.get("completed_scope", [])),
        remaining_gap=result.get("remaining_gap", ""),
        target_files=target_files,
        target_symbols=target_symbols,
        request_id=request.get("request_id"),
        result_id=result.get("result_id"),
        final_status="completed" if completed else "partial",
        stop_reason=stop_reason,
        evidence_ids=[evidence["event_digest"]],
    )
    persistence = {"saved": False}
    if persist:
        from luxcode_task_persistence import save_task_state

        persistence = save_task_state(
            {
                "task_id": task_id,
                "current_state": session["current_stage"],
                "free_gemini_metadata": {
                    "selected_engine": ENGINE_ID,
                    "request_id": request.get("request_id"),
                    "request_digest": request.get("request_digest"),
                    "result_id": result.get("result_id"),
                    "result_digest": result.get("result_digest"),
                    "completed_scope": session["completed_scope"],
                    "remaining_gap": session["remaining_gap"],
                    "quota_state": gate.get("quota_state"),
                    "retry_state": transport.get("retry_state"),
                    "failure_fingerprints": session.get("failed_attempt_fingerprints", []),
                    "evidence_ids": session.get("evidence_ids", []),
                    "final_status": session.get("final_status"),
                    "stop_reason": session.get("stop_reason"),
                    "restore_policy": build_gemini_restore_policy({}),
                },
            },
            mode="memory_only",
            event_type="free_gemini_handoff",
        )
    return {"ok": completed, "completed": completed, "selected_engine": ENGINE_ID, "transport_called": transport_called, "stop_reason": stop_reason, "request": request, "result": result, "transport": redact_secret(transport), "next_candidate": next_candidate, "session_state": session, "evidence": evidence, "persistence": persistence}
