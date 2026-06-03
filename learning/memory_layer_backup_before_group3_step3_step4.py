from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .group3_signals import MemoryReadSet, MemoryWriteCandidate


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


THEME_ROOTS = (
    "kaygi",
    "kork",
    "uzgun",
    "yalniz",
    "deger",
    "is",
    "kariyer",
    "iliski",
    "guven",
    "arzu",
    "etik",
    "belirsiz",
    "kararsiz",
    "anlam",
    "amac",
)

SYMBOL_TERMS = (
    "kapi",
    "esik",
    "yol",
    "ayna",
    "oda",
    "deniz",
    "tren",
    "isik",
    "golge",
    "karanlik",
)

SOFT_EMOTION = ("huzur", "rahat", "iyi", "umut", "sakin")
HEAVY_EMOTION = ("korku", "ofke", "huzursuz", "panik", "bunaldim", "tukendim")

SENSITIVE_TERMS = (
    "intihar",
    "kendime zarar",
    "tecavuz",
    "istismar",
    "adres",
    "telefon",
    "mail",
    "@",
)


def _tokenize(text: str) -> list[str]:
    folded = _fold_tr(text)
    variants = [folded, folded.replace("?", "i"), folded.replace("?", "u")]
    token_lists = [re.findall(r"[a-z0-9_]+", v) for v in variants]
    token_lists.sort(key=len, reverse=True)
    return token_lists[0] if token_lists else []


def _theme_tokens(text: str) -> list[str]:
    out: list[str] = []
    for t in _tokenize(text):
        if any(t.startswith(root) for root in THEME_ROOTS):
            out.append(t)
    return out


def _symbol_tokens(text: str) -> list[str]:
    toks = set(_tokenize(text))
    return [t for t in SYMBOL_TERMS if t in toks]


def _to_display_theme(token: str) -> str:
    mapping = {
        "kaygi": "kaygı",
        "kork": "korku",
        "yalniz": "yalnızlık",
        "deger": "değer",
        "is": "iş",
        "kariyer": "kariyer",
        "iliski": "ilişki",
        "guven": "güven",
        "arzu": "arzu",
        "etik": "etik",
        "belirsiz": "belirsizlik",
        "kararsiz": "kararsızlık",
        "anlam": "anlam",
        "amac": "amaç",
    }
    for root, label in mapping.items():
        if token.startswith(root):
            return label
    return token[:24]


def _to_display_symbol(token: str) -> str:
    mapping = {
        "kapi": "kapı",
        "esik": "eşik",
        "yol": "yol",
        "ayna": "ayna",
        "oda": "oda",
        "deniz": "deniz",
        "tren": "tren",
        "isik": "ışık",
        "golge": "gölge",
        "karanlik": "karanlık",
    }
    return mapping.get(token, token[:24])


@dataclass(slots=True)
class MemoryLayerEngine:
    def read_memory_signals(
        self,
        message: str,
        profile: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
    ) -> MemoryReadSet:
        profile = profile or {}
        session = session or {}
        msg = str(message or "")

        anchors = 0
        if profile.get("core_trigger"):
            anchors += 1
        if profile.get("weekly_report"):
            anchors += 1
        if isinstance(profile.get("memory_garden"), list) and profile.get("memory_garden"):
            anchors += 1
        if isinstance(session.get("messages"), list) and session.get("messages"):
            anchors += 1

        theme_counts: dict[str, int] = {}
        symbol_counts: dict[str, int] = {}
        emotion_score = 0

        for user_msg in (session.get("messages") if isinstance(session.get("messages"), list) else [])[-20:]:
            if not isinstance(user_msg, dict) or user_msg.get("role") != "user":
                continue
            content = str(user_msg.get("content", ""))
            for t in _theme_tokens(content):
                theme_counts[t] = theme_counts.get(t, 0) + 1
            for s in _symbol_tokens(content):
                symbol_counts[s] = symbol_counts.get(s, 0) + 1
            low = _fold_tr(content)
            if any(w in low for w in HEAVY_EMOTION):
                emotion_score += 2
            elif any(w in low for w in SOFT_EMOTION):
                emotion_score += 1

        # include current message as soft signal (read-only)
        for t in _theme_tokens(msg):
            theme_counts[t] = theme_counts.get(t, 0) + 1
        for s in _symbol_tokens(msg):
            symbol_counts[s] = symbol_counts.get(s, 0) + 1

        repeating_themes = [
            _to_display_theme(k)
            for k, v in sorted(theme_counts.items(), key=lambda kv: kv[1], reverse=True)
            if v >= 2
        ][:6]
        repeating_symbols = [
            _to_display_symbol(k)
            for k, v in sorted(symbol_counts.items(), key=lambda kv: kv[1], reverse=True)
            if v >= 2
        ][:6]

        if emotion_score <= 0:
            emotional_echo = "none"
        elif emotion_score <= 2:
            emotional_echo = "low"
        elif emotion_score <= 5:
            emotional_echo = "medium"
        else:
            emotional_echo = "high"

        recall_available = anchors > 0 or bool(repeating_themes) or bool(repeating_symbols)
        confidence = 0.0
        if recall_available:
            confidence = min(1.0, 0.45 + (0.08 * min(anchors, 4)) + (0.1 * min(len(repeating_themes), 3)) + (0.08 * min(len(repeating_symbols), 3)))

        risk_flags: list[str] = []
        low_msg = _fold_tr(msg)
        if any(x in low_msg for x in SENSITIVE_TERMS):
            risk_flags.append("sensitive_content_present")

        if not recall_available:
            return MemoryReadSet.neutral()

        return MemoryReadSet(
            recall_available=recall_available,
            repeating_themes=repeating_themes,
            repeating_symbols=repeating_symbols,
            emotional_echo=emotional_echo,
            has_recent_anchor=recall_available,
            symbolic_echo_count=len(repeating_symbols),
            relational_echo_count=len(repeating_themes),
            safe_summary="memory_read:themes_symbols_echo",
            confidence=confidence,
            risk_flags=risk_flags[:4],
        )

    def propose_memory_write(
        self,
        message: str,
        memory_read: MemoryReadSet,
        analysis: dict[str, Any] | None = None,
        safety: dict[str, Any] | None = None,
    ) -> MemoryWriteCandidate:
        _ = analysis
        safety = safety or {}
        msg = _fold_tr(str(message or ""))
        read_conf = float(memory_read.confidence or 0.0)

        sensitive_hits = sum(1 for t in SENSITIVE_TERMS if t in msg)
        safety_alert = bool(safety.get("is_crisis") or safety.get("has_immediate_risk") or safety.get("needs_gentle_check"))

        if sensitive_hits > 0 or safety_alert:
            sensitivity = "high" if sensitive_hits > 1 or safety_alert else "medium"
        elif any(x in msg for x in ("adres", "telefon", "@")):
            sensitivity = "medium"
        else:
            sensitivity = "low" if read_conf >= 0.65 else "none"

        evidence_count = len(memory_read.repeating_themes or []) + len(memory_read.repeating_symbols or [])
        if evidence_count >= 4:
            reason_bucket = "repeating_pattern"
        elif evidence_count >= 2:
            reason_bucket = "emerging_pattern"
        elif memory_read.emotional_echo in {"medium", "high"}:
            reason_bucket = "emotional_echo"
        else:
            reason_bucket = "weak_signal"

        requires_repeat_evidence = True
        should_write = False
        if read_conf >= 0.72 and evidence_count >= 2 and sensitivity in {"none", "low"}:
            should_write = True
            requires_repeat_evidence = False
        elif read_conf >= 0.6 and evidence_count >= 2 and sensitivity == "low":
            should_write = False
            requires_repeat_evidence = True

        risk_flags: list[str] = []
        if sensitivity in {"medium", "high"}:
            risk_flags.append("sensitive_content")
        if read_conf < 0.6:
            risk_flags.append("low_confidence")
        if evidence_count <= 1:
            risk_flags.append("low_evidence")
        if safety_alert:
            risk_flags.append("safety_alert_present")

        return MemoryWriteCandidate(
            should_write=should_write,
            reason_bucket=reason_bucket,
            safe_summary=f"memory_candidate:{reason_bucket}",
            sensitivity=sensitivity,
            confidence=max(0.0, min(1.0, read_conf)),
            evidence_count=evidence_count,
            requires_repeat_evidence=requires_repeat_evidence,
            category=reason_bucket,
            risk_flags=risk_flags[:6],
            reasons=[
                "read_only_candidate",
                "no_durable_write_in_step2",
            ],
        )


def read_memory_signals(
    message: str,
    profile: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> MemoryReadSet:
    return MemoryLayerEngine().read_memory_signals(message, profile, session)


def propose_memory_write(
    message: str,
    memory_read: MemoryReadSet,
    analysis: dict[str, Any] | None = None,
    safety: dict[str, Any] | None = None,
) -> MemoryWriteCandidate:
    return MemoryLayerEngine().propose_memory_write(message, memory_read, analysis, safety)
