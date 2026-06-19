from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
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
    context = {key: value for key, value in request.minimum_context.items() if not key.startswith("_")}
    schema_example = {
        "response_id": "rsp-local-unique",
        "request_id": request.request_id,
        "status": "completed",
        "analysis_summary": "Short explanation of the exact proposed change.",
        "completed_scope": ["tier1_local_patch_draft"],
        "remaining_gap": "safe_patch_preview_ready",
        "target_files": list(request.target_files),
        "target_symbols": list(request.target_symbols),
        "patch_operations": [
            {
                "operation_id": "op-1",
                "operation_type": "replace_text",
                "file_path": request.target_files[0] if request.target_files else "",
                "anchor_text": "",
                "old_text": "exact text copied from minimum_context_json",
                "new_text": "replacement text",
                "expected_occurrences": 1,
                "reason": "why this exact edit is required",
                "confidence": 0.9,
            }
        ],
        "validation_recommendations": ["py_compile", "targeted test"],
        "assumptions": [],
        "uncertainties": [],
        "risk_flags": [],
        "unsupported_requests": [],
        "model_metadata": {
            "runtime_id": TIER1_OLLAMA_RUNTIME_ID,
            "local_only": True,
            "external_api_used": False,
        },
    }
    return (
        "Return exactly one JSON object. Do not use markdown or code fences.\n"
        "You are the local Tier-1 coding model for LUXCODE. Produce only a SAFE PATCH PREVIEW; "
        "never claim that a file was written, a command was run, or a patch was applied.\n"
        f"request_id: {request.request_id}\n"
        f"task_summary: {request.task_summary}\n"
        f"remaining_gap: {request.remaining_gap}\n"
        f"allowed_target_files_json: {json.dumps(request.target_files, ensure_ascii=False)}\n"
        f"allowed_target_symbols_json: {json.dumps(request.target_symbols, ensure_ascii=False)}\n"
        f"minimum_context_json: {json.dumps(context, ensure_ascii=False, sort_keys=True)}\n"
        "Rules:\n"
        "1. Use only files listed in allowed_target_files_json.\n"
        "2. Use only replace_text operations in this phase.\n"
        "3. old_text must be copied exactly from minimum_context_json and expected_occurrences must be 1.\n"
        "4. Never invent a file, symbol, function, line, API, or repository fact.\n"
        "5. Return at most 3 patch operations. Keep edits minimal.\n"
        "6. If exact safe replacement text cannot be proven from the supplied context, return status "
        "needs_more_context, an empty patch_operations list, and explain the missing context in remaining_gap.\n"
        "7. target_files and target_symbols in the response must be subsets of the allowed lists.\n"
        "8. status must be completed, partial, needs_more_context, or blocked.\n"
        "Required response shape example (replace example values with real grounded values):\n"
        f"{json.dumps(schema_example, ensure_ascii=False, sort_keys=True)}"
    )

def _extract_model_text(data: Dict[str, Any]) -> str:
    text = str(data.get("response") or "")
    if text:
        return text.strip()
    message = data.get("message")
    if isinstance(message, dict):
        return str(message.get("content") or "").strip()
    return ""


def _normalize_ollama_response_payload(
    raw_text: str,
    *,
    request: WorkerRequest,
    ollama_data: Dict[str, Any],
) -> str:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_json") from exc
    if not isinstance(data, dict):
        raise ValueError("response must be object")

    operations = data.get("patch_operations")
    if not isinstance(operations, list):
        operations = []
        data["patch_operations"] = operations

    operation_files = [
        str(item.get("file_path") or "")
        for item in operations
        if isinstance(item, dict) and str(item.get("file_path") or "")
    ]
    data.setdefault("response_id", _stable_digest({"request": request.request_id, "text": raw_text}, prefix="ollama-rsp"))
    data["request_id"] = request.request_id
    data["provider_id"] = request.provider_id
    data["model_id"] = request.model_id
    data.setdefault("status", "completed" if operations else "needs_more_context")
    data.setdefault("analysis_summary", "Local model returned no analysis summary.")
    data.setdefault("completed_scope", ["tier1_local_patch_draft"] if operations else [])
    data.setdefault("remaining_gap", "safe_patch_preview_ready" if operations else "more exact source context required")
    data.setdefault("target_files", sorted(set(operation_files)))
    data.setdefault("target_symbols", [])
    data.setdefault("validation_recommendations", ["py_compile", "targeted test"] if operations else [])
    data.setdefault("assumptions", [])
    data.setdefault("uncertainties", [])
    data.setdefault("risk_flags", [])
    data.setdefault("scope_violations", [])
    data.setdefault("unsupported_requests", [])
    data["usage_metadata"] = {
        "input_tokens": int(ollama_data.get("prompt_eval_count") or 0),
        "output_tokens": int(ollama_data.get("eval_count") or 0),
        "estimated_cost": 0.0,
    }
    metadata = data.get("model_metadata") if isinstance(data.get("model_metadata"), dict) else {}
    metadata.update(
        {
            "runtime_id": TIER1_OLLAMA_RUNTIME_ID,
            "local_only": True,
            "external_api_used": False,
            "done_reason": str(ollama_data.get("done_reason") or ""),
        }
    )
    data["model_metadata"] = metadata
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def run_ollama_tier1_inference(
    *,
    request: WorkerRequest,
    endpoint: str = TIER1_OLLAMA_ENDPOINT,
    model_id: str = TIER1_OLLAMA_MODEL_ID,
    timeout_seconds: int = 90,
    repair_attempt: bool = False,
) -> Dict[str, Any]:
    started = time.perf_counter()
    model = check_ollama_model(model_id, endpoint=endpoint, timeout_seconds=5)
    if not model.get("ok"):
        return {
            "ok": False,
            "state": model.get("state", "runtime_unavailable"),
            "error": model.get("error", ""),
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
    if not model.get("model_available"):
        return {
            "ok": False,
            "state": "model_missing",
            "model_id": model_id,
            "models": model.get("models", []),
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
    prompt = _tier1_prompt(request)
    if repair_attempt:
        prompt += (
            "\nThe previous output was invalid. Return only one valid JSON object matching the exact schema. "
            "Do not add commentary."
        )
    payload = {
        "model": model_id,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "num_predict": 1400},
    }
    result = _ollama_json_request(endpoint, "/api/generate", payload, timeout_seconds=timeout_seconds)
    if not result.get("ok"):
        return {**result, "duration_ms": int((time.perf_counter() - started) * 1000)}
    ollama_data = result.get("data", {})
    text = _extract_model_text(ollama_data)
    if not text:
        return {
            "ok": False,
            "state": "empty_response",
            "raw": ollama_data,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
    try:
        normalized = _normalize_ollama_response_payload(text, request=request, ollama_data=ollama_data)
        response = parse_tier1_response(normalized, request=request, runtime_id=TIER1_OLLAMA_RUNTIME_ID)
    except ValueError as exc:
        return {
            "ok": False,
            "state": "invalid_json",
            "error": str(exc),
            "raw_text": text[:4000],
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
    return {
        "ok": True,
        "state": "response_parsed",
        "response": response,
        "raw_text": normalized,
        "model_id": model_id,
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }

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


def _safe_repository_file_contents(
    repository_root: str,
    target_files: Sequence[str],
    *,
    max_file_bytes: int = 2_000_000,
) -> Dict[str, str]:
    root = Path(repository_root).resolve()
    contents: Dict[str, str] = {}
    for raw in target_files:
        rel = str(raw or "").replace("\\", "/").strip()
        if not rel or rel.startswith(("/", "../")) or ".." in Path(rel).parts:
            continue
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if not path.is_file() or path.is_symlink() or path.stat().st_size > max_file_bytes:
            continue
        contents[rel] = path.read_text(encoding="utf-8", errors="replace")
    return contents


def _controlled_patch_steps_from_response(response: WorkerResponse) -> list[Dict[str, Any]]:
    steps: list[Dict[str, Any]] = []
    for operation in response.patch_operations:
        if operation.operation_type != "replace_text":
            continue
        steps.append(
            {
                "target_file": operation.file_path,
                "change_type": "replace_exact",
                "expected_original_text": operation.old_text,
                "replacement_text": operation.new_text,
                "purpose": operation.reason or "Ollama local safe patch preview",
                "validation_after_change": list(response.validation_recommendations),
            }
        )
    return steps


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    tier0_diagnostics: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    from luxcode_task_persistence import save_task_state
    from luxcode_tier0_deterministic_executor import run_tier0_diagnostics
    from luxcode_zero_cost_execution_router import route_zero_cost_task

    safe_targets = [str(item).replace("\\", "/").strip() for item in target_files if str(item).strip()]
    exact_contents = _safe_repository_file_contents(repository_root, safe_targets)
    safe_targets = [item for item in safe_targets if item in exact_contents]
    if not safe_targets:
        fingerprint = _stable_digest({"task_id": task_id, "reason": "no_safe_target_files"}, prefix="tier1-failure")
        return {
            "ok": False,
            "state": "tier1_context_missing",
            "error": "No safe existing target file was available for local model validation.",
            "evidence": _fallback_evidence(
                task_id=task_id,
                model_id=model_id,
                state="tier1_context_missing",
                summary="No safe existing target file was available",
                target_files=target_files,
                failure_fingerprint=fingerprint,
            ),
            "persistence": {"saved": False, "reason": "context_missing"},
        }

    diagnostics = dict(tier0_diagnostics) if isinstance(tier0_diagnostics, dict) else run_tier0_diagnostics(
        repository_root, task_summary, list(safe_targets)
    )
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
        selected_files=list(safe_targets),
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
            target_files=safe_targets,
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

    bounded_context = {
        key: str(value)[:12000]
        for key, value in minimum_context.items()
        if key in safe_targets and str(value).strip()
    }
    for key in safe_targets:
        bounded_context.setdefault(key, exact_contents[key][:12000])

    request = build_tier1_request_from_tier0(
        request_id=_stable_digest({"task_id": task_id, "tier": 1}, prefix="tier1-req"),
        task_id=task_id,
        task_summary=task_summary,
        tier0_diagnostics=diagnostics,
        target_files=safe_targets,
        target_symbols=target_symbols,
        minimum_context=bounded_context,
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
            target_files=safe_targets,
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
    if response.response_status.value not in {"completed", "partial"} or not response.patch_operations:
        fingerprint = _stable_digest(
            {"task_id": task_id, "status": response.response_status.value, "gap": response.remaining_gap},
            prefix="tier1-failure",
        )
        evidence = _fallback_evidence(
            task_id=task_id,
            model_id=model_id,
            state="tier1_needs_more_context",
            summary=response.analysis_summary or response.remaining_gap,
            target_files=safe_targets,
            failure_fingerprint=fingerprint,
        )
        return {
            "ok": False,
            "state": "tier1_needs_more_context",
            "route_decision": route,
            "model_state": model_state,
            "analysis_summary": response.analysis_summary,
            "remaining_gap": response.remaining_gap,
            "evidence": evidence,
            "raw_text": str(inference.get("raw_text") or "")[:4000],
            "persistence": {"saved": False, "reason": "more_context_required"},
        }

    validation = validate_tier1_response(
        request=request,
        response=response,
        known_files=set(safe_targets),
        known_symbols=set(target_symbols),
        protected_files=set(),
        file_contents=exact_contents,
        failed_patch_fingerprints=set(request.failed_attempt_fingerprints),
    )
    if not validation.get("valid"):
        fingerprint = _stable_digest({"task_id": task_id, "validation": validation}, prefix="tier1-failure")
        evidence = _fallback_evidence(
            task_id=task_id,
            model_id=model_id,
            state="tier1_validation_failed",
            summary="Tier 1 response failed validation",
            target_files=safe_targets,
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

    try:
        contract = build_safe_patch_contract_from_tier1_response(
            request=request,
            response=response,
            repository_root=repository_root,
            protected_files=[],
            file_contents=exact_contents,
        )
        preview = preview_tier1_safe_patch(contract)
    except Exception as exc:
        fingerprint = _stable_digest({"task_id": task_id, "error": str(exc)}, prefix="tier1-failure")
        return {
            "ok": False,
            "state": "tier1_contract_failed",
            "error": str(exc),
            "validation": validation,
            "evidence": _fallback_evidence(
                task_id=task_id,
                model_id=model_id,
                state="tier1_contract_failed",
                summary=str(exc),
                target_files=safe_targets,
                failure_fingerprint=fingerprint,
            ),
            "persistence": {"saved": False, "reason": "contract_failed"},
        }

    patch_steps = _controlled_patch_steps_from_response(response)
    root = Path(repository_root).resolve()
    expected_hashes = {rel: _file_sha256(root / rel) for rel in safe_targets if (root / rel).is_file()}
    evidence = build_tier1_evidence(
        request=request,
        response=response,
        patch_contract=contract,
        status="safe_patch_preview_ready",
        duration_ms=int(inference.get("duration_ms") or 0),
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
                "selected_files": list(safe_targets),
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
        "ok": bool(preview.get("valid") and patch_steps),
        "state": "safe_patch_preview_ready",
        "tier0_diagnostics": diagnostics,
        "remaining_gap": remaining_gap,
        "route_decision": route,
        "model_state": model_state,
        "request": {"request_id": request.request_id, "request_digest": request.request_digest},
        "model_response": {
            "response_id": response.response_id,
            "response_status": response.response_status.value,
            "analysis_summary": response.analysis_summary,
            "completed_scope": list(response.completed_scope),
            "remaining_gap": response.remaining_gap,
            "target_files": list(response.target_files),
            "target_symbols": list(response.target_symbols),
            "validation_recommendations": list(response.validation_recommendations),
            "risk_flags": list(response.risk_flags),
            "usage_metadata": dict(response.usage_metadata),
            "response_digest": response.response_digest,
        },
        "validation": validation,
        "safe_patch_contract": contract,
        "safe_patch_preview": preview,
        "patch_steps": patch_steps,
        "expected_file_hashes": expected_hashes,
        "files_to_modify": sorted({step["target_file"] for step in patch_steps}),
        "evidence": evidence,
        "next_remaining_gap": next_gap,
        "persistence": persistence,
        "raw_text": str(inference.get("raw_text") or "")[:4000],
        "duration_ms": int(inference.get("duration_ms") or 0),
    }
