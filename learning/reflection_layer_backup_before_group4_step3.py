from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .group4_signals import ReflectionSignal


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
        analysis = analysis or {}
        text = str(message or "").strip().lower()
        needs_clarification = any(x in text for x in ("anlamad", "hangisi", "netlestir", "netleştir"))
        answer_style = "neutral"
        if any(x in text for x in ("adim adim", "adım adım", "tek adim", "tek adım")):
            answer_style = "step_by_step"
        elif any(x in text for x in ("kisa", "kısa", "ozet", "özet")):
            answer_style = "concise"
        elif any(x in text for x in ("derin", "premium", "mimari")):
            answer_style = "reflective"

        half_step_style = "observation"
        if needs_clarification:
            half_step_style = "micro_question"

        risk_bucket = "none"
        if bool((analysis.get("safety_layer") or {}).get("needs_gentle_check")):
            risk_bucket = "light"

        return ReflectionSignal(
            answer_style_bucket=answer_style,
            needs_clarification=needs_clarification,
            risk_review_bucket=risk_bucket,
            half_step_style=half_step_style,
            safe_summary="reflection_stub_signal",
            confidence=0.24 if text else 0.0,
            risk_flags=[],
        )


def extract_reflection_signal(
    message: str,
    analysis: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> ReflectionSignal:
    return ReflectionLayerEngine().extract_reflection_signal(message, analysis, profile, session)

