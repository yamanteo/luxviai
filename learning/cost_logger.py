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
    "efficiency_dry_run_route": "",
    "efficiency_dry_run_confidence": 0.0,
    "would_use_short_context": False,
    "estimated_context_savings_chars": 0,
    "estimated_layer_savings_count": 0,
    "mandatory_guards_kept": "",
    "shadow_compare_enabled": False,
    "shadow_compare_route": "",
    "shadow_compare_summary": {},
    "current_context_chars": 0,
    "proposed_context_chars": 0,
    "estimated_saved_chars": 0,
    "proposed_history_limit": 18,
    "proposed_skipped_layers": [],
    "reason_tags": [],
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
    "estimated_context_savings_chars",
    "estimated_layer_savings_count",
    "current_context_chars",
    "proposed_context_chars",
    "estimated_saved_chars",
    "proposed_history_limit",
}
OPTIONAL_INT_FIELDS = {"first_chunk_ms"}
BOOL_FIELDS = {
    "observe_only",
    "policy_active",
    "count_guard_active",
    "safety_suppressed",
    "count_constraint_present",
    "would_use_short_context",
    "shadow_compare_enabled",
    "success",
}
FLOAT_FIELDS = {"estimated_cost", "efficiency_dry_run_confidence"}
LIST_FIELDS = {"proposed_skipped_layers", "reason_tags"}
DICT_FIELDS = {"shadow_compare_summary"}
STRING_FIELDS = set(SAFE_FIELD_DEFAULTS) - INT_FIELDS - OPTIONAL_INT_FIELDS - BOOL_FIELDS - FLOAT_FIELDS - LIST_FIELDS - DICT_FIELDS
DRY_RUN_ROUTES = {
    "full_current_path",
    "short_technical_candidate",
    "emotional_full_context_needed",
    "dream_symbolic_needed",
    "count_constrained_needed",
    "crisis_safety_full_needed",
    "workspace_future_needed",
}
REASON_TAGS = DRY_RUN_ROUTES | {
    "short_context_candidate",
    "full_context_needed",
    "short_technical_safe_path_candidate",
    "mandatory_safety_full_context",
    "luxeph_privacy_mode_no_short_path",
    "identity_guard_caution",
    "count_format_guard_full_context",
    "dream_symbolic_context",
    "emotional_support_context_needed",
    "long_generation_or_workspace_needs_context",
    "normal_chat_keep_current_path",
    "efficiency_router_fallback",
}
SKIPPABLE_LAYER_TAGS = {"group3_deep", "group4_deep", "long_memory"}
KEEP_GUARD_TAGS = {"safety", "identity_guard", "count_guard", "basic_command_intent", "cost_logging"}
MANDATORY_GUARDS = "safety,identity,count,basic_command,cost_logging"


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


def _safe_string_list(value: Any, allowed: set[str] | None = None, limit: int = 12) -> list[str]:
    raw = value if isinstance(value, list) else []
    out: list[str] = []
    for item in raw:
        text = str(item or "").strip()[:80]
        if not text:
            continue
        if allowed is not None and text not in allowed:
            continue
        if text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _safe_shadow_summary(value: Any) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    route = str(data.get("route", "") or "")[:80]
    if route not in DRY_RUN_ROUTES:
        route = "full_current_path"
    return {
        "route": route,
        "would_keep": _safe_string_list(data.get("would_keep"), KEEP_GUARD_TAGS, limit=8),
        "would_limit_history_to": max(0, _safe_int(data.get("would_limit_history_to"), 18)),
        "would_skip": _safe_string_list(data.get("would_skip"), SKIPPABLE_LAYER_TAGS, limit=8),
        "estimated_saved_chars": max(0, _safe_int(data.get("estimated_saved_chars"), 0)),
        "confidence": _safe_float(data.get("confidence")) or 0.0,
    }


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
    row["proposed_skipped_layers"] = _safe_string_list(row.get("proposed_skipped_layers"), SKIPPABLE_LAYER_TAGS, limit=8)
    row["reason_tags"] = _safe_string_list(row.get("reason_tags"), REASON_TAGS, limit=8)
    row["shadow_compare_summary"] = _safe_shadow_summary(row.get("shadow_compare_summary"))
    for key in STRING_FIELDS:
        row[key] = str(row.get(key, "") or "")[:120]
    if row["efficiency_dry_run_route"] not in DRY_RUN_ROUTES:
        row["efficiency_dry_run_route"] = "full_current_path"
    if row["shadow_compare_route"] not in DRY_RUN_ROUTES:
        row["shadow_compare_route"] = row["efficiency_dry_run_route"] or "full_current_path"
    if row["mandatory_guards_kept"]:
        row["mandatory_guards_kept"] = MANDATORY_GUARDS

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
