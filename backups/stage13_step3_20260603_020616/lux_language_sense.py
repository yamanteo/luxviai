from __future__ import annotations

import re
import unicodedata
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


_TR_ASCII_TABLE = str.maketrans({
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
})


def _clean_text(value: Any, limit: int = 600) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _fold(value: Any) -> str:
    text = _clean_text(value).translate(_TR_ASCII_TABLE).lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _tokens(value: Any) -> list[str]:
    return re.findall(r"[^\W_]+", _fold(value), flags=re.UNICODE)


def _contains_any_folded(folded: str, needles: tuple[str, ...]) -> bool:
    return any(n in folded for n in needles)


def _script_counts(text: str) -> dict[str, int]:
    counts = {
        "latin": 0,
        "arabic": 0,
        "cyrillic": 0,
        "cjk": 0,
        "kana": 0,
        "devanagari": 0,
        "other_letter": 0,
    }
    for ch in text:
        if not ch.isalpha():
            continue
        code = ord(ch)
        if "A" <= ch <= "Z" or "a" <= ch <= "z" or ch in "ÇĞİÖŞÜçğıöşü":
            counts["latin"] += 1
        elif 0x0600 <= code <= 0x06FF:
            counts["arabic"] += 1
        elif 0x0400 <= code <= 0x04FF:
            counts["cyrillic"] += 1
        elif 0x4E00 <= code <= 0x9FFF:
            counts["cjk"] += 1
        elif 0x3040 <= code <= 0x30FF:
            counts["kana"] += 1
        elif 0x0900 <= code <= 0x097F:
            counts["devanagari"] += 1
        else:
            counts["other_letter"] += 1
    return counts


def _nonzero_scripts(counts: dict[str, int]) -> list[str]:
    return [k for k, v in counts.items() if v > 0]


def _language_context(text: str, folded: str) -> tuple[str, str, str, str, float]:
    counts = _script_counts(text)
    scripts = _nonzero_scripts(counts)
    if not text:
        return "unknown", "unknown", "unknown", "none", 0.0
    if len(scripts) > 1:
        dominant = max(counts, key=lambda k: counts[k])
        dom = {
            "arabic": "ar",
            "cyrillic": "cyrillic_script",
            "cjk": "cjk_script",
            "kana": "kana_script",
            "devanagari": "devanagari_script",
            "latin": "latin_mixed",
        }.get(dominant, "unknown")
        return "mixed", dom, "script_mixed", "medium", 0.62

    tr_hits = sum(1 for n in (" ve ", " bir ", " bu ", " icin ", " degil", "misin", "miyim", " cok ", " artik", " is ") if n in f" {folded} ")
    en_hits = sum(1 for n in (" the ", " and ", " for ", " are ", "how ", "what ", "great", "again", "explain", "technical") if n in f" {folded} ")
    if counts["arabic"] > 0:
        return "single_language", "ar", "none", "none", 0.72
    if counts["cyrillic"] > 0:
        return "single_language", "cyrillic_script", "none", "none", 0.64
    if counts["cjk"] > 0 or counts["kana"] > 0:
        return "single_language", "cjk_or_kana_script", "none", "none", 0.64
    if counts["devanagari"] > 0:
        return "single_language", "devanagari_script", "none", "none", 0.64
    if tr_hits and en_hits:
        return "code_switching", "mixed_latin", "code_switching", "low", 0.78
    if en_hits > tr_hits:
        return "single_language", "en", "none", "none", 0.7
    if tr_hits > en_hits or any(ch in text for ch in "çğıöşüÇĞİÖŞÜ"):
        return "single_language", "tr", "none", "none", 0.72
    if counts["latin"] > 0:
        return "single_language", "latin_unknown", "none", "none", 0.44
    return "unknown", "unknown", "unknown", "none", 0.2


def _signal(value: bool, high: bool = False) -> str:
    if high:
        return "high"
    return "medium" if value else "none"


def _identity_inference_requested(folded: str) -> bool:
    identity_terms = (
        "dinimi",
        "dinim",
        "milliyetimi",
        "irkimi",
        "kimligimi",
        "siyasi gorusumu",
        "sinifimi",
        "kastimi",
        "bolgemi",
        "nereli oldugumu",
    )
    request_terms = ("tahmin", "cikar", "anla", "soyle", "bil")
    return _contains_any_folded(folded, identity_terms) and _contains_any_folded(folded, request_terms)


def _is_low_confidence_bundle(bundle: "LuxLanguageSenseBundle") -> bool:
    return _clamp(bundle.confidence) < 0.25


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


def extract_language_nuance_signal(message: Any, *, context: dict[str, Any] | None = None) -> LanguageNuanceSignal:
    _ = context
    text = _clean_text(message)
    if not text:
        return LanguageNuanceSignal.neutral()
    folded = _fold(text)
    language_context, dominant_language, mixed_language_state, transliteration_signal, lang_conf = _language_context(text, folded)

    slang_hit = _contains_any_folded(
        f" {folded} ",
        (" valla ", " vallahi ", " ya ", " abi ", " kanka ", " yav ", " iste ", " be "),
    )
    dialect_hit = _contains_any_folded(
        f" {folded} ",
        (" gelmiyom", " gidiyom", " bilmiyom", " napcam", " napcan", " noluyo", " diyom", " yapcam"),
    )
    idiom_high = _contains_any_folded(
        folded,
        (
            "tadim kacti",
            "sarpa sardi",
            "raydan cikti",
            "isler karisti",
            "icine dogdu",
            "kafam kazan",
            "su akar yolunu bulur",
        ),
    )
    idiom_low = _contains_any_folded(
        folded,
        ("elim kolum bagli", "canim sikildi", "ici disi", "havada kaldi", "yoluna girdi"),
    )
    positive_markers = ("harika", "super", "mukemmel", "sahane", "great", "perfect", "wonderful", "excellent")
    negative_markers = ("bozuldu", "kotu", "berbat", "yine", "again", "broke", "failed", "rezalet", "mahvoldu")
    irony_hit = _contains_any_folded(folded, positive_markers) and _contains_any_folded(folded, negative_markers)
    humor_hit = _contains_any_folded(folded, ("haha", "ahah", "lol", "komik", ":)", ":d"))
    poetic_hits = sum(1 for n in ("gibi", "icimde", "ruhum", "golge", "isik", "gece", "deniz", "rüzgar", "ruzgar") if n in folded)

    confidence = max(lang_conf, 0.0)
    for bump in (slang_hit, dialect_hit, idiom_high, idiom_low, irony_hit, humor_hit, poetic_hits >= 2):
        if bump:
            confidence += 0.08
    return LanguageNuanceSignal(
        language_context=language_context,
        dominant_language=dominant_language,
        mixed_language_state=mixed_language_state,
        slang_signal=_signal(slang_hit),
        idiom_signal="high" if idiom_high else _signal(idiom_low),
        irony_signal=_signal(irony_hit),
        humor_signal=_signal(humor_hit),
        poetic_density="medium" if poetic_hits >= 2 else ("low" if poetic_hits == 1 else "none"),
        dialect_register_signal=_signal(dialect_hit),
        transliteration_signal=transliteration_signal,
        confidence=_clamp(confidence),
        risk_flags=["identity_inference_blocked"] if _identity_inference_requested(folded) else [],
        safe_summary="language_nuance_bucket_signal",
    )


def extract_intent_repair_signal(message: Any, *, context: dict[str, Any] | None = None) -> IntentRepairSignal:
    _ = context
    text = _clean_text(message)
    if not text:
        return IntentRepairSignal.neutral()
    folded = _fold(text)
    toks = _tokens(text)
    typo_markers = {"bne", "yalnzim", "yalnizim", "yalnz", "yanliz", "calismiyo", "gelmiyo", "olmuyo"}
    typo_hit = any(tok in typo_markers for tok in toks)
    compact_typo_hit = _contains_any_folded(folded, ("bne yalnz", "bne yaln", "calismiyo", "gelmiyo", "olmuyo"))
    typo_signal = typo_hit or compact_typo_hit
    incomplete = bool(re.search(r"( ama| fakat| yani| cunku| çünkü|\.\.\.)\s*$", text.strip(), flags=re.IGNORECASE))
    short_ambiguous = len(toks) <= 3 and ("?" not in text) and not typo_signal
    identity_block = _identity_inference_requested(folded)
    ambiguity = "high" if identity_block else ("medium" if typo_signal or incomplete else ("low" if short_ambiguous else "none"))
    intent_repair = "medium" if typo_signal or incomplete or identity_block else ("low" if short_ambiguous else "none")
    confidence = 0.68 if typo_signal else (0.6 if incomplete or identity_block else (0.38 if short_ambiguous else 0.2))
    return IntentRepairSignal(
        typo_repair_signal=_signal(typo_signal),
        ambiguity_level=ambiguity,
        intent_repair_needed=intent_repair,
        incomplete_sentence_signal=_signal(incomplete),
        literal_vs_figurative="ambiguous" if typo_signal or incomplete else "unknown",
        confidence=confidence,
        risk_flags=["identity_inference_blocked"] if identity_block else [],
        safe_summary="intent_repair_bucket_signal" if intent_repair != "none" else "intent_repair_neutral",
    )


def extract_multilingual_reference_signal(
    message: Any,
    *,
    context: dict[str, Any] | None = None,
) -> MultilingualReferenceSignal:
    _ = context
    text = _clean_text(message)
    if not text:
        return MultilingualReferenceSignal.neutral()
    folded = _fold(text)
    cultural_hit = _contains_any_folded(
        folded,
        (
            "hababam sinifi",
            "nasreddin",
            "don kisot",
            "don quixote",
            "shakespeare",
            "star wars",
            "matrix",
            "alice harikalar",
        ),
    )
    named_reference = cultural_hit or bool(re.search(r"\b[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü]+)+", text))
    local_reference = _contains_any_folded(folded, ("kafe", "sokak", "mahalle", "cadde", "meydan"))
    identity_block = _identity_inference_requested(folded)
    confidence = 0.78 if cultural_hit else (0.48 if named_reference or local_reference else 0.2)
    return MultilingualReferenceSignal(
        cultural_reference_signal=_signal(cultural_hit, high=cultural_hit),
        local_reference_signal=_signal(local_reference),
        named_reference_signal=_signal(named_reference),
        reference_clarity="medium" if cultural_hit or named_reference else ("low" if local_reference else "unknown"),
        identity_inference_guard=True,
        confidence=confidence,
        risk_flags=["identity_inference_blocked"] if identity_block else [],
        safe_summary="multilingual_reference_bucket_signal" if cultural_hit or named_reference or identity_block else "multilingual_reference_neutral",
    )


def build_lux_language_sense_bundle(
    message: Any,
    *,
    context: dict[str, Any] | None = None,
) -> LuxLanguageSenseBundle:
    try:
        language = extract_language_nuance_signal(message, context=context)
        repair = extract_intent_repair_signal(message, context=context)
        reference = extract_multilingual_reference_signal(message, context=context)
        conf = max(
            _clamp(language.confidence),
            _clamp(repair.confidence),
            _clamp(reference.confidence),
        )
        risk_flags = _flags([*language.risk_flags, *repair.risk_flags, *reference.risk_flags])
        bundle = LuxLanguageSenseBundle(
            language_nuance=language,
            intent_repair=repair,
            multilingual_reference=reference,
            confidence=conf,
            active=False,
            risk_flags=risk_flags,
            safe_summary="lux_language_sense_read_only_bucket_signal" if conf >= 0.25 else "lux_language_sense_low_confidence_neutral",
            version="13_step2_read_only",
        )
        if _is_low_confidence_bundle(bundle):
            bundle.safe_summary = "lux_language_sense_low_confidence_neutral"
        return bundle
    except Exception:
        return LuxLanguageSenseBundle.neutral()


def neutral_lux_language_sense_bundle() -> LuxLanguageSenseBundle:
    return LuxLanguageSenseBundle.neutral()
