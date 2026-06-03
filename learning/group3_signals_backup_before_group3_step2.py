from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, safe_float(value, lo)))


@dataclass(slots=True)
class SymbolicSignal:
    density: str = "none"  # none|low|medium|high
    recurring_symbols: list[str] = field(default_factory=list)
    safe_summary: str = "no_symbolic_signal"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)

    @classmethod
    def neutral(cls) -> "SymbolicSignal":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "density": str(self.density),
            "recurring_symbols": [str(x) for x in self.recurring_symbols[:5]],
            "safe_summary": str(self.safe_summary),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": [str(x) for x in self.risk_flags[:6]],
        }


@dataclass(slots=True)
class DreamSignal:
    dream_context: bool = False
    false_positive_guarded: bool = True
    imagery_buckets: list[str] = field(default_factory=list)
    affect_bucket: str = "neutral"
    safe_summary: str = "no_dream_signal"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)

    @classmethod
    def neutral(cls) -> "DreamSignal":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "dream_context": bool(self.dream_context),
            "false_positive_guarded": bool(self.false_positive_guarded),
            "imagery_buckets": [str(x) for x in self.imagery_buckets[:5]],
            "affect_bucket": str(self.affect_bucket),
            "safe_summary": str(self.safe_summary),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": [str(x) for x in self.risk_flags[:6]],
        }


@dataclass(slots=True)
class ExistentialSignal:
    meaning_tension: str = "none"  # none|low|medium|high
    identity_tension: str = "none"
    direction_uncertainty: str = "none"
    safe_summary: str = "no_existential_signal"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)

    @classmethod
    def neutral(cls) -> "ExistentialSignal":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "meaning_tension": str(self.meaning_tension),
            "identity_tension": str(self.identity_tension),
            "direction_uncertainty": str(self.direction_uncertainty),
            "safe_summary": str(self.safe_summary),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": [str(x) for x in self.risk_flags[:6]],
        }


@dataclass(slots=True)
class MemoryReadSet:
    has_recent_anchor: bool = False
    symbolic_echo_count: int = 0
    relational_echo_count: int = 0
    safe_summary: str = "no_memory_read_signal"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)

    @classmethod
    def neutral(cls) -> "MemoryReadSet":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "has_recent_anchor": bool(self.has_recent_anchor),
            "symbolic_echo_count": max(0, int(self.symbolic_echo_count)),
            "relational_echo_count": max(0, int(self.relational_echo_count)),
            "safe_summary": str(self.safe_summary),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": [str(x) for x in self.risk_flags[:6]],
        }


@dataclass(slots=True)
class MemoryWriteCandidate:
    should_write: bool = False
    category: str = "none"
    safe_summary: str = "no_memory_write_candidate"
    confidence: float = 0.0
    evidence_count: int = 0
    risk_flags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @classmethod
    def neutral(cls) -> "MemoryWriteCandidate":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "should_write": bool(self.should_write),
            "category": str(self.category),
            "safe_summary": str(self.safe_summary),
            "confidence": round(clamp(self.confidence), 4),
            "evidence_count": max(0, int(self.evidence_count)),
            "risk_flags": [str(x) for x in self.risk_flags[:8]],
            "reasons": [str(x) for x in self.reasons[:8]],
        }


@dataclass(slots=True)
class Group3Bundle:
    memory_read: MemoryReadSet = field(default_factory=MemoryReadSet.neutral)
    symbolic: SymbolicSignal = field(default_factory=SymbolicSignal.neutral)
    dream: DreamSignal = field(default_factory=DreamSignal.neutral)
    existential: ExistentialSignal = field(default_factory=ExistentialSignal.neutral)
    memory_write_candidate: MemoryWriteCandidate = field(default_factory=MemoryWriteCandidate.neutral)
    safe_summary: str = "group3_neutral_bundle"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)

    @classmethod
    def neutral(cls) -> "Group3Bundle":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "memory_read": self.memory_read.to_safe_dict(),
            "symbolic": self.symbolic.to_safe_dict(),
            "dream": self.dream.to_safe_dict(),
            "existential": self.existential.to_safe_dict(),
            "memory_write_candidate": self.memory_write_candidate.to_safe_dict(),
            "safe_summary": str(self.safe_summary),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": [str(x) for x in self.risk_flags[:10]],
            "created_at": str(self.created_at),
        }

