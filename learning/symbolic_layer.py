from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .group3_signals import SymbolicSignal


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


SYMBOL_OBJECT_MAP: dict[str, tuple[str, str]] = {
    "kapi": ("kapı", "threshold"),
    "esik": ("eşik", "threshold"),
    "yol": ("yol", "path"),
    "patika": ("patika", "path"),
    "kopru": ("köprü", "path"),
    "ayna": ("ayna", "reflection"),
    "oda": ("oda", "containment"),
    "ev": ("ev", "containment"),
    "duvar": ("duvar", "containment"),
    "deniz": ("deniz", "water"),
    "okyanus": ("okyanus", "water"),
    "nehir": ("nehir", "water"),
    "gol": ("göl", "water"),
    "tren": ("tren", "path"),
    "isik": ("ışık", "reflection"),
    "golge": ("gölge", "shadow"),
    "karanlik": ("karanlık", "shadow"),
    "anahtar": ("anahtar", "threshold"),
}

PROPHECY_TERMS = ("kader", "kehanet", "fal", "kesin olacak", "gelecekte")


def _pick_density(hit_count: int) -> str:
    if hit_count <= 0:
        return "none"
    if hit_count == 1:
        return "low"
    if hit_count <= 3:
        return "medium"
    return "high"


def _pick_confidence(hit_count: int, archetype_hits: int) -> float:
    base = 0.2 + (min(hit_count, 5) * 0.12) + (min(archetype_hits, 3) * 0.08)
    return max(0.0, min(1.0, base))


@dataclass(slots=True)
class SymbolicLayerEngine:
    def extract_symbolic_signal(
        self,
        message: str,
        analysis: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
    ) -> SymbolicSignal:
        _ = analysis, profile
        raw = str(message or "")
        folded = _fold_tr(raw)
        variants = {folded, folded.replace("?", "i"), folded.replace("?", "u")}
        token_counts: dict[str, int] = {}
        for variant in variants:
            variant_counts: dict[str, int] = {}
            for tok in re.findall(r"[a-z0-9_]+", variant):
                variant_counts[tok] = variant_counts.get(tok, 0) + 1
            for tok, count in variant_counts.items():
                token_counts[tok] = max(token_counts.get(tok, 0), count)

        found_objects: list[str] = []
        archetype_counts: dict[str, int] = {}
        total_hits = 0
        for key, (label, archetype) in SYMBOL_OBJECT_MAP.items():
            count = token_counts.get(key, 0)
            if count <= 0:
                # light Turkish suffix tolerance: kapi+nin, oda+da, yol+da...
                count = sum(
                    c
                    for tok, c in token_counts.items()
                    if tok.startswith(key) and 0 < (len(tok) - len(key)) <= 4
                )
            if count <= 0:
                continue
            total_hits += count
            found_objects.append(label)
            archetype_counts[archetype] = archetype_counts.get(archetype, 0) + count

        if not found_objects:
            return SymbolicSignal.neutral()

        # continuity: repeated if same object appears multiple times OR previous user turns include same object
        continuity = "single"
        repeated_local = any(token_counts.get(k, 0) >= 2 for k in SYMBOL_OBJECT_MAP)
        repeated_session = False
        if isinstance(session, dict):
            for msg in session.get("messages", [])[-8:]:
                if not isinstance(msg, dict) or msg.get("role") != "user":
                    continue
                content = _fold_tr(str(msg.get("content", "")))
                if content and any(k in content for k in SYMBOL_OBJECT_MAP):
                    repeated_session = True
                    break
        if repeated_local or repeated_session:
            continuity = "repeated"

        archetype_bucket = "unknown"
        if archetype_counts:
            archetype_bucket = sorted(archetype_counts.items(), key=lambda x: x[1], reverse=True)[0][0]

        density = _pick_density(total_hits)
        confidence = _pick_confidence(total_hits, len(archetype_counts))
        risk_flags: list[str] = []
        if any(term in folded for term in PROPHECY_TERMS):
            risk_flags.append("prophecy_language_present")

        unique_objects = []
        seen = set()
        for obj in found_objects:
            if obj in seen:
                continue
            seen.add(obj)
            unique_objects.append(obj)
            if len(unique_objects) >= 6:
                break

        return SymbolicSignal(
            density=density,
            objects=unique_objects,
            archetype_bucket=archetype_bucket,
            continuity=continuity,
            recurring_symbols=unique_objects[:5],
            safe_summary=f"symbolic_signal:{density}:{archetype_bucket}",
            confidence=confidence,
            risk_flags=risk_flags[:4],
        )


def extract_symbolic_signal(
    message: str,
    analysis: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> SymbolicSignal:
    return SymbolicLayerEngine().extract_symbolic_signal(message, analysis, profile, session)
