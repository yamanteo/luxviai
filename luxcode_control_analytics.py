from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ENGINE_SEQUENCE = [
    "tier0_deterministic",
    "tier1_local_worker",
    "free_gemini",
    "nex",
    "nemotron",
    "qwen",
    "direct_deepseek",
    "whale",
    "codex",
]

ENGINE_LABELS = {
    "tier0_deterministic": "Tier 0 Deterministic",
    "tier1_local_worker": "Tier 1 Local Worker",
    "free_gemini": "Free Gemini",
    "free_cloud_worker": "Free Cloud",
    "nex": "Nex",
    "nemotron": "Nemotron",
    "qwen": "Qwen",
    "direct_deepseek": "Direct DeepSeek",
    "whale": "Whale",
    "codex": "Codex",
}

FREE_ENGINES = {"tier0_deterministic", "tier1_local_worker", "free_gemini", "free_cloud_worker", "nex", "nemotron", "qwen"}
LOCAL_ENGINES = {"tier0_deterministic", "tier1_local_worker"}
FREE_CLOUD_ENGINES = {"free_gemini", "free_cloud_worker", "nex", "nemotron", "qwen"}
PAID_ENGINES = {"direct_deepseek", "whale", "codex"}
FREE_RESULT_CLASSES = {"FREE_COMPLETED", "FREE_PARTIAL", "EXTERNAL_SERVICE_DEFERRED"}
SECRET_MASK = "[redacted]"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any, prefix: str) -> str:
    return f"{prefix}-{hashlib.sha256(_stable_json(value).encode('utf-8')).hexdigest()[:24]}"


def redact_secret(value: Any) -> Any:
    patterns = [
        re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)([^\s,;]+)"),
        re.compile(r"(?i)((?:api[_-]?key|token|secret|password|cookie)\s*[:=]\s*[\"']?)([^\"'\s,;]+)"),
        re.compile(r"(?i)()(sk-[A-Za-z0-9._~+/-]{8,})"),
    ]
    if isinstance(value, str):
        cleaned = value
        for pattern in patterns:
            cleaned = pattern.sub(lambda match: match.group(1) + SECRET_MASK, cleaned)
        return cleaned[:4000]
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(marker in key_text.lower() for marker in ("secret", "token", "api_key", "authorization", "cookie", "password")):
                out[key_text] = SECRET_MASK
            else:
                out[key_text] = redact_secret(item)
        return out
    if isinstance(value, list):
        return [redact_secret(item) for item in value[:300]]
    return value


def _engine_key(engine_id: str, model_id: str = "") -> str:
    raw = (engine_id or model_id or "unknown").lower()
    if "nex" in raw:
        return "nex"
    if "nemotron" in raw:
        return "nemotron"
    if "qwen" in raw:
        return "qwen"
    if "gemini" in raw:
        return "free_gemini"
    if "deepseek" in raw:
        return "direct_deepseek"
    if raw in ENGINE_LABELS:
        return raw
    return engine_id or "unknown"


def _percent(count: int, total: int) -> Optional[float]:
    if total <= 0:
        return None
    return round((count / total) * 100, 2)


def _status_completed(status: str, validation_outcome: str = "") -> bool:
    if validation_outcome.lower() in {"fail", "failed", "rollback", "rolled_back", "invalidated"}:
        return False
    return status in {"completed", "validated"}


def _unit_id(unit: Dict[str, Any]) -> str:
    return str(unit.get("unit_id") or unit.get("id") or _digest(unit, "unit"))


def _normalize_work_units(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    units: Dict[str, Dict[str, Any]] = {}
    raw_work_units = session.get("work_units", []) if isinstance(session.get("work_units"), list) else []
    for item in raw_work_units:
        if isinstance(item, dict):
            unit = dict(item)
            unit["unit_id"] = _unit_id(unit)
            units[unit["unit_id"]] = redact_secret(unit)
    raw_engine_runs = session.get("engine_runs", []) if isinstance(session.get("engine_runs"), list) else []
    for run in raw_engine_runs:
        if not isinstance(run, dict):
            continue
        engine = _engine_key(str(run.get("engine_id") or ""), str(run.get("model_id") or ""))
        validation = str(run.get("validation_outcome") or run.get("validation_result") or "")
        for unit_id in run.get("completed_unit_ids", []) or []:
            key = str(unit_id)
            unit = units.setdefault(key, {"unit_id": key, "unit_type": "unknown", "status": "completed"})
            if unit.get("completed_by_engine") is None:
                unit["completed_by_engine"] = engine
                unit["completed_by_model"] = str(run.get("model_id") or "")
                unit["completed_at"] = str(run.get("ended_at") or run.get("completed_at") or "")
            unit["validation_outcome"] = validation or unit.get("validation_outcome", "")
        for unit_id in run.get("remaining_unit_ids", []) or []:
            key = str(unit_id)
            units.setdefault(key, {"unit_id": key, "unit_type": "unknown", "status": "pending"})
    return [units[key] for key in sorted(units)]


def _completed_unique_units(work_units: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    completed: Dict[str, Dict[str, Any]] = {}
    for unit in work_units:
        unit_id = _unit_id(unit)
        status = str(unit.get("status") or "")
        validation = str(unit.get("validation_outcome") or unit.get("validation_result") or "")
        if unit.get("invalidated") or unit.get("rolled_back"):
            continue
        if _status_completed(status, validation) and unit_id not in completed:
            completed[unit_id] = unit
    return completed


def calculate_session_contribution(session: Dict[str, Any]) -> Dict[str, Any]:
    safe_session = redact_secret(session)
    session_id = str(safe_session.get("session_id") or safe_session.get("task_id") or "unknown")
    work_units = _normalize_work_units(safe_session)
    completed_unique = _completed_unique_units(work_units)
    total_units = len(work_units)
    enough_data = total_units > 0
    engine_runs = [run for run in safe_session.get("engine_runs", []) if isinstance(run, dict)]
    engine_metrics: Dict[str, Dict[str, Any]] = {}
    counted_units: set[str] = set()

    for run in engine_runs:
        engine = _engine_key(str(run.get("engine_id") or ""), str(run.get("model_id") or ""))
        metric = engine_metrics.setdefault(engine, {
            "engine_id": engine,
            "engine_label": ENGINE_LABELS.get(engine, engine),
            "model_id": str(run.get("model_id") or ""),
            "role": str(run.get("role") or ""),
            "task_count": 1,
            "completed_task_count": 0,
            "partial_task_count": 0,
            "rejected_task_count": 0,
            "deferred_task_count": 0,
            "completed_unit_ids": [],
            "task_contribution_percent": None,
            "remaining_gap_percent": None,
            "cumulative_completion_percent": None,
            "validation_success_percent": None,
            "average_duration_ms": None,
            "paid_call_avoidance_count": 0,
            "estimated_paid_scope_saved_percent": None,
        })
        metric["model_id"] = metric["model_id"] or str(run.get("model_id") or "")
        result_class = str(run.get("result_class") or run.get("outcome") or run.get("status") or "")
        if result_class in {"completed", "FREE_COMPLETED"}:
            metric["completed_task_count"] += 1
        elif result_class in {"partial", "FREE_PARTIAL"}:
            metric["partial_task_count"] += 1
        elif result_class in {"rejected", "FREE_REJECTED"}:
            metric["rejected_task_count"] += 1
        elif result_class in {"deferred", "EXTERNAL_SERVICE_DEFERRED"}:
            metric["deferred_task_count"] += 1
        if result_class in FREE_RESULT_CLASSES or (run.get("paid_call_avoided") is True):
            metric["paid_call_avoidance_count"] += 1

    for unit_id, unit in completed_unique.items():
        engine = _engine_key(str(unit.get("completed_by_engine") or "unknown"), str(unit.get("completed_by_model") or ""))
        if unit_id in counted_units:
            continue
        counted_units.add(unit_id)
        metric = engine_metrics.setdefault(engine, {
            "engine_id": engine,
            "engine_label": ENGINE_LABELS.get(engine, engine),
            "model_id": str(unit.get("completed_by_model") or ""),
            "role": "",
            "task_count": 1,
            "completed_task_count": 0,
            "partial_task_count": 0,
            "rejected_task_count": 0,
            "deferred_task_count": 0,
            "completed_unit_ids": [],
            "task_contribution_percent": None,
            "remaining_gap_percent": None,
            "cumulative_completion_percent": None,
            "validation_success_percent": None,
            "average_duration_ms": None,
            "paid_call_avoidance_count": 0,
            "estimated_paid_scope_saved_percent": None,
        })
        metric["completed_unit_ids"].append(unit_id)

    cumulative = 0
    for engine in sorted(engine_metrics, key=lambda key: ENGINE_SEQUENCE.index(key) if key in ENGINE_SEQUENCE else 999):
        metric = engine_metrics[engine]
        count = len(set(metric["completed_unit_ids"]))
        cumulative += count
        metric["completed_unit_ids"] = sorted(set(metric["completed_unit_ids"]))
        metric["task_contribution_percent"] = _percent(count, total_units)
        metric["cumulative_completion_percent"] = _percent(cumulative, total_units)
        metric["remaining_gap_percent"] = None if not enough_data else round(max(0.0, 100.0 - float(metric["cumulative_completion_percent"] or 0)), 2)
        metric["estimated_paid_scope_saved_percent"] = metric["task_contribution_percent"] if engine in FREE_ENGINES else 0.0
        validations = [run for run in engine_runs if _engine_key(str(run.get("engine_id") or ""), str(run.get("model_id") or "")) == engine and str(run.get("validation_outcome") or "").lower() in {"pass", "passed", "fail", "failed"}]
        if validations:
            passed = sum(1 for run in validations if str(run.get("validation_outcome") or "").lower() in {"pass", "passed"})
            metric["validation_success_percent"] = _percent(passed, len(validations))
        durations = [int(run.get("duration_ms") or 0) for run in engine_runs if _engine_key(str(run.get("engine_id") or ""), str(run.get("model_id") or "")) == engine and int(run.get("duration_ms") or 0) >= 0]
        if durations:
            metric["average_duration_ms"] = round(sum(durations) / len(durations), 2)

    completed_count = len(completed_unique)
    free_completed = sum(1 for unit in completed_unique.values() if _engine_key(str(unit.get("completed_by_engine") or ""), str(unit.get("completed_by_model") or "")) in FREE_ENGINES)
    local_completed = sum(1 for unit in completed_unique.values() if _engine_key(str(unit.get("completed_by_engine") or ""), str(unit.get("completed_by_model") or "")) in LOCAL_ENGINES)
    free_cloud_completed = sum(1 for unit in completed_unique.values() if _engine_key(str(unit.get("completed_by_engine") or ""), str(unit.get("completed_by_model") or "")) in FREE_CLOUD_ENGINES)
    paid_completed = sum(1 for unit in completed_unique.values() if _engine_key(str(unit.get("completed_by_engine") or ""), str(unit.get("completed_by_model") or "")) in PAID_ENGINES)
    paid_call_avoided = any((run.get("paid_call_avoided") is True) or str(run.get("result_class") or "") in FREE_RESULT_CLASSES for run in engine_runs)
    if completed_count == total_units and total_units > 0 and free_completed == completed_count:
        paid_call_avoided = True

    handoffs = build_handoff_records(safe_session, engine_metrics)
    confidence = "high" if enough_data and any(str(unit.get("validation_evidence") or unit.get("validation_outcome") or "") for unit in work_units) else ("medium" if enough_data else "not_enough_data")
    metrics = {
        "total_work_units": total_units,
        "completed_work_units": completed_count,
        "unique_completed_units": completed_count,
        "remaining_work_units": max(0, total_units - completed_count),
        "task_completion_percent": _percent(completed_count, total_units),
        "free_completion_percent": _percent(free_completed, total_units),
        "local_completion_percent": _percent(local_completed, total_units),
        "free_cloud_completion_percent": _percent(free_cloud_completed, total_units),
        "paid_completion_percent": _percent(paid_completed, total_units),
        "paid_work_reduction_percent": _percent(free_completed, total_units),
        "estimated_paid_scope_saved_percent": _percent(free_completed, total_units),
        "paid_call_avoided": paid_call_avoided,
        "codex_call_avoided": paid_call_avoided and paid_completed == 0,
        "whale_call_avoided": paid_call_avoided and paid_completed == 0,
        "deepseek_call_avoided": paid_call_avoided and paid_completed == 0,
        "calculation_basis": "validated_unique_work_units" if enough_data else "not_enough_measurable_work_units",
        "estimated_or_measured": "measured_scope" if enough_data else "not_enough_data",
        "confidence_level": confidence,
        "percentage_message": "" if enough_data else "Yuzde hesaplanamadi - yeterli olculebilir gorev birimi yok",
    }
    return {
        "ok": True,
        "session_id": session_id,
        "task_summary": safe_session.get("task_summary", ""),
        "active_engine": safe_session.get("active_engine") or (engine_runs[-1].get("engine_id") if engine_runs else ""),
        "metrics": metrics,
        "engine_chain": [engine_metrics[key] for key in sorted(engine_metrics, key=lambda item: ENGINE_SEQUENCE.index(item) if item in ENGINE_SEQUENCE else 999)],
        "work_units": work_units,
        "handoffs": handoffs,
        "calculation_evidence": {
            "calculation_basis": metrics["calculation_basis"],
            "total_work_units": total_units,
            "completed_work_units": completed_count,
            "unique_completed_units": completed_count,
            "validation_evidence": sorted({str(unit.get("validation_evidence") or unit.get("validation_outcome") or "") for unit in work_units if unit.get("validation_evidence") or unit.get("validation_outcome")}),
            "estimated_or_measured": metrics["estimated_or_measured"],
            "confidence_level": metrics["confidence_level"],
        },
        "generated_at": _now(),
    }


def build_handoff_records(session: Dict[str, Any], engine_metrics: Dict[str, Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    explicit = session.get("handoffs")
    records: List[Dict[str, Any]] = []
    if isinstance(explicit, list) and explicit:
        for item in explicit:
            if not isinstance(item, dict):
                continue
            record = {
                "handoff_from": str(item.get("handoff_from") or ""),
                "handoff_to": str(item.get("handoff_to") or ""),
                "handoff_reason": human_handoff_reason(str(item.get("handoff_reason") or item.get("reason") or "")),
                "completed_scope_digest": str(item.get("completed_scope_digest") or _digest(item.get("completed_scope", []), "completed-scope")),
                "remaining_gap": redact_secret(item.get("remaining_gap", "")),
                "remaining_gap_digest": str(item.get("remaining_gap_digest") or _digest(redact_secret(item.get("remaining_gap", "")), "remaining-gap")),
                "handoff_time": str(item.get("handoff_time") or item.get("created_at") or ""),
                "automatic_or_manual": str(item.get("automatic_or_manual") or "automatic"),
                "approval_required": bool(item.get("approval_required", False)),
            }
            records.append(record)
        return sorted(records, key=lambda record: (record["handoff_time"], record["handoff_from"], record["handoff_to"]))
    runs = [run for run in session.get("engine_runs", []) if isinstance(run, dict)]
    for index in range(len(runs) - 1):
        current = runs[index]
        nxt = runs[index + 1]
        records.append({
            "handoff_from": _engine_key(str(current.get("engine_id") or ""), str(current.get("model_id") or "")),
            "handoff_to": _engine_key(str(nxt.get("engine_id") or ""), str(nxt.get("model_id") or "")),
            "handoff_reason": human_handoff_reason(str(current.get("handoff_reason") or current.get("stop_reason") or current.get("failure_reason") or "")),
            "completed_scope_digest": str(current.get("completed_scope_digest") or _digest(current.get("completed_unit_ids", []), "completed-scope")),
            "remaining_gap": redact_secret(current.get("remaining_gap", "")),
            "remaining_gap_digest": str(current.get("remaining_gap_digest") or _digest(redact_secret(current.get("remaining_gap", "")), "remaining-gap")),
            "handoff_time": str(current.get("ended_at") or ""),
            "automatic_or_manual": str(current.get("automatic_or_manual") or "automatic"),
            "approval_required": bool(current.get("approval_required", False)),
        })
    return records


def human_handoff_reason(reason: str) -> str:
    normalized = reason.lower().strip()
    mapping = {
        "deterministic_limit": "Deterministik sinir",
        "local_model_gap": "Yerel model yetersiz kaldi",
        "complexity_or_context_gap": "Karmasiklik/context siniri",
        "schema_invalid": "Schema/output sorunu",
        "empty_response": "Schema/output sorunu",
        "rate_limited": "Ucretsiz servis yogun",
        "provider_unavailable": "Ucretsiz servis yogun",
        "validation_failed": "Validation basarisiz",
        "manual_approval_required": "Manuel uzman onayi gerekli",
        "paid_approval_required": "Ucretli motor onayi gerekli",
    }
    return mapping.get(normalized, reason or "Devir nedeni kaydedilmedi")


def _session_runtime_root(repository_root: str | Path) -> Path:
    return Path(repository_root or ".").expanduser().resolve() / ".luxcode_runtime" / "coder_sessions"


def load_persisted_analytics_sessions(repository_root: str | Path) -> List[Dict[str, Any]]:
    root = _session_runtime_root(repository_root)
    if not root.exists() or not root.is_dir():
        return []
    sessions: List[Dict[str, Any]] = []
    for session_dir in sorted(root.iterdir(), key=lambda item: item.name):
        session_file = session_dir / "session.json"
        if not session_file.exists() or session_file.stat().st_size > 120_000:
            continue
        try:
            data = json.loads(session_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        sessions.append(redact_secret({
            "session_id": data.get("session_id") or session_dir.name,
            "task_summary": data.get("task_summary", ""),
            "completed_scope": data.get("completed_scope", []),
            "remaining_gap": data.get("remaining_gap", data.get("coder_cli_remaining_gap", [])),
            "active_engine": data.get("selected_engine", ""),
            "work_units": data.get("analytics_work_units", []),
            "engine_runs": data.get("analytics_engine_runs", []),
            "handoffs": data.get("analytics_handoffs", []),
        }))
    return sessions


def _parse_time(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _session_time(session: Dict[str, Any]) -> Optional[datetime]:
    candidates = [session.get("started_at"), session.get("created_at"), session.get("generated_at")]
    raw_runs = session.get("engine_runs", []) if isinstance(session.get("engine_runs"), list) else []
    for run in raw_runs:
        if isinstance(run, dict):
            candidates.extend([run.get("started_at"), run.get("ended_at"), run.get("completed_at")])
    for candidate in candidates:
        parsed = _parse_time(str(candidate or ""))
        if parsed:
            return parsed
    return None


def _filter_sessions(sessions: List[Dict[str, Any]], *, from_: str = "", to: str = "", engine: str = "", model: str = "", status: str = "") -> List[Dict[str, Any]]:
    start = _parse_time(from_)
    end = _parse_time(to)
    output: List[Dict[str, Any]] = []
    for session in sessions:
        session_time = _session_time(session)
        if start and session_time and session_time < start:
            continue
        if end and session_time and session_time > end:
            continue
        runs = [run for run in session.get("engine_runs", []) if isinstance(run, dict)]
        if engine and not any(engine.lower() in str(run.get("engine_id", "")).lower() for run in runs):
            continue
        if model and not any(model.lower() in str(run.get("model_id", "")).lower() for run in runs):
            continue
        if status and not any(status.lower() == str(run.get("status", run.get("result_class", ""))).lower() for run in runs):
            continue
        output.append(session)
    return output


def build_analytics_summary(repository_root: str | Path = ".", *, sessions: Optional[List[Dict[str, Any]]] = None, from_: str = "", to: str = "", engine: str = "", model: str = "", status: str = "", **_: Any) -> Dict[str, Any]:
    raw_sessions = _filter_sessions(sessions if sessions is not None else load_persisted_analytics_sessions(repository_root), from_=from_, to=to, engine=engine, model=model, status=status)
    contributions = [calculate_session_contribution(session) for session in raw_sessions]
    measurable = [item for item in contributions if item["metrics"]["task_completion_percent"] is not None]
    avg_free = round(sum(float(item["metrics"]["free_completion_percent"] or 0) for item in measurable) / len(measurable), 2) if measurable else None
    avg_reduction = round(sum(float(item["metrics"]["paid_work_reduction_percent"] or 0) for item in measurable) / len(measurable), 2) if measurable else None
    return {
        "ok": True,
        "section": "Model Katkisi ve Tasarruf",
        "total_session_count": len(contributions),
        "fully_free_completed_count": sum(1 for item in contributions if item["metrics"]["task_completion_percent"] == 100 and item["metrics"]["paid_completion_percent"] in {0, None}),
        "paid_tier_session_count": sum(1 for item in contributions if (item["metrics"]["paid_completion_percent"] or 0) > 0),
        "codex_call_avoided_count": sum(1 for item in contributions if item["metrics"]["codex_call_avoided"]),
        "whale_call_avoided_count": sum(1 for item in contributions if item["metrics"]["whale_call_avoided"]),
        "deepseek_call_avoided_count": sum(1 for item in contributions if item["metrics"]["deepseek_call_avoided"]),
        "average_free_contribution_percent": avg_free,
        "average_paid_work_reduction_percent": avg_reduction,
        "deferred_paid_escalation_prevention_count": sum(1 for session in raw_sessions for run in session.get("engine_runs", []) if isinstance(run, dict) and str(run.get("result_class")) == "EXTERNAL_SERVICE_DEFERRED"),
        "percentage_message": "" if measurable else "Yuzde hesaplanamadi - yeterli olculebilir gorev birimi yok",
        "sessions": contributions,
        "generated_at": _now(),
    }


def build_engine_performance(repository_root: str | Path = ".", *, sessions: Optional[List[Dict[str, Any]]] = None, **filters: Any) -> Dict[str, Any]:
    summary = build_analytics_summary(repository_root, sessions=sessions, **filters)
    engines: Dict[str, Dict[str, Any]] = {}
    for session in summary["sessions"]:
        for metric in session["engine_chain"]:
            engine = metric["engine_id"]
            row = engines.setdefault(engine, {
                "engine": ENGINE_LABELS.get(engine, engine),
                "model": metric.get("model_id", ""),
                "total_task": 0,
                "completed_task": 0,
                "partial_task": 0,
                "rejected_task": 0,
                "deferred_task": 0,
                "average_contribution_percent": None,
                "validation_success_percent": None,
                "average_duration_ms": None,
                "paid_call_avoidance_count": 0,
                "estimated_savings_contribution_percent": None,
                "_contrib": [],
                "_validation": [],
                "_duration": [],
            })
            row["total_task"] += int(metric.get("task_count") or 1)
            row["completed_task"] += int(metric.get("completed_task_count") or 0)
            row["partial_task"] += int(metric.get("partial_task_count") or 0)
            row["rejected_task"] += int(metric.get("rejected_task_count") or 0)
            row["deferred_task"] += int(metric.get("deferred_task_count") or 0)
            row["paid_call_avoidance_count"] += int(metric.get("paid_call_avoidance_count") or 0)
            if metric.get("task_contribution_percent") is not None:
                row["_contrib"].append(float(metric["task_contribution_percent"]))
            if metric.get("validation_success_percent") is not None:
                row["_validation"].append(float(metric["validation_success_percent"]))
            if metric.get("average_duration_ms") is not None:
                row["_duration"].append(float(metric["average_duration_ms"]))
    rows = []
    for key in sorted(engines, key=lambda item: ENGINE_SEQUENCE.index(item) if item in ENGINE_SEQUENCE else 999):
        row = engines[key]
        row["average_contribution_percent"] = round(sum(row["_contrib"]) / len(row["_contrib"]), 2) if row["_contrib"] else None
        row["estimated_savings_contribution_percent"] = row["average_contribution_percent"] if key in FREE_ENGINES else 0.0
        row["validation_success_percent"] = round(sum(row["_validation"]) / len(row["_validation"]), 2) if row["_validation"] else None
        row["average_duration_ms"] = round(sum(row["_duration"]) / len(row["_duration"]), 2) if row["_duration"] else None
        for private in ("_contrib", "_validation", "_duration"):
            row.pop(private, None)
        rows.append(row)
    return {"ok": True, "engines": rows, "generated_at": _now()}


def build_savings_report(repository_root: str | Path = ".", *, sessions: Optional[List[Dict[str, Any]]] = None, **filters: Any) -> Dict[str, Any]:
    summary = build_analytics_summary(repository_root, sessions=sessions, **filters)
    return {
        "ok": True,
        "free_completion_percent": summary["average_free_contribution_percent"],
        "paid_work_reduction_percent": summary["average_paid_work_reduction_percent"],
        "paid_call_avoided_count": sum(1 for item in summary["sessions"] if item["metrics"]["paid_call_avoided"]),
        "codex_call_avoided_count": summary["codex_call_avoided_count"],
        "whale_call_avoided_count": summary["whale_call_avoided_count"],
        "deepseek_call_avoided_count": summary["deepseek_call_avoided_count"],
        "estimated_paid_scope_saved_percent": summary["average_paid_work_reduction_percent"],
        "cost_value_available": False,
        "cost_message": "Para degeri uretilmedi - token/fiyat verisi yok",
        "generated_at": _now(),
    }


def get_session_analytics(session_id: str, repository_root: str | Path = ".", *, sessions: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    iterable = sessions if sessions is not None else load_persisted_analytics_sessions(repository_root)
    for session in iterable:
        if str(session.get("session_id")) == str(session_id):
            return calculate_session_contribution(session)
    return {"ok": False, "error": "session_not_found", "session_id": session_id}


def get_handoff_trace(session_id: str, repository_root: str | Path = ".", *, sessions: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    session = get_session_analytics(session_id, repository_root, sessions=sessions)
    if not session.get("ok"):
        return session
    return {"ok": True, "session_id": session_id, "handoffs": session.get("handoffs", []), "generated_at": _now()}


def get_control_analytics_schema() -> Dict[str, Any]:
    return {
        "section": "Model Katkisi ve Tasarruf",
        "endpoints": [
            "GET /luxcode-control/analytics/summary",
            "GET /luxcode-control/analytics/engines",
            "GET /luxcode-control/analytics/sessions/{session_id}",
            "GET /luxcode-control/analytics/savings",
            "GET /luxcode-control/analytics/handoffs/{session_id}",
        ],
        "cli_commands": ["analytics-summary", "engine-performance", "session-contribution", "savings-report", "handoff-trace"],
        "no_auto_http": True,
        "percentage_policy": "no percentage without measurable work units",
    }
