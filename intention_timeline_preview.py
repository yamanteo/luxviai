from __future__ import annotations

import unicodedata
from typing import Any, Dict


TIMELINE_INTENTS = [
    "capture_intention",
    "plan_next_step",
    "park_for_later",
    "resume_context",
    "decision_checkpoint",
    "deadline_awareness_preview",
    "project_milestone_preview",
    "follow_up_needed",
    "closure_needed",
    "priority_shift",
    "energy_based_planning",
    "today_focus",
    "later_queue",
    "unknown_intention",
]


TIMELINE_SLOTS = [
    "now",
    "today",
    "tomorrow",
    "this_week",
    "next_week",
    "later",
    "someday",
    "parked",
    "waiting",
    "after_completion",
    "when_energy_available",
    "unknown_time",
]


FALSE_BOUNDARIES = {
    "real_calendar_write_performed": False,
    "real_reminder_created": False,
    "real_task_created": False,
    "real_memory_read_performed": False,
    "real_memory_write_performed": False,
    "db_write_performed": False,
    "file_created": False,
    "export_performed": False,
    "send_performed": False,
    "print_performed": False,
    "action_performed": False,
}


def _normalize(text: str) -> str:
    lowered = (text or "").strip().lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return ascii_text.replace("\u0131", "i").replace("\u00c4\u00b1", "i")


def intention_timeline_schema() -> Dict[str, Any]:
    return {
        "layer": "22.6",
        "name": "Intention Timeline Preview",
        "status": "schema_ready",
        "timeline_intents": TIMELINE_INTENTS,
        "timeline_slots": TIMELINE_SLOTS,
        "input_fields": [
            "command",
            "context_text",
            "project_name",
            "user_goal",
            "current_stage",
            "desired_timeframe",
            "energy_state",
            "priority_level",
            "risk_level",
        ],
        "safety_boundary": (
            "Read-only intention/time planning preview. No calendar, reminder, task, memory, DB, file, export, "
            "send, print, device, or agent action is performed."
        ),
        **FALSE_BOUNDARIES,
        "read_only": True,
    }


def _detect_time_slot(text: str, desired_timeframe: str) -> str:
    combined = _normalize(f"{text} {desired_timeframe}")
    if any(key in combined for key in ["bugun", "today"]):
        return "today"
    if any(key in combined for key in ["simdi", "hemen", "now"]):
        return "now"
    if any(key in combined for key in ["yarin", "tomorrow"]):
        return "tomorrow"
    if any(key in combined for key in ["bu hafta", "this week"]):
        return "this_week"
    if any(key in combined for key in ["haftaya", "gelecek hafta", "next week"]):
        return "next_week"
    if any(key in combined for key in ["sonra", "later", "devam etmek uzere", "devam ederiz"]):
        return "later"
    if any(key in combined for key in ["park", "beklet"]):
        return "parked"
    if any(key in combined for key in ["bitince", "tamamlaninca", "after completion"]):
        return "after_completion"
    if any(key in combined for key in ["enerji", "yorgun", "dusuk"]):
        return "when_energy_available"
    if any(key in combined for key in ["bekliyor", "waiting"]):
        return "waiting"
    return "unknown_time"


def _detect_intent(text: str) -> str:
    if any(key in text for key in ["enerji", "yorgun", "dusuk", "low energy"]):
        return "energy_based_planning"
    if any(key in text for key in ["karar", "decision"]):
        return "decision_checkpoint"
    if any(key in text for key in ["takip", "follow up", "follow-up"]):
        return "follow_up_needed"
    if any(key in text for key in ["milestone", "kilometre tasi", "asama cikar"]):
        return "project_milestone_preview"
    if any(key in text for key in ["siradaki adim", "next step", "sonraki adim"]):
        return "plan_next_step"
    if any(key in text for key in ["bugun", "today", "odaklan"]):
        return "today_focus"
    if any(key in text for key in ["haftaya", "gelecek hafta", "later queue"]):
        return "later_queue"
    if any(key in text for key in ["park", "sonra devam", "devam etmek uzere", "beklet"]):
        return "park_for_later"
    if any(key in text for key in ["bitince", "tekrar ac", "resume", "devam edelim"]):
        return "resume_context"
    if any(key in text for key in ["kapatalim", "kapanis", "bitti mi", "closure"]):
        return "closure_needed"
    if any(key in text for key in ["deadline", "son tarih", "teslim"]):
        return "deadline_awareness_preview"
    if any(key in text for key in ["oncelik", "priority"]):
        return "priority_shift"
    if text:
        return "capture_intention"
    return "unknown_intention"


def _priority_signal(text: str, priority_level: str) -> str:
    priority = _normalize(priority_level)
    if priority:
        return priority
    if any(key in text for key in ["acil", "urgent", "hemen", "bugun"]):
        return "high"
    if any(key in text for key in ["sonra", "park", "haftaya"]):
        return "low_or_deferred"
    return "normal"


def _energy_fit(text: str, energy_state: str) -> str:
    energy = _normalize(energy_state)
    if energy:
        return energy
    if any(key in text for key in ["enerjim dusuk", "yorgun", "dusuk enerji"]):
        return "low_energy_plan"
    if any(key in text for key in ["odak", "focus"]):
        return "focused"
    return "neutral"


def _next_step_for(intent: str, slot: str) -> str:
    if intent == "park_for_later":
        return "Park edilecek noktayi tek cumleyle adlandir ve donus tetigini belirle."
    if intent == "plan_next_step":
        return "Siradaki tek uygulanabilir adimi sec ve zaman slotuna koy."
    if intent == "today_focus":
        return "Bugun gorunur kalacak tek odagi sec."
    if intent == "decision_checkpoint":
        return "Karar bekleyen soruyu, secenekleri ve risk notunu ayir."
    if intent == "energy_based_planning":
        return "Dusuk enerjiye uygun en kucuk ilerleme adimini sec."
    if intent == "follow_up_needed":
        return "Takip gerekip gerekmedigini ve ne zaman bakilacagini isaretle."
    if intent == "closure_needed":
        return "Kapat, park et veya devam et ayrimini netlestir."
    if slot == "next_week":
        return "Haftaya devredilecek basligi ve ilk geri donus adimini yaz."
    return "Niyeti kisa baslik, zaman slotu ve tek sonraki adim olarak preview et."


def preview_intention_timeline(
    command: str,
    context_text: str = "",
    project_name: str = "",
    user_goal: str = "",
    current_stage: str = "",
    desired_timeframe: str = "",
    energy_state: str = "",
    priority_level: str = "",
    risk_level: str = "",
) -> Dict[str, Any]:
    raw_text = " ".join([command, context_text, project_name, user_goal, current_stage, desired_timeframe, energy_state, priority_level, risk_level])
    text = _normalize(raw_text)
    intent = _detect_intent(text)
    slot = _detect_time_slot(text, desired_timeframe)
    decision_needed = intent == "decision_checkpoint" or "karar" in text
    follow_needed = intent == "follow_up_needed" or "takip" in text
    closure_needed = intent == "closure_needed" or any(key in text for key in ["kapatalim", "kapanis", "bitti mi"])
    parked_context = ""
    if intent in {"park_for_later", "later_queue", "resume_context"} or slot in {"parked", "later", "next_week", "after_completion"}:
        parked_context = "Bu baglam gercek hafizaya yazilmaz; yalnizca response preview icinde park noktasi olarak gosterilir."
    resume_trigger = "unknown"
    if slot == "after_completion":
        resume_trigger = "after_current_work_is_complete"
    elif slot in {"parked", "later", "next_week"}:
        resume_trigger = "when_user_returns_to_this_project"
    elif intent == "follow_up_needed":
        resume_trigger = "when_follow_up_is_requested"

    return {
        "raw_command": command,
        "detected_timeline_intent": intent,
        "detected_time_slot": slot,
        "intention_summary": command.strip() or "No explicit intention text provided.",
        "next_step": _next_step_for(intent, slot),
        "parked_context": parked_context,
        "resume_trigger": resume_trigger,
        "timeline_notes": [
            f"Preview slot: {slot}",
            "No real calendar/reminder/task/memory write is performed.",
            "Use this as a planning preview only.",
        ],
        "priority_signal": _priority_signal(text, priority_level),
        "energy_fit": _energy_fit(text, energy_state),
        "decision_checkpoint_needed": decision_needed,
        "follow_up_needed": follow_needed,
        "closure_needed": closure_needed,
        "suggested_microcopy": _microcopy(intent, slot),
        "safety_boundary": (
            "Intention Timeline is read-only: no calendar, reminder, task, memory, DB, file, export, send, "
            "print, device, or agent action is performed."
        ),
        **FALSE_BOUNDARIES,
        "read_only": True,
    }


def _microcopy(intent: str, slot: str) -> str:
    if intent == "park_for_later" or slot == "parked":
        return "Bunu simdilik park ediyoruz; donunce buradan devam ederiz."
    if intent == "today_focus":
        return "Bugun sadece bunu onde tutalim."
    if intent == "decision_checkpoint":
        return "Burada karar bekleyen noktayi isaretliyorum."
    if intent == "energy_based_planning":
        return "Enerji dusukken en kucuk guvenli adimi secelim."
    if intent == "closure_needed":
        return "Kapatma mi, park etme mi, devam mi; bunu netlestirelim."
    if intent == "follow_up_needed":
        return "Bu is takip isteyebilir; simdilik sadece isaretliyorum."
    return "Niyeti zaman cizgisine preview olarak yerlestiriyorum."


def intention_timeline_status() -> Dict[str, Any]:
    return {
        "layer": "22.6",
        "name": "Intention Timeline Preview",
        "status": "intention_timeline_preview_ready",
        "read_only": True,
        "timeline_intents": TIMELINE_INTENTS,
        "timeline_slots": TIMELINE_SLOTS,
        "available_endpoints": [
            "GET /intention-timeline/schema",
            "POST /intention-timeline/preview",
            "GET /debug/intention-timeline-status",
        ],
        "integrates_with_preview_layers": ["Finality Sense", "Ambient Workspace", "Adaptive Interface"],
        "core_rule": "Preview intention/time/next-step placement only; never create calendar, reminder, task, memory, DB, file, send, print, or agent actions.",
        "backlog": ["stop/durdur final block leak"],
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        **FALSE_BOUNDARIES,
    }
