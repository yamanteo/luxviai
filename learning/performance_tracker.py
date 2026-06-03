from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io_utils import load_json, save_json


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


def _as_topic_list(topics: Any) -> list[str]:
    if not isinstance(topics, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for t in topics:
        key = _norm_text(t)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _mode_signature(response_mode: dict[str, Any] | None) -> dict[str, Any]:
    mode = response_mode or {}
    return {
        "answer_length": _norm_text(mode.get("answer_length")) or "medium",
        "style": _norm_text(mode.get("style")) or "warm",
        "use_one_step": bool(mode.get("use_one_step")),
        "repair_first": bool(mode.get("repair_first")),
        "give_code": bool(mode.get("give_code")),
        "ask_question": bool(mode.get("ask_question")),
        "tone": _norm_text(mode.get("tone")) or "calm",
    }


def _mode_key(signature: dict[str, Any]) -> str:
    return (
        f"{signature.get('answer_length','medium')}|"
        f"{signature.get('style','warm')}|"
        f"one:{1 if signature.get('use_one_step') else 0}|"
        f"repair:{1 if signature.get('repair_first') else 0}|"
        f"code:{1 if signature.get('give_code') else 0}|"
        f"ask:{1 if signature.get('ask_question') else 0}|"
        f"tone:{signature.get('tone','calm')}"
    )


@dataclass
class PerformanceTracker:
    base_dir: Path

    @property
    def users_dir(self) -> Path:
        return self.base_dir / "data" / "users"

    def _performance_path(self, user_id: str) -> Path:
        return self.users_dir / user_id / "performance.json"

    def _load_perf(self, user_id: str) -> dict[str, Any]:
        default = {
            "last_updated": None,
            "overall_performance": 0.0,
            "history": [],
            "response_mode_stats": {
                "overall": {},
                "by_topic": {},
                "last_updated": None,
            },
        }
        perf = load_json(self._performance_path(user_id), default)
        if not isinstance(perf, dict):
            return default
        perf.setdefault("history", [])
        perf.setdefault("response_mode_stats", {"overall": {}, "by_topic": {}, "last_updated": None})
        return perf

    def _save_perf(self, user_id: str, data: dict[str, Any]) -> None:
        data["last_updated"] = now_iso()
        save_json(self._performance_path(user_id), data)

    def summarize(self, rows: list[dict[str, Any]]) -> dict[str, float]:
        if not rows:
            return {"overall": 0.0}
        vals = [
            safe_float((r.get("quality") or {}).get("total_score", r.get("score", 0.0)), 0.0)
            for r in rows
            if isinstance(r, dict)
        ]
        vals = [v for v in vals if v >= 0.0]
        if not vals:
            return {"overall": 0.0}
        return {"overall": round(sum(vals) / len(vals), 4)}

    def get_recent_performance(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        perf = self._load_perf(user_id)
        rows = perf.get("history", [])
        if not isinstance(rows, list):
            return []
        return [r for r in rows[-max(1, min(limit, 500)) :] if isinstance(r, dict)]

    def get_topic_success_scores(self, user_id: str) -> dict[str, Any]:
        rows = self.get_recent_performance(user_id, limit=200)
        topic_stats: dict[str, dict[str, float]] = {}
        for row in rows:
            quality = row.get("quality", {}) if isinstance(row.get("quality"), dict) else {}
            score = safe_float(quality.get("total_score", 0.0), 0.0)
            success = 1 if score >= 0.85 else 0
            topics = _as_topic_list(row.get("topics"))
            if not topics:
                topics = ["general"]
            for topic in topics:
                ts = topic_stats.setdefault(topic, {"count": 0.0, "total_score": 0.0, "success_count": 0.0})
                ts["count"] += 1
                ts["total_score"] += score
                ts["success_count"] += success
        result: dict[str, Any] = {}
        for topic, raw in topic_stats.items():
            count = max(1.0, raw["count"])
            avg = raw["total_score"] / count
            succ = raw["success_count"] / count
            result[topic] = {
                "count": int(raw["count"]),
                "average_score": round(avg, 4),
                "success_rate": round(succ, 4),
            }
        return result

    def get_response_mode_success(self, user_id: str) -> dict[str, Any]:
        perf = self._load_perf(user_id)
        stats = perf.get("response_mode_stats", {})
        if not isinstance(stats, dict):
            return {"overall": {}, "by_topic": {}, "last_updated": None}
        return {
            "overall": stats.get("overall", {}) if isinstance(stats.get("overall"), dict) else {},
            "by_topic": stats.get("by_topic", {}) if isinstance(stats.get("by_topic"), dict) else {},
            "last_updated": stats.get("last_updated"),
        }

    def _update_bucket(self, bucket: dict[str, Any], mode_key: str, signature: dict[str, Any], quality_score: float) -> None:
        row = bucket.setdefault(
            mode_key,
            {
                "count": 0,
                "total_score": 0.0,
                "average_score": 0.0,
                "success_count": 0,
                "success_rate": 0.0,
                "signature": signature,
                "last_updated": None,
            },
        )
        row["count"] = int(row.get("count", 0)) + 1
        row["total_score"] = safe_float(row.get("total_score", 0.0), 0.0) + quality_score
        row["average_score"] = round(row["total_score"] / max(1, row["count"]), 4)
        row["success_count"] = int(row.get("success_count", 0)) + (1 if quality_score >= 0.85 else 0)
        row["success_rate"] = round(row["success_count"] / max(1, row["count"]), 4)
        row["signature"] = signature
        row["last_updated"] = now_iso()
        bucket[mode_key] = row

    def update_response_mode_result(
        self,
        user_id: str,
        response_mode: dict[str, Any],
        quality_score: float,
        micro_signals: dict[str, Any] | None = None,
        topics: list[str] | None = None,
    ) -> dict[str, Any]:
        perf = self._load_perf(user_id)
        stats = perf.setdefault("response_mode_stats", {"overall": {}, "by_topic": {}, "last_updated": None})
        if not isinstance(stats, dict):
            stats = {"overall": {}, "by_topic": {}, "last_updated": None}
            perf["response_mode_stats"] = stats

        signature = _mode_signature(response_mode)
        mode_key = _mode_key(signature)
        q = clamp(safe_float(quality_score, 0.0))

        overall_bucket = stats.setdefault("overall", {})
        by_topic = stats.setdefault("by_topic", {})
        if not isinstance(overall_bucket, dict):
            overall_bucket = {}
            stats["overall"] = overall_bucket
        if not isinstance(by_topic, dict):
            by_topic = {}
            stats["by_topic"] = by_topic

        self._update_bucket(overall_bucket, mode_key, signature, q)
        normalized_topics = _as_topic_list(topics or [])
        if not normalized_topics:
            normalized_topics = ["general"]
        for topic in normalized_topics[:8]:
            topic_bucket = by_topic.setdefault(topic, {})
            if not isinstance(topic_bucket, dict):
                topic_bucket = {}
                by_topic[topic] = topic_bucket
            self._update_bucket(topic_bucket, mode_key, signature, q)

        stats["last_updated"] = now_iso()
        perf["response_mode_stats"] = stats

        # Lightweight meta for dashboard/inspection
        metrics = perf.setdefault("context_selection_metrics", {})
        if not isinstance(metrics, dict):
            metrics = {}
            perf["context_selection_metrics"] = metrics
        metrics.setdefault("response_mode_updates", 0)
        metrics["response_mode_updates"] = int(metrics.get("response_mode_updates", 0)) + 1
        metrics["last_response_mode_key"] = mode_key
        metrics["last_quality_score"] = round(q, 4)
        metrics["last_micro_confusion"] = round(safe_float((micro_signals or {}).get("confusion_level", 0.0), 0.0), 4)
        metrics["last_micro_patience"] = round(safe_float((micro_signals or {}).get("patience_level", 1.0), 1.0), 4)
        metrics["updated_at"] = now_iso()

        self._save_perf(user_id, perf)
        return stats

    def get_best_response_mode_for_context(
        self,
        user_id: str,
        topics: list[str] | None = None,
        micro_signals: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        stats = self.get_response_mode_success(user_id)
        overall = stats.get("overall", {}) if isinstance(stats.get("overall"), dict) else {}
        by_topic = stats.get("by_topic", {}) if isinstance(stats.get("by_topic"), dict) else {}
        topics = _as_topic_list(topics or [])
        micro = micro_signals or {}

        candidates: list[dict[str, Any]] = []
        for key, row in overall.items():
            if not isinstance(row, dict):
                continue
            candidates.append(
                {
                    "mode_key": key,
                    "signature": row.get("signature", {}),
                    "count": int(row.get("count", 0)),
                    "average_score": safe_float(row.get("average_score", 0.0), 0.0),
                    "success_rate": safe_float(row.get("success_rate", 0.0), 0.0),
                    "source": "overall",
                    "topic_boost": 0.0,
                }
            )

        for topic in topics[:6]:
            bucket = by_topic.get(topic, {})
            if not isinstance(bucket, dict):
                continue
            for key, row in bucket.items():
                if not isinstance(row, dict):
                    continue
                topic_count = int(row.get("count", 0))
                # prefer stronger local topic evidence if available
                boost = min(0.2, topic_count * 0.01)
                candidates.append(
                    {
                        "mode_key": key,
                        "signature": row.get("signature", {}),
                        "count": topic_count,
                        "average_score": safe_float(row.get("average_score", 0.0), 0.0),
                        "success_rate": safe_float(row.get("success_rate", 0.0), 0.0),
                        "source": f"topic:{topic}",
                        "topic_boost": boost,
                    }
                )

        if not candidates:
            return {
                "mode_key": "",
                "signature": {},
                "confidence": 0.0,
                "count": 0,
                "average_score": 0.0,
                "success_rate": 0.0,
                "source": "none",
                "reason": "no_history",
            }

        # consolidate best per mode_key
        consolidated: dict[str, dict[str, Any]] = {}
        for c in candidates:
            key = c["mode_key"]
            score = clamp(
                (c["average_score"] * 0.5)
                + (c["success_rate"] * 0.35)
                + (min(1.0, c["count"] / 12.0) * 0.1)
                + c["topic_boost"]
            )
            old = consolidated.get(key)
            if old is None or score > safe_float(old.get("_score"), -1.0):
                c["_score"] = score
                consolidated[key] = c

        ranked = sorted(consolidated.values(), key=lambda x: safe_float(x.get("_score"), 0.0), reverse=True)
        best = ranked[0]

        # avoid overreacting on thin/low confidence data
        count = int(best.get("count", 0))
        avg = safe_float(best.get("average_score", 0.0), 0.0)
        succ = safe_float(best.get("success_rate", 0.0), 0.0)
        confidence = clamp((safe_float(best.get("_score", 0.0), 0.0) * 0.6) + (min(1.0, count / 10.0) * 0.4))
        if count < 3:
            confidence = min(confidence, 0.64)
        if avg < 0.72:
            confidence = min(confidence, 0.62)

        # micro-aware caution
        confusion = safe_float(micro.get("confusion_level", 0.0), 0.0)
        patience = safe_float(micro.get("patience_level", 1.0), 1.0)
        signature = dict(best.get("signature", {})) if isinstance(best.get("signature"), dict) else {}
        if confusion >= 0.5 and patience <= 0.5:
            # emergency nudging toward one-step short mode if history isn't decisive
            if confidence < 0.8:
                signature["answer_length"] = "short"
                signature["style"] = "step_by_step"
                signature["use_one_step"] = True
                signature["give_code"] = False
                signature["ask_question"] = False

        return {
            "mode_key": str(best.get("mode_key", "")),
            "signature": signature,
            "confidence": round(confidence, 4),
            "count": count,
            "average_score": round(avg, 4),
            "success_rate": round(succ, 4),
            "source": str(best.get("source", "overall")),
            "reason": "history_weighted_selection",
        }

