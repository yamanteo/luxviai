from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .behavior_policy import BehaviorPolicyManager
from .conversation_analyzer import ConversationAnalyzer
from .context_builder import LearningContextBuilder
from .fine_tune_builder import FineTuneCandidateStore
from .group1_layers import Group1LayerBridge
from .global_learning import GlobalLearningStore
from .human_risk_healing import HumanRiskHealingEngine
from .hybrid_optimizer import HybridOptimizer
from .io_utils import append_jsonl, load_json
from .micro_signal_engine import MicroSignalEngine
from .memory_layer import MemoryLayerEngine
from .group2_layers import Group2LayerBridge
from .group3_signals import Group3Bundle
from .group4_signals import Group4Bundle
from .emotional_graph_layer import EmotionalGraphLayerEngine
from .time_ecology_layer import TimeEcologyLayerEngine
from .cultural_epistemic_layer import CulturalEpistemicLayerEngine
from .reflection_layer import ReflectionLayerEngine
from .personal_language_dna import PersonalLanguageDNAEngine
from .personal_learning import PersonalLearningStore
from .performance_tracker import PerformanceTracker
from .quality_evaluator import QualityEvaluator
from .symbolic_layer import SymbolicLayerEngine
from .dream_layer import DreamLayerEngine
from .existential_layer import ExistentialLayerEngine
from .storage_rotation import StorageRotationEngine
from .telemetry import TelemetryEngine
from .lens_guard import resolve_lens_precedence

try:
    from .micro_human_signal_bridge import MicroHumanSignalBundle, build_micro_human_signal_bundle
except Exception:  # pragma: no cover - optional Step-1 hook must never break chat.
    MicroHumanSignalBundle = None  # type: ignore[assignment]
    build_micro_human_signal_bundle = None  # type: ignore[assignment]

try:
    from .lux_language_sense import (
        LuxLanguageSenseBundle,
        build_lux_language_sense_bundle,
        neutral_lux_language_sense_bundle,
    )
except Exception:  # pragma: no cover - optional Step-1 hook must never break chat.
    build_lux_language_sense_bundle = None  # type: ignore[assignment]
    LuxLanguageSenseBundle = None  # type: ignore[assignment]
    neutral_lux_language_sense_bundle = None  # type: ignore[assignment]

try:
    from .practical_support_layers import (
        PracticalSupportBundle,
        build_practical_support_bundle,
        neutral_practical_support_bundle,
    )
except Exception:  # pragma: no cover - optional passive scaffold must never break chat.
    PracticalSupportBundle = None  # type: ignore[assignment]
    build_practical_support_bundle = None  # type: ignore[assignment]
    neutral_practical_support_bundle = None  # type: ignore[assignment]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, safe_float(v, lo)))


def _language_bucket(message: str) -> str:
    text = str(message or "").strip()
    if not text:
        return "unknown"
    has_latin = any(("a" <= ch.lower() <= "z") for ch in text if ch.isalpha())
    has_arabic_script = any("\u0600" <= ch <= "\u06FF" for ch in text)
    has_cyrillic = any("\u0400" <= ch <= "\u04FF" for ch in text)
    has_cjk = any("\u4E00" <= ch <= "\u9FFF" for ch in text)
    if has_arabic_script:
        return "arabic_script"
    if has_cyrillic:
        return "cyrillic"
    if has_cjk:
        return "cjk"
    if has_latin:
        low = text.lower()
        tr_hits = sum(1 for token in (" ve ", " bir ", " bu ", " için ", " mi", " mı", "ğ", "ş", "ı", "ö", "ç", "ü") if token in low)
        en_hits = sum(1 for token in (" the ", " and ", " for ", " is ", " are ", "how ", "what ", "can ") if token in low)
        if tr_hits > en_hits:
            return "latin_tr_like"
        if en_hits > tr_hits:
            return "latin_en_like"
        return "latin_other"
    return "unknown"


def _response_length_bucket(text: str) -> str:
    ln = len(str(text or ""))
    if ln < 120:
        return "xs"
    if ln < 350:
        return "s"
    if ln < 800:
        return "m"
    if ln < 1600:
        return "l"
    return "xl"


def _half_step_type_bucket(response_mode: dict[str, Any]) -> str:
    if not isinstance(response_mode, dict) or not response_mode:
        return "none"
    use_one_step = bool(response_mode.get("use_one_step"))
    repair_first = bool(response_mode.get("repair_first"))
    answer_length = str(response_mode.get("answer_length", "")).strip().lower()
    if use_one_step and repair_first:
        return "one_step_repair"
    if use_one_step:
        return "one_step"
    if repair_first:
        return "repair_first"
    if answer_length == "short":
        return "short"
    if answer_length == "deep":
        return "deep"
    return "balanced"


def _utility_metaphor_leakage_flag(*, assistant_response: str, selected_lens: str) -> int:
    if str(selected_lens or "").strip().lower() != "technical":
        return 0
    low = str(assistant_response or "").lower()
    metaphor_markers = (
        "ayna",
        "golge",
        "ruya",
        "kalp",
        "kader",
        "evren",
        "simge",
        "sembol",
        "astro",
        "fal",
    )
    return 1 if any(m in low for m in metaphor_markers) else 0


def _micro_behavior_prompt_hint(bundle: dict[str, Any]) -> str:
    hint = bundle.get("repair_clarity_hint", {}) if isinstance(bundle, dict) else {}
    if not isinstance(hint, dict):
        return ""
    if safe_float(hint.get("confidence"), 0.0) < 0.7:
        return ""
    if hint.get("risk_flags"):
        return ""

    parts: list[str] = []
    if bool(hint.get("should_acknowledge_correction")):
        parts.append("kısa kabul et, savunmaya geçme ve hatayı kullanıcıya atfetme")
    if bool(hint.get("should_clarify")):
        parts.append("cevabı daha net ve sade yeniden kur")
    if bool(hint.get("should_reduce_questions")):
        parts.append("soru sayısını azalt; mümkünse soru yerine kısa next action ver")
    if bool(hint.get("should_be_more_direct")):
        parts.append("direkt konuya gir")
    if bool(hint.get("should_avoid_lens_offer")):
        parts.append("bu dönüşte Luxdream/Luxching/LuxMirror veya lens önerisi yapma")
    if bool(hint.get("should_avoid_metaphor")):
        parts.append("metafor kullanma")
    if bool(hint.get("should_repair_truncation")):
        parts.append("yarım kalan ifadeyi net tamamla")
    if not parts:
        return ""
    return "Onarım/netlik modu: " + "; ".join(parts[:4]) + "."


def _micro_behavior_telemetry_counts(bundle: dict[str, Any]) -> dict[str, int]:
    hint = bundle.get("repair_clarity_hint", {}) if isinstance(bundle, dict) else {}
    if not isinstance(hint, dict):
        return {}
    conf = safe_float(hint.get("confidence"), 0.0)
    risk_flags = hint.get("risk_flags") if isinstance(hint.get("risk_flags"), list) else []
    safe_summary = str(hint.get("safe_summary", "") or "").strip().lower()
    emitted = 1 if conf >= 0.70 and not risk_flags and safe_summary not in {"micro_behavior_hint_low_confidence_suppressed", "micro_behavior_hint_low_data_suppressed", "micro_behavior_hint_safety_suppressed"} else 0
    safety_suppressed = 1 if risk_flags or safe_summary == "micro_behavior_hint_safety_suppressed" else 0
    low_conf_suppressed = 1 if safe_summary in {"micro_behavior_hint_low_confidence_suppressed", "micro_behavior_hint_low_data_suppressed"} else 0
    suppressed = 1 if emitted == 0 else 0
    return {
        "micro_behavior_hint_emission_count": emitted,
        "micro_behavior_hint_suppressed_count": suppressed,
        "correction_ack_hint_count": 1 if emitted and bool(hint.get("should_acknowledge_correction")) else 0,
        "clarification_hint_count": 1 if emitted and bool(hint.get("should_clarify")) else 0,
        "reduce_questions_hint_count": 1 if emitted and bool(hint.get("should_reduce_questions")) else 0,
        "directness_hint_count": 1 if emitted and bool(hint.get("should_be_more_direct")) else 0,
        "avoid_lens_offer_hint_count": 1 if emitted and bool(hint.get("should_avoid_lens_offer")) else 0,
        "truncation_repair_hint_count": 1 if emitted and bool(hint.get("should_repair_truncation")) else 0,
        "low_confidence_behavior_suppressed_count": low_conf_suppressed,
        "safety_behavior_suppressed_count": safety_suppressed,
    }


def _bucket_from(bundle: dict[str, Any], section: str, key: str, default: str = "unknown") -> str:
    part = bundle.get(section, {}) if isinstance(bundle, dict) else {}
    if not isinstance(part, dict):
        return default
    value = str(part.get(key, default) or default).strip().lower()
    return value or default


def _micro_bridge_telemetry_fields(bundle: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, dict) or not bundle:
        return {}
    summary = str(bundle.get("safe_summary", "") or "").strip().lower()
    risk_flags = bundle.get("risk_flags") if isinstance(bundle.get("risk_flags"), list) else []
    micro_intent = bundle.get("micro_intent", {}) if isinstance(bundle.get("micro_intent"), dict) else {}
    repair = bundle.get("repair", {}) if isinstance(bundle.get("repair"), dict) else {}
    answer_success = bundle.get("answer_success", {}) if isinstance(bundle.get("answer_success"), dict) else {}
    trust_confusion = bundle.get("trust_confusion", {}) if isinstance(bundle.get("trust_confusion"), dict) else {}

    micro_intent_conf = safe_float(micro_intent.get("confidence"), 0.0)
    repair_needed = bool(repair.get("correction_needed"))
    safety_suppressed = 1 if risk_flags or summary == "micro_human_bridge_safety_suppressed" else 0
    low_conf_suppressed = 1 if summary == "micro_human_bridge_low_confidence_neutral" else 0
    return {
        "micro_bridge_presence_count": 1,
        "micro_bridge_neutral_count": 1 if summary in {"micro_human_bridge_neutral", "micro_human_bridge_low_confidence_neutral"} else 0,
        "micro_bridge_context_injection_count": 0,
        "micro_bridge_low_confidence_suppressed_count": low_conf_suppressed,
        "micro_intent_signal_count": 1 if micro_intent_conf >= 0.35 and safety_suppressed == 0 else 0,
        "intent_clarity_bucket": _bucket_from(bundle, "micro_intent", "intent_clarity_bucket"),
        "request_type_bucket": _bucket_from(bundle, "micro_intent", "request_type_bucket"),
        "confusion_bucket": _bucket_from(bundle, "trust_confusion", "confusion_bucket", "none"),
        "trust_state_bucket": _bucket_from(bundle, "trust_confusion", "trust_state_bucket"),
        "misunderstanding_risk_bucket": _bucket_from(bundle, "trust_confusion", "misunderstanding_risk_bucket", "none"),
        "repair_signal_count": 1 if repair_needed and safety_suppressed == 0 else 0,
        "correction_type_bucket": _bucket_from(bundle, "repair", "correction_type_bucket", "none"),
        "answer_success_bucket": _bucket_from(bundle, "answer_success", "answer_success_bucket"),
        "frustration_bucket": _bucket_from(bundle, "answer_success", "frustration_bucket", "none"),
        "followup_pressure_risk_bucket": (
            str(answer_success.get("followup_pressure_risk") or trust_confusion.get("followup_pressure_risk") or "none")
            .strip()
            .lower()
            or "none"
        ),
        "micro_low_confidence_suppressed_count": low_conf_suppressed,
        "micro_sensitive_suppressed_count": safety_suppressed,
    }


@dataclass
class LearningPipeline:
    base_dir: Path

    def __post_init__(self) -> None:
        self.policies = BehaviorPolicyManager(self.base_dir)
        self.performance_tracker = PerformanceTracker(self.base_dir)
        self.context_builder = LearningContextBuilder(self.base_dir, self.policies, self.performance_tracker)
        self.personal = PersonalLearningStore(self.base_dir)
        self.global_store = GlobalLearningStore(self.base_dir)
        self.micro = MicroSignalEngine()
        self.conversation_analyzer = ConversationAnalyzer()
        self.fine = FineTuneCandidateStore(self.base_dir)
        self.group1 = Group1LayerBridge()
        self.group2 = Group2LayerBridge()
        self.group3_symbolic = SymbolicLayerEngine()
        self.group3_dream = DreamLayerEngine()
        self.group3_existential = ExistentialLayerEngine()
        self.group3_memory = MemoryLayerEngine()
        self.group4_emotional_graph = EmotionalGraphLayerEngine()
        self.group4_time_ecology = TimeEcologyLayerEngine()
        self.group4_cultural_epistemic = CulturalEpistemicLayerEngine()
        self.group4_reflection = ReflectionLayerEngine()
        self.quality = QualityEvaluator()
        self.hybrid = HybridOptimizer(self.quality)
        self.language_dna = PersonalLanguageDNAEngine(self.base_dir)
        self.human_risk = HumanRiskHealingEngine(self.base_dir)
        self.telemetry = TelemetryEngine(self.base_dir)
        self.storage_rotation = StorageRotationEngine(self.base_dir)

    def _build_micro_human_bundle(
        self,
        message: str = "",
        analysis: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> Any:
        if MicroHumanSignalBundle is None:
            return {}
        if build_micro_human_signal_bundle is None:
            return MicroHumanSignalBundle.neutral().to_safe_dict()
        try:
            return build_micro_human_signal_bundle(
                message or "",
                session=session or {},
                analysis=analysis or {},
                context=context or {},
            ).to_safe_dict()
        except Exception:
            return MicroHumanSignalBundle.neutral().to_safe_dict()

    def _build_group3_bundle(
        self,
        *,
        memory_read: Any,
        symbolic: Any,
        dream: Any,
        existential: Any,
        memory_write_candidate: Any,
    ) -> Group3Bundle:
        parts = [
            safe_float(getattr(memory_read, "confidence", 0.0), 0.0),
            safe_float(getattr(symbolic, "confidence", 0.0), 0.0),
            safe_float(getattr(dream, "confidence", 0.0), 0.0),
            safe_float(getattr(existential, "confidence", 0.0), 0.0),
            safe_float(getattr(memory_write_candidate, "confidence", 0.0), 0.0),
        ]
        bundle_conf = round(sum(parts) / max(1, len(parts)), 4)
        risk_flags: list[str] = []
        for part in (memory_read, symbolic, dream, existential, memory_write_candidate):
            for flag in getattr(part, "risk_flags", []) or []:
                f = str(flag).strip()
                if f and f not in risk_flags:
                    risk_flags.append(f)
                if len(risk_flags) >= 10:
                    break
            if len(risk_flags) >= 10:
                break
        return Group3Bundle(
            memory_read=memory_read,
            symbolic=symbolic,
            dream=dream,
            existential=existential,
            memory_write_candidate=memory_write_candidate,
            safe_summary="group3_safe_signal_bundle",
            confidence=bundle_conf,
            risk_flags=risk_flags,
        )

    def _build_group4_bundle(
        self,
        *,
        emotional_graph: Any,
        time_ecology: Any,
        cultural_epistemic: Any,
        reflection: Any,
    ) -> Group4Bundle:
        parts = [
            safe_float(getattr(emotional_graph, "confidence", 0.0), 0.0),
            safe_float(getattr(time_ecology, "confidence", 0.0), 0.0),
            safe_float(getattr(cultural_epistemic, "confidence", 0.0), 0.0),
            safe_float(getattr(reflection, "confidence", 0.0), 0.0),
        ]
        bundle_conf = round(sum(parts) / max(1, len(parts)), 4)
        risk_flags: list[str] = []
        for part in (emotional_graph, time_ecology, cultural_epistemic, reflection):
            for flag in getattr(part, "risk_flags", []) or []:
                text = str(flag).strip()
                if not text or text in risk_flags:
                    continue
                risk_flags.append(text)
                if len(risk_flags) >= 10:
                    break
            if len(risk_flags) >= 10:
                break
        return Group4Bundle(
            emotional_graph=emotional_graph,
            time_ecology=time_ecology,
            cultural_epistemic=cultural_epistemic,
            reflection=reflection,
            safe_summary="group4_safe_signal_bundle",
            confidence=bundle_conf,
            risk_flags=risk_flags,
        )

    def _build_lux_language_sense_bundle(
        self,
        message: str = "",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if build_lux_language_sense_bundle is not None:
            try:
                return build_lux_language_sense_bundle(message or "", context=context or {}).to_safe_dict()
            except Exception:
                pass
        if neutral_lux_language_sense_bundle is not None:
            try:
                return neutral_lux_language_sense_bundle().to_safe_dict()
            except Exception:
                pass
        if LuxLanguageSenseBundle is not None:
            try:
                return LuxLanguageSenseBundle.neutral().to_safe_dict()
            except Exception:
                pass
        return {
            "active": False,
            "confidence": 0.0,
            "risk_flags": [],
            "safe_summary": "lux_language_sense_neutral_unavailable",
            "version": "13_step1_optional_hook",
        }

    def _build_practical_support_bundle(
        self,
        message: str = "",
        analysis: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if build_practical_support_bundle is not None:
            try:
                return build_practical_support_bundle(message or "", analysis=analysis or {}, context=context or {}).to_safe_dict()
            except Exception:
                pass
        if neutral_practical_support_bundle is not None:
            try:
                return neutral_practical_support_bundle().to_safe_dict()
            except Exception:
                pass
        if PracticalSupportBundle is not None:
            try:
                return PracticalSupportBundle.neutral().to_safe_dict()
            except Exception:
                pass
        return {
            "active": False,
            "context_injected": False,
            "behavior_started": False,
            "safe_summary": "practical_support_neutral_unavailable",
            "version": "practical_support_scaffold_unavailable",
            "candidate_count": 0,
            "safety_suppressed_count": 0,
            "context_injection_count": 0,
            "signals": {},
            "telemetry": {
                "practical_support_presence_count": 1,
                "practical_support_candidate_count": 0,
                "practical_support_context_injection_count": 0,
                "practical_support_active_behavior_count": 0,
                "practical_support_safety_suppressed_count": 0,
            },
        }

    def ensure_foundation(self, user_id: str) -> None:
        self.personal.ensure_user_files(user_id)
        self.global_store.ensure_global_files()
        self.fine.ensure_files()
        self.telemetry.ensure_file()
        self.storage_rotation.ensure_foundation()
        _ = self.policies.load_global_policy()
        _ = self.policies.load_user_policy(user_id)
        self.language_dna.ensure_file(user_id)
        self.human_risk.ensure_files(user_id)
        if not self.policies.global_policy_path().exists():
            self.policies.save_global_policy(self.policies.default_global_policy())
        if not self.policies.user_policy_path(user_id).exists():
            self.policies.save_user_policy(user_id, self.policies.default_user_policy())

    def build_live_context(
        self,
        user_id: str,
        user_message: str,
        analysis: dict[str, Any],
        mode: str,
        *,
        profile: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
        max_items: int = 12,
    ) -> dict[str, Any]:
        self.ensure_foundation(user_id)
        try:
            micro = self.micro.analyze(user_message)
            conv_analysis = self.conversation_analyzer.analyze_conversation(
                user_id=user_id,
                user_message=user_message,
                assistant_reply=None,
                existing_analysis=analysis,
                session=session or {},
                profile=profile or {},
                micro_signals=micro,
            )
            language_probe = self.language_dna.build_language_context(user_id=user_id, message=user_message)
            risk_preview = self.human_risk.analyze_human_risk(
                user_id=user_id,
                message=user_message,
                existing_analysis=analysis,
                micro_signals=micro,
                conversation_analysis=conv_analysis,
            )
            group3_profile = dict(profile or {})
            if not isinstance(group3_profile.get("memory_garden"), list):
                existing_garden = load_json(self.base_dir / "data" / "users" / user_id / "memory_garden.json", [])
                if isinstance(existing_garden, list):
                    group3_profile["memory_garden"] = existing_garden
            # Group-3 Step-1 scaffold order (read-only / no durable writes):
            # 1) memory read, 2) symbolic, 3) dream, 4) existential, 5) memory write candidate.
            group3_memory_read = self.group3_memory.read_memory_signals(
                user_message,
                profile=group3_profile,
                session=session or {},
            )
            group3_symbolic = self.group3_symbolic.extract_symbolic_signal(
                user_message,
                analysis=analysis,
                profile=group3_profile,
                session=session or {},
            )
            group3_dream = self.group3_dream.extract_dream_signal(
                user_message,
                analysis=analysis,
                profile=group3_profile,
                session=session or {},
            )
            group3_existential = self.group3_existential.extract_existential_signal(
                user_message,
                analysis=analysis,
                profile=group3_profile,
                session=session or {},
            )
            group3_memory_write = self.group3_memory.propose_memory_write(
                user_message,
                group3_memory_read,
                analysis=analysis,
                safety=(analysis.get("safety_layer") if isinstance(analysis.get("safety_layer"), dict) else {}),
            )
            group3_bundle = self._build_group3_bundle(
                memory_read=group3_memory_read,
                symbolic=group3_symbolic,
                dream=group3_dream,
                existential=group3_existential,
                memory_write_candidate=group3_memory_write,
            )
            group4_emotional_graph = self.group4_emotional_graph.extract_emotional_graph_signal(
                user_message,
                analysis=analysis,
                profile=profile or {},
                session=session or {},
            )
            group4_time_ecology = self.group4_time_ecology.extract_time_ecology_signal(
                user_message,
                analysis=analysis,
                profile=profile or {},
                session=session or {},
            )
            group4_cultural_epistemic = self.group4_cultural_epistemic.extract_cultural_epistemic_signal(
                user_message,
                analysis=analysis,
                profile=profile or {},
                session=session or {},
            )
            group4_reflection = self.group4_reflection.extract_reflection_signal(
                user_message,
                analysis=analysis,
                profile=profile or {},
                session=session or {},
            )
            group4_bundle = self._build_group4_bundle(
                emotional_graph=group4_emotional_graph,
                time_ecology=group4_time_ecology,
                cultural_epistemic=group4_cultural_epistemic,
                reflection=group4_reflection,
            )
            micro_human_bundle = self._build_micro_human_bundle(
                user_message,
                analysis=analysis,
                session=session or {},
                context={"mode": mode, "profile": profile or {}},
            )
            lux_language_sense_bundle = self._build_lux_language_sense_bundle(
                user_message,
                context={"mode": mode, "session": session or {}},
            )
            practical_support_bundle = self._build_practical_support_bundle(
                user_message,
                analysis=analysis,
                context={"mode": mode, "session": session or {}, "human_risk": risk_preview},
            )
            live = self.context_builder.build_live_context(
                user_id=user_id,
                message=user_message,
                micro_signals=micro,
                conversation_analysis=conv_analysis,
                profile=profile or {},
                session=session or {},
                max_items=max_items,
                language_context=language_probe,
                human_risk_signal=risk_preview,
                group3_bundle=group3_bundle.to_safe_dict(),
                group4_bundle=group4_bundle.to_safe_dict(),
                micro_human_bundle=micro_human_bundle,
                lux_language_sense_bundle=lux_language_sense_bundle,
            )
            lux_language_sense_meta = (
                live.get("lux_language_sense_meta", {})
                if isinstance(live.get("lux_language_sense_meta"), dict)
                else {}
            )
            self.telemetry.record_lux_language_sense_hook(
                active=bool(lux_language_sense_meta.get("active", False)),
                context_injected=bool(lux_language_sense_meta.get("context_injected", False)),
                low_confidence_suppressed=bool(lux_language_sense_meta.get("low_confidence_suppressed", False)),
                bundle=lux_language_sense_bundle,
            )
            policy_ctx = self.policies.build_policy_context(
                user_id,
                topics=list(live.get("topics", [])),
                micro_signals=micro,
                response_needs=dict(live.get("response_mode", {})),
                limit=6,
            )
            behavior_hints = [str(x).strip() for x in policy_ctx.get("user_rules", [])[:3] if str(x).strip()]
            if len(behavior_hints) < 3:
                for x in policy_ctx.get("global_rules", []):
                    val = str(x).strip()
                    if val and val not in behavior_hints:
                        behavior_hints.append(val)
                    if len(behavior_hints) >= 3:
                        break
            group1_signals = self.group1.extract_signals(analysis, user_message)
            group2_signals = self.group2.extract_signals(analysis, user_message)
            for hint in self.group1.behavior_hints(group1_signals):
                if hint and hint not in behavior_hints:
                    behavior_hints.append(hint)
                if len(behavior_hints) >= 5:
                    break
            for hint in self.group2.behavior_hints(group2_signals):
                if hint and hint not in behavior_hints:
                    behavior_hints.append(hint)
                if len(behavior_hints) >= 7:
                    break
            group2_priority = max(
                safe_float(group2_signals.get("clarification_need_signal"), 0.0),
                safe_float(group2_signals.get("relationship_distress_signal"), 0.0),
                1.0 - safe_float(group2_signals.get("safety_ethics_alignment"), 1.0),
            )
            if group2_priority >= 0.45:
                priority_hints = self.group2.behavior_hints(group2_signals)
                if priority_hints:
                    chosen = priority_hints[0]
                    if chosen in behavior_hints:
                        behavior_hints.remove(chosen)
                    behavior_hints.insert(0, chosen)
            micro_behavior_line = _micro_behavior_prompt_hint(micro_human_bundle)
            if micro_behavior_line:
                if micro_behavior_line in behavior_hints:
                    behavior_hints.remove(micro_behavior_line)
                behavior_hints.insert(0, micro_behavior_line)
            lux_language_behavior_line = str(lux_language_sense_meta.get("behavior_hint", "")).strip()
            if lux_language_behavior_line:
                if lux_language_behavior_line in behavior_hints:
                    behavior_hints.remove(lux_language_behavior_line)
                behavior_hints.insert(0, lux_language_behavior_line)
            behavior_hints = behavior_hints[:7]

            return {
                "behavior_hints": behavior_hints,
                "micro_signals": micro,
                "context_line": str(live.get("context_text", "")).strip(),
                "context_text": str(live.get("context_text", "")).strip(),
                "context_items": list(live.get("context_items", []))
                if isinstance(live.get("context_items"), list)
                else [],
                "selected_policies": list(live.get("selected_policies", []))
                if isinstance(live.get("selected_policies"), list)
                else [],
                "response_mode": dict(live.get("response_mode", {}))
                if isinstance(live.get("response_mode"), dict)
                else {},
                "response_mode_reason": list(live.get("response_mode_reason", []))
                if isinstance(live.get("response_mode_reason"), list)
                else [],
                "time_ecology_meta": dict(live.get("time_ecology_meta", {}))
                if isinstance(live.get("time_ecology_meta"), dict)
                else {},
                "reflection_meta": dict(live.get("reflection_meta", {}))
                if isinstance(live.get("reflection_meta"), dict)
                else {},
                "cultural_epistemic_meta": dict(live.get("cultural_epistemic_meta", {}))
                if isinstance(live.get("cultural_epistemic_meta"), dict)
                else {},
                "emotional_graph_meta": dict(live.get("emotional_graph_meta", {}))
                if isinstance(live.get("emotional_graph_meta"), dict)
                else {},
                "language_hints": list(language_probe.get("language_hints", []))
                if isinstance(language_probe.get("language_hints"), list)
                else [],
                "group1_layer_signals": dict(group1_signals),
                "group2_layer_signals": dict(group2_signals),
                "group3_bundle": group3_bundle.to_safe_dict(),
                "group4_bundle": group4_bundle.to_safe_dict(),
                "micro_human_bridge_meta": micro_human_bundle,
                "lux_language_sense_meta": lux_language_sense_meta,
                "practical_support_meta": practical_support_bundle,
                "micro_behavior_hint": (
                    dict(micro_human_bundle.get("repair_clarity_hint", {}))
                    if isinstance(micro_human_bundle, dict) and isinstance(micro_human_bundle.get("repair_clarity_hint"), dict)
                    else {}
                ),
                "human_risk": dict(risk_preview),
                "mode": mode,
                "analysis_theme": str(analysis.get("theme", "")),
                "analysis_emotion": str(analysis.get("primary_emotion", "")),
                "requested_density": str(live.get("requested_density", "adaptive")),
                "topics": list(live.get("topics", [])) if isinstance(live.get("topics"), list) else [],
                "ranking_debug": list(live.get("ranking_debug", []))
                if isinstance(live.get("ranking_debug"), list)
                else [],
                "dropped_items_summary": dict(live.get("dropped_items_summary", {}))
                if isinstance(live.get("dropped_items_summary"), dict)
                else {},
            }
        except Exception:
            # Fail-safe: never break live chat because of context builder/policy issues.
            micro = self.micro.analyze(user_message)
            context_line = (
                f"Learning hints: confusion={micro.get('confusion_level', 0)}, "
                f"patience={micro.get('patience_level', 1)}, recommendation={micro.get('response_recommendation', 'balanced')}."
            )
            return {
                "behavior_hints": [],
                "micro_signals": micro,
                "context_line": context_line,
                "context_text": context_line,
                "context_items": [],
                "selected_policies": [],
                "response_mode": {},
                "response_mode_reason": ["fallback_context_used"],
                "time_ecology_meta": {},
                "reflection_meta": {},
                "cultural_epistemic_meta": {},
                "emotional_graph_meta": {},
                "language_hints": [],
                "group1_layer_signals": {},
                "group2_layer_signals": {},
                "group3_bundle": Group3Bundle.neutral().to_safe_dict(),
                "group4_bundle": Group4Bundle.neutral().to_safe_dict(),
                "micro_human_bridge_meta": self._build_micro_human_bundle(
                    user_message,
                    analysis=analysis,
                    session=session or {},
                    context={"mode": mode},
                ),
                "lux_language_sense_meta": {
                    "present": False,
                    "active": False,
                    "context_injected": False,
                    "low_confidence_suppressed": False,
                    "safe_summary": "lux_language_sense_fallback_not_used",
                },
                "practical_support_meta": self._build_practical_support_bundle(
                    user_message,
                    analysis=analysis,
                    context={"mode": mode, "fallback": True},
                ),
                "micro_behavior_hint": {},
                "human_risk": {},
                "mode": mode,
                "analysis_theme": str(analysis.get("theme", "")),
                "analysis_emotion": str(analysis.get("primary_emotion", "")),
                "requested_density": "adaptive",
                "topics": [],
                "ranking_debug": [],
                "dropped_items_summary": {},
            }

    def build_light_context(self, user_id: str, user_message: str, analysis: dict[str, Any], mode: str) -> dict[str, Any]:
        # Backward-compatible alias used by current app flow.
        return self.build_live_context(user_id, user_message, analysis, mode)

    def _topic_scores_from_quality(self, quality: dict[str, Any], analysis: dict[str, Any], micro: dict[str, Any]) -> dict[str, float]:
        tech = safe_float(quality.get("technical_accuracy"), 0.0)
        natural = safe_float(quality.get("naturalness"), 0.0)
        emotional = safe_float(quality.get("emotional_alignment"), 0.0)
        repair = safe_float(quality.get("repair_value"), 0.0)
        confusion_reduce = 1.0 - safe_float(micro.get("confusion_level"), 0.0)
        patience = safe_float(micro.get("patience_level"), 0.0)
        task = safe_float(quality.get("task_success_potential"), 0.0)
        safety = safe_float(quality.get("safety_score"), 0.0)
        fine = safe_float(quality.get("fine_tune_value"), 0.0)
        hybrid = safe_float(quality.get("hybrid_depth"), 0.0)
        personal = safe_float(quality.get("personal_relevance"), 0.0)
        global_r = safe_float(quality.get("global_reusability"), 0.0)

        # Analysis layer sinyalleri
        rel_layer = 1.0 if (analysis.get("layers") or {}).get("relationship") else 0.0
        sym_layer = 1.0 if (analysis.get("layers") or {}).get("symbolic") else 0.0
        needs_presence = 1.0 if analysis.get("needs_presence") else 0.0

        return {
            "relationships": round(clamp(0.45 * rel_layer + 0.30 * emotional + 0.25 * repair), 4),
            "emotional_support": round(clamp(0.45 * emotional + 0.30 * needs_presence + 0.25 * natural), 4),
            "technical_guidance": round(clamp(0.65 * tech + 0.35 * task), 4),
            "coding_help": round(clamp(0.70 * tech + 0.30 * safe_float(quality.get("clarity"), 0.0)), 4),
            "creative_ideation": round(clamp(0.45 * hybrid + 0.30 * sym_layer + 0.25 * natural), 4),
            "natural_language": round(clamp(0.70 * natural + 0.30 * safe_float(quality.get("clarity"), 0.0)), 4),
            "repair_quality": round(clamp(0.75 * repair + 0.25 * confusion_reduce), 4),
            "confusion_reduction": round(clamp(0.70 * confusion_reduce + 0.30 * safe_float(quality.get("response_density_fit"), 0.0)), 4),
            "patience_management": round(clamp(0.60 * patience + 0.40 * safe_float(quality.get("response_density_fit"), 0.0)), 4),
            "task_success": round(clamp(0.70 * task + 0.30 * tech), 4),
            "human_like_tone": round(clamp(0.55 * natural + 0.45 * emotional), 4),
            "safety_ethics": round(clamp(safety), 4),
            "fine_tune_quality": round(clamp(0.45 * fine + 0.25 * global_r + 0.20 * personal + 0.10 * safety), 4),
        }

    def _derive_topics(
        self,
        *,
        analysis: dict[str, Any],
        quality: dict[str, Any],
        micro: dict[str, Any],
        topic_scores: dict[str, float],
        mode: str,
    ) -> list[str]:
        topics: list[str] = []
        top = sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)[:5]
        topics.extend([k for k, _ in top])

        if safe_float(micro.get("confusion_level"), 0.0) >= 0.35:
            topics.append("confusion_reduction")
        if safe_float(micro.get("patience_level"), 1.0) < 0.55:
            topics.append("patience_management")
        if safe_float(quality.get("technical_accuracy"), 0.0) >= 0.6:
            topics.append("technical_guidance")
        if safe_float(quality.get("repair_value"), 0.0) >= 0.6:
            topics.append("repair_quality")
        if safe_float(quality.get("safety_score"), 0.0) < 0.8:
            topics.append("safety_ethics")

        layers = analysis.get("layers", {}) if isinstance(analysis.get("layers"), dict) else {}
        if layers.get("relationship"):
            topics.append("relationships")
        if layers.get("human_layer"):
            topics.append("human_like_tone")
        if layers.get("dynamic_tone"):
            topics.append("natural_language")

        if mode in {"luxviai", "luxta", "luxeph"}:
            topics.append("task_success")
        # unique preserve order
        seen = set()
        out = []
        for t in topics:
            if t in seen:
                continue
            seen.add(t)
            out.append(t)
        return out[:8]

    def _build_user_profile_for_optimizer(self, user_id: str) -> dict[str, Any]:
        lessons = load_json(self.personal.lessons_path(user_id), {"items": []})
        policy = self.policies.load_user_policy(user_id)
        lesson_items = lessons.get("items", []) if isinstance(lessons, dict) and isinstance(lessons.get("items"), list) else []
        recent_themes = [str(x.get("theme", "")) for x in lesson_items[-10:] if isinstance(x, dict)]
        return {
            "preferred_style": list(policy.get("rules", []))[:3],
            "preferred_depth": str((policy.get("style") or {}).get("density", "adaptive")),
            "recent_themes": [x for x in recent_themes if x],
        }

    def _build_global_context_for_optimizer(self) -> dict[str, Any]:
        quality = load_json(self.global_store.quality_path, {"topics": {}})
        topics = quality.get("topics", {}) if isinstance(quality, dict) else {}
        top_pattern = ""
        if isinstance(topics, dict) and topics:
            best = sorted(topics.items(), key=lambda kv: safe_float((kv[1] or {}).get("average_score"), 0.0), reverse=True)
            if best:
                top_pattern = str(best[0][0])
        return {"top_pattern": top_pattern, "quality_labels": dict(quality.get("quality_labels", {})) if isinstance(quality, dict) else {}}

    def _apply_behavior_update(self, user_id: str, behavior_update: str) -> None:
        text = str(behavior_update or "").strip()
        if not text:
            return
        # Use policy merge to keep structured + deduplicated behavior rules.
        policy = self.policies.load_user_policy(user_id)
        merged = self.policies.merge_policy(
            policy,
            {
                "topic": "general",
                "rule": text,
                "behavior": text,
                "confidence": 0.82,
                "source": "pipeline_behavior_update",
            },
        )
        self.policies.save_user_policy(user_id, merged)

    def run_background_learning(
        self,
        *,
        user_id: str,
        user_message: str,
        assistant_response: str,
        mode: str,
        analysis: dict[str, Any],
        session_id: str | None,
        learning_context: dict[str, Any] | None = None,
    ) -> None:
        self.ensure_foundation(user_id)
        learning_context = learning_context or {}
        micro = self.micro.analyze(user_message, assistant_response)
        user_profile = self._build_user_profile_for_optimizer(user_id)
        existing_garden = load_json(self.base_dir / "data" / "users" / user_id / "memory_garden.json", [])
        group3_profile = dict(user_profile)
        if isinstance(existing_garden, list):
            group3_profile["memory_garden"] = existing_garden
        global_context = self._build_global_context_for_optimizer()
        conversation_analysis = self.conversation_analyzer.analyze_conversation(
            user_id=user_id,
            user_message=user_message,
            assistant_reply=assistant_response,
            existing_analysis=analysis,
            session={"session_id": session_id, "mode": mode},
            profile=user_profile,
            micro_signals=micro,
        )
        language_analysis = self.language_dna.analyze_language_dna(
            user_id=user_id,
            message=user_message,
            response=assistant_response,
            context={"mode": mode, "session_id": session_id},
        )
        self.language_dna.update_language_dna(user_id, language_analysis)
        human_risk_signal = self.human_risk.analyze_human_risk(
            user_id=user_id,
            message=user_message,
            existing_analysis=analysis,
            micro_signals=micro,
            conversation_analysis=conversation_analysis,
        )
        lens_guard = resolve_lens_precedence(
            message=user_message,
            mode=mode,
            analysis=analysis,
            human_risk=human_risk_signal,
        ).to_safe_dict()
        group1_signals = self.group1.extract_signals(analysis, user_message)
        group2_signals = self.group2.extract_signals(analysis, user_message)
        # Group-3 Step-1 scaffold order (read-only / no durable writes):
        # 1) memory read, 2) symbolic, 3) dream, 4) existential, 5) memory write candidate.
        group3_memory_read = self.group3_memory.read_memory_signals(
            user_message,
            profile=group3_profile,
            session={"session_id": session_id, "mode": mode},
        )
        group3_symbolic = self.group3_symbolic.extract_symbolic_signal(
            user_message,
            analysis=analysis,
            profile=group3_profile,
            session={"session_id": session_id, "mode": mode},
        )
        group3_dream = self.group3_dream.extract_dream_signal(
            user_message,
            analysis=analysis,
            profile=group3_profile,
            session={"session_id": session_id, "mode": mode},
        )
        group3_existential = self.group3_existential.extract_existential_signal(
            user_message,
            analysis=analysis,
            profile=group3_profile,
            session={"session_id": session_id, "mode": mode},
        )
        group3_memory_write = self.group3_memory.propose_memory_write(
            user_message,
            group3_memory_read,
            analysis=analysis,
            safety=(analysis.get("safety_layer") if isinstance(analysis.get("safety_layer"), dict) else {}),
        )
        group3_bundle = self._build_group3_bundle(
            memory_read=group3_memory_read,
            symbolic=group3_symbolic,
            dream=group3_dream,
            existential=group3_existential,
            memory_write_candidate=group3_memory_write,
        )
        group4_emotional_graph = self.group4_emotional_graph.extract_emotional_graph_signal(
            user_message,
            analysis=analysis,
            profile=group3_profile,
            session={"session_id": session_id, "mode": mode},
        )
        group4_time_ecology = self.group4_time_ecology.extract_time_ecology_signal(
            user_message,
            analysis=analysis,
            profile=group3_profile,
            session={"session_id": session_id, "mode": mode},
        )
        group4_cultural_epistemic = self.group4_cultural_epistemic.extract_cultural_epistemic_signal(
            user_message,
            analysis=analysis,
            profile=group3_profile,
            session={"session_id": session_id, "mode": mode},
        )
        group4_reflection = self.group4_reflection.extract_reflection_signal(
            user_message,
            analysis=analysis,
            profile=group3_profile,
            session={"session_id": session_id, "mode": mode},
        )
        group4_bundle = self._build_group4_bundle(
            emotional_graph=group4_emotional_graph,
            time_ecology=group4_time_ecology,
            cultural_epistemic=group4_cultural_epistemic,
            reflection=group4_reflection,
        )
        self.human_risk.append_signal(
            user_id=user_id,
            signal=human_risk_signal,
            mode=mode,
            session_id=session_id,
        )
        sensitive_for_global_or_ft = self.human_risk.is_sensitive_for_global_or_finetune(human_risk_signal)
        memory_gate = self.group3_memory.evaluate_memory_write_candidate(
            user_message,
            group3_memory_write,
            memory_read=group3_memory_read,
            analysis=analysis,
            safety={
                **(analysis.get("safety_layer") if isinstance(analysis.get("safety_layer"), dict) else {}),
                "is_sensitive_interaction": bool(sensitive_for_global_or_ft),
            },
        )
        memory_anchor_write: dict[str, Any] = {"written": False, "reason": "gate_blocked", "count": 0}
        if bool(memory_gate.get("allow_write")):
            anchor = self.group3_memory.build_safe_memory_anchor(
                candidate=group3_memory_write,
                gate=memory_gate,
                analysis=analysis,
                symbolic=group3_symbolic.to_safe_dict() if hasattr(group3_symbolic, "to_safe_dict") else {},
                dream=group3_dream.to_safe_dict() if hasattr(group3_dream, "to_safe_dict") else {},
                existential=group3_existential.to_safe_dict() if hasattr(group3_existential, "to_safe_dict") else {},
            )
            memory_anchor_write = self.group3_memory.persist_memory_anchor(
                base_dir=self.base_dir,
                user_id=user_id,
                anchor=anchor,
                max_items=160,
            )
        append_jsonl(
            self.personal.conversation_analysis_path(user_id),
            {
                "ts": now_iso(),
                "mode": mode,
                "session_id": session_id,
                "analysis": conversation_analysis,
                "language_dna": {
                    "detected_terms": list(language_analysis.get("detected_terms", []))
                    if isinstance(language_analysis.get("detected_terms"), list)
                    else [],
                    "language_hints": list(language_analysis.get("language_hints", []))
                    if isinstance(language_analysis.get("language_hints"), list)
                    else [],
                },
                "human_risk": {
                    "safety_level": str(human_risk_signal.get("safety_level", "normal")),
                    "recommended_response": dict(human_risk_signal.get("recommended_response", {}))
                    if isinstance(human_risk_signal.get("recommended_response"), dict)
                    else {},
                },
                "group1_layers": dict(group1_signals),
                "group2_layers": dict(group2_signals),
                "group3_bundle": group3_bundle.to_safe_dict(),
                "group4_bundle": group4_bundle.to_safe_dict(),
                "lens_guard": dict(lens_guard),
                "group3_memory_gate": {
                    "allow_write": bool(memory_gate.get("allow_write")),
                    "reason_bucket": str(memory_gate.get("reason_bucket", "none")),
                    "confidence": safe_float(memory_gate.get("confidence"), 0.0),
                    "written": bool(memory_anchor_write.get("written")),
                    "write_reason": str(memory_anchor_write.get("reason", "unknown")),
                },
            },
        )

        conversation_record = {
            "ts": now_iso(),
            "mode": mode,
            "session_id": session_id,
            "user_message": user_message[:6000],
            "assistant_response": assistant_response[:12000],
            "analysis": analysis,
            "micro_signals": micro,
            "language_dna": {
                "detected_terms": list(language_analysis.get("detected_terms", []))
                if isinstance(language_analysis.get("detected_terms"), list)
                else [],
            },
            "human_risk": {
                "safety_level": str(human_risk_signal.get("safety_level", "normal")),
            },
            "group1_layers": dict(group1_signals),
            "group2_layers": dict(group2_signals),
            "group3_bundle": group3_bundle.to_safe_dict(),
            "group4_bundle": group4_bundle.to_safe_dict(),
            "lens_guard": dict(lens_guard),
            "group3_memory_gate": {
                "allow_write": bool(memory_gate.get("allow_write")),
                "written": bool(memory_anchor_write.get("written")),
                "write_reason": str(memory_anchor_write.get("reason", "unknown")),
            },
        }
        self.personal.append_conversation_record(user_id, conversation_record)

        candidate = {
            "messages": [
                {"role": "user", "content": user_message[:2000]},
                {"role": "assistant", "content": assistant_response[:5000]},
            ],
            "meta": {
                "mode": mode,
                "theme": str(analysis.get("theme", "belirsiz")),
                "group1_layer_metrics": {
                    "emotion_signal_score": group1_signals.get("emotion_signal_score"),
                    "hidden_need_signal": group1_signals.get("hidden_need_signal"),
                    "tone_adaptation_score": group1_signals.get("tone_adaptation_score"),
                    "human_layer_alignment": group1_signals.get("human_layer_alignment"),
                    "response_tone_adjustment": group1_signals.get("response_tone_adjustment"),
                },
                "group2_layer_metrics": {
                    "narrative_continuity_score": group2_signals.get("narrative_continuity_score"),
                    "context_coherence_score": group2_signals.get("context_coherence_score"),
                    "contradiction_signal_score": group2_signals.get("contradiction_signal_score"),
                    "clarification_need_signal": group2_signals.get("clarification_need_signal"),
                    "relationship_distress_signal": group2_signals.get("relationship_distress_signal"),
                    "boundary_support_signal": group2_signals.get("boundary_support_signal"),
                    "safety_ethics_alignment": group2_signals.get("safety_ethics_alignment"),
                    "privacy_protection_score": group2_signals.get("privacy_protection_score"),
                    "response_risk_reduction": group2_signals.get("response_risk_reduction"),
                    "response_tone_adjustment": group2_signals.get("response_tone_adjustment"),
                },
                "group4_layer_metrics": {
                    "emotional_graph_confidence": group4_bundle.to_safe_dict().get("emotional_graph", {}).get("confidence"),
                    "time_ecology_confidence": group4_bundle.to_safe_dict().get("time_ecology", {}).get("confidence"),
                    "cultural_epistemic_confidence": group4_bundle.to_safe_dict().get("cultural_epistemic", {}).get("confidence"),
                    "reflection_confidence": group4_bundle.to_safe_dict().get("reflection", {}).get("confidence"),
                },
            },
        }
        quality = self.quality.evaluate(
            candidate,
            {
                "behavior_hints": (learning_context.get("behavior_hints", []) if isinstance(learning_context.get("behavior_hints"), list) else [])
                + (language_analysis.get("language_hints", []) if isinstance(language_analysis.get("language_hints"), list) else []),
                "micro_signals": micro,
                "requested_density": learning_context.get("requested_density", "adaptive"),
                "group1_layer_signals": group1_signals,
                "group2_layer_signals": group2_signals,
                "group3_bundle": group3_bundle.to_safe_dict(),
                "group4_bundle": group4_bundle.to_safe_dict(),
            },
        )
        topic_scores = self._topic_scores_from_quality(quality, analysis, micro)
        derived_topics = self._derive_topics(
            analysis=analysis,
            quality=quality,
            micro=micro,
            topic_scores=topic_scores,
            mode=mode,
        )
        analyzer_topics = (
            list(conversation_analysis.get("topics", []))
            if isinstance(conversation_analysis.get("topics"), list)
            else []
        )
        topics: list[str] = []
        seen_topics: set[str] = set()
        for topic in analyzer_topics + derived_topics:
            if topic in seen_topics:
                continue
            seen_topics.add(topic)
            topics.append(topic)
        if not topics:
            topics = derived_topics or ["natural_language"]
        if sensitive_for_global_or_ft and "safety_ethics" not in topics:
            topics.append("safety_ethics")
        if safe_float((human_risk_signal.get("risk_signals", {}) if isinstance(human_risk_signal.get("risk_signals"), dict) else {}).get("relationship_distress", 0.0), 0.0) >= 0.3:
            if "relationships" not in topics:
                topics.append("relationships")
        if safe_float(group2_signals.get("contradiction_signal_score"), 0.0) >= 0.45:
            if "confusion_reduction" not in topics:
                topics.append("confusion_reduction")
            if "repair_quality" not in topics:
                topics.append("repair_quality")
        if safe_float(group2_signals.get("relationship_distress_signal"), 0.0) >= 0.45 and "relationships" not in topics:
            topics.append("relationships")
        if safe_float(group2_signals.get("safety_ethics_alignment"), 1.0) < 0.8 and "safety_ethics" not in topics:
            topics.append("safety_ethics")
        topics = topics[:10]

        source_conversation = (
            f"User: {user_message.strip()}\n"
            f"Assistant: {assistant_response.strip()}\n"
            f"Theme: {analysis.get('theme', 'belirsiz')}\n"
            f"Emotion: {analysis.get('primary_emotion', 'notr')}"
        )
        optimizer_result = self.hybrid.optimize(
            user_id=user_id,
            source_conversation=source_conversation,
            topics=topics,
            user_profile=user_profile,
            global_context=global_context,
            conversation_analysis=conversation_analysis,
            target_score=0.90,
            elite_score=0.95,
            min_accept_score=0.85,
            max_attempts=80,
            patience=15,
            min_improvement_delta=0.01,
        )
        learning_signal = optimizer_result.get("learning_signal") if isinstance(optimizer_result, dict) else None

        lesson = {
            "ts": now_iso(),
            "kind": "conversation_feedback",
            "theme": str(analysis.get("theme", "belirsiz")),
            "emotion": str(analysis.get("primary_emotion", "notr")),
            "behavior": micro.get("next_best_behavior"),
            "quality_label": quality.get("quality_label"),
            "weakness": quality.get("weakness"),
            "optimizer_status": str(optimizer_result.get("status", "unknown")) if isinstance(optimizer_result, dict) else "unknown",
            "group1_signal": {
                "emotion_signal_score": group1_signals.get("emotion_signal_score"),
                "hidden_need_signal": group1_signals.get("hidden_need_signal"),
                "tone_adaptation_score": group1_signals.get("tone_adaptation_score"),
                "human_layer_alignment": group1_signals.get("human_layer_alignment"),
            },
        }
        self.personal.append_lesson(user_id, lesson)
        self.personal.append_lesson(
            user_id,
            {
                "ts": now_iso(),
                "kind": "group1_layer_bridge",
                "theme": "emotion_hidden_tone_human",
                "emotion": str(analysis.get("primary_emotion", "notr")),
                "behavior": self.group1.personal_lesson_text(group1_signals),
                "quality_label": quality.get("quality_label"),
            },
        )
        self.personal.append_lesson(
            user_id,
            {
                "ts": now_iso(),
                "kind": "group2_layer_bridge",
                "theme": "narrative_contradiction_relationship_safety",
                "emotion": str(analysis.get("primary_emotion", "notr")),
                "behavior": self.group2.personal_lesson_text(group2_signals),
                "quality_label": quality.get("quality_label"),
            },
        )
        self.personal.append_hybrid_question(
            user_id,
            {
                "ts": now_iso(),
                "prompt": user_message[:500],
                "quality_label": quality.get("quality_label"),
                "weakness": quality.get("weakness"),
                "optimizer_status": optimizer_result.get("status") if isinstance(optimizer_result, dict) else None,
                "best_score": optimizer_result.get("best_score") if isinstance(optimizer_result, dict) else None,
                "attempt_count": optimizer_result.get("attempt_count") if isinstance(optimizer_result, dict) else None,
                "attempts_summary": optimizer_result.get("attempts_summary", []) if isinstance(optimizer_result, dict) else [],
                "best_candidate": optimizer_result.get("best_candidate") if isinstance(optimizer_result, dict) else None,
                "targeted_weakness": (
                    (
                        optimizer_result.get("best_candidate", {}).get("targeted_weakness")
                        if isinstance(optimizer_result.get("best_candidate", {}), dict)
                        else None
                    )
                    if isinstance(optimizer_result, dict) else None
                ),
                "applied_improvement_strategy": (
                    (
                        optimizer_result.get("best_candidate", {}).get("applied_improvement_strategy")
                        if isinstance(optimizer_result.get("best_candidate", {}), dict)
                        else None
                    )
                    if isinstance(optimizer_result, dict) else None
                ),
                "improved_score": (
                    (
                        optimizer_result.get("best_candidate", {}).get("improved_score")
                        if isinstance(optimizer_result.get("best_candidate", {}), dict)
                        else None
                    )
                    if isinstance(optimizer_result, dict) else None
                ),
                "conversation_topics": topics,
                "response_needs": (
                    conversation_analysis.get("response_needs", {})
                    if isinstance(conversation_analysis, dict)
                    else {}
                ),
            },
        )

        # Group-3 safety-visible summary metrics (bucket-level only, no raw user text).
        gate_reasons = [str(x) for x in (memory_gate.get("reasons", []) if isinstance(memory_gate.get("reasons"), list) else [])]
        gate_reason_primary = gate_reasons[0] if gate_reasons else "none"
        msg_low = (user_message or "").lower()
        digit_count = sum(1 for ch in (user_message or "") if ch.isdigit())
        pii_like_signal = ("@" in msg_low) or ("http://" in msg_low) or ("https://" in msg_low) or digit_count >= 7
        g3_symbolic_active = (
            1
            if safe_float(getattr(group3_symbolic, "confidence", 0.0), 0.0) >= 0.68
            and str(getattr(group3_symbolic, "density", "none")) in {"medium", "high"}
            else 0
        )
        g3_dream_active = (
            1
            if safe_float(getattr(group3_dream, "confidence", 0.0), 0.0) >= 0.70
            and bool(getattr(group3_dream, "is_dream_context", False) or getattr(group3_dream, "dream_context", False))
            else 0
        )
        g3_existential_active = (
            1
            if safe_float(getattr(group3_existential, "confidence", 0.0), 0.0) >= 0.55
            and (
                str(getattr(group3_existential, "meaning_signal", "none")) == "active"
                or str(getattr(group3_existential, "direction_signal", "none")) == "active"
                or str(getattr(group3_existential, "uncertainty", "none")) in {"medium", "high"}
            )
            else 0
        )
        g3_memory_candidate_active = (
            1
            if bool(getattr(group3_memory_write, "should_write", False))
            and safe_float(getattr(group3_memory_write, "confidence", 0.0), 0.0) >= 0.60
            else 0
        )
        response_mode_for_perf = (
            learning_context.get("response_mode", {})
            if isinstance(learning_context.get("response_mode"), dict)
            else conversation_analysis.get("response_needs", {})
            if isinstance(conversation_analysis, dict)
            else {}
        )
        time_ecology_meta = learning_context.get("time_ecology_meta", {}) if isinstance(learning_context.get("time_ecology_meta"), dict) else {}
        reflection_meta = learning_context.get("reflection_meta", {}) if isinstance(learning_context.get("reflection_meta"), dict) else {}
        cultural_epistemic_meta = (
            learning_context.get("cultural_epistemic_meta", {})
            if isinstance(learning_context.get("cultural_epistemic_meta"), dict)
            else {}
        )
        emotional_graph_meta = (
            learning_context.get("emotional_graph_meta", {})
            if isinstance(learning_context.get("emotional_graph_meta"), dict)
            else {}
        )
        selected_lens = str(lens_guard.get("selected_lens", "normal") or "normal").strip().lower()
        lens_reason_bucket = str(lens_guard.get("reason_bucket", "normal_flow") or "normal_flow").strip().lower()
        lens_conf_bucket = str(lens_guard.get("confidence_bucket", "medium") or "medium").strip().lower()
        suppressed_lens_count = len(lens_guard.get("suppressed_lenses", [])) if isinstance(lens_guard.get("suppressed_lenses"), list) else 0
        lens_near_miss = 1 if bool(lens_guard.get("lens_stacking_near_miss")) else 0
        utility_metaphor_leakage = _utility_metaphor_leakage_flag(
            assistant_response=assistant_response,
            selected_lens=selected_lens,
        )
        technical_direct_answer_flag = 1 if selected_lens == "technical" else 0
        dream_false_positive_count = (
            1
            if selected_lens == "luxdream"
            and not bool(lens_guard.get("dream_context"))
            else 0
        )
        luxching_false_positive_count = (
            1
            if selected_lens == "luxching"
            and lens_reason_bucket not in {"explicit_command", "cooldown"}
            else 0
        )
        luxmirror_offer_flag = 1 if selected_lens == "luxmirror" else 0
        forced_question_flag = 1 if (technical_direct_answer_flag == 1 and str(assistant_response or "").strip().endswith("?")) else 0
        half_step_bucket = _half_step_type_bucket(response_mode_for_perf if isinstance(response_mode_for_perf, dict) else {})
        context_items = learning_context.get("context_items", []) if isinstance(learning_context.get("context_items"), list) else []
        ranking_debug = learning_context.get("ranking_debug", []) if isinstance(learning_context.get("ranking_debug"), list) else []
        group4_context_injection_count = sum(
            1
            for it in context_items
            if isinstance(it, dict) and str(it.get("source", "")).strip().lower() == "group4_bundle"
        )
        group4_low_confidence_suppressed_count = sum(
            1
            for d in ranking_debug
            if isinstance(d, dict)
            and str(d.get("source", "")).strip().lower() == "group4_bundle"
            and not bool(d.get("kept"))
            and safe_float((d.get("metrics", {}) if isinstance(d.get("metrics"), dict) else {}).get("confidence", 1.0), 1.0) < 0.56
        )
        response_length_bucket = _response_length_bucket(assistant_response)
        latency_bucket = "unknown"
        language_bucket = _language_bucket(user_message)
        te_hints = time_ecology_meta.get("hints", []) if isinstance(time_ecology_meta.get("hints"), list) else []
        te_hint_bucket = "|".join(str(x).strip() for x in te_hints[:5] if str(x).strip()) or "none"
        te_emitted = 1 if bool(time_ecology_meta.get("emitted")) else 0
        te_neutral = 1 if bool(time_ecology_meta.get("neutral")) else 0
        te_guard_suppressed = 1 if bool(time_ecology_meta.get("suppressed_by_guard")) else 0
        te_conf = safe_float(time_ecology_meta.get("confidence"), 0.0)
        te_tighten_only_violation = 0
        if any(h not in {"shorter", "slower", "fewer_questions", "drop_preamble", "slightly_warmer_cadence"} for h in te_hints):
            te_tighten_only_violation = 1
        safety_level_now = str(human_risk_signal.get("safety_level", "normal")).strip().lower()
        safety_flagged_turns_with_te_hint = 1 if safety_level_now in {"sensitive", "high_risk", "crisis"} and te_emitted == 1 else 0
        reflection_hints = reflection_meta.get("hints", []) if isinstance(reflection_meta.get("hints"), list) else []
        reflection_emitted = 1 if bool(reflection_meta.get("emitted")) else 0
        reflection_neutral = 1 if bool(reflection_meta.get("neutral")) else 0
        reflection_conf = safe_float(reflection_meta.get("confidence"), 0.0)
        reflection_low_conf_suppressed = 1 if str(reflection_meta.get("suppression_reason", "")).strip().lower() == "low_confidence" else 0
        reflection_style_bucket = str(reflection_meta.get("answer_style", getattr(group4_reflection, "answer_style_bucket", "neutral")) or "neutral").strip().lower()
        reflection_correction_signal = str(reflection_meta.get("correction_signal", getattr(group4_reflection, "correction_signal", "none")) or "none").strip().lower()
        reflection_utility_guard = str(reflection_meta.get("utility_guard_signal", getattr(group4_reflection, "utility_guard_signal", "none")) or "none").strip().lower()
        reflection_risk_review = str(reflection_meta.get("risk_review", getattr(group4_reflection, "risk_review_bucket", "none")) or "none").strip().lower()
        reflection_verbosity = str(reflection_meta.get("verbosity", getattr(group4_reflection, "verbosity_bucket", "unknown")) or "unknown").strip().lower()
        avoid_metaphor_signal = 1 if reflection_utility_guard in {"avoid_metaphor", "avoid_lens_offer"} else 0
        forced_question_reduction = 1 if ("fewer_questions" in reflection_hints or "next_action" in reflection_hints) else 0
        verbosity_too_long = 1 if reflection_verbosity == "too_long" else 0
        cultural_hints = (
            cultural_epistemic_meta.get("hints", [])
            if isinstance(cultural_epistemic_meta.get("hints"), list)
            else []
        )
        cultural_hint_bucket = "|".join(str(x).strip() for x in cultural_hints[:5] if str(x).strip()) or "none"
        cultural_emitted = 1 if bool(cultural_epistemic_meta.get("emitted")) else 0
        cultural_neutral = 1 if bool(cultural_epistemic_meta.get("neutral")) else 0
        cultural_conf = safe_float(cultural_epistemic_meta.get("confidence"), 0.0)
        cultural_low_conf_suppressed = (
            1 if str(cultural_epistemic_meta.get("suppression_reason", "")).strip().lower() == "low_confidence" else 0
        )
        cultural_guard_suppressed = 1 if bool(cultural_epistemic_meta.get("suppressed_by_guard")) else 0
        cultural_utility_suppressed = 1 if bool(cultural_epistemic_meta.get("utility_minimal")) else 0
        cultural_identity_block = 1 if bool(cultural_epistemic_meta.get("identity_inference_blocked")) else 0
        cultural_language_context = str(
            cultural_epistemic_meta.get("language_context", getattr(group4_cultural_epistemic, "language_context", "unknown"))
            or "unknown"
        ).strip().lower()
        cultural_register_bucket = str(
            cultural_epistemic_meta.get("register_formality", getattr(group4_cultural_epistemic, "register_formality", "unknown"))
            or "unknown"
        ).strip().lower()
        cultural_mixed_state = str(
            cultural_epistemic_meta.get("mixed_language_state", getattr(group4_cultural_epistemic, "mixed_language_state", "unknown"))
            or "unknown"
        ).strip().lower()
        forbidden_identity_pattern_count = 0
        technical_substance_drift_count = 0
        lens_frequency_drift_count = 0
        emotional_hints = (
            emotional_graph_meta.get("hints", [])
            if isinstance(emotional_graph_meta.get("hints"), list)
            else []
        )
        emotional_emitted = 1 if bool(emotional_graph_meta.get("emitted")) else 0
        emotional_neutral = 1 if bool(emotional_graph_meta.get("neutral")) else 0
        emotional_conf = safe_float(emotional_graph_meta.get("confidence"), 0.0)
        emotional_low_conf_suppressed = (
            1 if str(emotional_graph_meta.get("suppression_reason", "")).strip().lower() == "low_confidence" else 0
        )
        emotional_safety_suppressed = 1 if bool(emotional_graph_meta.get("suppressed_by_guard")) else 0
        emotional_utility_suppressed = 1 if bool(emotional_graph_meta.get("utility_minimal")) else 0
        emotional_intensity_bucket = str(
            emotional_graph_meta.get("emotional_intensity_bucket", getattr(group4_emotional_graph, "emotional_intensity_bucket", "none"))
            or "none"
        ).strip().lower()
        emotional_shift_bucket = str(
            emotional_graph_meta.get("shift_bucket", getattr(group4_emotional_graph, "shift_bucket", "unknown"))
            or "unknown"
        ).strip().lower()
        emotional_mixed_affect_bucket = str(
            emotional_graph_meta.get("mixed_affect_bucket", getattr(group4_emotional_graph, "mixed_affect_bucket", "none"))
            or "none"
        ).strip().lower()
        emotional_recovery_bucket = str(
            emotional_graph_meta.get("recovery_marker_bucket", getattr(group4_emotional_graph, "recovery_marker_bucket", "none"))
            or "none"
        ).strip().lower()
        emotional_support_bucket = str(
            emotional_graph_meta.get("support_need_bucket", getattr(group4_emotional_graph, "support_need_bucket", "none"))
            or "none"
        ).strip().lower()
        emotional_forbidden_phrases = (
            "sen " + "depresifsin",
            "travma " + "yasiyorsun",
            "travma " + "yaşıyorsun",
            "kaygili " + "baglaniyorsun",
            "kaygılı " + "bağlanıyorsun",
            "duygusal " + "grafigin",
            "duygusal " + "grafiğin",
            "sende " + "surekli",
            "sende " + "sürekli",
            "senin temel " + "problemin",
        )
        assistant_low = str(assistant_response or "").lower()
        forbidden_emotional_label_flag = 1 if any(p in assistant_low for p in emotional_forbidden_phrases) else 0
        therapeutic_drift_count = 1 if forbidden_emotional_label_flag else 0
        micro_bridge_counts = _micro_bridge_telemetry_fields(
            learning_context.get("micro_human_bridge_meta", {})
            if isinstance(learning_context.get("micro_human_bridge_meta"), dict)
            else {}
        )
        micro_behavior_counts = _micro_behavior_telemetry_counts(
            {
                "repair_clarity_hint": (
                    learning_context.get("micro_behavior_hint", {})
                    if isinstance(learning_context.get("micro_behavior_hint"), dict)
                    else {}
                )
            }
        )
        practical_support_meta = (
            learning_context.get("practical_support_meta", {})
            if isinstance(learning_context.get("practical_support_meta"), dict)
            else {}
        )
        practical_support_counts = (
            practical_support_meta.get("telemetry", {})
            if isinstance(practical_support_meta.get("telemetry"), dict)
            else {}
        )

        perf_row = {
            "ts": now_iso(),
            "topics": topics,
            "response_mode": response_mode_for_perf if isinstance(response_mode_for_perf, dict) else {},
            "quality": {
                "total_score": quality.get("total_score"),
                "quality_label": quality.get("quality_label"),
                "clarity": quality.get("clarity"),
                "hybrid_depth": quality.get("hybrid_depth"),
                "personal_relevance": quality.get("personal_relevance"),
                "global_reusability": quality.get("global_reusability"),
                "technical_accuracy": quality.get("technical_accuracy"),
                "behavioral_improvement": quality.get("behavioral_improvement"),
                "fine_tune_value": quality.get("fine_tune_value"),
                "safety_score": quality.get("safety_score"),
                "naturalness": quality.get("naturalness"),
                "emotional_alignment": quality.get("emotional_alignment"),
                "response_density_fit": quality.get("response_density_fit"),
                "task_success_potential": quality.get("task_success_potential"),
                "repair_value": quality.get("repair_value"),
                "weakness": quality.get("weakness"),
            },
            "signals": {
                "confusion_level": micro.get("confusion_level"),
                "patience_level": micro.get("patience_level"),
                "trust_shift": micro.get("trust_shift"),
                "urgency_level": micro.get("urgency_level"),
                "emotion_signal_score": group1_signals.get("emotion_signal_score"),
                "hidden_need_signal": group1_signals.get("hidden_need_signal"),
                "tone_adaptation_score": group1_signals.get("tone_adaptation_score"),
                "human_layer_alignment": group1_signals.get("human_layer_alignment"),
                "emotional_load_level": group1_signals.get("emotional_load_level"),
                "clarity_need_signal": group1_signals.get("clarity_need_signal"),
                "repair_need_signal": group1_signals.get("repair_need_signal"),
                "safety_sensitive_signal": group1_signals.get("safety_sensitive_signal"),
                "response_tone_adjustment": group1_signals.get("response_tone_adjustment"),
                "narrative_continuity_score": group2_signals.get("narrative_continuity_score"),
                "context_coherence_score": group2_signals.get("context_coherence_score"),
                "contradiction_signal_score": group2_signals.get("contradiction_signal_score"),
                "clarification_need_signal": group2_signals.get("clarification_need_signal"),
                "relationship_distress_signal": group2_signals.get("relationship_distress_signal"),
                "boundary_support_signal": group2_signals.get("boundary_support_signal"),
                "safety_ethics_alignment": group2_signals.get("safety_ethics_alignment"),
                "privacy_protection_score": group2_signals.get("privacy_protection_score"),
                "response_risk_reduction": group2_signals.get("response_risk_reduction"),
                "group2_response_tone_adjustment": group2_signals.get("response_tone_adjustment"),
                "group4_signal_count": int(
                    (1 if safe_float(group4_emotional_graph.confidence, 0.0) > 0.0 else 0)
                    + (1 if safe_float(group4_time_ecology.confidence, 0.0) > 0.0 else 0)
                    + (1 if safe_float(group4_cultural_epistemic.confidence, 0.0) > 0.0 else 0)
                    + (1 if safe_float(group4_reflection.confidence, 0.0) > 0.0 else 0)
                ),
                "group4_signal_presence_count": 1
                if int(
                    (1 if safe_float(group4_emotional_graph.confidence, 0.0) > 0.0 else 0)
                    + (1 if safe_float(group4_time_ecology.confidence, 0.0) > 0.0 else 0)
                    + (1 if safe_float(group4_cultural_epistemic.confidence, 0.0) > 0.0 else 0)
                    + (1 if safe_float(group4_reflection.confidence, 0.0) > 0.0 else 0)
                )
                > 0
                else 0,
                "emotional_graph_confidence": safe_float(group4_emotional_graph.confidence, 0.0),
                "emotional_graph_signal_presence_count": 1 if emotional_conf > 0.0 else 0,
                "emotional_graph_hint_emitted_count": int(emotional_emitted),
                "emotional_graph_neutral_count": int(emotional_neutral),
                "emotional_intensity_bucket": emotional_intensity_bucket,
                "emotional_shift_bucket": emotional_shift_bucket,
                "mixed_affect_bucket": emotional_mixed_affect_bucket,
                "recovery_marker_bucket": emotional_recovery_bucket,
                "support_need_bucket": emotional_support_bucket,
                "emotional_graph_low_confidence_suppressed_count": int(emotional_low_conf_suppressed),
                "emotional_graph_safety_suppressed_count": int(emotional_safety_suppressed),
                "utility_emotional_suppression_count": int(emotional_utility_suppressed),
                "user_visible_emotion_label_block_count": int(forbidden_emotional_label_flag),
                "clinical_label_block_count": int(forbidden_emotional_label_flag),
                "memory_write_block_count": 0,
                "therapeutic_drift_count": int(therapeutic_drift_count),
                "micro_bridge_presence_count": int(micro_bridge_counts.get("micro_bridge_presence_count", 0)),
                "micro_bridge_neutral_count": int(micro_bridge_counts.get("micro_bridge_neutral_count", 0)),
                "micro_bridge_context_injection_count": int(micro_bridge_counts.get("micro_bridge_context_injection_count", 0)),
                "micro_bridge_low_confidence_suppressed_count": int(micro_bridge_counts.get("micro_bridge_low_confidence_suppressed_count", 0)),
                "micro_intent_signal_count": int(micro_bridge_counts.get("micro_intent_signal_count", 0)),
                "intent_clarity_bucket": str(micro_bridge_counts.get("intent_clarity_bucket", "unknown")),
                "request_type_bucket": str(micro_bridge_counts.get("request_type_bucket", "unknown")),
                "confusion_bucket": str(micro_bridge_counts.get("confusion_bucket", "none")),
                "trust_state_bucket": str(micro_bridge_counts.get("trust_state_bucket", "unknown")),
                "misunderstanding_risk_bucket": str(micro_bridge_counts.get("misunderstanding_risk_bucket", "none")),
                "repair_signal_count": int(micro_bridge_counts.get("repair_signal_count", 0)),
                "correction_type_bucket": str(micro_bridge_counts.get("correction_type_bucket", "none")),
                "answer_success_bucket": str(micro_bridge_counts.get("answer_success_bucket", "unknown")),
                "frustration_bucket": str(micro_bridge_counts.get("frustration_bucket", "none")),
                "followup_pressure_risk_bucket": str(micro_bridge_counts.get("followup_pressure_risk_bucket", "none")),
                "micro_low_confidence_suppressed_count": int(micro_bridge_counts.get("micro_low_confidence_suppressed_count", 0)),
                "micro_sensitive_suppressed_count": int(micro_bridge_counts.get("micro_sensitive_suppressed_count", 0)),
                "micro_behavior_hint_emission_count": int(micro_behavior_counts.get("micro_behavior_hint_emission_count", 0)),
                "micro_behavior_hint_suppressed_count": int(micro_behavior_counts.get("micro_behavior_hint_suppressed_count", 0)),
                "correction_ack_hint_count": int(micro_behavior_counts.get("correction_ack_hint_count", 0)),
                "clarification_hint_count": int(micro_behavior_counts.get("clarification_hint_count", 0)),
                "reduce_questions_hint_count": int(micro_behavior_counts.get("reduce_questions_hint_count", 0)),
                "directness_hint_count": int(micro_behavior_counts.get("directness_hint_count", 0)),
                "avoid_lens_offer_hint_count": int(micro_behavior_counts.get("avoid_lens_offer_hint_count", 0)),
                "truncation_repair_hint_count": int(micro_behavior_counts.get("truncation_repair_hint_count", 0)),
                "low_confidence_behavior_suppressed_count": int(micro_behavior_counts.get("low_confidence_behavior_suppressed_count", 0)),
                "safety_behavior_suppressed_count": int(micro_behavior_counts.get("safety_behavior_suppressed_count", 0)),
                "practical_support_presence_count": int(practical_support_counts.get("practical_support_presence_count", 0)),
                "practical_support_candidate_count": int(practical_support_counts.get("practical_support_candidate_count", 0)),
                "practical_support_context_injection_count": int(practical_support_counts.get("practical_support_context_injection_count", 0)),
                "practical_support_active_behavior_count": int(practical_support_counts.get("practical_support_active_behavior_count", 0)),
                "practical_support_safety_suppressed_count": int(practical_support_counts.get("practical_support_safety_suppressed_count", 0)),
                "time_ecology_confidence": safe_float(group4_time_ecology.confidence, 0.0),
                "cultural_epistemic_confidence": safe_float(group4_cultural_epistemic.confidence, 0.0),
                "cultural_epistemic_signal_presence_count": 1 if cultural_conf > 0.0 else 0,
                "cultural_epistemic_hint_emitted_count": int(cultural_emitted),
                "cultural_epistemic_neutral_count": int(cultural_neutral),
                "cultural_epistemic_hint_bucket": cultural_hint_bucket,
                "cultural_epistemic_language_context_bucket": cultural_language_context,
                "cultural_epistemic_register_hint_bucket": cultural_register_bucket,
                "cultural_epistemic_mixed_language_state": cultural_mixed_state,
                "cultural_epistemic_low_confidence_neutral_count": int(cultural_low_conf_suppressed),
                "utility_cultural_suppression_count": int(cultural_utility_suppressed),
                "identity_inference_block_count": int(cultural_identity_block),
                "forbidden_identity_pattern_count": int(forbidden_identity_pattern_count),
                "technical_substance_drift_count": int(technical_substance_drift_count),
                "lens_frequency_drift_count": int(lens_frequency_drift_count),
                "safety_veto_suppression_count": int(cultural_guard_suppressed),
                "reflection_confidence": safe_float(group4_reflection.confidence, 0.0),
                "reflection_signal_presence_count": 1 if reflection_conf > 0.0 else 0,
                "reflection_hint_emitted_count": int(reflection_emitted),
                "reflection_neutral_count": int(reflection_neutral),
                "reflection_style_bucket": reflection_style_bucket,
                "reflection_correction_signal": reflection_correction_signal,
                "reflection_utility_guard_signal": reflection_utility_guard,
                "reflection_risk_review_bucket": reflection_risk_review,
                "reflection_verbosity_bucket": reflection_verbosity,
                "reflection_low_confidence_suppressed_count": int(reflection_low_conf_suppressed),
                "avoid_metaphor_signal_count": int(avoid_metaphor_signal),
                "forced_question_reduction_count": int(forced_question_reduction),
                "verbosity_too_long_count": int(verbosity_too_long),
                "selected_lens": selected_lens,
                "suppressed_lens_count": int(suppressed_lens_count),
                "lens_reason_bucket": lens_reason_bucket,
                "lens_confidence_bucket": lens_conf_bucket,
                "lens_stacking_near_miss_count": int(lens_near_miss),
                "lens_trigger_bucket": selected_lens,
                "utility_metaphor_leakage_count": int(utility_metaphor_leakage),
                "technical_direct_answer_flag": int(technical_direct_answer_flag),
                "dream_false_positive_count": int(dream_false_positive_count),
                "luxching_false_positive_count": int(luxching_false_positive_count),
                "luxmirror_offer_flag": int(luxmirror_offer_flag),
                "forced_question_flag": int(forced_question_flag),
                "half_step_type_bucket": half_step_bucket,
                "group4_context_injection_count": int(group4_context_injection_count),
                "group4_low_confidence_suppressed_count": int(group4_low_confidence_suppressed_count),
                "multilingual_language_bucket": language_bucket,
                "response_length_bucket": response_length_bucket,
                "latency_bucket": latency_bucket,
                "time_ecology_hint_emitted_count": int(te_emitted),
                "time_ecology_neutral_count": int(te_neutral),
                "time_ecology_emitted_hint_bucket": te_hint_bucket,
                "time_ecology_confidence_bucket": (
                    "high" if te_conf >= 0.8 else "medium" if te_conf >= 0.6 else "low"
                ),
                "guard_12_5_suppression_count": int(te_guard_suppressed),
                "tighten_only_violation_count": int(te_tighten_only_violation),
                "safety_flagged_turns_with_time_ecology_hint_count": int(safety_flagged_turns_with_te_hint),
                "safety_sensitive_interaction": 1 if str(human_risk_signal.get("safety_level", "normal")) in {"sensitive", "high_risk", "crisis"} else 0,
                "high_emotional_load": 1 if str(human_risk_signal.get("safety_level", "normal")) in {"high_risk", "crisis"} else 0,
                "grounding_needed": 1 if bool((human_risk_signal.get("recommended_response") or {}).get("should_offer_grounding")) else 0,
                "boundary_support": 1 if bool((human_risk_signal.get("recommended_response") or {}).get("should_validate")) else 0,
                "relationship_distress_support": 1
                if safe_float((human_risk_signal.get("risk_signals", {}) if isinstance(human_risk_signal.get("risk_signals"), dict) else {}).get("relationship_distress", 0.0), 0.0) >= 0.3
                else 0,
                "impulse_slowdown_support": 1
                if safe_float((human_risk_signal.get("risk_signals", {}) if isinstance(human_risk_signal.get("risk_signals"), dict) else {}).get("addiction_pattern_signal", 0.0), 0.0) >= 0.3
                else 0,
                "threat_perception_support": 1
                if safe_float((human_risk_signal.get("risk_signals", {}) if isinstance(human_risk_signal.get("risk_signals"), dict) else {}).get("threat_perception_sensitivity", 0.0), 0.0) >= 0.3
                else 0,
                "trauma_sensitive_support": 1
                if max(
                    safe_float((human_risk_signal.get("risk_signals", {}) if isinstance(human_risk_signal.get("risk_signals"), dict) else {}).get("trauma_sensitivity", 0.0), 0.0),
                    safe_float((human_risk_signal.get("risk_signals", {}) if isinstance(human_risk_signal.get("risk_signals"), dict) else {}).get("abuse_or_assault_signal", 0.0), 0.0),
                )
                >= 0.3
                else 0,
                "group3_signal_count": int(g3_symbolic_active + g3_dream_active + g3_existential_active + g3_memory_candidate_active),
                "symbolic_signal_count": int(g3_symbolic_active),
                "dream_context_count": int(g3_dream_active),
                "existential_signal_count": int(g3_existential_active),
                "memory_candidate_count": int(g3_memory_candidate_active),
                "memory_gate_allowed_count": 1 if bool(memory_gate.get("allow_write")) else 0,
                "memory_gate_blocked_count": 0 if bool(memory_gate.get("allow_write")) else 1,
                "memory_gate_block_reason": gate_reason_primary,
                "duplicate_anchor_block_count": 1 if str(memory_anchor_write.get("reason", "")) == "duplicate_anchor" else 0,
                "sensitive_block_count": 1 if "sensitive_content_detected" in gate_reasons else 0,
                "pii_block_count": 1 if ("sensitive_content_detected" in gate_reasons and pii_like_signal) else 0,
                "low_confidence_block_count": 1 if "low_confidence" in gate_reasons else 0,
            },
        }
        self.personal.append_performance(user_id, perf_row)
        try:
            self.performance_tracker.update_response_mode_result(
                user_id,
                perf_row.get("response_mode", {}) if isinstance(perf_row.get("response_mode"), dict) else {},
                safe_float(quality.get("total_score"), 0.0),
                micro_signals=micro,
                topics=topics,
            )
        except Exception:
            # Non-blocking path: background learning should continue.
            pass

        if sensitive_for_global_or_ft:
            global_lesson = {
                "ts": now_iso(),
                "mode": mode,
                "theme": "safety_sensitive_support",
                "recommendation": "Sensitive interaction: keep calm validation, gentle pacing, and safety boundaries.",
                "quality_label": quality.get("quality_label"),
                "weakness": quality.get("weakness"),
                "optimizer_status": optimizer_result.get("status") if isinstance(optimizer_result, dict) else None,
            }
        else:
            group2_priority = max(
                safe_float(group2_signals.get("clarification_need_signal"), 0.0),
                safe_float(group2_signals.get("relationship_distress_signal"), 0.0),
                1.0 - safe_float(group2_signals.get("safety_ethics_alignment"), 1.0),
            )
            recommendation_text = (
                self.group2.global_lesson_text(group2_signals)
                if group2_priority >= 0.45
                else self.group1.global_lesson_text(group1_signals)
            )
            global_lesson = {
                "ts": now_iso(),
                "mode": mode,
                "theme": str(analysis.get("theme", "belirsiz")),
                "recommendation": recommendation_text,
                "quality_label": quality.get("quality_label"),
                "weakness": quality.get("weakness"),
                "optimizer_status": optimizer_result.get("status") if isinstance(optimizer_result, dict) else None,
            }
        self.global_store.append_global_lesson(global_lesson)
        self.global_store.update_quality_aggregate(quality, topic_scores)
        self.global_store.append_analytics_run(
            {
                "ts": now_iso(),
                "user_id_hash": f"u_{abs(hash(user_id)) % 1000000}",
                "mode": mode,
                "theme": str(analysis.get("theme", "belirsiz")),
                "quality_label": quality.get("quality_label"),
                "score": quality.get("total_score"),
            }
        )

        if learning_signal and isinstance(learning_signal, dict):
            personal_update = str(learning_signal.get("personal_update", "")).strip()
            global_update = str(learning_signal.get("global_update", "")).strip()
            behavior_update = str(learning_signal.get("behavior_update", "")).strip()
            try:
                self.policies.update_policy_from_learning_signal(user_id, learning_signal)
            except Exception:
                # Non-blocking: background learning should continue even if policy update fails.
                pass
            if personal_update:
                self.personal.append_lesson(
                    user_id,
                    {
                        "ts": now_iso(),
                        "kind": "hybrid_optimizer",
                        "theme": str(analysis.get("theme", "belirsiz")),
                        "behavior": personal_update,
                        "quality_label": str(learning_signal.get("quality_label", "")),
                    },
                )
            if global_update and not sensitive_for_global_or_ft:
                self.global_store.append_global_lesson(
                    {
                        "ts": now_iso(),
                        "mode": mode,
                        "theme": str(analysis.get("theme", "belirsiz")),
                        "recommendation": global_update,
                        "quality_label": str(learning_signal.get("quality_label", "")),
                    }
                )
            elif global_update and sensitive_for_global_or_ft:
                self.global_store.append_global_lesson(
                    {
                        "ts": now_iso(),
                        "mode": mode,
                        "theme": "safety_sensitive_support",
                        "recommendation": "Sensitive case: prefer grounding, validation, and non-judgmental boundary language.",
                        "quality_label": str(learning_signal.get("quality_label", "")),
                    }
                )
            if behavior_update:
                self._apply_behavior_update(user_id, behavior_update)

            ft_candidate = learning_signal.get("fine_tune_candidate")
            ft_score = safe_float(learning_signal.get("score"), 0.0)
            if (
                isinstance(ft_candidate, dict)
                and ft_score >= 0.95
                and safe_float(quality.get("safety_score"), 0.0) >= 0.60
                and not sensitive_for_global_or_ft
            ):
                self.fine.add_candidate(ft_candidate, ft_score)

    def run_background_learning_safe(
        self,
        *,
        user_id: str,
        user_message: str,
        assistant_response: str,
        mode: str,
        analysis: dict[str, Any],
        session_id: str | None,
        learning_context: dict[str, Any] | None = None,
    ) -> None:
        module = "pipeline.run_background_learning"
        try:
            self.run_background_learning(
                user_id=user_id,
                user_message=user_message,
                assistant_response=assistant_response,
                mode=mode,
                analysis=analysis,
                session_id=session_id,
                learning_context=learning_context,
            )
            try:
                self.telemetry.record_background_result(success=True, module=module, error=None)
            except Exception:
                logging.exception("Telemetry write failed on background success path.")
            try:
                # Rotation is part of background maintenance; never block chat flow.
                self.storage_rotation.run_storage_rotation(trigger="background", force=False)
            except Exception:
                logging.exception("Storage rotation failed on background success path.")
        except Exception:
            try:
                self.telemetry.record_background_result(
                    success=False,
                    module=module,
                    error="background_learning_exception",
                )
            except Exception:
                logging.exception("Telemetry write failed on background failure path.")
            logging.exception("Learning Lab background task failed; chat response preserved.")
