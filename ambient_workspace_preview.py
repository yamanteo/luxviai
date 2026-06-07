from __future__ import annotations

import unicodedata
from typing import Any, Dict, List


WORKSPACE_MODES = [
    "report_workspace",
    "cv_workspace",
    "codex_review_workspace",
    "prompt_builder_workspace",
    "visual_prompt_workspace",
    "decision_workspace",
    "project_planning_workspace",
    "study_workspace",
    "message_draft_workspace",
    "meeting_brief_workspace",
    "finality_workspace",
    "unknown_workspace",
]


AMBIENT_LAYOUTS = [
    "focus_single_column",
    "block_stack",
    "checklist_panel",
    "split_context_preview",
    "compact_review_panel",
    "source_guard_panel",
    "finality_footer",
    "action_queue_preview",
    "visual_style_panel",
    "calm_deep_work_layout",
]


BLOCK_PRIORITIES = [
    "title_block",
    "goal_block",
    "context_block",
    "outline_block",
    "draft_block",
    "source_block",
    "risk_block",
    "checklist_block",
    "next_step_block",
    "finality_block",
    "style_block",
    "tone_block",
    "export_ready_block",
    "send_ready_block",
    "note_block",
    "command_block_hidden_from_export",
    "ai_note_hidden_from_export",
]


FALSE_BOUNDARIES = {
    "real_workspace_modified": False,
    "real_editor_changed": False,
    "real_ui_changed": False,
    "frontend_runtime_modified": False,
    "static_index_modified": False,
    "file_created": False,
    "export_performed": False,
    "send_performed": False,
    "print_performed": False,
    "memory_read_performed": False,
    "memory_write_performed": False,
    "db_write_performed": False,
    "action_performed": False,
}


def _normalize(text: str) -> str:
    lowered = (text or "").strip().lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return ascii_text.replace("ı", "i")


def ambient_workspace_schema() -> Dict[str, Any]:
    return {
        "layer": "22.5",
        "name": "Ambient Workspace Preview",
        "status": "schema_ready",
        "workspace_modes": WORKSPACE_MODES,
        "ambient_layouts": AMBIENT_LAYOUTS,
        "block_priorities": BLOCK_PRIORITIES,
        "input_fields": [
            "command",
            "workspace_context",
            "artifact_type",
            "user_goal",
            "current_blocks",
            "desired_output",
            "risk_level",
            "focus_mode",
        ],
        "safety_boundary": "Read-only workspace environment preview; no editor, UI, file, export, send, print, memory, or DB action.",
        **FALSE_BOUNDARIES,
        "read_only": True,
    }


def _detect_mode(command: str, workspace_context: str, artifact_type: str) -> str:
    if artifact_type and artifact_type.endswith("_workspace"):
        return artifact_type
    artifact_aliases = {
        "report": "report_workspace",
        "rapor": "report_workspace",
        "cv": "cv_workspace",
        "codex": "codex_review_workspace",
        "visual": "visual_prompt_workspace",
        "gorsel": "visual_prompt_workspace",
        "prompt": "prompt_builder_workspace",
        "decision": "decision_workspace",
        "karar": "decision_workspace",
        "finality": "finality_workspace",
    }
    normalized_artifact = _normalize(artifact_type)
    if normalized_artifact in artifact_aliases:
        return artifact_aliases[normalized_artifact]
    text = _normalize(f"{command} {workspace_context} {artifact_type}")
    if any(key in text for key in ["codex", "commit", "endpoint", "test", "smoke"]):
        return "codex_review_workspace"
    if any(key in text for key in ["cv", "ozgecmis"]):
        return "cv_workspace"
    if any(key in text for key in ["rapor", "report"]):
        return "report_workspace"
    if any(key in text for key in ["gorsel prompt", "visual prompt", "stil", "renk", "isik"]):
        return "visual_prompt_workspace"
    if any(key in text for key in ["prompt"]):
        return "prompt_builder_workspace"
    if any(key in text for key in ["karar", "decision"]):
        return "decision_workspace"
    if any(key in text for key in ["plan", "roadmap", "proje"]):
        return "project_planning_workspace"
    if any(key in text for key in ["ders", "calisma", "study", "tez"]):
        return "study_workspace"
    if any(key in text for key in ["mesaj", "mail", "taslak"]):
        return "message_draft_workspace"
    if any(key in text for key in ["toplanti", "brief"]):
        return "meeting_brief_workspace"
    if any(key in text for key in ["bitirme", "bitti", "finality", "kapanis"]):
        return "finality_workspace"
    return "unknown_workspace"


def _layout_for(mode: str, text: str) -> Dict[str, Any]:
    if "kaynak" in text or "uydurma" in text:
        return {
            "layout": "source_guard_panel",
            "visible": ["source_block", "risk_block", "checklist_block", "next_step_block"],
            "quiet": ["draft_block", "tone_block"],
            "cleanup": ["Separate claimed facts from source placeholders.", "Keep unsourced claims out of final text."],
            "microcopy": "Kaynak yoksa iddia yok; önce güvenli yer tutucu.",
            "source_guard": True,
        }
    if "export" in text or "girmeyecek" in text:
        return {
            "layout": "compact_review_panel",
            "visible": ["draft_block", "finality_block", "export_ready_block"],
            "quiet": ["note_block"],
            "cleanup": ["Keep command and ai_note blocks out of export preview.", "Show only clean content blocks."],
            "microcopy": "Komutlar export'e girmez; temiz içerik ayrı kalır.",
            "source_guard": False,
        }
    if mode == "report_workspace":
        return {
            "layout": "block_stack",
            "visible": ["title_block", "goal_block", "outline_block", "source_block", "finality_block"],
            "quiet": ["command_block_hidden_from_export", "ai_note_hidden_from_export"],
            "cleanup": ["Move sources near claims.", "Keep intro/body/result blocks in order."],
            "microcopy": "Raporu başlık, kaynak ve son kontrol bloklarıyla sakinleştir.",
            "source_guard": True,
        }
    if mode == "cv_workspace":
        return {
            "layout": "checklist_panel",
            "visible": ["goal_block", "draft_block", "tone_block", "checklist_block", "finality_block"],
            "quiet": ["source_block", "command_block_hidden_from_export"],
            "cleanup": ["Keep profile, experience, education, skills, language, and contact placeholders visible."],
            "microcopy": "CV alanı temiz, profesyonel ve eksik kontrol odaklı kalsın.",
            "source_guard": False,
        }
    if mode == "codex_review_workspace":
        return {
            "layout": "compact_review_panel",
            "visible": ["goal_block", "risk_block", "checklist_block", "next_step_block", "finality_block"],
            "quiet": ["draft_block", "tone_block"],
            "cleanup": ["Show commit, changed files, endpoints, tests, safety boundary, and next step blocks."],
            "microcopy": "Kod çıktısını commit, test ve risk bloklarıyla kontrol et.",
            "source_guard": False,
        }
    if mode == "visual_prompt_workspace":
        return {
            "layout": "visual_style_panel",
            "visible": ["style_block", "context_block", "risk_block", "checklist_block", "finality_block"],
            "quiet": ["export_ready_block", "send_ready_block"],
            "cleanup": ["Keep style ratio, locked elements, color/light, and scene continuity visible."],
            "microcopy": "Sahne, stil ve kilitli detaylar ayrı dursun.",
            "source_guard": False,
        }
    if mode == "decision_workspace":
        return {
            "layout": "checklist_panel",
            "visible": ["goal_block", "context_block", "risk_block", "next_step_block", "finality_block"],
            "quiet": ["draft_block", "source_block"],
            "cleanup": ["Reduce options to a few clear paths.", "Separate risk from preference."],
            "microcopy": "Kararı seçenek, risk ve sonraki adım olarak sadeleştir.",
            "source_guard": False,
        }
    if mode == "finality_workspace":
        return {
            "layout": "finality_footer",
            "visible": ["checklist_block", "next_step_block", "finality_block"],
            "quiet": ["draft_block", "style_block", "tone_block"],
            "cleanup": ["Show completion score, missing items, closure summary, and next step."],
            "microcopy": "Bitti mi, eksik mi, park mı; tek satırda netleştir.",
            "source_guard": False,
        }
    if "odak" in text or "deep" in text or "daginik" in text:
        return {
            "layout": "calm_deep_work_layout",
            "visible": ["goal_block", "outline_block", "draft_block", "next_step_block"],
            "quiet": ["note_block", "command_block_hidden_from_export", "ai_note_hidden_from_export"],
            "cleanup": ["Hide low-priority notes.", "Keep only the active goal and next step visible."],
            "microcopy": "Dağınıklığı azalt; sadece aktif bloklar kalsın.",
            "source_guard": False,
        }
    return {
        "layout": "focus_single_column",
        "visible": ["goal_block", "context_block", "next_step_block"],
        "quiet": ["note_block", "command_block_hidden_from_export"],
        "cleanup": ["Start with one goal and one next step."],
        "microcopy": "Önce tek hedef, sonra gerekli bloklar.",
        "source_guard": False,
    }


def preview_ambient_workspace(
    command: str,
    workspace_context: str = "",
    artifact_type: str = "",
    user_goal: str = "",
    current_blocks: List[Dict[str, Any]] | None = None,
    desired_output: str = "",
    risk_level: str = "",
    focus_mode: str = "",
) -> Dict[str, Any]:
    text = _normalize(" ".join([command, workspace_context, artifact_type, user_goal, desired_output, risk_level, focus_mode]))
    mode = _detect_mode(command, workspace_context, artifact_type)
    layout = _layout_for(mode, text)
    hidden_from_export = ["command_block_hidden_from_export", "ai_note_hidden_from_export"]
    if "voice" in text:
        hidden_from_export.append("voice_command_hidden_from_export")

    return {
        "raw_command": command,
        "detected_workspace_mode": mode,
        "recommended_layout": layout["layout"],
        "block_priorities": list(dict.fromkeys(layout["visible"] + hidden_from_export)),
        "visible_blocks": layout["visible"],
        "quiet_blocks": layout["quiet"],
        "hidden_from_export_blocks": hidden_from_export,
        "cleanup_suggestions": layout["cleanup"],
        "focus_recommendation": focus_mode or "Keep one active goal, one visible next step, and hide command-only blocks from export.",
        "finality_hint": "Use a finality footer when the work needs done/missing/next-step closure.",
        "source_guard_needed": bool(layout["source_guard"]),
        "suggested_microcopy": layout["microcopy"],
        "current_block_count_preview": len(current_blocks or []),
        "safety_boundary": (
            "Ambient Workspace is read-only: no real editor, UI, static/index.html, file, export, send, print, "
            "memory, DB, or agent action is performed."
        ),
        **FALSE_BOUNDARIES,
        "read_only": True,
    }


def ambient_workspace_status() -> Dict[str, Any]:
    return {
        "layer": "22.5",
        "name": "Ambient Workspace Preview",
        "status": "ambient_workspace_preview_ready",
        "read_only": True,
        "available_endpoints": [
            "GET /ambient-workspace/schema",
            "POST /ambient-workspace/preview",
            "GET /debug/ambient-workspace-status",
        ],
        "workspace_modes": WORKSPACE_MODES,
        "ambient_layouts": AMBIENT_LAYOUTS,
        "block_priorities": BLOCK_PRIORITIES,
        "core_rule": "Suggest workspace environment only; never mutate editor, UI, files, export, send, or memory.",
        "backlog": ["stop/durdur final block leak"],
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        **FALSE_BOUNDARIES,
    }
