from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from luxcode_free_gemini_worker import (
    DEFAULT_MODEL_ID,
    ENGINE_ID,
    GeminiGatePolicy,
    choose_gemini_api_key,
    evaluate_gemini_gates,
    execute_free_gemini_handoff,
)


GEMINI_BRIDGE_VERSION = "luxcode_gemini_task_bridge_v1"
MAX_TARGET_FILES = 4
MAX_FILE_BYTES = 2_000_000
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


def _safe_model_id(value: Any) -> str:
    model = str(value or DEFAULT_MODEL_ID).strip()
    if not model or "/" in model or "\\" in model or ".." in model:
        return DEFAULT_MODEL_ID
    return model


def build_gemini_runtime_configuration(
    environ: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    env = dict(os.environ if environ is None else environ)
    key_info = choose_gemini_api_key(env)
    key_type = str(env.get("LUXCODE_GEMINI_KEY_TYPE") or "auth_key").strip().lower()
    quota_state = str(env.get("LUXCODE_GEMINI_QUOTA_STATE") or "unknown").strip().lower()
    model_access_verified = _truthy(env.get("LUXCODE_GEMINI_MODEL_ACCESS_VERIFIED"))
    enabled = _truthy(env.get("LUXCODE_GEMINI_ENABLED"))
    api_key_present = bool(key_info.get("api_key_present"))
    auth_key_confirmed = api_key_present and key_type not in {"unknown", "unrestricted_standard"}
    policy = GeminiGatePolicy(
        enabled=enabled,
        verified=enabled and model_access_verified and auth_key_confirmed,
        transport_enabled=enabled and _truthy(env.get("LUXCODE_GEMINI_TRANSPORT_ENABLED", "1")),
        real_requests_enabled=enabled and _truthy(env.get("LUXCODE_GEMINI_REAL_REQUESTS")),
        network_allowed=enabled and _truthy(env.get("LUXCODE_GEMINI_NETWORK_ALLOWED")),
        free_tier_confirmed=enabled and _truthy(env.get("LUXCODE_GEMINI_FREE_TIER_CONFIRMED")),
        billing_disabled_confirmed=enabled and _truthy(
            env.get("LUXCODE_GEMINI_BILLING_DISABLED_CONFIRMED")
        ),
        billing_allowed=False,
        quota_state=quota_state,
        quota_available=quota_state in {"available", "quota_low"},
        model_access_verified=model_access_verified,
        auth_key_confirmed=auth_key_confirmed,
        key_type=key_type,
        runtime_start_allowed=False,
        model_download_allowed=False,
    )
    gate = evaluate_gemini_gates(policy)
    return {
        "bridge_version": GEMINI_BRIDGE_VERSION,
        "policy": policy,
        "gate": gate,
        "api_key": key_info.get("api_key"),
        "selected_key_name": key_info.get("selected_key_name"),
        "api_key_present": api_key_present,
        "model_id": _safe_model_id(env.get("LUXCODE_GEMINI_MODEL_ID")),
        "provider_health": (
            "healthy"
            if quota_state in {"available", "quota_low"}
            else quota_state
        ),
        "secret_persisted": False,
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
        return {"ok": False, "state": "no_patch_operations", "issues": ["no_patch_operations"]}

    steps: list[Dict[str, Any]] = []
    files_to_modify: list[str] = []
    issues: list[str] = []
    expected_hashes: Dict[str, str] = {}

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
                "purpose": str(item.get("reason") or "Gemini free-tier safe patch preview"),
                "validation_after_change": [
                    str(value)
                    for value in result.get("validation_recommendations", [])
                    if str(value).strip()
                ],
            }
        )

    if issues:
        return {"ok": False, "state": "patch_validation_failed", "issues": issues}
    if not steps:
        return {"ok": False, "state": "no_safe_patch_steps", "issues": ["no_safe_patch_steps"]}
    return {
        "ok": True,
        "state": "gemini_safe_patch_preview_ready",
        "patch_steps": steps,
        "files_to_modify": files_to_modify,
        "expected_file_hashes": expected_hashes,
    }


def execute_gemini_task_bridge(
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
    runtime = build_gemini_runtime_configuration(environ)
    safe_targets, bounded_context, original_hashes = _safe_repository_files(
        repository_root,
        target_files,
        minimum_context,
    )
    if not safe_targets:
        return {
            "ok": False,
            "state": "gemini_context_missing",
            "error": "No safe target file was available for Gemini.",
            "transport_called": False,
            "gate": runtime["gate"],
            "runtime": {key: value for key, value in runtime.items() if key not in {"api_key", "policy"}},
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }

    handoff = execute_free_gemini_handoff(
        task_id=task_id,
        session_id=f"{task_id}-gemini",
        task_summary=task_summary,
        previous_result={
            "completed": False,
            "remaining_gap": {
                "remaining_gap": "tier2_gemini_patch_draft_required",
                "previous_engine_state": previous_engine_state,
            },
        },
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        target_files=safe_targets,
        target_symbols=list(target_symbols),
        minimum_context=bounded_context,
        policy=runtime["policy"],
        api_key=runtime["api_key"],
        provider_health=runtime["provider_health"],
        registry_overrides={
            "free_gemini": {
                "enabled": runtime["policy"].enabled,
                "verified": runtime["policy"].verified,
                "availability": "available",
            }
        },
        http_call=http_call,
        persist=False,
        model_id=runtime["model_id"],
    )
    duration_ms = int((time.perf_counter() - started) * 1000)
    evidence = handoff.get("evidence") if isinstance(handoff.get("evidence"), dict) else {}
    transport = handoff.get("transport") if isinstance(handoff.get("transport"), dict) else {}
    result = handoff.get("result") if isinstance(handoff.get("result"), dict) else {}

    base = {
        "engine_id": ENGINE_ID,
        "provider_id": "google_gemini",
        "model_id": runtime["model_id"],
        "transport_called": bool(handoff.get("transport_called")),
        "duration_ms": duration_ms,
        "evidence": evidence,
        "gate": runtime["gate"],
        "runtime": {
            "selected_key_name": runtime["selected_key_name"],
            "api_key_present": runtime["api_key_present"],
            "model_id": runtime["model_id"],
            "provider_health": runtime["provider_health"],
            "secret_persisted": False,
        },
        "handoff": {
            "stop_reason": handoff.get("stop_reason"),
            "next_candidate": handoff.get("next_candidate"),
            "session_state": handoff.get("session_state"),
        },
        "external_api_used": bool(handoff.get("transport_called")),
        "local_only": False,
        "file_write_performed": False,
        "original_file_hashes": original_hashes,
    }

    if not handoff.get("completed") or not result:
        return {
            **base,
            "ok": False,
            "state": str(handoff.get("stop_reason") or "gemini_handoff_failed"),
            "error": ",".join(str(item) for item in handoff.get("blockers", [])),
            "transport": transport,
        }

    strict = _strict_patch_steps(
        repository_root=repository_root,
        target_files=safe_targets,
        result=result,
    )
    if not strict.get("ok"):
        return {
            **base,
            **strict,
            "ok": False,
            "model_response": result,
            "transport": transport,
        }

    usage = transport.get("usage_metadata", {})
    if not isinstance(usage, dict):
        usage = {}
    token_usage = {
        "input_tokens": int(usage.get("promptTokenCount", 0) or 0),
        "output_tokens": int(usage.get("candidatesTokenCount", 0) or 0),
        "total_tokens": int(usage.get("totalTokenCount", 0) or 0),
    }
    return {
        **base,
        **strict,
        "ok": True,
        "state": "gemini_safe_patch_preview_ready",
        "model_response": result,
        "transport": transport,
        "token_usage": token_usage,
        "provider_cost": "0.0_free_tier_confirmed",
        "approval_required": True,
        "can_apply_now": False,
    }
