from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .group4_signals import CulturalEpistemicSignal


def _language_context(message: str) -> str:
    text = str(message or "")
    if not text.strip():
        return "unknown"
    has_ascii = any("a" <= ch.lower() <= "z" for ch in text)
    has_tr = any(ch in text for ch in "çğıöşüÇĞİÖŞÜ")
    if has_ascii and has_tr:
        return "mixed"
    if has_tr:
        return "tr"
    if has_ascii:
        return "en"
    return "unknown"


@dataclass(slots=True)
class CulturalEpistemicLayerEngine:
    def extract_cultural_epistemic_signal(
        self,
        message: str,
        analysis: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
    ) -> CulturalEpistemicSignal:
        _ = analysis, profile, session
        low = str(message or "").lower()
        epistemic_style = "balanced"
        certainty_pref = "balanced"
        if any(x in low for x in ("emin misin", "kesin", "dogru mu", "doğru mu")):
            epistemic_style = "verification_first"
            certainty_pref = "high"
        elif any(x in low for x in ("fikir", "sence", "yorum")):
            epistemic_style = "exploratory"
            certainty_pref = "low"

        return CulturalEpistemicSignal(
            language_context=_language_context(message),
            cultural_sensitivity_bucket="neutral",
            epistemic_style_bucket=epistemic_style,
            certainty_preference_bucket=certainty_pref,
            safe_summary="cultural_epistemic_stub_signal",
            confidence=0.26 if str(message or "").strip() else 0.0,
            risk_flags=[],
        )


def extract_cultural_epistemic_signal(
    message: str,
    analysis: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> CulturalEpistemicSignal:
    return CulturalEpistemicLayerEngine().extract_cultural_epistemic_signal(message, analysis, profile, session)

