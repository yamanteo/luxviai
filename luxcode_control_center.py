from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from lux_controlled_apply_engine import execute_controlled_apply, get_controlled_apply_status, prepare_controlled_apply, rollback_controlled_apply
from luxcode_autonomy_permission_controller import get_autonomy_permission_status
from luxcode_control_analytics import build_analytics_summary, build_engine_performance, get_session_analytics, load_persisted_analytics_sessions, redact_secret
from luxcode_evidence_board import get_evidence_board_registry, get_evidence_board_status
from luxcode_first_usable_registry import ENGINE_ORDER, get_unified_engine_registry
from luxcode_first_usable_session_flow import build_handoff_preview, build_session_state
from luxcode_practical_coder_runtime import (
    build_minimum_context_for_coder,
    build_practical_coder_task_plan,
    control_practical_patch,
    create_repository_intake,
    draft_practical_patch,
    get_practical_coder_status,
    targeted_code_search,
    validate_practical_coder,
)
from luxcode_tier0_deterministic_executor import analyze_python_imports, build_repository_map, discover_validations, run_tier0_diagnostics


CONTROL_CENTER_VERSION = "luxcode_control_center_v1"
UNWIRED = "henüz bağlanmadı"
SAFE_INVARIANTS = {
    "external_api_used": False,
    "live_model_call_used": False,
    "paid_fallback_used": False,
    "automatic_apply_used": False,
    "automatic_commit_push_used": False,
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any, prefix: str) -> str:
    return f"{prefix}-{hashlib.sha256(_stable_json(value).encode('utf-8')).hexdigest()[:24]}"


def _repo_root(repository_root: str | Path | None = None) -> Path:
    root = Path(repository_root or ".").expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError("repository_root must be a valid directory")
    return root


def _ok(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, **SAFE_INVARIANTS, **payload}


def get_control_center_schema() -> Dict[str, Any]:
    return _ok({
        "version": CONTROL_CENTER_VERSION,
        "sections": [
            "First Usable tek gorev",
            "Aktif session ve motor zinciri",
            "Repository diagnostics",
            "Context/search/task plan",
            "Safe Patch preview ve approval",
            "Controlled apply guvenlik kapilari",
            "Validation/test sonuclari",
            "Rollback/snapshot",
            "Session gecmisi",
            "Evidence Board",
            "Deferred Queue ve explicit resume",
            "Approval merkezi",
            "Motor/system status",
            "Guvenli ayarlar",
            "Model Katkisi ve Tasarruf",
        ],
        "api_endpoints": [
            "GET /luxcode-control/schema",
            "GET /luxcode-control/status",
            "GET /luxcode-control/sessions",
            "GET /luxcode-control/sessions/{session_id}",
            "POST /luxcode-control/first-usable/run",
            "POST /luxcode-control/repository/diagnostics",
            "POST /luxcode-control/search",
            "POST /luxcode-control/context",
            "POST /luxcode-control/task-plan",
            "POST /luxcode-control/safe-patch/preview",
            "POST /luxcode-control/safe-patch/approval",
            "POST /luxcode-control/controlled-apply/prepare",
            "POST /luxcode-control/controlled-apply/execute",
            "POST /luxcode-control/validation/run",
            "POST /luxcode-control/rollback",
            "GET /luxcode-control/evidence-board",
            "GET /luxcode-control/deferred-queue",
            "POST /luxcode-control/deferred-queue/resume",
            "GET /luxcode-control/approvals",
            "GET /luxcode-control/motor-status",
            "GET /luxcode-control/settings",
        ],
        "cli_commands": [
            "control-status",
            "control-sessions",
            "control-session",
            "first-usable-run",
            "repo-diagnostics",
            "control-search",
            "control-context",
            "control-task-plan",
            "safe-patch-preview",
            "approval-center",
            "deferred-queue",
            "deferred-resume",
            "evidence-board",
            "motor-status",
            "control-settings",
        ],
        "unwired_policy": "Repoda gercek destek yoksa buton/API sonucu 'henüz bağlanmadı' olarak doner.",
    })


def get_control_center_status(repository_root: str | Path = ".") -> Dict[str, Any]:
    root = _repo_root(repository_root)
    sessions = load_persisted_analytics_sessions(root)
    return _ok({
        "version": CONTROL_CENTER_VERSION,
        "repository_root": str(root),
        "active_session_count": len(sessions),
        "engine_order": ENGINE_ORDER,
        "first_usable_connected": True,
        "repository_diagnostics_connected": True,
        "coder_runtime_connected": True,
        "safe_patch_connected": True,
        "controlled_apply_connected": True,
        "evidence_board_connected": True,
        "analytics_connected": True,
        "live_model_execution": "disabled_in_control_center",
        "paid_fallback": "blocked",
        "automatic_apply": "blocked",
        "commit_push": "not_available_from_control_center",
        "updated_at": _now(),
    })


def list_control_sessions(repository_root: str | Path = ".") -> Dict[str, Any]:
    root = _repo_root(repository_root)
    sessions = load_persisted_analytics_sessions(root)
    analytics = build_analytics_summary(root, sessions=sessions)
    return _ok({
        "repository_root": str(root),
        "session_count": len(sessions),
        "sessions": analytics.get("sessions", []),
        "history_source": ".luxcode_runtime/coder_sessions",
        "missing_history_note": "" if sessions else "Kayitli session yok; yeni gorev baslatildiginda gorunecek.",
    })


def get_control_session(session_id: str, repository_root: str | Path = ".") -> Dict[str, Any]:
    root = _repo_root(repository_root)
    detail = get_session_analytics(session_id, root)
    if not detail.get("ok"):
        return _ok({"session_id": session_id, "connected": False, "status": UNWIRED, "reason": "session_not_found"})
    return _ok({"session": detail})


def run_first_usable_task(payload: Dict[str, Any], repository_root: str | Path = ".") -> Dict[str, Any]:
    root = _repo_root(payload.get("repository_root") or repository_root)
    task_summary = str(payload.get("task_summary") or payload.get("task") or "")
    session_id = str(payload.get("session_id") or _digest({"task": task_summary, "root": str(root), "time": _now()}, "control-session"))
    task_id = str(payload.get("task_id") or session_id.replace("control-session-", "task-", 1))
    selected_files = [str(item) for item in payload.get("target_files") or payload.get("selected_files") or []]
    remaining_gap = payload.get("remaining_gap") or {"remaining_gap": task_summary or "new task"}
    minimum_context = payload.get("minimum_context") if isinstance(payload.get("minimum_context"), dict) else {}
    completed_scope = payload.get("completed_scope") if isinstance(payload.get("completed_scope"), list) else []
    session = build_session_state(session_id=session_id, task_id=task_id, current_stage="created", completed_scope=completed_scope, remaining_gap=remaining_gap)
    preview = build_handoff_preview(
        session={**session, "task_summary": task_summary},
        completed_scope=completed_scope,
        remaining_gap=remaining_gap,
        minimum_context={str(k): str(v) for k, v in minimum_context.items()},
        target_files=selected_files,
        registry_overrides=payload.get("registry_overrides") if isinstance(payload.get("registry_overrides"), dict) else None,
    )
    tier0 = None
    if payload.get("run_tier0_diagnostics") is True:
        tier0 = run_tier0_diagnostics(str(root), task_summary, selected_files)
    return _ok({
        "session_id": session_id,
        "task_id": task_id,
        "task_summary": redact_secret(task_summary),
        "mode": "preview_only",
        "first_usable_preview": preview,
        "tier0_diagnostics": tier0,
        "live_model_call": "not_started",
        "paid_fallback": "blocked",
        "next_user_action": "Inspect preview, then run explicit approved local steps if needed.",
    })


def repository_diagnostics(payload: Dict[str, Any], repository_root: str | Path = ".") -> Dict[str, Any]:
    root = _repo_root(payload.get("repository_root") or repository_root)
    selected_files = payload.get("selected_files") if isinstance(payload.get("selected_files"), list) else []
    task_summary = str(payload.get("task_summary") or "repository diagnostics")
    return _ok({
        "repository_map": build_repository_map(str(root)),
        "import_analysis": analyze_python_imports(str(root)),
        "validation_discovery": discover_validations(str(root)),
        "tier0_diagnostics": run_tier0_diagnostics(str(root), task_summary, [str(item) for item in selected_files] or None),
    })


def control_search(payload: Dict[str, Any], repository_root: str | Path = ".") -> Dict[str, Any]:
    root = _repo_root(payload.get("repository_root") or repository_root)
    return targeted_code_search(
        repository_root=str(root),
        query=str(payload.get("query") or ""),
        selected_files=[str(item) for item in payload.get("selected_files") or []],
        max_results=int(payload.get("max_results") or 30),
        case_sensitive=bool(payload.get("case_sensitive", False)),
    )


def control_context(payload: Dict[str, Any], repository_root: str | Path = ".") -> Dict[str, Any]:
    root = _repo_root(payload.get("repository_root") or repository_root)
    intake = payload.get("repository_intake") if isinstance(payload.get("repository_intake"), dict) else create_repository_intake(str(root), str(payload.get("task_summary") or ""), payload.get("requested_files") or [], payload.get("suspected_files") or [])
    return build_minimum_context_for_coder(
        repository_intake=intake,
        search_results=payload.get("search_results") if isinstance(payload.get("search_results"), list) else [],
        max_files=int(payload.get("max_files") or 8),
        max_chars=int(payload.get("max_chars") or 16000),
    )


def control_task_plan(payload: Dict[str, Any], repository_root: str | Path = ".") -> Dict[str, Any]:
    root = _repo_root(payload.get("repository_root") or repository_root)
    intake = payload.get("repository_intake") if isinstance(payload.get("repository_intake"), dict) else create_repository_intake(str(root), str(payload.get("task_summary") or ""), payload.get("requested_files") or [], payload.get("suspected_files") or [])
    return build_practical_coder_task_plan(
        repository_intake=intake,
        task_summary=str(payload.get("task_summary") or intake.get("task_summary") or ""),
        selected_files=[str(item) for item in payload.get("selected_files") or []],
        acceptance_criteria=[str(item) for item in payload.get("acceptance_criteria") or []],
    )


def safe_patch_preview(payload: Dict[str, Any], repository_root: str | Path = ".") -> Dict[str, Any]:
    root = _repo_root(payload.get("repository_root") or repository_root)
    task_plan = payload.get("task_plan") if isinstance(payload.get("task_plan"), dict) else control_task_plan({"repository_root": str(root), "task_summary": payload.get("task_summary", ""), "selected_files": payload.get("approved_files", [])}, root)
    return draft_practical_patch(
        repository_root=str(root),
        task_plan=task_plan,
        operations=payload.get("operations") if isinstance(payload.get("operations"), list) else [],
        approved_files=[str(item) for item in payload.get("approved_files") or task_plan.get("selected_files", [])],
        protected_files=[str(item) for item in payload.get("protected_files") or [".env", "luxcode_tasks.db", ".luxcode_runtime"]],
    )


def safe_patch_approval(payload: Dict[str, Any]) -> Dict[str, Any]:
    patch_contract = payload.get("patch_contract") if isinstance(payload.get("patch_contract"), dict) else {}
    if not patch_contract:
        return _ok({"approved": False, "status": "blocked", "reason": "patch_contract_required"})
    if str(payload.get("action") or "preview") == "apply" and not bool(payload.get("approval_confirmed", False)):
        return _ok({"approved": False, "status": "blocked", "reason": "approval_required", "patch_id": patch_contract.get("patch_id")})
    return control_practical_patch(
        patch_contract=patch_contract,
        action=str(payload.get("action") or "preview"),
        approval_confirmed=bool(payload.get("approval_confirmed", False)),
        approval_token=str(payload.get("approval_token") or ""),
        dry_run=bool(payload.get("dry_run", True)),
        validation_plan=payload.get("validation_plan") if isinstance(payload.get("validation_plan"), list) else [],
    )


def controlled_apply_prepare(payload: Dict[str, Any]) -> Dict[str, Any]:
    patch_contract = payload.get("patch_contract") if isinstance(payload.get("patch_contract"), dict) else payload
    if not isinstance(patch_contract, dict) or not patch_contract:
        return _ok({"status": "blocked", "reason": "patch_contract_required"})
    return prepare_controlled_apply(
        repository_root=patch_contract.get("repository_root"),
        patch_id=patch_contract.get("patch_id"),
        patch_steps=patch_contract.get("patch_steps") or patch_contract.get("operations") or [],
        approved_files=patch_contract.get("approved_files") or patch_contract.get("allowed_files") or [],
        forbidden_files=patch_contract.get("forbidden_files") or patch_contract.get("protected_files") or [".env", "luxcode_tasks.db", ".luxcode_runtime"],
        expected_file_hashes=patch_contract.get("expected_file_hashes") or {},
        mode="prepare",
        validation_plan=patch_contract.get("validation_plan") or [],
    )


def controlled_apply_execute(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not bool(payload.get("approval_confirmed")):
        return _ok({"status": "blocked", "reason": "approval_required", "automatic_apply_used": False})
    apply_request = payload.get("apply_request") if isinstance(payload.get("apply_request"), dict) else payload
    return execute_controlled_apply(
        repository_root=apply_request.get("repository_root"),
        patch_id=apply_request.get("patch_id"),
        patch_steps=apply_request.get("patch_steps") or apply_request.get("operations") or [],
        approved_files=apply_request.get("approved_files") or apply_request.get("allowed_files") or [],
        forbidden_files=apply_request.get("forbidden_files") or apply_request.get("protected_files") or [".env", "luxcode_tasks.db", ".luxcode_runtime"],
        approval_token=str(payload.get("approval_token") or apply_request.get("approval_token") or ""),
        expected_file_hashes=apply_request.get("expected_file_hashes") or {},
        mode="apply",
        validation_plan=apply_request.get("validation_plan") or [],
    )


def validation_run(payload: Dict[str, Any], repository_root: str | Path = ".") -> Dict[str, Any]:
    root = _repo_root(payload.get("repository_root") or repository_root)
    return validate_practical_coder(str(root), payload.get("validation_plan") if isinstance(payload.get("validation_plan"), list) else [])


def rollback_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload.get("rollback_id"):
        return _ok({"status": "blocked", "reason": "rollback_id_required", "rollback_connected": True})
    return rollback_controlled_apply(
        repository_root=payload.get("repository_root"),
        patch_id=payload.get("patch_id"),
        rollback_id=str(payload.get("rollback_id")),
        approval_token=str(payload.get("approval_token") or ""),
        mode=str(payload.get("mode") or "rollback_preview"),
    )


def evidence_board(task_id: str = "") -> Dict[str, Any]:
    return _ok({"registry": get_evidence_board_registry(), "status": get_evidence_board_status(task_id or None)})


def deferred_queue(repository_root: str | Path = ".") -> Dict[str, Any]:
    sessions = load_persisted_analytics_sessions(_repo_root(repository_root))
    deferred: List[Dict[str, Any]] = []
    for session in sessions:
        raw_runs = session.get("engine_runs", []) if isinstance(session.get("engine_runs"), list) else []
        for run in raw_runs:
            if isinstance(run, dict) and str(run.get("result_class") or run.get("status") or "") in {"EXTERNAL_SERVICE_DEFERRED", "deferred", "rate_limited", "provider_unavailable", "timeout"}:
                deferred.append({"session_id": session.get("session_id"), "engine_id": run.get("engine_id"), "model_id": run.get("model_id"), "reason": run.get("failure_reason") or run.get("status"), "resume_requires_explicit_request": True})
    return _ok({"deferred_count": len(deferred), "items": deferred, "resume_policy": "explicit_only_no_auto_http"})


def deferred_resume(payload: Dict[str, Any], repository_root: str | Path = ".") -> Dict[str, Any]:
    queue = deferred_queue(repository_root)
    session_id = str(payload.get("session_id") or "")
    match = [item for item in queue.get("items", []) if str(item.get("session_id")) == session_id]
    if not match:
        return _ok({"resume_started": False, "status": UNWIRED, "reason": "deferred_session_not_found"})
    if not bool(payload.get("explicit_resume")):
        return _ok({"resume_started": False, "status": "blocked", "reason": "explicit_resume_required"})
    return _ok({"resume_started": False, "status": UNWIRED, "reason": "live model resume endpoint not connected in control center", "matched_item": match[0]})


def approval_center(repository_root: str | Path = ".") -> Dict[str, Any]:
    return _ok({
        "permission_status": get_autonomy_permission_status(),
        "controlled_apply_status": get_controlled_apply_status(),
        "pending_approvals": [],
        "note": "Onay gerektiren patch/apply/deferred resume istekleri burada listelenir; kayitli pending approval yok.",
    })


def motor_status(repository_root: str | Path = ".") -> Dict[str, Any]:
    return _ok({
        "engines": get_unified_engine_registry(),
        "engine_performance": build_engine_performance(repository_root),
        "practical_coder": get_practical_coder_status(),
        "controlled_apply": get_controlled_apply_status(),
    })


def safe_settings() -> Dict[str, Any]:
    return _ok({
        "live_model_calls": "manual_explicit_only",
        "paid_fallback": "blocked",
        "automatic_apply": "blocked",
        "automatic_commit_push": "blocked",
        "secret_redaction": "enabled",
        "approval_required_for_apply": True,
        "deferred_resume": "explicit_only",
        "unsupported_features_label": UNWIRED,
    })
