
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from luxcode_free_cloud_worker import (
    CANONICAL_ENGINE_ID,
    OPENROUTER_PROVIDER_ID,
    PRIMARY_MODEL_ID,
    SCHEMA_SAFE_FALLBACK_MODEL_ID,
    TRANSIENT_DEFER_REASONS,
    FreeCloudPolicy,
    build_deferred_retry_decision,
    build_free_cloud_request,
    build_free_cloud_result,
    evaluate_free_cloud_gates,
    execute_openrouter_chat_completion,
    read_openrouter_api_key,
    redact_secret,
    select_next_free_cloud_model,
)


FREE_CLOUD_BRIDGE_VERSION = "luxcode_free_cloud_task_bridge_v1"
FREE_CLOUD_PRIMARY_MODEL_ID = PRIMARY_MODEL_ID
MAX_TARGET_FILES = 4
MAX_FILE_BYTES = 2_000_000
MAX_MODEL_ATTEMPTS = 2
FORBIDDEN_TEXT_HINTS = (
    "git ",
    "curl ",
    "wget ",
    "powershell",
    "cmd /c ",
    "bash ",
    "rm -rf",
    "http://",
    "https://",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _stable_digest(value: Any, prefix: str) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:24]}"


def build_free_cloud_runtime_configuration(
    environ: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    env = dict(os.environ if environ is None else environ)
    key = read_openrouter_api_key(env)
    enabled = _truthy(env.get("LUXCODE_OPENROUTER_ENABLED"))
    model_access_verified = _truthy(env.get("LUXCODE_OPENROUTER_MODEL_ACCESS_VERIFIED"))
    free_tier_confirmed = _truthy(env.get("LUXCODE_OPENROUTER_FREE_TIER_CONFIRMED"))
    quota_state = str(env.get("LUXCODE_OPENROUTER_QUOTA_STATE") or "unknown").strip().lower()

    policy = FreeCloudPolicy(
        enabled=enabled,
        verified=enabled and model_access_verified and bool(key.get("api_key_present")),
        transport_enabled=enabled and _truthy(
            env.get("LUXCODE_OPENROUTER_TRANSPORT_ENABLED", "1")
        ),
        real_requests_enabled=enabled and _truthy(
            env.get("LUXCODE_OPENROUTER_REAL_REQUESTS")
        ),
        network_allowed=enabled and _truthy(
            env.get("LUXCODE_OPENROUTER_NETWORK_ALLOWED")
        ),
        free_tier_confirmed=enabled and free_tier_confirmed,
        billing_allowed=False,
        paid_fallback_allowed=False,
        maximum_model_attempts=MAX_MODEL_ATTEMPTS,
    )
    gate = evaluate_free_cloud_gates(policy)
    return {
        "bridge_version": FREE_CLOUD_BRIDGE_VERSION,
        "policy": policy,
        "gate": gate,
        "api_key_present": bool(key.get("api_key_present")),
        "selected_key_name": "OPENROUTER_API_KEY" if key.get("api_key_present") else None,
        "provider_health": (
            "healthy"
            if quota_state in {"available", "quota_low"}
            else quota_state
        ),
        "quota_state": quota_state,
        "free_tier_confirmed": free_tier_confirmed,
        "billing_allowed": False,
        "paid_fallback_allowed": False,
        "secret_persisted": False,
        "models": [
            PRIMARY_MODEL_ID,
            SCHEMA_SAFE_FALLBACK_MODEL_ID,
        ],
    }


def _safe_repository_files(
    repository_root: str,
    target_files: Sequence[str],
    minimum_context: Dict[str, str],
) -> tuple[list[str], Dict[str, str], Dict[str, str]]:
    root = Path(repository_root).expanduser().resolve()
    safe_targets: list[str] = []
    exact_contents: Dict[str, str] = {}
    hashes: Dict[str, str] = {}

    for raw in target_files:
        rel = str(raw or "").replace("\\", "/").strip()
        if (
            not rel
            or rel.startswith(("/", "../"))
            or ".." in Path(rel).parts
            or rel in safe_targets
        ):
            continue
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size > MAX_FILE_BYTES
        ):
            continue
        data = path.read_bytes()
        exact = data.decode("utf-8", errors="replace")
        safe_targets.append(rel)
        exact_contents[rel] = exact
        hashes[rel] = hashlib.sha256(data).hexdigest()
        if len(safe_targets) >= MAX_TARGET_FILES:
            break

    bounded_context = {
        rel: str(minimum_context.get(rel) or exact_contents[rel])[:12000]
        for rel in safe_targets
    }
    return safe_targets, bounded_context, hashes


def _strict_patch_steps(
    *,
    repository_root: str,
    target_files: Sequence[str],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    root = Path(repository_root).expanduser().resolve()
    allowed = set(target_files)
    operations = result.get("patch_operations", [])
    if not isinstance(operations, list) or not operations:
        return {
            "ok": False,
            "state": "no_patch_operations",
            "issues": ["no_patch_operations"],
        }

    steps: list[Dict[str, Any]] = []
    files_to_modify: list[str] = []
    expected_hashes: Dict[str, str] = {}
    issues: list[str] = []

    for index, item in enumerate(operations[:8], 1):
        if not isinstance(item, dict):
            issues.append(f"operation_{index}_not_object")
            continue
        operation_type = str(item.get("operation_type") or "")
        rel = str(item.get("file_path") or "").replace("\\", "/").strip()
        old_text = str(item.get("old_text") or "")
        new_text = str(item.get("new_text") or "")
        try:
            expected_occurrences = int(item.get("expected_occurrences", 1) or 1)
        except (TypeError, ValueError):
            expected_occurrences = -1

        if operation_type != "replace_text":
            issues.append(f"operation_{index}_unsupported_type")
            continue
        if not rel or rel not in allowed or rel.startswith(("/", "../")) or ".." in Path(rel).parts:
            issues.append(f"operation_{index}_scope_violation")
            continue
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            issues.append(f"operation_{index}_path_escape")
            continue
        if not path.is_file() or path.is_symlink():
            issues.append(f"operation_{index}_missing_file")
            continue
        if not old_text or expected_occurrences <= 0:
            issues.append(f"operation_{index}_missing_exact_anchor")
            continue

        actual_text = path.read_text(encoding="utf-8", errors="replace")
        if actual_text.count(old_text) != expected_occurrences:
            issues.append(f"operation_{index}_occurrence_mismatch")
            continue

        combined = f"{old_text}\n{new_text}".lower()
        if any(marker in combined for marker in FORBIDDEN_TEXT_HINTS):
            issues.append(f"operation_{index}_forbidden_instruction")
            continue

        if rel not in files_to_modify:
            files_to_modify.append(rel)
            expected_hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        steps.append(
            {
                "target_file": rel,
                "change_type": "replace_exact",
                "expected_original_text": old_text,
                "replacement_text": new_text,
                "purpose": str(
                    item.get("reason")
                    or "OpenRouter free-model safe patch preview"
                ),
                "validation_after_change": [
                    str(value)
                    for value in result.get("validation_recommendations", [])
                    if str(value).strip()
                ],
            }
        )

    if issues:
        return {
            "ok": False,
            "state": "patch_validation_failed",
            "issues": issues,
        }
    if not steps:
        return {
            "ok": False,
            "state": "no_safe_patch_steps",
            "issues": ["no_safe_patch_steps"],
        }
    return {
        "ok": True,
        "state": "free_cloud_safe_patch_preview_ready",
        "patch_steps": steps,
        "files_to_modify": files_to_modify,
        "expected_file_hashes": expected_hashes,
    }


def _failure_result(
    *,
    request: Dict[str, Any],
    failure_category: str,
    remaining_gap: Any,
) -> Dict[str, Any]:
    status = (
        "provider_unavailable"
        if failure_category in {"provider_unavailable", "rate_limited", "timeout"}
        else "schema_invalid"
        if failure_category in {"schema_invalid", "empty_response"}
        else "blocked"
    )
    return build_free_cloud_result(
        request=request,
        status=status,
        analysis_summary=failure_category,
        remaining_gap=remaining_gap,
        failure_category=failure_category,
    )


def execute_free_cloud_task_bridge(
    *,
    task_id: str,
    repository_root: str,
    task_summary: str,
    target_files: Sequence[str],
    target_symbols: Sequence[str],
    minimum_context: Dict[str, str],
    previous_engine_state: str = "",
    environ: Mapping[str, str] | None = None,
    http_call=None,
) -> Dict[str, Any]:
    started = time.perf_counter()
    env = dict(os.environ if environ is None else environ)
    runtime = build_free_cloud_runtime_configuration(env)
    safe_targets, bounded_context, original_hashes = _safe_repository_files(
        repository_root,
        target_files,
        minimum_context,
    )
    base = {
        "engine_id": CANONICAL_ENGINE_ID,
        "provider_id": OPENROUTER_PROVIDER_ID,
        "runtime_id": "openrouter_chat_completions",
        "external_api_used": False,
        "file_write_performed": False,
        "local_only": False,
        "original_file_hashes": original_hashes,
        "runtime": {
            key: value
            for key, value in runtime.items()
            if key != "policy"
        },
        "gate": runtime["gate"],
    }

    if not safe_targets:
        return {
            **base,
            "ok": False,
            "state": "free_cloud_context_missing",
            "error": "No safe target file was available for OpenRouter.",
            "model_attempts": [],
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
    if not runtime["gate"].get("allowed"):
        return {
            **base,
            "ok": False,
            "state": "free_cloud_gate_blocked",
            "error": ",".join(runtime["gate"].get("blockers", [])),
            "model_attempts": [],
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }

    initial_gap: Any = {
        "remaining_gap": "tier3_free_cloud_patch_draft_required",
        "previous_engine_state": previous_engine_state,
    }
    remaining_gap = initial_gap
    completed_scope = ["tier0_deterministic", "tier1_local_worker", "free_gemini"]
    previous_result: Dict[str, Any] | None = None
    history: list[Dict[str, Any]] = []
    seen_request_digests: set[str] = set()
    total_usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "reasoning_tokens": 0,
        "cost": 0.0,
    }
    external_api_used = False
    final_state = "free_cloud_rejected"
    final_error = ""
    final_result: Dict[str, Any] = {}
    final_model = ""

    for _ in range(MAX_MODEL_ATTEMPTS):
        selection = select_next_free_cloud_model(
            previous_result=previous_result,
            attempt_history=history,
            remaining_gap=remaining_gap,
        )
        if not selection.get("selected"):
            final_state = str(selection.get("reason") or "fallback_not_selected")
            break

        model_id = str(selection.get("model_id") or PRIMARY_MODEL_ID)
        request_result = build_free_cloud_request(
            task_id=task_id,
            session_id=f"{task_id}-free-cloud",
            model_id=model_id,
            attempt_number=int(selection.get("attempt_number") or len(history) + 1),
            selection_reason=str(selection.get("reason") or ""),
            remaining_gap=remaining_gap,
            completed_scope=completed_scope,
            minimum_context=bounded_context,
            target_files=safe_targets,
            target_symbols=list(target_symbols),
            seen_request_digests=seen_request_digests,
        )
        if not request_result.get("ok"):
            final_state = str(request_result.get("reason") or "request_rejected")
            break

        request = request_result["request"]
        transport = execute_openrouter_chat_completion(
            request=request,
            policy=runtime["policy"],
            environ=env,
            http_call=http_call,
            live_execution_enabled=True,
            timeout_seconds=int(request.get("timeout_seconds") or 60),
        )
        external_api_used = external_api_used or bool(transport.get("http_attempts"))
        usage = transport.get("usage_metadata", {})
        if isinstance(usage, dict):
            for key in ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens"):
                total_usage[key] += int(usage.get(key, 0) or 0)
            total_usage["cost"] += float(usage.get("cost", 0.0) or 0.0)

        parsed = transport.get("result") if isinstance(transport.get("result"), dict) else {}
        attempt_record = {
            "model_id": model_id,
            "selection_reason": selection.get("reason"),
            "ok": bool(transport.get("ok")),
            "status": str(transport.get("status") or ""),
            "failure_reason": str(transport.get("failure_reason") or ""),
            "http_attempts": int(transport.get("http_attempts", 0) or 0),
            "structured_result_valid": bool(transport.get("structured_result_valid")),
            "usage_metadata": redact_secret(usage if isinstance(usage, dict) else {}),
        }

        if total_usage["cost"] > 0:
            history.append({"selection": selection, "request": request, "result": parsed, "transport": attempt_record})
            final_state = "reported_nonzero_cost"
            final_error = "OpenRouter reported a non-zero cost; the result was rejected."
            final_result = parsed
            final_model = model_id
            break

        if transport.get("ok") and parsed:
            strict = _strict_patch_steps(
                repository_root=repository_root,
                target_files=safe_targets,
                result=parsed,
            )
            attempt_record["patch_validation_state"] = strict.get("state")
            history.append({"selection": selection, "request": request, "result": parsed, "transport": attempt_record})
            if strict.get("ok"):
                duration_ms = int((time.perf_counter() - started) * 1000)
                evidence_payload = {
                    "task_id": task_id,
                    "engine_id": CANONICAL_ENGINE_ID,
                    "provider_id": OPENROUTER_PROVIDER_ID,
                    "selected_model": model_id,
                    "models_attempted": [
                        item["transport"]["model_id"]
                        for item in history
                    ],
                    "result_digest": parsed.get("result_digest", ""),
                    "files_to_modify": strict.get("files_to_modify", []),
                    "external_api_used": external_api_used,
                    "reported_cost": total_usage["cost"],
                    "file_write_performed": False,
                }
                evidence = {
                    **evidence_payload,
                    "evidence_digest": _stable_digest(
                        evidence_payload,
                        "free-cloud-evidence",
                    ),
                }
                return {
                    **base,
                    **strict,
                    "ok": True,
                    "state": "free_cloud_safe_patch_preview_ready",
                    "model_id": model_id,
                    "selected_model": model_id,
                    "model_response": parsed,
                    "model_attempts": [
                        redact_secret(item["transport"])
                        for item in history
                    ],
                    "token_usage": total_usage,
                    "provider_cost": "0.0_free_models_only",
                    "reported_cost": total_usage["cost"],
                    "evidence": evidence,
                    "external_api_used": external_api_used,
                    "duration_ms": duration_ms,
                    "approval_required": True,
                    "can_apply_now": False,
                    "paid_fallback_allowed": False,
                }

            previous_result = build_free_cloud_result(
                request=request,
                status="schema_invalid",
                analysis_summary="strict patch validation failed",
                remaining_gap=remaining_gap,
                failure_category="schema_invalid",
            )
            final_state = str(strict.get("state") or "patch_validation_failed")
            final_error = ",".join(str(item) for item in strict.get("issues", []))
            final_result = parsed
            final_model = model_id
            remaining_gap = previous_result.get("remaining_gap") or remaining_gap
            continue

        failure_category = str(
            transport.get("failure_reason")
            or transport.get("status")
            or "provider_unavailable"
        )
        synthetic = _failure_result(
            request=request,
            failure_category=failure_category,
            remaining_gap=remaining_gap,
        )
        history.append({"selection": selection, "request": request, "result": synthetic, "transport": attempt_record})
        previous_result = synthetic
        remaining_gap = synthetic.get("remaining_gap") or remaining_gap
        final_state = failure_category
        final_error = str(
            transport.get("provider_message")
            or transport.get("failure_reason")
            or ""
        )
        final_result = synthetic
        final_model = model_id

    duration_ms = int((time.perf_counter() - started) * 1000)
    deferred = build_deferred_retry_decision(
        reason=final_state if final_state in TRANSIENT_DEFER_REASONS else "",
        model_id=final_model,
        remaining_gap=remaining_gap,
        completed_scope=completed_scope,
    )
    evidence_payload = {
        "task_id": task_id,
        "engine_id": CANONICAL_ENGINE_ID,
        "provider_id": OPENROUTER_PROVIDER_ID,
        "selected_model": final_model,
        "models_attempted": [
            item["transport"]["model_id"]
            for item in history
        ],
        "state": final_state,
        "external_api_used": external_api_used,
        "reported_cost": total_usage["cost"],
        "file_write_performed": False,
    }
    return {
        **base,
        "ok": False,
        "state": final_state,
        "error": redact_secret(final_error),
        "model_id": final_model or PRIMARY_MODEL_ID,
        "selected_model": final_model or PRIMARY_MODEL_ID,
        "model_response": final_result,
        "model_attempts": [
            redact_secret(item["transport"])
            for item in history
        ],
        "token_usage": total_usage,
        "provider_cost": "0.0_free_models_only",
        "reported_cost": total_usage["cost"],
        "evidence": {
            **evidence_payload,
            "evidence_digest": _stable_digest(
                evidence_payload,
                "free-cloud-evidence",
            ),
        },
        "external_api_used": external_api_used,
        "duration_ms": duration_ms,
        "external_service_deferred": bool(
            deferred.get("external_service_deferred")
        ),
        "deferred_retry": deferred,
        "approval_required": True,
        "can_apply_now": False,
        "paid_fallback_allowed": False,
    }
