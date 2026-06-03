from __future__ import annotations

from dataclasses import dataclass


CONFUSION_WORDS = ("anlamadim", "nasil", "yani", "karisti", "olmadi", "bulamadim", "nerede")
CLOSING_WORDS = ("tamam", "neyse", "bosver")
TRUST_DROP_WORDS = ("emin misin", "guvenmiyorum", "yanlis", "sacma", "bozma")
URGENCY_WORDS = ("acil", "hemen", "simdi", "yetis")


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


@dataclass
class MicroSignalEngine:
    def analyze(self, user_text: str, assistant_text: str = "") -> dict:
        text = fold_tr_ascii(user_text)
        assistant = fold_tr_ascii(assistant_text)

        def ratio(words: tuple[str, ...], source: str) -> float:
            if not source:
                return 0.0
            hit = sum(1 for w in words if w in source)
            return min(1.0, hit / max(1, len(words) / 2))

        confusion = ratio(CONFUSION_WORDS, text)
        closing = ratio(CLOSING_WORDS, text)
        trust_drop = ratio(TRUST_DROP_WORDS, text)
        urgency = ratio(URGENCY_WORDS, text)

        short = 1.0 if len(text.split()) <= 3 else 0.0
        punctuation_spike = 1.0 if ("??" in user_text or "!!" in user_text) else 0.0
        patience = max(0.0, 1.0 - (confusion * 0.5 + trust_drop * 0.35 + punctuation_spike * 0.15))

        recommendation = "balanced"
        if confusion >= 0.45:
            recommendation = "single_step_clarity"
        if closing >= 0.45:
            recommendation = "gentle_wrap_up"
        if urgency >= 0.45:
            recommendation = "brief_direct_support"

        if assistant and "tek adim" in assistant:
            confusion = max(0.0, confusion - 0.1)

        return {
            "confusion_level": round(confusion, 3),
            "patience_level": round(patience, 3),
            "trust_shift": round(0.5 - trust_drop, 3),
            "closing_signal": round(max(closing, short * 0.3), 3),
            "urgency_level": round(urgency, 3),
            "response_recommendation": recommendation,
            "next_best_behavior": (
                "Kısa ve tek adım ilerle."
                if recommendation == "single_step_clarity"
                else "Nazik kapanış ve baskısız seçenek sun."
                if recommendation == "gentle_wrap_up"
                else "Kısa, net ve güven veren cevap ver."
                if recommendation == "brief_direct_support"
                else "Sıcak ve dengeli akışta devam et."
            ),
        }
