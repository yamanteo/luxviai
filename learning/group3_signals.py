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
    objects: list[str] = field(default_factory=list)
    archetype_bucket: str = "unknown"  # threshold|path|reflection|containment|water|shadow|unknown
    continuity: str = "none"  # none|single|repeated
    recurring_symbols: list[str] = field(default_factory=list)  # legacy alias
    safe_summary: str = "no_symbolic_signal"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)

    @classmethod
    def neutral(cls) -> "SymbolicSignal":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        objects = [str(x) for x in (self.objects or [])[:6]]
        recurring = [str(x) for x in (self.recurring_symbols or self.objects or [])[:5]]
        return {
            "density": str(self.density),
            "objects": objects,
            "archetype_bucket": str(self.archetype_bucket),
            "continuity": str(self.continuity),
            "recurring_symbols": recurring,
            "safe_summary": str(self.safe_summary),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": [str(x) for x in self.risk_flags[:6]],
        }


@dataclass(slots=True)
class DreamSignal:
    is_dream_context: bool = False
    false_positive_blocked: bool = False
    dream_intensity: str = "none"  # none|low|medium|high
    image_count_bucket: str = "none"  # none|few|many
    emotional_residue: str = "none"  # none|soft|tense|heavy|unknown
    continuation_ready: bool = False
    # legacy aliases used in earlier steps
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
        is_dream_context = bool(self.is_dream_context or self.dream_context)
        false_positive_blocked = bool(self.false_positive_blocked)
        return {
            "is_dream_context": is_dream_context,
            "false_positive_blocked": false_positive_blocked,
            "dream_intensity": str(self.dream_intensity),
            "image_count_bucket": str(self.image_count_bucket),
            "emotional_residue": str(self.emotional_residue),
            "continuation_ready": bool(self.continuation_ready),
            # legacy keys kept for backward compatibility
            "dream_context": is_dream_context,
            "false_positive_guarded": bool(self.false_positive_guarded),
            "imagery_buckets": [str(x) for x in self.imagery_buckets[:5]],
            "affect_bucket": str(self.affect_bucket),
            "safe_summary": str(self.safe_summary),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": [str(x) for x in self.risk_flags[:6]],
        }


@dataclass(slots=True)
class ExistentialSignal:
    meaning_signal: str = "none"  # none|background|active
    identity_signal: str = "none"  # none|background|active
    direction_signal: str = "none"  # none|background|active
    loneliness_signal: str = "none"  # none|background|active
    time_pressure: str = "none"  # none|low|medium|high
    uncertainty: str = "none"  # none|low|medium|high
    support_need: str = "none"  # none|soft|grounding|one_step
    # legacy aliases
    meaning_tension: str = "none"
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
            "meaning_signal": str(self.meaning_signal),
            "identity_signal": str(self.identity_signal),
            "direction_signal": str(self.direction_signal),
            "loneliness_signal": str(self.loneliness_signal),
            "time_pressure": str(self.time_pressure),
            "uncertainty": str(self.uncertainty),
            "support_need": str(self.support_need),
            # legacy keys
            "meaning_tension": str(self.meaning_tension),
            "identity_tension": str(self.identity_tension),
            "direction_uncertainty": str(self.direction_uncertainty),
            "safe_summary": str(self.safe_summary),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": [str(x) for x in self.risk_flags[:6]],
        }


@dataclass(slots=True)
class MemoryReadSet:
    recall_available: bool = False
    repeating_themes: list[str] = field(default_factory=list)
    repeating_symbols: list[str] = field(default_factory=list)
    emotional_echo: str = "none"  # none|low|medium|high
    # legacy aliases
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
        repeating_themes = [str(x) for x in (self.repeating_themes or [])[:6]]
        repeating_symbols = [str(x) for x in (self.repeating_symbols or [])[:6]]
        symbolic_echo_count = max(0, int(self.symbolic_echo_count or len(repeating_symbols)))
        return {
            "recall_available": bool(self.recall_available or self.has_recent_anchor),
            "repeating_themes": repeating_themes,
            "repeating_symbols": repeating_symbols,
            "emotional_echo": str(self.emotional_echo),
            # legacy keys
            "has_recent_anchor": bool(self.has_recent_anchor or self.recall_available),
            "symbolic_echo_count": symbolic_echo_count,
            "relational_echo_count": max(0, int(self.relational_echo_count)),
            "safe_summary": str(self.safe_summary),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": [str(x) for x in self.risk_flags[:6]],
        }


@dataclass(slots=True)
class MemoryWriteCandidate:
    should_write: bool = False
    reason_bucket: str = "none"
    safe_summary: str = "no_memory_write_candidate"
    sensitivity: str = "none"  # none|low|medium|high
    confidence: float = 0.0
    evidence_count: int = 0
    requires_repeat_evidence: bool = True
    # legacy aliases
    category: str = "none"
    risk_flags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @classmethod
    def neutral(cls) -> "MemoryWriteCandidate":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        reason_bucket = str(self.reason_bucket or self.category or "none")
        return {
            "should_write": bool(self.should_write),
            "reason_bucket": reason_bucket,
            "safe_summary": str(self.safe_summary),
            "sensitivity": str(self.sensitivity),
            "confidence": round(clamp(self.confidence), 4),
            "evidence_count": max(0, int(self.evidence_count)),
            "requires_repeat_evidence": bool(self.requires_repeat_evidence),
            # legacy keys
            "category": reason_bucket,
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
