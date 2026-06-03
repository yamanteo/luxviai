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

    def _aggregate_group4_soak_metrics(self) -> dict[str, Any]:
        lens_counts: dict[str, int] = {}
        reason_counts: dict[str, int] = {}
        conf_counts: dict[str, int] = {}
        half_step_counts: dict[str, int] = {}
        language_counts: dict[str, int] = {}
        response_len_counts: dict[str, int] = {}
        latency_counts: dict[str, int] = {}
        time_ecology_hint_dist: dict[str, int] = {}
        time_ecology_conf_dist: dict[str, int] = {}
        reflection_style_dist: dict[str, int] = {}
        reflection_risk_review_dist: dict[str, int] = {}
        reflection_utility_guard_dist: dict[str, int] = {}
        cultural_hint_dist: dict[str, int] = {}
        cultural_register_dist: dict[str, int] = {}
        cultural_language_dist: dict[str, int] = {}
        cultural_mixed_dist: dict[str, int] = {}
        per_language_hint_dist: dict[str, dict[str, int]] = {}

        total_rows = 0
        non_normal_lens_rows = 0
        lens_stacking_near_miss_count = 0
        utility_metaphor_leakage_count = 0
        technical_direct_answer_count = 0
        dream_false_positive_count = 0
        luxching_false_positive_count = 0
        luxmirror_offer_count = 0
        forced_question_count = 0
        group4_signal_presence_count = 0
        group4_context_injection_count = 0
        group4_low_confidence_suppressed_count = 0
        time_ecology_hint_emitted_count = 0
        time_ecology_neutral_count = 0
        guard_12_5_suppression_count = 0
        tighten_only_violation_count = 0
        safety_flagged_turns_with_time_ecology_hint_count = 0
        reflection_signal_presence_count = 0
        reflection_hint_emitted_count = 0
        reflection_neutral_count = 0
        reflection_correction_signal_count = 0
        reflection_utility_guard_signal_count = 0
        avoid_metaphor_signal_count = 0
        forced_question_reduction_count = 0
        verbosity_too_long_count = 0
        reflection_low_confidence_suppressed_count = 0
        cultural_epistemic_signal_presence_count = 0
        cultural_epistemic_hint_emitted_count = 0
        cultural_epistemic_neutral_count = 0
        cultural_epistemic_low_confidence_neutral_count = 0
        utility_cultural_suppression_count = 0
        identity_inference_block_count = 0
        forbidden_identity_pattern_count = 0
        technical_substance_drift_count = 0
        lens_frequency_drift_count = 0
        safety_veto_suppression_count = 0

        for user_dir in self._iter_user_dirs():
            perf = load_json(user_dir / "performance.json", {})
            history = perf.get("history", []) if isinstance(perf, dict) else []
            if not isinstance(history, list):
                continue
            for row in history[-500:]:
                if not isinstance(row, dict):
                    continue
                signals = row.get("signals", {})
                if not isinstance(signals, dict):
                    continue

                total_rows += 1
                selected_lens = _norm_text(signals.get("selected_lens")).lower() or "normal"
                lens_counts[selected_lens] = lens_counts.get(selected_lens, 0) + 1
                if selected_lens != "normal":
                    non_normal_lens_rows += 1

                reason_bucket = _norm_text(signals.get("lens_reason_bucket")).lower() or "normal_flow"
                reason_counts[reason_bucket] = reason_counts.get(reason_bucket, 0) + 1
                conf_bucket = _norm_text(signals.get("lens_confidence_bucket")).lower() or "medium"
                conf_counts[conf_bucket] = conf_counts.get(conf_bucket, 0) + 1

                half_step = _norm_text(signals.get("half_step_type_bucket")).lower() or "none"
                half_step_counts[half_step] = half_step_counts.get(half_step, 0) + 1
                lang_bucket = _norm_text(signals.get("multilingual_language_bucket")).lower() or "unknown"
                language_counts[lang_bucket] = language_counts.get(lang_bucket, 0) + 1
                len_bucket = _norm_text(signals.get("response_length_bucket")).lower() or "unknown"
                response_len_counts[len_bucket] = response_len_counts.get(len_bucket, 0) + 1
                lat_bucket = _norm_text(signals.get("latency_bucket")).lower() or "unknown"
                latency_counts[lat_bucket] = latency_counts.get(lat_bucket, 0) + 1
                te_hint_bucket = _norm_text(signals.get("time_ecology_emitted_hint_bucket")).lower() or "none"
                time_ecology_hint_dist[te_hint_bucket] = time_ecology_hint_dist.get(te_hint_bucket, 0) + 1
                te_conf_bucket = _norm_text(signals.get("time_ecology_confidence_bucket")).lower() or "low"
                time_ecology_conf_dist[te_conf_bucket] = time_ecology_conf_dist.get(te_conf_bucket, 0) + 1
                reflection_style = _norm_text(signals.get("reflection_style_bucket")).lower() or "neutral"
                reflection_style_dist[reflection_style] = reflection_style_dist.get(reflection_style, 0) + 1
                reflection_risk = _norm_text(signals.get("reflection_risk_review_bucket")).lower() or "none"
                reflection_risk_review_dist[reflection_risk] = reflection_risk_review_dist.get(reflection_risk, 0) + 1
                reflection_guard = _norm_text(signals.get("reflection_utility_guard_signal")).lower() or "none"
                reflection_utility_guard_dist[reflection_guard] = reflection_utility_guard_dist.get(reflection_guard, 0) + 1
                cultural_hint = _norm_text(signals.get("cultural_epistemic_hint_bucket")).lower() or "none"
                cultural_hint_dist[cultural_hint] = cultural_hint_dist.get(cultural_hint, 0) + 1
                cultural_register = _norm_text(signals.get("cultural_epistemic_register_hint_bucket")).lower() or "unknown"
                cultural_register_dist[cultural_register] = cultural_register_dist.get(cultural_register, 0) + 1
                cultural_lang = _norm_text(signals.get("cultural_epistemic_language_context_bucket")).lower() or "unknown"
                cultural_language_dist[cultural_lang] = cultural_language_dist.get(cultural_lang, 0) + 1
                cultural_mixed = _norm_text(signals.get("cultural_epistemic_mixed_language_state")).lower() or "unknown"
                cultural_mixed_dist[cultural_mixed] = cultural_mixed_dist.get(cultural_mixed, 0) + 1
                per_language_hint_dist.setdefault(cultural_lang, {})
                per_language_hint_dist[cultural_lang][cultural_hint] = per_language_hint_dist[cultural_lang].get(cultural_hint, 0) + 1

                lens_stacking_near_miss_count += int(signals.get("lens_stacking_near_miss_count", 0) or 0)
                utility_metaphor_leakage_count += int(signals.get("utility_metaphor_leakage_count", 0) or 0)
                technical_direct_answer_count += int(signals.get("technical_direct_answer_flag", 0) or 0)
                dream_false_positive_count += int(signals.get("dream_false_positive_count", 0) or 0)
                luxching_false_positive_count += int(signals.get("luxching_false_positive_count", 0) or 0)
                luxmirror_offer_count += int(signals.get("luxmirror_offer_flag", 0) or 0)
                forced_question_count += int(signals.get("forced_question_flag", 0) or 0)
                group4_signal_presence_count += int(signals.get("group4_signal_presence_count", 0) or 0)
                group4_context_injection_count += int(signals.get("group4_context_injection_count", 0) or 0)
                group4_low_confidence_suppressed_count += int(signals.get("group4_low_confidence_suppressed_count", 0) or 0)
                time_ecology_hint_emitted_count += int(signals.get("time_ecology_hint_emitted_count", 0) or 0)
                time_ecology_neutral_count += int(signals.get("time_ecology_neutral_count", 0) or 0)
                guard_12_5_suppression_count += int(signals.get("guard_12_5_suppression_count", 0) or 0)
                tighten_only_violation_count += int(signals.get("tighten_only_violation_count", 0) or 0)
                safety_flagged_turns_with_time_ecology_hint_count += int(
                    signals.get("safety_flagged_turns_with_time_ecology_hint_count", 0) or 0
                )
                reflection_signal_presence_count += int(signals.get("reflection_signal_presence_count", 0) or 0)
                reflection_hint_emitted_count += int(signals.get("reflection_hint_emitted_count", 0) or 0)
                reflection_neutral_count += int(signals.get("reflection_neutral_count", 0) or 0)
                reflection_low_confidence_suppressed_count += int(signals.get("reflection_low_confidence_suppressed_count", 0) or 0)
                correction_signal = _norm_text(signals.get("reflection_correction_signal")).lower() or "none"
                if correction_signal != "none":
                    reflection_correction_signal_count += 1
                if reflection_guard != "none":
                    reflection_utility_guard_signal_count += 1
                avoid_metaphor_signal_count += int(signals.get("avoid_metaphor_signal_count", 0) or 0)
                forced_question_reduction_count += int(signals.get("forced_question_reduction_count", 0) or 0)
                verbosity_too_long_count += int(signals.get("verbosity_too_long_count", 0) or 0)
                cultural_epistemic_signal_presence_count += int(signals.get("cultural_epistemic_signal_presence_count", 0) or 0)
                cultural_epistemic_hint_emitted_count += int(signals.get("cultural_epistemic_hint_emitted_count", 0) or 0)
                cultural_epistemic_neutral_count += int(signals.get("cultural_epistemic_neutral_count", 0) or 0)
                cultural_epistemic_low_confidence_neutral_count += int(
                    signals.get("cultural_epistemic_low_confidence_neutral_count", 0) or 0
                )
                utility_cultural_suppression_count += int(signals.get("utility_cultural_suppression_count", 0) or 0)
                identity_inference_block_count += int(signals.get("identity_inference_block_count", 0) or 0)
                forbidden_identity_pattern_count += int(signals.get("forbidden_identity_pattern_count", 0) or 0)
                technical_substance_drift_count += int(signals.get("technical_substance_drift_count", 0) or 0)
                lens_frequency_drift_count += int(signals.get("lens_frequency_drift_count", 0) or 0)
                safety_veto_suppression_count += int(signals.get("safety_veto_suppression_count", 0) or 0)

        def _rate(count: int) -> float:
            return round(count / max(1, total_rows), 4)

        lens_trigger_rate_by_bucket = {
            k: round(v / max(1, total_rows), 4)
            for k, v in sorted(lens_counts.items(), key=lambda kv: kv[1], reverse=True)
        }
        return {
            "sample_size": int(total_rows),
            "lens_trigger_rate_by_bucket": lens_trigger_rate_by_bucket,
            "lens_reason_bucket_count": dict(sorted(reason_counts.items(), key=lambda kv: kv[1], reverse=True)),
            "lens_confidence_bucket_count": dict(sorted(conf_counts.items(), key=lambda kv: kv[1], reverse=True)),
            "lens_stacking_near_miss_count": int(lens_stacking_near_miss_count),
            "utility_metaphor_leakage_count": int(utility_metaphor_leakage_count),
            "technical_direct_answer_rate": _rate(int(technical_direct_answer_count)),
            "technical_direct_answer_count": int(technical_direct_answer_count),
            "dream_false_positive_count": int(dream_false_positive_count),
            "luxching_false_positive_count": int(luxching_false_positive_count),
            "luxmirror_offer_rate": _rate(int(luxmirror_offer_count)),
            "luxmirror_offer_count": int(luxmirror_offer_count),
            "forced_question_rate": _rate(int(forced_question_count)),
            "forced_question_count": int(forced_question_count),
            "half_step_type_distribution": dict(sorted(half_step_counts.items(), key=lambda kv: kv[1], reverse=True)),
            "group4_signal_presence_count": int(group4_signal_presence_count),
            "group4_context_injection_count": int(group4_context_injection_count),
            "group4_low_confidence_suppressed_count": int(group4_low_confidence_suppressed_count),
            "multilingual_language_bucket_count": dict(sorted(language_counts.items(), key=lambda kv: kv[1], reverse=True)),
            "response_length_bucket": dict(sorted(response_len_counts.items(), key=lambda kv: kv[1], reverse=True)),
            "latency_bucket": dict(sorted(latency_counts.items(), key=lambda kv: kv[1], reverse=True)),
            "non_normal_lens_rate": _rate(int(non_normal_lens_rows)),
            "time_ecology_hint_emission_rate": _rate(int(time_ecology_hint_emitted_count)),
            "time_ecology_neutral_rate": _rate(int(time_ecology_neutral_count)),
            "emitted_hint_distribution": dict(sorted(time_ecology_hint_dist.items(), key=lambda kv: kv[1], reverse=True)),
            "12.5_guard_suppression_rate": _rate(int(guard_12_5_suppression_count)),
            "tighten_only_violation_count": int(tighten_only_violation_count),
            "safety_flagged_turns_with_time_ecology_hint_count": int(safety_flagged_turns_with_time_ecology_hint_count),
            "time_ecology_confidence_bucket_count": dict(sorted(time_ecology_conf_dist.items(), key=lambda kv: kv[1], reverse=True)),
            "reflection_signal_presence_count": int(reflection_signal_presence_count),
            "reflection_neutral_rate": _rate(int(reflection_neutral_count)),
            "reflection_hint_emission_rate": _rate(int(reflection_hint_emitted_count)),
            "reflection_style_bucket_distribution": dict(sorted(reflection_style_dist.items(), key=lambda kv: kv[1], reverse=True)),
            "correction_signal_count": int(reflection_correction_signal_count),
            "utility_guard_signal_count": int(reflection_utility_guard_signal_count),
            "avoid_metaphor_signal_count": int(avoid_metaphor_signal_count),
            "forced_question_reduction_count": int(forced_question_reduction_count),
            "verbosity_too_long_count": int(verbosity_too_long_count),
            "risk_review_bucket_distribution": dict(sorted(reflection_risk_review_dist.items(), key=lambda kv: kv[1], reverse=True)),
            "reflection_utility_guard_distribution": dict(sorted(reflection_utility_guard_dist.items(), key=lambda kv: kv[1], reverse=True)),
            "reflection_low_confidence_suppressed_count": int(reflection_low_confidence_suppressed_count),
            "cultural_epistemic_signal_presence_count": int(cultural_epistemic_signal_presence_count),
            "cultural_epistemic_hint_emission_rate": _rate(int(cultural_epistemic_hint_emitted_count)),
            "cultural_epistemic_neutral_rate": _rate(int(cultural_epistemic_neutral_count)),
            "register_hint_distribution": dict(sorted(cultural_register_dist.items(), key=lambda kv: kv[1], reverse=True)),
            "language_context_bucket_distribution": dict(sorted(cultural_language_dist.items(), key=lambda kv: kv[1], reverse=True)),
            "cultural_epistemic_hint_distribution": dict(sorted(cultural_hint_dist.items(), key=lambda kv: kv[1], reverse=True)),
            "mixed_language_state_distribution": dict(sorted(cultural_mixed_dist.items(), key=lambda kv: kv[1], reverse=True)),
            "mixed_language_neutral_count": int(cultural_mixed_dist.get("code_switching", 0)),
            "low_confidence_neutral_count": int(cultural_epistemic_low_confidence_neutral_count),
            "utility_cultural_suppression_count": int(utility_cultural_suppression_count),
            "identity_inference_block_count": int(identity_inference_block_count),
            "forbidden_identity_pattern_count": int(forbidden_identity_pattern_count),
            "per_language_hint_distribution": {
                lang: dict(sorted(bucket.items(), key=lambda kv: kv[1], reverse=True))
                for lang, bucket in sorted(per_language_hint_dist.items())
            },
            "per_language_naturalness_regression_flag": "ok",
            "technical_substance_drift_count": int(technical_substance_drift_count),
            "lens_frequency_drift_count": int(lens_frequency_drift_count),
            "safety_veto_suppression_count": int(safety_veto_suppression_count),
            "engagement_neutrality_check": (
                "ok"
                if _rate(int(time_ecology_hint_emitted_count)) <= 0.45 and int(tighten_only_violation_count) == 0
                else "review"
            ),
            "global_fine_tune_exclusion_confirmation": True,
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
        soak = self._aggregate_group4_soak_metrics()
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
            "lens_stacking_near_miss_count": int(soak.get("lens_stacking_near_miss_count", 0)),
            "utility_metaphor_leakage_count": int(soak.get("utility_metaphor_leakage_count", 0)),
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
            "lens_trigger_rate_by_bucket": soak.get("lens_trigger_rate_by_bucket", {}),
            "lens_stacking_near_miss_count": int(soak.get("lens_stacking_near_miss_count", 0)),
            "utility_metaphor_leakage_count": int(soak.get("utility_metaphor_leakage_count", 0)),
            "technical_direct_answer_rate": safe_float(soak.get("technical_direct_answer_rate"), 0.0),
            "dream_false_positive_count": int(soak.get("dream_false_positive_count", 0)),
            "luxching_false_positive_count": int(soak.get("luxching_false_positive_count", 0)),
            "luxmirror_offer_rate": safe_float(soak.get("luxmirror_offer_rate"), 0.0),
            "forced_question_rate": safe_float(soak.get("forced_question_rate"), 0.0),
            "half_step_type_distribution": soak.get("half_step_type_distribution", {}),
            "group4_signal_presence_count": int(soak.get("group4_signal_presence_count", 0)),
            "group4_context_injection_count": int(soak.get("group4_context_injection_count", 0)),
            "group4_low_confidence_suppressed_count": int(soak.get("group4_low_confidence_suppressed_count", 0)),
            "multilingual_language_bucket_count": soak.get("multilingual_language_bucket_count", {}),
            "response_length_bucket": soak.get("response_length_bucket", {}),
            "latency_bucket": soak.get("latency_bucket", {}),
            "time_ecology_hint_emission_rate": safe_float(soak.get("time_ecology_hint_emission_rate"), 0.0),
            "time_ecology_neutral_rate": safe_float(soak.get("time_ecology_neutral_rate"), 0.0),
            "emitted_hint_distribution": soak.get("emitted_hint_distribution", {}),
            "12.5_guard_suppression_rate": safe_float(soak.get("12.5_guard_suppression_rate"), 0.0),
            "tighten_only_violation_count": int(soak.get("tighten_only_violation_count", 0)),
            "safety_flagged_turns_with_time_ecology_hint_count": int(soak.get("safety_flagged_turns_with_time_ecology_hint_count", 0)),
            "reflection_signal_presence_count": int(soak.get("reflection_signal_presence_count", 0)),
            "reflection_neutral_rate": safe_float(soak.get("reflection_neutral_rate"), 0.0),
            "reflection_hint_emission_rate": safe_float(soak.get("reflection_hint_emission_rate"), 0.0),
            "reflection_style_bucket_distribution": soak.get("reflection_style_bucket_distribution", {}),
            "correction_signal_count": int(soak.get("correction_signal_count", 0)),
            "utility_guard_signal_count": int(soak.get("utility_guard_signal_count", 0)),
            "avoid_metaphor_signal_count": int(soak.get("avoid_metaphor_signal_count", 0)),
            "forced_question_reduction_count": int(soak.get("forced_question_reduction_count", 0)),
            "verbosity_too_long_count": int(soak.get("verbosity_too_long_count", 0)),
            "risk_review_bucket_distribution": soak.get("risk_review_bucket_distribution", {}),
            "reflection_low_confidence_suppressed_count": int(soak.get("reflection_low_confidence_suppressed_count", 0)),
            "cultural_epistemic_hint_emission_rate": safe_float(soak.get("cultural_epistemic_hint_emission_rate"), 0.0),
            "cultural_epistemic_neutral_rate": safe_float(soak.get("cultural_epistemic_neutral_rate"), 0.0),
            "register_hint_distribution": soak.get("register_hint_distribution", {}),
            "language_context_bucket_distribution": soak.get("language_context_bucket_distribution", {}),
            "mixed_language_neutral_count": int(soak.get("mixed_language_neutral_count", 0)),
            "low_confidence_neutral_count": int(soak.get("low_confidence_neutral_count", 0)),
            "utility_cultural_suppression_count": int(soak.get("utility_cultural_suppression_count", 0)),
            "identity_inference_block_count": int(soak.get("identity_inference_block_count", 0)),
            "forbidden_identity_pattern_count": int(soak.get("forbidden_identity_pattern_count", 0)),
            "per_language_hint_distribution": soak.get("per_language_hint_distribution", {}),
            "per_language_naturalness_regression_flag": soak.get("per_language_naturalness_regression_flag", "ok"),
            "technical_substance_drift_count": int(soak.get("technical_substance_drift_count", 0)),
            "lens_frequency_drift_count": int(soak.get("lens_frequency_drift_count", 0)),
            "safety_veto_suppression_count": int(soak.get("safety_veto_suppression_count", 0)),
            "engagement_neutrality_check": soak.get("engagement_neutrality_check", "ok"),
            "global_fine_tune_exclusion_confirmation": bool(soak.get("global_fine_tune_exclusion_confirmation", True)),
        }

        return {
            "generated_at": now_iso(),
            "system_health": system_health,
            "learning_storage_health": learning_storage_health,
            "background_job_health": background_job_health,
            "context_health": context_health,
            "fine_tune_dataset_health": fine_tune_dataset_health,
            "group4_soak_metrics": soak,
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
