from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import re


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


def fold_text(value: Any) -> str:
    text = str(value or "").lower()
    table = str.maketrans(
        {
            "ç": "c",
            "ğ": "g",
            "ı": "i",
            "i": "i",
            "ö": "o",
            "ş": "s",
            "ü": "u",
            "â": "a",
            "î": "i",
            "û": "u",
        }
    )
    return text.translate(table)


def has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def token_count(text: str) -> int:
    return len(re.findall(r"\w+", text, flags=re.UNICODE))


def is_safety_sensitive(message: str, analysis: dict[str, Any] | None = None) -> bool:
    analysis = analysis or {}
    if bool(analysis.get("crisis_risk")):
        return True
    safety = analysis.get("safety_layer", {})
    if isinstance(safety, dict):
        if bool(safety.get("route_to_emergency")) or bool(safety.get("needs_gentle_check")):
            return True
        level = str(safety.get("crisis_level", "")).strip().lower()
        if level in {"watch", "high", "crisis", "contextual"}:
            return True
    folded = fold_text(message)
    safety_terms = (
        "intihar",
        "olmek istiyorum",
        "oldurecegim",
        "kendime zarar",
        "zarar verecegim",
        "tecavuz",
        "istismar",
        "siddet",
        "silah",
        "bicak",
        "guvende degilim",
        "tehdit",
    )
    return has_any(folded, safety_terms)


def short_low_data(message: str) -> bool:
    folded = fold_text(message).strip()
    low_data = {"tamam", "evet", "hayir", "devam", "olur", "hmm", "peki", "ne", "?", "ok", "oke", "okey"}
    return folded in low_data or token_count(folded) <= 1


@dataclass(slots=True)
class MicroIntentSignal:
    intent_clarity_bucket: str = "unknown"  # unknown|clear|partial|ambiguous|unclear
    request_type_bucket: str = "unknown"  # unknown|technical|emotional|decision|dream|correction|meta_feedback|casual
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
            "intent_clarity_bucket": safe_bucket(self.intent_clarity_bucket, {"unknown", "clear", "partial", "ambiguous", "unclear"}, "unknown"),
            "request_type_bucket": safe_bucket(
                self.request_type_bucket,
                {"unknown", "technical", "emotional", "decision", "dream", "correction", "meta_feedback", "casual"},
                "unknown",
            ),
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
    trust_state_bucket: str = "unknown"  # unknown|neutral|stable|trust_building|verification_needed|trust_drop_possible|explicit_distrust|repair_needed
    confusion_bucket: str = "none"  # none|mild|low|medium|high|unknown
    misunderstanding_risk_signal: str = "none"  # none|possible|likely
    misunderstanding_risk_bucket: str = "none"  # none|low|medium|high|unknown
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
                {"unknown", "neutral", "stable", "trust_building", "verification_needed", "trust_drop_possible", "explicit_distrust", "repair_needed"},
                "unknown",
            ),
            "confusion_bucket": safe_bucket(self.confusion_bucket, {"none", "mild", "low", "medium", "high", "unknown"}, "none"),
            "misunderstanding_risk_signal": safe_bucket(
                self.misunderstanding_risk_signal,
                {"none", "possible", "likely"},
                "none",
            ),
            "misunderstanding_risk_bucket": safe_bucket(self.misunderstanding_risk_bucket, {"none", "low", "medium", "high", "unknown"}, "none"),
            "followup_pressure_risk": safe_bucket(self.followup_pressure_risk, {"none", "low", "medium", "high"}, "none"),
            "confidence": round(clamp(self.confidence), 4),
            "risk_flags": safe_flags(self.risk_flags),
            "safe_summary": str(self.safe_summary or "trust_confusion_neutral"),
        }


@dataclass(slots=True)
class RepairSignal:
    correction_needed: bool = False
    correction_type_bucket: str = "none"  # none|user_corrects_assistant|assistant_misattributed_text|wrong_lens|wrong_tone|wrong_fact|truncation_or_cutoff|unclear_response|unknown
    repair_needed_signal: str = "none"  # none|acknowledge|clarify|slow_down
    repair_urgency_bucket: str = "none"  # none|low|medium|high
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
            "correction_type_bucket": safe_bucket(
                self.correction_type_bucket,
                {
                    "none",
                    "user_corrects_assistant",
                    "assistant_misattributed_text",
                    "wrong_lens",
                    "wrong_tone",
                    "wrong_fact",
                    "truncation_or_cutoff",
                    "unclear_response",
                    "unknown",
                },
                "none",
            ),
            "repair_needed_signal": safe_bucket(
                self.repair_needed_signal,
                {"none", "acknowledge", "clarify", "slow_down"},
                "none",
            ),
            "repair_urgency_bucket": safe_bucket(self.repair_urgency_bucket, {"none", "low", "medium", "high"}, "none"),
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
    answer_success_bucket: str = "unknown"  # unknown|success|likely_success|partial|partial_success|failed|likely_failure|explicit_failure|not_applicable
    clarity_result_bucket: str = "unknown"  # unknown|clear|needs_more_clarity
    task_progress_bucket: str = "unknown"  # unknown|progressed|blocked|not_task
    frustration_bucket: str = "none"  # none|mild|medium|high|unknown
    followup_pressure_risk: str = "none"  # none|low|medium|high
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
                {"unknown", "success", "likely_success", "partial", "partial_success", "failed", "likely_failure", "explicit_failure", "not_applicable"},
                "unknown",
            ),
            "clarity_result_bucket": safe_bucket(self.clarity_result_bucket, {"unknown", "clear", "needs_more_clarity"}, "unknown"),
            "task_progress_bucket": safe_bucket(self.task_progress_bucket, {"unknown", "progressed", "blocked", "not_task"}, "unknown"),
            "frustration_bucket": safe_bucket(self.frustration_bucket, {"none", "mild", "medium", "high", "unknown"}, "none"),
            "followup_pressure_risk": safe_bucket(self.followup_pressure_risk, {"none", "low", "medium", "high"}, "none"),
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


def extract_micro_intent_signal(
    message: str,
    session: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> MicroIntentSignal:
    _ = session, context
    if is_safety_sensitive(message, analysis):
        return MicroIntentSignal(confidence=0.0, risk_flags=["safety_suppressed"], safe_summary="micro_intent_safety_suppressed")

    folded = fold_text(message)
    words = token_count(folded)
    if short_low_data(message):
        return MicroIntentSignal(
            intent_clarity_bucket="unknown",
            request_type_bucket="casual",
            micro_intent_bucket="confirmation" if folded.strip() in {"tamam", "evet", "ok", "oke", "okey"} else "none",
            user_effort_bucket="low",
            confidence=0.18,
            safe_summary="micro_intent_low_data_neutral",
        )

    technical_terms = ("kod", "terminal", "port", "dashboard", "endpoint", "websocket", "deploy", "hata", "dosya", "cmd", "errno", "api", "python")
    correction_terms = ("yanlis anladin", "bunu sen yazdin", "boyle kisaltmalar yazma", "metafor yapma", "ruya degil", "luxching degil")
    dream_terms = ("ruyam", "ruyamda", "ruya gordum", "kabus")
    decision_terms = ("kararsiz", "hangi yolu", "yapmali miyim", "gitmeli miyim", "devam etmeli miyim")
    emotional_terms = ("yoruldum", "uzuldum", "korkuyorum", "sinirlendim", "yalniz", "kafam karisti")
    meta_terms = ("cevap", "prompt", "davranis", "sistem", "model", "schema")

    request_type = "casual"
    if has_any(folded, technical_terms):
        request_type = "technical"
    elif has_any(folded, correction_terms):
        request_type = "correction"
    elif has_any(folded, dream_terms):
        request_type = "dream"
    elif has_any(folded, decision_terms):
        request_type = "decision"
    elif has_any(folded, emotional_terms):
        request_type = "emotional"
    elif has_any(folded, meta_terms):
        request_type = "meta_feedback"

    if has_any(folded, correction_terms):
        micro_intent = "correction"
    elif "?" in str(message) or has_any(folded, ("ne demek", "nasil", "neden", "hangi")):
        micro_intent = "question"
    elif has_any(folded, ("yap", "duzelt", "kontrol et", "ekle", "sil", "ac", "kapat")):
        micro_intent = "command"
    elif has_any(folded, ("devam", "surdur", "sonraki")):
        micro_intent = "continuation"
    else:
        micro_intent = "none"

    clarity = "clear" if request_type in {"technical", "correction", "dream", "decision"} or micro_intent in {"question", "command"} else "partial"
    effort = "high" if words >= 28 else "medium" if words >= 7 else "low"
    confidence = 0.74 if clarity == "clear" else 0.56
    return MicroIntentSignal(
        intent_clarity_bucket=clarity,
        request_type_bucket=request_type,
        micro_intent_bucket=micro_intent,
        user_effort_bucket=effort,
        confidence=confidence,
        safe_summary=f"micro_intent_{request_type}_{clarity}",
    )


def extract_trust_confusion_signal(
    message: str,
    session: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> TrustConfusionSignal:
    _ = session, context
    if is_safety_sensitive(message, analysis):
        return TrustConfusionSignal(confidence=0.0, risk_flags=["safety_suppressed"], safe_summary="trust_confusion_safety_suppressed")

    folded = fold_text(message)
    if short_low_data(message):
        return TrustConfusionSignal(trust_state_bucket="neutral", confidence=0.16, safe_summary="trust_confusion_low_data_neutral")

    confusion_high = ("anlamadim", "kafam karisti", "hic anlamadim", "nasil yani")
    confusion_medium = ("bu ne demek", "ne demek istedin", "bunu ac", "hangi", "ayni sey mi", "neyi engelledin")
    distrust_explicit = ("guvenmiyorum", "sacma", "yanlis soyluyorsun", "emin degilsin")
    trust_drop = ("emin misin", "bozmayalim", "beni anlamiyorsun", "yanlis anladin")
    trust_building = ("dogru", "aynen", "tam bu", "harika", "super")

    confusion = "none"
    misunderstanding = "none"
    if has_any(folded, confusion_high):
        confusion = "high"
        misunderstanding = "high"
    elif has_any(folded, confusion_medium):
        confusion = "medium"
        misunderstanding = "medium"
    elif "?" in str(message) and len(folded) < 80:
        confusion = "mild"
        misunderstanding = "low"

    trust = "neutral"
    if has_any(folded, distrust_explicit):
        trust = "explicit_distrust"
    elif has_any(folded, trust_drop):
        trust = "trust_drop_possible"
    elif has_any(folded, trust_building):
        trust = "trust_building"

    confidence = 0.74 if confusion in {"medium", "high"} or trust in {"explicit_distrust", "trust_drop_possible"} else 0.46
    return TrustConfusionSignal(
        trust_state_bucket=trust,
        confusion_bucket=confusion,
        misunderstanding_risk_signal="likely" if misunderstanding == "high" else "possible" if misunderstanding in {"medium", "low"} else "none",
        misunderstanding_risk_bucket=misunderstanding,
        followup_pressure_risk="medium" if confusion in {"medium", "high"} else "low" if confusion == "mild" else "none",
        confidence=confidence,
        safe_summary=f"trust_confusion_{trust}_{confusion}",
    )


def extract_repair_signal(
    message: str,
    session: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> RepairSignal:
    _ = session, context
    if is_safety_sensitive(message, analysis):
        return RepairSignal(confidence=0.0, risk_flags=["safety_suppressed"], safe_summary="repair_safety_suppressed")

    folded = fold_text(message)
    if short_low_data(message):
        return RepairSignal(confidence=0.12, safe_summary="repair_low_data_neutral")

    correction_type = "none"
    if has_any(folded, ("bunu sen yazdin", "sen yazdin", "ben yazmadim")):
        correction_type = "assistant_misattributed_text"
    elif has_any(folded, ("ruyadan bahsetmedim", "ruya degil", "luxching degil", "luxdream degil", "yanlis mod")):
        correction_type = "wrong_lens"
    elif has_any(folded, ("metafor yapma", "terapi dili", "boyle konusma", "fazla duygusal")):
        correction_type = "wrong_tone"
    elif has_any(folded, ("yanlis bilgi", "dogru degil", "boyle degil")):
        correction_type = "wrong_fact"
    elif has_any(folded, ("cevap yarim kaldi", "kelime bitmeden", "kesildi", "yarim kaldin")):
        correction_type = "truncation_or_cutoff"
    elif has_any(folded, ("yanlis anladin", "ben onu demedim", "onu demek istemedim")):
        correction_type = "user_corrects_assistant"
    elif has_any(folded, ("ne demek istedin", "anlamadim", "belirsiz")):
        correction_type = "unclear_response"

    if correction_type == "none":
        return RepairSignal(confidence=0.18, safe_summary="repair_no_correction")

    urgency = "high" if correction_type in {"assistant_misattributed_text", "wrong_lens", "truncation_or_cutoff"} else "medium"
    return RepairSignal(
        correction_needed=True,
        correction_type_bucket=correction_type,
        repair_needed_signal="clarify" if correction_type == "unclear_response" else "acknowledge",
        repair_urgency_bucket=urgency,
        frustration_bucket="medium" if has_any(folded, ("kac kere", "yine", "zaman kaybetme")) else "low",
        response_satisfaction_hint="unsatisfied",
        confidence=0.82,
        safe_summary=f"repair_{correction_type}",
    )


def extract_answer_success_signal(
    message: str,
    session: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> AnswerSuccessSignal:
    _ = session, context
    if is_safety_sensitive(message, analysis):
        return AnswerSuccessSignal(confidence=0.0, risk_flags=["safety_suppressed"], safe_summary="answer_success_safety_suppressed")

    folded = fold_text(message)
    if short_low_data(message):
        return AnswerSuccessSignal(answer_success_bucket="unknown", confidence=0.16, safe_summary="answer_success_low_data_neutral")

    success_terms = ("harika", "super", "tam bu", "bekledigim bu", "dogru", "aynen", "guzel oldu", "calisti", "oldu")
    partial_terms = ("iyi ama", "guzel ama", "kismen", "biraz oldu")
    failure_terms = ("olmadi", "yine olmadi", "bos cevap", "zaman kaybetme", "beni anlamiyorsun", "ise yaramadi")
    frustration_high = ("kac kere soyledim", "beni anlamiyorsun", "zaman kaybetme")
    frustration_medium = ("yine olmadi", "bos cevap", "hala olmadi")

    bucket = "unknown"
    clarity = "unknown"
    progress = "unknown"
    if has_any(folded, failure_terms):
        bucket = "explicit_failure" if has_any(folded, ("olmadi", "ise yaramadi", "bos cevap")) else "likely_failure"
        clarity = "needs_more_clarity"
        progress = "blocked"
    elif has_any(folded, partial_terms):
        bucket = "partial_success"
        clarity = "needs_more_clarity"
        progress = "progressed"
    elif has_any(folded, success_terms):
        bucket = "likely_success"
        clarity = "clear"
        progress = "progressed"

    frustration = "none"
    if has_any(folded, frustration_high):
        frustration = "high"
    elif has_any(folded, frustration_medium):
        frustration = "medium"
    elif bucket in {"explicit_failure", "likely_failure"}:
        frustration = "mild"

    followup_pressure = "medium" if frustration in {"medium", "high"} else "low" if bucket in {"partial_success", "likely_failure"} else "none"
    confidence = 0.78 if bucket not in {"unknown"} else 0.24
    return AnswerSuccessSignal(
        answer_success_bucket=bucket,
        clarity_result_bucket=clarity,
        task_progress_bucket=progress,
        frustration_bucket=frustration,
        followup_pressure_risk=followup_pressure,
        confidence=confidence,
        safe_summary=f"answer_success_{bucket}_{frustration}",
    )


def build_micro_human_signal_bundle(
    message: str,
    session: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> MicroHumanSignalBundle:
    if is_safety_sensitive(message, analysis):
        return MicroHumanSignalBundle(
            confidence=0.0,
            risk_flags=["safety_suppressed"],
            safe_summary="micro_human_bridge_safety_suppressed",
        )

    micro_intent = extract_micro_intent_signal(message, session=session, analysis=analysis, context=context)
    trust_confusion = extract_trust_confusion_signal(message, session=session, analysis=analysis, context=context)
    repair = extract_repair_signal(message, session=session, analysis=analysis, context=context)
    answer_success = extract_answer_success_signal(message, session=session, analysis=analysis, context=context)
    confidences = [
        micro_intent.confidence,
        trust_confusion.confidence,
        repair.confidence,
        answer_success.confidence,
    ]
    bundle_conf = round(sum(clamp(x) for x in confidences) / max(1, len(confidences)), 4)
    flags: list[str] = []
    for part in (micro_intent, trust_confusion, repair, answer_success):
        for flag in part.risk_flags:
            if flag not in flags:
                flags.append(flag)
    summary = "micro_human_bridge_low_confidence_neutral" if bundle_conf < 0.35 else "micro_human_bridge_read_only_signal"
    return MicroHumanSignalBundle(
        micro_intent=micro_intent,
        trust_confusion=trust_confusion,
        repair=repair,
        answer_success=answer_success,
        confidence=bundle_conf,
        risk_flags=flags,
        safe_summary=summary,
    )
