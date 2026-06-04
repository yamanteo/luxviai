from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


VERSION = "practical_support_scaffold_v1"
SIGNAL_NAMES = (
    "life_command",
    "one_step_action",
    "hidden_load",
    "regret_preview",
    "professional_turkish",
    "chaos_compression",
    "emotion_task_split",
    "lux_shortcut",
    "gentle_reminder",
)
SAFETY_LEVELS = {"sensitive", "high_risk", "crisis"}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def clamp(value: Any, lo: float = 0.0, hi: float = 1.0, default: float = 0.0) -> float:
    return max(lo, min(hi, safe_float(value, default)))


def _fold(value: str) -> str:
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
    return str(value or "").translate(table).lower()


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def _safe_analysis(analysis: dict[str, Any] | None) -> dict[str, Any]:
    return analysis if isinstance(analysis, dict) else {}


def _safety_suppressed(analysis: dict[str, Any] | None, context: dict[str, Any] | None = None) -> bool:
    a = _safe_analysis(analysis)
    c = context if isinstance(context, dict) else {}
    safety = a.get("safety_layer", {}) if isinstance(a.get("safety_layer"), dict) else {}
    human_risk = c.get("human_risk", {}) if isinstance(c.get("human_risk"), dict) else {}
    risk_level = str(human_risk.get("safety_level", safety.get("crisis_level", "normal")) or "normal").strip().lower()
    return bool(
        a.get("crisis_risk")
        or safety.get("route_to_emergency")
        or safety.get("needs_gentle_check")
        or risk_level in SAFETY_LEVELS
    )


def _confidence_bucket(confidence: float) -> str:
    c = clamp(confidence)
    if c >= 0.75:
        return "high"
    if c >= 0.55:
        return "medium"
    if c > 0.0:
        return "low"
    return "none"


@dataclass(frozen=True)
class PracticalSupportSignal:
    name: str
    active: bool = False
    candidate: bool = False
    confidence: float = 0.0
    intent_bucket: str = "none"
    safe_summary: str = "neutral"
    suppressed: bool = False
    suppression_reason: str = "none"
    telemetry_key: str = "none"
    evidence_count: int = 0
    risk_flags: list[str] = field(default_factory=list)

    @classmethod
    def neutral(cls, name: str, summary: str = "neutral") -> "PracticalSupportSignal":
        return cls(
            name=name,
            active=False,
            candidate=False,
            confidence=0.0,
            intent_bucket="none",
            safe_summary=summary,
            suppressed=False,
            suppression_reason="none",
            telemetry_key=f"{name}_neutral_count",
            evidence_count=0,
            risk_flags=[],
        )

    @classmethod
    def suppressed_by_safety(cls, name: str) -> "PracticalSupportSignal":
        return cls(
            name=name,
            active=False,
            candidate=False,
            confidence=0.0,
            intent_bucket="none",
            safe_summary="practical_support_safety_suppressed",
            suppressed=True,
            suppression_reason="safety",
            telemetry_key=f"{name}_safety_suppressed_count",
            evidence_count=0,
            risk_flags=["safety_suppressed"],
        )

    def to_safe_dict(self) -> dict[str, Any]:
        confidence = round(clamp(self.confidence), 4)
        return {
            "name": self.name,
            "active": False,
            "candidate": bool(self.candidate and not self.suppressed),
            "confidence": confidence,
            "confidence_bucket": _confidence_bucket(confidence),
            "intent_bucket": str(self.intent_bucket or "none"),
            "safe_summary": str(self.safe_summary or "neutral"),
            "suppressed": bool(self.suppressed),
            "suppression_reason": str(self.suppression_reason or "none"),
            "telemetry_key": str(self.telemetry_key or "none"),
            "evidence_count": int(max(0, self.evidence_count)),
            "risk_flags": [str(x) for x in self.risk_flags[:8]],
        }


@dataclass(frozen=True)
class LifeCommandSignal(PracticalSupportSignal):
    name: str = "life_command"


@dataclass(frozen=True)
class OneStepActionSignal(PracticalSupportSignal):
    name: str = "one_step_action"


@dataclass(frozen=True)
class HiddenLoadSignal(PracticalSupportSignal):
    name: str = "hidden_load"


@dataclass(frozen=True)
class RegretPreviewSignal(PracticalSupportSignal):
    name: str = "regret_preview"


@dataclass(frozen=True)
class ProfessionalTurkishSignal(PracticalSupportSignal):
    name: str = "professional_turkish"


@dataclass(frozen=True)
class ChaosCompressionSignal(PracticalSupportSignal):
    name: str = "chaos_compression"


@dataclass(frozen=True)
class EmotionTaskSplitSignal(PracticalSupportSignal):
    name: str = "emotion_task_split"


@dataclass(frozen=True)
class LuxShortcutSignal(PracticalSupportSignal):
    name: str = "lux_shortcut"


@dataclass(frozen=True)
class GentleReminderSignal(PracticalSupportSignal):
    name: str = "gentle_reminder"


SIGNAL_CLASSES = {
    "life_command": LifeCommandSignal,
    "one_step_action": OneStepActionSignal,
    "hidden_load": HiddenLoadSignal,
    "regret_preview": RegretPreviewSignal,
    "professional_turkish": ProfessionalTurkishSignal,
    "chaos_compression": ChaosCompressionSignal,
    "emotion_task_split": EmotionTaskSplitSignal,
    "lux_shortcut": LuxShortcutSignal,
    "gentle_reminder": GentleReminderSignal,
}


@dataclass(frozen=True)
class PracticalSupportBundle:
    life_command: LifeCommandSignal
    one_step_action: OneStepActionSignal
    hidden_load: HiddenLoadSignal
    regret_preview: RegretPreviewSignal
    professional_turkish: ProfessionalTurkishSignal
    chaos_compression: ChaosCompressionSignal
    emotion_task_split: EmotionTaskSplitSignal
    lux_shortcut: LuxShortcutSignal
    gentle_reminder: GentleReminderSignal
    active: bool = False
    context_injected: bool = False
    behavior_started: bool = False
    safe_summary: str = "practical_support_neutral_scaffold"
    version: str = VERSION

    @classmethod
    def neutral(cls, summary: str = "practical_support_neutral_scaffold") -> "PracticalSupportBundle":
        return cls(
            life_command=LifeCommandSignal.neutral("life_command"),
            one_step_action=OneStepActionSignal.neutral("one_step_action"),
            hidden_load=HiddenLoadSignal.neutral("hidden_load"),
            regret_preview=RegretPreviewSignal.neutral("regret_preview"),
            professional_turkish=ProfessionalTurkishSignal.neutral("professional_turkish"),
            chaos_compression=ChaosCompressionSignal.neutral("chaos_compression"),
            emotion_task_split=EmotionTaskSplitSignal.neutral("emotion_task_split"),
            lux_shortcut=LuxShortcutSignal.neutral("lux_shortcut"),
            gentle_reminder=GentleReminderSignal.neutral("gentle_reminder"),
            safe_summary=summary,
        )

    def to_safe_dict(self) -> dict[str, Any]:
        signals = {
            "life_command": self.life_command.to_safe_dict(),
            "one_step_action": self.one_step_action.to_safe_dict(),
            "hidden_load": self.hidden_load.to_safe_dict(),
            "regret_preview": self.regret_preview.to_safe_dict(),
            "professional_turkish": self.professional_turkish.to_safe_dict(),
            "chaos_compression": self.chaos_compression.to_safe_dict(),
            "emotion_task_split": self.emotion_task_split.to_safe_dict(),
            "lux_shortcut": self.lux_shortcut.to_safe_dict(),
            "gentle_reminder": self.gentle_reminder.to_safe_dict(),
        }
        candidate_count = sum(1 for s in signals.values() if bool(s.get("candidate")))
        safety_suppressed_count = sum(1 for s in signals.values() if str(s.get("suppression_reason")) == "safety")
        return {
            "active": False,
            "context_injected": False,
            "behavior_started": False,
            "safe_summary": str(self.safe_summary or "practical_support_neutral_scaffold"),
            "version": self.version,
            "candidate_count": int(candidate_count),
            "safety_suppressed_count": int(safety_suppressed_count),
            "context_injection_count": 0,
            "signals": signals,
            "telemetry": {
                "practical_support_presence_count": 1,
                "practical_support_candidate_count": int(candidate_count),
                "practical_support_context_injection_count": 0,
                "practical_support_active_behavior_count": 0,
                "practical_support_safety_suppressed_count": int(safety_suppressed_count),
            },
        }


def neutral_practical_support_bundle() -> PracticalSupportBundle:
    return PracticalSupportBundle.neutral()


def _candidate_signal(
    cls: type[PracticalSupportSignal],
    *,
    confidence: float,
    intent_bucket: str,
    evidence_count: int,
) -> PracticalSupportSignal:
    if confidence < 0.55:
        return cls.neutral(cls().name, summary="practical_support_low_confidence_neutral")
    name = cls().name
    return cls(
        active=False,
        candidate=True,
        confidence=round(clamp(confidence), 4),
        intent_bucket=intent_bucket,
        safe_summary=f"{name}_passive_candidate",
        suppressed=False,
        suppression_reason="none",
        telemetry_key=f"{name}_candidate_count",
        evidence_count=evidence_count,
        risk_flags=[],
    )


def _signal_from_keywords(
    name: str,
    text: str,
    keyword_groups: tuple[tuple[str, ...], ...],
    intent_bucket: str,
) -> PracticalSupportSignal:
    cls = SIGNAL_CLASSES[name]
    hits = sum(1 for group in keyword_groups if _contains_any(text, group))
    confidence = min(0.9, 0.34 + 0.22 * hits) if hits else 0.0
    return _candidate_signal(cls, confidence=confidence, intent_bucket=intent_bucket, evidence_count=hits)


def build_practical_support_bundle(
    message: str,
    *,
    analysis: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> PracticalSupportBundle:
    text = _fold(message)
    if not text.strip():
        return neutral_practical_support_bundle()
    if _safety_suppressed(analysis, context):
        return PracticalSupportBundle(
            life_command=LifeCommandSignal.suppressed_by_safety("life_command"),
            one_step_action=OneStepActionSignal.suppressed_by_safety("one_step_action"),
            hidden_load=HiddenLoadSignal.suppressed_by_safety("hidden_load"),
            regret_preview=RegretPreviewSignal.suppressed_by_safety("regret_preview"),
            professional_turkish=ProfessionalTurkishSignal.suppressed_by_safety("professional_turkish"),
            chaos_compression=ChaosCompressionSignal.suppressed_by_safety("chaos_compression"),
            emotion_task_split=EmotionTaskSplitSignal.suppressed_by_safety("emotion_task_split"),
            lux_shortcut=LuxShortcutSignal.suppressed_by_safety("lux_shortcut"),
            gentle_reminder=GentleReminderSignal.suppressed_by_safety("gentle_reminder"),
            safe_summary="practical_support_safety_suppressed",
        )

    has_task = _contains_any(text, ("proje", "gorev", "is", "para", "cv", "basvuru", "mail", "rapor", "teknik", "sorun"))
    has_load = _contains_any(text, ("kafam karisti", "ust uste", "gerdi", "bunaldim", "yuk", "sikistim"))
    has_fast_tool = _contains_any(text, ("codex", "render", "github", "terminal", "git", "deploy"))
    sentence_like_chunks = len([x for x in re.split(r"[.!?\n,;]+", text) if x.strip()])

    life_conf = 0.0
    life_hits = 0
    if has_task:
        life_conf += 0.32
        life_hits += 1
    if has_load:
        life_conf += 0.26
        life_hits += 1
    if sentence_like_chunks >= 3:
        life_conf += 0.18
        life_hits += 1

    one_step_conf = 0.0
    one_step_hits = 0
    if _contains_any(text, ("tek adim", "simdi ne", "ilk adim", "one step")):
        one_step_conf += 0.58
        one_step_hits += 1
    if has_fast_tool:
        one_step_conf += 0.22
        one_step_hits += 1

    hidden_load_conf = 0.0
    hidden_load_hits = 0
    if has_load:
        hidden_load_conf += 0.48
        hidden_load_hits += 1
    if has_task or has_fast_tool:
        hidden_load_conf += 0.18
        hidden_load_hits += 1

    split_conf = 0.0
    split_hits = 0
    if has_task and has_load:
        split_conf += 0.58
        split_hits += 2
    if _contains_any(text, ("duygu", "gorev", "ayir", "ayristir")):
        split_conf += 0.22
        split_hits += 1

    return PracticalSupportBundle(
        life_command=_candidate_signal(
            LifeCommandSignal,
            confidence=life_conf,
            intent_bucket="task_translation",
            evidence_count=life_hits,
        ),
        one_step_action=_candidate_signal(
            OneStepActionSignal,
            confidence=one_step_conf,
            intent_bucket="one_clear_next_action",
            evidence_count=one_step_hits,
        ),
        hidden_load=_candidate_signal(
            HiddenLoadSignal,
            confidence=hidden_load_conf,
            intent_bucket="load_aware_practical_support",
            evidence_count=hidden_load_hits,
        ),
        regret_preview=_signal_from_keywords(
            "regret_preview",
            text,
            (("pisman", "pismanlik", "rahatlar miyim"), ("gonderirsem", "karar", "secim")),
            "regret_relief_preview",
        ),
        professional_turkish=_signal_from_keywords(
            "professional_turkish",
            text,
            (("cv dili", "profesyonel", "resmi", "premium yap"), ("mail", "cv", "basvuru", "rapor")),
            "professional_language_cleanup",
        ),
        chaos_compression=_signal_from_keywords(
            "chaos_compression",
            text,
            (("toparla", "ozetle", "sikistir", "duzenle"), ("asil sorun", "sonraki adim", "engel")),
            "chaos_to_core_parts",
        ),
        emotion_task_split=_candidate_signal(
            EmotionTaskSplitSignal,
            confidence=split_conf,
            intent_bucket="emotion_task_separation",
            evidence_count=split_hits,
        ),
        lux_shortcut=_signal_from_keywords(
            "lux_shortcut",
            text,
            (("tek adim", "toparla", "codex modu", "cv dili", "premium yap"),),
            "shortcut_phrase_candidate",
        ),
        gentle_reminder=_signal_from_keywords(
            "gentle_reminder",
            text,
            (("hatirlat", "kalan is", "yarim kalan", "dun kalan"), ("baski yapma", "nazik", "sucluluk")),
            "gentle_reminder_candidate",
        ),
    )


def to_safe_dict(bundle: PracticalSupportBundle | dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(bundle, PracticalSupportBundle):
        return bundle.to_safe_dict()
    if isinstance(bundle, dict):
        safe = neutral_practical_support_bundle().to_safe_dict()
        if isinstance(bundle.get("signals"), dict):
            safe["signals"] = bundle["signals"]
        return safe
    return neutral_practical_support_bundle().to_safe_dict()
