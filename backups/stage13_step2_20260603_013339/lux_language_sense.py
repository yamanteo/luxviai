from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _clamp(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except Exception:
        number = default
    return max(0.0, min(1.0, number))


def _text(value: Any, default: str = "unknown", limit: int = 80) -> str:
    out = str(value or "").strip().lower()
    if not value:
        return default
    allowed = []
    for ch in value:
        if ch.isalnum() or ch in {"_", "-", "."}:
            allowed.append(ch.lower())
        if len(allowed) >= limit:
            break
    return "".join(allowed) or default


def _bucket(value: Any, allowed: set[str], default: str) -> str:
    candidate = _text(value, default=default, limit=48)
    return candidate if candidate in allowed else default


def _flags(values: Any, limit: int = 8) -> list[str]:
    out: list[str] = []
    if isinstance(values, (list, tuple, set)):
        source = values
    else:
        source = [values] if values else []
    for item in source:
        flag = _text(item, default="", limit=40)
        if flag and flag not in out:
            out.append(flag)
        if len(out) >= limit:
            break
    return out


SIGNAL_BUCKETS = {"none", "low", "medium", "high", "unknown"}
LANGUAGE_CONTEXT_BUCKETS = {
    "unknown",
    "single_language",
    "mixed",
    "code_switching",
    "transliteration",
    "ambiguous",
}
MIXED_LANGUAGE_BUCKETS = {
    "unknown",
    "none",
    "code_switching",
    "dominant_language_clear",
    "dominant_language_unclear",
    "script_mixed",
}
AMBIGUITY_BUCKETS = {"none", "low", "medium", "high", "unknown"}
LITERAL_FIGURATIVE_BUCKETS = {"unknown", "literal", "figurative", "mixed", "ambiguous"}


@dataclass(slots=True)
class LanguageNuanceSignal:
    language_context: str = "unknown"
    dominant_language: str = "unknown"
    mixed_language_state: str = "unknown"
    slang_signal: str = "none"
    idiom_signal: str = "none"
    irony_signal: str = "none"
    humor_signal: str = "none"
    poetic_density: str = "none"
    dialect_register_signal: str = "none"
    transliteration_signal: str = "none"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    safe_summary: str = "language_nuance_neutral"

    @classmethod
    def neutral(cls) -> "LanguageNuanceSignal":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "language_context": _bucket(self.language_context, LANGUAGE_CONTEXT_BUCKETS, "unknown"),
            "dominant_language": _text(self.dominant_language, default="unknown", limit=24),
            "mixed_language_state": _bucket(self.mixed_language_state, MIXED_LANGUAGE_BUCKETS, "unknown"),
            "slang_signal": _bucket(self.slang_signal, SIGNAL_BUCKETS, "none"),
            "idiom_signal": _bucket(self.idiom_signal, SIGNAL_BUCKETS, "none"),
            "irony_signal": _bucket(self.irony_signal, SIGNAL_BUCKETS, "none"),
            "humor_signal": _bucket(self.humor_signal, SIGNAL_BUCKETS, "none"),
            "poetic_density": _bucket(self.poetic_density, SIGNAL_BUCKETS, "none"),
            "dialect_register_signal": _bucket(self.dialect_register_signal, SIGNAL_BUCKETS, "none"),
            "transliteration_signal": _bucket(self.transliteration_signal, SIGNAL_BUCKETS, "none"),
            "confidence": round(_clamp(self.confidence), 4),
            "risk_flags": _flags(self.risk_flags),
            "safe_summary": _text(self.safe_summary, default="language_nuance_neutral", limit=60),
        }


@dataclass(slots=True)
class IntentRepairSignal:
    typo_repair_signal: str = "none"
    ambiguity_level: str = "unknown"
    intent_repair_needed: str = "none"
    incomplete_sentence_signal: str = "none"
    literal_vs_figurative: str = "unknown"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    safe_summary: str = "intent_repair_neutral"

    @classmethod
    def neutral(cls) -> "IntentRepairSignal":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "typo_repair_signal": _bucket(self.typo_repair_signal, SIGNAL_BUCKETS, "none"),
            "ambiguity_level": _bucket(self.ambiguity_level, AMBIGUITY_BUCKETS, "unknown"),
            "intent_repair_needed": _bucket(self.intent_repair_needed, SIGNAL_BUCKETS, "none"),
            "incomplete_sentence_signal": _bucket(self.incomplete_sentence_signal, SIGNAL_BUCKETS, "none"),
            "literal_vs_figurative": _bucket(self.literal_vs_figurative, LITERAL_FIGURATIVE_BUCKETS, "unknown"),
            "confidence": round(_clamp(self.confidence), 4),
            "risk_flags": _flags(self.risk_flags),
            "safe_summary": _text(self.safe_summary, default="intent_repair_neutral", limit=60),
        }


@dataclass(slots=True)
class MultilingualReferenceSignal:
    cultural_reference_signal: str = "none"
    local_reference_signal: str = "none"
    named_reference_signal: str = "none"
    reference_clarity: str = "unknown"
    identity_inference_guard: bool = True
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    safe_summary: str = "multilingual_reference_neutral"

    @classmethod
    def neutral(cls) -> "MultilingualReferenceSignal":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "cultural_reference_signal": _bucket(self.cultural_reference_signal, SIGNAL_BUCKETS, "none"),
            "local_reference_signal": _bucket(self.local_reference_signal, SIGNAL_BUCKETS, "none"),
            "named_reference_signal": _bucket(self.named_reference_signal, SIGNAL_BUCKETS, "none"),
            "reference_clarity": _bucket(self.reference_clarity, AMBIGUITY_BUCKETS, "unknown"),
            "identity_inference_guard": bool(self.identity_inference_guard),
            "confidence": round(_clamp(self.confidence), 4),
            "risk_flags": _flags(self.risk_flags),
            "safe_summary": _text(self.safe_summary, default="multilingual_reference_neutral", limit=60),
        }


@dataclass(slots=True)
class LuxLanguageSenseBundle:
    language_nuance: LanguageNuanceSignal = field(default_factory=LanguageNuanceSignal.neutral)
    intent_repair: IntentRepairSignal = field(default_factory=IntentRepairSignal.neutral)
    multilingual_reference: MultilingualReferenceSignal = field(default_factory=MultilingualReferenceSignal.neutral)
    confidence: float = 0.0
    active: bool = False
    risk_flags: list[str] = field(default_factory=list)
    safe_summary: str = "lux_language_sense_neutral_stub"
    version: str = "13_step0_schema"

    @classmethod
    def neutral(cls) -> "LuxLanguageSenseBundle":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "language_nuance": self.language_nuance.to_safe_dict(),
            "intent_repair": self.intent_repair.to_safe_dict(),
            "multilingual_reference": self.multilingual_reference.to_safe_dict(),
            "confidence": round(_clamp(self.confidence), 4),
            "active": bool(self.active),
            "risk_flags": _flags(self.risk_flags),
            "safe_summary": _text(self.safe_summary, default="lux_language_sense_neutral_stub", limit=80),
            "version": _text(self.version, default="13_step0_schema", limit=40),
        }


def neutral_lux_language_sense_bundle() -> LuxLanguageSenseBundle:
    return LuxLanguageSenseBundle.neutral()
