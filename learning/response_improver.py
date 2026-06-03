from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class ResponseImprover:
    """Weakness-driven candidate improver for hybrid optimization."""

    def improve(self, text: str) -> str:
        # Backward-compatible noop path used by older callers.
        return str(text or "")

    def improve_candidate(
        self,
        candidate: dict[str, Any],
        quality_report: dict[str, Any],
        conversation_analysis: dict[str, Any] | None = None,
        user_profile: dict[str, Any] | None = None,
        global_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        conversation_analysis = conversation_analysis or {}
        user_profile = user_profile or {}
        global_context = global_context or {}

        targeted_weakness = str(quality_report.get("weakness", "low_clarity") or "low_clarity")
        base = dict(candidate or {})
        improved = dict(base)
        improved["id"] = f"hyb_{uuid.uuid4().hex[:10]}"
        improved["created_at"] = _now_iso()
        improved["attempt"] = int(base.get("attempt", 0)) + 1

        notes: list[str] = []
        strategy = "general_safety_clarity"

        if targeted_weakness == "low_clarity":
            strategy = "clarity_one_step"
            improved["ideal_answer"] = _clarify_answer(_text(improved.get("ideal_answer")))
            improved["behavior_update"] = "Kullanici karistiginda tek adim + kontrol noktasi ile ilerle."
            notes.append("Cevap sadelestirildi ve net bir sonraki adim one alindi.")

        elif targeted_weakness == "not_hybrid_enough":
            strategy = "hybrid_bridge"
            improved["ideal_answer"] = _append_unique(
                _text(improved.get("ideal_answer")),
                "Teknik adimi, duygusal hizalamayi, guvenlik sinirini ve ogrenme kaydini ayni akista birlestir.",
            )
            improved["behavior_update"] = "Teknik + duygusal + urun + guvenlik + ogrenme boyutlarini birlikte bagla."
            notes.append("Hibrit bag kurallari eklendi.")

        elif targeted_weakness == "low_personalization":
            strategy = "personal_profile_alignment"
            style = _profile_style(user_profile)
            improved["ideal_answer"] = _append_unique(
                _text(improved.get("ideal_answer")),
                f"Kullanici tercihine gore ilerle: {style}.",
            )
            improved["personal_lesson"] = _append_unique(
                _text(improved.get("personal_lesson")),
                "Kullanici stili aktif kullanilarak cevap yogunlugu ayarlanir.",
            )
            notes.append("Kisisel profil sinyalleri cevap diline eklendi.")

        elif targeted_weakness == "low_global_value":
            strategy = "global_generalization"
            improved["ideal_answer"] = _sanitize_personal_data(_text(improved.get("ideal_answer")))
            improved["global_lesson"] = "Kisiye ozel detay olmadan, benzer durumlara uygulanabilir genel ders uret."
            notes.append("Kisisel izler temizlendi, genellenebilir ders guclendirildi.")

        elif targeted_weakness == "low_technical_accuracy":
            strategy = "technical_verification"
            improved["ideal_answer"] = _append_unique(
                _text(improved.get("ideal_answer")),
                "Once kontrol et, sonra tek adim uygula ve sonucu dogrula.",
            )
            improved["behavior_update"] = "Riskli teknik kesinliklerden kacin; her adimda dogrulama iste."
            notes.append("Teknik dogrulama adimi eklendi.")

        elif targeted_weakness == "low_behavioral_value":
            strategy = "explicit_behavior_rule"
            improved["behavior_update"] = "Kural: Kullanici tamam demeden ikinci adima gecme."
            improved["personal_lesson"] = _append_unique(
                _text(improved.get("personal_lesson")),
                "Tek adim onay modelini her teknik blokta uygula.",
            )
            notes.append("Davranis degisimi acik kurala cevrildi.")

        elif targeted_weakness == "low_fine_tune_value":
            strategy = "fine_tune_sanitization"
            improved["question"] = _sanitize_personal_data(_text(improved.get("question")))
            improved["ideal_answer"] = _sanitize_personal_data(_text(improved.get("ideal_answer")))
            improved["global_lesson"] = _append_unique(
                _sanitize_personal_data(_text(improved.get("global_lesson"))),
                "Bu yapi egitim datasina uygun, genellenebilir ve guvenli tutulmali.",
            )
            notes.append("Fine-tune uygunlugu icin anonimlestirme yapildi.")

        elif targeted_weakness == "low_safety":
            strategy = "safety_boundary_rewrite"
            cleaned = _strip_unsafe_claims(_text(improved.get("ideal_answer")))
            improved["ideal_answer"] = _append_unique(
                cleaned,
                "Guvenli sinirlari koru; tani, ilac, tedavi, dini hukum ve manipule edici dilden uzak dur.",
            )
            improved["behavior_update"] = "Safety-first: belirsizlikte kesin yargi verme, dusuk riskli adimla ilerle."
            notes.append("Riskli ifadeler temizlendi, guvenlik siniri netlestirildi.")

        elif targeted_weakness == "too_robotic":
            strategy = "human_warmth_adjustment"
            improved["ideal_answer"] = _humanize(_text(improved.get("ideal_answer")))
            improved["behavior_update"] = "Dogal, tekil ve yakin ton kullan; mekanik kaliplari azalt."
            notes.append("Metin daha dogal ve yakin tona tasindi.")

        elif targeted_weakness == "low_emotional_alignment":
            strategy = "emotional_alignment_tune"
            emo = (conversation_analysis.get("emotional_state") or {}) if isinstance(conversation_analysis, dict) else {}
            intensity = float((emo or {}).get("emotional_intensity", 0.4))
            tone = "sakin ve yavas"
            if intensity >= 0.65:
                tone = "daha sakin, daha kisa ve guven veren"
            improved["ideal_answer"] = _append_unique(
                _text(improved.get("ideal_answer")),
                f"Kullanici tonuna uy: {tone} cevap ver, sonra net bir sonraki adimi sun.",
            )
            notes.append("Duygusal yogunluga gore ton ayari yapildi.")

        elif targeted_weakness == "density_mismatch":
            strategy = "density_control"
            response_needs = conversation_analysis.get("response_needs") if isinstance(conversation_analysis, dict) else {}
            answer_length = str((response_needs or {}).get("answer_length", "medium"))
            if answer_length == "short":
                improved["ideal_answer"] = _compress(_text(improved.get("ideal_answer")), 380)
                notes.append("Yogunluk kisaltilarak tek-adim akisa yaklastirildi.")
            elif answer_length == "deep":
                improved["ideal_answer"] = _append_unique(
                    _text(improved.get("ideal_answer")),
                    "Derinlik korunurken bolumleme yap: baglam, adim, dogrulama, ogrenme.",
                )
                notes.append("Premium derinlik icin yapisal bolumleme eklendi.")
            else:
                notes.append("Orta yogunluk korunarak sade akisa getirildi.")

        elif targeted_weakness == "low_task_success":
            strategy = "task_completion_focus"
            improved["ideal_answer"] = _append_unique(
                _text(improved.get("ideal_answer")),
                "Bu adimi yaptiktan sonra ekranda gordugun sonucu bana yaz; sonra bir sonraki adima gececegim.",
            )
            improved["behavior_update"] = "Her cevapta test edilebilir tek sonraki adim ver."
            notes.append("Gorev tamamlama icin dogrulanabilir adim eklendi.")

        elif targeted_weakness == "low_repair_value":
            strategy = "repair_first"
            improved["ideal_answer"] = _prepend_unique(
                _text(improved.get("ideal_answer")),
                "Haklisin, fazla hizlandim. Simdi tek adim gidelim.",
            )
            improved["behavior_update"] = "Once kisa repair, sonra net adim kuralini uygula."
            notes.append("Repair dili en basa alindi.")

        else:
            improved["ideal_answer"] = _append_unique(
                _text(improved.get("ideal_answer")),
                "Netlik, guvenlik ve uygulanabilirlik dengesiyle tek bir sonraki adim ver.",
            )
            notes.append("Genel iyilestirme stratejisi uygulandi.")

        # Apply always-on sanitization and metadata.
        improved["question"] = _sanitize_personal_data(_text(improved.get("question")))
        improved["ideal_answer"] = _sanitize_personal_data(_text(improved.get("ideal_answer")))
        improved["personal_lesson"] = _sanitize_personal_data(_text(improved.get("personal_lesson")))
        improved["global_lesson"] = _sanitize_personal_data(_text(improved.get("global_lesson")))
        improved["targeted_weakness"] = targeted_weakness
        improved["applied_improvement_strategy"] = strategy

        # Provide a hint for optimizer comparisons.
        improved_score_hint = float(quality_report.get("total_score", 0.0)) + 0.01
        improved["improved_score_hint"] = round(min(1.0, improved_score_hint), 4)

        # Optional global context nudge.
        top_pattern = str(global_context.get("top_pattern", "")).strip()
        if top_pattern:
            improved["global_lesson"] = _append_unique(
                _text(improved.get("global_lesson")),
                f"Global pattern align: {top_pattern}.",
            )
            notes.append("Global pattern ipucu eklendi.")

        return {
            "improved_candidate": improved,
            "improvement_notes": notes,
            "applied_strategy": strategy,
            "targeted_weakness": targeted_weakness,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _compress(text: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _append_unique(base: str, extra: str) -> str:
    base_clean = _text(base)
    extra_clean = _text(extra)
    if not extra_clean:
        return base_clean
    if extra_clean.lower() in base_clean.lower():
        return base_clean
    if not base_clean:
        return extra_clean
    sep = "" if base_clean.endswith((".", "!", "?")) else "."
    return f"{base_clean}{sep} {extra_clean}".strip()


def _prepend_unique(base: str, extra: str) -> str:
    base_clean = _text(base)
    extra_clean = _text(extra)
    if not extra_clean:
        return base_clean
    if extra_clean.lower() in base_clean.lower():
        return base_clean
    if not base_clean:
        return extra_clean
    return f"{extra_clean} {base_clean}".strip()


def _sanitize_personal_data(text: str) -> str:
    out = _text(text)
    out = re.sub(r"\buser_[a-zA-Z0-9_]+\b", "user_x", out, flags=re.IGNORECASE)
    out = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[email]", out)
    out = re.sub(r"https?://\S+", "[link]", out)
    out = re.sub(r"\b(\+?\d[\d\s\-]{6,}\d)\b", "[phone]", out)
    return out.strip()


def _strip_unsafe_claims(text: str) -> str:
    out = _text(text)
    banned = (
        "kesin tani",
        "tani koy",
        "ilac kullan",
        "tedavi plani",
        "dini hukum",
        "kesin cozum",
    )
    lowered = out.lower()
    for token in banned:
        if token in lowered:
            out = re.sub(re.escape(token), "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def _clarify_answer(text: str) -> str:
    src = _text(text)
    if not src:
        return "Once tek adimla ilerleyelim: mevcut sonucu kontrol et ve gorunen durumu paylas."
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", src) if s.strip()]
    if not sentences:
        return src
    concise = " ".join(sentences[:2])
    concise = _compress(concise, 360)
    return _append_unique(concise, "Simdi sadece tek bir sonraki adimi uygula ve sonucu yaz.")


def _humanize(text: str) -> str:
    src = _text(text)
    if not src:
        return "Buradayim, beraber sakin bir adimla ilerleyelim."
    replacements = {
        "kullanici": "sen",
        "sistem": "buradaki akis",
        "prosedur": "yol",
    }
    out = src
    for old, new in replacements.items():
        out = re.sub(rf"\b{old}\b", new, out, flags=re.IGNORECASE)
    out = _prepend_unique(out, "Anliyorum, bunu daha sade ve net goturecegim.")
    return _compress(out, 700)


def _profile_style(profile: dict[str, Any]) -> str:
    pref = profile.get("preferred_style", [])
    if isinstance(pref, list) and pref:
        return ", ".join(str(x) for x in pref[:3])
    depth = str(profile.get("preferred_depth", "adaptive"))
    if depth:
        return f"density={depth}"
    return "sade, net, adim-adim"

