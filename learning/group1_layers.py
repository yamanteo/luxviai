from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


def _lc(value: Any) -> str:
    return _norm_text(value).lower()


def _truthy_word(value: Any, truthy: set[str]) -> bool:
    return _lc(value) in truthy


TRUTHY_HIGH = {"yüksek", "high", "aktif", "var"}


@dataclass
class Group1LayerBridge:
    """Emotion + Hidden + Dynamic Tone + Human Layer bridge.

    This module is intentionally lightweight: it converts existing layer outputs
    into safe numeric signals and short behavior hints without changing chat
    transport format or adding clinical labels.
    """

    def extract_signals(self, analysis: dict[str, Any], message: str = "") -> dict[str, Any]:
        layers = analysis.get("layers", {}) if isinstance(analysis.get("layers"), dict) else {}
        emotion = layers.get("emotion", {}) if isinstance(layers.get("emotion"), dict) else {}
        hidden = layers.get("hidden", {}) if isinstance(layers.get("hidden"), dict) else {}
        dynamic_tone = layers.get("dynamic_tone", {}) if isinstance(layers.get("dynamic_tone"), dict) else {}
        human_layer = layers.get("human_layer", {}) if isinstance(layers.get("human_layer"), dict) else {}

        intensity_raw = _safe_float(emotion.get("intensity", analysis.get("intensity", 5)), 5.0)
        intensity = _clamp(intensity_raw / 10.0)
        needs_presence = bool(analysis.get("needs_presence"))
        needs_silence = bool(analysis.get("needs_silence"))
        needs_solution = bool(analysis.get("needs_solution"))
        contradiction = _truthy_word(analysis.get("contradiction_marker"), {"var", "yes", "true"})
        cognitive_high = _truthy_word(analysis.get("cognitive_load"), {"yüksek", "high"})

        # Emotion block
        emotional_load_level = _clamp(
            intensity * 0.62
            + (0.14 if cognitive_high else 0.0)
            + (0.12 if needs_silence else 0.0)
            + (0.08 if contradiction else 0.0)
        )
        emotion_signal_score = _clamp(
            intensity * 0.55
            + (0.22 if needs_presence else 0.0)
            + (0.12 if _truthy_word(emotion.get("healing_signal"), {"var", "aktif"}) else 0.0)
            + (0.11 if _truthy_word(emotion.get("compression"), {"yüksek", "high"}) else 0.0)
        )

        # Hidden block
        typing_rhythm = _lc(hidden.get("typing_rhythm"))
        writing_style = _lc(hidden.get("writing_style"))
        pause_pattern = _lc(hidden.get("pause_pattern"))
        hidden_need_signal = _clamp(
            (0.35 if "kesik" in writing_style else 0.15)
            + (0.25 if "yavaş" in typing_rhythm or "yavas" in typing_rhythm else 0.12)
            + (0.18 if "uzun" in pause_pattern else 0.08)
            + (0.12 if bool(hidden.get("ghost_hesitation")) else 0.0)
            + (0.10 if needs_silence else 0.0)
        )

        # Dynamic tone block
        tempo = _lc(dynamic_tone.get("tempo"))
        warmth = _lc(dynamic_tone.get("warmth_calibration"))
        reflection_depth = _lc(dynamic_tone.get("reflection_depth"))
        tone_adaptation_score = _clamp(
            (0.28 if tempo in {"çok yavaş", "cok yavas", "yavaş", "yavas"} else 0.15)
            + (0.26 if warmth in {"yüksek", "high"} else 0.16)
            + (0.20 if reflection_depth in {"derin", "orta"} else 0.1)
            + (0.18 if needs_presence else 0.08)
            + (0.08 if needs_solution else 0.12)
        )

        # Human layer block
        human_warmth = _lc(human_layer.get("human_warmth"))
        natural_pause = _lc(human_layer.get("natural_pause"))
        repair_recovery = _lc(human_layer.get("repair_recovery"))
        imperfect_cadence = bool(human_layer.get("imperfect_cadence"))
        human_layer_alignment = _clamp(
            (0.30 if human_warmth in {"yüksek", "high", "orta"} else 0.12)
            + (0.24 if natural_pause in {"aktif", "orta"} else 0.1)
            + (0.22 if repair_recovery else 0.08)
            + (0.12 if imperfect_cadence else 0.06)
            + (0.12 if bool(human_layer) else 0.0)
        )

        # Derived response needs (safe, non-clinical)
        clarity_need_signal = _clamp(
            (0.44 if hidden_need_signal >= 0.5 else 0.2)
            + (0.24 if needs_solution else 0.08)
            + (0.2 if cognitive_high else 0.08)
            + (0.12 if "karış" in _lc(message) or "karis" in _lc(message) else 0.0)
        )
        repair_need_signal = _clamp(
            (0.38 if contradiction else 0.12)
            + (0.26 if needs_presence and emotional_load_level >= 0.55 else 0.1)
            + (0.2 if _truthy_word(analysis.get("attachment_risk"), {"yüksek", "high"}) else 0.0)
            + (0.16 if "karıştırdın" in _lc(message) or "karistirdin" in _lc(message) else 0.0)
        )
        safety_sensitive_signal = _clamp(
            _safe_float(_safe_float(analysis.get("crisis_risk"), 0.0), 0.0)
            + (0.35 if emotional_load_level >= 0.82 else 0.0)
            + (0.25 if _truthy_word(analysis.get("attachment_risk"), {"yüksek", "high"}) else 0.0)
        )
        response_tone_adjustment = (
            "short_calm_one_step"
            if clarity_need_signal >= 0.6 or repair_need_signal >= 0.6
            else "warm_balanced"
            if tone_adaptation_score >= 0.6
            else "direct_clear"
        )

        return {
            "emotion_signal_score": round(emotion_signal_score, 4),
            "hidden_need_signal": round(hidden_need_signal, 4),
            "tone_adaptation_score": round(tone_adaptation_score, 4),
            "human_layer_alignment": round(human_layer_alignment, 4),
            "emotional_load_level": round(emotional_load_level, 4),
            "clarity_need_signal": round(clarity_need_signal, 4),
            "repair_need_signal": round(repair_need_signal, 4),
            "safety_sensitive_signal": round(safety_sensitive_signal, 4),
            "response_tone_adjustment": response_tone_adjustment,
        }

    def behavior_hints(self, signals: dict[str, Any]) -> list[str]:
        hints: list[str] = []
        clarity = _safe_float(signals.get("clarity_need_signal"), 0.0)
        repair = _safe_float(signals.get("repair_need_signal"), 0.0)
        emotional_load = _safe_float(signals.get("emotional_load_level"), 0.0)
        tone = _norm_text(signals.get("response_tone_adjustment"))

        if repair >= 0.6:
            hints.append("Önce kısa bir onarım cümlesi kur, sonra tek net adım ver.")
        if clarity >= 0.55:
            hints.append("Yanıtı kısa ve tek adımlı tut; gereksiz teknik yoğunluk ekleme.")
        if emotional_load >= 0.72:
            hints.append("Ton sakin ve yargısız kalsın; zorlayıcı soru sayısını azalt.")
        if not hints:
            hints.append("Doğal, kısa ve net bir akışla ilerle.")
        if tone == "warm_balanced":
            hints.append("Sıcak ama dengeli bir ritim kullan.")
        return hints[:3]

    def personal_lesson_text(self, signals: dict[str, Any]) -> str:
        if _safe_float(signals.get("repair_need_signal"), 0.0) >= 0.6:
            return "Kullanıcı yoğunlukta önce kısa onarım ve tek adım yaklaşımıyla daha iyi ilerliyor."
        if _safe_float(signals.get("clarity_need_signal"), 0.0) >= 0.6:
            return "Kullanıcı karışıklık sinyalinde kısa ve tek görevli açıklama ile daha hızlı netleşiyor."
        return "Kullanıcı için doğal ton + net adım dengesi korunmalı."

    def global_lesson_text(self, signals: dict[str, Any]) -> str:
        if _safe_float(signals.get("clarity_need_signal"), 0.0) >= 0.6:
            return "Yüksek karışıklık sinyalinde kısa yanıt ve tek adım yaklaşımı başarıyı artırır."
        if _safe_float(signals.get("repair_need_signal"), 0.0) >= 0.6:
            return "Onarım ihtiyacı sinyalinde önce kısa toparlama, sonra net eylem vermek güveni korur."
        return "Doğal ritim ve düşük yoğunluklu açıklama birçok akışta tutarlılığı artırır."

