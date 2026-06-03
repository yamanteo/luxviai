from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .group3_signals import ExistentialSignal


def _fold_tr(value: str) -> str:
    raw = value or ""
    if any(ch in raw for ch in ("Ã", "Ä", "Å")):
        try:
            raw = raw.encode("latin1", "ignore").decode("utf-8", "ignore")
        except Exception:
            pass
    table = str.maketrans(
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
    return raw.translate(table).lower()


MEANING_TERMS = ("anlam", "amac", "niye", "neden", "bosluk", "anlamsiz")
IDENTITY_TERMS = ("kimim", "kendim", "ben kim", "kimlik", "ozum", "ozdeger")
DIRECTION_TERMS = ("yon", "nereye", "ne yapmak", "hangi yol", "ilerleyem", "kararsiz")
LONELINESS_TERMS = ("yalniz", "tek basima", "kimse yok", "gorulm", "anlasilm")
TIME_PRESSURE_TERMS = ("yetis", "gec", "zaman", "acele", "bugun", "yarin", "cok gec")
UNCERTAINTY_TERMS = ("bilmiyorum", "emin degilim", "kararsiz", "belirsiz", "kafam karisik")

HIGH_TIME_TERMS = ("hemen", "acil", "simdi", "yetişem", "gec kaldim")
HIGH_UNCERTAINTY_TERMS = ("hic bilmiyorum", "tamamen belirsiz", "ne yapacagimi bilmiyorum")

GROUNDING_TERMS = ("yoruldum", "karisti", "bunaldim", "sikistim", "dayanamiyorum")


def _signal_level(text: str, terms: tuple[str, ...]) -> str:
    hits = 0
    for t in terms:
        if re.search(rf"\b{re.escape(t)}", text):
            hits += 1
    if hits <= 0:
        return "none"
    if hits == 1:
        return "background"
    return "active"


def _bucket_from_hits(text: str, terms: tuple[str, ...], high_terms: tuple[str, ...] = ()) -> str:
    hits = sum(1 for t in terms if re.search(rf"\b{re.escape(t)}", text))
    if hits <= 0:
        return "none"
    if any(ht in text for ht in high_terms):
        return "high"
    if hits >= 3:
        return "high"
    if hits == 2:
        return "medium"
    return "low"


@dataclass(slots=True)
class ExistentialLayerEngine:
    def extract_existential_signal(
        self,
        message: str,
        analysis: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
    ) -> ExistentialSignal:
        _ = analysis, profile, session
        raw = str(message or "")
        folded = _fold_tr(raw)
        variants = [folded, folded.replace("?", "i"), folded.replace("?", "u")]

        def pick_signal(terms: tuple[str, ...]) -> str:
            rank = {"none": 0, "background": 1, "active": 2}
            best = "none"
            for v in variants:
                cur = _signal_level(v, terms)
                if rank[cur] > rank[best]:
                    best = cur
            return best

        def pick_bucket(terms: tuple[str, ...], high_terms: tuple[str, ...] = ()) -> str:
            rank = {"none": 0, "low": 1, "medium": 2, "high": 3}
            best = "none"
            for v in variants:
                cur = _bucket_from_hits(v, terms, high_terms)
                if rank[cur] > rank[best]:
                    best = cur
            return best

        meaning_signal = pick_signal(MEANING_TERMS)
        identity_signal = pick_signal(IDENTITY_TERMS)
        direction_signal = pick_signal(DIRECTION_TERMS)
        loneliness_signal = pick_signal(LONELINESS_TERMS)
        time_pressure = pick_bucket(TIME_PRESSURE_TERMS, HIGH_TIME_TERMS)
        uncertainty = pick_bucket(UNCERTAINTY_TERMS, HIGH_UNCERTAINTY_TERMS)

        if all(x == "none" for x in (meaning_signal, identity_signal, direction_signal, loneliness_signal)) and time_pressure == "none" and uncertainty == "none":
            return ExistentialSignal.neutral()

        support_need = "none"
        if any(any(t in v for t in GROUNDING_TERMS) for v in variants) or uncertainty in {"medium", "high"}:
            support_need = "grounding"
        if time_pressure in {"medium", "high"} or any("adim adim" in v or "yavas" in v for v in variants):
            support_need = "one_step" if support_need != "grounding" else "grounding"
        elif support_need == "none":
            support_need = "soft"

        confidence = 0.35
        active_count = sum(
            1 for s in (meaning_signal, identity_signal, direction_signal, loneliness_signal) if s != "none"
        )
        confidence += min(active_count * 0.12, 0.36)
        if time_pressure != "none":
            confidence += 0.08
        if uncertainty != "none":
            confidence += 0.1
        confidence = max(0.0, min(1.0, confidence))

        risk_flags: list[str] = []
        if any(any(x in v for x in ("kesin kader", "dini hukum", "fetva")) for v in variants):
            risk_flags.append("religious_judgment_risk")
        if any(any(x in v for x in ("tani", "tedavi", "ilac")) for v in variants):
            risk_flags.append("clinical_label_risk")

        summary_parts = []
        if meaning_signal != "none":
            summary_parts.append("meaning")
        if direction_signal != "none":
            summary_parts.append("direction")
        if uncertainty != "none":
            summary_parts.append(f"uncertainty:{uncertainty}")
        safe_summary = "existential_signal:" + (",".join(summary_parts) if summary_parts else "active")

        return ExistentialSignal(
            meaning_signal=meaning_signal,
            identity_signal=identity_signal,
            direction_signal=direction_signal,
            loneliness_signal=loneliness_signal,
            time_pressure=time_pressure,
            uncertainty=uncertainty,
            support_need=support_need,
            # legacy aliases
            meaning_tension="high" if meaning_signal == "active" else "low" if meaning_signal == "background" else "none",
            identity_tension="high" if identity_signal == "active" else "low" if identity_signal == "background" else "none",
            direction_uncertainty=time_pressure if time_pressure != "none" else uncertainty,
            safe_summary=safe_summary,
            confidence=confidence,
            risk_flags=risk_flags[:4],
        )


def extract_existential_signal(
    message: str,
    analysis: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> ExistentialSignal:
    return ExistentialLayerEngine().extract_existential_signal(message, analysis, profile, session)
