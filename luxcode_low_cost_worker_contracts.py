from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, List, Sequence, Set


ALLOWED_OPERATIONS: Set[str] = {"replace_text", "insert_before", "insert_after", "create_file"}
FORBIDDEN_OPERATIONS: Set[str] = {
    "delete_file",
    "rename_file",
    "binary_write",
    "chmod",
    "symlink",
    "external_path_write",
    "git_operation",
    "shell_operation",
    "network_operation",
    "package_install",
}
RESTRICTED_TEXT_HINTS = (
    "git ",
    "curl ",
    "wget ",
    "powershell",
    "bash ",
    "cmd /c ",
    "http://",
    "https://",
    "rm -rf",
)
SECRET_MARKERS = ("api_key", "apikey", "token", "password", "secret", "credential", "private_key")


class ResponseStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    NEEDS_MORE_CONTEXT = "needs_more_context"
    BLOCKED = "blocked"
    INVALID = "invalid"
    UNSAFE = "unsafe"
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"


class AvailabilityState(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    SLOW = "slow"
    STALLED = "stalled"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXHAUSTED = "quota_exhausted"
    AUTHENTICATION_FAILED = "authentication_failed"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class RetryState(str, Enum):
    NOT_STARTED = "not_started"
    FIRST_ATTEMPT = "first_attempt"
    FORMAT_REPAIR = "format_repair"
    CONTEXT_REPAIR = "context_repair"
    APPROACH_CHANGE = "approach_change"
    FALLBACK_REQUIRED = "fallback_required"
    BLOCKED = "blocked"


class ValidationResultStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True)
class WorkerCapability:
    worker_id: str
    provider_id: str
    model_id: str
    task_classes: List[str]
    supports_structured_json: bool = True
    supports_patch_generation: bool = True
    repository_access: bool = False
    terminal_access: bool = False
    git_access: bool = False
    network_access: bool = False
    external_provider: bool = False
    agent_execution: bool = False
    emergency_only: bool = False


@dataclass(frozen=True)
class CostPolicy:
    hard_cost_cap: float = 0.0
    estimated_input_tokens: int = 12000
    estimated_output_tokens: int = 4000
    estimated_cost: float = 0.0
    billing_allowed: bool = False
    automatic_purchase_allowed: bool = False
    automatic_upgrade_allowed: bool = False
    paid_escalation_allowed: bool = False
    approval_required: bool = True


@dataclass(frozen=True)
class WorkerRequest:
    request_id: str
    task_id: str
    provider_id: str
    model_id: str
    task_class: str
    task_summary: str
    remaining_gap: str
    target_files: List[str]
    target_symbols: List[str]
    minimum_context: Dict[str, str]
    completed_scope: List[str]
    failed_attempt_fingerprints: List[str]
    required_output_format: str
    acceptance_criteria: List[str]
    risk_level: str
    permission_mode: str
    maximum_input_tokens: int
    maximum_output_tokens: int
    maximum_cost: float
    timeout_seconds: int
    request_digest: str


@dataclass(frozen=True)
class PatchOperation:
    operation_id: str
    operation_type: str
    file_path: str
    anchor_text: str
    old_text: str
    new_text: str
    expected_occurrences: int
    reason: str
    confidence: float
    operation_digest: str = ""


@dataclass(frozen=True)
class WorkerResponse:
    response_id: str
    request_id: str
    provider_id: str
    model_id: str
    response_status: ResponseStatus
    analysis_summary: str
    completed_scope: List[str]
    remaining_gap: str
    target_files: List[str]
    target_symbols: List[str]
    patch_operations: List[PatchOperation]
    validation_recommendations: List[str]
    assumptions: List[str]
    uncertainties: List[str]
    risk_flags: List[str]
    scope_violations: List[str]
    unsupported_requests: List[str]
    usage_metadata: Dict[str, Any]
    response_digest: str


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    status: ValidationResultStatus
    issues: List[ValidationIssue]
    response_digest: str


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any, prefix: str = "worker") -> str:
    return f"{prefix}-{hashlib.sha256(_stable_json(value).encode('utf-8')).hexdigest()[:24]}"


def _normalize_path(path: str) -> str:
    normalized = str(path or "").replace("\\", "/").strip()
    if normalized.startswith(("../", "..\\", "\\\\", "//")):
        raise ValueError(f"unsafe target path: {path}")
    if os.path.isabs(normalized):
        raise ValueError(f"absolute path not allowed: {path}")
    if normalized == ".." or normalized.startswith("../"):
        raise ValueError(f"path traversal blocked: {path}")
    return normalized


def _reject_secret_content(value: str) -> None:
    lowered = (value or "").lower()
    if any(marker in lowered for marker in SECRET_MARKERS):
        raise ValueError("secret-like content blocked")


def _validate_requirements(value: Any, *, max_items: int = 500) -> List[str]:
    values = []
    if isinstance(value, (list, tuple, set)):
        for item in value:
            text = str(item).strip().replace("\r", "").replace("\n", " ")
            if text:
                values.append(text)
            if len(values) >= max_items:
                break
    return values


def build_worker_request(
    *,
    request_id: str,
    task_id: str,
    provider_id: str,
    model_id: str,
    task_class: str,
    task_summary: str,
    remaining_gap: str,
    target_files: Sequence[str],
    target_symbols: Sequence[str],
    minimum_context: Dict[str, str],
    completed_scope: Sequence[str],
    failed_attempt_fingerprints: Sequence[str],
    acceptance_criteria: Sequence[str],
    required_output_format: str = "structured_json_v1",
    risk_level: str = "low",
    permission_mode: str = "preview_only",
    maximum_input_tokens: int = 12000,
    maximum_output_tokens: int = 4000,
    maximum_cost: float = 0.0,
    timeout_seconds: int = 60,
) -> WorkerRequest:
    if maximum_input_tokens <= 0 or maximum_output_tokens <= 0 or timeout_seconds <= 0:
        raise ValueError("token and timeout values must be positive")
    if maximum_cost < 0:
        raise ValueError("maximum_cost cannot be negative")

    normalized_files = []
    for item in _validate_requirements(target_files):
        normalized_files.append(_normalize_path(item))
    normalized_symbols = [str(item).strip() for item in _validate_requirements(target_symbols)]
    normalized_completed = sorted({_ for _ in _validate_requirements(completed_scope)})
    failed = sorted({_ for _ in _validate_requirements(failed_attempt_fingerprints)})
    normalized_acceptance = [str(item).strip() for item in acceptance_criteria or [] if str(item).strip()]
    context = {str(key).strip(): str(value) for key, value in (minimum_context or {}).items() if str(key).strip()}

    for value in context.values():
        _reject_secret_content(value)

    if not request_id:
        raise ValueError("request_id required")
    if not task_id:
        raise ValueError("task_id required")
    if not provider_id or not model_id:
        raise ValueError("provider_id and model_id required")
    if required_output_format != "structured_json_v1":
        raise ValueError("unsupported output format")

    payload = {
        "request_id": str(request_id),
        "task_id": str(task_id),
        "provider_id": str(provider_id),
        "model_id": str(model_id),
        "task_class": str(task_class),
        "task_summary": str(task_summary),
        "remaining_gap": str(remaining_gap),
        "target_files": sorted(set(normalized_files)),
        "target_symbols": sorted(set(normalized_symbols)),
        "minimum_context": context,
        "completed_scope": normalized_completed,
        "failed_attempt_fingerprints": failed,
        "required_output_format": required_output_format,
        "acceptance_criteria": normalized_acceptance,
        "risk_level": str(risk_level),
        "permission_mode": str(permission_mode),
        "maximum_input_tokens": int(maximum_input_tokens),
        "maximum_output_tokens": int(maximum_output_tokens),
        "maximum_cost": float(maximum_cost),
        "timeout_seconds": int(timeout_seconds),
    }
    return WorkerRequest(request_digest=_digest(payload, prefix="worker-req"), **payload)


def parse_worker_response(raw: str) -> WorkerResponse:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid_json:{exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("response must be object")

    required = {
        "response_id",
        "request_id",
        "provider_id",
        "model_id",
        "response_status",
        "analysis_summary",
        "completed_scope",
        "remaining_gap",
        "target_files",
        "target_symbols",
        "patch_operations",
        "validation_recommendations",
        "assumptions",
        "uncertainties",
        "risk_flags",
        "scope_violations",
        "unsupported_requests",
        "usage_metadata",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"missing_keys:{','.join(sorted(missing))}")

    raw_ops = data.get("patch_operations", [])
    if not isinstance(raw_ops, list):
        raise ValueError("patch_operations must be list")

    operations: List[PatchOperation] = []
    for item in raw_ops:
        if not isinstance(item, dict):
            raise ValueError("patch operation must be object")
        operation_id = str(item.get("operation_id") or "")
        operation_type = str(item.get("operation_type") or "")
        file_path = _normalize_path(str(item.get("file_path") or ""))
        if operation_type not in ALLOWED_OPERATIONS | FORBIDDEN_OPERATIONS:
            raise ValueError(f"unsupported operation: {operation_type}")
        operations.append(
            PatchOperation(
                operation_id=operation_id or _digest({"request_id": data.get("request_id", ""), "file": file_path, "op": operation_type}, prefix="op"),
                operation_type=operation_type,
                file_path=file_path,
                anchor_text=str(item.get("anchor_text") or ""),
                old_text=str(item.get("old_text") or ""),
                new_text=str(item.get("new_text") or ""),
                expected_occurrences=int(item.get("expected_occurrences", 1) or 1),
                reason=str(item.get("reason") or ""),
                confidence=float(item.get("confidence", 0.0) or 0.0),
            ),
        )
    for idx, operation in enumerate(operations):
        payload = asdict(operation).copy()
        payload.pop("operation_digest", None)
        operations[idx] = PatchOperation(**{**payload, "operation_digest": _digest(payload, prefix="worker-op")})

    status = str(data.get("response_status") or ResponseStatus.INVALID.value)
    if status not in {item.value for item in ResponseStatus}:
        raise ValueError(f"invalid response_status: {status}")

    response_dict = dict(data)
    response_dict.pop("response_digest", None)
    response_dict.pop("status", None)
    response_dict["patch_operations"] = [asdict(op) for op in operations]
    digest = _digest(response_dict, prefix="worker-rsp")

    return WorkerResponse(
        response_id=str(data.get("response_id") or ""),
        request_id=str(data.get("request_id") or ""),
        provider_id=str(data.get("provider_id") or ""),
        model_id=str(data.get("model_id") or ""),
        response_status=ResponseStatus(status),
        analysis_summary=str(data.get("analysis_summary") or ""),
        completed_scope=_validate_requirements(data.get("completed_scope", [])),
        remaining_gap=str(data.get("remaining_gap") or ""),
        target_files=sorted(set(_validate_requirements(data.get("target_files", [])))),
        target_symbols=sorted(set(_validate_requirements(data.get("target_symbols", [])))),
        patch_operations=operations,
        validation_recommendations=[str(item) for item in data.get("validation_recommendations", []) if str(item).strip()],
        assumptions=[str(item) for item in data.get("assumptions", []) if str(item).strip()],
        uncertainties=[str(item) for item in data.get("uncertainties", []) if str(item).strip()],
        risk_flags=[str(item) for item in data.get("risk_flags", []) if str(item).strip()],
        scope_violations=[str(item) for item in data.get("scope_violations", []) if str(item).strip()],
        unsupported_requests=[str(item) for item in data.get("unsupported_requests", []) if str(item).strip()],
        usage_metadata={str(k): str(v) for k, v in (data.get("usage_metadata") or {}).items()},
        response_digest=digest,
    )


def validate_worker_request(request: WorkerRequest) -> None:
    if request.maximum_input_tokens <= 0 or request.maximum_output_tokens <= 0:
        raise ValueError("token limits must be positive")
    if request.maximum_cost < 0:
        raise ValueError("maximum_cost must be non-negative")
    for item in request.target_files:
        _normalize_path(item)
    for text in request.minimum_context.values():
        _reject_secret_content(text)


def validate_worker_response(
    *,
    request: WorkerRequest,
    response: WorkerResponse,
    known_files: Set[str],
    known_symbols: Set[str],
    protected_files: Set[str],
    file_contents: Dict[str, str],
    failed_patch_fingerprints: Set[str] | None = None,
) -> ValidationResult:
    failed = set(failed_patch_fingerprints or set())
    issues: List[ValidationIssue] = []
    for item in (
        ResponseStatus.COMPLETED,
        ResponseStatus.PARTIAL,
        ResponseStatus.NEEDS_MORE_CONTEXT,
        ResponseStatus.BLOCKED,
        ResponseStatus.INVALID,
        ResponseStatus.UNSAFE,
        ResponseStatus.PROVIDER_ERROR,
        ResponseStatus.TIMEOUT,
    ):
        if response.response_status == item and item not in {ResponseStatus.COMPLETED, ResponseStatus.PARTIAL}:
            if item not in {ResponseStatus.NEEDS_MORE_CONTEXT, ResponseStatus.BLOCKED, ResponseStatus.INVALID, ResponseStatus.UNSAFE, ResponseStatus.PROVIDER_ERROR, ResponseStatus.TIMEOUT}:
                issues.append(ValidationIssue("invalid_status", f"unsupported response status {response.response_status}"))
                break
    if response.request_id != request.request_id:
        issues.append(ValidationIssue("request_id_mismatch", "response request_id does not match"))
    if response.provider_id != request.provider_id or response.model_id != request.model_id:
        issues.append(ValidationIssue("provider_mismatch", "provider/model mismatch"))
    if set(response.target_files).difference(request.target_files):
        issues.append(ValidationIssue("scope_file", "response targets files outside request scope"))
    if set(response.target_symbols).difference(request.target_symbols):
        issues.append(ValidationIssue("scope_symbol", "response targets symbols outside request scope"))

    used_request_files = set(request.target_files)
    used_symbols = set(request.target_symbols)
    used_completed = set(request.completed_scope or [])

    for operation in response.patch_operations:
        if operation.operation_type not in ALLOWED_OPERATIONS:
            issues.append(ValidationIssue("unsupported_operation", f"unsupported operation {operation.operation_type}"))
        if operation.operation_type in FORBIDDEN_OPERATIONS:
            issues.append(ValidationIssue("forbidden_operation", f"forbidden operation {operation.operation_type}"))
        if operation.file_path in protected_files:
            issues.append(ValidationIssue("protected_file", f"protected file {operation.file_path}"))
        if operation.file_path not in used_request_files:
            issues.append(ValidationIssue("file_not_allowed", f"file not in request scope {operation.file_path}"))
        if operation.file_path not in known_files:
            issues.append(ValidationIssue("hallucinated_file", f"unknown file {operation.file_path}"))
        if not operation.anchor_text and not operation.old_text:
            issues.append(ValidationIssue("missing_anchor", f"operation has no anchor/old_text: {operation.operation_id}"))
        if operation.expected_occurrences < 0:
            issues.append(ValidationIssue("invalid_occurrences", f"negative occurrences for {operation.operation_id}"))
        combined = f"{operation.anchor_text} {operation.old_text} {operation.new_text}".lower()
        if any(item in combined for item in RESTRICTED_TEXT_HINTS):
            issues.append(ValidationIssue("forbidden_instruction", f"operation contains forbidden instruction {operation.operation_id}"))
        if operation.operation_type != "create_file":
            known_content = file_contents.get(operation.file_path, "")
            needle = operation.old_text or operation.anchor_text
            if needle and known_content.count(needle) != int(operation.expected_occurrences):
                issues.append(ValidationIssue("occurrence_mismatch", f"occurrence mismatch: {operation.operation_id}"))
        if operation.operation_digest in failed:
            issues.append(ValidationIssue("duplicate_failed_patch", f"repeated patch fingerprint {operation.operation_id}"))
        if not 0.0 <= operation.confidence <= 1.0:
            issues.append(ValidationIssue("invalid_confidence", f"invalid confidence {operation.operation_id}"))

    if set(response.completed_scope).intersection(used_completed):
        issues.append(ValidationIssue("completed_scope_repeat", "completed scope overlap"))

    if not set(used_symbols).issuperset(set(response.target_symbols)):
        issues.append(ValidationIssue("hallucinated_symbol", "response symbols outside request scope"))

    usage = response.usage_metadata or {}
    if int(usage.get("input_tokens", 0)) > request.maximum_input_tokens:
        issues.append(ValidationIssue("input_token_cap", "input token cap exceeded"))
    if int(usage.get("output_tokens", 0)) > request.maximum_output_tokens:
        issues.append(ValidationIssue("output_token_cap", "output token cap exceeded"))
    if float(usage.get("estimated_cost", 0.0)) > request.maximum_cost:
        issues.append(ValidationIssue("cost_cap", "cost cap exceeded"))

    status = ValidationResultStatus.VALID if not issues else ValidationResultStatus.INVALID
    return ValidationResult(valid=not issues, status=status, issues=issues, response_digest=response.response_digest)
