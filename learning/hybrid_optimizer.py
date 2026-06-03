from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .quality_evaluator import QualityEvaluator, safe_float
from .response_improver import ResponseImprover


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def shorten(text: str, limit: int = 320) -> str:
    val = (text or "").strip()
    if len(val) <= limit:
        return val
    return val[: limit - 3].rstrip() + "..."


TOPIC_HINTS: dict[str, str] = {
    "technical_guidance": "technical guidance",
    "coding_help": "coding help",
    "confusion_reduction": "confusion reduction",
    "patience_management": "patience management",
    "task_success": "task success",
    "relationships": "relationship awareness",
    "emotional_support": "emotional support",
    "human_like_tone": "human-like warm tone",
    "safety_ethics": "safety and ethics",
    "fine_tune_quality": "fine-tune quality",
    "natural_language": "natural language quality",
    "creative_ideation": "creative ideation",
    "repair_quality": "repair quality",
}

WEAKNESS_STRATEGIES: dict[str, dict[str, str]] = {
    "low_clarity": {
        "behavior_update": "Use short and explicit one-step instructions before any deep explanation.",
        "answer_patch": "Keep it concise, structured, and clear with one immediate next step.",
    },
    "not_hybrid_enough": {
        "behavior_update": "Blend technical, emotional, product, safety, and learning dimensions in one coherent response.",
        "answer_patch": "Combine practical steps with emotional calibration and learning outputs.",
    },
    "low_personalization": {
        "behavior_update": "Use personal learning profile cues more explicitly when shaping response flow.",
        "answer_patch": "Adapt wording and pacing to the user's known preference signals.",
    },
    "low_global_value": {
        "behavior_update": "Extract anonymous, reusable lessons from each conversation.",
        "answer_patch": "Remove personal details and frame lessons as generally reusable guidance.",
    },
    "low_technical_accuracy": {
        "behavior_update": "Prioritize safe, verifiable, and low-risk technical steps.",
        "answer_patch": "Add a validation checkpoint and avoid speculative technical claims.",
    },
    "low_behavioral_value": {
        "behavior_update": "Emit one concrete behavior rule update after each meaningful learning event.",
        "answer_patch": "State which behavior should change and in what context.",
    },
    "low_fine_tune_value": {
        "behavior_update": "Create cleaner, anonymized, instruction-quality candidate pairs.",
        "answer_patch": "Use reusable structure without user-identifying details.",
    },
    "low_safety": {
        "behavior_update": "Remove risky certainty and enforce safety boundaries in ambiguous cases.",
        "answer_patch": "Avoid clinical diagnosis, medication advice, religious rulings, and manipulative language.",
    },
    "too_robotic": {
        "behavior_update": "Shift to warmer single-person language with natural conversational cadence.",
        "answer_patch": "Use direct, human, and calm phrasing without mechanical tone.",
    },
    "low_emotional_alignment": {
        "behavior_update": "Align response tempo and warmth with user emotional intensity.",
        "answer_patch": "Validate feeling first, then move to an actionable next step.",
    },
    "density_mismatch": {
        "behavior_update": "Adapt response density to user preference: short-step or premium-depth mode.",
        "answer_patch": "Tune response length and structure to requested density.",
    },
    "low_task_success": {
        "behavior_update": "Always provide a testable next action and a completion check.",
        "answer_patch": "End with one verifiable next action and expected outcome.",
    },
    "low_repair_value": {
        "behavior_update": "When confusion or friction is detected, enter concise repair language mode.",
        "answer_patch": "Acknowledge gap briefly and restart with one clear step.",
    },
}


def label_from_score(score: float) -> str:
    s = clamp(score)
    if s < 0.70:
        return "weak"
    if s < 0.85:
        return "candidate"
    if s < 0.90:
        return "accepted"
    if s < 0.95:
        return "premium"
    return "elite"


@dataclass
class HybridOptimizer:
    evaluator: QualityEvaluator
    improver: ResponseImprover | None = None

    def __post_init__(self) -> None:
        if self.improver is None:
            self.improver = ResponseImprover()

    def _topic_line(self, topics: list[str]) -> str:
        if not topics:
            return "general learning quality"
        hints = [TOPIC_HINTS.get(t, t) for t in topics]
        return ", ".join(hints[:5])

    def _base_candidate(
        self,
        *,
        attempt: int,
        source_conversation: str,
        topics: list[str],
        user_profile: dict[str, Any] | None,
    ) -> dict[str, Any]:
        topic_line = self._topic_line(topics)
        profile_hint = ""
        if user_profile:
            pref = user_profile.get("preferred_style") or user_profile.get("styleDNA") or []
            if isinstance(pref, list) and pref:
                profile_hint = f" User preference style: {', '.join(str(x) for x in pref[:3])}."

        question = (
            f"How should the AI improve this conversation with a hybrid lens ({topic_line}) "
            f"while staying safe, clear, and human?{profile_hint}"
        )
        ideal_answer = (
            "Start by validating context briefly, then provide one clear action. "
            "If technical, add a verification step. "
            "If emotional intensity is high, reduce response density and keep calm tone. "
            "Record a personal lesson and an anonymous global lesson."
        )
        behavior_update = "When uncertainty appears, respond with one clear next step before deeper detail."
        personal_lesson = "User benefits from concise, structured, low-friction guidance."
        global_lesson = "One-step verified guidance improves completion in mixed technical-emotional contexts."

        return {
            "id": f"hyb_{uuid.uuid4().hex[:10]}",
            "attempt": attempt,
            "topics": list(topics),
            "question": question,
            "ideal_answer": ideal_answer + f" Source cue: {shorten(source_conversation, 180)}",
            "behavior_update": behavior_update,
            "personal_lesson": personal_lesson,
            "global_lesson": global_lesson,
            "fine_tune_ready": False,
            "created_at": now_iso(),
        }

    def _apply_weakness_strategy(
        self,
        candidate: dict[str, Any],
        weakness: str,
        user_profile: dict[str, Any] | None,
        global_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        strategy = WEAKNESS_STRATEGIES.get(
            weakness,
            {
                "behavior_update": "Increase clarity, safety, and practical usefulness in next attempt.",
                "answer_patch": "Use concise, testable, and human-friendly guidance.",
            },
        )
        out = dict(candidate)
        out["id"] = f"hyb_{uuid.uuid4().hex[:10]}"
        out["attempt"] = int(candidate.get("attempt", 0)) + 1

        profile_add = ""
        if user_profile:
            pref = user_profile.get("preferred_style") or []
            if isinstance(pref, list) and pref:
                profile_add = f" Match user style: {', '.join(str(x) for x in pref[:2])}."

        global_add = ""
        if global_context:
            gl = global_context.get("top_pattern") or global_context.get("recommendation")
            if gl:
                global_add = f" Global pattern: {shorten(str(gl), 120)}."

        out["behavior_update"] = strategy["behavior_update"]
        out["ideal_answer"] = (
            f"{strategy['answer_patch']} "
            "Keep safety boundaries and avoid clinical diagnosis, medication advice, religious rulings, or manipulation."
            f"{profile_add}{global_add}"
        )
        out["personal_lesson"] = shorten(
            f"{strategy['behavior_update']} Apply this preference-aware adjustment for the current user context.",
            240,
        )
        out["global_lesson"] = shorten(
            f"{strategy['answer_patch']} Store as anonymous reusable practice for similar future cases.",
            240,
        )
        out["fine_tune_ready"] = False
        out["created_at"] = now_iso()
        return out

    def _candidate_to_quality_input(self, candidate: dict[str, Any], source_conversation: str) -> dict[str, Any]:
        return {
            "messages": [
                {"role": "user", "content": shorten(source_conversation, 1200)},
                {
                    "role": "assistant",
                    "content": (
                        f"{candidate.get('ideal_answer', '')}\n"
                        f"Behavior update: {candidate.get('behavior_update', '')}\n"
                        f"Personal lesson: {candidate.get('personal_lesson', '')}\n"
                        f"Global lesson: {candidate.get('global_lesson', '')}"
                    ).strip(),
                },
            ],
            "meta": {
                "topics": candidate.get("topics", []),
            },
        }

    def _build_learning_signal(
        self,
        *,
        topics: list[str],
        best_candidate: dict[str, Any],
        best_score: float,
        status: str,
    ) -> dict[str, Any]:
        quality_label = (
            "elite"
            if status == "elite_accepted"
            else "premium"
            if status == "premium_accepted"
            else "accepted"
            if status == "accepted"
            else label_from_score(best_score)
        )

        fine_tune_candidate = None
        if quality_label == "elite":
            fine_tune_candidate = {
                "messages": [
                    {"role": "user", "content": best_candidate.get("question", "")},
                    {"role": "assistant", "content": best_candidate.get("ideal_answer", "")},
                ],
                "meta": {"topics": topics, "source": "hybrid_optimizer"},
            }

        return {
            "source": "hybrid_optimizer",
            "topics": topics,
            "quality_label": quality_label,
            "score": round(best_score, 4),
            "personal_update": best_candidate.get("personal_lesson", ""),
            "global_update": best_candidate.get("global_lesson", ""),
            "behavior_update": best_candidate.get("behavior_update", ""),
            "fine_tune_candidate": fine_tune_candidate,
            "created_at": now_iso(),
        }

    def optimize(
        self,
        *,
        user_id: str,
        source_conversation: str,
        topics: list[str],
        user_profile: dict[str, Any] | None = None,
        global_context: dict[str, Any] | None = None,
        conversation_analysis: dict[str, Any] | None = None,
        target_score: float = 0.90,
        elite_score: float = 0.95,
        min_accept_score: float = 0.85,
        max_attempts: int = 80,
        patience: int = 15,
        min_improvement_delta: float = 0.01,
    ) -> dict[str, Any]:
        _ = user_id
        conversation_analysis = conversation_analysis or {}
        response_needs = conversation_analysis.get("response_needs", {}) if isinstance(conversation_analysis, dict) else {}
        optimizer_hints = conversation_analysis.get("optimizer_hints", {}) if isinstance(conversation_analysis, dict) else {}
        convo_topics = conversation_analysis.get("topics", []) if isinstance(conversation_analysis, dict) else []
        micro_ctx = {
            "confusion_level": safe_float(
                (conversation_analysis.get("emotional_state") or {}).get("confusion_level", 0.0)
                if isinstance(conversation_analysis, dict)
                else 0.0,
                0.0,
            ),
            "patience_level": safe_float(
                (conversation_analysis.get("emotional_state") or {}).get("patience_level", 0.7)
                if isinstance(conversation_analysis, dict)
                else 0.7,
                0.7,
            ),
            "trust_shift": safe_float(
                (conversation_analysis.get("emotional_state") or {}).get("trust_level", 0.5) - 0.5
                if isinstance(conversation_analysis, dict)
                else 0.0,
                0.0,
            ),
            "urgency_level": safe_float(
                (conversation_analysis.get("emotional_state") or {}).get("urgency_level", 0.0)
                if isinstance(conversation_analysis, dict)
                else 0.0,
                0.0,
            ),
        }

        preferred_depth = str((user_profile or {}).get("preferred_depth", "adaptive"))
        answer_length = str((response_needs or {}).get("answer_length", "adaptive"))
        if answer_length == "short":
            requested_density = "short"
        elif answer_length == "deep":
            requested_density = "deep"
        else:
            requested_density = preferred_depth

        behavior_hints = list((user_profile or {}).get("preferred_style", []))
        if isinstance(optimizer_hints.get("prioritized_topics"), list):
            behavior_hints.extend(str(t) for t in optimizer_hints.get("prioritized_topics", [])[:3])

        attempts_summary: list[dict[str, Any]] = []
        best_candidate: dict[str, Any] | None = None
        best_score = -1.0
        best_quality: dict[str, Any] | None = None
        no_improvement_count = 0

        current = self._base_candidate(
            attempt=1,
            source_conversation=source_conversation,
            topics=topics,
            user_profile=user_profile,
        )

        for attempt in range(1, max_attempts + 1):
            current["attempt"] = attempt
            base_input = self._candidate_to_quality_input(current, source_conversation)
            base_quality = self.evaluator.evaluate(
                base_input,
                {
                    "behavior_hints": behavior_hints,
                    "requested_density": requested_density,
                    "micro_signals": micro_ctx,
                },
            )
            base_total = safe_float(base_quality.get("total_score"), 0.0)
            base_safety = safe_float(base_quality.get("safety_score"), 0.0)
            targeted_weakness = str(base_quality.get("weakness", "low_clarity"))

            improved_result = (self.improver or ResponseImprover()).improve_candidate(
                current,
                base_quality,
                conversation_analysis=conversation_analysis,
                user_profile=user_profile,
                global_context=global_context,
            )
            improved_candidate = dict(improved_result.get("improved_candidate", current))
            improved_candidate["attempt"] = attempt
            improved_input = self._candidate_to_quality_input(improved_candidate, source_conversation)
            improved_quality = self.evaluator.evaluate(
                improved_input,
                {
                    "behavior_hints": behavior_hints,
                    "requested_density": requested_density,
                    "micro_signals": micro_ctx,
                },
            )
            improved_total = safe_float(improved_quality.get("total_score"), 0.0)
            improved_safety = safe_float(improved_quality.get("safety_score"), 0.0)

            use_improved = False
            if improved_safety >= 0.60:
                if base_safety < 0.60:
                    use_improved = True
                elif improved_total > (base_total + 0.001):
                    use_improved = True

            if use_improved:
                chosen_candidate = dict(improved_candidate)
                chosen_quality = dict(improved_quality)
                chosen_total = improved_total
                chosen_safety = improved_safety
            else:
                chosen_candidate = dict(current)
                chosen_quality = dict(base_quality)
                chosen_total = base_total
                chosen_safety = base_safety

            chosen_candidate["score"] = chosen_quality
            chosen_candidate["targeted_weakness"] = targeted_weakness
            chosen_candidate["applied_improvement_strategy"] = str(improved_result.get("applied_strategy", "none"))
            chosen_candidate["improved_score"] = round(improved_total, 4)
            chosen_candidate["conversation_topics"] = list(convo_topics) if isinstance(convo_topics, list) else []
            chosen_candidate["response_needs"] = response_needs if isinstance(response_needs, dict) else {}

            chosen_weakness = str(chosen_quality.get("weakness", targeted_weakness))
            chosen_label = str(chosen_quality.get("quality_label", label_from_score(chosen_total)))

            improved_best = chosen_safety >= 0.60 and (chosen_total > (best_score + min_improvement_delta))
            if improved_best:
                best_score = chosen_total
                best_candidate = dict(chosen_candidate)
                best_quality = dict(chosen_quality)
                no_improvement_count = 0
            else:
                no_improvement_count += 1

            attempts_summary.append(
                {
                    "attempt": attempt,
                    "candidate_id": chosen_candidate.get("id"),
                    "base_score": round(base_total, 4),
                    "improved_score": round(improved_total, 4),
                    "total_score": round(chosen_total, 4),
                    "quality_label": chosen_label,
                    "safety_score": round(chosen_safety, 4),
                    "weakness": chosen_weakness,
                    "targeted_weakness": targeted_weakness,
                    "applied_improvement_strategy": str(improved_result.get("applied_strategy", "none")),
                    "used_improved_candidate": bool(use_improved),
                    "conversation_topics": list(convo_topics) if isinstance(convo_topics, list) else [],
                    "response_needs": response_needs if isinstance(response_needs, dict) else {},
                    "improvement_notes": list(improved_result.get("improvement_notes", []))
                    if isinstance(improved_result.get("improvement_notes"), list)
                    else [],
                    "improved": bool(improved_best),
                }
            )

            if chosen_safety >= 0.60 and chosen_total >= elite_score:
                final = dict(chosen_candidate)
                final["fine_tune_ready"] = True
                signal = self._build_learning_signal(
                    topics=topics,
                    best_candidate=final,
                    best_score=chosen_total,
                    status="elite_accepted",
                )
                return {
                    "status": "elite_accepted",
                    "accepted": True,
                    "best_score": round(chosen_total, 4),
                    "attempt_count": attempt,
                    "best_candidate": final,
                    "attempts_summary": attempts_summary,
                    "learning_signal": signal,
                }

            if chosen_safety >= 0.60 and chosen_total >= target_score:
                final = dict(chosen_candidate)
                signal = self._build_learning_signal(
                    topics=topics,
                    best_candidate=final,
                    best_score=chosen_total,
                    status="premium_accepted",
                )
                return {
                    "status": "premium_accepted",
                    "accepted": True,
                    "best_score": round(chosen_total, 4),
                    "attempt_count": attempt,
                    "best_candidate": final,
                    "attempts_summary": attempts_summary,
                    "learning_signal": signal,
                }

            if no_improvement_count >= patience:
                break

            # Next candidate from weakness strategy.
            current = self._apply_weakness_strategy(
                chosen_candidate,
                weakness=chosen_weakness,
                user_profile=user_profile,
                global_context=global_context,
            )

        # Final decision after loop
        if best_candidate is not None and best_quality is not None:
            final_best = dict(best_candidate)
            final_best["score"] = best_quality
            final_score = safe_float(best_quality.get("total_score"), best_score)
            final_safety = safe_float(best_quality.get("safety_score"), 0.0)
            if final_safety < 0.60:
                return {
                    "status": "rejected_low_quality",
                    "accepted": False,
                    "best_score": round(final_score, 4),
                    "attempt_count": len(attempts_summary),
                    "best_candidate": final_best,
                    "attempts_summary": attempts_summary,
                    "learning_signal": self._build_learning_signal(
                        topics=topics,
                        best_candidate=final_best,
                        best_score=final_score,
                        status="rejected_low_quality",
                    ),
                }

            if final_score >= min_accept_score:
                status = "accepted"
                if final_score >= target_score:
                    status = "premium_accepted"
                if final_score >= elite_score:
                    status = "elite_accepted"
                    final_best["fine_tune_ready"] = True

                return {
                    "status": status,
                    "accepted": True,
                    "best_score": round(final_score, 4),
                    "attempt_count": len(attempts_summary),
                    "best_candidate": final_best,
                    "attempts_summary": attempts_summary,
                    "learning_signal": self._build_learning_signal(
                        topics=topics,
                        best_candidate=final_best,
                        best_score=final_score,
                        status=status,
                    ),
                }

        stopped_status = "stopped_no_improvement" if attempts_summary and no_improvement_count >= patience else "max_attempts_reached"
        return {
            "status": "rejected_low_quality" if best_score < min_accept_score else stopped_status,
            "accepted": bool(best_score >= min_accept_score),
            "best_score": round(max(0.0, best_score), 4),
            "attempt_count": len(attempts_summary),
            "best_candidate": best_candidate or self._base_candidate(attempt=1, source_conversation=source_conversation, topics=topics, user_profile=user_profile),
            "attempts_summary": attempts_summary,
            "learning_signal": None,
        }

    # Backward compatible alias
    def run(self, seed: dict[str, Any]) -> dict[str, Any]:
        return self.optimize(
            user_id=str(seed.get("user_id", "default_user")),
            source_conversation=str(seed.get("source_conversation", "")),
            topics=list(seed.get("topics", [])) if isinstance(seed.get("topics"), list) else [],
            user_profile=seed.get("user_profile"),
            global_context=seed.get("global_context"),
            conversation_analysis=seed.get("conversation_analysis"),
            target_score=safe_float(seed.get("target_score", 0.90), 0.90),
            elite_score=safe_float(seed.get("elite_score", 0.95), 0.95),
            min_accept_score=safe_float(seed.get("min_accept_score", 0.85), 0.85),
            max_attempts=int(seed.get("max_attempts", 80)),
            patience=int(seed.get("patience", 15)),
            min_improvement_delta=safe_float(seed.get("min_improvement_delta", 0.01), 0.01),
        )
