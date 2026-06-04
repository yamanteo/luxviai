from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SAFE_FIELD_DEFAULTS: dict[str, Any] = {
    "ts": "",
    "route": "",
    "endpoint": "",
    "mode": "",
    "model": "",
    "budget_class": "",
    "observe_only": True,
    "policy_active": False,
    "prompt_chars": 0,
    "context_chars": 0,
    "history_chars": 0,
    "system_template_version": "lux_system_prompt_v1",
    "history_message_count": 0,
    "context_item_count": 0,
    "selected_layer_count": 0,
    "low_conf_suppressed_count": 0,
    "max_tokens": 0,
    "finish_reason": "",
    "auto_continue_parts": 0,
    "model_ms": 0,
    "first_chunk_ms": None,
    "total_ms": 0,
    "repair_call_count": 0,
    "count_guard_active": False,
    "safety_suppressed": False,
    "route_reason": "",
    "intent_bucket": "",
    "task_type": "",
    "count_constraint_present": False,
    "safety_level": "normal",
    "memory_recall_bucket": "",
    "project_topic_hash": "",
    "prompt_char_count": 0,
    "practical_support_candidate_count": 0,
    "estimated_input_tokens": 0,
    "estimated_output_tokens": 0,
    "estimated_cost": None,
    "cache_hint": "",
    "cache_status": "",
    "success": True,
    "error_type": "",
}

INT_FIELDS = {
    "prompt_chars",
    "context_chars",
    "history_chars",
    "history_message_count",
    "context_item_count",
    "selected_layer_count",
    "low_conf_suppressed_count",
    "max_tokens",
    "auto_continue_parts",
    "model_ms",
    "total_ms",
    "repair_call_count",
    "prompt_char_count",
    "practical_support_candidate_count",
    "estimated_input_tokens",
    "estimated_output_tokens",
}
OPTIONAL_INT_FIELDS = {"first_chunk_ms"}
BOOL_FIELDS = {
    "observe_only",
    "policy_active",
    "count_guard_active",
    "safety_suppressed",
    "count_constraint_present",
    "success",
}
FLOAT_FIELDS = {"estimated_cost"}
STRING_FIELDS = set(SAFE_FIELD_DEFAULTS) - INT_FIELDS - OPTIONAL_INT_FIELDS - BOOL_FIELDS - FLOAT_FIELDS


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def estimate_tokens(chars: Any) -> int:
    return max(0, int(round(_safe_int(chars, 0) / 4)))


def _safe_row(fields: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = dict(SAFE_FIELD_DEFAULTS)
    row.update({k: v for k, v in fields.items() if k in SAFE_FIELD_DEFAULTS})
    if not row.get("ts"):
        row["ts"] = now_iso()

    for key in INT_FIELDS:
        row[key] = max(0, _safe_int(row.get(key), 0))
    for key in OPTIONAL_INT_FIELDS:
        row[key] = None if row.get(key) is None else max(0, _safe_int(row.get(key), 0))
    for key in BOOL_FIELDS:
        row[key] = bool(row.get(key))
    for key in FLOAT_FIELDS:
        row[key] = _safe_float(row.get(key))
    for key in STRING_FIELDS:
        row[key] = str(row.get(key, "") or "")[:120]

    if not row["prompt_char_count"]:
        row["prompt_char_count"] = row["prompt_chars"]
    if not row["estimated_input_tokens"]:
        row["estimated_input_tokens"] = estimate_tokens(row["prompt_chars"] + row["history_chars"])
    if not row["estimated_output_tokens"]:
        row["estimated_output_tokens"] = estimate_tokens(row.get("response_chars", 0))
    return row


@dataclass
class CostLogger:
    base_dir: Path
    relative_path: str = "data/runtime/cost_logs.jsonl"

    @property
    def path(self) -> Path:
        return self.base_dir / self.relative_path

    def record(self, **fields: Any) -> None:
        try:
            row = _safe_row(fields)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception as exc:
            logging.warning(f"Cost logger skipped: {type(exc).__name__}")


def build_safe_cost_row(**fields: Any) -> dict[str, Any]:
    return _safe_row(fields)
