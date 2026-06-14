from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Dict, List, Optional, Tuple


TASK_STATES = {
    "created",
    "classified",
    "assigned",
    "acknowledged",
    "in_progress",
    "partially_complete",
    "blocked",
    "handoff_required",
    "verification_pending",
    "verification_failed",
    "completed",
    "rejected",
    "reopened",
    "cancelled",
}

ASSIGNMENT_STATES = {
    "prepared",
    "offered",
    "acknowledged",
    "active",
    "paused",
    "blocked",
    "completed",
    "rejected",
    "expired",
    "handed_off",
    "cancelled",
}

WORKFLOW_STATES = {
    "attempted",
    "accepted",
    "completed",
    "rejected",
}

PROGRESS_TYPES = {
    "started",
    "inspection_complete",
    "implementation_started",
    "implementation_progress",
    "validation_started",
    "validation_progress",
    "blocked",
    "partial_completion",
    "handoff_prepared",
    "verification_complete",
    "completed",
}

OWNERSHIP_MODES = {"read", "write", "exclusive_write"}
OWNERSHIP_STATES = {"requested", "active", "released", "expired", "conflicted", "cancelled"}
OWNERSHIP_FILE_LIMIT = 200

EVIDENCE_TYPES = {
    "inspection",
    "code_change",
    "test_result",
    "validator_result",
    "smoke_result",
    "behavioral_result",
    "failure",
    "warning",
    "decision",
    "handoff",
    "finality",
    "user_feedback",
}

RESULT_STATUSES = {"pass", "fail", "partial", "blocked", "warning", "unknown"}
FAILURE_CATEGORIES = {
    "syntax_error",
    "import_error",
    "validation_failure",
    "smoke_failure",
    "behavioral_failure",
    "missing_capability",
    "resource_pressure",
    "quota_exhausted",
    "authentication_failure",
    "file_conflict",
    "scope_violation",
    "protected_surface_violation",
    "unknown_failure",
}

HandoffDecision = ["partial", "rejected", "completed", "handoff_required"]
FinalityDecision = {"complete", "partial", "blocked", "handoff_required", "verification_required", "rejected", "cancelled"}
ReopenReason = {"new_evidence", "user_rejection", "regression_detected", "new_failure", "acceptance_mismatch"}
TaskVerificationType = {"technical", "behavioral"}


TASK_CONTRACTS: Dict[str, Dict[str, Any]] = {}
ASSIGNMENTS: Dict[str, Dict[str, Any]] = {}
ACKS: Dict[str, Dict[str, Any]] = {}
PROGRESS_EVENTS: Dict[str, List[Dict[str, Any]]] = {}
ATTEMPT_REGISTRY: Dict[str, Dict[str, Any]] = {}
FAILURE_SIGS: Dict[str, Dict[str, Any]] = {}
PARTIAL_COMPLETIONS: Dict[str, Dict[str, Any]] = {}
GAPS: Dict[str, Dict[str, Any]] = {}
HANDOFFS: Dict[str, Dict[str, Any]] = {}
OWNERSHIPS: Dict[str, Dict[str, Any]] = {}
VERIFICATIONS: Dict[str, Dict[str, Any]] = {}
FINALITY: Dict[str, Dict[str, Any]] = {}
REOPEN: Dict[str, Dict[str, Any]] = {}
TASK_EVENTS: Dict[str, List[Dict[str, Any]]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any, prefix: str = "lux") -> str:
    return prefix + "-" + sha256(_stable_json(value).encode("utf-8")).hexdigest()[:24]


def _normalize_text(value: Any, limit: int = 2400) -> str:
    return (str(value or "").replace("\x00", "").strip())[:limit]


def _normalize_list(values: Any, limit: int = 50) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        items = [values]
    elif isinstance(values, (list, tuple, set)):
        items = [str(v) for v in values]
    else:
        items = [str(values)]
    out: List[str] = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        out.append(text)
        seen.add(text)
        if len(out) >= limit:
            break
    return out


def _normalize_file_list(values: Any, limit: int = 120) -> List[str]:
    files = _normalize_list(values, limit=limit * 2)
    out: List[str] = []
    for path in files:
        normalized = path.replace("\\", "/").strip()
        if normalized.startswith("../") or "/../" in f"/{normalized}/":
            continue
        if normalized.lower() == ".env" or normalized.endswith("/.env"):
            continue
        if normalized and normalized not in out:
            out.append(normalized)
        if len(out) >= limit:
            break
    return out


def _normalize_symbol_list(values: Any, limit: int = 120) -> List[str]:
    symbols = _normalize_list(values, limit=limit * 2)
    return [sym.strip() for sym in symbols if sym.strip()][:limit]


def _safe(task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {
        "task_id": str(task_id),
        **{
            key: payload.get(key)
            for key in [
                "state",
                "task_contract_digest",
                "active_assignment_id",
                "active_worker_engine_id",
                "assignment_state",
                "evidence_board_digest",
                "latest_progress_event_id",
                "attempt_fingerprints",
                "failure_signatures",
                "partial_completion_digest",
                "remaining_gap_digest",
                "active_handoff_id",
                "file_ownership_state",
                "technical_verification_state",
                "behavioral_verification_state",
                "finality_state",
                "reopen_state",
                "multi_agent_updated_at",
            ]
        },
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def get_multi_agent_handoff_schema() -> Dict[str, Any]:
    return {
        "name": "LuxCode Multi-Agent Handoff & Evidence Board Foundation",
        "status": "ready",
        "layer": "multi_agent_handoff",
        "supported_task_states": sorted(TASK_STATES),
        "supported_assignment_states": sorted(ASSIGNMENT_STATES),
        "supported_evidence_types": sorted(EVIDENCE_TYPES),
        "supported_result_statuses": sorted(RESULT_STATUSES),
        "supported_failure_categories": sorted(FAILURE_CATEGORIES),
        "supported_ownership_modes": sorted(OWNERSHIP_MODES),
        "supported_ownership_states": sorted(OWNERSHIP_STATES),
        "public_functions": [
            "create_multi_agent_task_contract",
            "create_work_assignment",
            "record_worker_acknowledgement",
            "record_progress_event",
            "add_evidence_record",
            "check_attempt_fingerprint",
            "prepare_handoff",
            "accept_handoff",
            "set_technical_verification_result",
            "set_behavioral_verification_result",
            "set_finality_decision",
            "request_reopen",
            "extract_remaining_gap",
            "register_file_ownership",
            "get_multi_agent_status",
            "get_multi_agent_handoff_schema",
            "get_multi_agent_handoff_registry",
        ],
        "required_endpoints": [
            "/luxcode-multi-agent/schema",
            "/luxcode-multi-agent/registry",
            "/luxcode-multi-agent/task-contract",
            "/luxcode-multi-agent/work-assignment",
            "/luxcode-multi-agent/evidence",
            "/luxcode-multi-agent/progress",
            "/luxcode-multi-agent/attempt-check",
            "/luxcode-multi-agent/handoff",
            "/luxcode-multi-agent/finality",
            "/debug/luxcode-multi-agent-status",
        ],
        "read_only": True,
        "approval_required": True,
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
        "runtime_started": False,
        "runtime_restarted": False,
        "worker_execution_started": False,
        "paid_escalation": {
            "allowed_automatically": False,
            "approved_only": True,
            "external_api_required": False,
        },
        "multi_agent_router_policy_fields": [
            "router_policy_version",
            "task_class",
            "difficulty_score",
            "risk_level",
            "required_capabilities",
            "selected_engine",
            "selected_tier",
            "fallback_chain",
            "skipped_engines",
            "route_decision_digest",
            "paid_escalation_required",
            "paid_escalation_allowed",
            "routing_state",
        ],
    }


def get_multi_agent_handoff_registry() -> Dict[str, Any]:
    return {
        "name": "LuxCode Multi-Agent Handoff & Evidence Board Registry",
        "status": "ready",
        "layer": "multi_agent_handoff",
        "schemas": ["luxcode-multi-agent"],
        "endpoints": [
            "/luxcode-multi-agent/schema",
            "/luxcode-multi-agent/registry",
            "/luxcode-multi-agent/task-contract",
            "/luxcode-multi-agent/work-assignment",
            "/luxcode-multi-agent/evidence",
            "/luxcode-multi-agent/progress",
            "/luxcode-multi-agent/attempt-check",
            "/luxcode-multi-agent/handoff",
            "/luxcode-multi-agent/finality",
            "/debug/luxcode-multi-agent-status",
        ],
        "endpoint_count": 10,
        "contract_states": sorted(TASK_STATES),
        "assignment_states": sorted(ASSIGNMENT_STATES),
        "progress_states": ["started", "inspection_complete", "implementation_started", "implementation_progress", "validation_started", "validation_progress", "blocked", "partial_completion", "handoff_prepared", "verification_complete", "completed"],
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def _build_task_contract_digest(payload: Dict[str, Any]) -> str:
    stable_contract = {
        "task_version": payload.get("task_version", "v1"),
        "parent_task_id": payload.get("parent_task_id", ""),
        "root_task_id": payload.get("root_task_id", ""),
        "task_title": payload.get("task_title", ""),
        "task_summary": payload.get("task_summary", ""),
        "task_class": payload.get("task_class", ""),
        "risk_level": payload.get("risk_level", ""),
        "priority": payload.get("priority", ""),
        "required_capabilities": sorted(_normalize_list(payload.get("required_capabilities", []), limit=80)),
        "allowed_files": sorted(_normalize_file_list(payload.get("allowed_files", []), limit=200)),
        "protected_files": sorted(_normalize_file_list(payload.get("protected_files", []), limit=80)),
        "acceptance_criteria": sorted(_normalize_list(payload.get("acceptance_criteria", []), limit=80)),
        "technical_acceptance_criteria": sorted(_normalize_list(payload.get("technical_acceptance_criteria", []), limit=80)),
        "behavioral_acceptance_criteria": sorted(_normalize_list(payload.get("behavioral_acceptance_criteria", []), limit=80)),
        "router_decision_digest": payload.get("router_decision_digest", ""),
    }
    return _digest({"contract": stable_contract, "scope": "contract"}, prefix="ma-contract")


def _build_work_assignment_digest(payload: Dict[str, Any]) -> str:
    return _digest({"assignment": payload, "scope": "assignment"}, prefix="ma-assignment")


def _build_progress_digest(payload: Dict[str, Any]) -> str:
    return _digest({"progress": payload, "scope": "progress"}, prefix="ma-progress")


def _build_attempt_fingerprint(payload: Dict[str, Any]) -> str:
    normalized = {
        "task_id": payload.get("task_id", ""),
        "worker_engine_id": payload.get("worker_engine_id", ""),
        "hypothesis": _normalize_text(str(payload.get("hypothesis", "")), limit=300),
        "target_files": _normalize_file_list(payload.get("target_files", []), limit=120),
        "target_symbols": _normalize_symbol_list(payload.get("target_symbols", []), limit=120),
        "command_family": _normalize_text(payload.get("command_family", ""), limit=120),
        "patch_intent": _normalize_text(payload.get("patch_intent", ""), limit=240),
        "failure_signature": _normalize_text(payload.get("failure_signature", ""), limit=260),
    }
    return _digest(normalized, prefix="ma-attempt")


def _validate_contract_required_fields(payload: Dict[str, Any]) -> Tuple[bool, str]:
    required_fields = ["task_title", "task_summary", "task_class", "risk_level", "priority", "required_capabilities"]
    for field in required_fields:
        if not str(payload.get(field, "")).strip():
            return False, f"required field missing: {field}"
    if not (payload.get("allowed_files") or payload.get("protected_files")):
        return False, "allowed_files or protected_files is required"
    if not _normalize_list(payload.get("technical_acceptance_criteria")):
        return False, "technical acceptance criteria must not be empty"
    if not _normalize_list(payload.get("behavioral_acceptance_criteria")):
        return False, "behavioral acceptance criteria must not be empty"
    return True, ""


def _task_contract_conflict(task_id: str, assignment_id: str, files: List[str]) -> bool:
    if not files:
        return False
    for existing in ASSIGNMENTS.values():
        if (
            existing.get("task_id") != task_id
            or existing.get("assignment_id") == assignment_id
            or existing.get("assignment_state") not in {"active", "prepared", "offered", "acknowledged"}
        ):
            continue
        ownership = set(_normalize_file_list(existing.get("owned_files", [])))
        if any(file in ownership for file in files):
            return True
    return False


def _conflict_with_active_ownership(task_id: str, assignment_id: str, files: List[str]) -> bool:
    if not files:
        return False
    for existing in OWNERSHIPS.values():
        if existing.get("task_id") != task_id or existing.get("assignment_id") == assignment_id:
            continue
        if existing.get("ownership_state") != "active":
            continue
        if existing.get("ownership_mode") != "exclusive_write":
            continue
        if set(_normalize_file_list(existing.get("owned_files", [])) ) & set(files):
            return True
    return False


def create_multi_agent_task_contract(**payload: Any) -> Dict[str, Any]:
    task_id = _normalize_text(payload.get("task_id", payload.get("existing_task_id", "")), limit=180) or _digest(
        {
            "title": payload.get("task_title", ""),
            "summary": payload.get("task_summary", ""),
            "request": payload.get("task_request_digest", ""),
        },
        prefix="ma-task",
    )
    task_version = _normalize_text(payload.get("task_version", "v1"), limit=80)
    parent_task_id = _normalize_text(payload.get("parent_task_id", ""), limit=180)
    root_task_id = _normalize_text(payload.get("root_task_id", task_id), limit=180)
    if parent_task_id and parent_task_id not in TASK_CONTRACTS:
        return {
            "ok": False,
            "error": "parent task does not exist",
            "task_id": task_id,
            "external_api_used": False,
            "network_access_used": False,
            "shell_execution_used": False,
            "local_first": True,
        }

    now = _now()
    data = {
        "task_id": task_id,
        "task_version": task_version,
        "parent_task_id": parent_task_id,
        "root_task_id": root_task_id,
        "task_title": _normalize_text(payload.get("task_title", ""), limit=800),
        "task_summary": _normalize_text(payload.get("task_summary", ""), limit=1200),
        "task_class": _normalize_text(payload.get("task_class", ""), limit=120),
        "risk_level": _normalize_text(payload.get("risk_level", "low"), limit=80),
        "priority": _normalize_text(payload.get("priority", "medium"), limit=80),
        "required_capabilities": _normalize_list(payload.get("required_capabilities", []), limit=80),
        "allowed_files": _normalize_file_list(payload.get("allowed_files", []), limit=200),
        "protected_files": _normalize_file_list(payload.get("protected_files", []), limit=80),
        "acceptance_criteria": _normalize_list(payload.get("acceptance_criteria", []), limit=80),
        "technical_acceptance_criteria": _normalize_list(payload.get("technical_acceptance_criteria", []), limit=80),
        "behavioral_acceptance_criteria": _normalize_list(payload.get("behavioral_acceptance_criteria", []), limit=80),
        "router_decision_digest": _normalize_text(payload.get("router_decision_digest", ""), limit=400),
        "created_at": now,
        "updated_at": now,
        "task_state": "created",
        "task_contract_digest": "",
        "router_metadata": dict(payload.get("router_metadata") or {}),
        "task_contract": dict(payload.get("task_contract", {})),
        "multi_agent_events": [],
        "active_assignment_id": "",
        "active_worker_engine_id": "",
        "assignment_state": "",
        "evidence_board_digest": "",
        "latest_progress_event_id": "",
        "attempt_fingerprints": [],
        "failure_signatures": [],
        "partial_completion_digest": "",
        "remaining_gap_digest": "",
        "active_handoff_id": "",
        "file_ownership_state": "",
        "technical_verification_state": "",
        "behavioral_verification_state": "",
        "finality_state": "",
        "reopen_state": "",
        "multi_agent_updated_at": now,
    }

    if set(data["allowed_files"]) & set(data["protected_files"]):
        return {
            "ok": False,
            "error": "allowed and protected files overlap",
            "task_id": task_id,
            "external_api_used": False,
            "network_access_used": False,
            "shell_execution_used": False,
            "local_first": True,
        }

    valid, reason = _validate_contract_required_fields(data)
    if not valid:
        return {
            "ok": False,
            "error": reason,
            "task_id": task_id,
            "external_api_used": False,
            "network_access_used": False,
            "shell_execution_used": False,
            "local_first": True,
        }

    digest = _build_task_contract_digest(data)
    data["task_contract_digest"] = digest
    if "completed" in TASK_CONTRACTS.get(task_id, {}).get("task_state", ""):
        return {
            "ok": False,
            "error": "completed task cannot be recreated",
            "task_id": task_id,
            "external_api_used": False,
            "network_access_used": False,
            "shell_execution_used": False,
            "local_first": True,
        }
    TASK_CONTRACTS[task_id] = data
    TASK_EVENTS.setdefault(task_id, []).append({
        "event_type": "task_contract_created",
        "task_id": task_id,
        "created_at": now,
        "event_digest": _digest({"event": "task_contract_created", "task_id": task_id, "time": now}, prefix="ma-event"),
    })
    return {
        "ok": True,
        "task_id": task_id,
        "task_version": task_version,
        "task_state": "created",
        "task_contract_digest": digest,
        "task_contract": _safe(task_id, data),
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def create_work_assignment(**payload: Any) -> Dict[str, Any]:
    task_id = _normalize_text(payload.get("task_id", ""), limit=180)
    contract = TASK_CONTRACTS.get(task_id)
    if not contract:
        return {
            "ok": False,
            "error": "task_contract_not_found",
            "external_api_used": False,
            "network_access_used": False,
            "shell_execution_used": False,
            "local_first": True,
        }
    if contract.get("task_state") == "completed":
        return {
            "ok": False,
            "error": "completed task cannot accept assignment",
            "task_id": task_id,
            "external_api_used": False,
            "network_access_used": False,
            "shell_execution_used": False,
            "local_first": True,
        }

    assignment_id = _normalize_text(
        payload.get("assignment_id"),
        limit=200,
    ) or _digest({"task_id": task_id, "worker": payload.get("worker_engine_id", ""), "scope": _normalize_text(payload.get("assignment_scope", ""))}, prefix="ma-assign")
    worker_engine_id = _normalize_text(payload.get("worker_engine_id", ""), limit=180)
    if not worker_engine_id:
        return {
            "ok": False,
            "error": "worker_engine_id required",
            "task_id": task_id,
            "external_api_used": False,
            "network_access_used": False,
            "shell_execution_used": False,
            "local_first": True,
        }

    worker_tier = _normalize_text(payload.get("worker_tier", ""), limit=80)
    worker_role = _normalize_text(payload.get("worker_role", "worker"), limit=80)
    assignment_scope = _normalize_text(payload.get("assignment_scope", ""), limit=2400)
    allowed_files = _normalize_file_list(payload.get("allowed_files", []), limit=200)
    owned_files = _normalize_file_list(payload.get("owned_files", []), limit=200)
    required_capabilities = _normalize_list(payload.get("required_capabilities", []), limit=80)

    now = _now()

    if not assignment_scope:
        return {"ok": False, "error": "assignment_scope required", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    if not allowed_files and not owned_files:
        return {"ok": False, "error": "allowed_files or owned_files required", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    if not (payload.get("expected_outputs") is None):
        expected_outputs = _normalize_list(payload.get("expected_outputs"), limit=120)
    else:
        expected_outputs = []

    if any(file in contract.get("protected_files", []) for file in owned_files + allowed_files):
        return {
            "ok": False,
            "error": "protected files cannot be assigned",
            "task_id": task_id,
            "external_api_used": False,
            "network_access_used": False,
            "shell_execution_used": False,
            "local_first": True,
        }

    existing_task_assignment = contract.get("active_assignment_id")
    if existing_task_assignment and ASSIGNMENTS.get(existing_task_assignment, {}).get("assignment_state") in {"active", "acknowledged", "offered", "prepared"}:
        return {"ok": False, "error": "only one active assignment allowed per task", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    files_to_watch = _normalize_file_list(owned_files + allowed_files, limit=OWNERSHIP_FILE_LIMIT)
    if _task_contract_conflict(task_id, assignment_id, files_to_watch) or _conflict_with_active_ownership(task_id, assignment_id, files_to_watch):
        return {"ok": False, "error": "file ownership conflict", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    assignment_state = _normalize_text(payload.get("assignment_state", "prepared"), limit=80)
    if assignment_state not in ASSIGNMENT_STATES:
        assignment_state = "prepared"

    if payload.get("acknowledgement_required", True):
        assignment_state = "offered" if assignment_state == "prepared" else assignment_state

    expires_at = _normalize_text(payload.get("expires_at", ""), limit=80)
    assignment = {
        "assignment_id": assignment_id,
        "task_id": task_id,
        "worker_engine_id": worker_engine_id,
        "worker_tier": worker_tier or "standard",
        "worker_role": worker_role,
        "assignment_scope": assignment_scope,
        "allowed_files": allowed_files,
        "owned_files": owned_files,
        "required_capabilities": required_capabilities,
        "expected_outputs": expected_outputs,
        "started_at": now,
        "expires_at": expires_at,
        "assignment_state": assignment_state,
        "acknowledgement_required": bool(payload.get("acknowledgement_required", True)),
        "expected_capability_state": bool(payload.get("expected_capability_state", True)),
        "resource_constraints": _normalize_text(payload.get("resource_constraints", ""), limit=500),
        "estimated_risk": _normalize_text(payload.get("estimated_risk", ""), limit=200),
        "acknowledgement_required_scope": [],
        "acknowledgement_rejected_scope": [],
        "acknowledged_at": "",
        "worker_assignment_digest": "",
    }
    assignment["worker_assignment_digest"] = _build_work_assignment_digest(assignment)
    ASSIGNMENTS[assignment_id] = assignment
    register_file_ownership(
        task_id=task_id,
        assignment_id=assignment_id,
        worker_engine_id=worker_engine_id,
        file_path=files_to_watch,
        ownership_mode="exclusive_write",
        ownership_state="active",
    )
    contract["active_assignment_id"] = assignment_id
    contract["active_worker_engine_id"] = worker_engine_id
    contract["assignment_state"] = assignment_state
    contract["task_state"] = "assigned"
    contract["multi_agent_updated_at"] = now
    TASK_EVENTS.setdefault(task_id, []).append({
        "event_type": "assignment_created",
        "task_id": task_id,
        "assignment_id": assignment_id,
        "created_at": now,
        "event_digest": _digest({"event": "assignment_created", "task_id": task_id, "assignment_id": assignment_id, "time": now}, prefix="ma-event"),
    })

    return {
        "ok": True,
        "task_id": task_id,
        "assignment_id": assignment_id,
        "assignment_state": assignment_state,
        "worker_engine_id": worker_engine_id,
        "owned_files": files_to_watch,
        "assignment_digest": assignment["worker_assignment_digest"],
        "task_contract_digest": contract["task_contract_digest"],
        "task_contract": _safe(task_id, contract),
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def record_worker_acknowledgement(**payload: Any) -> Dict[str, Any]:
    assignment_id = _normalize_text(payload.get("assignment_id", ""), limit=180)
    assignment = ASSIGNMENTS.get(assignment_id)
    if not assignment:
        return {"ok": False, "error": "assignment_not_found", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    task_id = assignment.get("task_id")
    if not task_id:
        return {"ok": False, "error": "invalid assignment", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    contract = TASK_CONTRACTS.get(task_id)
    if not contract:
        return {"ok": False, "error": "task_not_found", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    if assignment.get("assignment_state") in {"completed", "rejected", "cancelled", "expired"}:
        return {"ok": False, "error": "assignment_inactive", "assignment_id": assignment_id, "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    accepted_scope = _normalize_list(payload.get("accepted_scope", []), limit=120)
    rejected_scope = _normalize_list(payload.get("rejected_scope", []), limit=120)
    missing_capabilities = _normalize_list(payload.get("missing_capabilities", []), limit=80)
    resource_constraints = _normalize_text(payload.get("resource_constraints", ""), limit=400)
    ack_scope = [item for item in assignment["owned_files"] if item in accepted_scope] if accepted_scope else assignment["owned_files"]
    if not ack_scope:
        ack_scope = []

    ack = {
        "acknowledgement_id": _digest({"assignment_id": assignment_id, "task_id": task_id, "accepted_scope": ack_scope, "ts": _now()}, prefix="ma-ack"),
        "assignment_id": assignment_id,
        "worker_engine_id": assignment.get("worker_engine_id", ""),
        "accepted": bool(payload.get("accepted", False)),
        "accepted_scope": _normalize_file_list(accepted_scope, limit=160),
        "rejected_scope": _normalize_file_list(rejected_scope, limit=160),
        "missing_capabilities": missing_capabilities,
        "resource_constraints": resource_constraints,
        "estimated_risk": _normalize_text(payload.get("estimated_risk", ""), limit=200),
        "acknowledgement_digest": _digest({
            "assignment_id": assignment_id,
            "worker_engine_id": assignment.get("worker_engine_id", ""),
            "accepted_scope": _normalize_file_list(accepted_scope, limit=80),
            "rejected_scope": _normalize_file_list(rejected_scope, limit=80),
            "missing_capabilities": missing_capabilities,
        }, prefix="ma-acksum"),
        "acknowledged_at": _now(),
    }
    assignment["acknowledgement_required"] = False
    if ack["accepted"]:
        if not accepted_scope and accepted_scope is not None and bool(rejected_scope):
            assignment["acknowledgement_rejected_scope"] = _normalize_file_list(rejected_scope, limit=120)
        assignment["assignment_state"] = "acknowledged"
        contract["task_state"] = "acknowledged"
        contract["active_worker_engine_id"] = assignment.get("worker_engine_id", "")
    else:
        assignment["assignment_state"] = "rejected"
        contract["task_state"] = "blocked"
    assignment["acknowledgement_required_scope"] = _normalize_file_list(ack_scope, limit=160)
    assignment["acknowledged_at"] = ack["acknowledged_at"]
    assignment["acknowledgement_digest"] = ack["acknowledgement_digest"]
    contract["multi_agent_updated_at"] = ack["acknowledged_at"]
    ACKS[ack["acknowledgement_id"]] = ack
    TASK_EVENTS.setdefault(task_id, []).append({
        "event_type": "assignment_acknowledged" if ack["accepted"] else "assignment_rejected",
        "task_id": task_id,
        "assignment_id": assignment_id,
        "created_at": ack["acknowledged_at"],
        "event_digest": _digest({"event": "ack", "assignment_id": assignment_id, "accepted": ack["accepted"], "time": ack["acknowledged_at"]}, prefix="ma-event"),
    })
    return {
        "ok": True,
        "task_id": task_id,
        "assignment_id": assignment_id,
        "accepted": ack["accepted"],
        "acknowledgement": ack,
        "assignment_state": assignment["assignment_state"],
        "task_contract": _safe(task_id, contract),
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def add_evidence_record(**payload: Any) -> Dict[str, Any]:
    from luxcode_evidence_board import add_evidence_record as _board_add
    from luxcode_evidence_board import get_task_evidence as _task_evidence

    task_id = _normalize_text(payload.get("task_id", ""), limit=180)
    contract = TASK_CONTRACTS.get(task_id)
    if not contract:
        return {"ok": False, "error": "task_not_found", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    assignment_id = _normalize_text(payload.get("assignment_id", ""), limit=180)
    assignment = ASSIGNMENTS.get(assignment_id)
    if assignment_id and (not assignment or assignment.get("task_id") != task_id):
        return {"ok": False, "error": "assignment_not_found", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    if payload.get("evidence_type") not in EVIDENCE_TYPES:
        return {"ok": False, "error": "unsupported evidence type", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    if str(payload.get("result_status", "")) not in RESULT_STATUSES:
        payload["result_status"] = "unknown"

    outcome = _board_add(
        task_id=task_id,
        assignment_id=assignment_id,
        worker_engine_id=assignment.get("worker_engine_id", "") if assignment else "",
        evidence_type=str(payload.get("evidence_type", "")),
        evidence_source=_normalize_text(payload.get("evidence_source", ""), limit=260),
        evidence_summary=_normalize_text(payload.get("evidence_summary", ""), limit=2000),
        command_summary=_normalize_text(payload.get("command_summary", ""), limit=800),
        result_status=str(payload.get("result_status", "unknown")),
        related_files=_normalize_file_list(payload.get("related_files", []), limit=80),
        related_symbols=_normalize_symbol_list(payload.get("related_symbols", []), limit=120),
        supersedes_evidence_id=_normalize_text(payload.get("supersedes_evidence_id", ""), limit=120),
        metadata=payload.get("metadata"),
    )
    if not outcome.get("ok"):
        return outcome
    evidence = outcome["evidence"]
    evidences = _task_evidence(task_id=task_id, limit=200)
    evidence_digest = _digest(
        {"task_id": task_id, "count": len(evidences), "last": evidence.get("evidence_digest", ""), "time": _now()},
        prefix="ma-evidence",
    )
    contract["evidence_board_digest"] = evidence_digest
    contract["multi_agent_updated_at"] = _now()
    if outcome.get("duplicate"):
        return {
            "ok": True,
            "task_id": task_id,
            "duplicate": True,
            "duplicate_of": outcome.get("duplicate_of"),
            "evidence": evidence,
            "evidence_count": len(evidences),
            "task_contract": _safe(task_id, contract),
            **{k: v for k, v in outcome.items() if k in {"external_api_used", "network_access_used", "shell_execution_used", "local_first"}},
        }
    return {
        "ok": True,
        "task_id": task_id,
        "duplicate": False,
        "evidence": evidence,
        "evidence_count": len(evidences),
        "task_contract": _safe(task_id, contract),
        **{k: v for k, v in outcome.items() if k in {"external_api_used", "network_access_used", "shell_execution_used", "local_first"}},
    }


def add_evidence_from_payload(**payload: Any) -> Dict[str, Any]:
    return add_evidence_record(**payload)


def record_progress_event(**payload: Any) -> Dict[str, Any]:
    task_id = _normalize_text(payload.get("task_id", ""), limit=180)
    contract = TASK_CONTRACTS.get(task_id)
    if not contract:
        return {"ok": False, "error": "task_not_found", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    assignment_id = _normalize_text(payload.get("assignment_id", contract.get("active_assignment_id", "")), limit=180)
    if assignment_id and assignment_id not in ASSIGNMENTS:
        return {"ok": False, "error": "assignment_not_found", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    if assignment_id and contract.get("active_assignment_id") and contract["active_assignment_id"] != assignment_id:
        return {"ok": False, "error": "assignment mismatch", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    event_id = _normalize_text(payload.get("progress_event_id", ""), limit=200) or _digest({"task_id": task_id, "assignment": assignment_id, "time": _now()}, prefix="ma-progress")
    progress_percent = payload.get("progress_percent", 0)
    try:
        progress_percent_int = int(progress_percent)
    except (TypeError, ValueError):
        return {"ok": False, "error": "invalid progress_percent", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    if progress_percent_int < 0 or progress_percent_int > 100:
        return {"ok": False, "error": "progress percent out of range", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    completed_items = _normalize_list(payload.get("completed_items", []), limit=120)
    remaining_items = _normalize_list(payload.get("remaining_items", []), limit=120)
    blocked_items = _normalize_list(payload.get("blocked_items", []), limit=120)
    current_action = _normalize_text(payload.get("current_action", ""), limit=400)
    current_hypothesis = _normalize_text(payload.get("current_hypothesis", ""), limit=400)
    evidence_ids = _normalize_list(payload.get("evidence_ids", []), limit=80)

    # backward-progress requires explicit reason
    prev_events = PROGRESS_EVENTS.get(task_id, [])
    prev_percent = max((int(item.get("progress_percent", 0) or 0) for item in prev_events), default=0)
    if progress_percent_int < prev_percent and not _normalize_text(payload.get("rejected_reason", "")):
        return {"ok": False, "error": "progress decreased without reason", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    if progress_percent_int == 100 and (remaining_items or blocked_items):
        return {"ok": False, "error": "cannot mark complete while remaining or blocked items exist", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    if remaining_items and completed_items and set(completed_items) & set(remaining_items):
        return {"ok": False, "error": "completed and remaining overlap", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    progress_type = _normalize_text(payload.get("progress_type", ""), limit=80)
    if progress_type not in {
        "started",
        "inspection_complete",
        "implementation_started",
        "implementation_progress",
        "validation_started",
        "validation_progress",
        "blocked",
        "partial_completion",
        "handoff_prepared",
        "verification_complete",
        "completed",
    }:
        progress_type = "implementation_progress"

    progress_event = {
        "progress_event_id": event_id,
        "task_id": task_id,
        "assignment_id": assignment_id,
        "worker_engine_id": ASSIGNMENTS.get(assignment_id, {}).get("worker_engine_id", ""),
        "progress_type": progress_type,
        "progress_percent": progress_percent_int,
        "completed_items": completed_items,
        "remaining_items": remaining_items,
        "blocked_items": blocked_items,
        "current_hypothesis": current_hypothesis,
        "current_action": current_action,
        "evidence_ids": evidence_ids,
        "created_at": _now(),
    }
    progress_event["progress_event_digest"] = _build_progress_digest(progress_event)
    PROGRESS_EVENTS.setdefault(task_id, []).append(progress_event)
    contract["latest_progress_event_id"] = progress_event["progress_event_id"]
    contract["multi_agent_updated_at"] = progress_event["created_at"]
    if progress_percent_int >= 100:
        contract["task_state"] = "completed"
    elif progress_percent_int > 0:
        contract["task_state"] = "in_progress"
    if blocked_items:
        contract["task_state"] = "blocked"
    return {
        "ok": True,
        "task_id": task_id,
        "assignment_id": assignment_id,
        "progress_event": progress_event,
        "event_count": len(PROGRESS_EVENTS.get(task_id, [])),
        "task_contract": _safe(task_id, contract),
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def check_attempt_fingerprint(**payload: Any) -> Dict[str, Any]:
    task_id = _normalize_text(payload.get("task_id", ""), limit=180)
    contract = TASK_CONTRACTS.get(task_id)
    if not contract:
        return {"ok": False, "error": "task_not_found", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    assignment_id = _normalize_text(payload.get("assignment_id", ""), limit=180)
    if assignment_id and assignment_id not in ASSIGNMENTS:
        return {"ok": False, "error": "assignment_not_found", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    fp_payload = {
        "task_id": task_id,
        "assignment_id": assignment_id,
        "worker_engine_id": _normalize_text(payload.get("worker_engine_id", ""), limit=180),
        "hypothesis": _normalize_text(payload.get("hypothesis", ""), limit=300),
        "target_files": _normalize_file_list(payload.get("target_files", []), limit=120),
        "target_symbols": _normalize_symbol_list(payload.get("target_symbols", []), limit=120),
        "command_family": _normalize_text(payload.get("command_family", ""), limit=80),
        "patch_intent": _normalize_text(payload.get("patch_intent", ""), limit=300),
        "failure_signature": _normalize_text(payload.get("failure_signature", ""), limit=420),
    }
    fp = _build_attempt_fingerprint(fp_payload)
    previous = ATTEMPT_REGISTRY.get(fp)
    duplicate = previous is not None
    duplicate_reason = ""
    if duplicate:
        duplicate_reason = "attempt repeated with same normalized footprint"
        if not payload.get("override_attempt", False) and previous.get("attempt_state") == "rejected":
            return {
                "ok": False,
                "task_id": task_id,
                "attempt_fingerprint": fp,
                "duplicate_detected": True,
                "duplicate_reason": duplicate_reason,
                "blocked": True,
                "external_api_used": False,
                "network_access_used": False,
                "shell_execution_used": False,
                "local_first": True,
            }
    outcome = "accepted" if (not duplicate or payload.get("override_attempt", False)) else "duplicate"
    attempt = {
        "attempt_fingerprint": fp,
        "task_id": task_id,
        "assignment_id": assignment_id,
        "attempt_state": outcome,
        "worker_engine_id": fp_payload["worker_engine_id"],
        "hypothesis": fp_payload["hypothesis"],
        "target_files": fp_payload["target_files"],
        "target_symbols": fp_payload["target_symbols"],
        "command_family": fp_payload["command_family"],
        "patch_intent": fp_payload["patch_intent"],
        "failure_signature": fp_payload["failure_signature"],
        "created_at": _now(),
        "duplicate_of": previous.get("attempt_fingerprint") if previous else "",
    }
    ATTEMPT_REGISTRY[fp] = attempt
    list_fp = _normalize_list(contract.get("attempt_fingerprints", []), limit=160)
    if fp not in list_fp:
        list_fp.append(fp)
        contract["attempt_fingerprints"] = list_fp[-120:]
    contract["multi_agent_updated_at"] = attempt["created_at"]
    return {
        "ok": True,
        "task_id": task_id,
        "assignment_id": assignment_id,
        "attempt_fingerprint": fp,
        "attempt_state": outcome,
        "duplicate_detected": duplicate,
        "duplicate_reason": duplicate_reason,
        "attempt": attempt,
        "task_contract": _safe(task_id, contract),
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def register_failure_signature(**payload: Any) -> Dict[str, Any]:
    task_id = _normalize_text(payload.get("task_id", ""), limit=180)
    contract = TASK_CONTRACTS.get(task_id)
    if not contract:
        return {"ok": False, "error": "task_not_found", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    assignment_id = _normalize_text(payload.get("assignment_id", ""), limit=180)
    if assignment_id and assignment_id not in ASSIGNMENTS:
        return {"ok": False, "error": "assignment_not_found", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    category = _normalize_text(payload.get("failure_category", "unknown_failure"), limit=80)
    if category not in FAILURE_CATEGORIES:
        category = "unknown_failure"
    normalized_message = _normalize_text(payload.get("normalized_message", ""), limit=1200)
    affected_files = _normalize_file_list(payload.get("affected_files", []), limit=120)
    affected_symbols = _normalize_symbol_list(payload.get("affected_symbols", []), limit=120)
    command_family = _normalize_text(payload.get("command_family", ""), limit=120)
    failure_signature = _digest({"task_id": task_id, "assignment_id": assignment_id, "category": category, "msg": normalized_message}, prefix="ma-failure")
    if failure_signature in FAILURE_SIGS and not payload.get("override_repeat", False):
        return {
            "ok": True,
            "task_id": task_id,
            "duplicate_of": failure_signature,
            "failure_signature_id": failure_signature,
            "duplicate_detected": True,
            "recoverable": False,
            "recommended_next_action": "try alternative command family",
            "task_contract": _safe(task_id, contract),
            "external_api_used": False,
            "network_access_used": False,
            "shell_execution_used": False,
            "local_first": True,
        }

    signature = {
        "failure_signature_id": failure_signature,
        "task_id": task_id,
        "assignment_id": assignment_id,
        "failure_category": category,
        "normalized_message": normalized_message,
        "affected_files": affected_files,
        "affected_symbols": affected_symbols,
        "command_family": command_family,
        "exit_code": int(payload.get("exit_code", 1) or 1),
        "failure_digest": _digest({"category": category, "msg": normalized_message, "task_id": task_id}, prefix="ma-fsign"),
        "recoverable": bool(payload.get("recoverable", False)),
        "recommended_next_action": _normalize_text(payload.get("recommended_next_action", "retry with alternate approach"), limit=400),
        "created_at": _now(),
        "created_by": _normalize_text(payload.get("created_by", ""), limit=120),
    }
    FAILURE_SIGS[failure_signature] = signature
    list_ids = _normalize_list(contract.get("failure_signatures", []), limit=160)
    if failure_signature not in list_ids:
        list_ids.append(failure_signature)
        contract["failure_signatures"] = list_ids[-120:]
    contract["multi_agent_updated_at"] = signature["created_at"]
    return {
        "ok": True,
        "task_id": task_id,
        "assignment_id": assignment_id,
        "failure_signature_id": failure_signature,
        "failure_signature": signature,
        "duplicate_detected": False,
        "task_contract": _safe(task_id, contract),
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def build_partial_completion(**payload: Any) -> Dict[str, Any]:
    task_id = _normalize_text(payload.get("task_id", ""), limit=180)
    contract = TASK_CONTRACTS.get(task_id)
    if not contract:
        return {"ok": False, "error": "task_not_found", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    assignment_id = _normalize_text(payload.get("assignment_id", ""), limit=180)
    completed_scope = _normalize_list(payload.get("completed_scope", []), limit=180)
    completed_files = _normalize_file_list(payload.get("completed_files", []), limit=120)
    completed_symbols = _normalize_symbol_list(payload.get("completed_symbols", []), limit=180)
    completed_acceptance_items = _normalize_list(payload.get("completed_acceptance_items", []), limit=120)
    remaining_files = _normalize_file_list(payload.get("remaining_files", []), limit=120)
    remaining_acceptance = _normalize_list(payload.get("remaining_acceptance_items", []), limit=120)
    blocked_scope = _normalize_list(payload.get("blocked_scope", []), limit=160)
    evidence_ids = _normalize_list(payload.get("evidence_ids", []), limit=80)
    completion_percent = int(payload.get("completion_percent", 0) or 0)
    if completion_percent < 0 or completion_percent > 100:
        return {"ok": False, "error": "completion_percent out of range", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    if set(completed_files) & set(remaining_files):
        return {"ok": False, "error": "completed and remaining files overlap", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    if set(completed_acceptance_items) & set(remaining_acceptance):
        return {"ok": False, "error": "completed and remaining acceptance overlap", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    if completion_percent > 0 and completion_percent < 10 and (completed_scope or completed_files or completed_acceptance_items):
        completion_percent = 10

    partial = {
        "task_id": task_id,
        "assignment_id": assignment_id,
        "completion_percent": completion_percent,
        "completed_scope": completed_scope,
        "completed_files": completed_files,
        "completed_symbols": completed_symbols,
        "completed_acceptance_items": completed_acceptance_items,
        "remaining_scope": _normalize_list(payload.get("remaining_scope", []), limit=180),
        "remaining_files": remaining_files,
        "remaining_acceptance_items": remaining_acceptance,
        "blocked_scope": blocked_scope,
        "evidence_ids": evidence_ids,
        "created_at": _now(),
    }
    partial["partial_completion_digest"] = _digest(
        {
            "task_id": task_id,
            "completion_percent": completion_percent,
            "completed_files": completed_files,
            "remaining_files": remaining_files,
        },
        prefix="ma-partial",
    )
    PARTIAL_COMPLETIONS[_digest({"task_id": task_id, "assignment_id": assignment_id}, prefix="ma-partial-key")] = partial
    contract["partial_completion_digest"] = partial["partial_completion_digest"]
    contract["task_state"] = "partially_complete" if completion_percent < 100 else "completed"
    contract["multi_agent_updated_at"] = partial["created_at"]
    return {
        "ok": True,
        "task_id": task_id,
        "assignment_id": assignment_id,
        "partial_completion": partial,
        "task_contract": _safe(task_id, contract),
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def extract_remaining_gap(**payload: Any) -> Dict[str, Any]:
    task_id = _normalize_text(payload.get("task_id", ""), limit=180)
    if task_id not in TASK_CONTRACTS:
        return {"ok": False, "error": "task_not_found", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    contract = TASK_CONTRACTS[task_id]
    partial = PARTIAL_COMPLETIONS.get(_digest({"task_id": task_id, "assignment_id": payload.get("assignment_id", "")}, prefix="ma-partial-key"), {})
    completed = set(_normalize_list(partial.get("completed_files", []), limit=200))
    completed_acceptance = set(_normalize_list(partial.get("completed_acceptance_items", []), limit=120))
    acceptance = set(_normalize_list(contract.get("acceptance_criteria", []), limit=200))
    technical = set(_normalize_list(contract.get("technical_acceptance_criteria", []), limit=160))
    behavioral = set(_normalize_list(contract.get("behavioral_acceptance_criteria", []), limit=160))
    remaining_files = _normalize_file_list(contract.get("allowed_files", []), limit=200)
    remaining_acceptance = sorted(acceptance | technical | behavioral)
    remaining_files = [file for file in remaining_files if file not in completed]
    remaining_acceptance = [item for item in remaining_acceptance if item not in completed_acceptance]
    remaining_scope = [item for item in _normalize_list(contract.get("required_capabilities", []), limit=120) if item]
    failed_attempts = _normalize_list(payload.get("failed_attempt_fingerprints", []), limit=80)
    gap = {
        "remaining_gap_id": _digest({"task_id": task_id, "remaining": remaining_files, "acceptance": remaining_acceptance}, prefix="ma-gap"),
        "task_id": task_id,
        "remaining_scope": remaining_scope,
        "remaining_files": remaining_files,
        "remaining_symbols": [],
        "missing_capabilities": [],
        "unmet_acceptance_criteria": remaining_acceptance,
        "blocked_reasons": _normalize_list(payload.get("blocked_reasons", []), limit=120),
        "recommended_worker_capabilities": _normalize_list(contract.get("required_capabilities", []), limit=80),
        "recommended_next_tier": _normalize_text(payload.get("recommended_next_tier", "normal"), limit=80),
        "gap_digest": _digest({"task_id": task_id, "remaining": remaining_files, "scope": remaining_scope, "acceptance": remaining_acceptance}, prefix="ma-gap-d"),
        "attempt_fingerprints": [],
        "failure_signatures": [],
        "partial_reference": partial.get("partial_completion_digest", ""),
        "created_at": _now(),
    }
    for item in failed_attempts:
        key = str(item)
        if key in ATTEMPT_REGISTRY:
            gap["attempt_fingerprints"].append(key)
    for key in _normalize_list(payload.get("failure_signatures", []), limit=80):
        if key in FAILURE_SIGS:
            gap["failure_signatures"].append(key)
    contract["remaining_gap_digest"] = gap["gap_digest"]
    contract["multi_agent_updated_at"] = gap["created_at"]
    GAPS[gap["remaining_gap_id"]] = gap
    return {
        "ok": True,
        "task_id": task_id,
        "remaining_gap": gap,
        "task_contract": _safe(task_id, contract),
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def register_file_ownership(**payload: Any) -> Dict[str, Any]:
    task_id = _normalize_text(payload.get("task_id", ""), limit=180)
    assignment_id = _normalize_text(payload.get("assignment_id", ""), limit=180)
    worker_engine_id = _normalize_text(payload.get("worker_engine_id", ""), limit=180)
    file_path = payload.get("file_path", [])
    if isinstance(file_path, str):
        file_paths = [file_path]
    else:
        file_paths = list(file_path or [])
    owned_files = _normalize_file_list(file_paths, limit=OWNERSHIP_FILE_LIMIT)
    if not owned_files:
        return {"ok": False, "error": "owned_files required", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    contract = TASK_CONTRACTS.get(task_id)
    if not contract:
        return {"ok": False, "error": "task_not_found", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    mode = _normalize_text(payload.get("ownership_mode", "read"), limit=80)
    if mode not in OWNERSHIP_MODES:
        mode = "read"
    state = _normalize_text(payload.get("ownership_state", "active"), limit=80)
    if state not in OWNERSHIP_STATES:
        state = "active"

    ownership_id = _digest({"task_id": task_id, "assignment_id": assignment_id, "worker": worker_engine_id, "files": owned_files, "state": state}, prefix="ma-own")
    ownership = {
        "ownership_id": ownership_id,
        "task_id": task_id,
        "assignment_id": assignment_id,
        "worker_engine_id": worker_engine_id,
        "file_path": owned_files,
        "ownership_mode": mode,
        "acquired_at": _now(),
        "expires_at": _normalize_text(payload.get("expires_at", ""), limit=80),
        "released_at": _normalize_text(payload.get("released_at", ""), limit=80),
        "ownership_state": state,
        "overlap_count": len(owned_files),
    }
    same_assignment_worker_conflict = any(
        existing.get("task_id") == task_id
        and existing.get("assignment_id") == assignment_id
        and existing.get("worker_engine_id") != worker_engine_id
        and existing.get("ownership_state") == "active"
        and existing.get("ownership_mode") == "exclusive_write"
        and bool(set(_normalize_file_list(existing.get("file_path", []), limit=OWNERSHIP_FILE_LIMIT)) & set(owned_files))
        for existing in OWNERSHIPS.values()
    )
    if (_conflict_with_active_ownership(task_id, assignment_id, owned_files) or same_assignment_worker_conflict) and state == "active" and mode == "exclusive_write":
        return {"ok": False, "error": "ownership conflict", "task_id": task_id, "assignment_id": assignment_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    OWNERSHIPS[ownership_id] = ownership
    contract["file_ownership_state"] = f"{state}:{mode}"
    contract["multi_agent_updated_at"] = ownership["acquired_at"]
    return {
        "ok": True,
        "task_id": task_id,
        "assignment_id": assignment_id,
        "ownership_id": ownership_id,
        "ownership": ownership,
        "task_contract": _safe(task_id, contract),
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def release_file_ownership(task_id: str, assignment_id: str = "", ownership_id: str = "") -> Dict[str, Any]:
    contract = TASK_CONTRACTS.get(task_id)
    if not contract:
        return {"ok": False, "error": "task_not_found", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    if ownership_id:
        item = OWNERSHIPS.get(ownership_id)
        if not item:
            return {"ok": False, "error": "ownership_not_found", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
        item["ownership_state"] = "released"
        item["released_at"] = _now()
        return {"ok": True, "task_id": task_id, "ownership_id": ownership_id, "ownership": item, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    if assignment_id:
        for key in list(OWNERSHIPS.keys()):
            ownership = OWNERSHIPS[key]
            if ownership.get("assignment_id") == assignment_id and ownership.get("task_id") == task_id and ownership.get("ownership_state") == "active":
                ownership["ownership_state"] = "released"
                ownership["released_at"] = _now()
        contract["file_ownership_state"] = "released"
        contract["multi_agent_updated_at"] = _now()
        return {"ok": True, "task_id": task_id, "assignment_id": assignment_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    return {"ok": False, "error": "ownership_id or assignment_id required", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}


def prepare_handoff(**payload: Any) -> Dict[str, Any]:
    task_id = _normalize_text(payload.get("task_id", ""), limit=180)
    contract = TASK_CONTRACTS.get(task_id)
    if not contract:
        return {"ok": False, "error": "task_not_found", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    if contract.get("task_state") == "completed":
        return {"ok": False, "error": "completed task cannot be handed off", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    from_worker = _normalize_text(payload.get("from_worker_engine_id", contract.get("active_worker_engine_id", "")), limit=180)
    to_worker = _normalize_text(payload.get("to_worker_engine_id", ""), limit=180)
    if not from_worker or not to_worker:
        return {"ok": False, "error": "from and to workers required", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    if to_worker == "Codex" or to_worker.lower() == "codex":
        return {"ok": False, "error": "Codex cannot auto-accept", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    partial = payload.get("partial_completion") or _build_partial_from_contract(task_id)
    if not isinstance(partial, dict):
        partial = {}
    completed_files = _normalize_file_list(partial.get("completed_files", []), limit=200)
    remaining_scope = _normalize_list(payload.get("remaining_scope", []), limit=180)
    remaining_files = _normalize_file_list(payload.get("remaining_files", []), limit=200)
    gap = extract_remaining_gap(task_id=task_id, assignment_id=contract.get("active_assignment_id", ""), failed_attempt_fingerprints=_normalize_list(payload.get("failed_attempt_fingerprints", []), limit=80))
    if not gap.get("ok"):
        return gap
    gap_data = gap["remaining_gap"]
    if remaining_files and set(remaining_files) & set(completed_files):
        return {"ok": False, "error": "completed scope repeated as remaining scope", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    handoff_id = _normalize_text(payload.get("handoff_id", ""), limit=180) or _digest(
        {
            "task_id": task_id,
            "from_worker": from_worker,
            "to_worker": to_worker,
            "gap": gap_data.get("remaining_gap_id"),
        },
        prefix="ma-handoff",
    )
    handoff = {
        "handoff_id": handoff_id,
        "task_id": task_id,
        "from_assignment_id": _normalize_text(payload.get("from_assignment_id", contract.get("active_assignment_id", "")), limit=180),
        "from_worker_engine_id": from_worker,
        "to_worker_engine_id": to_worker,
        "to_worker_tier": _normalize_text(payload.get("to_worker_tier", ""), limit=80),
        "handoff_reason": _normalize_text(payload.get("handoff_reason", ""), limit=500),
        "completed_scope": completed_files,
        "remaining_gap": gap_data,
        "evidence_ids": _normalize_list(payload.get("evidence_ids", []), limit=80),
        "attempt_fingerprints": _normalize_list(payload.get("attempt_fingerprints", []), limit=120),
        "failure_signatures": _normalize_list(payload.get("failure_signatures", []), limit=120),
        "owned_files_release": _normalize_file_list(payload.get("owned_files_release", []), limit=200),
        "requested_files": _normalize_file_list(payload.get("requested_files", []), limit=200),
        "required_capabilities": _normalize_list(payload.get("required_capabilities", []), limit=80),
        "handoff_state": "prepared",
        "handoff_digest": _digest({"task_id": task_id, "from": from_worker, "to": to_worker, "reason": payload.get("handoff_reason", "")}, prefix="ma-handoff-d"),
        "created_at": _now(),
        "expires_at": _normalize_text(payload.get("expires_at", ""), limit=80),
    }
    HANDOFFS[handoff_id] = handoff
    contract["active_handoff_id"] = handoff_id
    contract["task_state"] = "handoff_required"
    contract["assignment_state"] = "handed_off"
    contract["multi_agent_updated_at"] = handoff["created_at"]
    return {
        "ok": True,
        "task_id": task_id,
        "handoff_id": handoff_id,
        "handoff": handoff,
        "task_contract": _safe(task_id, contract),
        "handoff_acceptance_required": True,
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def accept_handoff(**payload: Any) -> Dict[str, Any]:
    task_id = _normalize_text(payload.get("task_id", ""), limit=180)
    contract = TASK_CONTRACTS.get(task_id)
    if not contract:
        return {"ok": False, "error": "task_not_found", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    handoff_id = _normalize_text(payload.get("handoff_id", contract.get("active_handoff_id", "")), limit=180)
    handoff = HANDOFFS.get(handoff_id)
    if not handoff:
        return {"ok": False, "error": "handoff_not_found", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    if payload.get("accepted") is not True:
        handoff["handoff_state"] = "rejected"
        contract["task_state"] = "blocked"
        contract["multi_agent_updated_at"] = _now()
        return {
            "ok": True,
            "task_id": task_id,
            "handoff_id": handoff_id,
            "handoff_state": "rejected",
            "task_contract": _safe(task_id, contract),
            "external_api_used": False,
            "network_access_used": False,
            "shell_execution_used": False,
            "local_first": True,
        }
    handoff["handoff_state"] = "accepted"
    contract["active_assignment_id"] = payload.get("to_assignment_id", "")
    contract["assignment_state"] = "prepared"
    contract["task_state"] = "assigned"
    contract["active_worker_engine_id"] = handoff.get("to_worker_engine_id", "")
    contract["multi_agent_updated_at"] = _now()
    return {
        "ok": True,
        "task_id": task_id,
        "handoff_id": handoff_id,
        "handoff_state": "accepted",
        "task_contract": _safe(task_id, contract),
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def set_technical_verification_result(**payload: Any) -> Dict[str, Any]:
    return _set_verification_result(verification_type="technical", **payload)


def set_behavioral_verification_result(**payload: Any) -> Dict[str, Any]:
    return _set_verification_result(verification_type="behavioral", **payload)


def _set_verification_result(verification_type: str = "technical", **payload: Any) -> Dict[str, Any]:
    task_id = _normalize_text(payload.get("task_id", ""), limit=180)
    contract = TASK_CONTRACTS.get(task_id)
    if not contract:
        return {"ok": False, "error": "task_not_found", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    scenario = _normalize_text(payload.get("scenario_id", ""), limit=180)
    verification_id = _normalize_text(payload.get("verification_id", ""), limit=180) or _digest(
        {"task_id": task_id, "type": verification_type, "scenario": scenario, "time": _now()},
        prefix="ma-verify",
    )
    if verification_type not in TaskVerificationType:
        return {"ok": False, "error": "unsupported verification type", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    compile_status = bool(payload.get("compile_status", False))
    validator_status = bool(payload.get("validator_status", False))
    targeted_smoke_status = bool(payload.get("targeted_smoke_status", False))
    diff_status = bool(payload.get("diff_check_status", True))
    artifact_status = bool(payload.get("artifact_check_status", True))
    evidences = _normalize_list(payload.get("evidence_ids", []), limit=80)
    expected_behavior = _normalize_text(payload.get("expected_behavior", ""), limit=500)
    observed_behavior = _normalize_text(payload.get("observed_behavior", ""), limit=500)
    result = {
        "verification_id": verification_id,
        "task_id": task_id,
        "verification_type": verification_type,
        "scenario_id": scenario,
        "compile_status": compile_status,
        "validator_status": validator_status,
        "targeted_smoke_status": targeted_smoke_status,
        "diff_check_status": diff_status,
        "artifact_check_status": artifact_status,
        "evidence_ids": evidences,
        "user_intent_match": bool(payload.get("user_intent_match", False)),
        "regression_detected": bool(payload.get("regression_detected", False)),
        "expected_behavior": expected_behavior,
        "observed_behavior": observed_behavior,
        "technical_passed": bool(compile_status and validator_status and diff_status and artifact_status),
        "behavioral_passed": bool(expected_behavior and observed_behavior and bool(payload.get("observed_behavior")) and bool(expected_behavior)),
        "created_at": _now(),
    }
    result["verification_passed"] = result["technical_passed"] if verification_type == "technical" else result["behavioral_passed"]
    result["verification_state_digest"] = _digest({"task_id": task_id, "type": verification_type, "passed": result["verification_passed"]}, prefix="ma-ver-state")
    VERIFICATIONS[result["verification_id"]] = result
    if verification_type == "technical":
        contract["technical_verification_state"] = "passed" if result["technical_passed"] else "failed"
    else:
        contract["behavioral_verification_state"] = "passed" if result["behavioral_passed"] else "failed"
    contract["multi_agent_updated_at"] = result["created_at"]
    return {
        "ok": True,
        "task_id": task_id,
        "verification_id": verification_id,
        "verification_type": verification_type,
        "verification": result,
        "task_contract": _safe(task_id, contract),
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def set_finality_decision(**payload: Any) -> Dict[str, Any]:
    task_id = _normalize_text(payload.get("task_id", ""), limit=180)
    contract = TASK_CONTRACTS.get(task_id)
    if not contract:
        return {"ok": False, "error": "task_not_found", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    handoff = extract_remaining_gap(task_id=task_id)
    if not handoff.get("ok"):
        remaining_gap = {}
    else:
        remaining_gap = handoff.get("remaining_gap", {})
    remaining_ids = list(remaining_gap.get("unmet_acceptance_criteria", [])) if remaining_gap else []
    blocking_failures = _normalize_list(payload.get("blocking_failures", []), limit=120)
    technical_ok = contract.get("technical_verification_state") == "passed"
    behavioral_ok = contract.get("behavioral_verification_state") == "passed"
    completion_score = float(payload.get("completion_score", 0.0) or 0.0)
    decision = _normalize_text(payload.get("decision", ""), limit=80)
    if decision not in FinalityDecision:
        if remaining_ids and not technical_ok:
            decision = "verification_required"
        elif remaining_ids or blocking_failures:
            decision = "verification_required"
        elif completion_score >= 0.99 and technical_ok and behavioral_ok:
            decision = "complete"
        elif completion_score >= 0.65:
            decision = "partial"
        else:
            decision = "blocked"

    if decision == "complete":
        if remaining_ids or blocking_failures or not (technical_ok and behavioral_ok) or contract.get("task_state") in {"created", "assigned", "in_progress", "partially_complete", "blocked", "handoff_required", "verification_pending"}:
            return {"ok": False, "error": "complete decision invalid without finality gates", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
        contract["task_state"] = "completed"
    elif decision == "partial":
        contract["task_state"] = "partially_complete"
    elif decision == "blocked":
        contract["task_state"] = "blocked"
    elif decision == "verification_required":
        contract["task_state"] = "verification_required"

    finality_id = _normalize_text(payload.get("finality_decision_id", ""), limit=200) or _digest(
        {"task_id": task_id, "decision": decision, "time": _now()},
        prefix="ma-final",
    )
    finality = {
        "finality_decision_id": finality_id,
        "task_id": task_id,
        "decision": decision,
        "completion_score": completion_score,
        "technical_passed": technical_ok,
        "behavioral_passed": behavioral_ok,
        "remaining_gaps": remaining_ids,
        "blocking_failures": blocking_failures,
        "evidence_ids": _normalize_list(payload.get("evidence_ids", []), limit=120),
        "evidence_count": len(_normalize_list(payload.get("evidence_ids", []), limit=120)),
        "decision_reason": _normalize_text(payload.get("decision_reason", ""), limit=800),
        "finality_digest": _digest({"task_id": task_id, "decision": decision, "reason": payload.get("decision_reason", "")}, prefix="ma-finality"),
        "created_at": _now(),
    }
    FINALITY[finality_id] = finality
    contract["finality_state"] = decision
    contract["multi_agent_updated_at"] = finality["created_at"]
    return {
        "ok": True,
        "task_id": task_id,
        "finality_decision_id": finality_id,
        "finality": finality,
        "task_contract": _safe(task_id, contract),
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def request_reopen(**payload: Any) -> Dict[str, Any]:
    task_id = _normalize_text(payload.get("task_id", ""), limit=180)
    contract = TASK_CONTRACTS.get(task_id)
    if not contract:
        return {"ok": False, "error": "task_not_found", "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}
    reason = _normalize_text(payload.get("reopen_reason", ""), limit=260)
    if not reason:
        return {"ok": False, "error": "reopen_reason required", "task_id": task_id, "external_api_used": False, "network_access_used": False, "shell_execution_used": False, "local_first": True}

    reason_key = None
    for value in ReopenReason:
        if value in reason.lower():
            reason_key = value
            break
    if not reason_key:
        reason_key = "new_evidence"
    reopen_allowed = bool(payload.get("reopen_allowed", False))
    if not reopen_allowed:
        return {
            "ok": False,
            "task_id": task_id,
            "reopen_allowed": False,
            "reopen_reason": reason_key,
            "external_api_used": False,
            "network_access_used": False,
            "shell_execution_used": False,
            "local_first": True,
        }

    reopen_id = _digest({"task_id": task_id, "reason": reason_key, "time": _now()}, prefix="ma-reopen")
    reopen = {
        "reopen_decision_id": reopen_id,
        "task_id": task_id,
        "reopen_allowed": True,
        "reopen_reason": reason_key,
        "new_evidence_ids": _normalize_list(payload.get("new_evidence_ids", []), limit=80),
        "user_rejection_present": bool(payload.get("user_rejection_present", False)),
        "new_failure_present": bool(payload.get("new_failure_present", False)),
        "reopened_scope": _normalize_list(payload.get("reopened_scope", []), limit=180),
        "reopened_evidence_ids": _normalize_list(payload.get("new_evidence_ids", []), limit=80),
        "created_at": _now(),
    }
    REOPEN[reopen_id] = reopen
    contract["reopen_state"] = reason_key
    contract["task_state"] = "reopened"
    contract["multi_agent_updated_at"] = reopen["created_at"]
    return {
        "ok": True,
        "task_id": task_id,
        "reopen_decision_id": reopen_id,
        "reopen": reopen,
        "task_contract": _safe(task_id, contract),
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def _build_partial_from_contract(task_id: str) -> Dict[str, Any]:
    contract = TASK_CONTRACTS.get(task_id, {})
    return {
        "completed_files": [],
        "remaining_files": list(contract.get("allowed_files", [])),
    }


def get_multi_agent_status(task_id: Optional[str] = None) -> Dict[str, Any]:
    if task_id:
        from luxcode_evidence_board import get_task_evidence

        contract = TASK_CONTRACTS.get(task_id)
        if not contract:
            return {
                "ok": False,
                "task_id": task_id,
                "found": False,
                "external_api_used": False,
                "network_access_used": False,
                "shell_execution_used": False,
                "local_first": True,
            }
        return {
            "ok": True,
            "task_id": task_id,
            "found": True,
            "task_contract": _safe(task_id, contract),
            "progress_events": len(PROGRESS_EVENTS.get(task_id, [])),
            "attempt_fingerprints": len(contract.get("attempt_fingerprints", [])),
            "failure_signatures": len(contract.get("failure_signatures", [])),
            "active_assignments": len([assignment for assignment in ASSIGNMENTS.values() if assignment.get("task_id") == task_id and assignment.get("assignment_state") in {"active", "acknowledged", "offered", "prepared"}]),
            "active_handoffs": len([handoff for handoff in HANDOFFS.values() if handoff.get("task_id") == task_id and handoff.get("handoff_state") in {"prepared", "awaiting_acceptance", "rejected", "accepted"}]),
            "evidence_count": len(get_task_evidence(task_id)),
            "external_api_used": False,
            "network_access_used": False,
            "shell_execution_used": False,
            "local_first": True,
        }

    return {
        "ok": True,
        "status": "ready",
        "tracked_task_count": len(TASK_CONTRACTS),
        "active_tasks": [item["task_id"] for item in TASK_CONTRACTS.values() if item.get("task_state") not in {"completed", "cancelled", "rejected"}],
        "active_assignments": len([item for item in ASSIGNMENTS.values() if item.get("assignment_state") in {"prepared", "offered", "acknowledged", "active"}]),
        "active_handoffs": len([item for item in HANDOFFS.values() if item.get("handoff_state") == "prepared"]),
        "active_ownerships": len([item for item in OWNERSHIPS.values() if item.get("ownership_state") == "active"]),
        "external_api_used": False,
        "network_access_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }
