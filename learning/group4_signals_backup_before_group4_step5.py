from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, safe_float(value, lo)))


def _safe_flags(flags: list[Any] | None, limit: int = 8) -> list[str]:
    out: list[str] = []
    for f in flags or []:
        text = str(f).strip()
        if not text or text in out:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


@dataclass(slots=True)
class EmotionalGraphSignal:
    dominant_emotion_bucket: str = "neutral"  # neutral|positive|negative|mixed|unknown
    emotion_shift_bucket: str = "stable"  # stable|shift_up|shift_down|oscillating|unknown
    emotional_intensity_bucket: str = "low"  # low|medium|high|unknown
    continuity_bucket: str = "unknown"  # unknown|single|continuing|repeating
    safe_summary: str = "no_emotional_graph_signal"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)

    @classmethod
    def neutral(cls) -> "EmotionalGraphSignal":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "dominant_emotion_bucket": str(self.dominant_emotion_bucket),
            "emotion_shift_bucket": str(self.emotion_shift_bucket),
            "emotional_intensity_bucket": str(self.emotional_intensity_bucket),
            "continuity_bucket": str(self.continuity_bucket),
            "safe_summary": str(self.safe_summary),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": _safe_flags(self.risk_flags),
        }


@dataclass(slots=True)
class TimeEcologySignal:
    time_of_day_bucket: str = "unknown"  # morning|afternoon|evening|night|unknown
    rhythm_bucket: str = "unknown"  # calm|rushed|repetitive|disrupted|unknown
    fatigue_context_bucket: str = "none"  # none|possible|explicit|high
    urgency_bucket: str = "none"  # none|low|medium|high
    safe_summary: str = "no_time_ecology_signal"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)

    @classmethod
    def neutral(cls) -> "TimeEcologySignal":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "time_of_day_bucket": str(self.time_of_day_bucket),
            "rhythm_bucket": str(self.rhythm_bucket),
            "fatigue_context_bucket": str(self.fatigue_context_bucket),
            "urgency_bucket": str(self.urgency_bucket),
            "safe_summary": str(self.safe_summary),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": _safe_flags(self.risk_flags),
        }


@dataclass(slots=True)
class CulturalEpistemicSignal:
    language_context: str = "unknown"  # tr|en|es|fr|de|ar|zh|ja|ru|pt|mixed|unknown
    register_formality: str = "unknown"  # formal|neutral|casual|unknown
    directness_style: str = "unknown"  # direct|softened|exploratory|unknown
    politeness_style: str = "unknown"  # formal_address|casual_address|neutral|unknown
    idiom_preference: str = "unknown"  # literal_plain|light_idiom|avoid_idiom|unknown
    explanation_style: str = "unknown"  # concise|example_led|principle_led|step_by_step|neutral|unknown
    mixed_language_state: str = "unknown"  # none|code_switching|dominant_language_clear|dominant_language_unclear|unknown
    cultural_sensitivity_bucket: str = "neutral"  # neutral|sensitive|high_attention
    epistemic_style_bucket: str = "balanced"  # balanced|certainty_seeking|exploratory|verification_first
    certainty_preference_bucket: str = "balanced"  # low|balanced|high
    safe_summary: str = "no_cultural_epistemic_signal"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)

    @classmethod
    def neutral(cls) -> "CulturalEpistemicSignal":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "language_context": str(self.language_context),
            "register_formality": str(self.register_formality),
            "directness_style": str(self.directness_style),
            "politeness_style": str(self.politeness_style),
            "idiom_preference": str(self.idiom_preference),
            "explanation_style": str(self.explanation_style),
            "mixed_language_state": str(self.mixed_language_state),
            "cultural_sensitivity_bucket": str(self.cultural_sensitivity_bucket),
            "epistemic_style_bucket": str(self.epistemic_style_bucket),
            "certainty_preference_bucket": str(self.certainty_preference_bucket),
            "safe_summary": str(self.safe_summary),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": _safe_flags(self.risk_flags),
        }


@dataclass(slots=True)
class ReflectionSignal:
    answer_style_bucket: str = "neutral"  # concise|explanatory|supportive|technical|reflective|neutral|unknown
    needs_clarification: bool = False
    risk_review_bucket: str = "none"  # none|low|medium|high
    half_step_style: str = "none"  # none|observation|option|natural_pause|gentle_question|next_action
    correction_signal: str = "none"  # none|user_correction|assistant_error_ack_needed|prompt_boundary_feedback
    utility_guard_signal: str = "none"  # none|technical_direct|avoid_metaphor|avoid_lens_offer
    verbosity_bucket: str = "unknown"  # short|medium|long|too_long|unknown
    safe_summary: str = "no_reflection_signal"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)

    @classmethod
    def neutral(cls) -> "ReflectionSignal":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "answer_style_bucket": str(self.answer_style_bucket),
            "needs_clarification": bool(self.needs_clarification),
            "risk_review_bucket": str(self.risk_review_bucket),
            "half_step_style": str(self.half_step_style),
            "correction_signal": str(self.correction_signal),
            "utility_guard_signal": str(self.utility_guard_signal),
            "verbosity_bucket": str(self.verbosity_bucket),
            "safe_summary": str(self.safe_summary),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": _safe_flags(self.risk_flags),
        }


@dataclass(slots=True)
class Group4Bundle:
    emotional_graph: EmotionalGraphSignal = field(default_factory=EmotionalGraphSignal.neutral)
    time_ecology: TimeEcologySignal = field(default_factory=TimeEcologySignal.neutral)
    cultural_epistemic: CulturalEpistemicSignal = field(default_factory=CulturalEpistemicSignal.neutral)
    reflection: ReflectionSignal = field(default_factory=ReflectionSignal.neutral)
    safe_summary: str = "group4_neutral_bundle"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)

    @classmethod
    def neutral(cls) -> "Group4Bundle":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "emotional_graph": self.emotional_graph.to_safe_dict(),
            "time_ecology": self.time_ecology.to_safe_dict(),
            "cultural_epistemic": self.cultural_epistemic.to_safe_dict(),
            "reflection": self.reflection.to_safe_dict(),
            "safe_summary": str(self.safe_summary),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": _safe_flags(self.risk_flags, limit=10),
            "created_at": str(self.created_at),
        }
