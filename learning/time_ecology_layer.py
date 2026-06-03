from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .group4_signals import TimeEcologySignal


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _lc(value: Any) -> str:
    return _norm(value).lower()


def _hour_to_bucket(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


def _resolve_timezone(profile: dict[str, Any] | None, session: dict[str, Any] | None) -> str:
    profile = profile or {}
    session = session or {}
    for src in (
        session.get("timezone"),
        session.get("tz"),
        profile.get("timezone"),
        profile.get("tz"),
        (profile.get("settings", {}) if isinstance(profile.get("settings"), dict) else {}).get("timezone"),
    ):
        tz = _norm(src)
        if tz:
            return tz
    return ""


def _time_of_day_bucket(profile: dict[str, Any] | None, session: dict[str, Any] | None) -> tuple[str, bool]:
    tz_name = _resolve_timezone(profile, session)
    if not tz_name:
        return "unknown", False
    try:
        now_in_tz = datetime.now(ZoneInfo(tz_name))
        return _hour_to_bucket(int(now_in_tz.hour)), True
    except Exception:
        return "unknown", False


def _detect_urgency_bucket(message: str) -> str:
    low = _lc(message)
    high_terms = (
        "acil",
        "hemen",
        "şimdi",
        "simdi",
        "hızlıca",
        "hizlica",
        "hÄ±zlÄ±ca",
        "quickly",
        "urgent",
        "asap",
        "right now",
    )
    medium_terms = (
        "kısa",
        "kisa",
        "kÄ±sa",
        "özet",
        "ozet",
        "Ã¶zet",
        "tek adım",
        "tek adim",
        "tek adÄ±m",
        "bir sonraki adım",
        "bir sonraki adim",
        "bir sonraki adÄ±m",
        "one step",
        "next step",
        "brief",
        "short",
    )
    low_terms = ("müsait olunca", "musait olunca", "mÃ¼sait olunca", "sonra", "later")

    if any(t in low for t in high_terms):
        return "high"
    if any(t in low for t in medium_terms):
        return "medium"
    if any(t in low for t in low_terms):
        return "low"
    return "none"


def _detect_fatigue_bucket(message: str, time_of_day: str) -> str:
    low = _lc(message)
    high_terms = (
        "çok yorgunum",
        "cok yorgunum",
        "Ã§ok yorgunum",
        "uykusuzum",
        "bitkinim",
        "tükendim",
        "tukendim",
        "tÃ¼kendim",
        "exhausted",
        "burned out",
    )
    explicit_terms = (
        "yorgunum",
        "yoruldum",
        "uykusuz",
        "fatigue",
        "tired",
        "sleepy",
    )
    late_context_terms = (
        "gece geç",
        "gece gec",
        "gece geÃ§",
        "bu saatte",
        "late night",
        "very late",
    )

    if any(t in low for t in high_terms):
        return "high"
    if any(t in low for t in explicit_terms):
        return "explicit"
    # Only "possible" when late context is explicitly present in this turn.
    if any(t in low for t in late_context_terms) and (time_of_day == "night" or "gece" in low or "late" in low):
        return "possible"
    return "none"


def _extract_recent_user_texts(session: dict[str, Any] | None, message: str) -> list[str]:
    texts: list[str] = []
    session = session or {}
    msgs = session.get("messages")
    if isinstance(msgs, list):
        for row in msgs[-8:]:
            if not isinstance(row, dict):
                continue
            if _lc(row.get("role")) != "user":
                continue
            content = _norm(row.get("content"))
            if content:
                texts.append(content)
    current = _norm(message)
    if current:
        texts.append(current)
    return texts[-8:]


def _detect_rhythm_bucket(message: str, session: dict[str, Any] | None, urgency: str) -> str:
    texts = _extract_recent_user_texts(session, message)
    if len(texts) <= 1:
        low = _lc(message)
        if urgency in {"medium", "high"} and len(low.split()) <= 10:
            return "rushed"
        if "..." in low or "???" in low or "!!!" in low:
            return "disrupted"
        return "unknown"

    low_texts = [_lc(t) for t in texts]
    current = low_texts[-1]
    duplicates = sum(1 for t in low_texts[:-1] if t == current and t)
    if duplicates >= 1:
        return "repetitive"

    abrupt_marks = sum(1 for t in low_texts[-3:] if ("..." in t or "???" in t or "!!!" in t))
    if abrupt_marks >= 2:
        return "disrupted"

    short_count = sum(1 for t in low_texts[-4:] if len(t.split()) <= 5)
    if urgency in {"medium", "high"} and short_count >= 3:
        return "rushed"

    return "calm"


def _has_safety_flag(analysis: dict[str, Any] | None) -> bool:
    a = analysis or {}
    if bool(a.get("crisis_risk")):
        return True
    safety = a.get("safety_layer", {})
    if isinstance(safety, dict):
        crisis_context = _lc(safety.get("crisis_context"))
        if crisis_context and crisis_context != "none":
            return True
    return False


def _confidence(
    *,
    time_of_day: str,
    urgency: str,
    fatigue: str,
    rhythm: str,
    timezone_known: bool,
    safety_flag: bool,
) -> float:
    if safety_flag:
        return 0.0
    score = 0.42
    if urgency != "none":
        score += 0.16
    if fatigue != "none":
        score += 0.16
    if rhythm != "unknown":
        score += 0.12
    if time_of_day != "unknown" and timezone_known:
        score += 0.08
    if fatigue in {"explicit", "high"}:
        score += 0.06
    return max(0.0, min(0.92, score))


@dataclass(slots=True)
class TimeEcologyLayerEngine:
    def extract_time_ecology_signal(
        self,
        message: str,
        analysis: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
    ) -> TimeEcologySignal:
        time_of_day, timezone_known = _time_of_day_bucket(profile, session)
        urgency = _detect_urgency_bucket(message)
        fatigue = _detect_fatigue_bucket(message, time_of_day)
        rhythm = _detect_rhythm_bucket(message, session, urgency)
        safety_flag = _has_safety_flag(analysis)

        conf = _confidence(
            time_of_day=time_of_day,
            urgency=urgency,
            fatigue=fatigue,
            rhythm=rhythm,
            timezone_known=timezone_known,
            safety_flag=safety_flag,
        )

        risk_flags: list[str] = []
        if not timezone_known:
            risk_flags.append("timezone_unknown")
        if safety_flag:
            risk_flags.append("safety_sensitive")
        if conf < 0.6:
            risk_flags.append("low_confidence")

        if conf < 0.6:
            safe_summary = "time_ecology_low_confidence_neutral"
        elif urgency in {"medium", "high"} or fatigue in {"explicit", "high"}:
            safe_summary = "time_ecology_tighten_hint_candidate"
        else:
            safe_summary = "time_ecology_soft_neutral"

        return TimeEcologySignal(
            time_of_day_bucket=time_of_day,
            rhythm_bucket=rhythm,
            fatigue_context_bucket=fatigue,
            urgency_bucket=urgency,
            safe_summary=safe_summary,
            confidence=conf,
            risk_flags=risk_flags,
        )


def extract_time_ecology_signal(
    message: str,
    analysis: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> TimeEcologySignal:
    return TimeEcologyLayerEngine().extract_time_ecology_signal(message, analysis, profile, session)
