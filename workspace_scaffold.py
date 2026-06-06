"""Read-only LuxWorkspace schema and block preview scaffold."""

from __future__ import annotations

import unicodedata
import uuid
from typing import Any, Dict, List, Mapping


WORKSPACE_BLOCK_TYPES = [
    "project",
    "document",
    "section",
    "heading",
    "paragraph",
    "command",
    "voice_command",
    "ai_note",
    "source",
    "citation",
    "draft",
    "final",
    "table_placeholder",
    "export_package_preview",
]

WORKSPACE_BLOCK_FIELDS = [
    "id",
    "type",
    "title",
    "content",
    "role",
    "copyable",
    "exportable",
    "editable",
    "order",
    "parent_id",
    "status",
    "metadata",
]

_COMMAND_BLOCK_TYPES = {"command", "voice_command"}
_NON_COPY_EXPORT_TYPES = set(_COMMAND_BLOCK_TYPES)
_NON_EXPORTABLE_INTERNAL_TYPES = {"command", "voice_command", "ai_note"}
_EXPORTABLE_CONTENT_TYPES = {"heading", "paragraph", "draft", "final", "section", "table_placeholder", "export_package_preview"}
_CONTENT_BLOCK_TYPES = {"heading", "paragraph", "draft", "final", "section", "table_placeholder", "export_package_preview"}
_FINAL_OUTPUT_TYPES = {"heading", "paragraph", "draft", "final", "table_placeholder"}


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return (
        text.lower()
        .replace("\u0131", "i")
        .replace("\u0130", "i")
        .replace("\u015f", "s")
        .replace("\u011f", "g")
        .replace("\u00fc", "u")
        .replace("\u00f6", "o")
        .replace("\u00e7", "c")
    )


def _block(
    block_type: str,
    *,
    title: str,
    content: str,
    role: str,
    order: int,
    parent_id: str = "",
    status: str = "preview",
    metadata: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    copyable = block_type not in _NON_COPY_EXPORT_TYPES
    exportable = block_type in _EXPORTABLE_CONTENT_TYPES and block_type not in _NON_EXPORTABLE_INTERNAL_TYPES
    editable = block_type not in {"source", "citation", "export_package_preview"} and block_type not in _NON_COPY_EXPORT_TYPES
    return {
        "id": str(uuid.uuid4()),
        "type": block_type,
        "title": title,
        "content": content,
        "role": role,
        "copyable": copyable,
        "exportable": exportable,
        "editable": editable,
        "order": order,
        "parent_id": parent_id,
        "status": status,
        "metadata": dict(metadata or {}),
    }


def workspace_schema() -> Dict[str, Any]:
    return {
        "block_types": list(WORKSPACE_BLOCK_TYPES),
        "block_fields": list(WORKSPACE_BLOCK_FIELDS),
        "rules": [
            "command and voice_command blocks are never copyable or exportable.",
            "ai_note blocks are internal preview notes and are never exportable.",
            "content blocks such as heading, paragraph, draft, and final can be exportable in preview.",
            "this scaffold never writes files, exports documents, or persists workspace data.",
        ],
        "read_only": True,
        "write_performed": False,
    }


def _workspace_kind(command: str) -> str:
    normalized = _normalize_text(command)
    if "cv" in normalized or "ozgecmis" in normalized:
        return "cv"
    if "sunum" in normalized or "presentation" in normalized:
        return "presentation"
    if "rapor" in normalized:
        return "report"
    if "akademik" in normalized or "paragraf" in normalized:
        return "rewrite"
    if "sonuc" in normalized:
        return "conclusion"
    return "workspace"


def _content_for_kind(kind: str, command: str, content: str) -> Dict[str, str]:
    if kind == "cv":
        return {
            "title": "CV Builder Preview",
            "heading": "Profesyonel CV Taslak Iskeleti",
            "draft": "Profil, deneyim, beceriler ve proje bolumleri icin read-only taslak plan.",
            "final": "CV dosyasi olusturulmaz; kullanici onayi olmadan export veya yazma yapilmaz.",
        }
    if kind == "presentation":
        return {
            "title": "Presentation Preview",
            "heading": "Sunum Akisi Taslagi",
            "draft": "Giris, problem, cozum, kanit ve kapanis slaytlari icin bolum onizlemesi.",
            "final": "Sunum dosyasi olusturulmaz; yalnizca plan onizlemesi sunulur.",
        }
    if kind == "report":
        return {
            "title": "Report Preview",
            "heading": "Rapor Taslak Iskeleti",
            "draft": "Yonetici ozeti, bulgular, analiz ve sonuc bolumleri icin read-only taslak.",
            "final": "Rapor PDF/Word olarak disari aktarilmaz; sadece scaffold preview doner.",
        }
    if kind == "rewrite":
        return {
            "title": "Rewrite Preview",
            "heading": "Akademiklestirme Onizlemesi",
            "draft": content or "Secilen paragraf daha resmi, acik ve akademik bir tona tasinabilir.",
            "final": "Gercek editor degisikligi yapilmaz; kullaniciya sadece onerilen yon verilir.",
        }
    if kind == "conclusion":
        return {
            "title": "Conclusion Preview",
            "heading": "Sonuc Bolumu Onizlemesi",
            "draft": content or "Metin sonuc bolumune uygun olarak toparlayici ve etkili hale getirilebilir.",
            "final": "Metin kaydedilmez; sonuc bolumu icin read-only yapi onerilir.",
        }
    return {
        "title": "Workspace Preview",
        "heading": "LuxWorkspace Blok Onizlemesi",
        "draft": command or "Kullanici komutu workspace bloklarina ayrilabilir.",
        "final": "Bu onizleme kalici workspace veya dosya olusturmaz.",
    }


def build_workspace_preview(command: str, content: str = "") -> Dict[str, Any]:
    kind = _workspace_kind(command)
    copy = _content_for_kind(kind, command, content)
    project_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    section_id = str(uuid.uuid4())
    blocks = [
        {
            **_block(
                "project",
                title="LuxWorkspace Project",
                content="Read-only workspace preview project.",
                role="container",
                order=0,
                metadata={"workspace_kind": kind},
            ),
            "id": project_id,
        },
        {
            **_block(
                "document",
                title=copy["title"],
                content="Document preview container; no file is created.",
                role="container",
                order=1,
                parent_id=project_id,
                metadata={"source": "preview"},
            ),
            "id": document_id,
        },
        _block(
            "command",
            title="User Command",
            content=command,
            role="input_command",
            order=2,
            parent_id=document_id,
            metadata={"read_only": True},
        ),
        {
            **_block(
                "section",
                title="Primary Section",
                content="Generated preview section.",
                role="structure",
                order=3,
                parent_id=document_id,
            ),
            "id": section_id,
        },
        _block("heading", title=copy["heading"], content=copy["heading"], role="content", order=4, parent_id=section_id),
        _block("draft", title="Draft Preview", content=copy["draft"], role="content", order=5, parent_id=section_id),
        _block("final", title="Final Preview Boundary", content=copy["final"], role="content", order=6, parent_id=section_id),
        _block(
            "export_package_preview",
            title="Export Boundary",
            content="Export package is preview-only; Word/PDF/export is disabled.",
            role="boundary",
            order=7,
            parent_id=document_id,
            metadata={"export_enabled": False},
        ),
    ]
    return {
        "workspace_id": str(uuid.uuid4()),
        "command": command,
        "content": content,
        "workspace_kind": kind,
        "blocks": blocks,
        "schema": workspace_schema(),
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
        "file_created": False,
        "export_performed": False,
    }


def _is_voice_command(command: str) -> bool:
    normalized = _normalize_text(command)
    return "sesli komut" in normalized or "voice command" in normalized


def _safe_preview_content(command: str, content: str) -> str:
    if content.strip():
        return content
    kind = _workspace_kind(command)
    if kind == "workspace":
        return "Workspace content preview placeholder."
    return ""


def _sanitize_exportable_command_echo(blocks: List[Dict[str, Any]], command: str) -> None:
    command_text = (command or "").strip()
    if not command_text:
        return
    for block in blocks:
        if block.get("exportable") is True and str(block.get("content", "")).strip() == command_text:
            block["content"] = "Workspace content preview placeholder."


def _with_internal_separation_blocks(command: str, content: str) -> List[Dict[str, Any]]:
    preview = build_workspace_preview(command, _safe_preview_content(command, content))
    blocks = list(preview["blocks"])
    _sanitize_exportable_command_echo(blocks, command)
    document = next((block for block in blocks if block.get("type") == "document"), {})
    document_id = str(document.get("id", ""))
    next_order = max(int(block.get("order", 0)) for block in blocks) + 1
    if _is_voice_command(command):
        blocks.append(
            _block(
                "voice_command",
                title="Voice Command",
                content=command,
                role="input_command",
                order=next_order,
                parent_id=document_id,
                metadata={"read_only": True, "excluded_from_export": True},
            )
        )
        next_order += 1
    blocks.append(
        _block(
            "ai_note",
            title="Separation Note",
            content="Internal preview note; command, voice command, and AI notes are excluded from clean export.",
            role="internal_note",
            order=next_order,
            parent_id=document_id,
            metadata={"read_only": True, "excluded_from_export": True},
        )
    )
    return sorted(blocks, key=lambda block: int(block.get("order", 0)))


def build_workspace_separation_preview(command: str, content: str = "") -> Dict[str, Any]:
    blocks = _with_internal_separation_blocks(command, content)
    command_blocks = [block for block in blocks if block.get("type") in _COMMAND_BLOCK_TYPES]
    content_blocks = [block for block in blocks if block.get("type") in _CONTENT_BLOCK_TYPES]
    exportable_blocks = [
        block
        for block in blocks
        if block.get("exportable") is True and block.get("type") not in _NON_EXPORTABLE_INTERNAL_TYPES
    ]
    non_exportable_blocks = [block for block in blocks if block.get("exportable") is False]
    final_output_blocks = [
        block
        for block in blocks
        if block.get("type") in _FINAL_OUTPUT_TYPES
        and block.get("exportable") is True
        and block.get("role") == "content"
    ]
    clean_export_preview = "\n\n".join(
        str(block.get("content", "")).strip()
        for block in final_output_blocks
        if str(block.get("content", "")).strip()
    )
    return {
        "separation_id": str(uuid.uuid4()),
        "command": command,
        "content": content,
        "original_blocks": blocks,
        "command_blocks": command_blocks,
        "content_blocks": content_blocks,
        "exportable_blocks": exportable_blocks,
        "non_exportable_blocks": non_exportable_blocks,
        "final_output_blocks": final_output_blocks,
        "clean_export_preview": clean_export_preview,
        "safety_note": "Read-only preview only; commands, voice commands, and AI notes are excluded from export output.",
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
        "file_created": False,
        "export_performed": False,
    }


def sample_workspace() -> Dict[str, Any]:
    return build_workspace_preview("CV hazirla", "Kisa profil, deneyim ve proje bilgileri icin taslak scaffold.")
