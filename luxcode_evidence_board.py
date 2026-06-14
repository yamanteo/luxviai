from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


ALLOWED_EVIDENCE_TYPES = {
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
MAX_EVIDENCE_PER_TASK = 320

BOARD: Dict[str, List[Dict[str, Any]]] = {}
INDEX: Dict[str, Dict[str, Dict[str, Any]]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any, prefix: str = "evidence") -> str:
    return f"{prefix}-{hashlib.sha256(_stable_json(value).encode('utf-8')).hexdigest()[:24]}"


def _normalize_list(values: Any, limit: int = 50) -> List[str]:
    if not values:
        return []
    if isinstance(values, str):
        items = [values]
    elif isinstance(values, (list, tuple, set)):
        items = list(values)
    else:
        return [str(values)]
    normalized: List[str] = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        if text not in seen:
            normalized.append(text)
            seen.add(text)
    return normalized[:limit]


def _normalize_text(value: str, max_length: int = 1200) -> str:
    safe = (value or "").replace("\x00", "").strip()
    return safe[:max_length]


def _sanitize_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    if not isinstance(metadata, dict):
        return sanitized
    for key, value in metadata.items():
        lowered = str(key).lower()
        if any(token in lowered for token in ("api_key", "token", "secret", "password", "authorization", "credential", "provider_payload", "raw_prompt", "full_source", "full_prompt")):
            continue
        sanitized[str(key)] = value
    return sanitized


def get_evidence_board_registry() -> Dict[str, Any]:
    return {
        "name": "LuxCode Multi-Agent Evidence Board",
        "status": "ready",
        "version": "multi_agent_evidence_v1",
        "read_only": True,
        "append_only": True,
        "records_per_task_limit": MAX_EVIDENCE_PER_TASK,
        "allowed_types": sorted(ALLOWED_EVIDENCE_TYPES),
        "allowed_statuses": sorted(RESULT_STATUSES),
        "external_api_used": False,
        "network_access_used": False,
        "subprocess_execution_used": False,
        "local_first": True,
        "secret_fields_blocked": [
            "api_key",
            "token",
            "secret",
            "password",
            "authorization",
            "credential",
            "raw_prompt",
            "full_prompt",
            "source_code",
        ],
    }


def get_evidence_board_status(task_id: Optional[str] = None) -> Dict[str, Any]:
    if task_id:
        records = BOARD.get(str(task_id), [])
        return {
            "task_id": str(task_id),
            "status": "ready",
            "records": len(records),
            "latest_record_id": records[-1].get("evidence_id") if records else "",
            "latest_record": records[-1] if records else {},
            "critical_count": sum(1 for item in records if item.get("result_status") in {"fail", "blocked"}),
            "external_api_used": False,
            "network_access_used": False,
            "subprocess_execution_used": False,
            "local_first": True,
        }

    all_records = [record for records in BOARD.values() for record in records]
    all_records.sort(key=lambda item: str(item.get("created_at", "")))
    return {
        "status": "ready",
        "tracked_tasks": len(BOARD),
        "total_records": len(all_records),
        "latest_records": all_records[-20:],
        "external_api_used": False,
        "network_access_used": False,
        "subprocess_execution_used": False,
        "local_first": True,
    }


def add_evidence_record(
    task_id: str,
    assignment_id: str,
    worker_engine_id: str,
    evidence_type: str,
    evidence_source: str,
    evidence_summary: str,
    command_summary: str = "",
    result_status: str = "unknown",
    related_files: Optional[List[str]] = None,
    related_symbols: Optional[List[str]] = None,
    evidence_id: str = "",
    supersedes_evidence_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    task_key = str(task_id or "").strip()
    if not task_key:
        return {
            "ok": False,
            "error": "task_id is required",
            "external_api_used": False,
            "network_access_used": False,
            "subprocess_execution_used": False,
            "local_first": True,
        }

    selected_type = str(evidence_type or "unknown").strip()
    if selected_type not in ALLOWED_EVIDENCE_TYPES:
        return {
            "ok": False,
            "error": "unsupported evidence_type",
            "task_id": task_key,
            "external_api_used": False,
            "network_access_used": False,
            "subprocess_execution_used": False,
            "local_first": True,
        }

    status = str(result_status or "unknown").strip().lower()
    if status not in RESULT_STATUSES:
        status = "unknown"

    files = _normalize_list(related_files, limit=50)
    symbols = _normalize_list(related_symbols, limit=80)
    evidence_payload = {
        "task_id": task_key,
        "assignment_id": str(assignment_id or "").strip(),
        "worker_engine_id": str(worker_engine_id or "").strip(),
        "evidence_type": selected_type,
        "evidence_source": _normalize_text(evidence_source),
        "evidence_summary": _normalize_text(evidence_summary),
        "command_summary": _normalize_text(command_summary),
        "result_status": status,
        "related_files": files,
        "related_symbols": symbols,
        "supersedes_evidence_id": str(supersedes_evidence_id or "").strip(),
        "metadata": _sanitize_metadata(metadata),
        "created_at": _now(),
    }
    fingerprint = _digest({
        "task_id": task_key,
        "assignment_id": evidence_payload["assignment_id"],
        "worker_engine_id": evidence_payload["worker_engine_id"],
        "evidence_type": selected_type,
        "result_status": status,
        "summary": evidence_payload["evidence_summary"],
        "command_summary": evidence_payload["command_summary"],
    }, prefix="evidence")
    record_id = str(evidence_id or fingerprint)
    duplicate = False
    existing_for_task = BOARD.setdefault(task_key, [])
    existing_index = [r for r in existing_for_task if r.get("evidence_digest") == fingerprint]
    if existing_index:
        duplicate = True
    record = {
        "evidence_id": record_id,
        "evidence_digest": fingerprint,
        "task_id": task_key,
        **evidence_payload,
    }
    existing_for_task.append(record)
    if len(existing_for_task) > MAX_EVIDENCE_PER_TASK:
        existing_for_task[:] = existing_for_task[-MAX_EVIDENCE_PER_TASK:]
    INDEX[record_id] = record
    return {
        "ok": True,
        "task_id": task_key,
        "evidence": record,
        "total_records": len(existing_for_task),
        "duplicate": duplicate,
        "duplicate_of": existing_index[0].get("evidence_id") if existing_index else "",
        "external_api_used": False,
        "network_access_used": False,
        "subprocess_execution_used": False,
        "local_first": True,
    }


def get_task_evidence(task_id: str, limit: int = 120) -> List[Dict[str, Any]]:
    items = BOARD.get(str(task_id), [])
    try:
        max_limit = max(1, min(int(limit), 200))
    except (TypeError, ValueError):
        max_limit = 20
    return [dict(item) for item in items[-max_limit:]]


def summarize_task_evidence(task_id: str) -> Dict[str, Any]:
    items = get_task_evidence(task_id, limit=MAX_EVIDENCE_PER_TASK)
    return {
        "task_id": str(task_id),
        "evidence_count": len(items),
        "status_counts": {status: sum(1 for item in items if item.get("result_status") == status) for status in sorted(RESULT_STATUSES)},
        "type_counts": {etype: sum(1 for item in items if item.get("evidence_type") == etype) for etype in sorted(ALLOWED_EVIDENCE_TYPES)},
        "latest_evidence_id": items[-1].get("evidence_id") if items else "",
        "latest_evidence_digest": items[-1].get("evidence_digest") if items else "",
        "external_api_used": False,
        "network_access_used": False,
        "subprocess_execution_used": False,
        "local_first": True,
    }
