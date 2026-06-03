from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from .io_utils import load_json, save_json
from .storage_rotation import StorageRotationEngine


_LOCK = Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


def _as_dt(value: Any) -> datetime | None:
    text = _norm_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def _jsonl_recent_count(path: Path, *, since: datetime, ts_keys: tuple[str, ...] = ("created_at", "ts")) -> int:
    if not path.exists():
        return 0
    count = 0
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if not isinstance(row, dict):
                    continue
                dt = None
                for k in ts_keys:
                    dt = _as_dt(row.get(k))
                    if dt is not None:
                        break
                if dt is not None and dt >= since:
                    count += 1
    except Exception:
        return 0
    return count


def _file_size(path: Path) -> int:
    try:
        return int(path.stat().st_size) if path.exists() else 0
    except Exception:
        return 0


@dataclass
class TelemetryEngine:
    base_dir: Path
    jsonl_rotation_threshold_bytes: int = 25 * 1024 * 1024  # 25 MB

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def users_dir(self) -> Path:
        return self.data_dir / "users"

    @property
    def global_dir(self) -> Path:
        return self.data_dir / "global"

    @property
    def telemetry_path(self) -> Path:
        return self.global_dir / "telemetry.json"

    @property
    def storage_rotation_report_path(self) -> Path:
        return self.global_dir / "storage_rotation_report.json"

    def _default_doc(self) -> dict[str, Any]:
        return {
            "version": 1,
            "updated_at": now_iso(),
            "background": {
                "total_background_runs": 0,
                "failed_background_runs": 0,
                "background_error_count": 0,
                "top_failing_modules": {},
                "last_background_error": {},
            },
        }

    def ensure_file(self) -> None:
        if self.telemetry_path.exists():
            return
        save_json(self.telemetry_path, self._default_doc())

    def _load(self) -> dict[str, Any]:
        self.ensure_file()
        doc = load_json(self.telemetry_path, self._default_doc())
        if not isinstance(doc, dict):
            doc = self._default_doc()
        if not isinstance(doc.get("background"), dict):
            doc["background"] = dict(self._default_doc()["background"])
        return doc

    def _save(self, doc: dict[str, Any]) -> None:
        doc["updated_at"] = now_iso()
        save_json(self.telemetry_path, doc)

    def record_background_result(self, *, success: bool, module: str, error: str | None = None) -> None:
        with _LOCK:
            doc = self._load()
            bg = doc.setdefault("background", {})
            if not isinstance(bg, dict):
                bg = {}
                doc["background"] = bg

            bg["total_background_runs"] = int(bg.get("total_background_runs", 0)) + 1
            if success:
                self._save(doc)
                return

            bg["failed_background_runs"] = int(bg.get("failed_background_runs", 0)) + 1
            bg["background_error_count"] = int(bg.get("background_error_count", 0)) + 1

            top = bg.setdefault("top_failing_modules", {})
            if not isinstance(top, dict):
                top = {}
                bg["top_failing_modules"] = top
            key = _norm_text(module) or "unknown"
            top[key] = int(top.get(key, 0)) + 1

            bg["last_background_error"] = {
                "at": now_iso(),
                "module": key,
                "message": _norm_text(error)[:300],
            }
            self._save(doc)

    def _iter_user_dirs(self) -> list[Path]:
        if not self.users_dir.exists():
            return []
        out: list[Path] = []
        try:
            for p in self.users_dir.iterdir():
                if p.is_dir():
                    out.append(p)
        except Exception:
            return []
        return out

    def _aggregate_context_metrics(self) -> dict[str, Any]:
        total_context_count = 0
        weighted_len_sum = 0.0
        weighted_items_sum = 0.0
        max_context_length = 0
        dropped_low_conf = 0

        for user_dir in self._iter_user_dirs():
            perf = load_json(user_dir / "performance.json", {})
            if not isinstance(perf, dict):
                continue
            m = perf.get("context_selection_metrics", {})
            if not isinstance(m, dict):
                continue
            count = int(m.get("context_selection_count", 0))
            avg_len = safe_float(m.get("average_context_length", 0.0), 0.0)
            avg_items = safe_float(m.get("average_context_item_count", m.get("prompt_context_item_count", 0.0)), 0.0)
            max_len = int(m.get("max_context_length", 0))
            total_context_count += count
            weighted_len_sum += avg_len * max(0, count)
            weighted_items_sum += avg_items * max(0, count)
            max_context_length = max(max_context_length, max_len, int(avg_len))
            dropped_low_conf += int(m.get("dropped_low_confidence_items", 0))

        avg_len_global = (weighted_len_sum / max(1, total_context_count)) if total_context_count > 0 else 0.0
        avg_items_global = (weighted_items_sum / max(1, total_context_count)) if total_context_count > 0 else 0.0

        return {
            "average_context_length": round(avg_len_global, 2),
            "max_context_length": int(max_context_length),
            "average_context_item_count": round(avg_items_global, 2),
            "context_selection_count": int(total_context_count),
            "dropped_low_confidence_items": int(dropped_low_conf),
        }

    def _aggregate_quality_windows(self) -> dict[str, float]:
        quality = load_json(self.global_dir / "global_quality_scores.json", {"history": []})
        history = quality.get("history", []) if isinstance(quality, dict) else []
        rows = [r for r in history if isinstance(r, dict)]
        now_utc = datetime.now(timezone.utc)
        d7 = now_utc - timedelta(days=7)
        d30 = now_utc - timedelta(days=30)

        vals7: list[float] = []
        vals30: list[float] = []
        for row in rows:
            ts = _as_dt(row.get("ts"))
            if ts is None:
                continue
            score = safe_float(row.get("total_score", 0.0), 0.0)
            if ts >= d30:
                vals30.append(score)
                if ts >= d7:
                    vals7.append(score)

        return {
            "average_quality_score_7d": round(sum(vals7) / max(1, len(vals7)), 4) if vals7 else 0.0,
            "average_quality_score_30d": round(sum(vals30) / max(1, len(vals30)), 4) if vals30 else 0.0,
        }

    def _collect_jsonl_paths(self) -> list[Path]:
        paths = [
            self.global_dir / "fine_tune_candidates.jsonl",
            self.global_dir / "elite_candidates.jsonl",
            self.global_dir / "pending_candidates.jsonl",
            self.global_dir / "rejected_candidates.jsonl",
            self.global_dir / "analytics_runs.jsonl",
        ]
        for user_dir in self._iter_user_dirs():
            paths.append(user_dir / "conversations.jsonl")
            paths.append(user_dir / "conversation_analysis.jsonl")
            paths.append(user_dir / "human_risk_healing.jsonl")
        return [p for p in paths if p.exists()]

    def _storage_health(self) -> dict[str, Any]:
        learning_size = 0
        try:
            for p in (self.base_dir / "learning").rglob("*.py"):
                learning_size += _file_size(p)
        except Exception:
            learning_size = 0

        jsonl_paths = self._collect_jsonl_paths()
        largest = sorted(
            [{"path": str(p).replace("\\", "/"), "size_bytes": _file_size(p)} for p in jsonl_paths],
            key=lambda x: int(x.get("size_bytes", 0)),
            reverse=True,
        )
        rotation_targets = [x for x in largest if int(x.get("size_bytes", 0)) >= self.jsonl_rotation_threshold_bytes]
        return {
            "learning_file_size": int(learning_size),
            "jsonl_rotation_needed": bool(rotation_targets),
            "largest_jsonl_files": largest[:8],
            "rotation_targets": rotation_targets[:8],
        }

    def _fine_tune_health(self) -> dict[str, Any]:
        fine_path = self.global_dir / "fine_tune_candidates.jsonl"
        elite_path = self.global_dir / "elite_candidates.jsonl"
        pending_path = self.global_dir / "pending_candidates.jsonl"
        rejected_path = self.global_dir / "rejected_candidates.jsonl"

        total = _count_jsonl(fine_path)
        elite = _count_jsonl(elite_path)
        pending = _count_jsonl(pending_path)
        rejected = _count_jsonl(rejected_path)

        since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        growth_24h = _jsonl_recent_count(fine_path, since=since_24h, ts_keys=("created_at", "ts"))
        size_bytes = _file_size(fine_path)

        return {
            "total_candidates": int(total),
            "elite_candidates": int(elite),
            "pending_candidates": int(pending),
            "rejected_candidates": int(rejected),
            "fine_tune_candidate_growth": int(growth_24h),
            "file_size_bytes": int(size_bytes),
            "jsonl_rotation_needed": bool(size_bytes >= self.jsonl_rotation_threshold_bytes),
        }

    def _storage_rotation_report(self) -> dict[str, Any]:
        # Keep reads defensive and cheap.
        try:
            engine = StorageRotationEngine(self.base_dir)
            return engine.build_storage_rotation_report()
        except Exception:
            raw = load_json(self.storage_rotation_report_path, {})
            if isinstance(raw, dict):
                return raw
            return {}

    def build_snapshot(self) -> dict[str, Any]:
        # All reads are defensive; telemetry must never crash callers.
        with _LOCK:
            doc = self._load()

        bg = doc.get("background", {}) if isinstance(doc.get("background"), dict) else {}
        total_runs = int(bg.get("total_background_runs", 0))
        failed_runs = int(bg.get("failed_background_runs", 0))
        background_error_count = int(bg.get("background_error_count", 0))
        success_rate = (
            round((total_runs - failed_runs) / max(1, total_runs), 4)
            if total_runs > 0
            else 1.0
        )
        top_fail = bg.get("top_failing_modules", {}) if isinstance(bg.get("top_failing_modules"), dict) else {}
        top_failing_modules = sorted(
            [{"module": str(k), "count": int(v)} for k, v in top_fail.items()],
            key=lambda x: int(x["count"]),
            reverse=True,
        )[:8]
        last_background_error = bg.get("last_background_error", {}) if isinstance(bg.get("last_background_error"), dict) else {}

        context = self._aggregate_context_metrics()
        quality = self._aggregate_quality_windows()
        storage = self._storage_health()
        fine = self._fine_tune_health()
        rotation = self._storage_rotation_report()

        jsonl_rotation_needed = (
            bool(storage.get("jsonl_rotation_needed"))
            or bool(fine.get("jsonl_rotation_needed"))
            or bool(rotation.get("rotation_needed", False))
        )

        system_health = {
            "background_success_rate": success_rate,
            "average_context_length": context.get("average_context_length", 0.0),
            "max_context_length": context.get("max_context_length", 0),
            "average_context_item_count": context.get("average_context_item_count", 0.0),
            "average_quality_score_7d": quality.get("average_quality_score_7d", 0.0),
            "average_quality_score_30d": quality.get("average_quality_score_30d", 0.0),
            "jsonl_rotation_needed": jsonl_rotation_needed,
        }

        background_job_health = {
            "total_background_runs": total_runs,
            "failed_background_runs": failed_runs,
            "background_error_count": background_error_count,
            "success_rate": success_rate,
            "top_failing_modules": top_failing_modules,
            "last_background_error": {
                "at": _norm_text(last_background_error.get("at")),
                "module": _norm_text(last_background_error.get("module")),
                "message": _norm_text(last_background_error.get("message")),
            }
            if last_background_error
            else {},
        }

        context_health = {
            "average_context_length": context.get("average_context_length", 0.0),
            "max_context_length": context.get("max_context_length", 0),
            "average_context_item_count": context.get("average_context_item_count", 0.0),
            "average_context_length_warning": bool(safe_float(context.get("average_context_length", 0.0), 0.0) >= 1050),
            "near_limit_warning": bool(int(context.get("max_context_length", 0)) >= 1150),
            "context_selection_count": int(context.get("context_selection_count", 0)),
        }

        learning_storage_health = {
            "learning_file_size": int(storage.get("learning_file_size", 0)),
            "jsonl_rotation_needed": bool(storage.get("jsonl_rotation_needed", False)),
            "largest_jsonl_files": storage.get("largest_jsonl_files", []),
            "rotation_targets": storage.get("rotation_targets", []),
            "storage_rotation": rotation.get("last_run", {}),
            "last_rotation_at": rotation.get("last_rotation_at"),
            "archived_files_count": int(rotation.get("archived_files_count", 0)),
            "rotation_needed": bool(rotation.get("rotation_needed", False)),
            "rotation_errors_count": int(rotation.get("rotation_errors_count", 0)),
            "active_file_sizes": rotation.get("active_file_sizes", {}),
            "archive_health": rotation.get("archive_health", {}),
        }

        fine_tune_dataset_health = {
            "fine_tune_candidate_growth": int(fine.get("fine_tune_candidate_growth", 0)),
            "total_candidates": int(fine.get("total_candidates", 0)),
            "elite_candidates": int(fine.get("elite_candidates", 0)),
            "pending_candidates": int(fine.get("pending_candidates", 0)),
            "rejected_candidates": int(fine.get("rejected_candidates", 0)),
            "file_size_bytes": int(fine.get("file_size_bytes", 0)),
            "jsonl_rotation_needed": bool(fine.get("jsonl_rotation_needed", False)),
            "rotation_needed": bool(rotation.get("rotation_needed", False)),
            "last_rotation_at": rotation.get("last_rotation_at"),
        }

        telemetry_metrics = {
            "background_error_count": background_error_count,
            "average_context_length": context.get("average_context_length", 0.0),
            "max_context_length": context.get("max_context_length", 0),
            "average_context_item_count": context.get("average_context_item_count", 0.0),
            "learning_file_size": int(storage.get("learning_file_size", 0)),
            "fine_tune_candidate_growth": int(fine.get("fine_tune_candidate_growth", 0)),
            "jsonl_rotation_needed": jsonl_rotation_needed,
            "average_quality_score_7d": quality.get("average_quality_score_7d", 0.0),
            "average_quality_score_30d": quality.get("average_quality_score_30d", 0.0),
            "top_failing_modules": top_failing_modules,
            "last_background_error": background_job_health.get("last_background_error", {}),
            "total_background_runs": total_runs,
            "failed_background_runs": failed_runs,
            "success_rate": success_rate,
            "storage_rotation_needed": bool(rotation.get("rotation_needed", False)),
            "last_rotation_at": rotation.get("last_rotation_at"),
            "archived_files_count": int(rotation.get("archived_files_count", 0)),
            "rotation_errors_count": int(rotation.get("rotation_errors_count", 0)),
        }

        return {
            "generated_at": now_iso(),
            "system_health": system_health,
            "learning_storage_health": learning_storage_health,
            "background_job_health": background_job_health,
            "context_health": context_health,
            "fine_tune_dataset_health": fine_tune_dataset_health,
            "telemetry_metrics": telemetry_metrics,
            "storage_rotation": {
                "last_rotation_at": rotation.get("last_rotation_at"),
                "rotation_needed": bool(rotation.get("rotation_needed", False)),
                "archived_files_count": int(rotation.get("archived_files_count", 0)),
                "rotation_errors_count": int(rotation.get("rotation_errors_count", 0)),
                "active_file_sizes": rotation.get("active_file_sizes", {}),
                "archive_health": rotation.get("archive_health", {}),
                "last_run": rotation.get("last_run", {}),
            },
        }
