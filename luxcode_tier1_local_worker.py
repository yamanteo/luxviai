from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from luxcode_low_cost_worker import build_safe_patch_contract_from_response, safe_patch_preview
from luxcode_low_cost_worker_contracts import (
    AvailabilityState,
    RetryState,
    WorkerRequest,
    WorkerResponse,
    build_worker_request,
    parse_worker_response,
    validate_worker_response,
)


TIER1_PROVIDER_ID = "tier1_local_worker"
TIER1_DEFAULT_RUNTIME_ID = "fixture_local_runtime"
TIER1_DEFAULT_MODEL_ID = "fixture_local_coding_model"
TIER1_OLLAMA_RUNTIME_ID = "ollama_loopback"
TIER1_OLLAMA_MODEL_ID = "qwen2.5-coder:7b"
TIER1_OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
TIER1_REQUIRED_OUTPUT = "structured_json_v1"
MAX_OLLAMA_RESPONSE_BYTES = 1_000_000


@dataclass(frozen=True)
class Tier1Evidence:
    evidence_id: str
    task_id: str
    tier: int
    runtime_id: str
    model_id: str
    status: str
    summary: str
    target_files: tuple[str, ...]
    response_digest: str
    patch_digest: str
    failure_fingerprint: str
    duration_ms: int
    resource_profile: str
    created_at: str


def _stable_digest(payload: Any, *, prefix: str) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:24]}"


def _require_loopback_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme != "http":
        raise ValueError("ollama endpoint must use http loopback")
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("ollama endpoint must be loopback")
    if parsed.port not in {None, 11434}:
        raise ValueError("ollama endpoint port not allowed")
    return endpoint.rstrip("/")


def _ollama_json_request(endpoint: str, path: str, payload: Dict[str, Any] | None = None, *, timeout_seconds: int = 10) -> Dict[str, Any]:
    base = _require_loopback_endpoint(endpoint)
    body = None if payload is None else json.dumps(payload, sort_keys=True).encode("utf-8")
    request = Request(
        base + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(MAX_OLLAMA_RESPONSE_BYTES + 1)
    except TimeoutError:
        return {"ok": False, "state": "timeout", "error": "timeout"}
    except HTTPError as exc:
        return {"ok": False, "state": "http_error", "status_code": exc.code, "error": str(exc)}
    except URLError as exc:
        return {"ok": False, "state": "connection_failure", "error": str(exc.reason)}
    if len(raw) > MAX_OLLAMA_RESPONSE_BYTES:
        return {"ok": False, "state": "response_too_large", "error": "response size limit exceeded"}
    if not raw:
        return {"ok": False, "state": "empty_response", "error": "empty response"}
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "state": "invalid_json", "error": str(exc)}
    return {"ok": True, "state": "available", "data": data}


def check_ollama_health(endpoint: str = TIER1_OLLAMA_ENDPOINT, *, timeout_seconds: int = 5) -> Dict[str, Any]:
    try:
        _require_loopback_endpoint(endpoint)
    except ValueError as exc:
        return {"ok": False, "state": "endpoint_rejected", "error": str(exc), "loopback_only": True}
    result = _ollama_json_request(endpoint, "/api/tags", timeout_seconds=timeout_seconds)
    if not result.get("ok"):
        return {**result, "loopback_only": True}
    models = result.get("data", {}).get("models", [])
    names = sorted(str(item.get("name") or "") for item in models if isinstance(item, dict) and item.get("name"))
    return {"ok": True, "state": "available", "models": names, "loopback_only": True}


def check_ollama_model(
    model_id: str = TIER1_OLLAMA_MODEL_ID,
    *,
    endpoint: str = TIER1_OLLAMA_ENDPOINT,
    timeout_seconds: int = 5,
) -> Dict[str, Any]:
    health = check_ollama_health(endpoint, timeout_seconds=timeout_seconds)
    if not health.get("ok"):
        return health
    models = health.get("models", [])
    return {
        **health,
        "model_id": model_id,
        "model_available": model_id in models,
        "state": "model_available" if model_id in models else "model_missing",
    }


def _tier1_prompt(request: WorkerRequest) -> str:
    files = ", ".join(request.target_files)
    symbols = ", ".join(request.target_symbols)
    context = {key: value for key, value in request.minimum_context.items() if not key.startswith("_")}
    return (
        "Return only one JSON object. Do not use markdown.\n"
        "You are a local coding model producing a safe patch draft for LUXCODE.\n"
        f"request_id: {request.request_id}\n"
        f"task_summary: {request.task_summary}\n"
        f"target_files: {files}\n"
        f"target_symbols: {symbols}\n"
        f"minimum_context_json: {json.dumps(context, sort_keys=True)}\n"
        "Required JSON keys: response_id, request_id, status, analysis_summary, completed_scope, "
        "remaining_gap, target_files, target_symbols, patch_operations, validation_recommendations, "
        "assumptions, uncertainties, risk_flags, unsupported_requests, model_metadata.\n"
        'model_metadata must include {"runtime_id":"ollama_loopback","local_only":true,"external_api_used":false}.\n'
        "Use status completed. Use exactly one patch_operations item with this exact shape: "
        '{"operation_id":"op-1","operation_type":"replace_text","file_path":"src/app.py",'
        '"anchor_text":"","old_text":"def greet():\\n    return 1\\n",'
        '"new_text":"def greet():\\n    return 2\\n","expected_occurrences":1,'
        '"reason":"safe local fixture patch","confidence":0.95}. '
        "Do not omit file_path. Do not use a file outside target_files. "
        "For the fixture, replace return 1 with return 2."
    )


def _extract_model_text(data: Dict[str, Any]) -> str:
    text = str(data.get("response") or "")
    if text:
        return text.strip()
    message = data.get("message")
    if isinstance(message, dict):
        return str(message.get("content") or "").strip()
    return ""


def run_ollama_tier1_inference(
    *,
    request: WorkerRequest,
    endpoint: str = TIER1_OLLAMA_ENDPOINT,
    model_id: str = TIER1_OLLAMA_MODEL_ID,
    timeout_seconds: int = 90,
    repair_attempt: bool = False,
) -> Dict[str, Any]:
    model = check_ollama_model(model_id, endpoint=endpoint, timeout_seconds=5)
    if not model.get("ok"):
        return {"ok": False, "state": model.get("state", "runtime_unavailable"), "error": model.get("error", "")}
    if not model.get("model_available"):
        return {"ok": False, "state": "model_missing", "model_id": model_id, "models": model.get("models", [])}
    prompt = _tier1_prompt(request)
    if repair_attempt:
        prompt += "\nPrevious output was not valid JSON. Return only valid JSON matching the requested schema."
    payload = {
        "model": model_id,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "num_predict": 450},
    }
    result = _ollama_json_request(endpoint, "/api/generate", payload, timeout_seconds=timeout_seconds)
    if not result.get("ok"):
        return result
    text = _extract_model_text(result.get("data", {}))
    if not text:
        return {"ok": False, "state": "empty_response", "raw": result.get("data", {})}
    try:
        response = parse_tier1_response(text, request=request, runtime_id=TIER1_OLLAMA_RUNTIME_ID)
    except ValueError as exc:
        return {"ok": False, "state": "invalid_json", "error": str(exc), "raw_text": text[:4000]}
    return {"ok": True, "state": "response_parsed", "response": response, "raw_text": text, "model_id": model_id}


def _remaining_gap_payload(tier0_diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    gap = tier0_diagnostics.get("remaining_gap") or {}
    if isinstance(gap, dict):
        return dict(gap.get("remaining_gap") or gap)
    return {}


def build_tier1_request_from_tier0(
    *,
    request_id: str,
    task_id: str,
    task_summary: str,
    tier0_diagnostics: Dict[str, Any],
    target_files: Sequence[str],
    target_symbols: Sequence[str],
    minimum_context: Dict[str, str],
    runtime_id: str = TIER1_DEFAULT_RUNTIME_ID,
    model_id: str = TIER1_DEFAULT_MODEL_ID,
) -> WorkerRequest:
    gap = _remaining_gap_payload(tier0_diagnostics)
    remaining_gap = str(gap.get("remaining_gap", "") or "tier0_remaining_gap")
    completed_scope = list(gap.get("completed_scope") or [])
    failed_fingerprints = list(gap.get("failed_attempt_fingerprints") or [])
    acceptance = [
        "local-runtime-only",
        "structured-json",
        "provider-neutral",
        "safe-patch-preview",
        "approval-required",
    ]
    return build_worker_request(
        request_id=request_id,
        task_id=task_id,
        provider_id=TIER1_PROVIDER_ID,
        model_id=model_id,
        task_class="small_code_fix",
        task_summary=task_summary,
        remaining_gap=remaining_gap,
        target_files=list(target_files),
        target_symbols=list(target_symbols),
        minimum_context={**minimum_context, "_tier1_runtime_id": runtime_id},
        completed_scope=completed_scope,
        failed_attempt_fingerprints=failed_fingerprints,
        acceptance_criteria=acceptance,
        required_output_format=TIER1_REQUIRED_OUTPUT,
        risk_level="low",
        permission_mode="preview_only",
        maximum_input_tokens=16000,
        maximum_output_tokens=4000,
        maximum_cost=0.0,
        timeout_seconds=90,
    )


def parse_tier1_response(raw: str, *, request: WorkerRequest, runtime_id: str = TIER1_DEFAULT_RUNTIME_ID) -> WorkerResponse:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_json") from exc
    if not isinstance(data, dict):
        raise ValueError("response must be object")
    model_metadata = dict(data.get("model_metadata") or {})
    if model_metadata.get("runtime_id") and model_metadata.get("runtime_id") != runtime_id:
        raise ValueError("runtime_id_mismatch")
    data.setdefault("provider_id", request.provider_id)
    data.setdefault("model_id", request.model_id)
    data["response_status"] = data.pop("status", data.get("response_status", "completed"))
    data.setdefault("scope_violations", [])
    data.setdefault("usage_metadata", {"input_tokens": 0, "output_tokens": 0, "estimated_cost": 0.0})
    return parse_worker_response(json.dumps(data, sort_keys=True, separators=(",", ":")))


def validate_tier1_response(
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


def build_safe_patch_contract_from_tier1_response(
    *,
    request: WorkerRequest,
    response: WorkerResponse,
    repository_root: str,
    repository_head: str = "",
    protected_files: Sequence[str] | None = None,
    file_contents: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    contract = build_safe_patch_contract_from_response(
        request=request,
        response=response,
        repository_root=repository_root,
        repository_head=repository_head,
        protected_files=protected_files or [],
        file_contents=file_contents or {},
    )
    contract["source"] = "tier1_local_worker"
    contract["tier"] = 1
    contract["runtime_id"] = str(request.minimum_context.get("_tier1_runtime_id") or TIER1_DEFAULT_RUNTIME_ID)
    return contract


def build_tier1_evidence(
    *,
    request: WorkerRequest,
    response: WorkerResponse,
    patch_contract: Dict[str, Any],
    status: str,
    duration_ms: int = 0,
    resource_profile: str = "fixture_local",
    failure_fingerprint: str = "",
) -> Dict[str, Any]:
    runtime_id = str(request.minimum_context.get("_tier1_runtime_id") or TIER1_DEFAULT_RUNTIME_ID)
    payload = {
        "task_id": request.task_id,
        "tier": 1,
        "runtime_id": runtime_id,
        "model_id": request.model_id,
        "status": status,
        "summary": response.analysis_summary,
        "target_files": tuple(response.target_files),
        "response_digest": response.response_digest,
        "patch_digest": patch_contract.get("patch_digest", ""),
        "failure_fingerprint": failure_fingerprint,
        "duration_ms": int(duration_ms),
        "resource_profile": resource_profile,
    }
    return asdict(
        Tier1Evidence(
            evidence_id=_stable_digest(payload, prefix="tier1-evidence"),
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **payload,
        )
    )


def build_tier1_remaining_gap(
    *,
    request: WorkerRequest,
    response: WorkerResponse,
    fallback_required: bool = False,
) -> Dict[str, Any]:
    payload = {
        "completed_scope": sorted(set(request.completed_scope + response.completed_scope)),
        "remaining_gap": response.remaining_gap,
        "target_files": sorted(set(response.target_files)),
        "target_symbols": sorted(set(response.target_symbols)),
        "failed_attempt_fingerprints": sorted(set(request.failed_attempt_fingerprints)),
        "fallback_required": bool(fallback_required),
    }
    return {**payload, "digest": _stable_digest(payload, prefix="tier1-gap")}


def calculate_tier1_retry_state(
    *,
    current_state: RetryState,
    failure_kind: str,
    similar_failure_count: int,
    availability: AvailabilityState,
) -> tuple[RetryState, bool]:
    if current_state == RetryState.BLOCKED:
        return RetryState.BLOCKED, False
    if availability in {AvailabilityState.DISABLED, AvailabilityState.AUTHENTICATION_FAILED}:
        return RetryState.BLOCKED, False
    if failure_kind == "invalid_json" and current_state in {RetryState.NOT_STARTED, RetryState.FIRST_ATTEMPT}:
        return RetryState.FORMAT_REPAIR, True
    if failure_kind in {"duplicate_patch", "same_patch"}:
        return RetryState.APPROACH_CHANGE, True
    if similar_failure_count >= 3:
        return RetryState.FALLBACK_REQUIRED, True
    return RetryState.BLOCKED, False


def preview_tier1_safe_patch(contract: Dict[str, Any]) -> Dict[str, Any]:
    return safe_patch_preview(contract)


def _fallback_evidence(
    *,
    task_id: str,
    model_id: str,
    state: str,
    summary: str,
    target_files: Sequence[str],
    failure_fingerprint: str,
) -> Dict[str, Any]:
    payload = {
        "task_id": task_id,
        "tier": 1,
        "runtime_id": TIER1_OLLAMA_RUNTIME_ID,
        "model_id": model_id,
        "status": state,
        "summary": summary,
        "target_files": tuple(target_files),
        "response_digest": "",
        "patch_digest": "",
        "failure_fingerprint": failure_fingerprint,
        "duration_ms": 0,
        "resource_profile": "ollama_loopback",
    }
    return asdict(
        Tier1Evidence(
            evidence_id=_stable_digest(payload, prefix="tier1-evidence"),
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **payload,
        )
    )


def _tier1_router_availability(model_state: Dict[str, Any]) -> Dict[str, Any]:
    tier1_state = "available" if model_state.get("ok") and model_state.get("model_available") else "disabled"
    return {
        "network_allowed": False,
        "availability": {
            "deterministic_local_tools": "available",
            "lightweight_local_coding_model": tier1_state,
            "free_cloud_open_coding_model": "disabled",
            "gemini_ai_studio_free": "disabled",
        },
    }


def execute_tier0_router_tier1_preview(
    *,
    task_id: str,
    repository_root: str,
    task_summary: str,
    target_files: Sequence[str],
    target_symbols: Sequence[str],
    minimum_context: Dict[str, str],
    endpoint: str = TIER1_OLLAMA_ENDPOINT,
    model_id: str = TIER1_OLLAMA_MODEL_ID,
    persist: bool = False,
) -> Dict[str, Any]:
    from luxcode_task_persistence import save_task_state
    from luxcode_tier0_deterministic_executor import run_tier0_diagnostics
    from luxcode_zero_cost_execution_router import route_zero_cost_task

    diagnostics = run_tier0_diagnostics(repository_root, task_summary, list(target_files))
    remaining_gap = diagnostics.get("remaining_gap", {})
    model_state = check_ollama_model(model_id, endpoint=endpoint, timeout_seconds=5)
    route = route_zero_cost_task(
        task_id=task_id,
        title=task_summary,
        description=str(remaining_gap),
        task_class="small_code_fix",
        required_capabilities=["code_generation", "patch_candidate_draft"],
        forbidden_capabilities=["network_operation"],
        risk_level="low",
        selected_files=list(target_files),
        difficulty_score=3,
        availability=_tier1_router_availability(model_state),
        policy={
            "paid_escalation_allowed": False,
            "network_allowed": False,
            "disabled_tiers": [] if model_state.get("model_available") else ["lightweight_local_coding_model"],
        },
        user_requires_free_only=True,
    )
    selected = route.get("selected_primary_tier") == "lightweight_local_coding_model"
    if not selected:
        state = "tier1_not_selected"
        fingerprint = _stable_digest({"task_id": task_id, "route": route, "model": model_state}, prefix="tier1-failure")
        evidence = _fallback_evidence(
            task_id=task_id,
            model_id=model_id,
            state=state,
            summary="Tier 1 local worker not selected by router",
            target_files=target_files,
            failure_fingerprint=fingerprint,
        )
        return {
            "ok": False,
            "state": state,
            "tier0_diagnostics": diagnostics,
            "remaining_gap": remaining_gap,
            "route_decision": route,
            "model_state": model_state,
            "evidence": evidence,
            "persistence": {"saved": False, "reason": "not_selected"},
        }

    request = build_tier1_request_from_tier0(
        request_id=_stable_digest({"task_id": task_id, "tier": 1}, prefix="tier1-req"),
        task_id=task_id,
        task_summary=task_summary,
        tier0_diagnostics=diagnostics,
        target_files=target_files,
        target_symbols=target_symbols,
        minimum_context=minimum_context,
        runtime_id=TIER1_OLLAMA_RUNTIME_ID,
        model_id=model_id,
    )
    inference = run_ollama_tier1_inference(request=request, endpoint=endpoint, model_id=model_id, timeout_seconds=90)
    if inference.get("state") == "invalid_json":
        inference = run_ollama_tier1_inference(
            request=request,
            endpoint=endpoint,
            model_id=model_id,
            timeout_seconds=90,
            repair_attempt=True,
        )
    if not inference.get("ok"):
        fingerprint = _stable_digest({"task_id": task_id, "inference": inference}, prefix="tier1-failure")
        evidence = _fallback_evidence(
            task_id=task_id,
            model_id=model_id,
            state=str(inference.get("state") or "tier1_inference_failed"),
            summary=str(inference.get("error") or "Tier 1 inference failed"),
            target_files=target_files,
            failure_fingerprint=fingerprint,
        )
        return {
            "ok": False,
            "state": "tier1_inference_failed",
            "tier0_diagnostics": diagnostics,
            "remaining_gap": remaining_gap,
            "route_decision": route,
            "model_state": model_state,
            "inference": {key: value for key, value in inference.items() if key != "response"},
            "evidence": evidence,
            "persistence": {"saved": False, "reason": "inference_failed"},
        }

    response = inference["response"]
    validation = validate_tier1_response(
        request=request,
        response=response,
        known_files=set(target_files),
        known_symbols=set(target_symbols),
        protected_files=set(),
        file_contents=minimum_context,
        failed_patch_fingerprints=set(request.failed_attempt_fingerprints),
    )
    if not validation.get("valid"):
        fingerprint = _stable_digest({"task_id": task_id, "validation": validation}, prefix="tier1-failure")
        evidence = _fallback_evidence(
            task_id=task_id,
            model_id=model_id,
            state="tier1_validation_failed",
            summary="Tier 1 response failed validation",
            target_files=target_files,
            failure_fingerprint=fingerprint,
        )
        return {
            "ok": False,
            "state": "tier1_validation_failed",
            "tier0_diagnostics": diagnostics,
            "remaining_gap": remaining_gap,
            "route_decision": route,
            "model_state": model_state,
            "validation": validation,
            "raw_text": str(inference.get("raw_text") or "")[:4000],
            "evidence": evidence,
            "persistence": {"saved": False, "reason": "validation_failed"},
        }

    contract = build_safe_patch_contract_from_tier1_response(
        request=request,
        response=response,
        repository_root=repository_root,
        protected_files=[],
        file_contents=minimum_context,
    )
    preview = preview_tier1_safe_patch(contract)
    evidence = build_tier1_evidence(
        request=request,
        response=response,
        patch_contract=contract,
        status="safe_patch_preview_ready",
        resource_profile="ollama_loopback",
    )
    next_gap = build_tier1_remaining_gap(request=request, response=response)
    persistence = {"saved": False, "reason": "disabled"}
    if persist:
        persistence = save_task_state(
            {
                "task_id": task_id,
                "current_state": "tier1_safe_patch_preview_ready",
                "repository_root": repository_root,
                "original_request": task_summary,
                "selected_files": list(target_files),
                "zero_cost_routing": route,
                "tier1_metadata": {
                    "request_digest": request.request_digest,
                    "response_digest": response.response_digest,
                    "patch_digest": contract.get("patch_digest", ""),
                    "preview_digest": preview.get("preview_digest", ""),
                    "evidence_id": evidence.get("evidence_id", ""),
                },
            },
            mode="memory_only",
            event_type="tier1_preview",
        )
    return {
        "ok": bool(preview.get("valid") and preview.get("operation_count", 0) >= 1),
        "state": "safe_patch_preview_ready",
        "tier0_diagnostics": diagnostics,
        "remaining_gap": remaining_gap,
        "route_decision": route,
        "model_state": model_state,
        "request": {"request_id": request.request_id, "request_digest": request.request_digest},
        "validation": validation,
        "safe_patch_contract": contract,
        "safe_patch_preview": preview,
        "evidence": evidence,
        "next_remaining_gap": next_gap,
        "persistence": persistence,
        "raw_text": str(inference.get("raw_text") or "")[:4000],
    }
