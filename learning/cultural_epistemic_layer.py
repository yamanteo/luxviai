from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .group4_signals import CulturalEpistemicSignal, clamp


LATIN_LANGUAGE_MARKERS: dict[str, tuple[str, ...]] = {
    "tr": (
        " bunu ",
        " bana ",
        " misin ",
        " anlat",
        " hata ",
        " var ",
        " calis",
        " ruyamda",
        " sade",
        " kisa",
        " adim",
        " lutfen",
        " icin ",
        " degil",
        "\u00e7",
        "\u011f",
        "\u0131",
        "\u00f6",
        "\u015f",
        "\u00fc",
    ),
    "en": (
        " please ",
        " could ",
        " would ",
        " explain",
        " this ",
        " how ",
        " what ",
        " professional",
        " concise",
        " technical",
        " step by step",
    ),
    "es": (" por favor", " explica", " explicar", " esto ", " una ", " que ", " para ", " como ", "\u00bf", "\u00f1"),
    "fr": (" s'il ", " veuillez", " explique", " ceci ", " pour ", " avec ", " vous ", " je ", "\u00e9", "\u00e0"),
    "de": (" bitte", " erkl\u00e4r", " dies", " und ", " der ", " die ", " das ", "\u00df", "\u00e4", "\u00f6", "\u00fc"),
    "pt": (" por favor", " explique", " isto ", " voc\u00ea", " para ", " como ", " obrigado", "\u00e3", "\u00e7\u00e3o"),
}

FORMAL_MARKERS = (
    "please",
    "could you",
    "would you",
    "professional",
    "l\u00fctfen",
    "lutfen",
    "rica",
    "por favor",
    "bitte",
    "veuillez",
    "s'il vous",
    "\u0645\u0646 \u0641\u0636\u0644\u0643",
    "\u4e01\u5be7",
    "\u304f\u3060\u3055\u3044",
)
CASUAL_MARKERS = (" kanka", " abi", " ya ", " pls", " bro", " selam", " hey")
DIRECT_MARKERS = (
    "sadece",
    "hemen",
    "direkt",
    "net",
    "k\u0131sa",
    "kisa",
    "sade",
    "just ",
    "only ",
    "direct",
    "short",
    "brief",
)
EXPLORATORY_MARKERS = ("sence", "belki", "yorum", "ne d\u00fc\u015f\u00fcn", "maybe", "perhaps", "what do you think")
CONCISE_MARKERS = ("k\u0131sa", "kisa", "sade", "brief", "concise", "kurz", "court", "corto", "curto", "\u77ed\u304f")
STEP_MARKERS = ("ad\u0131m ad\u0131m", "adim adim", "tek ad\u0131m", "tek adim", "step by step", "paso a paso", "schritt")
EXAMPLE_MARKERS = ("\u00f6rnek", "ornek", "example", "ejemplo", "exemple", "beispiel", "exemplo")
PRINCIPLE_MARKERS = ("neden", "mant\u0131k", "mantik", "principle", "logic", "why", "pourquoi", "warum", "por que")
IDENTITY_TERMS = (
    "k\u00fclt\u00fcr",
    "kultur",
    "din",
    "dini",
    "etnik",
    "milliyet",
    "nationality",
    "ethnicity",
    "religion",
    "political",
    "siyasi",
    "worldview",
    "class",
    "caste",
    "kimlik",
)
INFERENCE_TERMS = ("tahmin", "anlar", "infer", "guess", "\u00e7\u0131kar", "cikar", "belli olur", "understand from")
UTILITY_TERMS = (
    "kod",
    "debug",
    "deploy",
    "dashboard",
    "endpoint",
    "terminal",
    "port",
    "websocket",
    "dosya",
    "ayar",
    "config",
    "api",
    "build",
    "hata",
    "error",
    "python",
    "html",
    "css",
    "javascript",
)
IDIOM_MARKERS = ("kafam kar\u0131\u015ft\u0131", "kafam karisti", "i\u00e7ime sin", "icime sin", "on my mind")


def _lc(value: Any) -> str:
    return str(value or "").strip().lower()


def _wrapped_low(text: str) -> str:
    return f" {_lc(text)} "


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    low = _lc(text)
    wrapped = f" {low} "
    return any(marker in low or marker in wrapped for marker in markers)


def _script_counts(text: str) -> dict[str, int]:
    counts = {"latin": 0, "arabic": 0, "cyrillic": 0, "cjk": 0, "kana": 0}
    for ch in str(text or ""):
        code = ord(ch)
        if ("a" <= ch.lower() <= "z") or (0x00C0 <= code <= 0x024F):
            counts["latin"] += 1
        elif 0x0600 <= code <= 0x06FF:
            counts["arabic"] += 1
        elif 0x0400 <= code <= 0x04FF:
            counts["cyrillic"] += 1
        elif 0x4E00 <= code <= 0x9FFF:
            counts["cjk"] += 1
        elif 0x3040 <= code <= 0x30FF:
            counts["kana"] += 1
    return counts


def _latin_scores(text: str) -> dict[str, int]:
    wrapped = _wrapped_low(text)
    scores: dict[str, int] = {}
    for lang, markers in LATIN_LANGUAGE_MARKERS.items():
        scores[lang] = sum(1 for marker in markers if marker in wrapped or marker in _lc(text))
    return scores


def _language_context(text: str) -> tuple[str, str, float]:
    if not str(text or "").strip():
        return "unknown", "unknown", 0.0
    counts = _script_counts(text)
    active_scripts = [name for name, count in counts.items() if count > 0]
    non_latin_scripts = [s for s in active_scripts if s != "latin"]
    script_total = sum(counts.values()) or 1

    if counts.get("latin", 0) == 0 and counts.get("kana", 0) > 0:
        return "ja", "none", 0.86
    if counts.get("latin", 0) == 0 and counts.get("cjk", 0) > 0:
        return "zh", "none", 0.76

    if len(non_latin_scripts) == 1 and counts.get("latin", 0) == 0:
        script = non_latin_scripts[0]
        if script == "arabic":
            return "ar", "none", 0.84
        if script == "cyrillic":
            return "ru", "none", 0.78
        if script == "kana":
            return "ja", "none", 0.86
        if script == "cjk":
            return "zh", "none", 0.76

    if non_latin_scripts and counts.get("latin", 0) > 0:
        dominant = max(counts, key=lambda k: counts[k])
        mixed_state = "dominant_language_clear" if counts[dominant] / script_total >= 0.65 else "dominant_language_unclear"
        if mixed_state == "dominant_language_clear":
            if dominant == "arabic":
                return "ar", mixed_state, 0.72
            if dominant == "cyrillic":
                return "ru", mixed_state, 0.68
            if dominant == "kana":
                return "ja", mixed_state, 0.72
            if dominant == "cjk":
                return "zh", mixed_state, 0.68
        return "mixed", "code_switching", 0.64

    if counts.get("latin", 0) > 0:
        scores = _latin_scores(text)
        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        top_lang, top_score = sorted_scores[0]
        second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0
        language_hits = [lang for lang, score in scores.items() if score > 0]
        if len(language_hits) >= 2 and second_score >= 2:
            if top_score >= second_score + 3:
                return top_lang, "dominant_language_clear", 0.68
            return "mixed", "code_switching", 0.66
        if top_score >= 2:
            return top_lang, "none", 0.70
        if top_score == 1:
            return top_lang, "dominant_language_unclear", 0.54
    return "unknown", "unknown", 0.25


def _register_formality(text: str) -> str:
    if _contains_any(text, FORMAL_MARKERS):
        return "formal"
    if _contains_any(text, CASUAL_MARKERS):
        return "casual"
    return "neutral"


def _directness_style(text: str) -> str:
    if _contains_any(text, EXPLORATORY_MARKERS):
        return "exploratory"
    if _contains_any(text, FORMAL_MARKERS):
        return "softened"
    if _contains_any(text, DIRECT_MARKERS):
        return "direct"
    return "unknown"


def _politeness_style(text: str, formality: str) -> str:
    if formality == "formal":
        return "formal_address"
    if formality == "casual":
        return "casual_address"
    return "neutral"


def _idiom_preference(text: str) -> str:
    if _contains_any(text, UTILITY_TERMS) or _contains_any(text, ("literal", "plain", "sade", "net", "teknik")):
        return "avoid_idiom"
    if _contains_any(text, IDIOM_MARKERS):
        return "light_idiom"
    if _contains_any(text, DIRECT_MARKERS):
        return "literal_plain"
    return "unknown"


def _explanation_style(text: str) -> str:
    if _contains_any(text, STEP_MARKERS):
        return "step_by_step"
    if _contains_any(text, EXAMPLE_MARKERS):
        return "example_led"
    if _contains_any(text, PRINCIPLE_MARKERS):
        return "principle_led"
    if _contains_any(text, CONCISE_MARKERS):
        return "concise"
    return "neutral"


def _identity_inference_requested(text: str) -> bool:
    low = _lc(text)
    if not any(term in low for term in IDENTITY_TERMS):
        return False
    return any(term in low for term in INFERENCE_TERMS)


def _confidence(
    *,
    language_confidence: float,
    formality: str,
    directness: str,
    idiom: str,
    explanation: str,
    identity_guard: bool,
) -> float:
    if identity_guard:
        return 0.82
    score = language_confidence
    if formality in {"formal", "casual"}:
        score += 0.08
    if directness in {"direct", "softened", "exploratory"}:
        score += 0.08
    if idiom in {"literal_plain", "light_idiom", "avoid_idiom"}:
        score += 0.05
    if explanation in {"concise", "example_led", "principle_led", "step_by_step"}:
        score += 0.09
    return round(clamp(score), 4)


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
        text = str(message or "")
        language_context, mixed_state, language_confidence = _language_context(text)
        formality = _register_formality(text)
        directness = _directness_style(text)
        politeness = _politeness_style(text, formality)
        idiom = _idiom_preference(text)
        explanation = _explanation_style(text)
        identity_guard = _identity_inference_requested(text)
        utility_turn = _contains_any(text, UTILITY_TERMS)

        risk_flags: list[str] = []
        if identity_guard:
            risk_flags.append("identity_inference_request")
        if utility_turn:
            risk_flags.append("utility_turn")

        confidence = _confidence(
            language_confidence=language_confidence,
            formality=formality,
            directness=directness,
            idiom=idiom,
            explanation=explanation,
            identity_guard=identity_guard,
        )
        if confidence < 0.6 and not identity_guard:
            safe_summary = "low_confidence_register_neutral"
        elif identity_guard:
            safe_summary = "identity_inference_blocked_language_not_identity"
        elif utility_turn:
            safe_summary = "utility_register_minimal"
        else:
            safe_summary = "language_register_fit_signal"

        epistemic_style = "balanced"
        certainty_pref = "balanced"
        low = _lc(text)
        if any(x in low for x in ("emin misin", "kesin", "dogru mu", "do\u011fru mu", "sure?", "are you sure")):
            epistemic_style = "verification_first"
            certainty_pref = "high"
        elif directness == "exploratory":
            epistemic_style = "exploratory"
            certainty_pref = "low"

        return CulturalEpistemicSignal(
            language_context=language_context,
            register_formality=formality if confidence >= 0.6 or identity_guard else "unknown",
            directness_style=directness if confidence >= 0.6 or identity_guard else "unknown",
            politeness_style=politeness if confidence >= 0.6 or identity_guard else "unknown",
            idiom_preference=idiom if confidence >= 0.6 or identity_guard else "unknown",
            explanation_style=explanation if confidence >= 0.6 or identity_guard else "unknown",
            mixed_language_state=mixed_state,
            cultural_sensitivity_bucket="neutral",
            epistemic_style_bucket=epistemic_style,
            certainty_preference_bucket=certainty_pref,
            safe_summary=safe_summary,
            confidence=confidence,
            risk_flags=risk_flags,
        )


def extract_cultural_epistemic_signal(
    message: str,
    analysis: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> CulturalEpistemicSignal:
    return CulturalEpistemicLayerEngine().extract_cultural_epistemic_signal(message, analysis, profile, session)
