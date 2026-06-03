from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io_utils import append_jsonl, load_json, save_json


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _norm_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _lesson_signature(lesson: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _norm_text(lesson.get("kind")),
        _norm_text(lesson.get("theme")),
        _norm_text(lesson.get("behavior") or lesson.get("recommendation")),
    )


def _hybrid_signature(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _norm_text(row.get("prompt")),
        _norm_text(row.get("quality_label")),
        _norm_text(row.get("weakness")),
        _norm_text(row.get("optimizer_status")),
    )


@dataclass
class PersonalLearningStore:
    base_dir: Path

    @property
    def users_dir(self) -> Path:
        return self.base_dir / "data" / "users"

    def user_dir(self, user_id: str) -> Path:
        return self.users_dir / user_id

    def conversations_path(self, user_id: str) -> Path:
        return self.user_dir(user_id) / "conversations.jsonl"

    def lessons_path(self, user_id: str) -> Path:
        return self.user_dir(user_id) / "personal_lessons.json"

    def performance_path(self, user_id: str) -> Path:
        return self.user_dir(user_id) / "performance.json"

    def language_dna_path(self, user_id: str) -> Path:
        return self.user_dir(user_id) / "personal_language_dna.json"

    def dashboard_path(self, user_id: str) -> Path:
        return self.user_dir(user_id) / "personal_dashboard.json"

    def hybrid_questions_path(self, user_id: str) -> Path:
        return self.user_dir(user_id) / "hybrid_questions.json"

    def conversation_analysis_path(self, user_id: str) -> Path:
        return self.user_dir(user_id) / "conversation_analysis.jsonl"

    def ensure_user_files(self, user_id: str) -> None:
        if not self.lessons_path(user_id).exists():
            save_json(self.lessons_path(user_id), {"items": [], "updated_at": None, "count": 0})
        if not self.performance_path(user_id).exists():
            save_json(
                self.performance_path(user_id),
                {
                    "last_updated": None,
                    "overall_performance": 0.0,
                    "clarity_score": 0.0,
                    "emotional_alignment": 0.0,
                    "technical_success": 0.0,
                    "repair_success": 0.0,
                    "confusion_reduction": 0.0,
                    "patience_management": 0.0,
                    "naturalness_score": 0.0,
                    "task_success": 0.0,
                    "history": [],
                },
            )
        if not self.language_dna_path(user_id).exists():
            save_json(self.language_dna_path(user_id), {"keywords": {}, "style_preferences": []})
        if not self.dashboard_path(user_id).exists():
            save_json(self.dashboard_path(user_id), {"updated_at": None, "snapshots": []})
        if not self.hybrid_questions_path(user_id).exists():
            save_json(self.hybrid_questions_path(user_id), {"items": [], "updated_at": None, "count": 0})

    def append_conversation_record(self, user_id: str, record: dict[str, Any]) -> None:
        append_jsonl(self.conversations_path(user_id), record)

    def append_lesson(self, user_id: str, lesson: dict[str, Any]) -> None:
        data = load_json(self.lessons_path(user_id), {"items": []})
        items = data.setdefault("items", [])
        if isinstance(items, list) and items:
            last = items[-1]
            if isinstance(last, dict) and _lesson_signature(last) == _lesson_signature(lesson):
                # Avoid noisy consecutive duplicates.
                data["updated_at"] = now_iso()
                data["count"] = len(items)
                save_json(self.lessons_path(user_id), data)
                return
        items.append(lesson)
        if len(items) > 2000:
            data["items"] = items[-2000:]
        data["updated_at"] = now_iso()
        data["count"] = len(data.get("items", []))
        save_json(self.lessons_path(user_id), data)

    def append_hybrid_question(self, user_id: str, row: dict[str, Any]) -> None:
        data = load_json(self.hybrid_questions_path(user_id), {"items": []})
        items = data.setdefault("items", [])
        if isinstance(items, list) and items:
            last = items[-1]
            if isinstance(last, dict) and _hybrid_signature(last) == _hybrid_signature(row):
                data["updated_at"] = now_iso()
                data["count"] = len(items)
                save_json(self.hybrid_questions_path(user_id), data)
                return
        items.append(row)
        if len(data["items"]) > 500:
            data["items"] = data["items"][-500:]
        data["updated_at"] = now_iso()
        data["count"] = len(data.get("items", []))
        save_json(self.hybrid_questions_path(user_id), data)

    def append_performance(self, user_id: str, perf: dict[str, Any]) -> None:
        data = load_json(self.performance_path(user_id), {"history": []})
        history = data.setdefault("history", [])
        history.append(perf)
        if len(history) > 500:
            data["history"] = history[-500:]

        rows = data["history"]
        if rows:
            overall = sum(safe_float(r.get("quality", {}).get("total_score"), 0.0) for r in rows) / len(rows)
            clarity = sum(safe_float(r.get("quality", {}).get("clarity"), 0.0) for r in rows) / len(rows)
            emo = sum(safe_float(r.get("quality", {}).get("emotional_alignment"), 0.0) for r in rows) / len(rows)
            tech = sum(safe_float(r.get("quality", {}).get("technical_accuracy"), 0.0) for r in rows) / len(rows)
            repair = sum(safe_float(r.get("quality", {}).get("repair_value"), 0.0) for r in rows) / len(rows)
            conf = sum(1.0 - safe_float(r.get("signals", {}).get("confusion_level"), 0.0) for r in rows) / len(rows)
            patience = sum(safe_float(r.get("signals", {}).get("patience_level"), 0.0) for r in rows) / len(rows)
            natural = sum(safe_float(r.get("quality", {}).get("naturalness"), 0.0) for r in rows) / len(rows)
            task = sum(safe_float(r.get("quality", {}).get("task_success_potential"), 0.0) for r in rows) / len(rows)
        else:
            overall = clarity = emo = tech = repair = conf = patience = natural = task = 0.0

        data["last_updated"] = now_iso()
        data["overall_performance"] = round(overall, 4)
        data["clarity_score"] = round(clarity, 4)
        data["emotional_alignment"] = round(emo, 4)
        data["technical_success"] = round(tech, 4)
        data["repair_success"] = round(repair, 4)
        data["confusion_reduction"] = round(conf, 4)
        data["patience_management"] = round(patience, 4)
        data["naturalness_score"] = round(natural, 4)
        data["task_success"] = round(task, 4)
        save_json(self.performance_path(user_id), data)
