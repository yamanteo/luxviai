from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from lux_controlled_apply_engine import execute_controlled_apply, prepare_controlled_apply
from lux_debug_intelligence_core import analyze_lux_debug_request
from lux_safe_patch_draft_engine import build_safe_patch_draft
from lux_verification_recovery_engine import (
    analyze_verification_results,
    execute_verification_run,
    prepare_recovery_action,
    prepare_verification_run,
)
from luxcode_master_router_preview import build_luxcode_master_router_preview
from luxcode_autonomy_permission_controller import (
    approve_scope_expansion,
    create_permission_profile,
    evaluate_requested_action,
    get_autonomy_permission_status,
    get_safe_permission_metadata,
    revoke_scope_access,
)
from luxcode_task_persistence import (
    archive_task_state,
    delete_task_state,
    get_task_persistence_status,
    initialize_task_store,
    list_task_states,
    load_task_state,
    restore_active_tasks,
    save_task_state,
)
from luxcode_terminal_process_runtime import (
    cancel_terminal_runtime,
    execute_terminal_action,
    get_safe_runtime_metadata,
    plan_terminal_action,
)
from luxcode_live_app_interaction_testing import (
    cancel_live_test_runtime,
    execute_live_test,
    get_safe_live_test_metadata,
    plan_live_test,
)
from luxcode_local_network_access_intelligence import (
    cancel_network_access_runtime,
    create_network_access_plan,
    execute_network_access_plan,
    get_safe_network_access_metadata,
)


TASK_STATES = {
    "created",
    "routed",
    "diagnosing",
    "diagnosis_ready",
    "patch_drafting",
    "patch_ready",
    "awaiting_approval",
    "approval_verified",
    "apply_prepared",
    "applying",
    "applied",
    "verification_prepared",
    "verifying",
    "verified",
    "recovery_review",
    "rollback_recommended",
    "completed",
    "blocked",
    "failed",
    "cancelled",
    "paused",
    "awaiting_scope_permission",
    "awaiting_irreversible_confirmation",
    "autonomy_paused",
    "budget_exhausted",
}

TERMINAL_STATES = {"cancelled", "blocked", "failed", "completed"}
EXECUTION_BLOCKED_STATES = TERMINAL_STATES | {"paused", "awaiting_scope_permission", "awaiting_irreversible_confirmation", "autonomy_paused", "budget_exhausted"}
SAFE_INVARIANTS = {
    "scope_expansion_blocked": True,
    "destructive_action_blocked": True,
    "external_api_used": False,
    "local_first": True,
}
DEFAULT_FORBIDDEN_FILES = [".env", "static/index.html"]

_TASKS: Dict[str, Dict[str, Any]] = {}
_PERSISTENCE_CONFIG: Dict[str, Any] = {"mode": "disabled", "storage_root": "", "enabled": False}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "lux-task-" + hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()[:32]


def _unique(items: Iterable[Any]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).replace("\\", "/").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _safe_root(repository_root: Optional[str]) -> str:
    if not repository_root:
        return ""
    try:
        return str(Path(repository_root).resolve())
    except OSError:
        return str(repository_root)


def _file_hashes(repository_root: str, files: List[str]) -> Dict[str, str]:
    root = Path(repository_root)
    hashes: Dict[str, str] = {}
    for rel in files:
        path = (root / rel).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            continue
        if path.exists() and path.is_file():
            hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        clean: Dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(secret in lowered for secret in ("secret", "api_key", "token", "password", ".env")):
                continue
            clean[key] = _redact(item)
        return clean
    if isinstance(value, list):
        return [_redact(item) for item in value[:40]]
    if isinstance(value, str):
        if ".env" in value or len(value) > 2000:
            return value[:2000].replace(".env", "[redacted-env]")
    return value


def _classify_adjacent(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for item in raw or []:
        text = _stable_json(item).lower()
        if "directly_related" in text or "required" in text:
            scope = "required_for_current_task"
        elif "optional" in text or "nice" in text:
            scope = "optional_improvement"
        elif "out_of_scope" in text or "unrelated" in text:
            scope = "out_of_scope"
        else:
            scope = "recommended_follow_up"
        finding = dict(item)
        finding["scope_classification"] = scope
        finding["auto_added_to_patch_targets"] = scope == "required_for_current_task"
        findings.append(finding)
    return findings


def _make_patch_id(task: Dict[str, Any]) -> str:
    draft = task.get("patch_draft_result", {})
    return draft.get("request_id") or _digest([task["task_id"], task.get("selected_files"), task.get("original_request")])


def _patch_steps(task: Dict[str, Any], supplied: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    if supplied is not None:
        return deepcopy(supplied)
    approved = task.get("approval_state", {}).get("patch_steps")
    if approved:
        return deepcopy(approved)
    return deepcopy(task.get("patch_draft_result", {}).get("patch_steps", []))


def _approval_snapshot(
    task: Dict[str, Any],
    patch_id: str,
    patch_steps: List[Dict[str, Any]],
    approved_files: List[str],
    expected_hashes: Dict[str, str],
) -> Dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "patch_id": patch_id,
        "patch_digest": _digest({"patch_id": patch_id, "steps": patch_steps}),
        "approved_files": approved_files,
        "repository_root": task["repository_root"],
        "expected_file_hashes": expected_hashes,
        "patch_steps": patch_steps,
    }


def _approval_valid(task: Dict[str, Any]) -> Tuple[bool, str]:
    approval = task.get("approval_state", {})
    snapshot = approval.get("approval_snapshot") or {}
    if not approval.get("approved"):
        return False, "explicit task approval is required"
    current = _approval_snapshot(
        task,
        snapshot.get("patch_id", ""),
        _patch_steps(task),
        _unique(snapshot.get("approved_files", [])),
        dict(snapshot.get("expected_file_hashes", {})),
    )
    if current != snapshot:
        approval["approved"] = False
        approval["invalidated_reason"] = "approval-bound patch, file list, repository root, hashes, or steps changed"
        return False, approval["invalidated_reason"]
    return True, ""


def _pending_for_state(state: str) -> List[str]:
    order = [
        "route",
        "diagnose",
        "draft_patch",
        "approve_patch",
        "prepare_apply",
        "apply",
        "prepare_verification",
        "execute_verification",
        "review_recovery",
        "complete",
    ]
    completed_by_state = {
        "created": 0,
        "routed": 1,
        "diagnosis_ready": 2,
        "patch_ready": 3,
        "awaiting_approval": 3,
        "approval_verified": 4,
        "apply_prepared": 5,
        "applied": 6,
        "verification_prepared": 7,
        "verified": 9,
        "recovery_review": 9,
        "rollback_recommended": 9,
        "completed": 10,
    }
    return order[completed_by_state.get(state, 0) :]


def _summary(task: Dict[str, Any]) -> Dict[str, Any]:
    state = task["current_state"]
    can_advance = state not in EXECUTION_BLOCKED_STATES and state != "awaiting_approval"
    if state == "approval_verified":
        can_advance = True
    if state == "apply_prepared":
        can_advance = bool(task.get("approval_state", {}).get("apply_execution_approved"))
    if state == "verification_prepared":
        can_advance = bool(task.get("approval_state", {}).get("verification_execution_approved"))
    return {
        "task_id": task["task_id"],
        "current_state": state,
        "original_request": task["original_request"],
        "repository_root": task["repository_root"],
        "route_result": _redact(task.get("route_result", {})),
        "diagnosis_summary": _redact(task.get("diagnosis_result", {})),
        "patch_summary": _redact(task.get("patch_draft_result", {})),
        "approval_state": _redact(task.get("approval_state", {})),
        "apply_summary": _redact(task.get("apply_result", {})),
        "verification_summary": _redact(task.get("verification_result", {})),
        "recovery_summary": _redact(task.get("recovery_result", {})),
        "selected_files": list(task.get("selected_files", [])),
        "changed_files": list(task.get("changed_files", [])),
        "forbidden_files": list(task.get("forbidden_files", [])),
        "adjacent_findings": _redact(task.get("adjacent_findings", [])),
        "completed_steps": list(task.get("completed_steps", [])),
        "pending_steps": _pending_for_state(state),
        "blocked_reasons": list(task.get("blocked_reasons", [])),
        "next_safe_action": task.get("next_safe_action", ""),
        "persistence_status": dict(task.get("persistence_status", {})),
        "persistence_warning": task.get("persistence_warning", ""),
        "restored_from_persistence": bool(task.get("restored_from_persistence", False)),
        "requires_explicit_resume": bool(task.get("requires_explicit_resume", False)),
        "execution_triggered_on_restore": bool(task.get("execution_triggered_on_restore", False)),
        "permission_profile": _redact(task.get("permission_profile", {})),
        "safe_permission_metadata": _redact(task.get("safe_permission_metadata", {})),
        "permission_audit": _redact(task.get("permission_audit", [])),
        "last_permission_evaluation": _redact(task.get("last_permission_evaluation", {})),
        "scope_expansion_request": _redact(task.get("scope_expansion_request", {})),
        "terminal_runtime_plan": _redact(task.get("terminal_runtime_plan", {})),
        "terminal_runtime_result": _redact(task.get("terminal_runtime_result", {})),
        "live_test_plan": _redact(task.get("live_test_plan", {})),
        "live_test_result": _redact(task.get("live_test_result", {})),
        "network_access_plan": _redact(task.get("network_access_plan", {})),
        "network_access_result": _redact(task.get("network_access_result", {})),
        "can_advance": can_advance,
        "requires_user_approval": state in {"awaiting_approval", "apply_prepared", "verification_prepared"},
        **SAFE_INVARIANTS,
    }


def _touch(task: Dict[str, Any], state: Optional[str] = None, step: Optional[str] = None) -> Dict[str, Any]:
    if state:
        if state not in TASK_STATES:
            raise ValueError(f"invalid task state: {state}")
        task["current_state"] = state
    if step and step not in task["completed_steps"]:
        task["completed_steps"].append(step)
    task["updated_at"] = _now()
    task["pending_steps"] = _pending_for_state(task["current_state"])
    return task


def _block(task: Dict[str, Any], reason: str, state: str = "blocked") -> Dict[str, Any]:
    if reason not in task["blocked_reasons"]:
        task["blocked_reasons"].append(reason)
    task["next_safe_action"] = "Resolve blocked reason or cancel the task."
    return _touch(task, state)


def _operation_for_action(action: str, state: str) -> str:
    if action == "route" or (action == "next" and state == "created"):
        return "inspect"
    if action == "diagnose" or (action == "next" and state == "routed"):
        return "read"
    if action in {"draft", "patch"} or (action == "next" and state == "diagnosis_ready"):
        return "read"
    if action == "prepare_apply" or (action == "next" and state == "approval_verified"):
        return "edit_file"
    if action == "apply" or (action == "next" and state == "apply_prepared"):
        return "edit_file"
    if action == "prepare_verification" or (action == "next" and state == "applied"):
        return "run_validator"
    if action == "execute_verification" or (action == "next" and state == "verification_prepared"):
        return "run_validator"
    return "inspect"


def _target_for_operation(task: Dict[str, Any], operation: str) -> str:
    files = task.get("changed_files") or task.get("selected_files") or task.get("requested_files") or []
    return files[0] if files else ""


def _permission_check(task: Dict[str, Any], action: str) -> Tuple[bool, Dict[str, Any]]:
    profile = task.get("permission_profile")
    if not profile:
        return True, {}
    operation = _operation_for_action(action, task.get("current_state", "created"))
    target = _target_for_operation(task, operation)
    result = evaluate_requested_action(
        profile=profile,
        task_id=task.get("task_id", ""),
        operation=operation,
        target_path=target,
        metadata={
            "files_changed": max(1, len(task.get("changed_files", []))) if operation in {"edit_file", "refactor"} else 0,
            "validation_runs": len([step for step in task.get("completed_steps", []) if "verification" in step]),
            "scope_expansions": profile.get("scope_expansion_count", 0),
            "why_needed": "The task transition needs this selected file or folder.",
        },
        recovery_plan_available=True,
    )
    task.setdefault("permission_audit", []).append(result.get("audit", result))
    task["last_permission_evaluation"] = result
    if result.get("allowed"):
        return True, result
    task["previous_state_before_scope_pause"] = task.get("current_state", "created")
    if result.get("state") == "awaiting_scope_permission":
        task["scope_expansion_request"] = result.get("scope_request", {})
        task["next_safe_action"] = "Review the scope-expansion request before continuing."
        _touch(task, "awaiting_scope_permission")
    elif result.get("state") == "budget_exhausted":
        task["next_safe_action"] = result.get("reason", "Autonomy budget exhausted.")
        _touch(task, "budget_exhausted")
    elif result.get("state") == "awaiting_irreversible_confirmation":
        task["next_safe_action"] = "Review irreversible-action confirmation before continuing."
        _touch(task, "awaiting_irreversible_confirmation")
    else:
        task["next_safe_action"] = result.get("reason", "Permission approval is required before continuing.")
        _touch(task, "autonomy_paused")
    return False, result


def _persist_task(task: Dict[str, Any], event_type: str = "state_transition", previous_state: Optional[str] = None) -> None:
    if not _PERSISTENCE_CONFIG.get("enabled"):
        return
    result = save_task_state(
        task,
        expected_revision=task.get("persistence_revision"),
        mode=_PERSISTENCE_CONFIG.get("mode"),
        storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
        event_type=event_type,
        previous_state=previous_state,
    )
    task["persistence_status"] = {
        "enabled": True,
        "durable": bool(result.get("durable")),
        "last_save_ok": bool(result.get("ok") and result.get("saved", True)),
        "revision": result.get("revision", task.get("persistence_revision", 0)),
    }
    if result.get("ok") and result.get("revision") is not None:
        task["persistence_revision"] = int(result["revision"])
        task.pop("persistence_warning", None)
    elif not result.get("ok"):
        task["persistence_warning"] = result.get("error", "persistence save failed")
        task["next_safe_action"] = "Retry persistence save or continue with in-memory task state."


def _persist_and_summarize(task: Dict[str, Any], event_type: str = "state_transition", previous_state: Optional[str] = None) -> Dict[str, Any]:
    _persist_task(task, event_type=event_type, previous_state=previous_state)
    return _summary(task)


def _restore_payload_to_task(payload: Dict[str, Any]) -> Tuple[bool, str]:
    task_id = str(payload.get("task_id") or "")
    state = str(payload.get("current_state") or "")
    if not task_id:
        return False, "restored task_id missing"
    if state not in TASK_STATES:
        return False, "restored task state invalid"
    task = deepcopy(payload)
    task.setdefault("completed_steps", [])
    task.setdefault("blocked_reasons", [])
    task.setdefault("pending_steps", _pending_for_state(state))
    task.setdefault("safety_flags", dict(SAFE_INVARIANTS))
    task["restored_from_persistence"] = True
    task["requires_explicit_resume"] = True
    task["execution_triggered_on_restore"] = False
    _TASKS[task_id] = task
    return True, ""


def get_task_orchestrator_schema() -> Dict[str, Any]:
    return {
        "name": "LuxCode Task Orchestrator & Continuity Core",
        "status": "local_first_in_memory_mvp",
        "supported_states": sorted(TASK_STATES),
        "public_functions": [
            "get_task_orchestrator_schema",
            "create_luxcode_task",
            "advance_luxcode_task",
            "approve_luxcode_task_step",
            "cancel_luxcode_task",
            "resume_luxcode_task",
            "get_luxcode_task_status",
            "get_task_orchestrator_status",
            "configure_luxcode_task_persistence",
            "save_luxcode_task_to_persistence",
            "load_luxcode_task_from_persistence",
            "list_luxcode_persisted_tasks",
            "archive_luxcode_persisted_task",
            "delete_luxcode_persisted_task",
            "restore_luxcode_active_tasks",
            "approve_luxcode_task_scope_expansion",
            "revoke_luxcode_task_scope",
            "plan_luxcode_task_terminal_action",
            "execute_luxcode_task_terminal_action",
            "cancel_luxcode_task_terminal_runtime",
            "plan_luxcode_task_live_test",
            "execute_luxcode_task_live_test",
            "cancel_luxcode_task_live_test",
            "plan_luxcode_task_network_access",
            "execute_luxcode_task_network_access",
            "cancel_luxcode_task_network_access",
        ],
        "integrated_engines": [
            "LuxCode Master Router Preview",
            "Lux Debug Intelligence Core",
            "Safe Patch Draft Engine",
            "Approval-Gated Controlled Apply Engine",
            "Local Verification Execution & Recovery Engine",
        ],
        "state_storage": "in_memory_with_optional_local_persistence",
        "known_limitation": "persistence is disabled until explicitly initialized",
        "persistence": get_task_persistence_status(),
        "autonomy_permission": get_autonomy_permission_status(),
        "terminal_runtime": "available_for_structured_actions",
        "live_testing": "available_for_localhost_structured_scenarios",
        "network_access": "available_for_localhost_and_selected_lan_verification",
        "automatic_apply_enabled": False,
        "automatic_rollback_enabled": False,
        **SAFE_INVARIANTS,
    }


def create_luxcode_task(
    original_request: str = "",
    repository_root: Optional[str] = None,
    suspected_files: Optional[List[str]] = None,
    changed_files: Optional[List[str]] = None,
    mode: Optional[str] = None,
    traceback_text: str = "",
    selected_files: Optional[List[str]] = None,
    requested_files: Optional[List[str]] = None,
    forbidden_files: Optional[List[str]] = None,
    permission_mode: str = "approval_required",
    scope_items: Optional[List[Dict[str, Any]]] = None,
    selected_folders: Optional[List[str]] = None,
    autonomy_budgets: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    now = _now()
    root = _safe_root(repository_root)
    task_id = "lux-task-" + uuid.uuid4().hex[:16]
    files = _unique((selected_files or []) + (requested_files or []) + (suspected_files or []))
    task = {
        "task_id": task_id,
        "created_at": now,
        "updated_at": now,
        "current_state": "created",
        "original_request": original_request,
        "repository_root": root,
        "mode": mode or "plan",
        "traceback_text": traceback_text,
        "route_result": {},
        "diagnosis_result": {},
        "patch_draft_result": {},
        "approval_state": {"approved": False, "approval_events": []},
        "apply_result": {},
        "verification_result": {},
        "recovery_result": {},
        "selected_files": files,
        "changed_files": _unique(changed_files or []),
        "requested_files": _unique(requested_files or files),
        "forbidden_files": _unique((forbidden_files or []) + DEFAULT_FORBIDDEN_FILES),
        "adjacent_findings": [],
        "blocked_reasons": [],
        "completed_steps": [],
        "pending_steps": _pending_for_state("created"),
        "next_safe_action": "Advance to route the request.",
        "pause_reason": "",
        "cancellation_reason": "",
        "safety_flags": dict(SAFE_INVARIANTS),
    }
    permission = create_permission_profile(
        task_id=task_id,
        permission_mode=permission_mode,
        repository_root=root or str(Path.cwd()),
        command_text=original_request,
        scope_items=scope_items,
        selected_files=files,
        selected_folders=selected_folders or [],
        autonomy_budgets=autonomy_budgets,
    )
    if permission.get("ok"):
        task["permission_profile"] = permission["profile"]
        task["safe_permission_metadata"] = get_safe_permission_metadata(permission["profile"])
    else:
        task["permission_profile"] = {}
        task["permission_warning"] = permission.get("reason", "permission profile could not be created")
    _TASKS[task_id] = task
    return _persist_and_summarize(task, event_type="create")


def _advance_route(task: Dict[str, Any]) -> None:
    if "route" in task["completed_steps"]:
        return
    task["route_result"] = build_luxcode_master_router_preview(task["original_request"], context=task.get("mode") or "")
    task["next_safe_action"] = "Advance to read-only diagnosis."
    _touch(task, "routed", "route")


def _advance_diagnosis(task: Dict[str, Any]) -> None:
    if "diagnose" in task["completed_steps"]:
        return
    _touch(task, "diagnosing")
    diagnosis = analyze_lux_debug_request(
        issue_text=task["original_request"],
        traceback_text=task.get("traceback_text", ""),
        suspected_files=task.get("selected_files", []),
        changed_files=task.get("changed_files", []),
        repository_root=task.get("repository_root") or None,
        max_files=8,
        mode="full_debug_preview",
    )
    task["diagnosis_result"] = diagnosis
    task["adjacent_findings"] = _classify_adjacent(diagnosis.get("adjacent_issues", []))
    selected = [item.get("path") or item.get("file") for item in diagnosis.get("selected_context", []) if isinstance(item, dict)]
    task["selected_files"] = _unique(task.get("selected_files", []) + [item for item in selected if item])
    task["next_safe_action"] = "Advance to safe patch draft preview."
    _touch(task, "diagnosis_ready", "diagnose")


def _advance_patch(task: Dict[str, Any]) -> None:
    if "draft_patch" in task["completed_steps"]:
        return
    _touch(task, "patch_drafting")
    diagnosis = task.get("diagnosis_result", {})
    draft = build_safe_patch_draft(
        issue_summary=diagnosis.get("normalized_issue") or task["original_request"],
        root_cause_hypotheses=diagnosis.get("root_cause_hypotheses", []),
        selected_context=diagnosis.get("selected_context", []),
        requested_files=task.get("requested_files") or task.get("selected_files", []),
        forbidden_files=task.get("forbidden_files", []),
        repository_root=task.get("repository_root") or None,
        change_intent=task["original_request"],
        mode="preview",
        max_patch_files=4,
        max_hunks_per_file=3,
    )
    task["patch_draft_result"] = draft
    task["next_safe_action"] = "Review patch draft and submit exact approval before apply preparation."
    _touch(task, "awaiting_approval", "draft_patch")


def _prepare_apply(task: Dict[str, Any]) -> None:
    ok, reason = _approval_valid(task)
    if not ok:
        task["next_safe_action"] = "Review patch draft and submit exact approval before apply preparation."
        _block(task, reason, "awaiting_approval")
        return
    if "prepare_apply" in task["completed_steps"]:
        return
    approval = task["approval_state"]["approval_snapshot"]
    result = prepare_controlled_apply(
        repository_root=approval["repository_root"],
        patch_id=approval["patch_id"],
        patch_steps=approval["patch_steps"],
        approved_files=approval["approved_files"],
        forbidden_files=task.get("forbidden_files", []),
        expected_file_hashes=approval["expected_file_hashes"],
        mode="prepare",
        require_clean_tree=False,
    )
    task["apply_result"] = result
    task["next_safe_action"] = "Apply requires explicit apply_execution approval; no automatic apply occurs."
    _touch(task, "apply_prepared", "prepare_apply")


def _execute_apply(task: Dict[str, Any]) -> None:
    if "apply" in task["completed_steps"]:
        return
    ok, reason = _approval_valid(task)
    if not ok:
        _block(task, reason, "awaiting_approval")
        return
    if not task.get("approval_state", {}).get("apply_execution_approved"):
        _block(task, "apply execution requires explicit approval", "apply_prepared")
        return
    approval = task["approval_state"]["approval_snapshot"]
    _touch(task, "applying")
    result = execute_controlled_apply(
        repository_root=approval["repository_root"],
        patch_id=approval["patch_id"],
        patch_steps=approval["patch_steps"],
        approved_files=approval["approved_files"],
        forbidden_files=task.get("forbidden_files", []),
        approval_token=task["approval_state"].get("controlled_apply_approval_token"),
        expected_file_hashes=approval["expected_file_hashes"],
        mode="apply",
        require_clean_tree=False,
    )
    task["apply_result"] = result
    if result.get("transaction_state") == "applied":
        task["changed_files"] = _unique(task.get("changed_files", []) + result.get("files_changed", []))
        task["next_safe_action"] = "Advance to prepare verification."
        _touch(task, "applied", "apply")
    else:
        _block(task, "controlled apply did not complete", "blocked")


def _prepare_verification(task: Dict[str, Any]) -> None:
    if "prepare_verification" in task["completed_steps"]:
        return
    checks = task.get("verification_checks") or [
        {"check_type": "py_compile", "check_id": "compile_changed", "files": task.get("changed_files", [])[:5]},
        {"check_type": "git_diff_check", "check_id": "diff_check"},
    ]
    result = prepare_verification_run(
        repository_root=task.get("repository_root") or None,
        verification_id=_digest([task["task_id"], "verification"]),
        changed_files=task.get("changed_files", []),
        requested_checks=checks,
        mode="prepare",
        max_checks=4,
        timeout_seconds=20,
        controlled_apply_result=task.get("apply_result", {}),
    )
    task["verification_result"] = result
    task["next_safe_action"] = "Verification execution requires exact verification approval."
    _touch(task, "verification_prepared", "prepare_verification")


def _execute_verification(task: Dict[str, Any]) -> None:
    if "execute_verification" in task["completed_steps"]:
        return
    if not task.get("approval_state", {}).get("verification_execution_approved"):
        _block(task, "verification execution requires explicit approval", "verification_prepared")
        return
    prepared = task.get("verification_result", {})
    result = execute_verification_run(
        repository_root=task.get("repository_root") or None,
        verification_id=prepared.get("verification_id"),
        changed_files=task.get("changed_files", []),
        requested_checks=task.get("verification_checks") or [
            {"check_type": "py_compile", "check_id": "compile_changed", "files": task.get("changed_files", [])[:5]},
            {"check_type": "git_diff_check", "check_id": "diff_check"},
        ],
        approval_token=task["approval_state"].get("verification_approval_token"),
        mode="execute",
        max_checks=4,
        timeout_seconds=20,
        controlled_apply_result=task.get("apply_result", {}),
    )
    task["verification_result"] = result
    summary = result.get("summary", {})
    if summary.get("failed") or summary.get("timed_out") or summary.get("blocked"):
        task["recovery_result"] = prepare_recovery_action(
            repository_root=task.get("repository_root") or None,
            verification_id=result.get("verification_id"),
            changed_files=task.get("changed_files", []),
            controlled_apply_result=task.get("apply_result", {}),
            check_results=result.get("check_results", []),
            allow_automatic_rollback=False,
            mode="recovery_preview",
        )
        decision = task["recovery_result"].get("recovery_decision")
        if decision == "rollback_recommended":
            _touch(task, "rollback_recommended", "execute_verification")
        else:
            _touch(task, "recovery_review", "execute_verification")
        task["next_safe_action"] = task["recovery_result"].get("safe_next_step", "Review recovery result.")
    else:
        task["next_safe_action"] = "Task verified; no recovery needed."
        _touch(task, "completed", "execute_verification")


def advance_luxcode_task(
    task_id: str,
    action: str = "next",
    patch_steps: Optional[List[Dict[str, Any]]] = None,
    verification_checks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    if task["current_state"] in EXECUTION_BLOCKED_STATES:
        return _summary(task)
    previous_state = task["current_state"]
    allowed, _permission_result = _permission_check(task, action)
    if not allowed:
        return _persist_and_summarize(task, event_type=f"permission_pause:{action}", previous_state=previous_state)
    if patch_steps is not None:
        task["approval_state"]["patch_steps"] = deepcopy(patch_steps)
    if verification_checks is not None:
        task["verification_checks"] = deepcopy(verification_checks)
    state = task["current_state"]
    if action == "route" or (action == "next" and state == "created"):
        _advance_route(task)
    elif action == "diagnose" or (action == "next" and state == "routed"):
        _advance_diagnosis(task)
    elif action in {"draft", "patch"} or (action == "next" and state == "diagnosis_ready"):
        _advance_patch(task)
    elif action == "prepare_apply" or (action == "next" and state == "approval_verified"):
        _prepare_apply(task)
    elif action == "apply" or (action == "next" and state == "apply_prepared"):
        _execute_apply(task)
    elif action == "prepare_verification" or (action == "next" and state == "applied"):
        _prepare_verification(task)
    elif action == "execute_verification" or (action == "next" and state == "verification_prepared"):
        _execute_verification(task)
    else:
        _block(task, f"invalid transition from {state} via {action}")
    return _persist_and_summarize(task, event_type=f"advance:{action}", previous_state=previous_state)


def approve_luxcode_task_step(
    task_id: str,
    patch_id: Optional[str] = None,
    patch_digest: Optional[str] = None,
    approved_files: Optional[List[str]] = None,
    expected_file_hashes: Optional[Dict[str, str]] = None,
    patch_steps: Optional[List[Dict[str, Any]]] = None,
    repository_root: Optional[str] = None,
    approve_apply_execution: bool = False,
    controlled_apply_approval_token: Optional[str] = None,
    approve_verification_execution: bool = False,
    verification_approval_token: Optional[str] = None,
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    if task["current_state"] in EXECUTION_BLOCKED_STATES:
        return _summary(task)
    previous_state = task["current_state"]
    steps = _patch_steps(task, patch_steps)
    files = _unique(approved_files or [step.get("target_file") for step in steps if isinstance(step, dict)])
    hashes = dict(expected_file_hashes or _file_hashes(task["repository_root"], files))
    pid = patch_id or _make_patch_id(task)
    snapshot = _approval_snapshot(task, pid, steps, files, hashes)
    if repository_root and _safe_root(repository_root) != task["repository_root"]:
        _block(task, "approval repository root does not match task repository root", "awaiting_approval")
        return _persist_and_summarize(task, event_type="approval_blocked", previous_state=previous_state)
    if patch_digest and patch_digest != snapshot["patch_digest"]:
        _block(task, "approval patch digest does not match current patch", "awaiting_approval")
        return _persist_and_summarize(task, event_type="approval_blocked", previous_state=previous_state)
    task["approval_state"].update(
        {
            "approved": True,
            "approval_snapshot": snapshot,
            "patch_id": pid,
            "patch_digest": snapshot["patch_digest"],
            "approved_files": files,
            "expected_file_hashes": hashes,
            "patch_steps": steps,
            "apply_execution_approved": bool(approve_apply_execution),
            "controlled_apply_approval_token": controlled_apply_approval_token,
            "verification_execution_approved": bool(approve_verification_execution),
            "verification_approval_token": verification_approval_token,
        }
    )
    task["approval_state"].setdefault("approval_events", []).append({"approved_at": _now(), "patch_digest": snapshot["patch_digest"]})
    task["next_safe_action"] = "Advance to prepare controlled apply."
    _touch(task, "approval_verified", "approve_patch")
    return _persist_and_summarize(task, event_type="approve", previous_state=previous_state)


def cancel_luxcode_task(task_id: str, reason: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    previous_state = task["current_state"]
    task["cancellation_reason"] = reason
    task["next_safe_action"] = "Task cancelled; no execution transitions are allowed."
    _touch(task, "cancelled")
    return _persist_and_summarize(task, event_type="cancel", previous_state=previous_state)


def pause_luxcode_task(task_id: str, reason: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    if task["current_state"] in TERMINAL_STATES:
        return _summary(task)
    previous_state = task["current_state"]
    task["previous_state_before_pause"] = task["current_state"]
    task["pause_reason"] = reason
    task["next_safe_action"] = "Resume before any execution transition."
    _touch(task, "paused")
    return _persist_and_summarize(task, event_type="pause", previous_state=previous_state)


def resume_luxcode_task(task_id: str) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    if task["current_state"] != "paused":
        return _summary(task)
    previous_state = task["current_state"]
    prior = task.get("previous_state_before_pause") or "created"
    task["pause_reason"] = task.get("pause_reason", "")
    task["next_safe_action"] = "Continue from the next safe checkpoint."
    _touch(task, prior)
    return _persist_and_summarize(task, event_type="resume", previous_state=previous_state)


def get_luxcode_task_status(task_id: str) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    return _summary(task)


def get_task_orchestrator_status() -> Dict[str, Any]:
    states = [task["current_state"] for task in _TASKS.values()]
    return {
        "name": "LuxCode Task Orchestrator & Continuity Core",
        "status": "ready",
        "state_storage": "in_memory_with_optional_local_persistence",
        "known_limitation": "persistence is disabled until explicitly initialized",
        "persistence": {
            "enabled": bool(_PERSISTENCE_CONFIG.get("enabled")),
            **get_task_persistence_status(
                mode=_PERSISTENCE_CONFIG.get("mode"),
                storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
            ),
        },
        "autonomy_permission": get_autonomy_permission_status(),
        "terminal_runtime": "available_for_structured_actions",
        "live_testing": "available_for_localhost_structured_scenarios",
        "task_count": len(_TASKS),
        "active_task_count": sum(1 for state in states if state not in TERMINAL_STATES and state != "paused"),
        "paused_task_count": states.count("paused"),
        "blocked_task_count": states.count("blocked"),
        "completed_task_count": states.count("completed"),
        "available_endpoints": [
            "/luxcode-task/schema",
            "/luxcode-task/create",
            "/luxcode-task/advance",
            "/luxcode-task/approve",
            "/luxcode-task/pause",
            "/luxcode-task/resume",
            "/luxcode-task/cancel",
            "/luxcode-task/{task_id}",
            "/debug/luxcode-task-orchestrator-status",
        ],
        **SAFE_INVARIANTS,
    }


def configure_luxcode_task_persistence(mode: str = "disabled", storage_root: Optional[str] = None, privacy_mode: bool = True) -> Dict[str, Any]:
    result = initialize_task_store(mode=mode, storage_root=storage_root, privacy_mode=privacy_mode)
    _PERSISTENCE_CONFIG.update({"mode": mode, "storage_root": storage_root or "", "enabled": mode != "disabled"})
    return result


def save_luxcode_task_to_persistence(task_id: str, expected_revision: Optional[int] = None) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = save_task_state(
        task,
        expected_revision=expected_revision if expected_revision is not None else task.get("persistence_revision"),
        mode=_PERSISTENCE_CONFIG.get("mode"),
        storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
        event_type="manual_save",
    )
    if result.get("ok") and result.get("revision") is not None:
        task["persistence_revision"] = int(result["revision"])
        task.pop("persistence_warning", None)
    elif not result.get("ok"):
        task["persistence_warning"] = result.get("error", "persistence save failed")
    return result


def load_luxcode_task_from_persistence(task_id: str, include_deleted: bool = False) -> Dict[str, Any]:
    result = load_task_state(
        task_id=task_id,
        mode=_PERSISTENCE_CONFIG.get("mode"),
        storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
        include_deleted=include_deleted,
    )
    if not result.get("ok") or not result.get("found"):
        return result
    ok, error = _restore_payload_to_task(result["task"])
    if not ok:
        return {"ok": False, "error": error, **SAFE_INVARIANTS}
    return {"ok": True, "task": _summary(_TASKS[task_id]), "execution_triggered": False, **SAFE_INVARIANTS}


def list_luxcode_persisted_tasks(**kwargs: Any) -> Dict[str, Any]:
    return list_task_states(
        mode=_PERSISTENCE_CONFIG.get("mode"),
        storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
        **kwargs,
    )


def archive_luxcode_persisted_task(task_id: str, expected_revision: Optional[int] = None) -> Dict[str, Any]:
    return archive_task_state(
        task_id=task_id,
        mode=_PERSISTENCE_CONFIG.get("mode"),
        storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
        expected_revision=expected_revision,
    )


def delete_luxcode_persisted_task(
    task_id: str,
    hard_delete: bool = False,
    approval_token: str = "",
    confirmation_phrase: str = "",
) -> Dict[str, Any]:
    return delete_task_state(
        task_id=task_id,
        mode=_PERSISTENCE_CONFIG.get("mode"),
        storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
        hard_delete=hard_delete,
        approval_token=approval_token,
        confirmation_phrase=confirmation_phrase,
    )


def restore_luxcode_active_tasks(limit: int = 50) -> Dict[str, Any]:
    result = restore_active_tasks(
        mode=_PERSISTENCE_CONFIG.get("mode"),
        storage_root=_PERSISTENCE_CONFIG.get("storage_root"),
        limit=limit,
    )
    if not result.get("ok"):
        return result
    restored = []
    for payload in result.get("restored_tasks", []):
        ok, error = _restore_payload_to_task(payload)
        restored.append({"task_id": payload.get("task_id"), "restored": ok, "error": error, "execution_triggered": False})
    return {"ok": True, "restored_tasks": restored, "restored_count": len(restored), "execution_triggered": False, **SAFE_INVARIANTS}


def approve_luxcode_task_scope_expansion(
    task_id: str,
    requested_path: str,
    requested_operation: str = "read",
    approval_option: str = "allow_read_once",
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = approve_scope_expansion(
        profile=task.get("permission_profile", {}),
        requested_path=requested_path,
        requested_operation=requested_operation,
        approval_option=approval_option,
        repository_root=task.get("repository_root"),
    )
    if result.get("ok") and result.get("profile"):
        task["permission_profile"] = result["profile"]
        task["safe_permission_metadata"] = get_safe_permission_metadata(result["profile"])
        if task.get("current_state") == "awaiting_scope_permission":
            _touch(task, task.get("previous_state_before_scope_pause") or "created")
        task["next_safe_action"] = "Scope permission updated; explicitly advance to continue."
    return _persist_and_summarize(task, event_type="scope_permission_update")


def revoke_luxcode_task_scope(task_id: str, target_path: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = revoke_scope_access(profile=task.get("permission_profile", {}), target_path=target_path)
    if result.get("ok") and result.get("profile"):
        task["permission_profile"] = result["profile"]
        task["safe_permission_metadata"] = get_safe_permission_metadata(result["profile"])
        task["next_safe_action"] = "Scope access revoked immediately."
    return _persist_and_summarize(task, event_type="scope_permission_revoke")


def plan_luxcode_task_terminal_action(
    task_id: str,
    action_type: str,
    working_directory: str = ".",
    executable: str = "python",
    arguments: Optional[List[Any]] = None,
    timeout_seconds: int = 30,
    process_mode: str = "foreground",
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = plan_terminal_action(
        action_type=action_type,
        repository_root=task.get("repository_root") or str(Path.cwd()),
        working_directory=working_directory,
        executable=executable,
        arguments=arguments or [],
        timeout_seconds=timeout_seconds,
        process_mode=process_mode,
        permission_profile=task.get("permission_profile", {}),
        metadata={"task_id": task_id},
    )
    task["terminal_runtime_plan"] = result.get("plan", result)
    return _persist_and_summarize(task, event_type="terminal_runtime_plan")


def execute_luxcode_task_terminal_action(task_id: str, approval_digest: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = execute_terminal_action(task.get("terminal_runtime_plan", {}), approval_digest=approval_digest)
    if result.get("runtime"):
        task["terminal_runtime_result"] = get_safe_runtime_metadata(result["runtime"])
    else:
        task["terminal_runtime_result"] = result
    return _persist_and_summarize(task, event_type="terminal_runtime_execute")


def cancel_luxcode_task_terminal_runtime(task_id: str, runtime_id: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = cancel_terminal_runtime(task_id=task_id, runtime_id=runtime_id)
    task["terminal_runtime_result"] = result
    return _persist_and_summarize(task, event_type="terminal_runtime_cancel")


def plan_luxcode_task_live_test(
    task_id: str,
    scenario: Dict[str, Any],
    working_directory: str = ".",
    service: Optional[Dict[str, Any]] = None,
    approval_digest: str = "",
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    scenario = dict(scenario or {})
    scenario.setdefault("task_id", task_id)
    result = plan_live_test(
        scenario=scenario,
        repository_root=task.get("repository_root") or str(Path.cwd()),
        working_directory=working_directory,
        permission_profile=task.get("permission_profile", {}),
        service=service,
        approval_digest=approval_digest,
    )
    task["live_test_plan"] = result.get("plan", result)
    return _persist_and_summarize(task, event_type="live_test_plan")


def execute_luxcode_task_live_test(task_id: str, approval_digest: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = execute_live_test(task.get("live_test_plan", {}), approval_digest=approval_digest)
    if result.get("runtime"):
        task["live_test_result"] = get_safe_live_test_metadata(result["runtime"])
    else:
        task["live_test_result"] = result
    return _persist_and_summarize(task, event_type="live_test_execute")


def cancel_luxcode_task_live_test(task_id: str, runtime_id: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    target_runtime = runtime_id or task.get("live_test_result", {}).get("live_test_runtime_id") or task.get("live_test_plan", {}).get("live_test_runtime_id", "")
    result = cancel_live_test_runtime(target_runtime, reason=f"task {task_id} cancelled")
    task["live_test_result"] = result.get("runtime", result)
    return _persist_and_summarize(task, event_type="live_test_cancel")


def plan_luxcode_task_network_access(
    task_id: str,
    bind_host: str = "127.0.0.1",
    port: int = 0,
    working_directory: str = ".",
    service: Optional[Dict[str, Any]] = None,
    selected_lan_ip: str = "",
    approval_digest: str = "",
) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = create_network_access_plan(
        task_id=task_id,
        repository_root=task.get("repository_root") or str(Path.cwd()),
        working_directory=working_directory,
        bind_host=bind_host,
        port=port,
        permission_profile=task.get("permission_profile", {}),
        service=service,
        selected_lan_ip=selected_lan_ip,
        approval_digest=approval_digest,
    )
    task["network_access_plan"] = result.get("plan", result)
    return _persist_and_summarize(task, event_type="network_access_plan")


def execute_luxcode_task_network_access(task_id: str) -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    result = execute_network_access_plan(task.get("network_access_plan", {}))
    if result.get("runtime"):
        task["network_access_result"] = get_safe_network_access_metadata(result["runtime"])
    else:
        task["network_access_result"] = result
    return _persist_and_summarize(task, event_type="network_access_execute")


def cancel_luxcode_task_network_access(task_id: str, runtime_id: str = "") -> Dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        return {"ok": False, "task_id": task_id, "found": False, "safe_response": True, **SAFE_INVARIANTS}
    target_runtime = runtime_id or task.get("network_access_result", {}).get("network_access_runtime_id") or task.get("network_access_plan", {}).get("network_access_runtime_id", "")
    result = cancel_network_access_runtime(target_runtime, reason=f"task {task_id} cancelled")
    task["network_access_result"] = result.get("runtime", result)
    return _persist_and_summarize(task, event_type="network_access_cancel")
