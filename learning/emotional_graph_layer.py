from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .group4_signals import EmotionalGraphSignal, clamp


EMOTION_MARKERS: dict[str, tuple[str, ...]] = {
    "fatigue": ("yorgun", "tukend", "t\u00fckend", "exhausted", "tired", "bitkin"),
    "anxiety": ("kaygi", "kayg\u0131", "endise", "endi\u015fe", "anxious", "worry", "korku", "korkuyorum"),
    "sadness": ("uzgun", "\u00fczg\u00fcn", "aglad", "a\u011flad", "agli", "a\u011fl\u0131", "sad", "mutsuz"),
    "anger": ("sinir", "ofke", "\u00f6fke", "angry", "kizgin", "k\u0131zg\u0131n", "a\u011f\u0131r konu\u015f"),
    "hope": ("umut", "hope", "hopeful", "iyi olacak"),
    "calm": ("rahat", "huzur", "sakin", "calm", "relaxed"),
    "joy": ("mutlu", "sevin", "joy", "happy", "guzel hissed"),
    "loneliness": ("yalniz", "yaln\u0131z", "lonely", "tek basima", "tek ba\u015f\u0131ma"),
}
POSITIVE_BUCKETS = {"hope", "calm", "joy"}
NEGATIVE_BUCKETS = {"fatigue", "anxiety", "sadness", "anger", "loneliness"}
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
SAFETY_TERMS = (
    "kendime zarar",
    "intihar",
    "oldurmek",
    "\u00f6ld\u00fcrmek",
    "suicide",
    "kill myself",
    "hurt myself",
    "ona zarar",
    "birine zarar",
)
HIGH_INTENSITY_TERMS = ("cok", "\u00e7ok", "asiri", "a\u015f\u0131r\u0131", "dayanam", "art\u0131k", "artik", "patlay")
RECOVERY_MARKERS: dict[str, tuple[str, ...]] = {
    "grounding": ("rahatlad", "nefes", "sakinlest", "sakinle\u015ft", "grounded"),
    "hope": ("umut", "iyi olacak", "hope"),
    "clarity": ("net", "anladim", "anlad\u0131m", "daha net", "clearer"),
    "acceptance": ("kabullen", "kabul", "tamam oldu", "oldu"),
}


def _lc(value: Any) -> str:
    return str(value or "").strip().lower()


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    low = _lc(text)
    return any(marker in low for marker in markers)


def _explicit_emotions(message: str) -> list[str]:
    low = _lc(message)
    found: list[str] = []
    for bucket, markers in EMOTION_MARKERS.items():
        if any(marker in low for marker in markers):
            found.append(bucket)
    return found


def _dominant_emotion_bucket(explicit: list[str]) -> str:
    if not explicit:
        return "neutral"
    if len(set(explicit)) >= 2:
        return "mixed"
    bucket = explicit[0]
    if bucket in POSITIVE_BUCKETS:
        return "positive"
    if bucket in NEGATIVE_BUCKETS:
        return "negative"
    return "neutral"


def _explicit_bucket(explicit: list[str]) -> str:
    if not explicit:
        return "none"
    unique = []
    for item in explicit:
        if item not in unique:
            unique.append(item)
    if len(unique) >= 2:
        return "mixed"
    return unique[0]


def _intensity_bucket(message: str, explicit: list[str]) -> str:
    if not explicit:
        return "none"
    low = _lc(message)
    score = 1
    if _contains_any(low, HIGH_INTENSITY_TERMS):
        score += 1
    if "!" in low:
        score += 1
    if len(explicit) >= 2:
        score += 1
    if score >= 3:
        return "high"
    if score == 2:
        return "medium"
    return "low"


def _mixed_affect_bucket(message: str, explicit: list[str]) -> str:
    if len(set(explicit).intersection(POSITIVE_BUCKETS)) and len(set(explicit).intersection(NEGATIVE_BUCKETS)):
        return "positive_negative_mix"
    low = _lc(message)
    if (
        ("hem " in low and ("ama" in low or "fakat" in low))
        or low.count("hem ") >= 2
        or ("bir yanim" in low and "bir yanim" in low)
    ):
        return "uncertainty_mix"
    if "rahat" in low and any(x in low for x in ("ama", "kaygi", "kork", "gergin")):
        return "calm_with_tension"
    return "none"


def _recovery_bucket(message: str) -> str:
    low = _lc(message)
    for bucket, markers in RECOVERY_MARKERS.items():
        if any(marker in low for marker in markers):
            return bucket
    return "none"


def _support_need_bucket(*, explicit: list[str], intensity: str, mixed_affect: str, recovery: str, safety: bool) -> str:
    if safety:
        return "safety"
    if not explicit and recovery == "none" and mixed_affect == "none":
        return "none"
    if intensity == "high":
        return "high"
    if intensity == "medium" or mixed_affect != "none":
        return "medium"
    return "low"


def _recent_user_messages(session: dict[str, Any] | None, limit: int = 6) -> list[str]:
    if not isinstance(session, dict):
        return []
    raw = session.get("messages") or session.get("history") or session.get("turns") or []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for row in raw[-limit:]:
        if isinstance(row, dict):
            role = _lc(row.get("role"))
            if role and role not in {"user", "human"}:
                continue
            text = row.get("content") or row.get("message") or row.get("text") or ""
        else:
            text = row
        if str(text or "").strip():
            out.append(str(text))
    return out[-limit:]


def _continuity_and_shift(current: list[str], session: dict[str, Any] | None) -> tuple[str, str]:
    if not current:
        return "none", "unknown"
    recent = _recent_user_messages(session)
    previous_buckets: list[str] = []
    for msg in recent:
        for bucket in _explicit_emotions(msg):
            if bucket not in previous_buckets:
                previous_buckets.append(bucket)
    current_primary = current[0]
    if current_primary in previous_buckets:
        return "repeated_current_session", "stable"
    if previous_buckets:
        prev_positive = any(x in POSITIVE_BUCKETS for x in previous_buckets)
        prev_negative = any(x in NEGATIVE_BUCKETS for x in previous_buckets)
        cur_positive = current_primary in POSITIVE_BUCKETS
        cur_negative = current_primary in NEGATIVE_BUCKETS
        if (prev_positive and cur_negative) or (prev_negative and cur_positive):
            return "emerging", "soft_shift"
        return "emerging", "stable"
    return "single_turn", "stable"


def _confidence(*, explicit: list[str], intensity: str, mixed_affect: str, recovery: str, support: str, safety: bool, utility: bool) -> float:
    if safety:
        return 0.72
    if utility and not explicit:
        return 0.0
    score = 0.0
    if explicit:
        score += 0.60
    if intensity in {"medium", "high"}:
        score += 0.12
    if mixed_affect != "none":
        score += 0.16
    if recovery != "none":
        score += 0.14
    if support in {"medium", "high"}:
        score += 0.08
    if utility:
        score = min(score, 0.62)
    return round(clamp(score), 4)


@dataclass(slots=True)
class EmotionalGraphLayerEngine:
    def extract_emotional_graph_signal(
        self,
        message: str,
        analysis: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
    ) -> EmotionalGraphSignal:
        _ = analysis, profile
        text = str(message or "")
        explicit = _explicit_emotions(text)
        utility = _contains_any(text, UTILITY_TERMS)
        safety = _contains_any(text, SAFETY_TERMS)
        intensity = _intensity_bucket(text, explicit)
        mixed_affect = _mixed_affect_bucket(text, explicit)
        recovery = _recovery_bucket(text)
        support = _support_need_bucket(
            explicit=explicit,
            intensity=intensity,
            mixed_affect=mixed_affect,
            recovery=recovery,
            safety=safety,
        )
        continuity, shift = _continuity_and_shift(explicit, session)
        confidence = _confidence(
            explicit=explicit,
            intensity=intensity,
            mixed_affect=mixed_affect,
            recovery=recovery,
            support=support,
            safety=safety,
            utility=utility,
        )
        risk_flags: list[str] = []
        if safety:
            risk_flags.append("safety_route_required")
        if utility:
            risk_flags.append("utility_turn")

        if safety:
            safe_summary = "safety_route_emotional_graph_neutral"
        elif confidence < 0.6:
            safe_summary = "low_confidence_emotional_cadence_neutral"
        elif utility:
            safe_summary = "utility_emotional_graph_minimal"
        else:
            safe_summary = "safe_emotional_cadence_signal"

        dominant = _dominant_emotion_bucket(explicit)
        emotion_shift = "stable"
        if shift == "soft_shift":
            emotion_shift = "shift_up" if dominant == "positive" else "shift_down"
        elif shift == "mixed":
            emotion_shift = "oscillating"

        return EmotionalGraphSignal(
            dominant_emotion_bucket=dominant,
            emotion_shift_bucket=emotion_shift,
            emotional_intensity_bucket=intensity if confidence >= 0.6 or safety else "none",
            shift_bucket=shift if confidence >= 0.6 or safety else "unknown",
            continuity_bucket=continuity if confidence >= 0.6 or safety else "none",
            mixed_affect_bucket=mixed_affect if confidence >= 0.6 or safety else "none",
            recovery_marker_bucket=recovery if confidence >= 0.6 or safety else "none",
            explicit_emotion_bucket=_explicit_bucket(explicit) if confidence >= 0.6 or safety else "none",
            support_need_bucket=support if confidence >= 0.6 or safety else "none",
            safe_summary=safe_summary,
            confidence=confidence,
            risk_flags=risk_flags,
        )


def extract_emotional_graph_signal(
    message: str,
    analysis: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> EmotionalGraphSignal:
    return EmotionalGraphLayerEngine().extract_emotional_graph_signal(message, analysis, profile, session)
