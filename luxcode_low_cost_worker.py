from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Sequence

from luxcode_low_cost_worker_contracts import (
    ALLOWED_OPERATIONS,
    AvailabilityState,
    FORBIDDEN_OPERATIONS,
    RetryState,
    WorkerRequest,
    WorkerResponse,
    build_worker_request,
    parse_worker_response,
    validate_worker_response,
)
from luxcode_safe_patch_runtime import build_patch_contract, preview_patch


DEFAULT_COST_GAP = 0.0


class LowCostProviderType(str, Enum):
    EXTERNAL = "external"
    INTERNAL = "internal"


@dataclass(frozen=True)
class LowCostProvider:
    provider_id: str
    provider_type: str
    display_name: str
    availability: str
    enabled: bool
    verified: bool
    cost_class: str
    supports_structured_output: bool
    supports_coding: bool
    supports_patch_generation: bool
    external_provider: bool
    agent_execution: bool
    emergency_only: bool = False


@dataclass(frozen=True)
class LowCostPolicy:
    provider_id: str
    provider_type: LowCostProviderType
    hard_cost_cap: float = 0.0
    estimated_input_tokens: int = 12000
    estimated_output_tokens: int = 4000
    estimated_cost: float = 0.0
    billing_allowed: bool = False
    automatic_purchase_allowed: bool = False
    automatic_upgrade_allowed: bool = False
    paid_escalation_allowed: bool = False
    approval_required: bool = True


def get_provider_catalog() -> Dict[str, LowCostProvider]:
    return {
        "direct_deepseek": LowCostProvider(
            provider_id="direct_deepseek",
            provider_type="external",
            display_name="Direct DeepSeek (provider-neutral draft path)",
            availability="unknown",
            enabled=False,
            verified=False,
            cost_class="low_cost_paid",
            supports_structured_output=True,
            supports_coding=True,
            supports_patch_generation=True,
            external_provider=True,
            agent_execution=False,
            emergency_only=False,
        ),
        "whale": LowCostProvider(
            provider_id="whale",
            provider_type="internal",
            display_name="Whale (in-repo agent lane)",
            availability="disabled",
            enabled=False,
            verified=True,
            cost_class="low_cost_internal",
            supports_structured_output=True,
            supports_coding=True,
            supports_patch_generation=True,
            external_provider=False,
            agent_execution=True,
            emergency_only=False,
        ),
        "codex": LowCostProvider(
            provider_id="codex",
            provider_type="internal",
            display_name="Codex emergency fallback",
            availability="disabled",
            enabled=False,
            verified=True,
            cost_class="emergency_only",
            supports_structured_output=True,
            supports_coding=True,
            supports_patch_generation=True,
            external_provider=False,
            agent_execution=False,
            emergency_only=True,
        ),
    }


def get_cost_policy(provider_id: str) -> LowCostPolicy:
    return LowCostPolicy(
        provider_id=provider_id,
        provider_type=LowCostProviderType.EXTERNAL if "deepseek" in provider_id else LowCostProviderType.INTERNAL,
    )


def enforce_cost_policy(policy: LowCostPolicy) -> None:
    if policy.hard_cost_cap < 0:
        raise PermissionError("hard_cost_cap must be non-negative")
    if policy.estimated_cost > policy.hard_cost_cap:
        raise PermissionError("estimated_cost exceeds hard_cost_cap")
    if policy.billing_allowed:
        raise PermissionError("billing must stay disabled")
    if policy.automatic_purchase_allowed:
        raise PermissionError("automatic_purchase_disabled")
    if policy.automatic_upgrade_allowed:
        raise PermissionError("automatic_upgrade_disabled")
    if policy.paid_escalation_allowed:
        raise PermissionError("paid_escalation_disabled")


def build_low_cost_request_from_tier0(
    *,
    request_id: str,
    task_id: str,
    task_summary: str,
    tier0_diagnostics: Dict[str, Any],
    target_files: Sequence[str],
    target_symbols: Sequence[str],
    provider_id: str = "whale",
    model_id: str = "low_cost_default",
    minimum_context: Dict[str, str] | None = None,
    acceptance_criteria: Sequence[str] | None = None,
) -> WorkerRequest:
    gap = tier0_diagnostics.get("remaining_gap") or {}
    if isinstance(gap, dict):
        remaining_gap = str(gap.get("remaining_gap", "") or "")
        completed_scope = list(gap.get("completed_scope") or [])
        failed_attempt_fingerprints = list(gap.get("failed_attempt_fingerprints") or [])
        required_scope = list(gap.get("required_capabilities") or [])
    else:
        remaining_gap = ""
        completed_scope = []
        failed_attempt_fingerprints = []
        required_scope = []

    context_payload = minimum_context or {}
    acceptance = list(acceptance_criteria or ["local-only", "approval-gated", "safe patch", "rollback"])
    return build_worker_request(
        request_id=request_id,
        task_id=task_id,
        provider_id=provider_id,
        model_id=model_id,
        task_class="small_code_fix",
        task_summary=task_summary,
        remaining_gap=remaining_gap,
        target_files=list(target_files),
        target_symbols=list(target_symbols),
        minimum_context=context_payload,
        completed_scope=completed_scope,
        failed_attempt_fingerprints=failed_attempt_fingerprints,
        required_output_format="structured_json_v1",
        risk_level="low",
        permission_mode="preview_only",
        maximum_input_tokens=12000 + len(required_scope) * 25,
        maximum_output_tokens=4000,
        maximum_cost=DEFAULT_COST_GAP,
        timeout_seconds=60,
        acceptance_criteria=acceptance,
    )


def calculate_retry_state(
    *,
    current_state: RetryState,
    failure_kind: str,
    similar_failure_count: int,
    availability: AvailabilityState,
) -> tuple[RetryState, bool]:
    if current_state == RetryState.BLOCKED:
        return RetryState.BLOCKED, False
    if availability == AvailabilityState.AUTHENTICATION_FAILED:
        return RetryState.BLOCKED, False
    if availability in {
        AvailabilityState.QUOTA_EXHAUSTED,
        AvailabilityState.RATE_LIMITED,
        AvailabilityState.TEMPORARILY_UNAVAILABLE,
        AvailabilityState.DISABLED,
    }:
        return RetryState.FALLBACK_REQUIRED, True
    if failure_kind == "invalid_json":
        if current_state in {RetryState.NOT_STARTED, RetryState.FIRST_ATTEMPT}:
            return RetryState.FORMAT_REPAIR, True
        return RetryState.BLOCKED, False
    if failure_kind == "missing_context":
        if current_state == RetryState.FIRST_ATTEMPT:
            return RetryState.CONTEXT_REPAIR, True
        return RetryState.BLOCKED, False
    if failure_kind in {"same_patch", "duplicate_patch"}:
        return RetryState.APPROACH_CHANGE, True
    if similar_failure_count >= 3:
        return RetryState.FALLBACK_REQUIRED, True
    if failure_kind == "timeout":
        return RetryState.FIRST_ATTEMPT, True
    return RetryState.BLOCKED, False


def _convert_operation(op: Any) -> Dict[str, Any]:
    return {
        "operation_id": str(op.operation_id),
        "operation_type": str(op.operation_type),
        "file_path": op.file_path,
        "expected_occurrences": int(op.expected_occurrences or 1),
        "anchor_text": str(op.anchor_text or ""),
        "old_text": str(op.old_text or ""),
        "new_text": str(op.new_text or ""),
        "reason": str(op.reason or ""),
        "confidence": float(op.confidence or 0.0),
    }


def build_safe_patch_contract_from_response(
    request: WorkerRequest,
    response: WorkerResponse,
    *,
    repository_root: str,
    repository_head: str = "",
    protected_files: Sequence[str] | None = None,
    expected_working_tree_clean: bool = True,
    file_contents: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    validate_result = validate_worker_response(
        request=request,
        response=response,
        known_files=set(request.target_files),
        known_symbols=set(request.target_symbols),
        protected_files=set(protected_files or []),
        file_contents=file_contents or {file: "" for file in request.target_files},
    )
    if not validate_result.valid:
        raise ValueError("worker response failed validation")

    allowed_files = sorted(set(request.target_files + response.target_files))
    wrapper = build_patch_contract(
        task_id=request.request_id,
        repository_root=repository_root,
        patch_title="low_cost_worker_draft",
        patch_summary=response.analysis_summary,
        target_files=allowed_files,
        operations=[_convert_operation(op) for op in response.patch_operations],
        allowed_files=allowed_files,
        protected_files=sorted(set(protected_files or [])),
        risk_level=request.risk_level,
        permission_mode="approval_required" if request.permission_mode == "preview_only" else request.permission_mode,
        expected_repository_head=repository_head,
        expected_working_tree_clean=expected_working_tree_clean,
    )
    if not wrapper.get("ok", False):
        raise ValueError(wrapper.get("error", "invalid safe patch contract"))
    contract = dict(wrapper.get("patch_contract") or {})
    contract["ok"] = True
    return contract


def safe_patch_preview(contract: Dict[str, Any]) -> Dict[str, Any]:
    return preview_patch(contract)


def build_signature_bundle(*, request: WorkerRequest, response: WorkerResponse) -> Dict[str, str]:
    return {
        "request_digest": request.request_digest,
        "response_digest": response.response_digest,
        "request_signature": hashlib.sha256(f"{request.request_id}:{request.task_id}".encode("utf-8")).hexdigest(),
        "response_signature": hashlib.sha256(response.response_digest.encode("utf-8")).hexdigest(),
    }
