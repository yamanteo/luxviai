from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Sequence

from luxcode_first_usable_registry import ENGINE_ORDER, build_safe_config, engine_failure_fingerprint, get_unified_engine_registry, select_engine_preview


HEALTH_STATES = {
    "healthy",
    "degraded",
    "slow",
    "stalled",
    "not_installed",
    "not_running",
    "rate_limited",
    "quota_exhausted",
    "authentication_failed",
    "memory_insufficient",
    "disabled",
    "unknown",
}
RESULT_STATUSES = {
    "completed",
    "partial",
    "needs_more_context",
    "blocked",
    "invalid",
    "unsafe",
    "runtime_unavailable",
    "provider_error",
    "timeout",
    "fallback_required",
}
SESSION_STAGES = {"created", "intake", "engine_selection", "worker_request", "worker_response", "completed", "blocked", "handoff_required"}
SECRET_MASK = "[redacted]"
MAX_CONTEXT_CHARS = 12000


@dataclass(frozen=True)
class RuntimeHealthSnapshot:
    engine_id: str
    availability: str
    health_status: str
    consecutive_failures: int
    last_error_category: str | None
    average_latency_ms: int | None
    cooldown_until: str | None
    capacity_summary: str | None
    health_digest: str


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def digest(value: Any, prefix: str) -> str:
    return f"{prefix}-{sha256(stable_json(value).encode('utf-8')).hexdigest()[:24]}"


def redact_secret(value: Any) -> Any:
    patterns = [
        re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)([^\s,;]+)"),
        re.compile(r"(?i)((?:api[_-]?key|token|secret|password|cookie)\s*[:=]\s*[\"']?)([^\"'\s,;]+)"),
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
            if any(marker in str(key).lower() for marker in ("secret", "token", "api_key", "authorization", "cookie", "password")):
                cleaned[str(key)] = SECRET_MASK
            else:
                cleaned[str(key)] = redact_secret(item)
        return cleaned
    if isinstance(value, list):
        return [redact_secret(item) for item in value[:200]]
    return value


def build_runtime_health_snapshot(
    engine_id: str,
    *,
    availability: str = "available",
    health_status: str = "healthy",
    consecutive_failures: int = 0,
    last_error_category: str | None = None,
    average_latency_ms: int | None = None,
    cooldown_until: str | None = None,
    capacity_summary: str | None = None,
) -> Dict[str, Any]:
    status = health_status if health_status in HEALTH_STATES else "unknown"
    payload = {
        "engine_id": engine_id,
        "availability": availability,
        "health_status": status,
        "consecutive_failures": max(0, int(consecutive_failures or 0)),
        "last_error_category": last_error_category,
        "average_latency_ms": average_latency_ms,
        "cooldown_until": cooldown_until,
        "capacity_summary": capacity_summary,
    }
    return asdict(RuntimeHealthSnapshot(health_digest=digest(payload, "health"), **payload))


def _health_to_selector(snapshot: Dict[str, Any]) -> str:
    status = str(snapshot.get("health_status") or "unknown")
    if snapshot.get("cooldown_until"):
        return "cooldown"
    if status in {"healthy", "slow"}:
        return "healthy"
    return status


def _completed_scope_digest(completed_scope: Sequence[str] | None) -> str:
    return digest(sorted(str(item) for item in (completed_scope or [])), "completed-scope")


def _limited_context(minimum_context: Dict[str, str]) -> Dict[str, str]:
    total = 0
    output: Dict[str, str] = {}
    for key in sorted(minimum_context):
        clean_key = str(key)
        clean_value = str(redact_secret(minimum_context[key]))
        if any(marker in clean_key.lower() for marker in (".env", "secret", "token", "api_key", "authorization")):
            continue
        remaining = MAX_CONTEXT_CHARS - total
        if remaining <= 0:
            break
        output[clean_key] = clean_value[:remaining]
        total += len(output[clean_key])
    return output


def build_request_envelope(
    *,
    task_id: str,
    session_id: str,
    engine_id: str,
    tier: int | None,
    task_summary: str,
    remaining_gap: Any,
    completed_scope: Sequence[str] | None,
    target_files: Sequence[str],
    target_symbols: Sequence[str],
    minimum_context: Dict[str, str],
    evidence_ids: Sequence[str] | None = None,
    failed_attempt_fingerprints: Sequence[str] | None = None,
    task_class: str = "small_code_fix",
    acceptance_criteria: Sequence[str] | None = None,
    required_output_schema: str = "structured_json_v1",
    risk_level: str = "low",
    maximum_input_tokens: int = 12000,
    maximum_output_tokens: int = 4000,
    maximum_cost: float = 0.0,
    timeout_seconds: int = 60,
    seen_request_digests: set[str] | None = None,
) -> Dict[str, Any] | None:
    if not remaining_gap:
        return None
    payload = {
        "request_id": "",
        "task_id": task_id,
        "session_id": session_id,
        "engine_id": engine_id,
        "tier": tier,
        "task_class": task_class,
        "task_summary": str(redact_secret(task_summary)),
        "remaining_gap": redact_secret(remaining_gap),
        "completed_scope_digest": _completed_scope_digest(completed_scope),
        "target_files": [str(item) for item in target_files],
        "target_symbols": [str(item) for item in target_symbols],
        "minimum_context": _limited_context(minimum_context),
        "evidence_ids": [str(item) for item in (evidence_ids or [])],
        "failed_attempt_fingerprints": [str(item) for item in (failed_attempt_fingerprints or [])],
        "acceptance_criteria": [str(item) for item in (acceptance_criteria or ["structured-json", "safe-preview"])],
        "required_output_schema": required_output_schema,
        "risk_level": risk_level,
        "maximum_input_tokens": max(0, int(maximum_input_tokens)),
        "maximum_output_tokens": max(0, int(maximum_output_tokens)),
        "maximum_cost": max(0.0, float(maximum_cost)),
        "timeout_seconds": max(1, int(timeout_seconds)),
    }
    request_core = {key: value for key, value in payload.items() if key not in {"request_id", "request_digest"}}
    payload["request_digest"] = digest(request_core, "request")
    payload["request_id"] = payload["request_digest"].replace("request-", "req-", 1)
    if seen_request_digests is not None:
        if payload["request_digest"] in seen_request_digests:
            return None
        seen_request_digests.add(payload["request_digest"])
    return payload


def build_result_envelope(
    *,
    request: Dict[str, Any],
    status: str,
    analysis_summary: str,
    completed_scope: Sequence[str] | None = None,
    remaining_gap: Any = None,
    target_files: Sequence[str] | None = None,
    target_symbols: Sequence[str] | None = None,
    patch_operations: Sequence[Dict[str, Any]] | None = None,
    validation_recommendations: Sequence[str] | None = None,
    evidence_records: Sequence[Dict[str, Any]] | None = None,
    assumptions: Sequence[str] | None = None,
    uncertainties: Sequence[str] | None = None,
    risk_flags: Sequence[str] | None = None,
    usage_metadata: Dict[str, Any] | None = None,
    failure_fingerprints: Sequence[str] | None = None,
) -> Dict[str, Any]:
    safe_status = status if status in RESULT_STATUSES else "invalid"
    if safe_status == "completed" and not (patch_operations or validation_recommendations):
        safe_status = "invalid"
    payload = {
        "result_id": "",
        "request_id": request.get("request_id"),
        "task_id": request.get("task_id"),
        "session_id": request.get("session_id"),
        "engine_id": request.get("engine_id"),
        "tier": request.get("tier"),
        "status": safe_status,
        "analysis_summary": str(redact_secret(analysis_summary)),
        "completed_scope": [str(item) for item in (completed_scope or [])],
        "remaining_gap": redact_secret(remaining_gap or ""),
        "target_files": [str(item) for item in (target_files or request.get("target_files", []))],
        "target_symbols": [str(item) for item in (target_symbols or request.get("target_symbols", []))],
        "patch_operations": redact_secret(list(patch_operations or [])),
        "validation_recommendations": [str(item) for item in (validation_recommendations or [])],
        "evidence_records": redact_secret(list(evidence_records or [])),
        "assumptions": [str(redact_secret(item)) for item in (assumptions or [])],
        "uncertainties": [str(redact_secret(item)) for item in (uncertainties or [])],
        "risk_flags": [str(item) for item in (risk_flags or [])],
        "usage_metadata": redact_secret(usage_metadata or {}),
        "failure_fingerprints": [str(item) for item in (failure_fingerprints or [])],
    }
    payload["result_digest"] = digest({key: value for key, value in payload.items() if key not in {"result_id", "result_digest"}}, "result")
    payload["result_id"] = payload["result_digest"].replace("result-", "res-", 1)
    return payload


def build_session_state(
    *,
    session_id: str,
    task_id: str,
    current_stage: str = "created",
    selected_engine: str | None = None,
    selected_tier: int | None = None,
    completed_scope: Sequence[str] | None = None,
    remaining_gap: Any = None,
    target_files: Sequence[str] | None = None,
    target_symbols: Sequence[str] | None = None,
    failed_attempt_fingerprints: Sequence[str] | None = None,
    evidence_ids: Sequence[str] | None = None,
    request_id: str | None = None,
    result_id: str | None = None,
    final_status: str | None = None,
    stop_reason: str | None = None,
) -> Dict[str, Any]:
    stage = current_stage if current_stage in SESSION_STAGES else "blocked"
    payload = {
        "session_id": session_id,
        "task_id": task_id,
        "current_stage": stage,
        "selected_engine": selected_engine,
        "selected_tier": selected_tier,
        "completed_scope": [str(item) for item in (completed_scope or [])],
        "remaining_gap": redact_secret(remaining_gap or ""),
        "target_files": [str(item) for item in (target_files or [])],
        "target_symbols": [str(item) for item in (target_symbols or [])],
        "failed_attempt_fingerprints": [str(item) for item in (failed_attempt_fingerprints or [])],
        "evidence_ids": [str(item) for item in (evidence_ids or [])],
        "request_id": request_id,
        "result_id": result_id,
        "final_status": final_status,
        "stop_reason": stop_reason,
    }
    payload["session_digest"] = digest({key: value for key, value in payload.items() if key != "session_digest"}, "session")
    return payload


def build_guard_fingerprints(*, task: Any, context: Any, request: Any, response: Any, engine_id: str, validation_error: Any) -> Dict[str, str]:
    return {
        "task_fingerprint": digest(task, "task-fp"),
        "context_fingerprint": digest(context, "context-fp"),
        "request_fingerprint": digest(request, "request-fp"),
        "response_fingerprint": digest(response, "response-fp"),
        "engine_failure_fingerprint": engine_failure_fingerprint(engine_id, response or validation_error),
        "validation_failure_fingerprint": digest(validation_error, "validation-fp"),
    }


def build_decision_event(
    *,
    session_id: str,
    task_id: str,
    engine: Dict[str, Any],
    event_type: str,
    decision_reason: str,
    selected: bool,
    rejected_reason: str | None,
    health_status: str,
    retry_state: str | None,
    estimated_cost: float | None,
    completed: bool,
    remaining_gap: Any,
    failure_fingerprint: str | None = None,
    timestamp: str = "1970-01-01T00:00:00Z",
) -> Dict[str, Any]:
    payload = {
        "event_id": "",
        "session_id": session_id,
        "task_id": task_id,
        "engine_id": engine.get("engine_id"),
        "tier": engine.get("tier"),
        "event_type": event_type,
        "decision_reason": decision_reason,
        "selected": bool(selected),
        "rejected_reason": rejected_reason,
        "health_status": health_status,
        "retry_state": retry_state,
        "cost_class": engine.get("cost_class"),
        "estimated_cost": estimated_cost,
        "completed": bool(completed),
        "remaining_gap_digest": digest(remaining_gap, "remaining-gap"),
        "failure_fingerprint": failure_fingerprint,
        "timestamp": timestamp,
    }
    payload["event_digest"] = digest({key: value for key, value in payload.items() if key not in {"event_id", "event_digest"}}, "event")
    payload["event_id"] = payload["event_digest"].replace("event-", "evt-", 1)
    return payload


def build_handoff_preview(
    *,
    session: Dict[str, Any],
    completed: bool = False,
    completed_scope: Sequence[str] | None = None,
    remaining_gap: Any = None,
    minimum_context: Dict[str, str] | None = None,
    target_files: Sequence[str] | None = None,
    target_symbols: Sequence[str] | None = None,
    runtime_health_snapshots: Dict[str, Dict[str, Any]] | None = None,
    provider_health_snapshots: Dict[str, Dict[str, Any]] | None = None,
    failed_attempt_fingerprints: Sequence[str] | None = None,
    seen_request_digests: set[str] | None = None,
    seen_stage_input_digests: set[str] | None = None,
    free_tier_exhaustion_confirmed: bool = False,
    paid_escalation_approved: bool = False,
    cost_budget: float | None = None,
    manual_request: bool = False,
    emergency_request: bool = False,
    registry_overrides: Dict[str, Dict[str, Any]] | None = None,
    config_overrides: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    minimum_context = minimum_context or {}
    target_files = list(target_files or [])
    target_symbols = list(target_symbols or [])
    runtime_selector = {engine_id: _health_to_selector(snapshot) for engine_id, snapshot in (runtime_health_snapshots or {}).items()}
    provider_selector = {engine_id: _health_to_selector(snapshot) for engine_id, snapshot in (provider_health_snapshots or {}).items()}
    stage_input_digest = digest({"session": session.get("session_id"), "remaining_gap": remaining_gap, "context": _limited_context(minimum_context)}, "stage-input")
    if seen_stage_input_digests is not None:
        if stage_input_digest in seen_stage_input_digests:
            return {
                "selected_engine": None,
                "selected_tier": None,
                "request_id": None,
                "request_digest": None,
                "context_digest": digest(_limited_context(minimum_context), "context"),
                "remaining_gap": redact_secret(remaining_gap or ""),
                "required_approval": False,
                "execution_allowed": False,
                "blockers": ["duplicate_stage_input"],
                "stop_reason": "blocked",
                "decision": None,
                "request": None,
                "session_state": build_session_state(session_id=session["session_id"], task_id=session["task_id"], current_stage="blocked", remaining_gap=remaining_gap, stop_reason="duplicate_stage_input"),
            }
        seen_stage_input_digests.add(stage_input_digest)
    if completed:
        return {
            "selected_engine": None,
            "selected_tier": None,
            "request_id": None,
            "request_digest": None,
            "context_digest": digest(_limited_context(minimum_context), "context"),
            "remaining_gap": redact_secret(remaining_gap or ""),
            "required_approval": False,
            "execution_allowed": False,
            "blockers": [],
            "stop_reason": "completed_by_lower_tier",
            "decision": select_engine_preview(completed=True, completed_scope=completed_scope, remaining_gap=remaining_gap),
            "request": None,
            "session_state": build_session_state(session_id=session["session_id"], task_id=session["task_id"], current_stage="completed", completed_scope=completed_scope, remaining_gap=remaining_gap, final_status="completed", stop_reason="completed_by_lower_tier"),
        }
    decision = select_engine_preview(
        completed=False,
        completed_scope=completed_scope,
        remaining_gap=remaining_gap,
        failed_engine_fingerprints=failed_attempt_fingerprints,
        runtime_health=runtime_selector,
        provider_health=provider_selector,
        free_tier_exhaustion_confirmed=free_tier_exhaustion_confirmed,
        paid_escalation_approved=paid_escalation_approved,
        cost_budget=cost_budget,
        manual_request=manual_request,
        emergency_request=emergency_request,
        registry_overrides=registry_overrides,
        config_overrides=config_overrides,
    )
    selected = decision.get("selected_engine")
    blockers = [] if selected else [item.get("reason", "not_selected") for item in decision.get("rejected_candidates", [])]
    if selected in {"whale", "codex"}:
        stop_reason = "handoff_required"
        execution_allowed = False
    elif selected:
        stop_reason = "worker_request_ready"
        execution_allowed = False
    else:
        stop_reason = "blocked"
        execution_allowed = False
    request = None
    if selected and selected not in {"whale", "codex"}:
        request = build_request_envelope(
            task_id=session["task_id"],
            session_id=session["session_id"],
            engine_id=selected,
            tier=decision.get("selected_tier"),
            task_summary=str(session.get("task_summary") or ""),
            remaining_gap=remaining_gap,
            completed_scope=completed_scope,
            target_files=target_files,
            target_symbols=target_symbols,
            minimum_context=minimum_context,
            failed_attempt_fingerprints=failed_attempt_fingerprints,
            maximum_cost=build_safe_config(config_overrides).get("maximum_cost_per_request", 0.0),
            seen_request_digests=seen_request_digests,
        )
        if request is None:
            blockers.append("empty_or_duplicate_request")
            stop_reason = "blocked"
    session_state = build_session_state(
        session_id=session["session_id"],
        task_id=session["task_id"],
        current_stage="handoff_required" if stop_reason == "handoff_required" else ("worker_request" if request else stop_reason),
        selected_engine=selected,
        selected_tier=decision.get("selected_tier"),
        completed_scope=completed_scope,
        remaining_gap=remaining_gap,
        target_files=target_files,
        target_symbols=target_symbols,
        failed_attempt_fingerprints=failed_attempt_fingerprints,
        request_id=request.get("request_id") if request else None,
        stop_reason=stop_reason,
    )
    return {
        "selected_engine": selected,
        "selected_tier": decision.get("selected_tier"),
        "request_id": request.get("request_id") if request else None,
        "request_digest": request.get("request_digest") if request else None,
        "context_digest": digest(_limited_context(minimum_context), "context"),
        "remaining_gap": redact_secret(remaining_gap or ""),
        "required_approval": bool(decision.get("required_approval")),
        "execution_allowed": execution_allowed,
        "blockers": blockers,
        "stop_reason": stop_reason,
        "decision": decision,
        "request": request,
        "session_state": session_state,
    }


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _patch_id(result: Dict[str, Any]) -> str:
    return digest({"result_id": result.get("result_id"), "result_digest": result.get("result_digest")}, "first-usable-patch")


def _patch_steps_from_result(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = []
    for operation in result.get("patch_operations", []):
        if not isinstance(operation, dict):
            continue
        op_type = str(operation.get("operation_type") or operation.get("type") or "")
        if op_type != "replace_text":
            continue
        steps.append(
            {
                "target_file": str(operation.get("file_path") or operation.get("target_file") or ""),
                "change_type": "replace_exact",
                "expected_original_text": str(operation.get("old_text") or ""),
                "replacement_text": str(operation.get("new_text") or ""),
                "purpose": str(operation.get("reason") or "first usable fixture patch"),
                "validation_after_change": list(result.get("validation_recommendations", [])),
            }
        )
    return [step for step in steps if step["target_file"]]


def build_fixture_safe_patch_preview(repository_root: str, result: Dict[str, Any]) -> Dict[str, Any]:
    from lux_controlled_apply_engine import prepare_controlled_apply

    root = Path(repository_root).resolve()
    steps = _patch_steps_from_result(result)
    approved_files = sorted({step["target_file"] for step in steps})
    expected_hashes = {rel: _file_sha256(root / rel) for rel in approved_files if (root / rel).exists()}
    patch_id = _patch_id(result)
    prepared = prepare_controlled_apply(
        repository_root=str(root),
        patch_id=patch_id,
        patch_steps=steps,
        approved_files=approved_files,
        forbidden_files=[".env"],
        expected_file_hashes=expected_hashes,
        mode="prepare",
        validation_plan=list(result.get("validation_recommendations", [])),
        require_clean_tree=False,
    )
    payload = {
        "patch_id": patch_id,
        "operation_count": len(steps),
        "files_to_modify": approved_files,
        "approval_required": True,
        "approval_digest": prepared.get("approval_digest", ""),
        "precondition_hashes": prepared.get("file_hashes_before", {}),
        "risk_flags": list(result.get("risk_flags", [])),
        "controlled_apply": redact_secret(prepared),
        "patch_steps": steps,
        "expected_file_hashes": expected_hashes,
        "preview_digest": "",
    }
    payload["preview_digest"] = digest({key: value for key, value in payload.items() if key != "preview_digest"}, "patch-preview")
    return payload


def _run_fixture_validation(repository_root: str, validation_plan: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    root = Path(repository_root).resolve()
    checks = []
    for item in validation_plan:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "py_compile":
            checks.append({"check": item, "status": "skipped", "reason": "unsupported_fixture_check"})
            continue
        rel = str(item.get("path") or "")
        target = (root / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            checks.append({"check": item, "status": "failed", "reason": "path_outside_fixture"})
            continue
        completed = subprocess.run([sys.executable, "-m", "py_compile", str(target)], cwd=str(root), capture_output=True, text=True, timeout=15, shell=False)
        checks.append({"check": item, "status": "passed" if completed.returncode == 0 else "failed", "returncode": completed.returncode, "stderr": completed.stderr[-500:]})
    passed = bool(checks) and all(item.get("status") in {"passed", "skipped"} for item in checks)
    return {"passed": passed, "checks": checks, "validation_digest": digest(checks, "validation")}


def execute_fixture_safe_workflow(
    *,
    repository_root: str,
    request: Dict[str, Any],
    result: Dict[str, Any],
    temporary_fixture_repo: bool,
    approval_token: str | None = None,
    validation_plan: Sequence[Dict[str, Any]] | None = None,
    seen_apply_digests: set[str] | None = None,
    persist: bool = False,
) -> Dict[str, Any]:
    from lux_controlled_apply_engine import execute_controlled_apply, rollback_controlled_apply

    preview = build_fixture_safe_patch_preview(repository_root, result)
    base_session = build_session_state(
        session_id=str(request.get("session_id")),
        task_id=str(request.get("task_id")),
        current_stage="worker_response",
        selected_engine=str(request.get("engine_id")),
        selected_tier=request.get("tier"),
        completed_scope=result.get("completed_scope", []),
        remaining_gap=result.get("remaining_gap"),
        target_files=result.get("target_files", []),
        target_symbols=result.get("target_symbols", []),
        request_id=str(request.get("request_id")),
        result_id=str(result.get("result_id")),
    )
    evidence = {
        "evidence_id": digest({"request": request.get("request_digest"), "result": result.get("result_digest"), "preview": preview.get("preview_digest")}, "evidence"),
        "preview_digest": preview.get("preview_digest"),
        "approval_state": "not_submitted" if not approval_token else "submitted",
        "validation_state": "not_started",
        "rollback_state": "not_started",
    }
    if result.get("status") == "completed" and not result.get("patch_operations"):
        state = {**base_session, "current_stage": "completed", "final_status": "completed", "stop_reason": "completed_without_patch"}
        return {"ok": True, "final_status": "completed", "stop_reason": "completed_without_patch", "preview": None, "apply": None, "validation": None, "rollback": None, "session_state": state, "evidence": evidence, "persistence": {"saved": False}}
    if result.get("status") in {"invalid", "unsafe", "blocked"}:
        state = {**base_session, "current_stage": "blocked", "final_status": "blocked", "stop_reason": "unsafe_or_invalid_result"}
        return {"ok": False, "final_status": "blocked", "stop_reason": "unsafe_or_invalid_result", "preview": preview, "apply": None, "validation": None, "rollback": None, "session_state": state, "evidence": evidence, "persistence": {"saved": False}}
    if not preview.get("operation_count"):
        state = {**base_session, "current_stage": "handoff_required", "final_status": "partial", "stop_reason": "remaining_gap_only"}
        return {"ok": False, "final_status": "partial", "stop_reason": "remaining_gap_only", "preview": preview, "apply": None, "validation": None, "rollback": None, "session_state": state, "evidence": evidence, "persistence": {"saved": False}}
    if not temporary_fixture_repo:
        state = {**base_session, "current_stage": "blocked", "final_status": "blocked", "stop_reason": "protected_repository_apply_blocked"}
        return {"ok": False, "final_status": "blocked", "stop_reason": "protected_repository_apply_blocked", "preview": preview, "apply": None, "validation": None, "rollback": None, "session_state": state, "evidence": evidence, "persistence": {"saved": False}}
    if not approval_token:
        state = {**base_session, "current_stage": "handoff_required", "final_status": "awaiting_approval", "stop_reason": "awaiting_approval"}
        return {"ok": False, "final_status": "awaiting_approval", "stop_reason": "awaiting_approval", "preview": preview, "apply": None, "validation": None, "rollback": None, "session_state": state, "evidence": evidence, "persistence": {"saved": False}}
    apply_digest = digest({"patch_id": preview["patch_id"], "approval_token": approval_token, "repo": str(Path(repository_root).resolve())}, "apply-attempt")
    if seen_apply_digests is not None:
        if apply_digest in seen_apply_digests:
            state = {**base_session, "current_stage": "blocked", "final_status": "blocked", "stop_reason": "duplicate_apply_attempt"}
            return {"ok": False, "final_status": "blocked", "stop_reason": "duplicate_apply_attempt", "preview": preview, "apply": None, "validation": None, "rollback": None, "session_state": state, "evidence": evidence, "persistence": {"saved": False}}
        seen_apply_digests.add(apply_digest)
    apply_result = execute_controlled_apply(
        repository_root=repository_root,
        patch_id=preview["patch_id"],
        patch_steps=preview["patch_steps"],
        approved_files=preview["files_to_modify"],
        forbidden_files=[".env"],
        approval_token=approval_token,
        expected_file_hashes=preview["expected_file_hashes"],
        mode="apply",
        validation_plan=list(validation_plan or []),
        require_clean_tree=False,
    )
    if apply_result.get("transaction_state") != "applied":
        state = {**base_session, "current_stage": "blocked", "final_status": "blocked", "stop_reason": "apply_blocked"}
        evidence["approval_state"] = "invalid_or_blocked"
        return {"ok": False, "final_status": "blocked", "stop_reason": "apply_blocked", "preview": preview, "apply": redact_secret(apply_result), "validation": None, "rollback": None, "session_state": state, "evidence": evidence, "persistence": {"saved": False}}
    validation = _run_fixture_validation(repository_root, validation_plan or [])
    evidence["validation_state"] = "passed" if validation.get("passed") else "failed"
    rollback = None
    if validation.get("passed"):
        state = {**base_session, "current_stage": "completed", "final_status": "completed", "stop_reason": "validation_passed"}
        final_status = "completed"
        ok = True
    else:
        rollback = rollback_controlled_apply(
            repository_root=repository_root,
            patch_id=preview["patch_id"],
            patch_steps=preview["patch_steps"],
            approved_files=preview["files_to_modify"],
            forbidden_files=[".env"],
            approval_token=apply_result.get("approval_digest"),
            expected_file_hashes=preview["expected_file_hashes"],
            mode="rollback",
            rollback_id=apply_result.get("rollback_id"),
            require_clean_tree=False,
        )
        evidence["rollback_state"] = str(rollback.get("transaction_state"))
        state = {**base_session, "current_stage": "blocked", "final_status": "rolled_back", "stop_reason": "validation_failed_rolled_back"}
        final_status = "rolled_back"
        ok = False
    persistence = {"saved": False}
    if persist:
        from luxcode_task_persistence import save_task_state

        persistence = save_task_state(
            {
                "task_id": request.get("task_id"),
                "current_state": state.get("current_stage"),
                "first_usable_session": state,
                "first_usable_patch_preview": {"patch_id": preview.get("patch_id"), "preview_digest": preview.get("preview_digest"), "files_to_modify": preview.get("files_to_modify")},
                "approval_state": evidence.get("approval_state"),
                "validation_state": evidence.get("validation_state"),
                "rollback_state": evidence.get("rollback_state"),
                "evidence_ids": [evidence["evidence_id"]],
                "final_status": final_status,
                "restore_policy": build_first_usable_restore_policy({}),
            },
            mode="memory_only",
            event_type="first_usable_fixture_workflow",
        )
    return {"ok": ok, "final_status": final_status, "stop_reason": state["stop_reason"], "preview": preview, "apply": redact_secret(apply_result), "validation": validation, "rollback": redact_secret(rollback), "session_state": state, "evidence": evidence, "persistence": persistence}


def build_first_usable_restore_policy(task_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "engine_auto_execute": False,
        "paid_call_auto_start": False,
        "apply_auto_repeat": False,
        "approval_revalidation_required": True,
        "precondition_revalidation_required": True,
        "secrets_persisted": False,
        "restore_digest": digest(task_state or {"empty": True}, "restore-policy"),
    }
