from __future__ import annotations

from dataclasses import dataclass
from typing import Any


WEIGHTS: dict[str, float] = {
    "clarity": 0.12,
    "hybrid_depth": 0.12,
    "personal_relevance": 0.12,
    "global_reusability": 0.10,
    "technical_accuracy": 0.12,
    "behavioral_improvement": 0.12,
    "fine_tune_value": 0.10,
    "safety_score": 0.08,
    "naturalness": 0.07,
    "emotional_alignment": 0.07,
    "response_density_fit": 0.04,
    "task_success_potential": 0.03,
    "repair_value": 0.01,
}

METRIC_TO_WEAKNESS: dict[str, str] = {
    "clarity": "low_clarity",
    "hybrid_depth": "not_hybrid_enough",
    "personal_relevance": "low_personalization",
    "global_reusability": "low_global_value",
    "technical_accuracy": "low_technical_accuracy",
    "behavioral_improvement": "low_behavioral_value",
    "fine_tune_value": "low_fine_tune_value",
    "safety_score": "low_safety",
    "naturalness": "too_robotic",
    "emotional_alignment": "low_emotional_alignment",
    "response_density_fit": "density_mismatch",
    "task_success_potential": "low_task_success",
    "repair_value": "low_repair_value",
}

UNSAFE_PATTERNS = (
    "tani",
    "diagnosis",
    "ilac",
    "medicine dosage",
    "tedavi",
    "treatment plan",
    "kesin cozum",
    "dini hukum",
    "fatwa",
    "kendine zarar ver",
)

RISK_PATTERNS = (
    "bunu kesin yap",
    "garanti",
    "yuzde yuz",
)

TECH_WORDS = (
    "kod",
    "python",
    "javascript",
    "html",
    "css",
    "api",
    "deploy",
    "render",
    "github",
    "fastapi",
    "endpoint",
    "terminal",
)

EMOTION_WORDS = (
    "hissed",
    "kayg",
    "uzgun",
    "yalniz",
    "sakin",
    "kirgin",
    "zor",
)

ARCH_WORDS = ("mimari", "katman", "modul", "pipeline", "sistem", "strateji")
LEARNING_WORDS = ("ogren", "lesson", "policy", "behavior", "personal", "global", "dashboard")
SAFETY_WORDS = ("guvenli", "risk", "sinir", "etik", "kriz")
ACTION_WORDS = ("1.", "2.", "once", "sonra", "adim", "kontrol", "dogrula")
REPAIR_WORDS = ("haklisin", "anliyorum", "yavaslayalim", "tek adim", "toparlayayim", "duzelteyim")
WARM_WORDS = ("beraber", "yanindayim", "sakin", "nazik", "yardimci")
ROBOTIC_WORDS = ("kullanici", "sistem", "modul", "analiz", "prosedur")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def fold_tr_ascii(text: str) -> str:
    mapping = str.maketrans(
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
    return (text or "").translate(mapping).lower()


def count_hits(text: str, words: tuple[str, ...]) -> int:
    low = fold_tr_ascii(text)
    return sum(1 for w in words if w in low)


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
class QualityEvaluator:
    """Heuristic quality evaluator (stage-3)."""

    def evaluate(self, candidate: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        messages = candidate.get("messages", []) if isinstance(candidate, dict) else []
        user_text = " ".join(str(m.get("content", "")) for m in messages if str(m.get("role", "")).lower() == "user").strip()
        assistant_text = " ".join(str(m.get("content", "")) for m in messages if str(m.get("role", "")).lower() == "assistant").strip()
        text = assistant_text or " ".join(str(m.get("content", "")) for m in messages).strip()

        words = [w for w in text.split() if w.strip()]
        n_words = len(words)
        n_sentences = max(1, text.count(".") + text.count("?") + text.count("!"))
        avg_sentence_len = n_words / n_sentences

        clarity = 0.55
        if 35 <= n_words <= 220:
            clarity += 0.20
        if 8 <= avg_sentence_len <= 22:
            clarity += 0.15
        if count_hits(text, ACTION_WORDS) > 0:
            clarity += 0.10
        clarity = clamp(clarity)

        domain_count = 0
        if count_hits(text, TECH_WORDS) > 0:
            domain_count += 1
        if count_hits(text, EMOTION_WORDS) > 0:
            domain_count += 1
        if count_hits(text, ARCH_WORDS) > 0:
            domain_count += 1
        if count_hits(text, SAFETY_WORDS) > 0:
            domain_count += 1
        if count_hits(text, LEARNING_WORDS) > 0:
            domain_count += 1
        hybrid_depth = clamp(0.2 + (domain_count / 5.0) * 0.8)

        behavior_hints = context.get("behavior_hints", []) if isinstance(context.get("behavior_hints"), list) else []
        hint_hit = 0
        folded_text = fold_tr_ascii(text)
        for hint in behavior_hints[:3]:
            h = fold_tr_ascii(str(hint))
            tokens = [t for t in h.split() if len(t) > 3][:4]
            if any(t in folded_text for t in tokens):
                hint_hit += 1
        personal_relevance = clamp(0.45 + hint_hit * 0.2 + (0.1 if count_hits(text, ("tek adim", "adim adim")) else 0.0))

        personal_markers = ("teoman", "user_", "mail", "@", "telefon")
        personal_leak = any(p in folded_text for p in personal_markers)
        global_reusability = clamp(0.82 - (0.32 if personal_leak else 0.0))

        tech_signals = count_hits(text, TECH_WORDS)
        tech_task_words = count_hits(user_text, TECH_WORDS)
        technical_accuracy = 0.62
        if tech_task_words > 0:
            technical_accuracy += 0.18 if tech_signals > 0 else -0.22
            technical_accuracy += 0.10 if count_hits(text, ("kontrol", "dogrula", "adim")) > 0 else 0.0
        technical_accuracy = clamp(technical_accuracy)

        behavioral_improvement = clamp(0.45 + 0.2 * (1 if count_hits(text, ("bundan sonra", "once", "sonra", "kural")) else 0) + 0.2 * (1 if count_hits(text, LEARNING_WORDS) else 0))

        fine_tune_value = 0.55
        if not personal_leak:
            fine_tune_value += 0.2
        if 40 <= n_words <= 220:
            fine_tune_value += 0.12
        if count_hits(text, ACTION_WORDS) > 0:
            fine_tune_value += 0.08
        fine_tune_value = clamp(fine_tune_value)

        unsafe_hits = count_hits(text, UNSAFE_PATTERNS)
        risk_hits = count_hits(text, RISK_PATTERNS)
        safety_score = clamp(0.94 - unsafe_hits * 0.30 - risk_hits * 0.12)

        warm_hits = count_hits(text, WARM_WORDS)
        robotic_hits = count_hits(text, ROBOTIC_WORDS)
        naturalness = clamp(0.62 + warm_hits * 0.08 - robotic_hits * 0.04)

        micro = context.get("micro_signals", {}) if isinstance(context.get("micro_signals"), dict) else {}
        confusion_level = safe_float(micro.get("confusion_level"), 0.0)
        emotional_alignment = clamp(0.62 + warm_hits * 0.08 + (0.12 if confusion_level > 0 and count_hits(text, ("tek adim", "yavas", "sakin")) > 0 else 0.0))

        requested_density = fold_tr_ascii(str(context.get("requested_density", "")))
        response_density_fit = 0.64
        if "short" in requested_density or "tek adim" in requested_density:
            response_density_fit = 0.86 if n_words <= 120 else 0.56
        elif "deep" in requested_density or "premium" in requested_density:
            response_density_fit = 0.86 if n_words >= 90 else 0.58
        response_density_fit = clamp(response_density_fit)

        task_success_potential = clamp(0.52 + (0.28 if count_hits(text, ACTION_WORDS) > 0 else 0.0) + (0.12 if "?" in text else 0.0))
        repair_value = clamp(0.35 + (0.55 if count_hits(text, REPAIR_WORDS) > 0 else 0.0))

        metrics = {
            "clarity": clarity,
            "hybrid_depth": hybrid_depth,
            "personal_relevance": personal_relevance,
            "global_reusability": global_reusability,
            "technical_accuracy": technical_accuracy,
            "behavioral_improvement": behavioral_improvement,
            "fine_tune_value": fine_tune_value,
            "safety_score": safety_score,
            "naturalness": naturalness,
            "emotional_alignment": emotional_alignment,
            "response_density_fit": response_density_fit,
            "task_success_potential": task_success_potential,
            "repair_value": repair_value,
        }

        total_score = clamp(sum(metrics[k] * WEIGHTS[k] for k in WEIGHTS))
        quality_label = label_from_score(total_score)
        if safety_score < 0.60:
            quality_label = "unsafe_rejected"

        weakest_metric = min(metrics, key=lambda k: metrics[k])
        weakness = METRIC_TO_WEAKNESS.get(weakest_metric, "low_clarity")

        result = {k: round(v, 4) for k, v in metrics.items()}
        result["total_score"] = round(total_score, 4)
        result["quality_label"] = quality_label
        result["weakness"] = weakness
        return result
