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
from .personal_language_dna import PersonalLanguageDNAEngine
from .personal_learning import PersonalLearningStore
from .performance_tracker import PerformanceTracker
from .quality_evaluator import QualityEvaluator
from .symbolic_layer import SymbolicLayerEngine
from .dream_layer import DreamLayerEngine
from .existential_layer import ExistentialLayerEngine
from .storage_rotation import StorageRotationEngine
from .telemetry import TelemetryEngine


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, safe_float(v, lo)))


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
        self.quality = QualityEvaluator()
        self.hybrid = HybridOptimizer(self.quality)
        self.language_dna = PersonalLanguageDNAEngine(self.base_dir)
        self.human_risk = HumanRiskHealingEngine(self.base_dir)
        self.telemetry = TelemetryEngine(self.base_dir)
        self.storage_rotation = StorageRotationEngine(self.base_dir)

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
            # Group-3 Step-1 scaffold order (read-only / no durable writes):
            # 1) memory read, 2) symbolic, 3) dream, 4) existential, 5) memory write candidate.
            group3_memory_read = self.group3_memory.read_memory_signals(
                user_message,
                profile=profile or {},
                session=session or {},
            )
            group3_symbolic = self.group3_symbolic.extract_symbolic_signal(
                user_message,
                analysis=analysis,
                profile=profile or {},
                session=session or {},
            )
            group3_dream = self.group3_dream.extract_dream_signal(
                user_message,
                analysis=analysis,
                profile=profile or {},
                session=session or {},
            )
            group3_existential = self.group3_existential.extract_existential_signal(
                user_message,
                analysis=analysis,
                profile=profile or {},
                session=session or {},
            )
            group3_memory_write = self.group3_memory.propose_memory_write(
                user_message,
                group3_memory_read,
                analysis=analysis,
                safety=(analysis.get("safety_layer") if isinstance(analysis.get("safety_layer"), dict) else {}),
            )
            group3_bundle = Group3Bundle(
                memory_read=group3_memory_read,
                symbolic=group3_symbolic,
                dream=group3_dream,
                existential=group3_existential,
                memory_write_candidate=group3_memory_write,
                safe_summary="group3_step1_scaffold",
                confidence=0.0,
                risk_flags=[],
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
                "language_hints": list(language_probe.get("language_hints", []))
                if isinstance(language_probe.get("language_hints"), list)
                else [],
                "group1_layer_signals": dict(group1_signals),
                "group2_layer_signals": dict(group2_signals),
                "group3_bundle": group3_bundle.to_safe_dict(),
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
                "language_hints": [],
                "group1_layer_signals": {},
                "group2_layer_signals": {},
                "group3_bundle": Group3Bundle.neutral().to_safe_dict(),
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
        group1_signals = self.group1.extract_signals(analysis, user_message)
        group2_signals = self.group2.extract_signals(analysis, user_message)
        # Group-3 Step-1 scaffold order (read-only / no durable writes):
        # 1) memory read, 2) symbolic, 3) dream, 4) existential, 5) memory write candidate.
        group3_memory_read = self.group3_memory.read_memory_signals(
            user_message,
            profile=user_profile,
            session={"session_id": session_id, "mode": mode},
        )
        group3_symbolic = self.group3_symbolic.extract_symbolic_signal(
            user_message,
            analysis=analysis,
            profile=user_profile,
            session={"session_id": session_id, "mode": mode},
        )
        group3_dream = self.group3_dream.extract_dream_signal(
            user_message,
            analysis=analysis,
            profile=user_profile,
            session={"session_id": session_id, "mode": mode},
        )
        group3_existential = self.group3_existential.extract_existential_signal(
            user_message,
            analysis=analysis,
            profile=user_profile,
            session={"session_id": session_id, "mode": mode},
        )
        group3_memory_write = self.group3_memory.propose_memory_write(
            user_message,
            group3_memory_read,
            analysis=analysis,
            safety=(analysis.get("safety_layer") if isinstance(analysis.get("safety_layer"), dict) else {}),
        )
        group3_bundle = Group3Bundle(
            memory_read=group3_memory_read,
            symbolic=group3_symbolic,
            dream=group3_dream,
            existential=group3_existential,
            memory_write_candidate=group3_memory_write,
            safe_summary="group3_step1_scaffold",
            confidence=0.0,
            risk_flags=[],
        )
        self.human_risk.append_signal(
            user_id=user_id,
            signal=human_risk_signal,
            mode=mode,
            session_id=session_id,
        )
        sensitive_for_global_or_ft = self.human_risk.is_sensitive_for_global_or_finetune(human_risk_signal)
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

        perf_row = {
            "ts": now_iso(),
            "topics": topics,
            "response_mode": (
                learning_context.get("response_mode", {})
                if isinstance(learning_context.get("response_mode"), dict)
                else conversation_analysis.get("response_needs", {})
                if isinstance(conversation_analysis, dict)
                else {}
            ),
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
