from __future__ import annotations

import re
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


def _sanitize_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"https?://\S+", "[link]", text, flags=re.IGNORECASE)
    text = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "[email]", text, flags=re.IGNORECASE)
    text = re.sub(r"\buser_[a-z0-9_]+\b", "[user]", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d{8,}\b", "[number]", text)
    return text.strip()


def _global_lesson_signature(lesson: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _norm_text(lesson.get("mode")),
        _norm_text(lesson.get("theme")),
        _norm_text(lesson.get("recommendation")),
    )


@dataclass
class GlobalLearningStore:
    base_dir: Path

    @property
    def global_dir(self) -> Path:
        return self.base_dir / "data" / "global"

    @property
    def lessons_path(self) -> Path:
        return self.global_dir / "global_lessons.json"

    @property
    def quality_path(self) -> Path:
        return self.global_dir / "global_quality_scores.json"

    @property
    def patterns_path(self) -> Path:
        return self.global_dir / "global_human_patterns.json"

    @property
    def dashboard_path(self) -> Path:
        return self.global_dir / "learning_dashboard.json"

    @property
    def analytics_runs_path(self) -> Path:
        return self.global_dir / "analytics_runs.jsonl"

    def ensure_global_files(self) -> None:
        if not self.lessons_path.exists():
            save_json(self.lessons_path, {"items": [], "updated_at": None})
        if not self.quality_path.exists():
            save_json(self.quality_path, {"topics": {}, "quality_labels": {}, "history": [], "updated_at": None})
        if not self.patterns_path.exists():
            save_json(self.patterns_path, {"patterns": [], "updated_at": None})
        if not self.dashboard_path.exists():
            save_json(self.dashboard_path, {"snapshots": [], "updated_at": None})

    def append_global_lesson(self, lesson: dict[str, Any]) -> None:
        safe_lesson = dict(lesson if isinstance(lesson, dict) else {})
        safe_lesson["recommendation"] = _sanitize_text(safe_lesson.get("recommendation", ""))
        safe_lesson["theme"] = _sanitize_text(safe_lesson.get("theme", ""))
        safe_lesson["mode"] = _sanitize_text(safe_lesson.get("mode", ""))
        data = load_json(self.lessons_path, {"items": []})
        items = data.setdefault("items", [])
        if isinstance(items, list) and items:
            last = items[-1]
            if isinstance(last, dict) and _global_lesson_signature(last) == _global_lesson_signature(safe_lesson):
                data["updated_at"] = now_iso()
                save_json(self.lessons_path, data)
                return
        items.append(safe_lesson)
        if len(data["items"]) > 2000:
            data["items"] = data["items"][-2000:]
        data["updated_at"] = now_iso()
        save_json(self.lessons_path, data)

    def append_quality_score(self, row: dict[str, Any]) -> None:
        data = load_json(self.quality_path, {"topics": {}, "quality_labels": {}, "history": []})
        history = data.setdefault("history", [])
        history.append(row)
        if len(history) > 2000:
            data["history"] = history[-2000:]
        data["updated_at"] = now_iso()
        save_json(self.quality_path, data)

    def update_quality_aggregate(self, quality: dict[str, Any], topic_scores: dict[str, float]) -> None:
        data = load_json(self.quality_path, {"topics": {}, "quality_labels": {}, "history": []})
        topics = data.setdefault("topics", {})
        labels = data.setdefault("quality_labels", {})

        label = str(quality.get("quality_label", "candidate"))
        labels[label] = int(labels.get(label, 0)) + 1

        for topic, score_raw in topic_scores.items():
            score = safe_float(score_raw, 0.0)
            row = topics.setdefault(topic, {"count": 0, "average_score": 0.0, "best_score": 0.0})
            count = int(row.get("count", 0))
            avg = safe_float(row.get("average_score", 0.0), 0.0)
            best = safe_float(row.get("best_score", 0.0), 0.0)
            new_count = count + 1
            new_avg = ((avg * count) + score) / max(1, new_count)
            row["count"] = new_count
            row["average_score"] = round(new_avg, 4)
            row["best_score"] = round(max(best, score), 4)
            topics[topic] = row

        hist_row = {
            "ts": now_iso(),
            "total_score": safe_float(quality.get("total_score", 0.0), 0.0),
            "quality_label": label,
            "weakness": str(quality.get("weakness", "")),
            "topic_scores": topic_scores,
        }
        history = data.setdefault("history", [])
        history.append(hist_row)
        if len(history) > 2000:
            data["history"] = history[-2000:]
        data["updated_at"] = now_iso()
        save_json(self.quality_path, data)

    def append_analytics_run(self, row: dict[str, Any]) -> None:
        append_jsonl(self.analytics_runs_path, row)
