from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .group3_signals import DreamSignal


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


POSITIVE_PATTERNS = (
    r"\bruyamda\b",
    r"\bruya g(o|ö)rd(u|ü)m\b",
    r"\bruya g[a-z]?rd[a-z]?m\b",
    r"\bkabus g(o|ö)rd(u|ü)m\b",
    r"\bkabus g[a-z]?rd[a-z]?m\b",
    r"\buyand(i|ı)g(i|ı)mda\b",
    r"\buyand[a-z]*mda\b",
    r"\bruyami yorumla\b",
    r"\bruya(y)?a eslik et\b",
)

FALSE_POSITIVE_PATTERNS = (
    r"\bruya\s+(kafe|cafe|bar|pub|otel|hotel|restoran)\b",
    r"\bruya diye (bir )?(arkadas|dost)\w*\b",
    r"\bruya gibi\b",
    r"\bruya adli\b",
)

IMAGE_TERMS = (
    "deniz",
    "ev",
    "oda",
    "kapi",
    "yol",
    "tren",
    "ayna",
    "isik",
    "golge",
    "dag",
    "orman",
    "su",
)

TENSE_WORDS = ("huzursuz", "korku", "gergin", "panik", "kabus")
HEAVY_WORDS = ("bogul", "olum", "karanlik", "sikism", "kacis", "donakal")
SOFT_WORDS = ("sakin", "huzur", "hafif", "iyi", "rahat")


def _count_image_terms(text: str) -> int:
    return sum(1 for t in IMAGE_TERMS if re.search(rf"\b{re.escape(t)}\b", text))


@dataclass(slots=True)
class DreamLayerEngine:
    def extract_dream_signal(
        self,
        message: str,
        analysis: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
    ) -> DreamSignal:
        _ = analysis, profile, session
        raw = str(message or "")
        folded = _fold_tr(raw)
        variants = [folded, folded.replace("?", "u"), folded.replace("?", "i")]

        false_positive = any(re.search(p, variant) for variant in variants for p in FALSE_POSITIVE_PATTERNS)
        positive_hits = sum(1 for p in POSITIVE_PATTERNS if any(re.search(p, variant) for variant in variants))
        is_dream_context = positive_hits > 0 and not false_positive

        if not is_dream_context and not false_positive:
            return DreamSignal.neutral()

        image_count = max(_count_image_terms(v) for v in variants) if is_dream_context else 0
        if image_count <= 0:
            image_count_bucket = "none"
        elif image_count <= 2:
            image_count_bucket = "few"
        else:
            image_count_bucket = "many"

        if not is_dream_context:
            dream_intensity = "none"
        elif positive_hits <= 1 and image_count <= 1:
            dream_intensity = "low"
        elif positive_hits >= 3 or image_count >= 3:
            dream_intensity = "high"
        else:
            dream_intensity = "medium"

        emotional_residue = "unknown"
        if not is_dream_context:
            emotional_residue = "none"
        elif any(any(w in v for w in HEAVY_WORDS) for v in variants):
            emotional_residue = "heavy"
        elif any(any(w in v for w in TENSE_WORDS) for v in variants):
            emotional_residue = "tense"
        elif any(any(w in v for w in SOFT_WORDS) for v in variants):
            emotional_residue = "soft"

        continuation_ready = is_dream_context and (
            any("ruyami yorumla" in v for v in variants)
            or any("ruyaya eslik et" in v for v in variants)
            or any("uyandigimda" in v for v in variants)
            or image_count >= 1
        )
        confidence = 0.0
        if false_positive:
            confidence = 0.9
        elif is_dream_context:
            confidence = min(1.0, 0.45 + (positive_hits * 0.15) + (0.05 * min(image_count, 4)))

        risk_flags: list[str] = []
        if any(any(x in v for x in ("kehanet", "fal", "kader")) for v in variants):
            risk_flags.append("prophecy_language_present")

        summary = "dream_signal:none"
        if false_positive:
            summary = "dream_signal:false_positive_blocked"
        elif is_dream_context:
            summary = f"dream_signal:{dream_intensity}:{emotional_residue}"

        return DreamSignal(
            is_dream_context=is_dream_context,
            false_positive_blocked=bool(false_positive),
            dream_intensity=dream_intensity,
            image_count_bucket=image_count_bucket,
            emotional_residue=emotional_residue,
            continuation_ready=bool(continuation_ready),
            dream_context=is_dream_context,
            false_positive_guarded=not is_dream_context,
            imagery_buckets=[image_count_bucket] if image_count_bucket != "none" else [],
            affect_bucket=emotional_residue if emotional_residue != "none" else "neutral",
            safe_summary=summary,
            confidence=confidence,
            risk_flags=risk_flags[:4],
        )


def extract_dream_signal(
    message: str,
    analysis: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> DreamSignal:
    return DreamLayerEngine().extract_dream_signal(message, analysis, profile, session)
