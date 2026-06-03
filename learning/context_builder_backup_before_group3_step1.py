from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .behavior_policy import BehaviorPolicyManager, safe_float
from .io_utils import load_json
from .performance_tracker import PerformanceTracker


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


def _lc(value: Any) -> str:
    return _norm_text(value).lower()


def _read_jsonl_tail(path: Path, limit: int = 5) -> list[dict[str, Any]]:
    import json

    if not path.exists():
        return []
    tail: deque[str] = deque(maxlen=max(1, limit))
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    tail.append(line.strip())
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for ln in tail:
        try:
            row = json.loads(ln)
            if isinstance(row, dict):
                rows.append(row)
        except Exception:
            continue
    return rows


def _confidence_from_label(label: str) -> float:
    m = _lc(label)
    if m == "elite":
        return 0.95
    if m == "premium":
        return 0.9
    if m == "accepted":
        return 0.84
    if m == "candidate":
        return 0.72
    if m == "unsafe_rejected":
        return 0.3
    return 0.65


def _infer_topics_from_message(message: str) -> list[str]:
    msg = _lc(message)
    topics: list[str] = []
    if any(x in msg for x in ("hata", "error", "deploy", "render", "terminal", "api", "build")):
        topics.append("technical_guidance")
    if any(x in msg for x in ("kod", "python", "html", "css", "javascript")):
        topics.append("coding_help")
    if any(x in msg for x in ("karis", "anlamad", "nasil", "yani", "nerede")):
        topics.append("confusion_reduction")
    if any(x in msg for x in ("yavas", "hizli", "tek adim", "adim adim")):
        topics.append("patience_management")
    if any(x in msg for x in ("duygu", "hissed", "yalniz", "kaygi", "destek")):
        topics.append("emotional_support")
    if any(x in msg for x in ("guven", "repair", "yanlis", "bozdu", "duzelt")):
        topics.append("trust_repair")
    if any(x in msg for x in ("risk", "etik", "guvenlik")):
        topics.append("safety_ethics")
    if any(x in msg for x in ("mimari", "architecture", "pipeline", "optimizer")):
        topics.append("ai_architecture")
    if not topics:
        topics.append("natural_language")
    out: list[str] = []
    seen: set[str] = set()
    for t in topics:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out[:8]


def _as_iso_dt(value: Any) -> datetime | None:
    s = _norm_text(value)
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _privacy_risk(text: str) -> float:
    low = _lc(text)
    if not low:
        return 0.0
    risk = 0.0
    markers = ("user_", "@", "http://", "https://", "istanbul", "sok", "mah", "cad")
    if any(m in low for m in markers):
        risk += 0.6
    # number-like phone pattern
    if sum(ch.isdigit() for ch in low) >= 8:
        risk += 0.3
    return clamp(risk)


def _topic_relevance(text: str, topics: list[str]) -> float:
    content = _lc(text)
    if not content:
        return 0.0
    hit = 0
    for t in topics:
        token = _lc(t).replace("_", " ")
        bits = [b for b in token.split() if len(b) > 2]
        if any(b in content for b in bits):
            hit += 1
    return clamp(hit / max(1, len(topics)))


def _source_priority(source: str) -> float:
    src = _lc(source)
    if src == "safety_baseline":
        return 1.0
    if src == "human_risk_healing":
        return 0.96
    if src == "personal_language_dna":
        return 0.88
    if src.startswith("user_policy"):
        return 0.9
    if src.startswith("global_policy"):
        return 0.78
    if src == "micro_signal_engine":
        return 0.84
    if src == "conversation_analysis":
        return 0.86
    if src == "personal_lessons":
        return 0.82
    if src == "global_lessons":
        return 0.72
    if src.startswith("conversation_analysis_tail"):
        return 0.68
    if src == "performance":
        return 0.65
    if src == "fallback":
        return 0.5
    return 0.6


def _is_completion_ack(message: str, conversation_analysis: dict[str, Any]) -> bool:
    msg = _lc(message)
    short = len(msg.split()) <= 4
    ack = any(x in msg for x in ("tamam", "ok", "oldu", "evet", "anladim", "yaptim"))
    task_state = conversation_analysis.get("task_state", {}) if isinstance(conversation_analysis, dict) else {}
    success_signal = bool(task_state.get("task_success_signal"))
    return bool(short and ack and success_signal)


def _is_verification_intent(message: str, topics: list[str]) -> bool:
    msg = _lc(message)
    if "emin misin" not in msg:
        return False
    technical_topic = any(t in topics for t in ("technical_guidance", "coding_help", "task_success", "app_development"))
    technical_phrase = any(
        x in msg
        for x in (
            "adim",
            "adım",
            "deploy",
            "render",
            "kod",
            "api",
            "hata",
            "kurulum",
            "build",
            "terminal",
        )
    )
    caution_phrase = any(x in msg for x in ("bozmayal", "bozulmasin", "bozulmasın", "riske atmayal"))
    return bool(technical_topic or technical_phrase or caution_phrase)


@dataclass
class LearningContextBuilder:
    base_dir: Path
    policy_manager: BehaviorPolicyManager
    performance_tracker: PerformanceTracker | None = None

    def __post_init__(self) -> None:
        if self.performance_tracker is None:
            self.performance_tracker = PerformanceTracker(self.base_dir)

    @property
    def users_dir(self) -> Path:
        return self.base_dir / "data" / "users"

    @property
    def global_dir(self) -> Path:
        return self.base_dir / "data" / "global"

    def _user_dir(self, user_id: str) -> Path:
        return self.users_dir / user_id

    def _build_response_mode(
        self,
        *,
        message: str,
        micro_signals: dict[str, Any],
        conversation_analysis: dict[str, Any],
        topics: list[str],
        best_mode_hint: dict[str, Any] | None,
        human_risk_signal: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], list[str]]:
        response_needs = conversation_analysis.get("response_needs", {}) if isinstance(conversation_analysis, dict) else {}
        emotional = conversation_analysis.get("emotional_state", {}) if isinstance(conversation_analysis, dict) else {}
        reasons: list[str] = []

        confusion = safe_float(micro_signals.get("confusion_level", 0.0), 0.0)
        patience = safe_float(micro_signals.get("patience_level", 1.0), 1.0)
        urgency = safe_float(micro_signals.get("urgency_level", 0.0), 0.0)
        trust_shift = safe_float(micro_signals.get("trust_shift", 0.5), 0.5)
        closing_signal = safe_float(micro_signals.get("closing_signal", 0.0), 0.0)
        risk_signal = human_risk_signal or {}
        safety_level = _lc(risk_signal.get("safety_level", "normal"))
        risk_response = risk_signal.get("recommended_response", {}) if isinstance(risk_signal.get("recommended_response"), dict) else {}
        msg_low = _lc(message)

        # Lightweight message-level boosts to avoid under-reacting to explicit user wording.
        confusion_terms = (
            "anlamad",
            "nereye",
            "karisti",
            "karıştı",
            "karisti.",
            "yavas git",
            "yavaş git",
            "tek tek",
            "adim adim",
            "adım adım",
        )
        if any(x in msg_low for x in confusion_terms):
            confusion = max(confusion, 0.62)
            reasons.append("message_confusion_boost")

        fatigue_terms = ("yoruldum", "cok yoruldum", "çok yoruldum", "artik karisti", "artık karıştı")
        if any(x in msg_low for x in fatigue_terms):
            patience = min(patience, 0.42)
            confusion = max(confusion, 0.48)
            reasons.append("message_fatigue_boost")

        # False-positive dampening rules
        if _is_completion_ack(message, conversation_analysis):
            closing_signal = min(closing_signal, 0.15)
            patience = max(patience, 0.65)
            confusion = min(confusion, 0.2)
            reasons.append("short_ack_detected: closing/fatigue sinyali yumuşatıldı")
        if _is_verification_intent(message, topics):
            trust_shift = max(trust_shift, 0.45)
            reasons.append("verification_intent_detected: trust drop varsayımı azaltıldı")

        answer_length = _norm_text(response_needs.get("answer_length")) or "medium"
        style = _norm_text(response_needs.get("response_style")) or "warm"
        tone = "calm"
        if style in {"direct", "step_by_step"}:
            tone = "direct" if urgency >= 0.45 else "concise"
        elif style in {"reflective", "warm"}:
            tone = "warm"
        elif style == "premium_architecture":
            tone = "deep"

        use_one_step = bool(response_needs.get("should_use_one_step")) or confusion >= 0.5
        repair_first = bool(response_needs.get("should_repair_first")) or trust_shift < 0.4
        give_code = bool(response_needs.get("should_give_code")) and not use_one_step
        ask_question = bool(response_needs.get("should_ask_question")) and patience > 0.45 and not use_one_step

        # Hard situational overrides
        if confusion >= 0.55:
            answer_length = "short"
            style = "step_by_step"
            use_one_step = True
            give_code = False
            ask_question = False
            tone = "calm"
            reasons.append("high_confusion_override: short + one_step")
        elif patience <= 0.45 and confusion >= 0.35:
            answer_length = "short"
            style = "step_by_step"
            use_one_step = True
            repair_first = True
            tone = "calm"
            reasons.append("low_patience_override: repair + one_step")
        elif ("ai_architecture" in topics or "technical_guidance" in topics) and confusion <= 0.2 and "premium" in _lc(message):
            answer_length = "deep"
            style = "premium_architecture"
            use_one_step = False
            reasons.append("premium_architecture_trigger")

        if safety_level in {"sensitive", "high_risk", "crisis"}:
            answer_length = "short"
            tone = "calm"
            style = "warm" if style not in {"step_by_step", "direct"} else style
            if bool(risk_response.get("should_slow_down")):
                use_one_step = True
            if bool(risk_response.get("should_avoid_details")):
                give_code = False
                ask_question = False
            if safety_level in {"high_risk", "crisis"}:
                repair_first = True
            reasons.append(f"human_risk_override:{safety_level}")

        # Adaptive hint from historical success (avoid aggressive switching)
        hint = best_mode_hint or {}
        hint_conf = safe_float(hint.get("confidence", 0.0), 0.0)
        hint_sig = hint.get("signature", {}) if isinstance(hint.get("signature"), dict) else {}
        if hint_conf >= 0.72 and confusion < 0.55:
            # only if not hard overridden by confusion state
            style = _norm_text(hint_sig.get("style")) or style
            answer_length = _norm_text(hint_sig.get("answer_length")) or answer_length
            use_one_step = bool(hint_sig.get("use_one_step")) if hint_sig.get("use_one_step") is not None else use_one_step
            repair_first = bool(hint_sig.get("repair_first")) if hint_sig.get("repair_first") is not None else repair_first
            give_code = bool(hint_sig.get("give_code")) if hint_sig.get("give_code") is not None else give_code
            ask_question = bool(hint_sig.get("ask_question")) if hint_sig.get("ask_question") is not None else ask_question
            tone = _norm_text(hint_sig.get("tone")) or tone
            reasons.append(f"history_mode_applied(conf={round(hint_conf,2)})")
        elif hint_conf > 0:
            reasons.append(f"history_mode_ignored_low_conf({round(hint_conf,2)})")

        avoid = ["clinical_diagnosis", "medication_advice", "religious_ruling", "manipulative_language"]
        if use_one_step:
            avoid.extend(["long_explanation", "large_code_block", "too_many_questions"])
        if style == "premium_architecture":
            avoid.append("shallow_generic_reply")
        if safety_level in {"sensitive", "high_risk", "crisis"}:
            avoid.extend(["force_disclosure", "explicit_trigger_details", "judgmental_language"])

        avoid_uniq: list[str] = []
        seen: set[str] = set()
        for a in avoid:
            if a in seen:
                continue
            seen.add(a)
            avoid_uniq.append(a)

        response_mode = {
            "answer_length": answer_length,
            "style": style,
            "use_one_step": use_one_step,
            "repair_first": repair_first,
            "give_code": give_code,
            "ask_question": ask_question,
            "tone": tone,
            "avoid": avoid_uniq,
        }
        return response_mode, reasons

    def _rank_item(
        self,
        item: dict[str, Any],
        *,
        topics: list[str],
        micro_signals: dict[str, Any],
        topic_success: dict[str, Any],
        now_utc: datetime,
        duplicate_seen: set[str],
    ) -> tuple[float, dict[str, float], str]:
        text = _norm_text(item.get("text"))
        topic = _norm_text(item.get("topic"))
        source = _norm_text(item.get("source"))
        confidence = clamp(safe_float(item.get("confidence", 0.0), 0.0))
        ts = _as_iso_dt(item.get("ts"))

        topic_match = _topic_relevance(f"{text} {topic}", topics)
        if topic and topic in topic_success:
            perf_success = clamp(safe_float((topic_success.get(topic) or {}).get("average_score", 0.0), 0.0))
        else:
            perf_success = 0.55

        if ts is None:
            recency = 0.45
        else:
            age_days = max(0.0, (now_utc - ts).total_seconds() / 86400.0)
            recency = clamp(1.0 - min(1.0, age_days / 30.0))

        source_pri = _source_priority(source)
        safety_pri = 1.0 if ("safety" in _lc(source) or "safety" in _lc(topic) or "klin" in _lc(text)) else 0.0
        confusion = safe_float(micro_signals.get("confusion_level", 0.0), 0.0)
        patience = safe_float(micro_signals.get("patience_level", 1.0), 1.0)
        urgency = safe_float(micro_signals.get("urgency_level", 0.0), 0.0)
        micro_rel = 0.4
        if confusion >= 0.35 and any(x in _lc(text) for x in ("tek adim", "kisa", "sade")):
            micro_rel += 0.35
        if patience <= 0.55 and any(x in _lc(text) for x in ("yavas", "sakin", "tek adim")):
            micro_rel += 0.2
        if urgency >= 0.45 and any(x in _lc(text) for x in ("net", "dogrula", "adim")):
            micro_rel += 0.15
        micro_rel = clamp(micro_rel)

        key = _lc(text)
        duplicate_penalty = 0.35 if key in duplicate_seen else 0.0
        privacy_penalty = _privacy_risk(text)

        # weighted score
        score = (
            (topic_match * 0.25)
            + (confidence * 0.20)
            + (recency * 0.10)
            + (source_pri * 0.10)
            + (perf_success * 0.15)
            + (safety_pri * 0.10)
            + (micro_rel * 0.10)
            - (duplicate_penalty * 0.12)
            - (privacy_penalty * 0.25)
        )
        score = clamp(score)

        metrics = {
            "topic_match_score": round(topic_match, 4),
            "confidence": round(confidence, 4),
            "recency": round(recency, 4),
            "source_priority": round(source_pri, 4),
            "performance_success": round(perf_success, 4),
            "safety_priority": round(safety_pri, 4),
            "micro_signal_relevance": round(micro_rel, 4),
            "duplicate_penalty": round(duplicate_penalty, 4),
            "privacy_risk_penalty": round(privacy_penalty, 4),
        }
        reason = "ok"
        if confidence < 0.56:
            reason = "low_confidence"
        elif privacy_penalty >= 0.6:
            reason = "privacy_risk"
        elif duplicate_penalty > 0:
            reason = "duplicate"
        elif score < 0.52:
            reason = "low_rank_score"
        return score, metrics, reason

    def build_live_context(
        self,
        user_id: str,
        message: str,
        micro_signals: dict[str, Any] | None = None,
        conversation_analysis: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
        max_items: int = 12,
        language_context: dict[str, Any] | None = None,
        human_risk_signal: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = profile, session
        micro_signals = micro_signals or {}
        conversation_analysis = conversation_analysis or {}
        language_context = language_context or {}
        human_risk_signal = human_risk_signal or {}
        max_items = max(5, min(max_items, 12))
        now_utc = datetime.now(timezone.utc)

        message_topics = (
            list(conversation_analysis.get("topics", []))
            if isinstance(conversation_analysis.get("topics"), list) and conversation_analysis.get("topics")
            else _infer_topics_from_message(message)
        )
        user_dir = self._user_dir(user_id)

        # historical helpers (fast local reads)
        topic_success = (self.performance_tracker or PerformanceTracker(self.base_dir)).get_topic_success_scores(user_id)
        mode_hint = (self.performance_tracker or PerformanceTracker(self.base_dir)).get_best_response_mode_for_context(
            user_id,
            topics=message_topics,
            micro_signals=micro_signals,
        )

        response_mode, response_mode_reason = self._build_response_mode(
            message=message,
            micro_signals=micro_signals,
            conversation_analysis=conversation_analysis,
            topics=message_topics,
            best_mode_hint=mode_hint,
            human_risk_signal=human_risk_signal,
        )

        policy_ctx = self.policy_manager.build_policy_context(
            user_id,
            topics=message_topics,
            micro_signals=micro_signals,
            response_needs=response_mode,
            limit=6,
        )
        selected_policies = policy_ctx.get("selected_policies", []) if isinstance(policy_ctx, dict) else []

        # build candidate pool
        candidates: list[dict[str, Any]] = []
        candidates.append(
            {
                "type": "behavior_policy",
                "priority": 0.99,
                "topic": "safety_ethics",
                "text": "Safety: klinik/tıbbi/dini kesinlik verme; doğal dost dili koru.",
                "source": "safety_baseline",
                "confidence": 0.99,
                "ts": now_utc.isoformat().replace("+00:00", "Z"),
            }
        )

        confusion = safe_float(micro_signals.get("confusion_level", 0.0), 0.0)
        patience = safe_float(micro_signals.get("patience_level", 1.0), 1.0)
        urgency = safe_float(micro_signals.get("urgency_level", 0.0), 0.0)
        candidates.append(
            {
                "type": "micro_signal",
                "priority": 0.85,
                "topic": "confusion_reduction",
                "text": f"Micro signal: confusion={round(confusion,2)}, patience={round(patience,2)}, urgency={round(urgency,2)}.",
                "source": "micro_signal_engine",
                "confidence": 0.84,
                "ts": now_utc.isoformat().replace("+00:00", "Z"),
            }
        )
        candidates.append(
            {
                "type": "response_need",
                "priority": 0.9,
                "topic": "response_mode",
                "text": (
                    f"Response mode: {response_mode['answer_length']}, {response_mode['tone']}, "
                    f"style={response_mode['style']}, one_step={str(response_mode['use_one_step']).lower()}."
                ),
                "source": "conversation_analysis",
                "confidence": 0.9,
                "ts": now_utc.isoformat().replace("+00:00", "Z"),
            }
        )
        if response_mode.get("repair_first"):
            candidates.append(
                {
                    "type": "response_need",
                    "priority": 0.9,
                    "topic": "trust_repair",
                    "text": "Repair needed: önce kısa toparlama dili kullan, sonra tek net adım ver.",
                    "source": "conversation_analysis",
                    "confidence": 0.88,
                    "ts": now_utc.isoformat().replace("+00:00", "Z"),
                }
            )

        language_hints = language_context.get("language_hints", []) if isinstance(language_context.get("language_hints"), list) else []
        for hint in language_hints[:3]:
            txt = _norm_text(hint)
            if not txt:
                continue
            candidates.append(
                {
                    "type": "language_dna",
                    "priority": 0.77,
                    "topic": "natural_language",
                    "text": f"Language DNA: {txt}",
                    "source": "personal_language_dna",
                    "confidence": 0.8,
                    "ts": now_utc.isoformat().replace("+00:00", "Z"),
                }
            )

        risk_level = _lc(human_risk_signal.get("safety_level", "normal"))
        risk_reco = human_risk_signal.get("recommended_response", {}) if isinstance(human_risk_signal.get("recommended_response"), dict) else {}
        if risk_level in {"sensitive", "high_risk", "crisis"}:
            risk_line = "Response safety: user may be emotionally sensitive; keep calm, short, and non-judgmental language."
            if bool(risk_reco.get("should_offer_grounding")):
                risk_line = "Response safety: keep calm and validating language; offer gentle grounding before deeper steps."
            candidates.append(
                {
                    "type": "human_risk",
                    "priority": 0.94,
                    "topic": "safety_ethics",
                    "text": risk_line,
                    "source": "human_risk_healing",
                    "confidence": 0.93,
                    "ts": now_utc.isoformat().replace("+00:00", "Z"),
                }
            )

        for pol in selected_policies[:10]:
            if not isinstance(pol, dict):
                continue
            behavior = _norm_text(pol.get("behavior"))
            if not behavior:
                continue
            candidates.append(
                {
                    "type": "behavior_policy",
                    "priority": safe_float(pol.get("relevance", 0.7), 0.7),
                    "topic": _norm_text(pol.get("topic", "general")),
                    "text": behavior,
                    "source": f"{_norm_text(pol.get('scope','policy'))}_policy",
                    "confidence": safe_float(pol.get("confidence", 0.75), 0.75),
                    "ts": _norm_text(pol.get("updated_at")) or now_utc.isoformat().replace("+00:00", "Z"),
                }
            )

        personal_lessons = load_json(user_dir / "personal_lessons.json", {"items": []})
        for lesson in (personal_lessons.get("items", []) if isinstance(personal_lessons, dict) else [])[-20:]:
            if not isinstance(lesson, dict):
                continue
            behavior = _norm_text(lesson.get("behavior") or lesson.get("recommendation"))
            if not behavior:
                continue
            label_conf = _confidence_from_label(_norm_text(lesson.get("quality_label")))
            topic = _norm_text(lesson.get("theme")) or "general"
            candidates.append(
                {
                    "type": "personal_lesson",
                    "priority": 0.7,
                    "topic": topic,
                    "text": behavior,
                    "source": "personal_lessons",
                    "confidence": clamp(0.5 + label_conf * 0.4),
                    "ts": _norm_text(lesson.get("ts")),
                }
            )

        global_lessons = load_json(self.global_dir / "global_lessons.json", {"items": []})
        for lesson in (global_lessons.get("items", []) if isinstance(global_lessons, dict) else [])[-20:]:
            if not isinstance(lesson, dict):
                continue
            rec = _norm_text(lesson.get("recommendation"))
            if not rec:
                continue
            if _privacy_risk(rec) >= 0.6:
                continue
            label_conf = _confidence_from_label(_norm_text(lesson.get("quality_label", "candidate")))
            topic = _norm_text(lesson.get("theme")) or "general"
            candidates.append(
                {
                    "type": "global_lesson",
                    "priority": 0.64,
                    "topic": topic,
                    "text": rec,
                    "source": "global_lessons",
                    "confidence": clamp(0.5 + label_conf * 0.35),
                    "ts": _norm_text(lesson.get("ts")),
                }
            )

        ca_tail = _read_jsonl_tail(user_dir / "conversation_analysis.jsonl", limit=20)
        if ca_tail:
            last = ca_tail[-1]
            last_analysis = last.get("analysis", {}) if isinstance(last, dict) else {}
            if isinstance(last_analysis, dict):
                focus = _norm_text((last_analysis.get("learning_opportunity") or {}).get("recommended_training_focus"))
                if focus:
                    candidates.append(
                        {
                            "type": "performance_hint",
                            "priority": 0.62,
                            "topic": focus,
                            "text": f"Recent learning focus: {focus}.",
                            "source": "conversation_analysis_tail",
                            "confidence": 0.72,
                            "ts": _norm_text(last.get("ts")),
                        }
                    )

        performance = load_json(user_dir / "performance.json", {})
        if isinstance(performance, dict):
            overall = safe_float(performance.get("overall_performance", 0.0), 0.0)
            if overall > 0:
                hint = "Performance trend: güçlü alanları koru."
                if overall < 0.75:
                    hint = "Performance trend: netlik ve tek-adım akışını güçlendir."
                candidates.append(
                    {
                        "type": "performance_hint",
                        "priority": 0.6,
                        "topic": "general",
                        "text": hint,
                        "source": "performance",
                        "confidence": clamp(0.58 + overall * 0.2),
                        "ts": _norm_text(performance.get("last_updated")),
                    }
                )

        # rank + filter
        selected: list[dict[str, Any]] = []
        ranking_debug: list[dict[str, Any]] = []
        dropped_summary = {
            "low_confidence": 0,
            "privacy_risk": 0,
            "duplicate": 0,
            "low_rank_score": 0,
        }
        duplicate_seen: set[str] = set()

        scored: list[tuple[float, dict[str, float], str, dict[str, Any]]] = []
        for item in candidates:
            score, metrics, reason = self._rank_item(
                item,
                topics=message_topics,
                micro_signals=micro_signals,
                topic_success=topic_success,
                now_utc=now_utc,
                duplicate_seen=duplicate_seen,
            )
            entry = dict(item)
            entry["rank_score"] = round(score, 4)
            scored.append((score, metrics, reason, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        for score, metrics, reason, item in scored:
            text = _norm_text(item.get("text"))
            low_conf = safe_float(item.get("confidence", 0.0), 0.0) < 0.56
            priv_risk = _privacy_risk(text) >= 0.6
            dup = _lc(text) in duplicate_seen
            low_rank = score < 0.52

            if low_conf or priv_risk or dup or low_rank:
                if low_conf:
                    dropped_summary["low_confidence"] += 1
                elif priv_risk:
                    dropped_summary["privacy_risk"] += 1
                elif dup:
                    dropped_summary["duplicate"] += 1
                else:
                    dropped_summary["low_rank_score"] += 1
                ranking_debug.append(
                    {
                        "text": text[:120],
                        "source": item.get("source"),
                        "topic": item.get("topic"),
                        "score": round(score, 4),
                        "metrics": metrics,
                        "kept": False,
                        "drop_reason": reason,
                    }
                )
                continue

            duplicate_seen.add(_lc(text))
            selected.append(item)
            ranking_debug.append(
                {
                    "text": text[:120],
                    "source": item.get("source"),
                    "topic": item.get("topic"),
                    "score": round(score, 4),
                    "metrics": metrics,
                    "kept": True,
                    "drop_reason": "",
                }
            )
            if len(selected) >= max_items:
                break

        # Ensure 5-12 rule
        if len(selected) < 5:
            fillers = [
                {
                    "type": "behavior_policy",
                    "priority": 0.6,
                    "topic": "general",
                    "text": "Yanıtı kısa, net ve uygulanabilir tut.",
                    "source": "fallback",
                    "confidence": 0.7,
                    "ts": now_utc.isoformat().replace("+00:00", "Z"),
                    "rank_score": 0.6,
                },
                {
                    "type": "response_need",
                    "priority": 0.6,
                    "topic": "confusion_reduction",
                    "text": "Gerekirse tek adım ilerle, kullanıcı onayını bekle.",
                    "source": "fallback",
                    "confidence": 0.7,
                    "ts": now_utc.isoformat().replace("+00:00", "Z"),
                    "rank_score": 0.6,
                },
            ]
            for f in fillers:
                if len(selected) >= 5:
                    break
                if _lc(f.get("text")) not in duplicate_seen:
                    duplicate_seen.add(_lc(f.get("text")))
                    selected.append(f)

        selected = selected[:max_items]

        selected_policies = [x for x in selected if x.get("type") == "behavior_policy"]
        selected_personal = [x for x in selected if x.get("type") in {"personal_lesson", "performance_hint"} and "global" not in _lc(x.get("source"))]
        selected_global = [x for x in selected if x.get("type") == "global_lesson" or _lc(x.get("source")).startswith("global")]
        selected_language = [x for x in selected if x.get("type") == "language_dna"]
        selected_human_risk = [x for x in selected if x.get("type") == "human_risk"]

        # Build compact context text for live prompt
        lines = ["LIVE LEARNING CONTEXT:"]
        for it in selected:
            lines.append(f"- {_norm_text(it.get('text'))}")
        context_text = "\n".join(lines)
        if len(context_text) > 1200:
            compact_lines = ["LIVE LEARNING CONTEXT:"]
            size = len(compact_lines[0])
            for it in selected:
                line = f"- {_norm_text(it.get('text'))}"
                if size + len(line) + 1 > 1200:
                    break
                compact_lines.append(line)
                size += len(line) + 1
            context_text = "\n".join(compact_lines)

        # Update lightweight per-user metrics for dashboard/debug
        try:
            perf = load_json(user_dir / "performance.json", {})
            if isinstance(perf, dict):
                m = perf.setdefault("context_selection_metrics", {})
                if isinstance(m, dict):
                    m["context_selection_count"] = int(m.get("context_selection_count", 0)) + 1
                    m["dropped_low_confidence_items"] = int(m.get("dropped_low_confidence_items", 0)) + int(dropped_summary["low_confidence"])
                    m["average_context_length"] = round(
                        (
                            safe_float(m.get("average_context_length", len(context_text)), len(context_text))
                            * max(0, int(m["context_selection_count"]) - 1)
                            + len(context_text)
                        )
                        / max(1, int(m["context_selection_count"])),
                        2,
                    )
                    m["max_context_length"] = max(int(m.get("max_context_length", 0)), int(len(context_text)))
                    m["prompt_context_item_count"] = len(selected)
                    m["average_context_item_count"] = round(
                        (
                            safe_float(m.get("average_context_item_count", len(selected)), len(selected))
                            * max(0, int(m["context_selection_count"]) - 1)
                            + len(selected)
                        )
                        / max(1, int(m["context_selection_count"])),
                        2,
                    )
                    if ranking_debug:
                        kept = [d for d in ranking_debug if d.get("kept")]
                        if kept:
                            avg_topic_match = sum(safe_float((d.get("metrics") or {}).get("topic_match_score", 0.0), 0.0) for d in kept) / max(1, len(kept))
                            m["topic_context_match_score"] = round(avg_topic_match, 4)
                    total_dropped = sum(int(v) for v in dropped_summary.values())
                    m["false_positive_risk_estimate"] = round(clamp(total_dropped / max(1, len(candidates))), 4)
                    m["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                from .io_utils import save_json

                save_json(user_dir / "performance.json", perf)
        except Exception:
            # never break live context for metric write failures
            pass

        return {
            "context_text": context_text,
            "context_items": selected,
            "selected_policies": selected_policies,
            "selected_personal_lessons": selected_personal,
            "selected_global_lessons": selected_global,
            "selected_language_hints": selected_language,
            "selected_human_risk_hints": selected_human_risk,
            "response_mode": response_mode,
            "response_mode_reason": response_mode_reason,
            "topics": message_topics,
            "requested_density": (
                "short"
                if response_mode.get("answer_length") == "short"
                else "deep"
                if response_mode.get("answer_length") == "deep"
                else "adaptive"
            ),
            "ranking_debug": ranking_debug[:30],
            "dropped_items_summary": dropped_summary,
        }

    # Backward-compatible alias for earlier phases.
    def build(self, policy_context: dict[str, Any], micro_signals: dict[str, Any]) -> str:
        hints = policy_context.get("user_rules", [])[:2] + policy_context.get("global_rules", [])[:1]
        summary = "; ".join(_norm_text(x) for x in hints if _norm_text(x))
        return (
            f"Behavior hints: {summary}. "
            f"Confusion={micro_signals.get('confusion_level', 0)}, "
            f"Patience={micro_signals.get('patience_level', 1)}."
        )
