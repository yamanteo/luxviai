from __future__ import annotations

import unicodedata
from typing import Any, Dict, List


FINALITY_STATES = [
    "complete",
    "almost_complete",
    "incomplete",
    "needs_next_step",
    "needs_review",
    "needs_closure_summary",
    "ready_to_ship",
    "blocked",
    "waiting_for_input",
    "overbuilt",
    "should_pause",
    "should_continue_later",
    "decision_needed",
    "risk_check_needed",
    "unknown",
]


ARTIFACT_TYPES = [
    "codex_output",
    "project_update",
    "prompt",
    "report",
    "message_draft",
    "design_review",
    "code_change",
    "roadmap",
    "decision",
    "conversation",
    "task_list",
    "unknown",
]


FALSE_BOUNDARIES = {
    "real_action_enabled": False,
    "action_performed": False,
    "task_completed_performed": False,
    "message_sent": False,
    "file_created": False,
    "export_performed": False,
    "calendar_write_performed": False,
    "memory_read_performed": False,
    "memory_write_performed": False,
    "db_write_performed": False,
    "device_control_performed": False,
}


def _normalize(text: str) -> str:
    lowered = (text or "").strip().lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return ascii_text.replace("ı", "i")


def finality_schema() -> Dict[str, Any]:
    return {
        "layer": "22.3",
        "name": "Finality Sense Preview",
        "status": "schema_ready",
        "finality_states": FINALITY_STATES,
        "artifact_types": ARTIFACT_TYPES,
        "input_fields": [
            "command",
            "context_text",
            "artifact_type",
            "project_stage",
            "user_goal",
            "risk_level",
            "desired_depth",
        ],
        "output_fields": [
            "detected_finality_state",
            "completion_score",
            "missing_items",
            "closure_needed",
            "next_step_needed",
            "recommended_next_step",
            "ship_ready",
            "pause_recommended",
            "continue_later_recommended",
            "risk_check_needed",
            "overbuilding_warning",
            "concise_closure_summary",
        ],
        "safety_boundary": "Read-only finality preview; no task completion, send, export, calendar, memory, DB, or device action.",
        **FALSE_BOUNDARIES,
        "read_only": True,
    }


def _detect_artifact_type(command: str, context_text: str, artifact_type: str) -> str:
    if artifact_type and artifact_type in ARTIFACT_TYPES:
        return artifact_type
    text = _normalize(f"{command} {context_text}")
    if any(key in text for key in ["codex", "commit", "push", "smoke", "endpoint", "static/index", "typewriter"]):
        return "codex_output"
    if any(key in text for key in ["rapor", "report"]):
        return "report"
    if any(key in text for key in ["mesaj", "mail", "draft", "taslak"]):
        return "message_draft"
    if any(key in text for key in ["code", "kod", "bug", "fix"]):
        return "code_change"
    if any(key in text for key in ["roadmap", "layer", "katman", "plan"]):
        return "roadmap"
    if any(key in text for key in ["karar", "decision"]):
        return "decision"
    if any(key in text for key in ["gorev", "task", "checklist"]):
        return "task_list"
    if any(key in text for key in ["prompt"]):
        return "prompt"
    if any(key in text for key in ["tasarim", "design", "gorsel"]):
        return "design_review"
    if any(key in text for key in ["konusma", "conversation", "sohbet"]):
        return "conversation"
    return "unknown"


def _codex_missing_items(text: str) -> List[str]:
    checks = [
        ("commit", "Commit hash/status missing"),
        ("değişen dosya|degisen dosya|changed files", "Changed files not clearly listed"),
        ("endpoint", "Endpoint summary missing"),
        ("test|smoke|pass", "Test result missing"),
        ("chat/stream|typewriter|durdur|static/index", "Safety boundary touch status missing"),
    ]
    missing = []
    for pattern, label in checks:
        if "|" in pattern:
            variants = pattern.split("|")
            if not any(variant in text for variant in variants):
                missing.append(label)
        elif pattern not in text:
            missing.append(label)
    return missing


def _derive_state(command: str, context_text: str, artifact_type: str, risk_level: str) -> Dict[str, Any]:
    text = _normalize(f"{command} {context_text}")
    missing_items: List[str] = []
    state = "unknown"
    score = 45
    closure_needed = False
    next_step_needed = False
    ship_ready = False
    pause_recommended = False
    continue_later = False
    risk_needed = False
    overbuilt_warning = ""

    if any(key in text for key in ["siradaki adim", "sonraki adim", "next step"]):
        state = "needs_next_step"
        score = 62
        next_step_needed = True
    elif any(key in text for key in ["kapanis ozeti", "son bir kapanis", "kapatabilir", "kapatabilir miyiz"]):
        state = "needs_closure_summary"
        score = 78
        closure_needed = True
    elif any(key in text for key in ["ship", "yayina", "canliya", "release"]):
        state = "ready_to_ship"
        score = 82
        ship_ready = True
        risk_needed = True
    elif any(key in text for key in ["eksik", "kaldı mı", "kaldi mi", "missing"]):
        state = "needs_review"
        score = 64
        missing_items = ["Verify required outputs", "Check safety boundaries", "Confirm test result"]
    elif any(key in text for key in ["uzatmayalim", "uzatma", "gereksiz uzadi", "overbuilt"]):
        state = "overbuilt"
        score = 70
        pause_recommended = True
        overbuilt_warning = "This looks like it may be expanding beyond the useful closure point."
    elif any(key in text for key in ["burada duralim", "sonra devam", "park edelim"]):
        state = "should_continue_later"
        score = 68
        continue_later = True
        closure_needed = True
    elif any(key in text for key in ["karar vermem", "karar gerekiyor", "decision"]):
        state = "decision_needed"
        score = 55
        next_step_needed = True
    elif any(key in text for key in ["tamam mi", "bitti mi", "complete", "done"]):
        state = "almost_complete"
        score = 76
        closure_needed = True
    elif not context_text.strip() and len(command.strip()) < 8:
        state = "waiting_for_input"
        score = 30
        missing_items = ["More context would improve the finality preview"]

    if artifact_type == "codex_output":
        codex_missing = _codex_missing_items(text)
        if codex_missing:
            missing_items.extend(item for item in codex_missing if item not in missing_items)
            state = "needs_review"
            score = min(score, 66)
            ship_ready = False
        elif state in {"unknown", "almost_complete", "ready_to_ship"}:
            state = "ready_to_ship"
            score = max(score, 84)
            ship_ready = True
            risk_needed = True

    if risk_level and _normalize(risk_level) in {"high", "privacy", "safety", "critical"}:
        risk_needed = True
        if state == "ready_to_ship":
            state = "risk_check_needed"
            score = min(score, 72)
            ship_ready = False

    if state == "unknown" and context_text.strip():
        state = "needs_review"
        score = 58
        missing_items = ["Clarify acceptance criteria", "Confirm desired next step"]

    return {
        "state": state,
        "score": max(0, min(100, score)),
        "missing_items": missing_items,
        "closure_needed": closure_needed,
        "next_step_needed": next_step_needed,
        "ship_ready": ship_ready,
        "pause_recommended": pause_recommended,
        "continue_later_recommended": continue_later,
        "risk_check_needed": risk_needed,
        "overbuilding_warning": overbuilt_warning,
    }


def preview_finality(
    command: str,
    context_text: str = "",
    artifact_type: str = "",
    project_stage: str = "",
    user_goal: str = "",
    risk_level: str = "",
    desired_depth: str = "",
) -> Dict[str, Any]:
    detected_artifact = _detect_artifact_type(command, context_text, artifact_type)
    derived = _derive_state(command, context_text, detected_artifact, risk_level)

    state = derived["state"]
    if derived["ship_ready"]:
        recommended = "Preview says this may be ready to ship after a final safety/test check; no real deploy is performed."
    elif derived["next_step_needed"]:
        recommended = "Pick one concrete next step and avoid widening the scope."
    elif derived["pause_recommended"]:
        recommended = "Pause expansion, summarize what is done, and continue only if a missing item is real."
    elif derived["continue_later_recommended"]:
        recommended = "Park this with a short closure note; no reminder or calendar write is performed."
    elif derived["closure_needed"]:
        recommended = "Write a short closure summary and stop adding new scope."
    elif state == "waiting_for_input":
        recommended = "Add the artifact or acceptance criteria if you want a sharper finality preview."
    else:
        recommended = "Review missing items, then decide whether to close or continue."

    closure_summary = (
        f"Finality preview: {state}. Score {derived['score']}/100. "
        f"Next: {recommended}"
    )

    return {
        "raw_command": command,
        "detected_artifact_type": detected_artifact,
        "detected_finality_state": state,
        "completion_score": derived["score"],
        "missing_items": derived["missing_items"],
        "closure_needed": derived["closure_needed"],
        "next_step_needed": derived["next_step_needed"],
        "recommended_next_step": recommended,
        "ship_ready": derived["ship_ready"],
        "pause_recommended": derived["pause_recommended"],
        "continue_later_recommended": derived["continue_later_recommended"],
        "risk_check_needed": derived["risk_check_needed"],
        "overbuilding_warning": derived["overbuilding_warning"],
        "concise_closure_summary": closure_summary,
        "finality_reasoning_summary": (
            "This read-only preview uses the supplied command/context to classify closure state, missing items, "
            "next-step need, ship readiness, pause/continue-later signals, and risk-check need."
        ),
        "input_context": {
            "project_stage": project_stage,
            "user_goal": user_goal,
            "risk_level": risk_level,
            "desired_depth": desired_depth or "concise",
        },
        "safety_boundary": (
            "No real completion, send, export, print, file creation, calendar write, memory read/write, DB write, "
            "or device control is performed."
        ),
        **FALSE_BOUNDARIES,
        "read_only": True,
    }


def finality_status() -> Dict[str, Any]:
    return {
        "layer": "22.3",
        "name": "Finality Sense Preview",
        "status": "finality_preview_ready",
        "read_only": True,
        "available_endpoints": [
            "GET /finality/schema",
            "POST /finality/preview",
            "GET /debug/finality-status",
        ],
        "finality_states": FINALITY_STATES,
        "artifact_types": ARTIFACT_TYPES,
        "core_rule": "Preview closure and ship-readiness only; never perform real task completion.",
        "backlog": ["stop/durdur final block leak"],
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        **FALSE_BOUNDARIES,
    }
