from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _fold_tr_ascii(value: str) -> str:
    raw = str(value or "")
    # Best-effort mojibake recovery.
    if any(ch in raw for ch in ("Ã", "Ä", "Å")):
        try:
            raw = raw.encode("latin1", "ignore").decode("utf-8", "ignore")
        except Exception:
            pass
    raw = (
        raw.replace("ı", "i")
        .replace("İ", "I")
        .replace("ğ", "g")
        .replace("Ğ", "G")
        .replace("ş", "s")
        .replace("Ş", "S")
        .replace("ö", "o")
        .replace("Ö", "O")
        .replace("ü", "u")
        .replace("Ü", "U")
        .replace("ç", "c")
        .replace("Ç", "C")
    )
    normalized = unicodedata.normalize("NFKD", raw)
    ascii_folded = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return ascii_folded.lower()


def _contains_any(text: str, parts: tuple[str, ...]) -> bool:
    return any(p in text for p in parts)


def _detect_safety(analysis: dict[str, Any] | None, human_risk: dict[str, Any] | None) -> bool:
    a = analysis or {}
    if bool(a.get("crisis_risk")):
        return True
    safety = a.get("safety_layer", {}) if isinstance(a.get("safety_layer"), dict) else {}
    crisis_ctx = _fold_tr_ascii(_norm(safety.get("crisis_context")))
    if crisis_ctx in {"self_harm", "violence", "abuse", "immediate_risk"}:
        return True
    hr = human_risk or {}
    level = _fold_tr_ascii(_norm(hr.get("safety_level")))
    return level in {"high_risk", "crisis"}


def _detect_technical_context(message: str) -> bool:
    low = _fold_tr_ascii(message)
    technical_terms = (
        "sekme",
        "buton",
        "aktif degil",
        "dashboard",
        "deploy",
        "kod",
        "terminal",
        "endpoint",
        "websocket",
        "app",
        "ui",
        "sesli komut",
        "ekran",
        "menu",
        "dosya",
        "port",
        "hata",
        "calismiyor",
        "render",
        "server",
        "api",
        "build",
        "fix",
    )
    return _contains_any(low, technical_terms)


def _detect_real_dream_context(message: str) -> bool:
    low = _fold_tr_ascii(message)
    false_positive = (
        "ruya gibi",
        "ruya kafe",
        "ruya bar",
        "adi ruya",
        "ismin ruya",
    )
    if _contains_any(low, false_positive):
        return False
    explicit = (
        "ruyamda",
        "ruya gordum",
        "kabus gordum",
        "ruyami yorumlar misin",
        "sana bir ruyami anlatayim",
        "ruya analizi",
        "luxdream yap",
        "cmd:luxdream",
        "dream analysis",
        "i had a dream",
    )
    if _contains_any(low, explicit):
        return True
    if "ruya" in low or "dream" in low:
        context_verbs = ("anlat", "gordum", "uyandim", "hissettim", "yorumla", "sahne", "scene")
        return _contains_any(low, context_verbs)
    return False


def _detect_decision_context(message: str) -> bool:
    low = _fold_tr_ascii(message)
    markers = (
        "kararsiz",
        "iki yol",
        "hangisi dogru",
        "olur mu olmaz mi",
        "acaba",
        "emin degilim",
        "bilemiyorum",
        "gitmeli miyim",
        "girmeli miyim",
        "cikmali miyim",
        "devam etmeli miyim",
        "birakmali miyim",
        "yapmali miyim",
        "should i",
    )
    if _contains_any(low, markers):
        return True
    reg = re.compile(r"\b\w+(mali|meli)\s*miyim\b|\b\w+(sam|sem)\s*mi\b", re.IGNORECASE)
    return bool(reg.search(low))


def _detect_luxmirror_explicit(message: str) -> bool:
    low = _fold_tr_ascii(message)
    return _contains_any(low, ("luxmirror yap", "lux mirror yap", "cmd:luxmirror"))


def _detect_luxching_explicit(message: str) -> bool:
    low = _fold_tr_ascii(message)
    return _contains_any(low, ("cmd:luxching", "luxching yap", "i ching ile bak", "iching ile bak"))


@dataclass(slots=True)
class LensGuardDecision:
    selected_lens: str = "normal"  # safety|technical|normal|luxmirror|luxdream|luxching
    suppressed_lenses: list[str] = field(default_factory=list)
    reason_bucket: str = "normal_flow"  # safety|utility|dream_context|decision_context|explicit_command|cooldown|normal_flow
    confidence_bucket: str = "medium"  # low|medium|high
    risk_flags: list[str] = field(default_factory=list)
    technical_context: bool = False
    dream_context: bool = False
    decision_context: bool = False
    lens_stacking_near_miss: bool = False

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "selected_lens": self.selected_lens,
            "suppressed_lenses": [str(x) for x in self.suppressed_lenses[:8]],
            "reason_bucket": self.reason_bucket,
            "confidence_bucket": self.confidence_bucket,
            "risk_flags": [str(x) for x in self.risk_flags[:8]],
            "technical_context": bool(self.technical_context),
            "dream_context": bool(self.dream_context),
            "decision_context": bool(self.decision_context),
            "lens_stacking_near_miss": bool(self.lens_stacking_near_miss),
        }


def resolve_lens_precedence(
    *,
    message: str,
    mode: str = "luxviai",
    analysis: dict[str, Any] | None = None,
    human_risk: dict[str, Any] | None = None,
) -> LensGuardDecision:
    _ = mode  # Step 1.5: mode-aware branching can be expanded in Step 2.
    safety = _detect_safety(analysis, human_risk)
    technical = _detect_technical_context(message)
    dream = _detect_real_dream_context(message)
    decision = _detect_decision_context(message)
    mirror_explicit = _detect_luxmirror_explicit(message)
    ching_explicit = _detect_luxching_explicit(message)

    candidates: list[str] = []
    if safety:
        candidates.append("safety")
    if technical:
        candidates.append("technical")
    if mirror_explicit:
        candidates.append("luxmirror")
    if dream:
        candidates.append("luxdream")
    if ching_explicit:
        candidates.append("luxching")

    selected = "normal"
    reason = "normal_flow"
    confidence = "medium"
    if safety:
        selected, reason, confidence = "safety", "safety", "high"
    elif technical:
        selected, reason, confidence = "technical", "utility", "high"
    elif mirror_explicit:
        selected, reason, confidence = "luxmirror", "explicit_command", "high"
    elif dream:
        selected, reason, confidence = "luxdream", "dream_context", "medium"
    elif ching_explicit:
        selected, reason, confidence = "luxching", "explicit_command", "medium"
    elif decision:
        selected, reason, confidence = "normal", "decision_context", "medium"

    suppressed = [c for c in candidates if c != selected]
    near_miss = len(candidates) > 1
    flags: list[str] = []
    if near_miss:
        flags.append("stacking_near_miss")
    if technical and (dream or ching_explicit or mirror_explicit):
        flags.append("utility_over_symbolic_preferred")

    return LensGuardDecision(
        selected_lens=selected,
        suppressed_lenses=suppressed,
        reason_bucket=reason,
        confidence_bucket=confidence,
        risk_flags=flags,
        technical_context=technical,
        dream_context=dream,
        decision_context=decision,
        lens_stacking_near_miss=near_miss,
    )
