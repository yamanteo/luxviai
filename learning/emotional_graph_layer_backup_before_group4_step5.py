from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .group4_signals import EmotionalGraphSignal


def _bucket_emotion(value: Any) -> str:
    low = str(value or "").strip().lower()
    if not low:
        return "unknown"
    if low in {"mutlu", "rahat", "huzurlu", "joy", "calm", "hopeful"}:
        return "positive"
    if low in {"uzgun", "kaygili", "ofkeli", "yorgun", "sad", "anxious", "angry", "tired"}:
        return "negative"
    if low in {"mixed", "karisik", "ambivalent"}:
        return "mixed"
    return "neutral"


def _bucket_intensity(value: Any) -> str:
    try:
        iv = float(value)
    except Exception:
        return "unknown"
    if iv >= 7:
        return "high"
    if iv >= 4:
        return "medium"
    return "low"


@dataclass(slots=True)
class EmotionalGraphLayerEngine:
    def extract_emotional_graph_signal(
        self,
        message: str,
        analysis: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
    ) -> EmotionalGraphSignal:
        _ = message, profile, session
        analysis = analysis or {}
        bucket = _bucket_emotion(analysis.get("primary_emotion"))
        intensity = _bucket_intensity(analysis.get("intensity"))
        continuity = "continuing" if analysis.get("theme") else "unknown"
        return EmotionalGraphSignal(
            dominant_emotion_bucket=bucket,
            emotion_shift_bucket="stable",
            emotional_intensity_bucket=intensity,
            continuity_bucket=continuity,
            safe_summary="emotional_graph_stub_signal",
            confidence=0.24 if bucket != "unknown" else 0.0,
            risk_flags=[],
        )


def extract_emotional_graph_signal(
    message: str,
    analysis: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> EmotionalGraphSignal:
    return EmotionalGraphLayerEngine().extract_emotional_graph_signal(message, analysis, profile, session)

