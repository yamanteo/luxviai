from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


def _lc(value: Any) -> str:
    return _norm_text(value).lower()


def _fold_tr_ascii(text: str) -> str:
    mapping = str.maketrans(
        {
            "ç": "c",
            "Ç": "c",
            "ğ": "g",
            "Ğ": "g",
            "ı": "i",
            "İ": "i",
            "ö": "o",
            "Ö": "o",
            "ş": "s",
            "Ş": "s",
            "ü": "u",
            "Ü": "u",
        }
    )
    return (text or "").translate(mapping).lower()


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    low = _fold_tr_ascii(text)
    return any(n in low for n in needles)


def _bool_from(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    txt = _fold_tr_ascii(_norm_text(value))
    return txt in {"true", "1", "yes", "var", "aktif", "high", "yuksek"}


@dataclass
class Group2LayerBridge:
    """Narrative + Contradiction + Relationship + Safety/Ethics bridge.

    Produces short, safe and non-clinical signals to improve response behavior
    without changing transport format.
    """

    def extract_signals(self, analysis: dict[str, Any], message: str = "") -> dict[str, Any]:
        layers = analysis.get("layers", {}) if isinstance(analysis.get("layers"), dict) else {}
        narrative = layers.get("narrative", {}) if isinstance(layers.get("narrative"), dict) else {}
        contradiction = layers.get("contradiction", {}) if isinstance(layers.get("contradiction"), dict) else {}
        relationship = layers.get("relationship", {}) if isinstance(layers.get("relationship"), dict) else {}
        safety = layers.get("safety_ethics", {}) if isinstance(layers.get("safety_ethics"), dict) else {}

        low_message = _fold_tr_ascii(message)

        # Narrative
        has_narrative = bool(narrative) or _contains_any(
            low_message,
            ("hikaye", "anlati", "toparla", "bunu duzenle", "devam", "baglam"),
        )
        has_context_refs = _contains_any(
            low_message,
            ("dun", "once", "simdi", "az once", "bu konuda", "bunu", "onu"),
        )
        narrative_continuity_score = _clamp(
            (0.48 if has_narrative else 0.22)
            + (0.22 if has_context_refs else 0.08)
            + (0.2 if _norm_text(narrative.get("story_pattern")) else 0.06)
            + (0.1 if _norm_text(narrative.get("inner_rewrite")) else 0.04)
        )

        # Contradiction
        contradiction_marked = bool(contradiction.get("detected")) or _bool_from(analysis.get("contradiction_marker"))
        contradiction_text = _contains_any(
            low_message,
            ("farkli soyluyorsun", "hangisi dogru", "celiski", "yanlis anladin", "onu demek istemedim"),
        )
        contradiction_signal_score = _clamp(
            (0.45 if contradiction_marked else 0.12)
            + (0.34 if contradiction_text else 0.08)
            + (0.12 if _norm_text(contradiction.get("meta_awareness")) else 0.0)
        )
        clarification_need_signal = _clamp(
            0.20
            + contradiction_signal_score * 0.55
            + (0.15 if _contains_any(low_message, ("hangisi", "netlestir", "acikla")) else 0.0)
        )

        # Relationship
        relationship_text = _contains_any(
            low_message,
            ("aldatiyor", "guven", "kiskan", "yanlis anladin", "yargilama", "iliski", "kiril"),
        )
        relationship_distress_signal = _clamp(
            (0.30 if relationship_text else 0.10)
            + (0.22 if _contains_any(_lc(relationship.get("pattern")), ("gerilim", "kopuk", "catism")) else 0.08)
            + (0.18 if _contains_any(_lc(relationship.get("social_exhaustion")), ("var", "high", "yuksek")) else 0.06)
            + (0.14 if _contains_any(_lc(relationship.get("approach_withdrawal")), ("geri", "withdraw")) else 0.0)
        )
        boundary_support_signal = _clamp(
            0.18
            + relationship_distress_signal * 0.42
            + (0.18 if _contains_any(low_message, ("yargilamadan", "sinir", "zorlamadan")) else 0.0)
            + (0.12 if _contains_any(_lc(safety.get("parasocial_risk")), ("orta", "yuksek", "high")) else 0.0)
        )

        # Safety & privacy
        crisis_level = _lc(safety.get("crisis_level"))
        crisis_context = _lc(safety.get("crisis_context"))
        needs_gentle = bool(safety.get("needs_gentle_check"))
        has_risky_request = _contains_any(
            low_message,
            ("kesin soyle", "garanti ver", "etik olmayan", "riskli", "tehlikeli"),
        )
        safety_ethics_alignment = _clamp(
            0.92
            - (0.20 if crisis_level in {"high", "critical", "yuksek"} else 0.0)
            - (0.10 if has_risky_request else 0.0)
            - (0.08 if "immediate" in crisis_context else 0.0)
            + (0.06 if needs_gentle else 0.0)
        )

        pii_hits = 0
        pii_hits += 1 if re.search(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", message or "", flags=re.IGNORECASE) else 0
        pii_hits += 1 if re.search(r"\b\d{10,}\b", message or "") else 0
        pii_hits += 1 if re.search(r"https?://\S+", message or "", flags=re.IGNORECASE) else 0
        privacy_protection_score = _clamp(0.95 - pii_hits * 0.15)

        context_coherence_score = _clamp(
            0.25
            + narrative_continuity_score * 0.45
            + (0.20 if contradiction_signal_score < 0.45 else 0.08)
            + (0.10 if _norm_text(analysis.get("theme")) else 0.04)
        )

        response_risk_reduction = _clamp(
            0.20
            + safety_ethics_alignment * 0.35
            + boundary_support_signal * 0.25
            + (0.16 if clarification_need_signal >= 0.5 else 0.06)
            + (0.14 if needs_gentle else 0.0)
        )

        if clarification_need_signal >= 0.60:
            response_tone_adjustment = "clarify_then_one_step"
        elif relationship_distress_signal >= 0.55:
            response_tone_adjustment = "warm_boundary_support"
        elif safety_ethics_alignment < 0.75:
            response_tone_adjustment = "safety_first_concise"
        else:
            response_tone_adjustment = "coherent_calm"

        return {
            "narrative_continuity_score": round(narrative_continuity_score, 4),
            "context_coherence_score": round(context_coherence_score, 4),
            "contradiction_signal_score": round(contradiction_signal_score, 4),
            "clarification_need_signal": round(clarification_need_signal, 4),
            "relationship_distress_signal": round(relationship_distress_signal, 4),
            "boundary_support_signal": round(boundary_support_signal, 4),
            "safety_ethics_alignment": round(safety_ethics_alignment, 4),
            "privacy_protection_score": round(privacy_protection_score, 4),
            "response_risk_reduction": round(response_risk_reduction, 4),
            "response_tone_adjustment": response_tone_adjustment,
        }

    def behavior_hints(self, signals: dict[str, Any]) -> list[str]:
        hints: list[str] = []
        contradiction = _safe_float(signals.get("contradiction_signal_score"), 0.0)
        clarification = _safe_float(signals.get("clarification_need_signal"), 0.0)
        distress = _safe_float(signals.get("relationship_distress_signal"), 0.0)
        boundary = _safe_float(signals.get("boundary_support_signal"), 0.0)
        safety_align = _safe_float(signals.get("safety_ethics_alignment"), 1.0)

        if contradiction >= 0.45 or clarification >= 0.55:
            hints.append("Once anlami netlestir, sonra tek net adimla ilerle.")
        if distress >= 0.5 or boundary >= 0.5:
            hints.append("Yargisiz ve sakin dil kullan; kesin iliski yargilarindan kacin.")
        if safety_align < 0.8:
            hints.append("Guvenlik ve mahremiyet oncelikli kal; kesinlikten uzak bir ton sec.")
        if not hints:
            hints.append("Baglami koruyarak kisa ve net ilerle.")
        return hints[:3]

    def personal_lesson_text(self, signals: dict[str, Any]) -> str:
        if _safe_float(signals.get("clarification_need_signal"), 0.0) >= 0.55:
            return "Kullanici uyum sorusunda once netlestirme sonra tek adimla daha iyi ilerliyor."
        if _safe_float(signals.get("relationship_distress_signal"), 0.0) >= 0.5:
            return "Iliski gerilimi sinyalinde yargisiz ve sinir koruyan ton daha faydali."
        if _safe_float(signals.get("safety_ethics_alignment"), 1.0) < 0.8:
            return "Riskli baglamda kisa, sakin ve guvenlik odakli yanit tercih edilmeli."
        return "Baglam butunlugunu koruyan net ve sade yanitlar daha tutarli sonuc veriyor."

    def global_lesson_text(self, signals: dict[str, Any]) -> str:
        if _safe_float(signals.get("clarification_need_signal"), 0.0) >= 0.55:
            return "Uyumsuzluk sinyalinde once netlestirme, sonra tek adim verme tutarliligi artirir."
        if _safe_float(signals.get("relationship_distress_signal"), 0.0) >= 0.5:
            return "Iliski geriliminde yargisiz ve sinir-koruyucu dil guveni destekler."
        if _safe_float(signals.get("safety_ethics_alignment"), 1.0) < 0.8:
            return "Hassas baglamda guvenlik ve mahremiyet oncelikli, kisa yanit riski azaltir."
        return "Baglam surekliligini koruyan sakin dil genel kaliteyi dengeli bicimde artirir."

