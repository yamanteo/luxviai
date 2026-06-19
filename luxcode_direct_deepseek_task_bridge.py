from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from luxcode_direct_deepseek_transport import (
    DEFAULT_MODEL_ID,
    MAX_TASK_COST_USD,
    MAX_TASK_OUTPUT_TOKENS,
    MAX_TASK_TIMEOUT_SECONDS,
    DeepSeekTransportPolicy,
    execute_direct_deepseek_handoff,
    get_deepseek_pricing_snapshot,
    redact_secret,
)


ENGINE_ID = "direct_deepseek"
PROVIDER_ID = "deepseek"
DIRECT_DEEPSEEK_MODEL_ID = DEFAULT_MODEL_ID
MAX_TARGET_FILES = 4
MAX_FILE_BYTES = 300_000
EXACT_APPROVAL_TEXT = "I APPROVE PAID DEEPSEEK"
FORBIDDEN_TEXT_HINTS = (
    ".env",
    "api_key",
    "authorization:",
    "bearer ",
    "rm -rf",
    "format c:",
    "del /s",
    "powershell -enc",
)


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def _digest(value: Any, prefix: str) -> str:
    raw = _stable_json(value).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:32]}"


def _bounded_cost(value: Any) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return MAX_TASK_COST_USD
    return max(0.0, min(amount, MAX_TASK_COST_USD))


def build_direct_deepseek_task_approval(
    *,
    task_id: str,
    repository_root: str,
    target_files: Sequence[str],
    maximum_cost_usd: float = MAX_TASK_COST_USD,
    model_id: str = DIRECT_DEEPSEEK_MODEL_ID,
) -> Dict[str, Any]:
    payload = {
        "task_id": str(task_id),
        "repository_root": str(Path(repository_root).expanduser().resolve()),
        "target_files": sorted(
            {
                str(item).replace("\\", "/").strip()
                for item in target_files
                if str(item).strip()
            }
        )[:MAX_TARGET_FILES],
        "model_id": str(model_id),
        "maximum_cost_usd": _bounded_cost(maximum_cost_usd),
        "confirmation_text": EXACT_APPROVAL_TEXT,
        "single_request_only": True,
        "automatic_purchase_allowed": False,
        "automatic_upgrade_allowed": False,
        "auto_apply_allowed": False,
    }
    payload["approval_digest"] = _digest(payload, "deepseek-approval")
    return payload


def validate_direct_deepseek_task_approval(
    *,
    approval: Mapping[str, Any] | None,
    task_id: str,
    repository_root: str,
    target_files: Sequence[str],
) -> Dict[str, Any]:
    expected = build_direct_deepseek_task_approval(
        task_id=task_id,
        repository_root=repository_root,
        target_files=target_files,
        maximum_cost_usd=(approval or {}).get(
            "maximum_cost_usd", MAX_TASK_COST_USD
        ),
        model_id=str(
            (approval or {}).get("model_id") or DIRECT_DEEPSEEK_MODEL_ID
        ),
    )
    actual_digest = str((approval or {}).get("approval_digest") or "")
    confirmation = str((approval or {}).get("confirmation_text") or "")
    approved = bool((approval or {}).get("approved"))
    blockers = []
    if not approved:
        blockers.append("task_paid_escalation_not_approved")
    if actual_digest != expected["approval_digest"]:
        blockers.append("approval_digest_mismatch")
    if confirmation != EXACT_APPROVAL_TEXT:
        blockers.append("approval_text_mismatch")
    if bool((approval or {}).get("consumed")):
        blockers.append("single_request_approval_already_consumed")
    return {
        "allowed": not blockers,
        "blockers": blockers,
        "expected": expected,
        "actual_digest": actual_digest,
    }


def build_direct_deepseek_runtime_configuration(
    environ: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    data = os.environ if environ is None else environ
    api_key = str(data.get("DEEPSEEK_API_KEY") or "")
    maximum_cost = _bounded_cost(
        data.get("LUXCODE_DEEPSEEK_MAX_COST_USD", MAX_TASK_COST_USD)
    )
    flags = {
        "engine_enabled": data.get("LUXCODE_DEEPSEEK_ENABLED") == "1",
        "transport_enabled": (
            data.get("LUXCODE_DEEPSEEK_TRANSPORT_ENABLED") == "1"
        ),
        "real_requests_enabled": (
            data.get("LUXCODE_DEEPSEEK_REAL_REQUESTS_ENABLED") == "1"
        ),
        "network_allowed": (
            data.get("LUXCODE_DEEPSEEK_NETWORK_ALLOWED") == "1"
        ),
        "billing_enabled": (
            data.get("LUXCODE_DEEPSEEK_BILLING_ENABLED") == "1"
        ),
        "model_access_verified": (
            data.get("LUXCODE_DEEPSEEK_MODEL_ACCESS_VERIFIED") == "1"
        ),
        "pricing_verified": (
            data.get("LUXCODE_DEEPSEEK_PRICING_VERIFIED") == "1"
        ),
        "account_balance_confirmed": (
            data.get("LUXCODE_DEEPSEEK_ACCOUNT_BALANCE_CONFIRMED") == "1"
        ),
        "api_key_present": bool(api_key.strip()),
    }
    blockers = [
        name
        for name, allowed in flags.items()
        if not allowed
    ]
    pricing = get_deepseek_pricing_snapshot(DIRECT_DEEPSEEK_MODEL_ID)
    if (
        pricing.cache_miss_input_per_1m is None
        or pricing.output_per_1m is None
    ):
        blockers.append("unknown_pricing")
    if maximum_cost <= 0:
        blockers.append("invalid_cost_cap")

    policy = DeepSeekTransportPolicy(
        transport_enabled=flags["transport_enabled"]
        and flags["engine_enabled"]
        and flags["network_allowed"],
        real_requests_allowed=flags["real_requests_enabled"],
        billing_allowed=flags["billing_enabled"],
        paid_escalation_allowed=False,
        automatic_purchase_allowed=False,
        automatic_upgrade_allowed=False,
        explicit_user_approval=False,
    )
    return {
        "status": "READY_FOR_TASK_APPROVAL" if not blockers else "BLOCKED",
        "blockers": sorted(set(blockers)),
        "flags": flags,
        "policy": policy,
        "api_key": api_key if api_key.strip() else None,
        "api_key_present": bool(api_key.strip()),
        "selected_key_name": "DEEPSEEK_API_KEY",
        "model_id": DIRECT_DEEPSEEK_MODEL_ID,
        "maximum_cost_usd": maximum_cost,
        "pricing_snapshot_version": pricing.version,
        "pricing": {
            "cache_hit_input_per_1m": pricing.cache_hit_input_per_1m,
            "cache_miss_input_per_1m": pricing.cache_miss_input_per_1m,
            "output_per_1m": pricing.output_per_1m,
        },
        "secret_persisted": False,
        "automatic_purchase_allowed": False,
        "automatic_upgrade_allowed": False,
        "auto_apply_allowed": False,
    }


def _safe_repository_files(
    repository_root: str,
    target_files: Sequence[str],
    minimum_context: Mapping[str, str],
) -> tuple[list[str], Dict[str, str], Dict[str, str]]:
    root = Path(repository_root).expanduser().resolve()
    safe_targets: list[str] = []
    context: Dict[str, str] = {}
    hashes: Dict[str, str] = {}

    for item in target_files:
        rel = str(item).replace("\\", "/").strip()
        if (
            not rel
            or rel.startswith(("/", "../"))
            or ".." in Path(rel).parts
            or rel in safe_targets
            or rel == ".env"
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
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        safe_targets.append(rel)
        context[rel] = str(minimum_context.get(rel) or text)[:12000]
        hashes[rel] = hashlib.sha256(raw).hexdigest()
        if len(safe_targets) >= MAX_TARGET_FILES:
            break

    return safe_targets, context, hashes


def _strict_patch_steps(
    *,
    repository_root: str,
    target_files: Sequence[str],
    contract: Mapping[str, Any],
    model_response: Mapping[str, Any],
) -> Dict[str, Any]:
    root = Path(repository_root).expanduser().resolve()
    allowed = set(target_files)
    operations = contract.get("operations", [])
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
            expected_occurrences = int(
                item.get("expected_occurrences", 1) or 1
            )
        except (TypeError, ValueError):
            expected_occurrences = -1

        if operation_type != "replace_text":
            issues.append(f"operation_{index}_unsupported_type")
            continue
        if (
            not rel
            or rel not in allowed
            or rel.startswith(("/", "../"))
            or ".." in Path(rel).parts
        ):
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
        if not old_text or expected_occurrences != 1:
            issues.append(f"operation_{index}_missing_exact_anchor")
            continue
        actual_text = path.read_text(encoding="utf-8", errors="replace")
        if actual_text.count(old_text) != 1:
            issues.append(f"operation_{index}_occurrence_mismatch")
            continue
        combined = f"{old_text}\n{new_text}".lower()
        if any(marker in combined for marker in FORBIDDEN_TEXT_HINTS):
            issues.append(f"operation_{index}_forbidden_instruction")
            continue

        if rel not in files_to_modify:
            files_to_modify.append(rel)
            expected_hashes[rel] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
        steps.append(
            {
                "target_file": rel,
                "change_type": "replace_exact",
                "expected_original_text": old_text,
                "replacement_text": new_text,
                "purpose": str(
                    item.get("reason")
                    or "Direct DeepSeek paid safe patch preview"
                ),
                "validation_after_change": [
                    str(value)
                    for value in model_response.get(
                        "validation_recommendations", []
                    )
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
        "state": "direct_deepseek_safe_patch_preview_ready",
        "patch_steps": steps,
        "files_to_modify": files_to_modify,
        "expected_file_hashes": expected_hashes,
    }


def execute_direct_deepseek_task_bridge(
    *,
    task_id: str,
    repository_root: str,
    task_summary: str,
    target_files: Sequence[str],
    target_symbols: Sequence[str],
    minimum_context: Mapping[str, str],
    previous_result: Mapping[str, Any],
    approval: Mapping[str, Any] | None,
    environ: Mapping[str, str] | None = None,
    http_call=None,
) -> Dict[str, Any]:
    started = time.perf_counter()
    runtime = build_direct_deepseek_runtime_configuration(environ)
    safe_targets, bounded_context, original_hashes = _safe_repository_files(
        repository_root,
        target_files,
        minimum_context,
    )
    approval_check = validate_direct_deepseek_task_approval(
        approval=approval,
        task_id=task_id,
        repository_root=repository_root,
        target_files=target_files,
    )
    blockers = list(runtime["blockers"]) + list(
        approval_check["blockers"]
    )
    if not bool(previous_result.get("free_tier_exhaustion_confirmed")):
        blockers.append("free_tiers_not_exhausted")

    base = {
        "engine_id": ENGINE_ID,
        "provider_id": PROVIDER_ID,
        "model_id": DIRECT_DEEPSEEK_MODEL_ID,
        "duration_ms": 0,
        "runtime": {
            "status": runtime["status"],
            "blockers": runtime["blockers"],
            "api_key_present": runtime["api_key_present"],
            "selected_key_name": runtime["selected_key_name"],
            "model_id": runtime["model_id"],
            "maximum_cost_usd": runtime["maximum_cost_usd"],
            "pricing_snapshot_version": runtime[
                "pricing_snapshot_version"
            ],
            "secret_persisted": False,
        },
        "approval": {
            "allowed": approval_check["allowed"],
            "blockers": approval_check["blockers"],
            "approval_digest": str(
                (approval or {}).get("approval_digest") or ""
            ),
            "single_request_only": True,
        },
        "external_api_used": False,
        "file_write_performed": False,
        "original_file_hashes": original_hashes,
        "automatic_purchase_allowed": False,
        "automatic_upgrade_allowed": False,
        "auto_apply_allowed": False,
        "next_candidate": "whale_manual",
    }

    if not safe_targets:
        return {
            **base,
            "ok": False,
            "state": "deepseek_context_missing",
            "blockers": ["no_safe_target_files"],
            "duration_ms": int(
                (time.perf_counter() - started) * 1000
            ),
        }
    if blockers:
        return {
            **base,
            "ok": False,
            "state": "deepseek_paid_approval_required",
            "blockers": sorted(set(blockers)),
            "duration_ms": int(
                (time.perf_counter() - started) * 1000
            ),
        }

    policy = runtime["policy"]
    policy = DeepSeekTransportPolicy(
        transport_enabled=policy.transport_enabled,
        real_requests_allowed=policy.real_requests_allowed,
        billing_allowed=policy.billing_allowed,
        paid_escalation_allowed=False,
        automatic_purchase_allowed=False,
        automatic_upgrade_allowed=False,
        explicit_user_approval=True,
    )
    handoff = execute_direct_deepseek_handoff(
        task_id=task_id,
        task_summary=task_summary,
        previous_tier="free_cloud_worker",
        previous_result={
            "completed": False,
            "remaining_gap": previous_result.get("remaining_gap")
            or {
                "remaining_gap": (
                    "tier4_direct_deepseek_patch_draft_required"
                )
            },
        },
        repository_root=repository_root,
        target_files=safe_targets,
        target_symbols=list(target_symbols),
        minimum_context=bounded_context,
        free_tier_exhaustion_confirmed=True,
        paid_escalation_approved=True,
        policy=policy,
        api_key=runtime["api_key"],
        hard_cost_cap=runtime["maximum_cost_usd"],
        max_tokens=MAX_TASK_OUTPUT_TOKENS,
        timeout_seconds=MAX_TASK_TIMEOUT_SECONDS,
        http_call=http_call,
        persist=False,
    )
    duration_ms = int((time.perf_counter() - started) * 1000)
    base["duration_ms"] = duration_ms
    base["external_api_used"] = bool(
        handoff.get("direct_deepseek_called")
    )

    if not handoff.get("ok"):
        return {
            **base,
            "ok": False,
            "state": str(
                handoff.get("state")
                or "direct_deepseek_handoff_failed"
            ),
            "blockers": list(handoff.get("blockers", [])),
            "transport": redact_secret(
                handoff.get("transport", {})
            ),
            "evidence": redact_secret(
                handoff.get("evidence", {})
            ),
            "remaining_gap": redact_secret(
                handoff.get("remaining_gap")
            ),
        }

    contract = handoff.get("safe_patch_contract", {})
    response = handoff.get("model_response", {})
    if not isinstance(contract, dict):
        contract = {}
    if not isinstance(response, dict):
        response = {}
    strict = _strict_patch_steps(
        repository_root=repository_root,
        target_files=safe_targets,
        contract=contract,
        model_response=response,
    )
    if not strict.get("ok"):
        return {
            **base,
            **strict,
            "ok": False,
            "transport": redact_secret(
                handoff.get("transport", {})
            ),
            "model_response": redact_secret(response),
            "evidence": redact_secret(
                handoff.get("evidence", {})
            ),
        }

    transport = handoff.get("transport", {})
    if not isinstance(transport, dict):
        transport = {}
    token_usage = {
        "input_tokens": int(
            transport.get("input_tokens", 0) or 0
        ),
        "output_tokens": int(
            transport.get("output_tokens", 0) or 0
        ),
    }
    actual_cost = transport.get("actual_estimated_cost")
    return {
        **base,
        **strict,
        "ok": True,
        "state": "direct_deepseek_safe_patch_preview_ready",
        "transport": redact_secret(transport),
        "model_response": redact_secret(response),
        "evidence": redact_secret(
            handoff.get("evidence", {})
        ),
        "token_usage": token_usage,
        "provider_cost": actual_cost,
        "maximum_cost_usd": runtime["maximum_cost_usd"],
        "approval_required_for_apply": True,
        "can_apply_now": False,
    }
