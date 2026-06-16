from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Callable, Dict, List, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from luxcode_first_usable_registry import engine_failure_fingerprint, select_engine_preview


CANONICAL_ENGINE_ID = "free_cloud_worker"
LEGACY_ALIAS = "free_32b"
OPENROUTER_PROVIDER_ID = "openrouter"
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
MAXIMUM_MODEL_ATTEMPTS = 2
MAXIMUM_TRANSPORT_ATTEMPTS = 2
MAX_REQUEST_BYTES = 24_000
MAX_RESPONSE_BYTES = 200_000
MAX_PROMPT_CHARS = 12_000
MAX_COMPLETION_TOKENS = 512
MAX_TRANSPORT_TIMEOUT_SECONDS = 12

PRIMARY_MODEL_ID = "nex-agi/nex-n2-pro:free"
DEEP_REASONING_FALLBACK_MODEL_ID = "nvidia/nemotron-3-ultra-550b-a55b:free"
SCHEMA_SAFE_FALLBACK_MODEL_ID = "qwen/qwen3-next-80b-a3b-instruct:free"

VALID_RESULT_STATUSES = {
    "completed",
    "partial",
    "blocked",
    "invalid",
    "unsafe",
    "provider_unavailable",
    "quota_exhausted",
    "schema_invalid",
    "empty_response",
    "fallback_required",
}
TERMINAL_FAILURES = {"quota_exhausted", "unsafe", "duplicate_failure", "invalid"}
SCHEMA_SAFE_REASONS = {"provider_unavailable", "rate_limited", "provider_error", "schema_invalid", "empty_response"}
TRANSIENT_DEFER_REASONS = {"rate_limited", "provider_unavailable", "timeout"}
COOLDOWN_SECONDS_BY_REASON = {
    "rate_limited": 240,
    "provider_unavailable": 180,
    "timeout": 120,
}
MAX_DEFERRED_COOLDOWN_SECONDS = 720
SECRET_MASK = "[redacted]"
MAX_CONTEXT_CHARS = 12000
ALLOWED_MODEL_IDS = {PRIMARY_MODEL_ID, DEEP_REASONING_FALLBACK_MODEL_ID, SCHEMA_SAFE_FALLBACK_MODEL_ID}
RETRYABLE_HTTP_STATUSES = {408, 429, 502, 503}
NON_RETRYABLE_HTTP_STATUSES = {400, 401, 402, 403, 404}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        raise HTTPError(req.full_url, code, "redirect blocked", headers, fp)


@dataclass(frozen=True)
class FreeCloudPolicy:
    enabled: bool = False
    verified: bool = False
    transport_enabled: bool = False
    real_requests_enabled: bool = False
    network_allowed: bool = False
    free_tier_confirmed: bool = False
    billing_allowed: bool = False
    paid_fallback_allowed: bool = False
    maximum_model_attempts: int = MAXIMUM_MODEL_ATTEMPTS


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def digest(value: Any, prefix: str) -> str:
    return f"{prefix}-{sha256(stable_json(value).encode('utf-8')).hexdigest()[:24]}"


def redact_secret(value: Any) -> Any:
    patterns = [
        re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)([^\s,;]+)"),
        re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._~+/-]{8,})"),
        re.compile(r"(?i)((?:api[_-]?key|token|secret|password|cookie)\s*[:=]\s*[\"']?)([^\"'\s,;]+)"),
        re.compile(r"(?i)([?&](?:api[_-]?key|token|secret|password)=)([^&#]+)"),
        re.compile(r"(?i)()(sk-or-[A-Za-z0-9._~+/-]{8,})"),
        re.compile(r"(?i)()(sk-[A-Za-z0-9._~+/-]{8,})"),
    ]
    if isinstance(value, str):
        result = value
        for pattern in patterns:
            result = pattern.sub(lambda match: match.group(1) + SECRET_MASK, result)
        return result
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in ("secret", "token", "api_key", "authorization", "cookie", "password")):
                cleaned[str(key)] = SECRET_MASK
            else:
                cleaned[str(key)] = redact_secret(item)
        return cleaned
    if isinstance(value, list):
        return [redact_secret(item) for item in value[:200]]
    return value


def get_free_cloud_model_registry() -> Dict[str, Dict[str, Any]]:
    return {
        "primary": {
            "model_id": PRIMARY_MODEL_ID,
            "provider_id": OPENROUTER_PROVIDER_ID,
            "role": "primary",
            "selection_order": 1,
            "free_tier_required": True,
        },
        "deep_reasoning_fallback": {
            "model_id": DEEP_REASONING_FALLBACK_MODEL_ID,
            "provider_id": OPENROUTER_PROVIDER_ID,
            "role": "deep_reasoning_fallback",
            "selection_order": 2,
            "free_tier_required": True,
        },
        "schema_safe_fallback": {
            "model_id": SCHEMA_SAFE_FALLBACK_MODEL_ID,
            "provider_id": OPENROUTER_PROVIDER_ID,
            "role": "schema_safe_fallback",
            "selection_order": 2,
            "free_tier_required": True,
        },
    }


def get_free_cloud_worker_status() -> Dict[str, Any]:
    return {
        "canonical_engine_id": CANONICAL_ENGINE_ID,
        "legacy_alias": LEGACY_ALIAS,
        "provider_id": OPENROUTER_PROVIDER_ID,
        "models": get_free_cloud_model_registry(),
        "safe_defaults": asdict(FreeCloudPolicy()),
        "api_key_read_allowed": False,
        "real_http_call_allowed": False,
        "official_endpoint": OPENROUTER_ENDPOINT,
        "maximum_transport_attempts": MAXIMUM_TRANSPORT_ATTEMPTS,
        "maximum_request_bytes": MAX_REQUEST_BYTES,
        "maximum_response_bytes": MAX_RESPONSE_BYTES,
        "maximum_completion_tokens": MAX_COMPLETION_TOKENS,
        "deferred_retry_policy": {
            "transient_reasons": sorted(TRANSIENT_DEFER_REASONS),
            "base_cooldown_seconds": dict(COOLDOWN_SECONDS_BY_REASON),
            "maximum_cooldown_seconds": MAX_DEFERRED_COOLDOWN_SECONDS,
            "paid_escalation_requires_explicit_approval": True,
        },
    }


def resolve_free_cloud_engine_id(engine_id: str) -> Dict[str, Any]:
    normalized = str(engine_id or "").strip()
    if normalized in {CANONICAL_ENGINE_ID, LEGACY_ALIAS}:
        return {"ok": True, "engine_id": CANONICAL_ENGINE_ID, "legacy_alias": LEGACY_ALIAS, "input_engine_id": normalized}
    return {"ok": False, "engine_id": "unknown", "legacy_alias": LEGACY_ALIAS, "input_engine_id": normalized}


def evaluate_free_cloud_gates(policy: FreeCloudPolicy) -> Dict[str, Any]:
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
    if policy.billing_allowed:
        blockers.append("billing_forbidden")
    if policy.paid_fallback_allowed:
        blockers.append("paid_fallback_forbidden")
    if int(policy.maximum_model_attempts or 0) > MAXIMUM_MODEL_ATTEMPTS:
        blockers.append("attempt_limit_exceeded")
    return {
        "allowed": not blockers,
        "blockers": sorted(set(blockers)),
        "real_http_call_permitted": not blockers,
        "api_key_read": False,
        "maximum_model_attempts": min(max(0, int(policy.maximum_model_attempts or 0)), MAXIMUM_MODEL_ATTEMPTS),
    }


def validate_openrouter_endpoint(url: str = OPENROUTER_ENDPOINT) -> Dict[str, Any]:
    parsed = urlparse(str(url or ""))
    if parsed.scheme != "https":
        return {"ok": False, "reason": "https_required", "endpoint": redact_secret(url)}
    if parsed.hostname != "openrouter.ai":
        return {"ok": False, "reason": "non_official_host", "endpoint": redact_secret(url)}
    if parsed.port is not None:
        return {"ok": False, "reason": "port_override_forbidden", "endpoint": redact_secret(url)}
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return {"ok": False, "reason": "credential_or_query_forbidden", "endpoint": redact_secret(url)}
    if parsed.path != "/api/v1/chat/completions":
        return {"ok": False, "reason": "unsupported_path", "endpoint": redact_secret(url)}
    if str(url) != OPENROUTER_ENDPOINT:
        return {"ok": False, "reason": "custom_endpoint_forbidden", "endpoint": redact_secret(url)}
    return {"ok": True, "reason": "official_endpoint", "endpoint": OPENROUTER_ENDPOINT}


def validate_free_cloud_model(model_id: str) -> Dict[str, Any]:
    model = str(model_id or "")
    if model not in ALLOWED_MODEL_IDS:
        return {"ok": False, "reason": "model_not_allowed", "model_id": model}
    if not model.endswith(":free"):
        return {"ok": False, "reason": "non_free_model_forbidden", "model_id": model}
    return {"ok": True, "reason": "model_allowed", "model_id": model}


def build_openrouter_provider_policy() -> Dict[str, Any]:
    return {
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
    }


def build_free_cloud_response_schema() -> Dict[str, Any]:
    return {
        "name": "free_cloud_worker_result_v1",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["completed", "partial", "blocked", "rejected"]},
                "summary": {"type": "string"},
                "completed_scope": {"type": "array", "items": {"type": "string"}},
                "remaining_gap": {"type": "string"},
                "patch_operations": {"type": "array", "items": {"type": "object"}},
                "validation_suggestions": {"type": "array", "items": {"type": "string"}},
                "test_suggestions": {"type": "array", "items": {"type": "string"}},
                "failure_reason": {"type": "string"},
            },
            "required": [
                "status",
                "summary",
                "completed_scope",
                "remaining_gap",
                "patch_operations",
                "validation_suggestions",
                "test_suggestions",
                "failure_reason",
            ],
            "additionalProperties": False,
        },
    }


def read_openrouter_api_key(environ: Dict[str, str] | None = None) -> Dict[str, Any]:
    data = os.environ if environ is None else environ
    value = str(data.get("OPENROUTER_API_KEY") or "")
    return {
        "api_key_present": bool(value.strip()),
        "api_key": value if value.strip() else None,
    }


def build_openrouter_messages(request: Dict[str, Any]) -> List[Dict[str, str]]:
    payload = {
        "task": "Return a bounded structured JSON object for the requested code gap.",
        "contract": {
            "status": "completed|partial|blocked|rejected",
            "summary": "short",
            "completed_scope": [],
            "remaining_gap": "",
            "patch_operations": [],
            "validation_suggestions": [],
            "test_suggestions": [],
            "failure_reason": "",
        },
        "remaining_gap": request.get("remaining_gap"),
        "target_files": request.get("target_files", []),
        "target_symbols": request.get("target_symbols", []),
        "minimum_context": request.get("minimum_context", {}),
        "acceptance_criteria": request.get("acceptance_criteria", []),
    }
    prompt = stable_json(redact_secret(payload))[:MAX_PROMPT_CHARS]
    return [
        {"role": "system", "content": "You return only JSON. Do not include markdown, tools, web, or hidden reasoning."},
        {"role": "user", "content": prompt},
    ]


def build_openrouter_chat_payload(request: Dict[str, Any], *, max_tokens: int = MAX_COMPLETION_TOKENS) -> Dict[str, Any]:
    model_id = str(request.get("model_id") or "")
    model_check = validate_free_cloud_model(model_id)
    if not model_check.get("ok"):
        raise ValueError(str(model_check.get("reason")))
    if len(stable_json(request).encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("request_too_large")
    tokens = max(1, min(int(max_tokens or MAX_COMPLETION_TOKENS), MAX_COMPLETION_TOKENS))
    payload = {
        "model": model_id,
        "messages": build_openrouter_messages(request),
        "temperature": 0.1,
        "max_tokens": tokens,
        "stream": False,
        "response_format": {"type": "json_schema", "json_schema": build_free_cloud_response_schema()},
        "provider": build_openrouter_provider_policy(),
    }
    if model_id != SCHEMA_SAFE_FALLBACK_MODEL_ID:
        payload["reasoning"] = {"effort": "none", "exclude": True}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_REQUEST_BYTES:
        raise ValueError("request_too_large")
    return payload


def classify_openrouter_error(status_code: int | None = None, *, error_status: str = "") -> Dict[str, Any]:
    if error_status in {"timeout", "network_timeout"}:
        return {"failure_category": "timeout", "retryable": True}
    if error_status in {"network_error", "dns_error", "connect_failure"}:
        return {"failure_category": "provider_unavailable", "retryable": True}
    mapping = {
        400: ("unsupported_parameters", False),
        401: ("authentication_failed", False),
        402: ("paid_or_credit_required", False),
        403: ("provider_policy_blocked", False),
        404: ("unsupported_parameters", False),
        408: ("timeout", True),
        429: ("rate_limited", True),
        502: ("provider_unavailable", True),
        503: ("provider_unavailable", True),
    }
    category, retryable = mapping.get(int(status_code or 0), ("provider_unavailable", bool(status_code and int(status_code) >= 500)))
    return {"failure_category": category, "retryable": retryable}


def _extract_single_json_object(text: str) -> Dict[str, Any] | None:
    return _extract_single_json_object_with_metadata(text)["data"]


def _extract_single_json_object_with_metadata(text: str) -> Dict[str, Any]:
    cleaned = str(text or "").strip()
    metadata: Dict[str, Any] = {
        "content_type": type(text).__name__,
        "content_empty": cleaned == "",
        "json_parse_mode": "none",
        "markdown_json_fence": False,
        "single_json_object_found": False,
        "multiple_json_objects": False,
        "data": None,
    }
    if not cleaned:
        return metadata
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            metadata.update({"json_parse_mode": "direct", "single_json_object_found": True, "data": data})
        return metadata
    except json.JSONDecodeError:
        pass
    fence = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, flags=re.I | re.S)
    if fence:
        metadata["markdown_json_fence"] = True
        try:
            data = json.loads(fence.group(1).strip())
            if isinstance(data, dict):
                metadata.update({"json_parse_mode": "markdown_json_fence", "single_json_object_found": True, "data": data})
            return metadata
        except json.JSONDecodeError:
            return metadata

    decoder = json.JSONDecoder()
    matches: List[Dict[str, Any]] = []
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            data, end = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            matches.append({"data": data, "start": index, "end": index + end})
            if len(matches) > 1:
                metadata["multiple_json_objects"] = True
                return metadata
    if len(matches) == 1:
        metadata.update({"json_parse_mode": "extracted_single_object", "single_json_object_found": True, "data": matches[0]["data"]})
    return metadata


def parse_openrouter_structured_result(raw: Any, *, request: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(raw, dict):
        data = raw
    else:
        data = _extract_single_json_object(str(raw or ""))
        if data is None:
            return build_free_cloud_result(request=request, status="schema_invalid", analysis_summary="schema_invalid", failure_category="schema_invalid:no_json_object")
    status_map = {"completed": "completed", "partial": "partial", "blocked": "blocked", "rejected": "invalid"}
    status = str(data.get("status") or "")
    if status not in status_map:
        return build_free_cloud_result(request=request, status="schema_invalid", analysis_summary="schema_invalid", failure_category=f"schema_invalid:status:{status[:40]}")
    required = ("status", "summary", "completed_scope", "remaining_gap", "patch_operations", "validation_suggestions", "test_suggestions", "failure_reason")
    missing = [key for key in required if key not in data]
    if missing:
        return build_free_cloud_result(request=request, status="schema_invalid", analysis_summary="schema_invalid", failure_category="schema_invalid:missing:" + ",".join(missing))
    for key in ("completed_scope", "patch_operations", "validation_suggestions", "test_suggestions"):
        if key in data and not isinstance(data.get(key), list):
            return build_free_cloud_result(request=request, status="schema_invalid", analysis_summary="schema_invalid", failure_category=f"schema_invalid:type:{key}:{type(data.get(key)).__name__}")
    if not isinstance(data.get("summary"), str) or not isinstance(data.get("failure_reason"), str):
        return build_free_cloud_result(request=request, status="schema_invalid", analysis_summary="schema_invalid", failure_category="schema_invalid:type:summary_or_failure_reason")
    if not isinstance(data.get("remaining_gap"), (str, dict, list)):
        return build_free_cloud_result(request=request, status="schema_invalid", analysis_summary="schema_invalid", failure_category=f"schema_invalid:type:remaining_gap:{type(data.get('remaining_gap')).__name__}")
    return build_free_cloud_result(
        request=request,
        status=status_map[status],
        analysis_summary=str(data.get("summary") or ""),
        completed_scope=data.get("completed_scope") or [],
        remaining_gap=data.get("remaining_gap") or "",
        patch_operations=data.get("patch_operations") or [],
        validation_recommendations=list(data.get("validation_suggestions") or []) + list(data.get("test_suggestions") or []),
        assumptions=[],
        uncertainties=[],
        risk_flags=[],
        failure_category=str(data.get("failure_reason") or status_map[status]),
    )


def _inspect_openrouter_response(response: Dict[str, Any], payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    choices = response.get("choices")
    first = choices[0] if isinstance(choices, list) and choices else None
    message = first.get("message") if isinstance(first, dict) else None
    content = message.get("content") if isinstance(message, dict) else first.get("text") if isinstance(first, dict) else None
    reasoning = ""
    if isinstance(message, dict):
        reasoning = str(message.get("reasoning_content") or message.get("reasoning") or "")
    extraction = _extract_single_json_object_with_metadata(content if isinstance(content, str) else "")
    reasoning_extraction = _extract_single_json_object_with_metadata(reasoning) if not str(content or "").strip() and reasoning else {"single_json_object_found": False, "json_parse_mode": "none"}
    return {
        "http_status": response.get("http_status"),
        "choices_present": isinstance(choices, list) and bool(choices),
        "message_present": isinstance(message, dict),
        "message_content_type": type(content).__name__,
        "content_empty": not bool(str(content or "").strip()),
        "content_json_object": extraction["json_parse_mode"] == "direct",
        "markdown_json_fence": extraction["markdown_json_fence"],
        "safe_single_json_object": extraction["single_json_object_found"] or reasoning_extraction["single_json_object_found"],
        "multiple_json_objects": extraction["multiple_json_objects"],
        "json_parse_mode": extraction["json_parse_mode"],
        "reasoning_field_present": isinstance(message, dict) and any(key in message for key in ("reasoning", "reasoning_content")),
        "reasoning_json_parse_mode": reasoning_extraction["json_parse_mode"],
        "reasoning_single_json_object_found": reasoning_extraction["single_json_object_found"],
        "response_format_requested": bool((payload or {}).get("response_format")),
    }


def _extract_openrouter_content(response: Dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict):
        content = str(message.get("content") or "")
        if content.strip():
            return content
        return str(message.get("reasoning_content") or message.get("reasoning") or "")
    return str(first.get("text") or "")


def _bounded_read_response(response: Any) -> bytes:
    raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("response_too_large")
    return raw


def _request_openrouter_without_redirects(url: str, payload: Dict[str, Any], api_key: str, *, timeout_seconds: int) -> Dict[str, Any]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_REQUEST_BYTES:
        return {"ok": False, "status": "request_too_large", "retryable": False, "http_attempts": 0}
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
    timeout = max(1, min(int(timeout_seconds or MAX_TRANSPORT_TIMEOUT_SECONDS), MAX_TRANSPORT_TIMEOUT_SECONDS))
    started = time.perf_counter()
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = _bounded_read_response(response)
            latency_ms = int((time.perf_counter() - started) * 1000)
            status_code = int(getattr(response, "status", 200))
            request_id = response.headers.get("x-request-id", "")
    except TimeoutError:
        return {"ok": False, "status": "timeout", "failure_category": "timeout", "retryable": True, "latency_ms": timeout * 1000}
    except HTTPError as exc:
        raw = b""
        try:
            raw = exc.read(min(MAX_RESPONSE_BYTES, 4096))
        except Exception:
            raw = b""
        mapped = classify_openrouter_error(exc.code)
        return {"ok": False, "status": "http_error", "http_status": exc.code, "failure_category": mapped["failure_category"], "retryable": mapped["retryable"], "error": redact_secret(raw.decode("utf-8", "replace") or str(exc))}
    except URLError as exc:
        mapped = classify_openrouter_error(error_status="network_error")
        return {"ok": False, "status": "network_error", "failure_category": mapped["failure_category"], "retryable": mapped["retryable"], "error": redact_secret(str(exc.reason))}
    except ValueError as exc:
        return {"ok": False, "status": str(exc), "failure_category": str(exc), "retryable": False}
    if not raw:
        return {"ok": False, "status": "empty_response", "failure_category": "empty_response", "retryable": False, "http_status": status_code}
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "status": "schema_invalid", "failure_category": "schema_invalid", "retryable": False, "http_status": status_code}
    return {"ok": True, "status": "success", "http_status": status_code, "response": redact_secret(data), "latency_ms": latency_ms, "provider_request_id": request_id}


def execute_openrouter_chat_completion(
    *,
    request: Dict[str, Any],
    policy: FreeCloudPolicy,
    environ: Dict[str, str] | None = None,
    http_call: Callable[..., Dict[str, Any]] | None = None,
    live_execution_enabled: bool = False,
    timeout_seconds: int = MAX_TRANSPORT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    endpoint = validate_openrouter_endpoint(OPENROUTER_ENDPOINT)
    model_check = validate_free_cloud_model(str(request.get("model_id") or ""))
    gates = evaluate_free_cloud_gates(policy)
    if not live_execution_enabled:
        return {"ok": False, "transport_ready": False, "failure_reason": "live_execution_disabled", "http_attempts": 0, "endpoint": endpoint, "model": model_check}
    if not endpoint.get("ok"):
        return {"ok": False, "transport_ready": False, "failure_reason": endpoint.get("reason"), "http_attempts": 0, "endpoint": endpoint}
    if not model_check.get("ok"):
        return {"ok": False, "transport_ready": False, "failure_reason": model_check.get("reason"), "http_attempts": 0, "model": model_check}
    if not gates.get("allowed"):
        return {"ok": False, "transport_ready": False, "failure_reason": "gate_blocked", "blockers": gates["blockers"], "http_attempts": 0}
    key_ref = read_openrouter_api_key(environ)
    if not key_ref["api_key_present"]:
        return {"ok": False, "transport_ready": False, "failure_reason": "missing_api_key", "http_attempts": 0, "api_key_present": False}
    try:
        payload = build_openrouter_chat_payload(request)
    except ValueError as exc:
        return {"ok": False, "transport_ready": False, "failure_reason": str(exc), "http_attempts": 0}
    call = http_call or _request_openrouter_without_redirects
    attempts: List[Dict[str, Any]] = []
    for attempt in range(1, MAXIMUM_TRANSPORT_ATTEMPTS + 1):
        result = call(OPENROUTER_ENDPOINT, payload, key_ref["api_key"], timeout_seconds=timeout_seconds)
        safe_result = redact_secret(result)
        attempts.append({"attempt": attempt, "status": safe_result.get("status"), "http_status": safe_result.get("http_status"), "failure_category": safe_result.get("failure_category")})
        if result.get("ok"):
            response = result.get("response", {})
            if isinstance(response, dict):
                response["http_status"] = result.get("http_status")
            metadata = _inspect_openrouter_response(response if isinstance(response, dict) else {}, payload)
            content = _extract_openrouter_content(response if isinstance(response, dict) else {})
            if metadata.get("http_status") == 200 and metadata.get("choices_present") and metadata.get("message_present") and metadata.get("content_empty") and not metadata.get("safe_single_json_object"):
                attempts[-1]["model_result_outcome"] = "empty_response"
                if attempt < MAXIMUM_TRANSPORT_ATTEMPTS:
                    time.sleep(0.05)
                    continue
                empty_result = build_free_cloud_result(
                    request=request,
                    status="empty_response",
                    analysis_summary="empty_response",
                    remaining_gap=request.get("remaining_gap", ""),
                    failure_category="empty_response",
                )
                return {
                    "ok": False,
                    "transport_ready": True,
                    "live_external_verified": False,
                    "transport_status": "success",
                    "model_result_outcome": "empty_response",
                    "status": "empty_response",
                    "failure_reason": "empty_response",
                    "http_attempts": len(attempts),
                    "model_attempts": 1,
                    "selected_model": request.get("model_id"),
                    "structured_result_valid": False,
                    "result": empty_result,
                    "attempts": attempts,
                    "response_metadata": metadata,
                    "paid_fallback_allowed": False,
                }
            parsed = parse_openrouter_structured_result(content, request=request)
            structured_valid = parsed.get("status") not in {"schema_invalid", "invalid"}
            attempts[-1]["model_result_outcome"] = classify_savings_outcome(parsed, request.get("remaining_gap")) if structured_valid else "schema_invalid"
            return {
                "ok": structured_valid,
                "transport_ready": True,
                "live_external_verified": structured_valid,
                "transport_status": "success",
                "model_result_outcome": classify_savings_outcome(parsed, request.get("remaining_gap")) if structured_valid else "schema_invalid",
                "status": classify_savings_outcome(parsed, request.get("remaining_gap")) if structured_valid else "schema_invalid",
                "failure_reason": "" if structured_valid else "schema_invalid",
                "http_attempts": len(attempts),
                "model_attempts": 1,
                "selected_model": request.get("model_id"),
                "structured_result_valid": structured_valid,
                "result": parsed,
                "attempts": attempts,
                "response_metadata": metadata,
                "paid_fallback_allowed": False,
            }
        if not result.get("retryable") or attempt >= MAXIMUM_TRANSPORT_ATTEMPTS:
            return {
                "ok": False,
                "transport_ready": True,
                "live_external_verified": False,
                "status": result.get("status"),
                "failure_reason": result.get("failure_category") or result.get("status"),
                "http_attempts": len(attempts),
                "model_attempts": 1,
                "selected_model": request.get("model_id"),
                "structured_result_valid": False,
                "attempts": attempts,
                "paid_fallback_allowed": False,
            }
        time.sleep(0.05)
    return {"ok": False, "transport_ready": True, "failure_reason": "retry_exhausted", "http_attempts": len(attempts), "attempts": attempts}


def build_free_cloud_restore_policy(record: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "restore_auto_http": False,
        "request_auto_resend": False,
        "requires_explicit_live_execution": True,
        "record_loaded": bool(record),
    }


def run_free_cloud_live_qualification(*, environ: Dict[str, str] | None = None, http_call: Callable[..., Dict[str, Any]] | None = None) -> Dict[str, Any]:
    initial_remaining_gap = {"remaining_gap": "analyze off-by-one fixture and propose safe patch operation"}
    request_result = build_free_cloud_request(
        task_id="free-cloud-live-fixture",
        session_id="free-cloud-live-fixture",
        model_id=PRIMARY_MODEL_ID,
        attempt_number=1,
        selection_reason="primary_first",
        remaining_gap=initial_remaining_gap,
        completed_scope=[],
        minimum_context={"fixture.py": "def last_index(items):\n    return len(items)\n"},
        target_files=["fixture.py"],
        target_symbols=["last_index"],
        maximum_output_tokens=MAX_COMPLETION_TOKENS,
        timeout_seconds=MAX_TRANSPORT_TIMEOUT_SECONDS,
    )
    if not request_result.get("ok"):
        return {"implementation_validated": False, "live_external_verified": False, "live_reason": request_result.get("reason")}
    policy = FreeCloudPolicy(
        enabled=True,
        verified=True,
        transport_enabled=True,
        real_requests_enabled=True,
        network_allowed=True,
        free_tier_confirmed=True,
        billing_allowed=False,
        paid_fallback_allowed=False,
    )
    result = execute_openrouter_chat_completion(
        request=request_result["request"],
        policy=policy,
        environ=environ,
        http_call=http_call,
        live_execution_enabled=True,
    )
    model_results = [result]
    selected_models = [PRIMARY_MODEL_ID] if result.get("http_attempts", 0) else []
    fallback_used = False
    fallback_reason = ""
    final_result = result

    if result.get("failure_reason") in {"empty_response", "schema_invalid"} or result.get("status") in {"empty_response", "schema_invalid"}:
        selection = select_next_free_cloud_model(
            previous_result=result.get("result"),
            attempt_history=[{"result": result.get("result")}],
            remaining_gap=(result.get("result") or {}).get("remaining_gap") or initial_remaining_gap,
        )
        if selection.get("selected") and selection.get("model_id") == SCHEMA_SAFE_FALLBACK_MODEL_ID:
            fallback_used = True
            fallback_reason = str(result.get("failure_reason") or result.get("status") or "")
            schema_fallback_request = build_free_cloud_request(
                task_id="free-cloud-live-fixture",
                session_id="free-cloud-live-fixture",
                model_id=SCHEMA_SAFE_FALLBACK_MODEL_ID,
                attempt_number=2,
                selection_reason=str(selection.get("reason") or fallback_reason),
                remaining_gap=(result.get("result") or {}).get("remaining_gap") or initial_remaining_gap,
                completed_scope=[],
                minimum_context={},
                target_files=[],
                target_symbols=[],
                maximum_output_tokens=MAX_COMPLETION_TOKENS,
                timeout_seconds=MAX_TRANSPORT_TIMEOUT_SECONDS,
            )
            if schema_fallback_request.get("ok"):
                schema_fallback_result = execute_openrouter_chat_completion(
                    request=schema_fallback_request["request"],
                    policy=policy,
                    environ=environ,
                    http_call=http_call,
                    live_execution_enabled=True,
                )
                model_results.append(schema_fallback_result)
                if schema_fallback_result.get("http_attempts", 0):
                    selected_models.append(SCHEMA_SAFE_FALLBACK_MODEL_ID)
                final_result = schema_fallback_result

    model_http_attempts = [
        {
            "model": item.get("selected_model"),
            "http_attempts": item.get("http_attempts", 0),
            "outcome": item.get("failure_reason") or item.get("status") if not item.get("ok") else item.get("status"),
        }
        for item in model_results
    ]
    total_http_attempts = sum(int(item.get("http_attempts", 0) or 0) for item in model_results)
    model_attempt_count = len([item for item in model_results if int(item.get("http_attempts", 0) or 0) > 0])
    final_outcome = final_result.get("failure_reason") or final_result.get("status") if not final_result.get("ok") else final_result.get("status")
    deferred_retry = build_deferred_retry_decision(
        reason=str(final_outcome or ""),
        model_id=str(final_result.get("selected_model") or ""),
        remaining_gap=(final_result.get("result") or {}).get("remaining_gap") or initial_remaining_gap,
        completed_scope=[],
    )
    return {
        "implementation_validated": True,
        "transport_ready": final_result.get("transport_ready", False),
        "live_external_verified": final_result.get("live_external_verified", False),
        "selected_model": final_result.get("selected_model") or PRIMARY_MODEL_ID,
        "selected_models": selected_models,
        "model_http_attempts": model_http_attempts,
        "http_attempt_count": total_http_attempts,
        "model_attempt_count": model_attempt_count,
        "nex_final_outcome": result.get("status") or result.get("failure_reason"),
        "schema_fallback_called": SCHEMA_SAFE_FALLBACK_MODEL_ID in selected_models,
        "transport_outcome": final_result.get("transport_status") or final_result.get("status"),
        "structured_result_valid": final_result.get("structured_result_valid", False),
        "outcome": final_outcome,
        "fallback_used": fallback_used and final_result is not result,
        "fallback_reason": fallback_reason,
        "live_reason": final_result.get("failure_reason", ""),
        "external_service_deferred": deferred_retry["external_service_deferred"],
        "deferred_retry": deferred_retry,
        "retry_after_seconds": deferred_retry["retry_after_seconds"],
        "response_metadata": final_result.get("response_metadata", {}),
        "secret_redaction_status": "PASS",
        "paid_fallback_blocked": all(item.get("paid_fallback_allowed", False) is False for item in model_results),
        "safe_result": redact_secret({"models": model_results}),
    }


def _completed_scope_digest(completed_scope: Sequence[str] | None) -> str:
    return digest(sorted(str(item) for item in (completed_scope or [])), "completed-scope")


def _limited_context(minimum_context: Dict[str, Any], *, remaining_only: bool = False) -> Dict[str, str]:
    total = 0
    output: Dict[str, str] = {}
    for key in sorted(minimum_context or {}):
        clean_key = str(key)
        if remaining_only and clean_key.lower().startswith(("completed", "done", "finished")):
            continue
        if any(marker in clean_key.lower() for marker in (".env", "secret", "token", "api_key", "authorization", "password")):
            continue
        value = str(redact_secret(minimum_context[key]))
        remaining = MAX_CONTEXT_CHARS - total
        if remaining <= 0:
            break
        output[clean_key] = value[:remaining]
        total += len(output[clean_key])
    return output


def _empty_gap(remaining_gap: Any) -> bool:
    if remaining_gap is None or remaining_gap == "":
        return True
    if isinstance(remaining_gap, dict):
        value = remaining_gap.get("remaining_gap", remaining_gap)
        return value in ("", None, [], {})
    return False


def _request_core(
    *,
    request_id: str,
    task_id: str,
    session_id: str,
    model_id: str,
    attempt_number: int,
    selection_reason: str,
    remaining_gap: Any,
    completed_scope: Sequence[str] | None,
    minimum_context: Dict[str, Any],
    target_files: Sequence[str],
    target_symbols: Sequence[str],
    acceptance_criteria: Sequence[str] | None,
    required_output_schema: str,
    maximum_input_tokens: int,
    maximum_output_tokens: int,
    timeout_seconds: int,
) -> Dict[str, Any]:
    return {
        "request_id": request_id,
        "task_id": str(task_id),
        "session_id": str(session_id),
        "engine_id": CANONICAL_ENGINE_ID,
        "legacy_alias": LEGACY_ALIAS,
        "model_id": model_id,
        "attempt_number": max(1, min(int(attempt_number or 1), MAXIMUM_MODEL_ATTEMPTS)),
        "selection_reason": selection_reason,
        "remaining_gap": redact_secret(remaining_gap),
        "completed_scope_digest": _completed_scope_digest(completed_scope),
        "minimum_context": _limited_context(minimum_context, remaining_only=attempt_number > 1),
        "target_files": [str(item) for item in target_files],
        "target_symbols": [str(item) for item in target_symbols],
        "acceptance_criteria": [str(item) for item in (acceptance_criteria or ["structured-json", "remaining-gap-only", "no-apply"])],
        "required_output_schema": required_output_schema,
        "maximum_input_tokens": max(0, int(maximum_input_tokens or 0)),
        "maximum_output_tokens": max(0, int(maximum_output_tokens or 0)),
        "timeout_seconds": max(1, min(int(timeout_seconds or 60), 120)),
    }


def build_free_cloud_request(
    *,
    task_id: str,
    session_id: str,
    model_id: str,
    attempt_number: int,
    selection_reason: str,
    remaining_gap: Any,
    completed_scope: Sequence[str] | None = None,
    minimum_context: Dict[str, Any] | None = None,
    target_files: Sequence[str] | None = None,
    target_symbols: Sequence[str] | None = None,
    acceptance_criteria: Sequence[str] | None = None,
    required_output_schema: str = "free_cloud_worker_result_v1",
    maximum_input_tokens: int = 12000,
    maximum_output_tokens: int = 4000,
    timeout_seconds: int = 60,
    seen_request_digests: set[str] | None = None,
) -> Dict[str, Any]:
    if _empty_gap(remaining_gap):
        return {"ok": False, "reason": "empty_remaining_gap", "request": None}
    request = _request_core(
        request_id="",
        task_id=task_id,
        session_id=session_id,
        model_id=model_id,
        attempt_number=attempt_number,
        selection_reason=selection_reason,
        remaining_gap=remaining_gap,
        completed_scope=completed_scope,
        minimum_context=minimum_context or {},
        target_files=target_files or [],
        target_symbols=target_symbols or [],
        acceptance_criteria=acceptance_criteria,
        required_output_schema=required_output_schema,
        maximum_input_tokens=maximum_input_tokens,
        maximum_output_tokens=maximum_output_tokens,
        timeout_seconds=timeout_seconds,
    )
    request["request_digest"] = digest({key: value for key, value in request.items() if key not in {"request_id", "request_digest"}}, "free-cloud-request")
    request["request_id"] = request["request_digest"].replace("free-cloud-request-", "free-cloud-req-", 1)
    if seen_request_digests is not None:
        if request["request_digest"] in seen_request_digests:
            return {"ok": False, "reason": "duplicate_request_digest", "request": None}
        seen_request_digests.add(request["request_digest"])
    return {"ok": True, "reason": "request_ready", "request": request}


def build_free_cloud_result(
    *,
    request: Dict[str, Any],
    status: str,
    analysis_summary: str = "",
    completed_scope: Sequence[str] | None = None,
    remaining_gap: Any = "",
    target_files: Sequence[str] | None = None,
    target_symbols: Sequence[str] | None = None,
    patch_operations: Sequence[Dict[str, Any]] | None = None,
    validation_recommendations: Sequence[str] | None = None,
    assumptions: Sequence[str] | None = None,
    uncertainties: Sequence[str] | None = None,
    risk_flags: Sequence[str] | None = None,
    failure_category: str = "",
) -> Dict[str, Any]:
    safe_status = status if status in VALID_RESULT_STATUSES else "invalid"
    payload = {
        "status": safe_status,
        "analysis_summary": str(redact_secret(analysis_summary))[:4000],
        "completed_scope": [str(item) for item in (completed_scope or [])],
        "remaining_gap": redact_secret(remaining_gap or ""),
        "target_files": [str(item) for item in (target_files or request.get("target_files", []))],
        "target_symbols": [str(item) for item in (target_symbols or request.get("target_symbols", []))],
        "patch_operations": redact_secret(list(patch_operations or [])),
        "validation_recommendations": [str(item) for item in (validation_recommendations or [])],
        "assumptions": [str(redact_secret(item)) for item in (assumptions or [])],
        "uncertainties": [str(redact_secret(item)) for item in (uncertainties or [])],
        "risk_flags": [str(item) for item in (risk_flags or [])],
        "failure_category": str(failure_category or safe_status),
        "request_digest": request.get("request_digest", ""),
        "model_id": request.get("model_id", ""),
    }
    payload["result_digest"] = digest(payload, "free-cloud-result")
    return payload


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc_iso(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _format_utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_deferred_retry_decision(
    *,
    reason: str,
    model_id: str,
    remaining_gap: Any,
    completed_scope: Sequence[str] | None = None,
    prior_defer_count: int = 0,
    now: str | None = None,
) -> Dict[str, Any]:
    clean_reason = str(reason or "")
    if clean_reason not in TRANSIENT_DEFER_REASONS:
        return {
            "external_service_deferred": False,
            "reason": clean_reason,
            "retry_after_seconds": 0,
            "next_action": "continue_policy",
        }
    multiplier = max(1, min(int(prior_defer_count or 0) + 1, 3))
    retry_after = min(COOLDOWN_SECONDS_BY_REASON.get(clean_reason, 180) * multiplier, MAX_DEFERRED_COOLDOWN_SECONDS)
    deferred_at_dt = _parse_utc_iso(now or "") or _parse_utc_iso(_utc_now_iso())
    next_retry_dt = deferred_at_dt + timedelta(seconds=retry_after)
    return {
        "external_service_deferred": True,
        "reason": clean_reason,
        "live_reason": clean_reason,
        "model_id": str(model_id or ""),
        "selected_engine": CANONICAL_ENGINE_ID,
        "selected_model": str(model_id or ""),
        "deferred_at": _format_utc_iso(deferred_at_dt),
        "retry_after_seconds": retry_after,
        "cooldown_seconds": retry_after,
        "next_retry_eligible_at": _format_utc_iso(next_retry_dt),
        "temporary_failure_count": multiplier,
        "cooldown_tier": "short" if retry_after <= 240 else "medium",
        "next_action": "retry_free_cloud_after_cooldown",
        "remaining_gap": redact_secret(remaining_gap or ""),
        "remaining_gap_digest": digest(redact_secret(remaining_gap or ""), "remaining-gap"),
        "completed_scope_digest": _completed_scope_digest(completed_scope),
        "paid_escalation_allowed": False,
        "whale_or_codex_escalation_allowed": False,
    }


def inspect_deferred_retry_eligibility(metadata: Dict[str, Any] | None, *, now: str | None = None) -> Dict[str, Any]:
    record = redact_secret(dict(metadata or {}))
    if not record.get("external_service_deferred"):
        return {"retry_eligible": True, "external_service_deferred": False, "remaining_cooldown_seconds": 0, "reason": "not_deferred"}
    next_retry = _parse_utc_iso(str(record.get("next_retry_eligible_at") or ""))
    current = _parse_utc_iso(now or "") or _parse_utc_iso(_utc_now_iso())
    if next_retry is None:
        return {
            "retry_eligible": False,
            "external_service_deferred": True,
            "remaining_cooldown_seconds": None,
            "reason": "missing_or_invalid_next_retry_eligible_at",
            "paid_escalation_allowed": False,
            "whale_or_codex_escalation_allowed": False,
        }
    remaining = max(0, int((next_retry - current).total_seconds()))
    return {
        "retry_eligible": remaining == 0,
        "external_service_deferred": remaining > 0,
        "remaining_cooldown_seconds": remaining,
        "reason": str(record.get("live_reason") or record.get("reason") or ""),
        "deferred_at": record.get("deferred_at", ""),
        "next_retry_eligible_at": record.get("next_retry_eligible_at", ""),
        "paid_escalation_allowed": False,
        "whale_or_codex_escalation_allowed": False,
        "http_attempts": 0 if remaining > 0 else None,
    }


def restore_deferred_retry_metadata(metadata: Dict[str, Any] | None, *, now: str | None = None) -> Dict[str, Any]:
    record = redact_secret(dict(metadata or {}))
    eligibility = inspect_deferred_retry_eligibility(record, now=now)
    return {
        "metadata_loaded": bool(record),
        "external_service_deferred": bool(record.get("external_service_deferred")) and not eligibility.get("retry_eligible", False),
        "retry_eligibility": eligibility,
        "auto_http_started": False,
        "paid_escalation_allowed": False,
        "whale_or_codex_escalation_allowed": False,
        "metadata": record,
    }


def classify_savings_outcome(result: Dict[str, Any], previous_remaining_gap: Any = None) -> str:
    status = str(result.get("status") or "")
    if status == "completed" and (result.get("patch_operations") or not result.get("remaining_gap")):
        return "FREE_COMPLETED"
    if status == "partial" and result.get("completed_scope") and result.get("remaining_gap") and result.get("remaining_gap") != previous_remaining_gap:
        return "FREE_PARTIAL"
    return "FREE_REJECTED"


def select_next_free_cloud_model(
    *,
    previous_result: Dict[str, Any] | None = None,
    attempt_history: Sequence[Dict[str, Any]] | None = None,
    remaining_gap: Any = None,
) -> Dict[str, Any]:
    history = list(attempt_history or [])
    if len(history) >= MAXIMUM_MODEL_ATTEMPTS:
        return {"selected": False, "reason": "maximum_attempts_reached", "model_role": None, "model_id": None}
    if _empty_gap(remaining_gap):
        return {"selected": False, "reason": "empty_remaining_gap", "model_role": None, "model_id": None}
    models = get_free_cloud_model_registry()
    if not previous_result:
        return {"selected": True, "reason": "primary_first", "model_role": "primary", "model_id": models["primary"]["model_id"], "attempt_number": 1}
    status = str(previous_result.get("status") or "")
    failure = str(previous_result.get("failure_category") or status)
    if status == "completed":
        return {"selected": False, "reason": "completed_no_fallback", "model_role": None, "model_id": None}
    if failure == "complexity_or_context_gap" or (status in {"partial", "blocked"} and failure == "complexity_or_context_gap"):
        return {"selected": True, "reason": "complexity_or_context_gap", "model_role": "deep_reasoning_fallback", "model_id": models["deep_reasoning_fallback"]["model_id"], "attempt_number": len(history) + 1}
    if failure in SCHEMA_SAFE_REASONS or status in {"provider_unavailable", "schema_invalid"}:
        return {"selected": True, "reason": failure, "model_role": "schema_safe_fallback", "model_id": models["schema_safe_fallback"]["model_id"], "attempt_number": len(history) + 1}
    if failure in TERMINAL_FAILURES or status in TERMINAL_FAILURES:
        return {"selected": False, "reason": failure, "model_role": None, "model_id": None}
    return {"selected": False, "reason": "fallback_not_allowed", "model_role": None, "model_id": None}


def run_free_cloud_fixture_flow(
    *,
    task_id: str,
    session_id: str,
    remaining_gap: Any,
    minimum_context: Dict[str, Any],
    target_files: Sequence[str] | None = None,
    target_symbols: Sequence[str] | None = None,
    first_result: Dict[str, Any] | None = None,
    seen_request_digests: set[str] | None = None,
) -> Dict[str, Any]:
    seen = seen_request_digests if seen_request_digests is not None else set()
    attempts: List[Dict[str, Any]] = []
    selection = select_next_free_cloud_model(remaining_gap=remaining_gap)
    if not selection.get("selected"):
        return {"ok": False, "attempts": [], "stop_reason": selection["reason"], "savings_outcome": "FREE_REJECTED"}
    first = build_free_cloud_request(
        task_id=task_id,
        session_id=session_id,
        model_id=selection["model_id"],
        attempt_number=1,
        selection_reason=selection["reason"],
        remaining_gap=remaining_gap,
        completed_scope=[],
        minimum_context=minimum_context,
        target_files=target_files or [],
        target_symbols=target_symbols or [],
        seen_request_digests=seen,
    )
    if not first.get("ok"):
        return {"ok": False, "attempts": [], "stop_reason": first["reason"], "savings_outcome": "FREE_REJECTED"}
    result = first_result or build_free_cloud_result(request=first["request"], status="blocked", remaining_gap=remaining_gap, failure_category="fixture_missing")
    attempts.append({"selection": selection, "request": first["request"], "result": result})
    if result.get("status") == "completed" or _empty_gap(result.get("remaining_gap")):
        return {"ok": True, "attempts": attempts, "stop_reason": "completed_or_no_gap", "savings_outcome": classify_savings_outcome(result, remaining_gap)}
    next_selection = select_next_free_cloud_model(previous_result=result, attempt_history=attempts, remaining_gap=result.get("remaining_gap"))
    if not next_selection.get("selected"):
        return {"ok": True, "attempts": attempts, "stop_reason": next_selection["reason"], "savings_outcome": classify_savings_outcome(result, remaining_gap)}
    second = build_free_cloud_request(
        task_id=task_id,
        session_id=session_id,
        model_id=next_selection["model_id"],
        attempt_number=2,
        selection_reason=next_selection["reason"],
        remaining_gap=result.get("remaining_gap"),
        completed_scope=result.get("completed_scope", []),
        minimum_context=minimum_context,
        target_files=result.get("target_files", target_files or []),
        target_symbols=result.get("target_symbols", target_symbols or []),
        seen_request_digests=seen,
    )
    if not second.get("ok"):
        return {"ok": True, "attempts": attempts, "stop_reason": second["reason"], "savings_outcome": "FREE_REJECTED"}
    attempts.append({"selection": next_selection, "request": second["request"], "result": None})
    return {"ok": True, "attempts": attempts, "stop_reason": "second_attempt_prepared", "savings_outcome": classify_savings_outcome(result, remaining_gap)}


def direct_deepseek_eligible_after_free_cloud(
    *,
    completed_scope: Sequence[str] | None,
    free_cloud_exhausted: bool,
    paid_escalation_approved: bool = False,
) -> Dict[str, Any]:
    scope = list(completed_scope or [])
    decision = select_engine_preview(
        completed=False,
        completed_scope=scope,
        remaining_gap={"remaining_gap": "paid candidate after free cloud"},
        registry_overrides={"free_gemini": {"enabled": False}, CANONICAL_ENGINE_ID: {"enabled": False}, "direct_deepseek": {"enabled": True, "availability": "available"}},
        config_overrides={"network_allowed": True, "billing_allowed": True, "paid_escalation_allowed": True, "maximum_cost_per_request": 0.001},
        free_tier_exhaustion_confirmed=free_cloud_exhausted,
        paid_escalation_approved=paid_escalation_approved,
        cost_budget=0.001,
    )
    return {
        "eligible": decision.get("selected_engine") == "direct_deepseek",
        "decision": decision,
        "free_cloud_exhausted": free_cloud_exhausted,
    }


def build_free_cloud_manual_handoff_metadata(*, remaining_gap: Any, completed_scope: Sequence[str] | None, failure_classification: str, recommended_next_engine: str = "direct_deepseek") -> Dict[str, Any]:
    payload = {
        "remaining_gap": redact_secret(remaining_gap or ""),
        "completed_scope_digest": _completed_scope_digest(completed_scope),
        "failure_classification": str(failure_classification or ""),
        "recommended_next_engine": str(recommended_next_engine or ""),
        "manual_approval_required": True,
        "full_prompt_persisted": False,
        "secrets_persisted": False,
    }
    payload["handoff_digest"] = digest(payload, "free-cloud-handoff")
    return payload


def build_free_cloud_persistence_snapshot(*, session_state: Dict[str, Any], request: Dict[str, Any] | None, result: Dict[str, Any] | None, deferred_retry: Dict[str, Any] | None = None, outcome: str = "") -> Dict[str, Any]:
    payload = {
        "canonical_engine_id": CANONICAL_ENGINE_ID,
        "legacy_requested_engine": LEGACY_ALIAS,
        "model_attempt_history": [
            {
                "model_id": str((request or {}).get("model_id") or (result or {}).get("model_id") or ""),
                "request_digest": str((request or {}).get("request_digest") or ""),
                "result_digest": str((result or {}).get("result_digest") or ""),
                "outcome": str(outcome or (result or {}).get("status") or ""),
            }
        ],
        "completed_scope_digest": _completed_scope_digest((result or {}).get("completed_scope", session_state.get("completed_scope", []))),
        "remaining_gap": redact_secret((result or {}).get("remaining_gap", session_state.get("remaining_gap", ""))),
        "free_cloud_outcome": str(outcome or ""),
        "deferred_metadata": redact_secret(deferred_retry or {}),
        "cooldown_eligibility": inspect_deferred_retry_eligibility(deferred_retry or {}),
        "duplicate_fingerprint": engine_failure_fingerprint(CANONICAL_ENGINE_ID, (result or {}).get("remaining_gap", session_state.get("remaining_gap", ""))),
        "validation_evidence": [str(item) for item in session_state.get("evidence_ids", [])],
        "paid_escalation_blocked": True,
        "manual_handoff_eligibility": bool((result or {}).get("remaining_gap")),
        "auto_http_on_restore": False,
        "auto_paid_escalation_on_restore": False,
    }
    payload = redact_secret(payload)
    payload["snapshot_digest"] = digest(payload, "free-cloud-snapshot")
    return payload


def execute_free_cloud_first_usable_handoff(
    *,
    task_id: str,
    session_id: str,
    task_summary: str,
    previous_result: Dict[str, Any],
    completed_scope: Sequence[str],
    target_files: Sequence[str],
    target_symbols: Sequence[str],
    minimum_context: Dict[str, Any],
    policy: FreeCloudPolicy,
    execution_gate_open: bool = False,
    restored_deferred_metadata: Dict[str, Any] | None = None,
    now: str | None = None,
    seen_request_digests: set[str] | None = None,
    seen_stage_input_digests: set[str] | None = None,
    failed_engine_fingerprints: Sequence[str] | None = None,
    http_call: Callable[..., Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    from luxcode_first_usable_session_flow import build_handoff_preview, build_session_state

    if previous_result.get("completed") is True:
        session = build_session_state(session_id=session_id, task_id=task_id, current_stage="completed", completed_scope=completed_scope, remaining_gap=previous_result.get("remaining_gap", ""), final_status="completed", stop_reason="completed_by_lower_tier")
        return {"ok": True, "completed": True, "transport_called": False, "stop_reason": "completed_by_lower_tier", "session_state": session}

    remaining_gap = previous_result.get("remaining_gap") or previous_result.get("next_remaining_gap")
    if _empty_gap(remaining_gap):
        session = build_session_state(session_id=session_id, task_id=task_id, current_stage="blocked", completed_scope=completed_scope, remaining_gap="", final_status="blocked", stop_reason="empty_remaining_gap")
        return {"ok": False, "completed": False, "transport_called": False, "stop_reason": "empty_remaining_gap", "session_state": session}

    restored = restore_deferred_retry_metadata(restored_deferred_metadata or {}, now=now)
    if restored_deferred_metadata and not restored["retry_eligibility"].get("retry_eligible"):
        session = build_session_state(session_id=session_id, task_id=task_id, current_stage="handoff_required", selected_engine=CANONICAL_ENGINE_ID, selected_tier=3, completed_scope=completed_scope, remaining_gap=remaining_gap, target_files=target_files, target_symbols=target_symbols, final_status="deferred", stop_reason="cooldown_active")
        return {"ok": False, "completed": False, "transport_called": False, "http_attempts": 0, "external_service_deferred": True, "retry_eligibility": restored["retry_eligibility"], "session_state": session, "persistence": {"free_cloud_metadata": restored}}

    preview = build_handoff_preview(
        session={"session_id": session_id, "task_id": task_id, "task_summary": task_summary},
        completed=False,
        completed_scope=completed_scope,
        remaining_gap=remaining_gap,
        minimum_context=minimum_context,
        target_files=target_files,
        target_symbols=target_symbols,
        seen_request_digests=seen_request_digests,
        seen_stage_input_digests=seen_stage_input_digests,
        failed_attempt_fingerprints=failed_engine_fingerprints,
        registry_overrides={CANONICAL_ENGINE_ID: {"enabled": policy.enabled, "verified": policy.verified, "availability": "available"}},
    )
    if preview.get("selected_engine") != CANONICAL_ENGINE_ID:
        return {"ok": False, "completed": False, "transport_called": False, "stop_reason": "free_cloud_not_selected", "preview": preview, "session_state": preview.get("session_state")}
    if not execution_gate_open:
        return {"ok": False, "completed": False, "transport_called": False, "stop_reason": "execution_gate_closed", "preview": preview, "session_state": preview.get("session_state")}

    request_result = build_free_cloud_request(
        task_id=task_id,
        session_id=session_id,
        model_id=PRIMARY_MODEL_ID,
        attempt_number=1,
        selection_reason="primary_first",
        remaining_gap=remaining_gap,
        completed_scope=completed_scope,
        minimum_context=minimum_context,
        target_files=target_files,
        target_symbols=target_symbols,
        seen_request_digests=seen_request_digests,
    )
    if not request_result.get("ok"):
        session = build_session_state(session_id=session_id, task_id=task_id, current_stage="blocked", selected_engine=CANONICAL_ENGINE_ID, selected_tier=3, completed_scope=completed_scope, remaining_gap=remaining_gap, target_files=target_files, target_symbols=target_symbols, final_status="blocked", stop_reason=str(request_result.get("reason")))
        return {"ok": False, "completed": False, "transport_called": False, "stop_reason": request_result.get("reason"), "session_state": session}

    result = execute_openrouter_chat_completion(request=request_result["request"], policy=policy, environ={"OPENROUTER_API_KEY": "fixture-not-persisted"}, http_call=http_call, live_execution_enabled=True)
    model_results = [result]
    final_result = result
    parsed = result.get("result") or {}
    if result.get("failure_reason") in {"empty_response", "schema_invalid", "provider_unavailable", "rate_limited"} or parsed.get("failure_category") in SCHEMA_SAFE_REASONS or parsed.get("failure_category") == "complexity_or_context_gap":
        selection = select_next_free_cloud_model(previous_result=parsed, attempt_history=[{"result": parsed}], remaining_gap=parsed.get("remaining_gap") or remaining_gap)
        if selection.get("selected"):
            second_request = build_free_cloud_request(
                task_id=task_id,
                session_id=session_id,
                model_id=str(selection["model_id"]),
                attempt_number=2,
                selection_reason=str(selection["reason"]),
                remaining_gap=parsed.get("remaining_gap") or remaining_gap,
                completed_scope=parsed.get("completed_scope", []),
                minimum_context={},
                target_files=[],
                target_symbols=[],
                seen_request_digests=seen_request_digests,
            )
            if second_request.get("ok"):
                second_result = execute_openrouter_chat_completion(request=second_request["request"], policy=policy, environ={"OPENROUTER_API_KEY": "fixture-not-persisted"}, http_call=http_call, live_execution_enabled=True)
                model_results.append(second_result)
                final_result = second_result
                parsed = second_result.get("result") or {}
    transport_called = any(bool(item.get("http_attempts", 0)) for item in model_results)
    total_http_attempts = sum(int(item.get("http_attempts", 0) or 0) for item in model_results)
    model_attempt_count = len([item for item in model_results if int(item.get("http_attempts", 0) or 0) > 0])
    final_reason = str(final_result.get("failure_reason") or final_result.get("status") or "")
    deferred_retry = build_deferred_retry_decision(reason=final_reason, model_id=str(final_result.get("selected_model") or ""), remaining_gap=parsed.get("remaining_gap") or remaining_gap)
    savings_outcome = final_result.get("status") if final_result.get("structured_result_valid") else "FREE_REJECTED"
    if deferred_retry.get("external_service_deferred"):
        final_status = "deferred"
        stop_reason = str(deferred_retry.get("live_reason") or "external_service_deferred")
    elif final_result.get("structured_result_valid") and savings_outcome == "FREE_COMPLETED":
        final_status = "completed"
        stop_reason = "free_cloud_completed"
    elif final_result.get("structured_result_valid") and savings_outcome == "FREE_PARTIAL":
        final_status = "partial"
        stop_reason = "free_cloud_partial"
    else:
        final_status = "manual_decision_required"
        stop_reason = "free_cloud_rejected"

    next_gap = "" if final_status == "completed" else parsed.get("remaining_gap", remaining_gap)
    session = build_session_state(session_id=session_id, task_id=task_id, current_stage="completed" if final_status == "completed" else "handoff_required", selected_engine=CANONICAL_ENGINE_ID, selected_tier=3, completed_scope=list(completed_scope) + list(parsed.get("completed_scope", [])), remaining_gap=next_gap, target_files=target_files, target_symbols=target_symbols, request_id=request_result["request"].get("request_id"), result_id=parsed.get("result_digest"), final_status=final_status, stop_reason=stop_reason)
    persistence = build_free_cloud_persistence_snapshot(session_state=session, request=request_result["request"], result=parsed, deferred_retry=deferred_retry, outcome=savings_outcome)
    handoff = None
    if final_status in {"partial", "manual_decision_required"}:
        handoff = build_free_cloud_manual_handoff_metadata(remaining_gap=next_gap, completed_scope=session.get("completed_scope", []), failure_classification=stop_reason)
    return {"ok": final_status == "completed", "completed": final_status == "completed", "transport_called": transport_called, "http_attempts": total_http_attempts, "model_attempt_count": model_attempt_count, "model_results": redact_secret(model_results), "stop_reason": stop_reason, "savings_outcome": savings_outcome, "external_service_deferred": deferred_retry.get("external_service_deferred", False), "deferred_retry": deferred_retry, "result": parsed, "session_state": session, "persistence": persistence, "manual_handoff": handoff, "deepseek_eligible": False, "paid_escalation_blocked": True}
