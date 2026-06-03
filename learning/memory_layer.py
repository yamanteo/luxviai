from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from .group3_signals import MemoryReadSet, MemoryWriteCandidate
from .io_utils import load_json, save_json


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

PREFERENCE_MARKERS: dict[str, tuple[str, ...]] = {
    "pref_step_by_step": ("adim adim", "tek adim", "tek tek"),
    "pref_short_clear": ("kisa anlat", "kisa ve net", "sade anlat", "somut anlat"),
}

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

HIGH_RISK_FLAGS = {"sensitive_content", "safety_alert_present"}
PII_PATTERNS = (
    re.compile(r"\b\d{10,}\b"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"https?://\S+"),
)


def _tokenize(text: str) -> list[str]:
    folded = _fold_tr(text)
    variants = [folded, folded.replace("?", "i"), folded.replace("?", "u")]
    token_lists = [re.findall(r"[a-z0-9_]+", v) for v in variants]
    token_lists.sort(key=len, reverse=True)
    return token_lists[0] if token_lists else []


def _theme_tokens(text: str) -> list[str]:
    out: list[str] = []
    folded = _fold_tr(text)
    for t in _tokenize(folded):
        if any(t.startswith(root) for root in THEME_ROOTS):
            out.append(t)
    for pref_key, phrases in PREFERENCE_MARKERS.items():
        if any(ph in folded for ph in phrases):
            out.append(pref_key)
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
        "pref_step_by_step": "adım adım tercih",
        "pref_short_clear": "kısa/net anlatım tercihi",
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sanitize_memory_summary(text: str, max_len: int = 220) -> str:
    value = str(text or "")
    # Remove obvious contact/URL patterns.
    value = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[redacted-email]", value)
    value = re.sub(r"https?://\S+", "[redacted-url]", value)
    value = re.sub(r"\b\d{10,}\b", "[redacted-number]", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:max_len]


def detect_sensitive_memory_content(text: str) -> bool:
    low = _fold_tr(str(text or ""))
    if any(term in low for term in SENSITIVE_TERMS):
        return True
    for pattern in PII_PATTERNS:
        if pattern.search(str(text or "")):
            return True
    return False


def _anchor_signature(anchor: dict[str, Any]) -> str:
    text = _fold_tr(str(anchor.get("text", "")))
    kind = _fold_tr(str(anchor.get("kind", "")))
    theme = _fold_tr(str(anchor.get("theme", "")))
    return f"{kind}|{theme}|{text[:140]}"


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

        # Add weak, sanitized repeat evidence from existing user memory garden (if any).
        for item in (profile.get("memory_garden") if isinstance(profile.get("memory_garden"), list) else [])[-40:]:
            if not isinstance(item, dict):
                continue
            text_part = str(item.get("text", ""))
            for t in _theme_tokens(text_part):
                theme_counts[t] = theme_counts.get(t, 0) + 1
            for s in _symbol_tokens(text_part):
                symbol_counts[s] = symbol_counts.get(s, 0) + 1
            item_theme = str(item.get("theme", ""))
            for t in _theme_tokens(item_theme):
                theme_counts[t] = theme_counts.get(t, 0) + 1

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

    def evaluate_memory_write_candidate(
        self,
        message: str,
        candidate: MemoryWriteCandidate,
        *,
        memory_read: MemoryReadSet | None = None,
        analysis: dict[str, Any] | None = None,
        safety: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = analysis
        safety = safety or {}
        memory_read = memory_read or MemoryReadSet.neutral()

        reasons: list[str] = []
        confidence = float(candidate.confidence or 0.0)
        evidence_count = int(candidate.evidence_count or 0)
        sensitivity = str(candidate.sensitivity or "none")
        reason_bucket = str(candidate.reason_bucket or candidate.category or "none")
        sanitized_summary = sanitize_memory_summary(candidate.safe_summary or "")

        if not bool(candidate.should_write):
            reasons.append("candidate_should_write_false")
        if confidence < 0.72:
            reasons.append("low_confidence")
        if sensitivity in {"medium", "high"}:
            reasons.append("sensitivity_block")
        if bool(candidate.requires_repeat_evidence):
            reasons.append("requires_repeat_evidence")
        if evidence_count < 2:
            reasons.append("insufficient_evidence")
        if reason_bucket in {"none", "weak_signal"}:
            reasons.append("weak_reason_bucket")

        risk_flags = {str(x) for x in (candidate.risk_flags or [])}
        if risk_flags.intersection(HIGH_RISK_FLAGS):
            reasons.append("high_risk_flag")
        if detect_sensitive_memory_content(message) or detect_sensitive_memory_content(sanitized_summary):
            reasons.append("sensitive_content_detected")
        if bool(safety.get("is_crisis")) or bool(safety.get("has_immediate_risk")) or bool(safety.get("is_sensitive_interaction")):
            reasons.append("safety_gate_block")

        allow_write = len(reasons) == 0
        return {
            "allow_write": allow_write,
            "confidence": round(max(0.0, min(1.0, confidence)), 4),
            "sensitivity": sensitivity,
            "reason_bucket": reason_bucket,
            "evidence_count": evidence_count,
            "sanitized_summary": sanitized_summary,
            "reasons": reasons[:8],
            "risk_flags": [str(x) for x in (candidate.risk_flags or [])[:8]],
            "requires_repeat_evidence": bool(candidate.requires_repeat_evidence),
            "recall_available": bool(memory_read.recall_available),
        }

    def should_persist_memory_candidate(
        self,
        message: str,
        candidate: MemoryWriteCandidate,
        *,
        memory_read: MemoryReadSet | None = None,
        analysis: dict[str, Any] | None = None,
        safety: dict[str, Any] | None = None,
    ) -> bool:
        gate = self.evaluate_memory_write_candidate(
            message,
            candidate,
            memory_read=memory_read,
            analysis=analysis,
            safety=safety,
        )
        return bool(gate.get("allow_write"))

    def build_safe_memory_anchor(
        self,
        *,
        candidate: MemoryWriteCandidate,
        gate: dict[str, Any],
        analysis: dict[str, Any] | None = None,
        symbolic: dict[str, Any] | None = None,
        dream: dict[str, Any] | None = None,
        existential: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        analysis = analysis or {}
        symbolic = symbolic or {}
        dream = dream or {}
        existential = existential or {}

        summary = sanitize_memory_summary(str(gate.get("sanitized_summary", candidate.safe_summary or "")))
        theme = str(analysis.get("theme", "belirsiz"))[:64]
        emotion = str(analysis.get("primary_emotion", "nötr"))[:48]
        intensity = int(analysis.get("intensity", 1) or 1)
        intensity = max(1, min(10, intensity))
        support_need = str(existential.get("support_need", "soft"))
        archetype = str(symbolic.get("archetype_bucket", "unknown"))

        return {
            "text": summary or "güvenli bellek özeti",
            "theme": theme,
            "emotion": emotion,
            "intensity": intensity,
            "kind": "group3_safe_anchor",
            "source": "learning_group3_step4",
            "layers": {
                "symbolic_bucket": archetype,
                "dream_context": bool(dream.get("is_dream_context") or dream.get("dream_context")),
                "existential_support": support_need,
                "memory_reason_bucket": str(gate.get("reason_bucket", "none")),
            },
            "confidence": float(gate.get("confidence", candidate.confidence or 0.0)),
            "sensitivity": str(gate.get("sensitivity", candidate.sensitivity or "none")),
            "ts": _now_iso(),
        }

    def persist_memory_anchor(
        self,
        *,
        base_dir: Path,
        user_id: str,
        anchor: dict[str, Any],
        max_items: int = 160,
    ) -> dict[str, Any]:
        user_safe = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id or "default_user")).lower()[:64] or "default_user"
        path = Path(base_dir) / "data" / "users" / user_safe / "memory_garden.json"
        garden = load_json(path, [])
        if not isinstance(garden, list):
            garden = []

        sig = _anchor_signature(anchor)
        if any(_anchor_signature(item) == sig for item in garden[-80:] if isinstance(item, dict)):
            return {"written": False, "reason": "duplicate_anchor", "count": len(garden)}

        garden.append(anchor)
        if len(garden) > max_items:
            garden = garden[-max_items:]
        save_json(path, garden)
        return {"written": True, "reason": "ok", "count": len(garden)}


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
