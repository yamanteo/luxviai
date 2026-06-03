from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io_utils import append_jsonl, load_json, save_json


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


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
    out = (text or "").translate(mapping)
    out = (
        out.replace("Ã§", "c")
        .replace("Ã‡", "c")
        .replace("ÄŸ", "g")
        .replace("Ä", "g")
        .replace("Ä±", "i")
        .replace("Ä°", "i")
        .replace("Ã¶", "o")
        .replace("Ã–", "o")
        .replace("ÅŸ", "s")
        .replace("Å", "s")
        .replace("Ã¼", "u")
        .replace("Ãœ", "u")
    )
    return out.lower()


RISK_PATTERNS: dict[str, tuple[str, ...]] = {
    "addiction_pattern_signal": (
        "kumar",
        "bir kez daha oyna",
        "kaybettim ama",
        "kontrol edemiyorum",
        "bagimlilik",
        "duramiyorum",
    ),
    "violence_risk_signal": (
        "zarar verecegim",
        "oldurecegim",
        "vuracagim",
        "intikam alacagim",
        "siddet",
    ),
    "anger_escalation": (
        "cok sinirlendim",
        "ofkeliyim",
        "patlayacagim",
        "dayanamiyorum",
        "yeter artik",
    ),
    "compulsive_loop_signal": (
        "tekrar tekrar",
        "surekli kontrol",
        "emin olamiyorum",
        "ya olursa",
        "bir daha kontrol etsem",
    ),
    "relationship_distress": (
        "bana guvenmiyor",
        "kavga",
        "gecimsizlik",
        "terk",
        "iliski cok kotu",
        "bittik",
    ),
    "jealousy_control_signal": (
        "kiskaniyorum",
        "kontrol etmek istiyorum",
        "telefonunu karistir",
        "kimle konustu",
        "aldatiyor mu",
    ),
    "betrayal_trust_break": (
        "aldatildi",
        "guvenim kirildi",
        "ihanet",
        "yalan soyledi",
    ),
    "threat_perception_sensitivity": (
        "herkes bana karsi",
        "bana zarar verecekler",
        "kesin kotu niyet",
        "tehdit altindayim",
    ),
    "trauma_sensitivity": (
        "tetiklendi",
        "flashback",
        "donup kaliyorum",
        "kotu bir sey yasadim",
        "guvende hissetmiyorum",
    ),
    "abuse_or_assault_signal": (
        "istismar",
        "taciz",
        "saldiri",
        "tecavuz",
        "aile ici siddet",
    ),
}


DO_NOT_DO = [
    "diagnose",
    "clinical_label",
    "force_disclosure",
    "give_treatment",
    "give_medication_advice",
    "religious_judgment",
    "blame_user",
]


@dataclass
class HumanRiskHealingEngine:
    base_dir: Path

    @property
    def users_dir(self) -> Path:
        return self.base_dir / "data" / "users"

    def _signals_path(self, user_id: str) -> Path:
        return self.users_dir / user_id / "human_risk_healing.jsonl"

    def _summary_path(self, user_id: str) -> Path:
        return self.users_dir / user_id / "human_risk_summary.json"

    def ensure_files(self, user_id: str) -> None:
        summary_path = self._summary_path(user_id)
        if not summary_path.exists():
            save_json(
                summary_path,
                {
                    "counts": {
                        "sensitive": 0,
                        "high_risk": 0,
                        "crisis": 0,
                        "grounding_needed": 0,
                        "boundary_support": 0,
                        "relationship_distress_support": 0,
                        "impulse_slowdown_support": 0,
                        "threat_perception_support": 0,
                        "trauma_sensitive_support": 0,
                    },
                    "last_updated": now_iso(),
                },
            )

    def _pattern_score(self, text: str, key: str) -> float:
        patterns = RISK_PATTERNS.get(key, ())
        if not patterns:
            return 0.0
        hits = sum(1 for p in patterns if p in text)
        if hits <= 0:
            return 0.0
        base = 0.28 if hits == 1 else 0.42
        if hits >= 3:
            base = 0.62
        return clamp(base + min(0.25, (hits - 1) * 0.08))

    def _detect_signals(
        self,
        message: str,
        existing_analysis: dict[str, Any] | None,
        micro_signals: dict[str, Any] | None,
        conversation_analysis: dict[str, Any] | None,
    ) -> dict[str, float]:
        analysis = existing_analysis or {}
        micro = micro_signals or {}
        conv = conversation_analysis or {}
        text = fold_tr_ascii(message)
        out: dict[str, float] = {}

        for key in RISK_PATTERNS:
            out[key] = self._pattern_score(text, key)

        # Use non-clinical supporting hints from prior analysis/micro state.
        confusion = safe_float((micro or {}).get("confusion_level", 0.0), 0.0)
        urgency = safe_float((micro or {}).get("urgency_level", 0.0), 0.0)
        patience = safe_float((micro or {}).get("patience_level", 1.0), 1.0)
        emotional_intensity = safe_float(
            ((conv.get("emotional_state") or {}) if isinstance(conv, dict) else {}).get("emotional_intensity", 0.0),
            0.0,
        )

        if urgency >= 0.72 and patience <= 0.42:
            out["anger_escalation"] = clamp(max(out.get("anger_escalation", 0.0), 0.52))
        if confusion >= 0.65:
            out["compulsive_loop_signal"] = clamp(max(out.get("compulsive_loop_signal", 0.0), 0.36))
        if emotional_intensity >= 0.72:
            out["trauma_sensitivity"] = clamp(max(out.get("trauma_sensitivity", 0.0), 0.26))

        if bool((analysis or {}).get("crisis_risk")):
            out["violence_risk_signal"] = clamp(max(out.get("violence_risk_signal", 0.0), 0.65))

        return out

    def _safety_level(self, risk_signals: dict[str, float], existing_analysis: dict[str, Any] | None) -> str:
        analysis = existing_analysis or {}
        if bool((analysis or {}).get("crisis_risk")):
            return "crisis"

        max_risk = max((safe_float(v, 0.0) for v in risk_signals.values()), default=0.0)
        high_violence = safe_float(risk_signals.get("violence_risk_signal", 0.0), 0.0)
        assault = safe_float(risk_signals.get("abuse_or_assault_signal", 0.0), 0.0)
        if high_violence >= 0.72:
            return "crisis"
        if max_risk >= 0.6 or assault >= 0.55:
            return "high_risk"
        if max_risk >= 0.28:
            return "sensitive"
        return "normal"

    def _recommended_response(self, risk_signals: dict[str, float], safety_level: str) -> dict[str, Any]:
        anger = safe_float(risk_signals.get("anger_escalation", 0.0), 0.0)
        addiction = safe_float(risk_signals.get("addiction_pattern_signal", 0.0), 0.0)
        trauma = safe_float(risk_signals.get("trauma_sensitivity", 0.0), 0.0)
        abuse = safe_float(risk_signals.get("abuse_or_assault_signal", 0.0), 0.0)
        threat = safe_float(risk_signals.get("threat_perception_sensitivity", 0.0), 0.0)
        loop = safe_float(risk_signals.get("compulsive_loop_signal", 0.0), 0.0)

        tone = "calm"
        answer_length = "medium"
        should_validate = False
        should_slow_down = False
        should_avoid_details = False
        should_offer_grounding = False
        should_escalate_safety = False

        if safety_level in {"sensitive", "high_risk", "crisis"}:
            should_validate = True
            should_slow_down = True
            tone = "calm"
            answer_length = "short"

        if max(anger, addiction, trauma, abuse, threat, loop) >= 0.35:
            should_offer_grounding = True

        if abuse >= 0.3 or trauma >= 0.35:
            should_avoid_details = True

        if safety_level in {"high_risk", "crisis"}:
            should_escalate_safety = True

        return {
            "tone": tone,
            "answer_length": answer_length,
            "should_validate": should_validate,
            "should_slow_down": should_slow_down,
            "should_avoid_details": should_avoid_details,
            "should_offer_grounding": should_offer_grounding,
            "should_escalate_safety": should_escalate_safety,
        }

    def analyze_human_risk(
        self,
        user_id: str,
        message: str,
        existing_analysis: dict[str, Any] | None = None,
        micro_signals: dict[str, Any] | None = None,
        conversation_analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.ensure_files(user_id)
        risk_signals = self._detect_signals(message, existing_analysis, micro_signals, conversation_analysis)
        safety_level = self._safety_level(risk_signals, existing_analysis)
        recommended = self._recommended_response(risk_signals, safety_level)
        max_risk = max((safe_float(v, 0.0) for v in risk_signals.values()), default=0.0)

        return {
            "risk_signals": {k: round(clamp(v), 4) for k, v in risk_signals.items()},
            "safety_level": safety_level,
            "recommended_response": recommended,
            "do_not_do": list(DO_NOT_DO),
            "max_risk": round(max_risk, 4),
            "updated_at": now_iso(),
        }

    def append_signal(
        self,
        user_id: str,
        signal: dict[str, Any],
        *,
        mode: str,
        session_id: str | None = None,
    ) -> None:
        self.ensure_files(user_id)
        row = {
            "ts": now_iso(),
            "mode": mode,
            "session_id": _norm_text(session_id),
            "signal": signal,
        }
        append_jsonl(self._signals_path(user_id), row)

        summary = load_json(self._summary_path(user_id), {"counts": {}})
        counts = summary.get("counts", {}) if isinstance(summary.get("counts"), dict) else {}
        safety_level = str(signal.get("safety_level", "normal"))
        if safety_level in {"sensitive", "high_risk", "crisis"}:
            counts["sensitive"] = int(counts.get("sensitive", 0)) + 1
        if safety_level == "high_risk":
            counts["high_risk"] = int(counts.get("high_risk", 0)) + 1
        if safety_level == "crisis":
            counts["crisis"] = int(counts.get("crisis", 0)) + 1

        recommended = signal.get("recommended_response", {}) if isinstance(signal.get("recommended_response"), dict) else {}
        if bool(recommended.get("should_offer_grounding")):
            counts["grounding_needed"] = int(counts.get("grounding_needed", 0)) + 1
        if bool(recommended.get("should_validate")):
            counts["boundary_support"] = int(counts.get("boundary_support", 0)) + 1

        risk = signal.get("risk_signals", {}) if isinstance(signal.get("risk_signals"), dict) else {}
        if safe_float(risk.get("relationship_distress", 0.0), 0.0) >= 0.3:
            counts["relationship_distress_support"] = int(counts.get("relationship_distress_support", 0)) + 1
        if safe_float(risk.get("addiction_pattern_signal", 0.0), 0.0) >= 0.3:
            counts["impulse_slowdown_support"] = int(counts.get("impulse_slowdown_support", 0)) + 1
        if safe_float(risk.get("threat_perception_sensitivity", 0.0), 0.0) >= 0.3:
            counts["threat_perception_support"] = int(counts.get("threat_perception_support", 0)) + 1
        if max(
            safe_float(risk.get("trauma_sensitivity", 0.0), 0.0),
            safe_float(risk.get("abuse_or_assault_signal", 0.0), 0.0),
        ) >= 0.3:
            counts["trauma_sensitive_support"] = int(counts.get("trauma_sensitive_support", 0)) + 1

        summary["counts"] = counts
        summary["last_updated"] = now_iso()
        save_json(self._summary_path(user_id), summary)

    def get_last_signal(self, user_id: str) -> dict[str, Any]:
        path = self._signals_path(user_id)
        if not path.exists():
            return {}
        try:
            import json

            tail: deque[str] = deque(maxlen=1)
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        tail.append(line.strip())
            if not tail:
                return {}
            row = json.loads(tail[-1])
            if isinstance(row, dict) and isinstance(row.get("signal"), dict):
                return row["signal"]
        except Exception:
            return {}
        return {}

    def get_summary_metrics(self, user_id: str) -> dict[str, Any]:
        summary = load_json(self._summary_path(user_id), {"counts": {}})
        counts = summary.get("counts", {}) if isinstance(summary.get("counts"), dict) else {}
        return {
            "regulation_support_score": round(
                clamp(
                    (
                        int(counts.get("grounding_needed", 0))
                        + int(counts.get("boundary_support", 0))
                        + int(counts.get("relationship_distress_support", 0))
                    )
                    / max(1, int(counts.get("sensitive", 0)))
                ),
                4,
            ),
            "safety_sensitive_interactions": int(counts.get("sensitive", 0)),
            "trust_repair_support": int(counts.get("boundary_support", 0)),
            "high_emotional_load_count": int(counts.get("high_risk", 0)) + int(counts.get("crisis", 0)),
            "grounding_needed_count": int(counts.get("grounding_needed", 0)),
            "boundary_support_count": int(counts.get("boundary_support", 0)),
            "relationship_distress_support": int(counts.get("relationship_distress_support", 0)),
            "impulse_slowdown_support": int(counts.get("impulse_slowdown_support", 0)),
            "threat_perception_support": int(counts.get("threat_perception_support", 0)),
            "trauma_sensitive_support": int(counts.get("trauma_sensitive_support", 0)),
            "updated_at": summary.get("last_updated"),
        }

    def is_sensitive_for_global_or_finetune(self, signal: dict[str, Any]) -> bool:
        if not isinstance(signal, dict):
            return False
        safety_level = str(signal.get("safety_level", "normal"))
        if safety_level in {"high_risk", "crisis"}:
            return True
        risk = signal.get("risk_signals", {}) if isinstance(signal.get("risk_signals"), dict) else {}
        sensitive_keys = (
            "abuse_or_assault_signal",
            "trauma_sensitivity",
            "violence_risk_signal",
            "addiction_pattern_signal",
        )
        threshold = 0.28 if safety_level == "sensitive" else 0.35
        for key in sensitive_keys:
            if safe_float(risk.get(key, 0.0), 0.0) >= threshold:
                return True
        return False
