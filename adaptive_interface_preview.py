from __future__ import annotations

import unicodedata
from typing import Any, Dict, List


ADAPTIVE_SURFACES = [
    "default_chat_surface",
    "workspace_surface",
    "visual_surface",
    "drive_minimal_surface",
    "night_calm_surface",
    "decision_surface",
    "finality_closure_surface",
    "pointer_context_bubble",
    "device_bridge_surface",
    "luxway_mobile_surface",
    "emotional_reflection_surface",
    "meta_quality_surface",
    "compact_summary_surface",
    "deep_work_surface",
    "presentation_surface",
    "unknown_surface",
]


UI_DENSITIES = ["ultra_minimal", "minimal", "balanced", "expanded", "deep_work"]


INTERACTION_STYLES = [
    "one_tap",
    "voice_first",
    "command_first",
    "card_based",
    "timeline_based",
    "contextual_bubble",
    "workspace_blocks",
    "calm_text",
    "checklist",
    "preview_only",
]


FALSE_BOUNDARIES = {
    "real_ui_changed": False,
    "frontend_runtime_modified": False,
    "css_modified": False,
    "dom_modified": False,
    "static_index_modified": False,
    "real_action_enabled": False,
    "action_performed": False,
    "memory_read_performed": False,
    "memory_write_performed": False,
    "db_write_performed": False,
    "file_created": False,
    "export_performed": False,
    "device_control_performed": False,
}


def _normalize(text: str) -> str:
    lowered = (text or "").strip().lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return ascii_text.replace("ı", "i")


def adaptive_interface_schema() -> Dict[str, Any]:
    return {
        "layer": "22.4",
        "name": "Adaptive Interface Preview",
        "status": "schema_ready",
        "adaptive_surfaces": ADAPTIVE_SURFACES,
        "ui_densities": UI_DENSITIES,
        "interaction_styles": INTERACTION_STYLES,
        "input_fields": [
            "command",
            "user_context",
            "task_type",
            "energy_state",
            "attention_state",
            "device_context",
            "environment",
            "risk_level",
            "desired_output",
        ],
        "safety_boundary": "Read-only UI recommendation; no real UI runtime, CSS, DOM, theme, or static/index.html change.",
        **FALSE_BOUNDARIES,
        "read_only": True,
    }


def _detect_task_type(command: str, user_context: str, task_type: str) -> str:
    if task_type:
        return task_type
    text = _normalize(f"{command} {user_context}")
    if any(key in text for key in ["workspace", "rapor", "belge", "yazi", "duzenle"]):
        return "workspace"
    if any(key in text for key in ["sunum", "presentation", "slide"]):
        return "presentation"
    if any(key in text for key in ["gorsel", "visual", "ambrosia", "ruya"]):
        return "visual"
    if any(key in text for key in ["surus", "araba", "drive", "eller serbest"]):
        return "drive"
    if any(key in text for key in ["gece", "sakin", "uyku"]):
        return "night_calm"
    if any(key in text for key in ["karar", "decision"]):
        return "decision"
    if any(key in text for key in ["bitti", "tamam", "kapanis", "ship"]):
        return "finality"
    if any(key in text for key in ["sectigim", "yaninda", "baloncuk", "pointer"]):
        return "pointer"
    if any(key in text for key in ["cihaz", "kopru", "telefon", "device"]):
        return "device_bridge"
    if any(key in text for key in ["ozet", "sade", "compact"]):
        return "compact_summary"
    return "general"


def _surface_for(task_type: str, text: str) -> Dict[str, Any]:
    if task_type == "workspace":
        return {
            "surface": "workspace_surface",
            "density": "expanded",
            "style": "workspace_blocks",
            "visible": ["document blocks", "section outline", "next action chip"],
            "hidden": ["decorative panels", "unneeded agent controls"],
            "blocked": ["real export", "file write"],
            "microcopy": "Belgeyi bloklar halinde sakinleştirelim.",
        }
    if task_type == "presentation":
        return {
            "surface": "presentation_surface",
            "density": "balanced",
            "style": "card_based",
            "visible": ["slide outline", "speaker note preview", "structure cards"],
            "hidden": ["dense document controls"],
            "blocked": ["real PPT export", "file write"],
            "microcopy": "Sunum akışını önce kartlarla görelim.",
        }
    if task_type == "visual":
        return {
            "surface": "visual_surface",
            "density": "balanced",
            "style": "card_based",
            "visible": ["style mix", "scene state", "negative constraints"],
            "hidden": ["text-heavy workspace controls"],
            "blocked": ["real image generation"],
            "microcopy": "Görsel niyeti sade bir preview'e çevirelim.",
        }
    if task_type == "drive":
        return {
            "surface": "drive_minimal_surface",
            "density": "ultra_minimal",
            "style": "voice_first",
            "visible": ["one safe prompt", "large confirmation state"],
            "hidden": ["long text", "scrolling lists", "dense buttons"],
            "blocked": ["device control", "message send", "call start"],
            "microcopy": "Tek cümle, düşük dikkat yükü.",
        }
    if task_type == "night_calm":
        return {
            "surface": "night_calm_surface",
            "density": "minimal",
            "style": "calm_text",
            "visible": ["short response", "soft next step", "night tone"],
            "hidden": ["dense controls", "bright action clusters"],
            "blocked": ["real audio playback", "theme runtime change"],
            "microcopy": "Sakin, kısa, yumuşak ilerleyelim.",
        }
    if task_type == "decision":
        return {
            "surface": "decision_surface",
            "density": "balanced",
            "style": "checklist",
            "visible": ["options", "tradeoffs", "recommended next step"],
            "hidden": ["unrelated mode controls"],
            "blocked": ["automatic decision"],
            "microcopy": "Kararı tek ekranda netleştirelim.",
        }
    if task_type == "finality":
        return {
            "surface": "finality_closure_surface",
            "density": "minimal",
            "style": "checklist",
            "visible": ["done state", "missing items", "next step"],
            "hidden": ["new idea expansion"],
            "blocked": ["real task completion", "deploy/export action"],
            "microcopy": "Kapat, park et veya bir sonraki adıma geç.",
        }
    if task_type == "pointer":
        return {
            "surface": "pointer_context_bubble",
            "density": "minimal",
            "style": "contextual_bubble",
            "visible": ["small bubble", "one action", "preview result"],
            "hidden": ["full panel", "global controls"],
            "blocked": ["real screen read", "real click"],
            "microcopy": "Seçili şeyin yanında küçük bir öneri yeter.",
        }
    if task_type == "device_bridge":
        return {
            "surface": "device_bridge_surface",
            "density": "balanced",
            "style": "card_based",
            "visible": ["permission state", "prepared action preview", "blocked real action"],
            "hidden": ["unsafe direct controls"],
            "blocked": ["device control", "send/export/print"],
            "microcopy": "Önce hazırla, onaysız hiçbir şey yapma.",
        }
    if task_type == "compact_summary":
        return {
            "surface": "compact_summary_surface",
            "density": "minimal",
            "style": "one_tap",
            "visible": ["one-screen summary", "single next step"],
            "hidden": ["deep settings", "long explanations"],
            "blocked": ["real save/export"],
            "microcopy": "Tek ekranda, net ve hafif.",
        }
    if task_type == "workspace" and "deep" in text:
        return {
            "surface": "deep_work_surface",
            "density": "deep_work",
            "style": "workspace_blocks",
            "visible": ["outline", "focus section", "source placeholders"],
            "hidden": ["casual chat controls"],
            "blocked": ["real export"],
            "microcopy": "Odak alanını büyüt, gürültüyü azalt.",
        }
    return {
        "surface": "default_chat_surface",
        "density": "balanced",
        "style": "command_first",
        "visible": ["chat answer", "small next step"],
        "hidden": ["advanced controls"],
        "blocked": ["real action"],
        "microcopy": "Önce sade bir cevap, sonra gerekirse yüzey değişimi.",
    }


def preview_adaptive_interface(
    command: str,
    user_context: str = "",
    task_type: str = "",
    energy_state: str = "",
    attention_state: str = "",
    device_context: str = "",
    environment: str = "",
    risk_level: str = "",
    desired_output: str = "",
) -> Dict[str, Any]:
    text = _normalize(" ".join([command, user_context, energy_state, attention_state, device_context, environment, desired_output]))
    detected_task = _detect_task_type(command, user_context, task_type)
    if "deep work" in text or "uzun rapor" in text:
        detected_task = "workspace"
        surface_data = {
            "surface": "deep_work_surface",
            "density": "deep_work",
            "style": "workspace_blocks",
            "visible": ["focus outline", "source placeholders", "section progress"],
            "hidden": ["casual chat clutter", "decorative controls"],
            "blocked": ["real export", "file write"],
            "microcopy": "Odak yüzeyi açık; kapsamı bölümlere ayıralım.",
        }
    else:
        surface_data = _surface_for(detected_task, text)

    if risk_level and _normalize(risk_level) in {"high", "safety", "privacy"}:
        surface_data["density"] = "minimal"
        surface_data["visible"] = list(dict.fromkeys(surface_data["visible"] + ["risk boundary note"]))
        surface_data["blocked"] = list(dict.fromkeys(surface_data["blocked"] + ["high-risk direct action"]))

    return {
        "raw_command": command,
        "detected_task_type": detected_task,
        "detected_context": {
            "user_context": user_context,
            "energy_state": energy_state,
            "attention_state": attention_state,
            "device_context": device_context,
            "environment": environment,
            "risk_level": risk_level,
            "desired_output": desired_output,
        },
        "recommended_surface": surface_data["surface"],
        "ui_density": surface_data["density"],
        "interaction_style": surface_data["style"],
        "visible_elements": surface_data["visible"],
        "hidden_elements": surface_data["hidden"],
        "blocked_elements": surface_data["blocked"],
        "suggested_microcopy": surface_data["microcopy"],
        "accessibility_notes": [
            "Keep text readable and one-screen where possible.",
            "Reduce attention load before adding controls.",
            "Use short microcopy and clear confirmation states.",
        ],
        "safety_boundary": "This is a read-only interface recommendation; no runtime UI, CSS, DOM, or static/index.html change is performed.",
        **FALSE_BOUNDARIES,
        "read_only": True,
    }


def adaptive_interface_status() -> Dict[str, Any]:
    return {
        "layer": "22.4",
        "name": "Adaptive Interface Preview",
        "status": "adaptive_interface_preview_ready",
        "read_only": True,
        "available_endpoints": [
            "GET /adaptive-interface/schema",
            "POST /adaptive-interface/preview",
            "GET /debug/adaptive-interface-status",
        ],
        "adaptive_surfaces": ADAPTIVE_SURFACES,
        "ui_densities": UI_DENSITIES,
        "interaction_styles": INTERACTION_STYLES,
        "core_rule": "Suggest UI surface only; never change frontend runtime, CSS, DOM, or static/index.html.",
        "backlog": ["stop/durdur final block leak"],
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        **FALSE_BOUNDARIES,
    }
