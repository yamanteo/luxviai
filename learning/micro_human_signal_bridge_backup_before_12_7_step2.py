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


def clamp(value: Any, lo: float = 0.0, hi: float = 1.0, default: float = 0.0) -> float:
    return max(lo, min(hi, safe_float(value, default)))


def safe_bool(value: Any) -> bool:
    return bool(value) if isinstance(value, bool) else str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def safe_bucket(value: Any, allowed: set[str], default: str) -> str:
    bucket = str(value or "").strip().lower()
    return bucket if bucket in allowed else default


def safe_flags(flags: list[Any] | None, limit: int = 8) -> list[str]:
    out: list[str] = []
    for item in flags or []:
        text = str(item or "").strip().lower()
        if not text or text in out:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


@dataclass(slots=True)
class MicroIntentSignal:
    intent_clarity_bucket: str = "unknown"  # unknown|clear|partial|unclear
    micro_intent_bucket: str = "none"  # none|question|command|correction|confirmation|continuation
    user_effort_bucket: str = "unknown"  # unknown|low|medium|high
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    safe_summary: str = "micro_intent_neutral"

    @classmethod
    def neutral(cls) -> "MicroIntentSignal":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "intent_clarity_bucket": safe_bucket(self.intent_clarity_bucket, {"unknown", "clear", "partial", "unclear"}, "unknown"),
            "micro_intent_bucket": safe_bucket(
                self.micro_intent_bucket,
                {"none", "question", "command", "correction", "confirmation", "continuation"},
                "none",
            ),
            "user_effort_bucket": safe_bucket(self.user_effort_bucket, {"unknown", "low", "medium", "high"}, "unknown"),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": safe_flags(self.risk_flags),
            "safe_summary": str(self.safe_summary or "micro_intent_neutral"),
        }


@dataclass(slots=True)
class TrustConfusionSignal:
    trust_state_bucket: str = "unknown"  # unknown|stable|verification_needed|repair_needed
    confusion_bucket: str = "none"  # none|low|medium|high
    misunderstanding_risk_signal: str = "none"  # none|possible|likely
    followup_pressure_risk: str = "none"  # none|low|medium|high
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    safe_summary: str = "trust_confusion_neutral"

    @classmethod
    def neutral(cls) -> "TrustConfusionSignal":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "trust_state_bucket": safe_bucket(
                self.trust_state_bucket,
                {"unknown", "stable", "verification_needed", "repair_needed"},
                "unknown",
            ),
            "confusion_bucket": safe_bucket(self.confusion_bucket, {"none", "low", "medium", "high"}, "none"),
            "misunderstanding_risk_signal": safe_bucket(
                self.misunderstanding_risk_signal,
                {"none", "possible", "likely"},
                "none",
            ),
            "followup_pressure_risk": safe_bucket(self.followup_pressure_risk, {"none", "low", "medium", "high"}, "none"),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": safe_flags(self.risk_flags),
            "safe_summary": str(self.safe_summary or "trust_confusion_neutral"),
        }


@dataclass(slots=True)
class RepairSignal:
    correction_needed: bool = False
    repair_needed_signal: str = "none"  # none|acknowledge|clarify|slow_down
    frustration_bucket: str = "none"  # none|low|medium|high
    response_satisfaction_hint: str = "unknown"  # unknown|satisfied|partial|unsatisfied
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    safe_summary: str = "repair_neutral"

    @classmethod
    def neutral(cls) -> "RepairSignal":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "correction_needed": bool(self.correction_needed),
            "repair_needed_signal": safe_bucket(
                self.repair_needed_signal,
                {"none", "acknowledge", "clarify", "slow_down"},
                "none",
            ),
            "frustration_bucket": safe_bucket(self.frustration_bucket, {"none", "low", "medium", "high"}, "none"),
            "response_satisfaction_hint": safe_bucket(
                self.response_satisfaction_hint,
                {"unknown", "satisfied", "partial", "unsatisfied"},
                "unknown",
            ),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": safe_flags(self.risk_flags),
            "safe_summary": str(self.safe_summary or "repair_neutral"),
        }


@dataclass(slots=True)
class AnswerSuccessSignal:
    answer_success_bucket: str = "unknown"  # unknown|success|partial|failed|not_applicable
    clarity_result_bucket: str = "unknown"  # unknown|clear|needs_more_clarity
    task_progress_bucket: str = "unknown"  # unknown|progressed|blocked|not_task
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    safe_summary: str = "answer_success_neutral"

    @classmethod
    def neutral(cls) -> "AnswerSuccessSignal":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "answer_success_bucket": safe_bucket(
                self.answer_success_bucket,
                {"unknown", "success", "partial", "failed", "not_applicable"},
                "unknown",
            ),
            "clarity_result_bucket": safe_bucket(self.clarity_result_bucket, {"unknown", "clear", "needs_more_clarity"}, "unknown"),
            "task_progress_bucket": safe_bucket(self.task_progress_bucket, {"unknown", "progressed", "blocked", "not_task"}, "unknown"),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": safe_flags(self.risk_flags),
            "safe_summary": str(self.safe_summary or "answer_success_neutral"),
        }


@dataclass(slots=True)
class MicroHumanSignalBundle:
    micro_intent: MicroIntentSignal = field(default_factory=MicroIntentSignal.neutral)
    trust_confusion: TrustConfusionSignal = field(default_factory=TrustConfusionSignal.neutral)
    repair: RepairSignal = field(default_factory=RepairSignal.neutral)
    answer_success: AnswerSuccessSignal = field(default_factory=AnswerSuccessSignal.neutral)
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    safe_summary: str = "micro_human_bridge_neutral"
    created_at: str = field(default_factory=now_iso)

    @classmethod
    def neutral(cls) -> "MicroHumanSignalBundle":
        return cls()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "micro_intent": self.micro_intent.to_safe_dict(),
            "trust_confusion": self.trust_confusion.to_safe_dict(),
            "repair": self.repair.to_safe_dict(),
            "answer_success": self.answer_success.to_safe_dict(),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": safe_flags(self.risk_flags, limit=10),
            "safe_summary": str(self.safe_summary or "micro_human_bridge_neutral"),
            "created_at": str(self.created_at),
        }


def neutral_bundle() -> MicroHumanSignalBundle:
    return MicroHumanSignalBundle.neutral()
