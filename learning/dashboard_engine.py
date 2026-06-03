from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .behavior_policy import BehaviorPolicyManager
from .io_utils import load_json
from .telemetry import TelemetryEngine


TOPIC_META: dict[str, dict[str, str]] = {
    "relationships": {"label": "Relationships", "recommendation": "Relationship + empathy + boundary training should increase."},
    "emotional_support": {"label": "Emotional support", "recommendation": "Short, calm and validating response style should stay primary."},
    "technical_guidance": {"label": "Technical guidance", "recommendation": "One-step + verification guidance pattern should be reinforced."},
    "coding_help": {"label": "Coding help", "recommendation": "Actionable code guidance with quick checks should be increased."},
    "creative_ideation": {"label": "Creative ideation", "recommendation": "Creative ideas should be paired with concrete execution steps."},
    "natural_language": {"label": "Natural language", "recommendation": "Reduce robotic phrasing and keep warm human cadence."},
    "repair_quality": {"label": "Repair quality", "recommendation": "Rupture-repair language should be faster and clearer."},
    "confusion_reduction": {"label": "Confusion reduction", "recommendation": "When confusion spikes, narrow scope and give one clear next step."},
    "patience_management": {"label": "Patience management", "recommendation": "Adapt response density to patience level."},
    "task_success": {"label": "Task success", "recommendation": "Every technical flow should end with explicit completion checks."},
    "human_like_tone": {"label": "Human-like tone", "recommendation": "Keep warm + clear + grounded conversational rhythm."},
    "safety_ethics": {"label": "Safety & ethics", "recommendation": "Maintain safe boundaries and avoid risky certainty."},
    "fine_tune_quality": {"label": "Fine-tune quality", "recommendation": "Increase anonymized reusable high-quality training candidates."},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, safe_float(v, lo)))


def parse_iso_optional(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def quality_label(score: float) -> str:
    s = clamp(score)
    if s < 0.45:
        return "weak"
    if s < 0.75:
        return "improving"
    if s < 0.90:
        return "strong"
    return "elite"


def growth_percent(previous_score: float, current_score: float) -> int:
    return int(round((safe_float(current_score) - safe_float(previous_score)) * 100))


def filter_rows_by_days(rows: list[dict[str, Any]], now_utc: datetime, days: int, offset_days: int = 0) -> list[dict[str, Any]]:
    end = now_utc - timedelta(days=offset_days)
    start = end - timedelta(days=days)
    out: list[dict[str, Any]] = []
    for row in rows:
        ts = parse_iso_optional(row.get("ts"))
        if ts and start <= ts < end:
            out.append(row)
    return out


@dataclass
class LearningDashboardEngine:
    base_dir: Path

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
    def policy(self) -> BehaviorPolicyManager:
        return BehaviorPolicyManager(self.base_dir)

    @property
    def telemetry(self) -> TelemetryEngine:
        return TelemetryEngine(self.base_dir)

    def _count_jsonl(self, path: Path) -> int:
        if not path.exists():
            return 0
        try:
            with path.open("r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    def fine_tune_stats(self) -> dict[str, Any]:
        fine = self._count_jsonl(self.global_dir / "fine_tune_candidates.jsonl")
        elite = self._count_jsonl(self.global_dir / "elite_candidates.jsonl")
        pending = self._count_jsonl(self.global_dir / "pending_candidates.jsonl")
        rejected = self._count_jsonl(self.global_dir / "rejected_candidates.jsonl")

        last_dt: datetime | None = None
        for p in [
            self.global_dir / "fine_tune_candidates.jsonl",
            self.global_dir / "elite_candidates.jsonl",
            self.global_dir / "pending_candidates.jsonl",
            self.global_dir / "rejected_candidates.jsonl",
        ]:
            if p.exists():
                ts = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
                if last_dt is None or ts > last_dt:
                    last_dt = ts

        return {
            "total_candidates": fine,
            "elite_candidates": elite,
            "pending_candidates": pending,
            "rejected_candidates": rejected,
            "last_candidate_created_at": now_iso() if last_dt is None else last_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }

    def _performance_rows(self, user_id: str) -> list[dict[str, Any]]:
        perf = load_json(self.users_dir / user_id / "performance.json", {"history": []})
        rows = perf.get("history", [])
        return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []

    def _human_support_metrics(self, user_id: str) -> dict[str, Any]:
        summary = load_json(self.users_dir / user_id / "human_risk_summary.json", {"counts": {}})
        counts = summary.get("counts", {}) if isinstance(summary.get("counts"), dict) else {}
        sensitive = max(1, int(counts.get("sensitive", 0)))
        regulation = clamp(
            (
                int(counts.get("grounding_needed", 0))
                + int(counts.get("boundary_support", 0))
                + int(counts.get("relationship_distress_support", 0))
            )
            / sensitive
        )
        return {
            "regulation_support_score": round(regulation, 4),
            "safety_sensitive_interactions": int(counts.get("sensitive", 0)),
            "trust_repair_support": int(counts.get("boundary_support", 0)),
            "high_emotional_load_count": int(counts.get("high_risk", 0)) + int(counts.get("crisis", 0)),
            "grounding_needed_count": int(counts.get("grounding_needed", 0)),
            "boundary_support_count": int(counts.get("boundary_support", 0)),
            "relationship_distress_support": int(counts.get("relationship_distress_support", 0)),
            "impulse_slowdown_support": int(counts.get("impulse_slowdown_support", 0)),
            "threat_perception_support": int(counts.get("threat_perception_support", 0)),
            "trauma_sensitive_support": int(counts.get("trauma_sensitive_support", 0)),
            "updated_at": summary.get("last_updated"),
        }

    def _group1_metrics_from_rows(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {
                "emotion_signal_score": 0.0,
                "hidden_need_signal": 0.0,
                "tone_adaptation_score": 0.0,
                "human_layer_alignment": 0.0,
                "emotional_load_level": 0.0,
                "clarity_need_signal": 0.0,
                "repair_need_signal": 0.0,
                "safety_sensitive_signal": 0.0,
                "response_tone_adjustment": "warm_balanced",
                "samples": 0,
            }

        fields = [
            "emotion_signal_score",
            "hidden_need_signal",
            "tone_adaptation_score",
            "human_layer_alignment",
            "emotional_load_level",
            "clarity_need_signal",
            "repair_need_signal",
            "safety_sensitive_signal",
        ]
        accum = {k: 0.0 for k in fields}
        count = 0
        tone_counter: dict[str, int] = {}

        for row in rows[-400:]:
            signals = row.get("signals", {}) if isinstance(row.get("signals"), dict) else {}
            for k in fields:
                accum[k] += safe_float(signals.get(k), 0.0)
            tone = str(signals.get("response_tone_adjustment", "")).strip()
            if tone:
                tone_counter[tone] = tone_counter.get(tone, 0) + 1
            count += 1

        top_tone = "warm_balanced"
        if tone_counter:
            top_tone = sorted(tone_counter.items(), key=lambda kv: kv[1], reverse=True)[0][0]

        out = {k: round(accum[k] / max(1, count), 4) for k in fields}
        out["response_tone_adjustment"] = top_tone
        out["samples"] = count
        return out

    def _group2_metrics_from_rows(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {
                "narrative_continuity_score": 0.0,
                "context_coherence_score": 0.0,
                "contradiction_signal_score": 0.0,
                "clarification_need_signal": 0.0,
                "relationship_distress_signal": 0.0,
                "boundary_support_signal": 0.0,
                "safety_ethics_alignment": 0.0,
                "privacy_protection_score": 0.0,
                "response_risk_reduction": 0.0,
                "response_tone_adjustment": "coherent_calm",
                "samples": 0,
            }

        fields = [
            "narrative_continuity_score",
            "context_coherence_score",
            "contradiction_signal_score",
            "clarification_need_signal",
            "relationship_distress_signal",
            "boundary_support_signal",
            "safety_ethics_alignment",
            "privacy_protection_score",
            "response_risk_reduction",
        ]
        accum = {k: 0.0 for k in fields}
        count = 0
        tone_counter: dict[str, int] = {}

        for row in rows[-400:]:
            signals = row.get("signals", {}) if isinstance(row.get("signals"), dict) else {}
            for k in fields:
                accum[k] += safe_float(signals.get(k), 0.0)
            tone = str(signals.get("group2_response_tone_adjustment", "")).strip()
            if tone:
                tone_counter[tone] = tone_counter.get(tone, 0) + 1
            count += 1

        top_tone = "coherent_calm"
        if tone_counter:
            top_tone = sorted(tone_counter.items(), key=lambda kv: kv[1], reverse=True)[0][0]

        out = {k: round(accum[k] / max(1, count), 4) for k in fields}
        out["response_tone_adjustment"] = top_tone
        out["samples"] = count
        return out

    def _group3_metrics_from_rows(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        base = {
            "group3_signal_counts": 0,
            "symbolic_signal_count": 0,
            "dream_context_count": 0,
            "existential_signal_count": 0,
            "memory_candidate_count": 0,
            "memory_gate_allowed_count": 0,
            "memory_gate_blocked_count": 0,
            "duplicate_anchor_block_count": 0,
            "sensitive_block_count": 0,
            "pii_block_count": 0,
            "low_confidence_block_count": 0,
            "memory_gate_block_reasons": {},
            "samples": 0,
        }
        if not rows:
            return base

        reason_counts: dict[str, int] = {}
        count = 0
        for row in rows[-600:]:
            signals = row.get("signals", {}) if isinstance(row.get("signals"), dict) else {}
            base["group3_signal_counts"] += int(signals.get("group3_signal_count", 0) or 0)
            base["symbolic_signal_count"] += int(signals.get("symbolic_signal_count", 0) or 0)
            base["dream_context_count"] += int(signals.get("dream_context_count", 0) or 0)
            base["existential_signal_count"] += int(signals.get("existential_signal_count", 0) or 0)
            base["memory_candidate_count"] += int(signals.get("memory_candidate_count", 0) or 0)
            base["memory_gate_allowed_count"] += int(signals.get("memory_gate_allowed_count", 0) or 0)
            base["memory_gate_blocked_count"] += int(signals.get("memory_gate_blocked_count", 0) or 0)
            base["duplicate_anchor_block_count"] += int(signals.get("duplicate_anchor_block_count", 0) or 0)
            base["sensitive_block_count"] += int(signals.get("sensitive_block_count", 0) or 0)
            base["pii_block_count"] += int(signals.get("pii_block_count", 0) or 0)
            base["low_confidence_block_count"] += int(signals.get("low_confidence_block_count", 0) or 0)
            reason = str(signals.get("memory_gate_block_reason", "")).strip()
            blocked = int(signals.get("memory_gate_blocked_count", 0) or 0)
            if blocked > 0 and reason and reason != "none":
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            count += 1

        base["memory_gate_block_reasons"] = dict(sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:12])
        base["samples"] = count
        return base

    def _topic_scores_from_rows(self, rows: list[dict[str, Any]]) -> dict[str, float]:
        if not rows:
            return {k: 0.0 for k in TOPIC_META}

        acc: dict[str, list[float]] = {k: [] for k in TOPIC_META}
        for row in rows:
            q = row.get("quality", {}) if isinstance(row.get("quality"), dict) else {}
            s = row.get("signals", {}) if isinstance(row.get("signals"), dict) else {}
            tech = safe_float(q.get("technical_accuracy"), 0.0)
            task = safe_float(q.get("task_success_potential"), 0.0)
            natural = safe_float(q.get("naturalness"), 0.0)
            emotional = safe_float(q.get("emotional_alignment"), 0.0)
            repair = safe_float(q.get("repair_value"), 0.0)
            confusion = 1.0 - safe_float(s.get("confusion_level"), 0.0)
            patience = safe_float(s.get("patience_level"), 0.0)
            safety = safe_float(q.get("safety_score"), 0.0)
            fine = safe_float(q.get("fine_tune_value"), 0.0)
            hybrid = safe_float(q.get("hybrid_depth"), 0.0)
            personal = safe_float(q.get("personal_relevance"), 0.0)
            global_r = safe_float(q.get("global_reusability"), 0.0)
            clarity = safe_float(q.get("clarity"), 0.0)

            acc["relationships"].append(clamp(0.5 * emotional + 0.5 * repair))
            acc["emotional_support"].append(clamp(0.7 * emotional + 0.3 * natural))
            acc["technical_guidance"].append(clamp(0.6 * tech + 0.4 * task))
            acc["coding_help"].append(clamp(0.7 * tech + 0.3 * clarity))
            acc["creative_ideation"].append(clamp(0.7 * hybrid + 0.3 * natural))
            acc["natural_language"].append(clamp(0.65 * natural + 0.35 * clarity))
            acc["repair_quality"].append(clamp(0.7 * repair + 0.3 * confusion))
            acc["confusion_reduction"].append(clamp(0.7 * confusion + 0.3 * clarity))
            acc["patience_management"].append(clamp(0.7 * patience + 0.3 * confusion))
            acc["task_success"].append(clamp(0.7 * task + 0.3 * tech))
            acc["human_like_tone"].append(clamp(0.5 * natural + 0.5 * emotional))
            acc["safety_ethics"].append(clamp(safety))
            acc["fine_tune_quality"].append(clamp(0.45 * fine + 0.25 * global_r + 0.20 * personal + 0.10 * safety))

        return {k: round(sum(v) / max(1, len(v)), 4) for k, v in acc.items()}

    def _window_summary(self, current_rows: list[dict[str, Any]], previous_rows: list[dict[str, Any]], ft: dict[str, Any]) -> dict[str, Any]:
        cur_scores = [safe_float((r.get("quality") or {}).get("total_score"), 0.0) for r in current_rows]
        prev_scores = [safe_float((r.get("quality") or {}).get("total_score"), 0.0) for r in previous_rows]
        cur_avg = sum(cur_scores) / max(1, len(cur_scores))
        prev_avg = sum(prev_scores) / max(1, len(prev_scores))
        growth = growth_percent(prev_avg, cur_avg)

        labels = [str((r.get("quality") or {}).get("quality_label", "candidate")) for r in current_rows]
        accepted = sum(1 for l in labels if l in {"accepted", "premium", "elite"})
        premium = sum(1 for l in labels if l in {"premium", "elite"})

        return {
            "overall_growth_percent": growth,
            "total_training_runs": len(current_rows),
            "accepted_learnings": accepted,
            "premium_learnings": premium,
            "elite_candidates": int(ft.get("elite_candidates", 0)),
            "fine_tune_candidates": int(ft.get("total_candidates", 0)),
        }

    def _build_topic_report(self, current: dict[str, float], previous: dict[str, float]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        topics: dict[str, Any] = {}
        weak: list[dict[str, Any]] = []
        strong: list[dict[str, Any]] = []
        for key, meta in TOPIC_META.items():
            prev = round(clamp(previous.get(key, 0.0)), 4)
            cur = round(clamp(current.get(key, 0.0)), 4)
            status = quality_label(cur)
            growth = growth_percent(prev, cur)
            rec = meta["recommendation"]
            topics[key] = {
                "label": meta["label"],
                "previous_score": prev,
                "current_score": cur,
                "growth_percent": growth,
                "status": status,
                "recommendation": rec,
            }
            if status in {"weak", "improving"}:
                weak.append(
                    {
                        "topic": key,
                        "label": meta["label"],
                        "score": cur,
                        "reason": "Low score or slow improvement.",
                        "recommendation": rec,
                        "suggested_training_runs": max(6, int(round((0.9 - cur) * 40))),
                    }
                )
            else:
                strong.append(
                    {
                        "topic": key,
                        "label": meta["label"],
                        "score": cur,
                        "confidence": "high" if status == "elite" else "medium-high",
                        "best_behavior_pattern": rec,
                    }
                )

        weak.sort(key=lambda x: x["score"])
        strong.sort(key=lambda x: x["score"], reverse=True)
        recommendations = [str(x["recommendation"]) for x in weak[:5]]
        return topics, weak[:6], strong[:6], recommendations

    def _enrich_with_global_quality(self, topic_scores: dict[str, float]) -> dict[str, float]:
        global_quality = load_json(self.global_dir / "global_quality_scores.json", {"topics": {}})
        g_topics = global_quality.get("topics", {}) if isinstance(global_quality, dict) else {}
        enriched = dict(topic_scores)
        for key in TOPIC_META:
            g_row = g_topics.get(key, {}) if isinstance(g_topics, dict) else {}
            g_avg = safe_float((g_row or {}).get("average_score"), None)
            if g_avg is None:
                continue
            local = safe_float(enriched.get(key, 0.0), 0.0)
            enriched[key] = round(clamp(local * 0.7 + g_avg * 0.3), 4)
        return enriched

    def build_user_dashboard(self, user_id: str, *, telemetry_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
        telemetry = telemetry_snapshot if isinstance(telemetry_snapshot, dict) else self.telemetry.build_snapshot()
        now_utc = datetime.now(timezone.utc)
        rows = self._performance_rows(user_id)
        lessons = load_json(self.users_dir / user_id / "personal_lessons.json", {"items": []})
        hybrid = load_json(self.users_dir / user_id / "hybrid_questions.json", {"items": []})
        global_lessons = load_json(self.global_dir / "global_lessons.json", {"items": []})
        rows_7 = filter_rows_by_days(rows, now_utc, 7, 0)
        rows_prev_7 = filter_rows_by_days(rows, now_utc, 7, 7)
        rows_30 = filter_rows_by_days(rows, now_utc, 30, 0)
        rows_prev_30 = filter_rows_by_days(rows, now_utc, 30, 30)

        current_topics = self._topic_scores_from_rows(rows_30 or rows)
        previous_topics = self._topic_scores_from_rows(rows_prev_30)
        current_topics = self._enrich_with_global_quality(current_topics)
        ft = self.fine_tune_stats()

        last_7 = self._window_summary(rows_7, rows_prev_7, ft)
        last_30 = self._window_summary(rows_30, rows_prev_30, ft)
        topics, weak, strong, recommendations = self._build_topic_report(current_topics, previous_topics)

        overall_growth = int(last_30.get("overall_growth_percent", 0))
        total_runs = len(rows)
        accepted_total = sum(1 for r in rows if str((r.get("quality") or {}).get("quality_label", "")) in {"accepted", "premium", "elite"})
        premium_total = sum(1 for r in rows if str((r.get("quality") or {}).get("quality_label", "")) in {"premium", "elite"})
        lesson_count = len(lessons.get("items", [])) if isinstance(lessons, dict) and isinstance(lessons.get("items"), list) else 0
        hybrid_count = len(hybrid.get("items", [])) if isinstance(hybrid, dict) and isinstance(hybrid.get("items"), list) else 0
        global_lesson_count = len(global_lessons.get("items", [])) if isinstance(global_lessons, dict) and isinstance(global_lessons.get("items"), list) else 0
        if lesson_count == 0:
            recommendations.append("Personal lessons are empty; run more guided conversations for better personalization.")
        if hybrid_count == 0:
            recommendations.append("Hybrid question log is empty; add more reflective follow-up prompts.")
        human_support = self._human_support_metrics(user_id)
        group1_metrics = self._group1_metrics_from_rows(rows)
        group2_metrics = self._group2_metrics_from_rows(rows)
        group3_metrics = self._group3_metrics_from_rows(rows)

        return {
            "scope": "user",
            "user_id": user_id,
            "generated_at": now_iso(),
            "last_7_days": last_7,
            "last_30_days": last_30,
            "overall_growth_percent": overall_growth,
            "total_training_runs": total_runs,
            "accepted_learnings": accepted_total,
            "premium_learnings": premium_total,
            "elite_candidates": int(ft.get("elite_candidates", 0)),
            "fine_tune_candidates": int(ft.get("total_candidates", 0)),
            "topics": topics,
            "weak_areas": weak,
            "strong_areas": strong,
            "recommendations": recommendations,
            "fine_tune": ft,
            "personal_learning_count": lesson_count,
            "hybrid_questions_count": hybrid_count,
            "global_lessons_seen": global_lesson_count,
            "human_support_metrics": human_support,
            "group1_layer_metrics": group1_metrics,
            "group2_layer_metrics": group2_metrics,
            "group3_layer_metrics": group3_metrics,
            "system_health": telemetry.get("system_health", {}),
            "learning_storage_health": telemetry.get("learning_storage_health", {}),
            "background_job_health": telemetry.get("background_job_health", {}),
            "context_health": telemetry.get("context_health", {}),
            "fine_tune_dataset_health": telemetry.get("fine_tune_dataset_health", {}),
            "group4_soak_metrics": telemetry.get("group4_soak_metrics", {}),
            "telemetry_metrics": telemetry.get("telemetry_metrics", {}),
            "storage_rotation": telemetry.get("storage_rotation", {}),
        }

    def build_user_performance_dashboard(self, user_id: str) -> dict[str, Any]:
        telemetry = self.telemetry.build_snapshot()
        perf = load_json(self.users_dir / user_id / "performance.json", {})
        lessons = load_json(self.users_dir / user_id / "personal_lessons.json", {"items": []})
        policy = self.policy.load_user_policy(user_id)
        lessons_items = lessons.get("items", []) if isinstance(lessons, dict) else []
        rows = perf.get("history", []) if isinstance(perf, dict) else []
        recent_lessons = lessons_items[-5:] if isinstance(lessons_items, list) else []
        context_metrics = perf.get("context_selection_metrics", {}) if isinstance(perf, dict) else {}
        if not isinstance(context_metrics, dict):
            context_metrics = {}
        response_mode_stats = perf.get("response_mode_stats", {}) if isinstance(perf, dict) else {}
        if not isinstance(response_mode_stats, dict):
            response_mode_stats = {}
        overall_modes = response_mode_stats.get("overall", {}) if isinstance(response_mode_stats.get("overall"), dict) else {}
        ranked_modes: list[dict[str, Any]] = []
        for mode_key, row in overall_modes.items():
            if not isinstance(row, dict):
                continue
            ranked_modes.append(
                {
                    "mode_key": str(mode_key),
                    "average_score": safe_float(row.get("average_score"), 0.0),
                    "success_rate": safe_float(row.get("success_rate"), 0.0),
                    "count": int(row.get("count", 0)),
                }
            )
        ranked_modes.sort(
            key=lambda x: (x["average_score"], x["success_rate"], x["count"]),
            reverse=True,
        )

        # Top weakness trends from recent rows
        weakness_counter: dict[str, int] = {}
        for row in rows[-100:] if isinstance(rows, list) else []:
            wk = str((row.get("quality") or {}).get("weakness", "")).strip()
            if not wk:
                continue
            weakness_counter[wk] = weakness_counter.get(wk, 0) + 1
        sorted_weak = sorted(weakness_counter.items(), key=lambda x: x[1], reverse=True)
        rec = [f"Improve: {w[0]}" for w in sorted_weak[:4]]
        human_support = self._human_support_metrics(user_id)
        group1_metrics = self._group1_metrics_from_rows(rows if isinstance(rows, list) else [])
        group2_metrics = self._group2_metrics_from_rows(rows if isinstance(rows, list) else [])
        group3_metrics = self._group3_metrics_from_rows(rows if isinstance(rows, list) else [])

        return {
            "user_id": user_id,
            "overall_performance": safe_float(perf.get("overall_performance"), 0.0),
            "clarity_score": safe_float(perf.get("clarity_score"), 0.0),
            "emotional_alignment": safe_float(perf.get("emotional_alignment"), 0.0),
            "technical_success": safe_float(perf.get("technical_success"), 0.0),
            "repair_success": safe_float(perf.get("repair_success"), 0.0),
            "confusion_reduction": safe_float(perf.get("confusion_reduction"), 0.0),
            "patience_management": safe_float(perf.get("patience_management"), 0.0),
            "naturalness_score": safe_float(perf.get("naturalness_score"), 0.0),
            "task_success": safe_float(perf.get("task_success"), 0.0),
            "personal_learning_count": len(lessons_items) if isinstance(lessons_items, list) else 0,
            "behavior_policy_count": len(policy.get("rules", [])) if isinstance(policy, dict) else 0,
            "recent_lessons": recent_lessons,
            "recommended_next_improvements": rec,
            "response_mode_success": {
                "total_modes": len(overall_modes),
                "best_modes": ranked_modes[:5],
                "last_updated": response_mode_stats.get("last_updated"),
            },
            "context_selection_metrics": {
                "context_selection_count": int(context_metrics.get("context_selection_count", 0)),
                "dropped_low_confidence_items": int(context_metrics.get("dropped_low_confidence_items", 0)),
                "average_context_length": safe_float(context_metrics.get("average_context_length", 0.0), 0.0),
                "max_context_length": int(context_metrics.get("max_context_length", 0)),
                "prompt_context_item_count": int(context_metrics.get("prompt_context_item_count", 0)),
                "average_context_item_count": safe_float(context_metrics.get("average_context_item_count", 0.0), 0.0),
                "topic_context_match_score": safe_float(context_metrics.get("topic_context_match_score", 0.0), 0.0),
                "false_positive_risk_estimate": safe_float(context_metrics.get("false_positive_risk_estimate", 0.0), 0.0),
                "updated_at": context_metrics.get("updated_at"),
            },
            "human_support_metrics": human_support,
            "group1_layer_metrics": group1_metrics,
            "group2_layer_metrics": group2_metrics,
            "group3_layer_metrics": group3_metrics,
            "system_health": telemetry.get("system_health", {}),
            "learning_storage_health": telemetry.get("learning_storage_health", {}),
            "background_job_health": telemetry.get("background_job_health", {}),
            "context_health": telemetry.get("context_health", {}),
            "fine_tune_dataset_health": telemetry.get("fine_tune_dataset_health", {}),
            "group4_soak_metrics": telemetry.get("group4_soak_metrics", {}),
            "telemetry_metrics": telemetry.get("telemetry_metrics", {}),
            "storage_rotation": telemetry.get("storage_rotation", {}),
        }

    def build_global_dashboard(self) -> dict[str, Any]:
        telemetry = self.telemetry.build_snapshot()
        user_ids = sorted([p.name for p in self.users_dir.iterdir() if p.is_dir() and (p / "profile.json").exists()]) if self.users_dir.exists() else []
        dashboards = [self.build_user_dashboard(uid, telemetry_snapshot=telemetry) for uid in user_ids]
        ft = self.fine_tune_stats()
        global_lessons = load_json(self.global_dir / "global_lessons.json", {"items": []})

        total_7_runs = sum(int(d.get("last_7_days", {}).get("total_training_runs", 0)) for d in dashboards)
        total_30_runs = sum(int(d.get("last_30_days", {}).get("total_training_runs", 0)) for d in dashboards)
        total_runs = sum(int(d.get("total_training_runs", 0)) for d in dashboards)
        acc_7 = sum(int(d.get("last_7_days", {}).get("accepted_learnings", 0)) for d in dashboards)
        acc_30 = sum(int(d.get("last_30_days", {}).get("accepted_learnings", 0)) for d in dashboards)
        acc_total = sum(int(d.get("accepted_learnings", 0)) for d in dashboards)
        prem_7 = sum(int(d.get("last_7_days", {}).get("premium_learnings", 0)) for d in dashboards)
        prem_30 = sum(int(d.get("last_30_days", {}).get("premium_learnings", 0)) for d in dashboards)
        prem_total = sum(int(d.get("premium_learnings", 0)) for d in dashboards)

        growth_values = [safe_float(d.get("overall_growth_percent"), 0.0) for d in dashboards]
        overall_growth = int(round(sum(growth_values) / max(1, len(growth_values)))) if growth_values else 0

        current_topic_pool: dict[str, list[float]] = {k: [] for k in TOPIC_META}
        previous_topic_pool: dict[str, list[float]] = {k: [] for k in TOPIC_META}
        for d in dashboards:
            topics = d.get("topics", {}) if isinstance(d.get("topics"), dict) else {}
            for key in TOPIC_META:
                t = topics.get(key, {})
                current_topic_pool[key].append(safe_float((t or {}).get("current_score"), 0.0))
                previous_topic_pool[key].append(safe_float((t or {}).get("previous_score"), 0.0))

        current_topics = {k: round(sum(v) / max(1, len(v)), 4) for k, v in current_topic_pool.items()}
        previous_topics = {k: round(sum(v) / max(1, len(v)), 4) for k, v in previous_topic_pool.items()}
        current_topics = self._enrich_with_global_quality(current_topics)

        topics, weak, strong, recommendations = self._build_topic_report(current_topics, previous_topics)
        support_rows = [self._human_support_metrics(uid) for uid in user_ids]
        support_count = max(1, len(support_rows))
        global_support = {
            "regulation_support_score": round(
                sum(safe_float(r.get("regulation_support_score"), 0.0) for r in support_rows) / support_count,
                4,
            )
            if support_rows
            else 0.0,
            "safety_sensitive_interactions": sum(int(r.get("safety_sensitive_interactions", 0)) for r in support_rows),
            "trust_repair_support": sum(int(r.get("trust_repair_support", 0)) for r in support_rows),
            "high_emotional_load_count": sum(int(r.get("high_emotional_load_count", 0)) for r in support_rows),
            "grounding_needed_count": sum(int(r.get("grounding_needed_count", 0)) for r in support_rows),
            "boundary_support_count": sum(int(r.get("boundary_support_count", 0)) for r in support_rows),
            "relationship_distress_support": sum(int(r.get("relationship_distress_support", 0)) for r in support_rows),
            "impulse_slowdown_support": sum(int(r.get("impulse_slowdown_support", 0)) for r in support_rows),
            "threat_perception_support": sum(int(r.get("threat_perception_support", 0)) for r in support_rows),
            "trauma_sensitive_support": sum(int(r.get("trauma_sensitive_support", 0)) for r in support_rows),
        }
        group1_rows = [self._group1_metrics_from_rows(self._performance_rows(uid)) for uid in user_ids]
        group1_count = max(1, len(group1_rows))
        tone_counts: dict[str, int] = {}
        for r in group1_rows:
            tone = str(r.get("response_tone_adjustment", "")).strip()
            if not tone:
                continue
            tone_counts[tone] = tone_counts.get(tone, 0) + 1
        global_top_tone = (
            sorted(tone_counts.items(), key=lambda kv: kv[1], reverse=True)[0][0]
            if tone_counts
            else "warm_balanced"
        )

        global_group1 = {
            "emotion_signal_score": round(sum(safe_float(r.get("emotion_signal_score"), 0.0) for r in group1_rows) / group1_count, 4)
            if group1_rows
            else 0.0,
            "hidden_need_signal": round(sum(safe_float(r.get("hidden_need_signal"), 0.0) for r in group1_rows) / group1_count, 4)
            if group1_rows
            else 0.0,
            "tone_adaptation_score": round(sum(safe_float(r.get("tone_adaptation_score"), 0.0) for r in group1_rows) / group1_count, 4)
            if group1_rows
            else 0.0,
            "human_layer_alignment": round(sum(safe_float(r.get("human_layer_alignment"), 0.0) for r in group1_rows) / group1_count, 4)
            if group1_rows
            else 0.0,
            "emotional_load_level": round(sum(safe_float(r.get("emotional_load_level"), 0.0) for r in group1_rows) / group1_count, 4)
            if group1_rows
            else 0.0,
            "clarity_need_signal": round(sum(safe_float(r.get("clarity_need_signal"), 0.0) for r in group1_rows) / group1_count, 4)
            if group1_rows
            else 0.0,
            "repair_need_signal": round(sum(safe_float(r.get("repair_need_signal"), 0.0) for r in group1_rows) / group1_count, 4)
            if group1_rows
            else 0.0,
            "safety_sensitive_signal": round(sum(safe_float(r.get("safety_sensitive_signal"), 0.0) for r in group1_rows) / group1_count, 4)
            if group1_rows
            else 0.0,
            "response_tone_adjustment": global_top_tone,
        }
        group2_rows = [self._group2_metrics_from_rows(self._performance_rows(uid)) for uid in user_ids]
        group2_count = max(1, len(group2_rows))
        group2_tone_counts: dict[str, int] = {}
        for r in group2_rows:
            tone = str(r.get("response_tone_adjustment", "")).strip()
            if not tone:
                continue
            group2_tone_counts[tone] = group2_tone_counts.get(tone, 0) + 1
        global_group2_tone = (
            sorted(group2_tone_counts.items(), key=lambda kv: kv[1], reverse=True)[0][0]
            if group2_tone_counts
            else "coherent_calm"
        )
        global_group2 = {
            "narrative_continuity_score": round(sum(safe_float(r.get("narrative_continuity_score"), 0.0) for r in group2_rows) / group2_count, 4)
            if group2_rows
            else 0.0,
            "context_coherence_score": round(sum(safe_float(r.get("context_coherence_score"), 0.0) for r in group2_rows) / group2_count, 4)
            if group2_rows
            else 0.0,
            "contradiction_signal_score": round(sum(safe_float(r.get("contradiction_signal_score"), 0.0) for r in group2_rows) / group2_count, 4)
            if group2_rows
            else 0.0,
            "clarification_need_signal": round(sum(safe_float(r.get("clarification_need_signal"), 0.0) for r in group2_rows) / group2_count, 4)
            if group2_rows
            else 0.0,
            "relationship_distress_signal": round(sum(safe_float(r.get("relationship_distress_signal"), 0.0) for r in group2_rows) / group2_count, 4)
            if group2_rows
            else 0.0,
            "boundary_support_signal": round(sum(safe_float(r.get("boundary_support_signal"), 0.0) for r in group2_rows) / group2_count, 4)
            if group2_rows
            else 0.0,
            "safety_ethics_alignment": round(sum(safe_float(r.get("safety_ethics_alignment"), 0.0) for r in group2_rows) / group2_count, 4)
            if group2_rows
            else 0.0,
            "privacy_protection_score": round(sum(safe_float(r.get("privacy_protection_score"), 0.0) for r in group2_rows) / group2_count, 4)
            if group2_rows
            else 0.0,
            "response_risk_reduction": round(sum(safe_float(r.get("response_risk_reduction"), 0.0) for r in group2_rows) / group2_count, 4)
            if group2_rows
            else 0.0,
            "response_tone_adjustment": global_group2_tone,
        }
        group3_rows = [self._group3_metrics_from_rows(self._performance_rows(uid)) for uid in user_ids]
        global_group3: dict[str, Any] = {
            "group3_signal_counts": 0,
            "symbolic_signal_count": 0,
            "dream_context_count": 0,
            "existential_signal_count": 0,
            "memory_candidate_count": 0,
            "memory_gate_allowed_count": 0,
            "memory_gate_blocked_count": 0,
            "duplicate_anchor_block_count": 0,
            "sensitive_block_count": 0,
            "pii_block_count": 0,
            "low_confidence_block_count": 0,
            "memory_gate_block_reasons": {},
            "samples": 0,
        }
        reason_counts: dict[str, int] = {}
        for r in group3_rows:
            global_group3["group3_signal_counts"] += int(r.get("group3_signal_counts", 0))
            global_group3["symbolic_signal_count"] += int(r.get("symbolic_signal_count", 0))
            global_group3["dream_context_count"] += int(r.get("dream_context_count", 0))
            global_group3["existential_signal_count"] += int(r.get("existential_signal_count", 0))
            global_group3["memory_candidate_count"] += int(r.get("memory_candidate_count", 0))
            global_group3["memory_gate_allowed_count"] += int(r.get("memory_gate_allowed_count", 0))
            global_group3["memory_gate_blocked_count"] += int(r.get("memory_gate_blocked_count", 0))
            global_group3["duplicate_anchor_block_count"] += int(r.get("duplicate_anchor_block_count", 0))
            global_group3["sensitive_block_count"] += int(r.get("sensitive_block_count", 0))
            global_group3["pii_block_count"] += int(r.get("pii_block_count", 0))
            global_group3["low_confidence_block_count"] += int(r.get("low_confidence_block_count", 0))
            global_group3["samples"] += int(r.get("samples", 0))
            rr = r.get("memory_gate_block_reasons", {})
            if isinstance(rr, dict):
                for k, v in rr.items():
                    kk = str(k).strip()
                    if not kk:
                        continue
                    reason_counts[kk] = reason_counts.get(kk, 0) + int(v or 0)
        global_group3["memory_gate_block_reasons"] = dict(sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:12])

        # learning_dashboard.json snapshot saygisi (okuma)
        dashboard_state = load_json(self.global_dir / "learning_dashboard.json", {"snapshots": []})
        snapshots = dashboard_state.get("snapshots", []) if isinstance(dashboard_state, dict) else []
        global_lesson_count = len(global_lessons.get("items", [])) if isinstance(global_lessons, dict) and isinstance(global_lessons.get("items"), list) else 0
        if global_lesson_count == 0:
            recommendations.append("Global lessons are empty; increase anonymized learning writes.")

        return {
            "scope": "global",
            "generated_at": now_iso(),
            "user_count": len(user_ids),
            "last_7_days": {
                "overall_growth_percent": overall_growth,
                "total_training_runs": total_7_runs,
                "accepted_learnings": acc_7,
                "premium_learnings": prem_7,
                "elite_candidates": int(ft.get("elite_candidates", 0)),
                "fine_tune_candidates": int(ft.get("total_candidates", 0)),
            },
            "last_30_days": {
                "overall_growth_percent": overall_growth,
                "total_training_runs": total_30_runs,
                "accepted_learnings": acc_30,
                "premium_learnings": prem_30,
                "elite_candidates": int(ft.get("elite_candidates", 0)),
                "fine_tune_candidates": int(ft.get("total_candidates", 0)),
            },
            "overall_growth_percent": overall_growth,
            "total_training_runs": total_runs,
            "accepted_learnings": acc_total,
            "premium_learnings": prem_total,
            "elite_candidates": int(ft.get("elite_candidates", 0)),
            "fine_tune_candidates": int(ft.get("total_candidates", 0)),
            "topics": topics,
            "weak_areas": weak,
            "strong_areas": strong,
            "recommendations": recommendations,
            "fine_tune": ft,
            "learning_dashboard_snapshots": len(snapshots) if isinstance(snapshots, list) else 0,
            "global_lessons_count": global_lesson_count,
            "human_support_metrics": global_support,
            "group1_layer_metrics": global_group1,
            "group2_layer_metrics": global_group2,
            "group3_layer_metrics": global_group3,
            "system_health": telemetry.get("system_health", {}),
            "learning_storage_health": telemetry.get("learning_storage_health", {}),
            "background_job_health": telemetry.get("background_job_health", {}),
            "context_health": telemetry.get("context_health", {}),
            "fine_tune_dataset_health": telemetry.get("fine_tune_dataset_health", {}),
            "group4_soak_metrics": telemetry.get("group4_soak_metrics", {}),
            "telemetry_metrics": telemetry.get("telemetry_metrics", {}),
            "storage_rotation": telemetry.get("storage_rotation", {}),
        }

    def render_html(self) -> str:
        data = self.build_global_dashboard()
        l7 = data.get("last_7_days", {})
        l30 = data.get("last_30_days", {})
        topics = data.get("topics", {})
        weak = data.get("weak_areas", [])
        strong = data.get("strong_areas", [])
        fine = data.get("fine_tune", {})

        rows = []
        for key, row in topics.items():
            status = str(row.get("status", "improving"))
            color = {"weak": "#d97070", "improving": "#d5b66a", "strong": "#8bc28b", "elite": "#6ec1e4"}.get(status, "#d5b66a")
            rows.append(
                "<tr>"
                f"<td>{html.escape(str(row.get('label', key)))}</td>"
                f"<td>{safe_float(row.get('previous_score', 0.0)):.2f}</td>"
                f"<td>{safe_float(row.get('current_score', 0.0)):.2f}</td>"
                f"<td>{int(row.get('growth_percent', 0))}%</td>"
                f"<td style='color:{color};font-weight:600'>{html.escape(status)}</td>"
                f"<td>{html.escape(str(row.get('recommendation', '')))}</td>"
                "</tr>"
            )
        topic_rows = "".join(rows) or "<tr><td colspan='6'>No data</td></tr>"

        weak_html = "".join(
            f"<li><b>{html.escape(str(x.get('label', '')))}</b> ({safe_float(x.get('score'), 0.0):.2f}) - {html.escape(str(x.get('recommendation', '')))}</li>"
            for x in weak[:5]
        ) or "<li>No weak area.</li>"
        strong_html = "".join(
            f"<li><b>{html.escape(str(x.get('label', '')))}</b> ({safe_float(x.get('score'), 0.0):.2f})</li>"
            for x in strong[:5]
        ) or "<li>No strong area.</li>"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Luxviai Learning Dashboard</title>
  <style>
    body {{ background:#080808; color:#E8E5DF; font-family:Inter,Arial,sans-serif; margin:0; padding:20px; }}
    h1 {{ color:#ED9107; margin:0 0 8px; font-weight:500; }}
    .muted {{ color:#9AA3A6; font-size:.85rem; margin-bottom:12px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:10px; margin-bottom:12px; }}
    .card {{ border:1px solid rgba(237,145,7,.25); border-radius:10px; padding:10px; background:#0B0B0B; }}
    .label {{ color:#B8B1A3; font-size:.78rem; }}
    .value {{ font-size:1.2rem; margin-top:4px; }}
    table {{ width:100%; border-collapse:collapse; background:#0B0B0B; border:1px solid rgba(237,145,7,.22); }}
    th, td {{ border-bottom:1px solid rgba(255,255,255,.08); padding:8px; font-size:.82rem; vertical-align:top; }}
    th {{ color:#F5D68A; text-align:left; font-weight:500; }}
    .cols {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:10px; }}
    ul {{ margin:8px 0 0 16px; padding:0; }}
    li {{ margin:4px 0; }}
  </style>
</head>
<body>
  <h1>Luxviai Learning Dashboard</h1>
  <div class="muted">Generated: {html.escape(str(data.get("generated_at", now_iso())))}</div>

  <div class="grid">
    <div class="card"><div class="label">7d growth</div><div class="value">{int(l7.get("overall_growth_percent", 0))}%</div></div>
    <div class="card"><div class="label">30d growth</div><div class="value">{int(l30.get("overall_growth_percent", 0))}%</div></div>
    <div class="card"><div class="label">Total runs</div><div class="value">{int(data.get("total_training_runs", 0))}</div></div>
    <div class="card"><div class="label">Accepted</div><div class="value">{int(data.get("accepted_learnings", 0))}</div></div>
    <div class="card"><div class="label">Premium</div><div class="value">{int(data.get("premium_learnings", 0))}</div></div>
    <div class="card"><div class="label">Elite candidates</div><div class="value">{int(data.get("elite_candidates", 0))}</div></div>
  </div>

  <table>
    <thead><tr><th>Topic</th><th>Prev</th><th>Current</th><th>Growth</th><th>Status</th><th>Recommendation</th></tr></thead>
    <tbody>{topic_rows}</tbody>
  </table>

  <div class="cols">
    <div class="card"><div class="label">Weak areas</div><ul>{weak_html}</ul></div>
    <div class="card"><div class="label">Strong areas</div><ul>{strong_html}</ul></div>
  </div>

  <div class="grid" style="margin-top:10px;">
    <div class="card"><div class="label">Fine-tune total</div><div class="value">{int(fine.get("total_candidates", 0))}</div></div>
    <div class="card"><div class="label">Elite</div><div class="value">{int(fine.get("elite_candidates", 0))}</div></div>
    <div class="card"><div class="label">Pending</div><div class="value">{int(fine.get("pending_candidates", 0))}</div></div>
    <div class="card"><div class="label">Rejected</div><div class="value">{int(fine.get("rejected_candidates", 0))}</div></div>
  </div>
</body>
</html>"""
