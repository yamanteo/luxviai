from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    out = (text or "").translate(mapping)
    # mojibake fallback patterns (multi-char) must be handled via replace
    out = (
        out.replace("Ã§", "c")
        .replace("Ã‡", "c")
        .replace("ÄŸ", "g")
        .replace("Äž", "g")
        .replace("Ä±", "i")
        .replace("Ä°", "i")
        .replace("Ã¶", "o")
        .replace("Ã–", "o")
        .replace("ÅŸ", "s")
        .replace("Åž", "s")
        .replace("Ã¼", "u")
        .replace("Ãœ", "u")
    )
    return out.lower()


TOPIC_PATTERNS: dict[str, tuple[str, ...]] = {
    "technical_guidance": ("hata", "error", "debug", "deploy", "render", "server", "endpoint", "terminal"),
    "coding_help": ("kod", "code", "python", "javascript", "html", "css", "api", "fonksiyon", "function"),
    "app_development": ("uygulama", "app", "mobil", "web", "tasarim", "ui", "ux"),
    "ai_architecture": ("mimari", "architecture", "pipeline", "modul", "module", "optimizer", "learning lab"),
    "fine_tuning_learning": ("fine tune", "fine-tune", "dataset", "jsonl", "candidate"),
    "personal_learning": ("kisisel", "personal", "profil", "profile", "davranis", "behavior"),
    "global_learning": ("global", "anonim", "anonymous", "genel ders", "global lesson"),
    "emotional_support": ("uzgun", "kotu", "yalniz", "kaygi", "sakin", "destek", "hissed"),
    "relationships": ("iliski", "guven", "kirgin", "yaklasim", "uzaklas", "baglan"),
    "trust_repair": ("yanlis", "olmedi", "olmadı", "bozdu", "haklisin", "guzel ama", "repair"),
    "confusion_reduction": ("anlamadim", "karisti", "nasil", "yani", "bulamadim", "nerede"),
    "patience_management": ("yavas", "hizli", "adim adim", "tek adim", "sikildim", "uzun"),
    "task_success": ("calisti", "oldu", "tamamlandi", "success", "done", "bitti"),
    "safety_ethics": ("guvenlik", "etik", "risk", "kriz", "sinir", "manipul"),
    "trauma_sensitive": ("travma", "istismar", "saldiri", "tetiklen", "flashback"),
    "natural_language": ("ton", "dil", "ifade", "cumle", "yazi hizi", "dogal"),
    "creative_ideation": ("fikir", "yaratici", "konsept", "vision", "vizyon"),
    "product_design": ("tasarim", "premium", "hiza", "padding", "layout", "safe area"),
    "voice_prosody": ("mikrofon", "sesli", "voice", "prosody", "speech", "dinleme"),
    "micro_signals": ("sabir", "karisik", "confusion", "patience", "trust shift"),
    "dashboard_tracking": ("dashboard", "metrik", "score", "rapor", "tracking"),
}


EMOTION_WORDS: dict[str, tuple[str, ...]] = {
    "anxious": ("kaygi", "panik", "endise", "acil", "yetismiyor"),
    "sad": ("uzgun", "yalniz", "kotu", "kirgin"),
    "angry": ("sacma", "sinir", "ofke", "biktim", "yeter"),
    "hopeful": ("guzel", "harika", "umut", "olacak", "basar"),
    "focused": ("adim", "plan", "yapalim", "devam"),
}


RISK_PATTERNS: dict[str, tuple[str, ...]] = {
    "crisis_risk": ("kendime zarar", "yasamak istemiyorum", "dayanamiyorum"),
    "self_harm_risk": ("kendimi kes", "intihar", "kendime zarar"),
    "violence_risk": ("oldur", "siddet", "zarar ver"),
    "abuse_or_trauma_signal": ("istismar", "saldiri", "travma", "taciz"),
    "addiction_pattern_signal": ("bagimliyim", "bagimlilik", "kumar", "alkol", "madde"),
    "dependency_risk": ("beni birakma", "hep burada kal", "sadece sen", "sen olmazsan"),
    "manipulation_risk": ("manipule et", "kandir", "zorlama", "kontrol et"),
    "clinical_label_risk": ("tani koy", "tedavi", "ilac", "hastalik", "teshis"),
}


LAYER_TOPIC_MAP: dict[str, str] = {
    "emotion": "emotional_support",
    "narrative": "natural_language",
    "contradiction": "confusion_reduction",
    "relationship": "relationships",
    "symbolic": "creative_ideation",
    "dream": "creative_ideation",
    "existential": "emotional_support",
    "memory": "personal_learning",
    "emotional_graph": "dashboard_tracking",
    "hidden": "micro_signals",
    "dynamic_tone": "natural_language",
    "safety_ethics": "safety_ethics",
    "time_ecology": "product_design",
    "cultural_epistemic": "natural_language",
    "reflection": "trust_repair",
    "human_layer": "human_like_tone",
}


NEED_TYPES: tuple[str, ...] = (
    "practical_guidance",
    "explanation",
    "emotional_support",
    "repair_needed",
    "decision_support",
    "idea_generation",
    "technical_debugging",
    "architecture_planning",
    "reassurance",
    "safety_support",
)


TOPIC_LABEL_TO_INTENT: dict[str, str] = {
    "technical_guidance": "teknik yonlendirme istemek",
    "coding_help": "kodlama yardimi istemek",
    "app_development": "uygulama gelistirme destegi istemek",
    "ai_architecture": "ai mimarisi planlamak",
    "fine_tuning_learning": "fine-tuning ogrenme akisi kurmak",
    "personal_learning": "kisisel ogrenme davranisini gelistirmek",
    "global_learning": "global ogrenme kalitesini artirmak",
    "emotional_support": "duygusal destek istemek",
    "relationships": "iliski baglamini anlamak",
    "trust_repair": "guven ve onarim ihtiyaci",
    "confusion_reduction": "karmasayi azaltmak",
    "patience_management": "daha sade ve yavas akis istemek",
    "task_success": "gorev sonucuna ulasmak",
    "safety_ethics": "guvenlik ve etik cerceveyi korumak",
    "trauma_sensitive": "hassas bir konuyu guvenli ele almak",
    "natural_language": "ifade ve ton iyilestirmesi istemek",
    "creative_ideation": "yaratici fikir uretmek",
    "product_design": "urun tasarimi iyilestirmek",
    "voice_prosody": "sesli komut ve ritim deneyimini duzeltmek",
    "micro_signals": "kullanici sinyallerini daha iyi yorumlamak",
    "dashboard_tracking": "gelisim metriklerini takip etmek",
}


def _hits(text: str, patterns: tuple[str, ...]) -> int:
    return sum(1 for p in patterns if p in text)


def _resolve_topic_scores(text: str, analysis: dict[str, Any]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for topic, patterns in TOPIC_PATTERNS.items():
        hit = _hits(text, patterns)
        if hit > 0:
            scores[topic] = hit / max(1, len(patterns))

    layers = analysis.get("layers") if isinstance(analysis, dict) else {}
    if isinstance(layers, dict):
        for layer_key, enabled in layers.items():
            if not enabled:
                continue
            topic = LAYER_TOPIC_MAP.get(str(layer_key))
            if topic:
                scores[topic] = max(scores.get(topic, 0.0), 0.35)
    return scores


def _dominant_emotion(text: str, analysis: dict[str, Any]) -> str:
    from_analysis = str((analysis or {}).get("primary_emotion", "")).strip()
    if from_analysis:
        return from_analysis
    best = ("neutral", 0)
    for label, words in EMOTION_WORDS.items():
        count = _hits(text, words)
        if count > best[1]:
            best = (label, count)
    return best[0]


def _extract_active_task(text: str, analysis: dict[str, Any]) -> str:
    theme = str((analysis or {}).get("theme", "")).strip()
    if theme:
        return theme
    if "render" in text or "deploy" in text:
        return "Render deployment"
    if "api" in text or "endpoint" in text or "server" in text:
        return "API and server flow"
    if "mobil" in text or "mobile" in text:
        return "Mobile UX stabilization"
    if "dil" in text or "language" in text or "ceviri" in text:
        return "Localization quality"
    return "General conversation quality"


def _task_stage(text: str) -> str:
    if any(x in text for x in ("hata", "error", "debug", "olmadi", "calismiyor")):
        return "debugging"
    if any(x in text for x in ("deploy", "build", "release")):
        return "deployment"
    if any(x in text for x in ("tasarim", "ui", "ux", "hiza", "padding")):
        return "design_refinement"
    if any(x in text for x in ("plan", "mimari", "architecture", "strategy")):
        return "architecture_planning"
    if any(x in text for x in ("test", "kontrol", "verify", "smoke")):
        return "validation"
    return "ongoing"


def _last_completed_step(session: dict[str, Any] | None) -> str:
    if not isinstance(session, dict):
        return ""
    messages = session.get("messages")
    if not isinstance(messages, list):
        return ""
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        if str(msg.get("role", "")).lower() != "user":
            continue
        content = fold_tr_ascii(str(msg.get("content", "")))
        if any(x in content for x in ("tamam", "oldu", "calisti", "yaptim", "bitti")):
            return str(msg.get("content", ""))[:220]
    return ""


def _risk_flags(text: str, analysis: dict[str, Any]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for key, patterns in RISK_PATTERNS.items():
        out[key] = _hits(text, patterns) > 0

    # keep analysis safety signals as high-priority hints if available
    safety_layer = analysis.get("safety_layer") if isinstance(analysis, dict) else {}
    if isinstance(safety_layer, dict):
        crisis_ctx = str(safety_layer.get("crisis_context", "")).strip()
        if crisis_ctx:
            out["crisis_risk"] = True
    if bool(analysis.get("crisis_risk")):
        out["crisis_risk"] = True

    return out


def _status_from_trust(value: float) -> str:
    if value >= 0.1:
        return "rising"
    if value <= -0.1:
        return "falling"
    return "stable"


def _bool_topic(topics: list[str], key: str) -> bool:
    return key in topics


@dataclass
class ConversationAnalyzer:
    def analyze_conversation(
        self,
        user_id: str,
        user_message: str,
        assistant_reply: str | None = None,
        existing_analysis: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
        micro_signals: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = user_id
        analysis = existing_analysis or {}
        profile = profile or {}
        micro = micro_signals or {}

        raw_user = str(user_message or "")
        raw_assistant = str(assistant_reply or "")
        merged_text = fold_tr_ascii(f"{raw_user}\n{raw_assistant}")
        user_text = fold_tr_ascii(raw_user)

        topic_scores = _resolve_topic_scores(merged_text, analysis)
        if not topic_scores:
            topic_scores["natural_language"] = 0.2

        topics = [k for k, _ in sorted(topic_scores.items(), key=lambda item: item[1], reverse=True)]
        if safe_float(micro.get("confusion_level"), 0.0) >= 0.35 and "confusion_reduction" not in topics:
            topics.append("confusion_reduction")
        if safe_float(micro.get("patience_level"), 1.0) <= 0.55 and "patience_management" not in topics:
            topics.append("patience_management")
        if any(_bool_topic(topics, t) for t in ("technical_guidance", "coding_help", "app_development")) and "task_success" not in topics:
            topics.append("task_success")
        if _hits(merged_text, RISK_PATTERNS["clinical_label_risk"]) > 0 and "safety_ethics" not in topics:
            topics.append("safety_ethics")
        topics = topics[:10]

        dominant_topic = topics[0] if topics else "natural_language"
        visible_intent = TOPIC_LABEL_TO_INTENT.get(dominant_topic, "genel yardim istemek")

        confusion = clamp(safe_float(micro.get("confusion_level"), 0.0))
        patience = clamp(safe_float(micro.get("patience_level"), 0.7))
        trust_shift = clamp(safe_float(micro.get("trust_shift"), 0.5), -1.0, 1.0)
        urgency = clamp(safe_float(micro.get("urgency_level"), 0.0))
        closing_signal = clamp(safe_float(micro.get("closing_signal"), 0.0))

        hidden_intent = "daha guvenli ve net yonlendirme ihtiyaci"
        need_type = "practical_guidance"
        if dominant_topic in {"emotional_support", "relationships", "trust_repair"}:
            hidden_intent = "gorulmek ve duygusal olarak anlasilmak"
            need_type = "emotional_support"
        elif dominant_topic in {"ai_architecture", "fine_tuning_learning"}:
            hidden_intent = "sistematik ve yuksek kalite mimari netligi"
            need_type = "architecture_planning"
        elif dominant_topic in {"confusion_reduction", "patience_management"}:
            hidden_intent = "karmasayi azaltip tek adimla ilerlemek"
            need_type = "explanation"
        elif urgency >= 0.45:
            hidden_intent = "hizli ve dusuk riskli cozumle bloktan cikmak"
            need_type = "technical_debugging"
        elif closing_signal >= 0.5:
            hidden_intent = "baskisiz, sakin ve yormayan bir akis"
            need_type = "reassurance"
        if need_type not in NEED_TYPES:
            need_type = "practical_guidance"

        intent = {
            "visible_intent": visible_intent,
            "hidden_intent": hidden_intent,
            "need_type": need_type,
            "urgency": round(urgency, 3),
            "confidence": round(clamp(0.55 + min(0.4, len(topics) * 0.04)), 3),
        }

        fatigue = clamp((1.0 - patience) * 0.55 + closing_signal * 0.45)
        openness = clamp(0.45 + min(0.35, len(raw_user.split()) / 120.0) - closing_signal * 0.2)
        emotion = _dominant_emotion(merged_text, analysis)
        emotional_masking_possible = (
            "iyiyim" in user_text and any(x in user_text for x in ("ama", "neyse", "bosver"))
        ) or closing_signal >= 0.55

        emotional_state = {
            "primary_emotion": emotion,
            "emotional_intensity": round(clamp(0.3 + urgency * 0.35 + confusion * 0.2 + (1.0 - patience) * 0.15), 3),
            "confusion_level": round(confusion, 3),
            "patience_level": round(patience, 3),
            "trust_level": round(clamp(0.5 + (trust_shift * 0.4)), 3),
            "urgency_level": round(urgency, 3),
            "fatigue_level": round(fatigue, 3),
            "openness_level": round(openness, 3),
            "closing_signal": round(closing_signal, 3),
            "emotional_masking_possible": bool(emotional_masking_possible),
        }

        active_task = _extract_active_task(merged_text, analysis)
        stage = _task_stage(merged_text)
        blocked = any(x in user_text for x in ("hata", "error", "olmadi", "calismiyor", "takildi", "anlamadim"))
        success_signal = any(x in user_text for x in ("oldu", "calisti", "tamam", "bitti", "cozuldu"))
        dropoff = clamp(fatigue * 0.5 + confusion * 0.3 + (0.2 if blocked else 0.0))

        next_best_step = "Mevcut ekranda gordugunu tek satirla paylas, sonra sadece bir adim ilerleyelim."
        if "technical_guidance" in topics or "coding_help" in topics:
            next_best_step = "Once tek bir kontrol adimi yap, sonucu paylas, sonra ikinci adima gecelim."
        elif "emotional_support" in topics:
            next_best_step = "Once su anki duygunu tek cumleyle adlandiralim, sonra bir sonraki adimi secelim."

        task_state = {
            "active_task": active_task,
            "task_stage": stage,
            "user_blocked": bool(blocked),
            "last_completed_step": _last_completed_step(session),
            "next_best_step": next_best_step,
            "task_success_signal": bool(success_signal),
            "dropoff_risk": round(dropoff, 3),
        }

        trust_direction = _status_from_trust(trust_shift)
        repair_needed = trust_direction == "falling" or confusion >= 0.4 or any(
            x in user_text for x in ("yanlis", "olmadi", "karisti", "bozdu")
        )
        closeness = any(x in user_text for x in ("yanimda", "dinle", "anla", "destek", "yalniz"))
        space = closing_signal >= 0.55 or any(x in user_text for x in ("sonra", "simdi degil", "bosver"))
        attachment_pressure = "low"
        if any(x in user_text for x in ("birakma", "hep burada", "sadece sen")):
            attachment_pressure = "high"
        elif closeness:
            attachment_pressure = "medium"

        tone = "calm"
        if urgency >= 0.45:
            tone = "direct"
        elif _bool_topic(topics, "emotional_support"):
            tone = "warm"
        elif _bool_topic(topics, "ai_architecture"):
            tone = "deep"
        elif confusion >= 0.35:
            tone = "concise"

        relationship_state = {
            "trust_direction": trust_direction,
            "repair_needed": bool(repair_needed),
            "attachment_pressure": attachment_pressure,
            "user_needs_closeness": bool(closeness),
            "user_needs_space": bool(space),
            "best_tone": tone,
        }

        risks = _risk_flags(merged_text, analysis)
        risk_active = any(bool(v) for v in risks.values())

        answer_length = "medium"
        if confusion >= 0.35 or patience <= 0.55 or urgency >= 0.45:
            answer_length = "short"
        elif "premium" in user_text or "derin" in user_text or _bool_topic(topics, "ai_architecture"):
            answer_length = "deep"

        response_style = "warm"
        if _bool_topic(topics, "technical_guidance") or _bool_topic(topics, "coding_help"):
            response_style = "step_by_step"
        elif urgency >= 0.45:
            response_style = "direct"
        elif _bool_topic(topics, "ai_architecture"):
            response_style = "premium_architecture"
        elif _bool_topic(topics, "emotional_support"):
            response_style = "reflective"

        response_needs = {
            "answer_length": answer_length,
            "response_style": response_style,
            "should_ask_question": bool(not blocked and not risk_active and patience > 0.45),
            "should_give_code": bool(_bool_topic(topics, "coding_help") and confusion < 0.45),
            "should_repair_first": bool(repair_needed),
            "should_slow_down": bool(confusion >= 0.35 or patience <= 0.55),
            "should_use_one_step": bool(confusion >= 0.35 or blocked),
            "should_avoid_theory_labels": True,
        }

        can_personal = bool(topics and (confusion >= 0.2 or blocked or repair_needed))
        can_global = bool(topics and not risks.get("clinical_label_risk", False))
        can_fine = bool(
            can_global
            and not risk_active
            and answer_length != "short"
            and _bool_topic(topics, "technical_guidance")
            and _bool_topic(topics, "task_success")
        )
        behavior_update_needed = (
            "Tek adim + kontrol noktasi + kullanici onayi modeli guclendirilmeli."
            if response_needs["should_use_one_step"]
            else "Ton uyumu korunurken gorev tamamlama adimi netlestirilmeli."
        )
        recommended_focus = (
            "confusion_reduction"
            if confusion >= 0.35
            else "trust_repair"
            if repair_needed
            else "task_success"
            if blocked
            else topics[0]
        )

        learning_opportunity = {
            "can_create_personal_lesson": can_personal,
            "can_create_global_lesson": can_global,
            "can_create_fine_tune_candidate": can_fine,
            "behavior_update_needed": behavior_update_needed,
            "dashboard_topic": topics[0] if topics else "natural_language",
            "recommended_training_focus": recommended_focus,
        }

        personal_candidates: list[str] = []
        if response_needs["should_use_one_step"]:
            personal_candidates.append("Kullanici karistiginda tek adim + sonuc dogrulama akisini uygula.")
        if repair_needed:
            personal_candidates.append("Once kisa repair dili, sonra net eylem adimi ver.")
        if response_style == "premium_architecture":
            personal_candidates.append("Derin teknik mimariyi sade bolumler halinde sun.")

        global_candidates: list[str] = []
        if can_global and _bool_topic(topics, "technical_guidance"):
            global_candidates.append("Teknik bloklarda bir adim + dogrulama kalibi tamamlanma oranini artirir.")
        if can_global and _bool_topic(topics, "confusion_reduction"):
            global_candidates.append("Karmasik anlarda cevap yogunlugunu dusurmek kullanici sabrini korur.")
        if can_global and _bool_topic(topics, "trust_repair"):
            global_candidates.append("Once boslugu kabul edip sonra net adim vermek guveni hizli toparlar.")

        optimizer_hints = {
            "prioritized_topics": topics[:5],
            "target_response_style": response_style,
            "target_answer_length": answer_length,
            "should_force_one_step": response_needs["should_use_one_step"],
            "risk_active": risk_active,
            "targeted_training_focus": recommended_focus,
            "weakness_hint": (
                "low_clarity"
                if response_needs["should_use_one_step"]
                else "low_emotional_alignment"
                if _bool_topic(topics, "emotional_support")
                else "not_hybrid_enough"
                if _bool_topic(topics, "ai_architecture")
                else "low_task_success"
            ),
        }

        return {
            "ts": now_iso(),
            "topics": topics,
            "intent": intent,
            "emotional_state": emotional_state,
            "task_state": task_state,
            "relationship_state": relationship_state,
            "learning_opportunity": learning_opportunity,
            "risk_flags": risks,
            "response_needs": response_needs,
            "personal_learning_candidates": personal_candidates,
            "global_learning_candidates": global_candidates,
            "optimizer_hints": optimizer_hints,
        }


_DEFAULT_ANALYZER = ConversationAnalyzer()


def analyze_conversation(
    user_id: str,
    user_message: str,
    assistant_reply: str | None = None,
    existing_analysis: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    micro_signals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _DEFAULT_ANALYZER.analyze_conversation(
        user_id=user_id,
        user_message=user_message,
        assistant_reply=assistant_reply,
        existing_analysis=existing_analysis,
        session=session,
        profile=profile,
        micro_signals=micro_signals,
    )
