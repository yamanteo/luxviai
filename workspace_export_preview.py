"""Read-only LuxWorkspace export-clean preview package scaffold."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Mapping

from workspace_scaffold import build_workspace_separation_preview


_EXCLUDED_EXPORT_TYPES = {"command", "voice_command", "ai_note"}
_INCLUDED_EXPORT_TYPES = {"heading", "paragraph", "draft", "final", "citation", "source", "table_placeholder"}
_PREVIEW_EXPORT_TYPES = {"copy", "pdf", "word", "presentation", "send"}


def _sample_blocks() -> List[Dict[str, Any]]:
    preview = build_workspace_separation_preview(
        "sesli komut: giris bolumunu kisalt",
        "Giris bolumu icin temiz icerik onizlemesi.",
    )
    return list(preview.get("original_blocks", []))


def _block_with_reason(block: Mapping[str, Any], reason: str) -> Dict[str, Any]:
    item = dict(block)
    item["export_clean_reason"] = reason
    return item


def build_workspace_export_preview(
    blocks: List[Mapping[str, Any]] | None = None,
    export_type: str = "copy",
) -> Dict[str, Any]:
    requested_export_type = (export_type or "copy").strip().lower()
    normalized_export_type = requested_export_type if requested_export_type in _PREVIEW_EXPORT_TYPES else "copy"
    source_blocks = [dict(block) for block in (blocks or _sample_blocks())]
    included_blocks: List[Dict[str, Any]] = []
    excluded_blocks: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for block in source_blocks:
        block_type = str(block.get("type", ""))
        content = str(block.get("content", "")).strip()
        if block_type in _EXCLUDED_EXPORT_TYPES:
            excluded_blocks.append(_block_with_reason(block, f"{block_type} is internal command/control data."))
            continue
        if block_type in _INCLUDED_EXPORT_TYPES and content:
            included_blocks.append(_block_with_reason(block, f"{block_type} is clean content allowed in preview export."))
            continue
        excluded_blocks.append(_block_with_reason(block, f"{block_type or 'unknown'} is structural, empty, or not export-clean."))

    clean_text_preview = "\n\n".join(
        str(block.get("content", "")).strip()
        for block in included_blocks
        if str(block.get("content", "")).strip()
    )
    if not included_blocks:
        warnings.append("No exportable clean content blocks were found.")
    if requested_export_type not in _PREVIEW_EXPORT_TYPES:
        warnings.append(f"Unknown export_type '{requested_export_type}' was treated as copy preview.")
    if normalized_export_type in {"pdf", "word", "presentation", "send"}:
        warnings.append(f"{normalized_export_type} is preview-only; no file, presentation, copy, or send action is performed.")

    return {
        "export_preview_id": str(uuid.uuid4()),
        "export_type": normalized_export_type,
        "requested_export_type": requested_export_type,
        "read_only": True,
        "export_performed": False,
        "file_written": False,
        "write_performed": False,
        "send_performed": False,
        "copy_performed": False,
        "included_blocks": included_blocks,
        "excluded_blocks": excluded_blocks,
        "clean_text_preview": clean_text_preview,
        "export_package_preview": {
            "type": normalized_export_type,
            "status": "preview_only",
            "included_count": len(included_blocks),
            "excluded_count": len(excluded_blocks),
            "file_output_enabled": False,
            "send_enabled": False,
            "copy_enabled": False,
        },
        "warnings": warnings,
        "safety_note": "Export-clean preview only; command, voice command, and AI note blocks are excluded and no real export is performed.",
    }
