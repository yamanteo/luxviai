from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .group4_signals import ReflectionSignal


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _lc(value: Any) -> str:
    return _norm(value).lower()


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(t in text for t in terms)


def _safety_flag(analysis: dict[str, Any] | None) -> bool:
    analysis = analysis or {}
    if bool(analysis.get("crisis_risk")):
        return True
    safety = analysis.get("safety_layer", {})
    if isinstance(safety, dict):
        crisis_context = _lc(safety.get("crisis_context"))
        if crisis_context and crisis_context != "none":
            return True
        if bool(safety.get("needs_gentle_check")):
            return True
    return False


def _answer_style(text: str) -> str:
    technical_terms = (
        "kod",
        "debug",
        "deploy",
        "endpoint",
        "terminal",
        "port",
        "websocket",
        "dosya",
        "api",
        "hata",
        "build",
        "config",
    )
    concise_terms = ("kisa", "kısa", "brief", "short", "tek adim", "tek adım", "bir sonraki adim", "bir sonraki adım")
    supportive_terms = ("yoruldum", "yorgunum", "karisti", "karıştı", "zorlandim", "zorlandım")
    reflective_terms = ("sence", "anlami", "anlamı", "dusun", "düşün", "hissed", "neden")
    if _has_any(text, technical_terms):
        return "technical"
    if _has_any(text, concise_terms):
        return "concise"
    if _has_any(text, supportive_terms):
        return "supportive"
    if _has_any(text, reflective_terms):
        return "reflective"
    if text:
        return "neutral"
    return "unknown"


def _needs_clarification(text: str) -> bool:
    return _has_any(
        text,
        (
            "anlamad",
            "hangisi",
            "netlestir",
            "netleştir",
            "yanlis anladin",
            "yanlış anladın",
            "onu demedim",
            "ne demek",
        ),
    )


def _correction_signal(text: str) -> str:
    if _has_any(text, ("ben ruyadan bahsetmedim", "ben rüyadan bahsetmedim", "ruyadan bahsetmedim", "rüyadan bahsetmedim")):
        return "assistant_error_ack_needed"
    if _has_any(text, ("bunu sen yazdin", "bunu sen yazdın", "sen yazdin", "sen yazdın")):
        return "assistant_error_ack_needed"
    if _has_any(text, ("yanlis anladin", "yanlış anladın", "onu demek istemedim", "onu demedim")):
        return "user_correction"
    if _has_any(text, ("metafor yapma", "boyle kisaltmalar yazma", "böyle kısaltmalar yazma", "teknik bir sey", "teknik bir şey")):
        return "prompt_boundary_feedback"
    return "none"


def _utility_guard(text: str, answer_style: str, correction_signal: str) -> str:
    if correction_signal == "prompt_boundary_feedback" and "metafor" in text:
        return "avoid_metaphor"
    if answer_style == "technical":
        if _has_any(text, ("metafor", "siir", "şiir", "lens", "ruya", "rüya", "luxdream", "luxching", "luxmirror")):
            return "avoid_lens_offer"
        return "technical_direct"
    return "none"


def _half_step_style(text: str, answer_style: str, correction_signal: str, needs_clarification: bool) -> str:
    if correction_signal in {"assistant_error_ack_needed", "user_correction", "prompt_boundary_feedback"}:
        return "next_action"
    if answer_style in {"technical", "concise"}:
        return "next_action"
    if _has_any(text, ("cikmali miyim", "çıkmalı mıyım", "hangisini", "karar", "secenek", "seçenek")):
        return "option"
    if needs_clarification:
        return "gentle_question"
    if answer_style == "reflective":
        return "observation"
    if answer_style == "supportive":
        return "natural_pause"
    return "none"


def _verbosity_bucket(text: str) -> str:
    word_count = len(text.split())
    if word_count == 0:
        return "unknown"
    if word_count <= 12:
        return "short"
    if word_count <= 45:
        return "medium"
    if word_count <= 90:
        return "long"
    return "too_long"


def _risk_review_bucket(text: str, analysis: dict[str, Any] | None, safety_flag: bool) -> str:
    if safety_flag:
        return "high"
    analysis = analysis or {}
    risk_terms = (
        "risk",
        "etik",
        "tehlike",
        "zarar",
        "tanı",
        "tani",
        "ilaç",
        "ilac",
        "tedavi",
        "dini hüküm",
        "fal",
        "kehanet",
    )
    if _has_any(text, risk_terms):
        return "medium"
    if bool((analysis.get("safety_layer") or {}).get("needs_gentle_check")):
        return "medium"
    return "none"


def _confidence(
    *,
    text: str,
    answer_style: str,
    needs_clarification: bool,
    risk_review: str,
    correction_signal: str,
    utility_guard: str,
    half_step_style: str,
    verbosity: str,
) -> float:
    if not text:
        return 0.0
    score = 0.42
    if answer_style not in {"neutral", "unknown"}:
        score += 0.12
    if needs_clarification:
        score += 0.12
    if risk_review != "none":
        score += 0.16
    if correction_signal != "none":
        score += 0.18
    if utility_guard != "none":
        score += 0.14
    if half_step_style != "none":
        score += 0.08
    if verbosity in {"long", "too_long"}:
        score += 0.06
    return max(0.0, min(0.94, score))


@dataclass(slots=True)
class ReflectionLayerEngine:
    def extract_reflection_signal(
        self,
        message: str,
        analysis: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
    ) -> ReflectionSignal:
        _ = profile, session
        text = _lc(message)
        safety = _safety_flag(analysis)
        style = _answer_style(text)
        needs_clarification = _needs_clarification(text)
        correction = _correction_signal(text)
        utility = _utility_guard(text, style, correction)
        half_step = _half_step_style(text, style, correction, needs_clarification)
        verbosity = _verbosity_bucket(text)
        risk_review = _risk_review_bucket(text, analysis, safety)
        conf = _confidence(
            text=text,
            answer_style=style,
            needs_clarification=needs_clarification,
            risk_review=risk_review,
            correction_signal=correction,
            utility_guard=utility,
            half_step_style=half_step,
            verbosity=verbosity,
        )
        risk_flags: list[str] = []
        if safety:
            risk_flags.append("safety_sensitive")
        if conf < 0.6:
            risk_flags.append("low_confidence")
        if utility in {"avoid_metaphor", "avoid_lens_offer"}:
            risk_flags.append("utility_guard")

        if conf < 0.6:
            safe_summary = "reflection_low_confidence_neutral"
        elif correction != "none":
            safe_summary = "reflection_correction_guard"
        elif utility != "none":
            safe_summary = "reflection_utility_guard"
        elif risk_review != "none":
            safe_summary = "reflection_risk_review"
        else:
            safe_summary = "reflection_quality_hint"

        return ReflectionSignal(
            answer_style_bucket=style,
            needs_clarification=needs_clarification,
            risk_review_bucket=risk_review,
            half_step_style=half_step,
            correction_signal=correction,
            utility_guard_signal=utility,
            verbosity_bucket=verbosity,
            safe_summary=safe_summary,
            confidence=conf,
            risk_flags=risk_flags,
        )


def extract_reflection_signal(
    message: str,
    analysis: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> ReflectionSignal:
    return ReflectionLayerEngine().extract_reflection_signal(message, analysis, profile, session)
