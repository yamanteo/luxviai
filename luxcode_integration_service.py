from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence

from lux_controlled_apply_engine import (
    execute_controlled_apply,
    prepare_controlled_apply,
    rollback_controlled_apply,
)


SERVICE_VERSION = "luxcode_integration_service_v1"
DEFAULT_FORBIDDEN = [
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".luxcode_runtime",
    "luxcode_tasks.db",
]
MAX_FILES = 20
MAX_SINGLE_FILE_BYTES = 2_000_000


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_relative_files(
    main_root: Path,
    source_root: Path,
    approved_files: Sequence[str],
) -> tuple[List[str], List[Dict[str, str]]]:
    safe: List[str] = []
    blocked: List[Dict[str, str]] = []
    for raw in dict.fromkeys(
        str(item).replace("\\", "/").strip()
        for item in approved_files
        if str(item).strip()
    ):
        if (
            not raw
            or raw.startswith("/")
            or ".." in Path(raw).parts
            or raw in DEFAULT_FORBIDDEN
            or raw.startswith(".luxcode_runtime/")
        ):
            blocked.append({"file": raw, "reason": "unsafe_path"})
            continue
        source = (source_root / raw).resolve()
        main = (main_root / raw).resolve()
        try:
            source.relative_to(source_root)
            main.relative_to(main_root)
        except ValueError:
            blocked.append({"file": raw, "reason": "path_escape"})
            continue
        if not source.is_file() or source.is_symlink():
            blocked.append({"file": raw, "reason": "source_file_missing"})
            continue
        if source.stat().st_size > MAX_SINGLE_FILE_BYTES:
            blocked.append({"file": raw, "reason": "source_file_too_large"})
            continue
        if main.exists() and (not main.is_file() or main.is_symlink()):
            blocked.append({"file": raw, "reason": "unsafe_main_target"})
            continue
        if len(safe) >= MAX_FILES:
            blocked.append({"file": raw, "reason": "maximum_files_exceeded"})
            continue
        safe.append(raw)
    return safe, blocked


def get_integration_service_status() -> Dict[str, Any]:
    return {
        "service": "integration",
        "version": SERVICE_VERSION,
        "status": "ready",
        "service_ready": True,
        "controlled_apply_connected": True,
        "rollback_connected": True,
        "approval_required": True,
        "automatic_apply_allowed": False,
        "delete_operations_allowed": False,
        "external_api_used": False,
        "git_operations_used": False,
    }


def prepare_integration(
    main_repository_root: str | Path,
    source_workspace_root: str | Path,
    *,
    patch_id: str,
    approved_files: Sequence[str],
    forbidden_files: Sequence[str] | None = None,
    validation_plan: Sequence[Any] | None = None,
) -> Dict[str, Any]:
    main_root = Path(main_repository_root).expanduser().resolve()
    source_root = Path(source_workspace_root).expanduser().resolve()
    if not main_root.is_dir():
        raise ValueError("main_repository_root must be an existing directory")
    if not source_root.is_dir():
        return {
            "ok": False,
            "status": "blocked",
            "reason": "source_workspace_missing",
            "automatic_apply_used": False,
            "external_api_used": False,
        }

    safe_files, blocked = _safe_relative_files(
        main_root,
        source_root,
        approved_files,
    )
    if not safe_files:
        return {
            "ok": False,
            "status": "blocked",
            "reason": "no_safe_approved_files",
            "blocked_files": blocked,
            "automatic_apply_used": False,
            "external_api_used": False,
        }

    steps: List[Dict[str, Any]] = []
    expected_hashes: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    unchanged: List[str] = []

    for rel in safe_files:
        source = source_root / rel
        source_text = source.read_text(encoding="utf-8", errors="strict")
        source_hashes[rel] = _sha256(source)
        main = main_root / rel
        if main.is_file():
            main_text = main.read_text(encoding="utf-8", errors="strict")
            main_hash = _sha256(main)
            expected_hashes[rel] = main_hash
            if main_hash == source_hashes[rel]:
                unchanged.append(rel)
                continue
            steps.append(
                {
                    "target_file": rel,
                    "change_type": "replace_exact",
                    "expected_original_text": main_text,
                    "expected_original_hash": hashlib.sha256(
                        main_text.encode("utf-8")
                    ).hexdigest(),
                    "replacement_text": source_text,
                    "purpose": "Integrate explicitly approved workspace file.",
                    "validation_after_change": list(validation_plan or []),
                }
            )
        else:
            expected_hashes[rel] = ""
            steps.append(
                {
                    "target_file": rel,
                    "change_type": "create_new_text_file",
                    "replacement_text": source_text,
                    "purpose": "Create explicitly approved new workspace file.",
                    "validation_after_change": list(validation_plan or []),
                }
            )

    if not steps:
        return {
            "ok": True,
            "status": "no_changes",
            "patch_id": patch_id,
            "approved_files": safe_files,
            "unchanged_files": unchanged,
            "blocked_files": blocked,
            "automatic_apply_used": False,
            "external_api_used": False,
        }

    prepared = prepare_controlled_apply(
        repository_root=str(main_root),
        patch_id=str(patch_id),
        patch_steps=steps,
        approved_files=[step["target_file"] for step in steps],
        forbidden_files=list(forbidden_files or DEFAULT_FORBIDDEN),
        expected_file_hashes=expected_hashes,
        mode="prepare",
        max_files=MAX_FILES,
        max_total_changed_lines=4000,
        require_clean_tree=False,
        validation_plan=list(validation_plan or []),
    )

    return {
        "ok": not bool(
            prepared.get("blocked_items")
            or prepared.get("precondition_failures")
        ),
        "status": prepared.get("transaction_state", "blocked"),
        "service_version": SERVICE_VERSION,
        "patch_id": patch_id,
        "main_repository_root": str(main_root),
        "source_workspace_root": str(source_root),
        "approved_files": [step["target_file"] for step in steps],
        "unchanged_files": unchanged,
        "blocked_files": blocked,
        "source_file_hashes": source_hashes,
        "patch_contract": {
            "repository_root": str(main_root),
            "source_workspace_root": str(source_root),
            "patch_id": patch_id,
            "patch_steps": steps,
            "approved_files": [step["target_file"] for step in steps],
            "forbidden_files": list(forbidden_files or DEFAULT_FORBIDDEN),
            "expected_file_hashes": expected_hashes,
            "source_file_hashes": source_hashes,
            "validation_plan": list(validation_plan or []),
            "approval_digest": prepared.get("approval_digest", ""),
            "approval_phrase": prepared.get("approval_phrase", ""),
        },
        "controlled_apply_preview": prepared,
        "approval_required": True,
        "automatic_apply_used": False,
        "external_api_used": False,
        "git_operations_used": False,
    }


def execute_integration(
    patch_contract: Dict[str, Any],
    *,
    approval_confirmed: bool,
    approval_token: str,
) -> Dict[str, Any]:
    if not approval_confirmed:
        return {
            "ok": False,
            "status": "blocked",
            "reason": "approval_required",
            "automatic_apply_used": False,
            "external_api_used": False,
        }
    if not isinstance(patch_contract, dict) or not patch_contract:
        return {
            "ok": False,
            "status": "blocked",
            "reason": "patch_contract_required",
            "automatic_apply_used": False,
            "external_api_used": False,
        }

    source_root = Path(
        str(patch_contract.get("source_workspace_root") or "")
    ).expanduser().resolve()
    source_hashes = patch_contract.get("source_file_hashes", {})
    if not source_root.is_dir() or not isinstance(source_hashes, dict):
        return {
            "ok": False,
            "status": "blocked",
            "reason": "source_workspace_precondition_failed",
            "automatic_apply_used": False,
            "external_api_used": False,
        }

    source_failures: List[str] = []
    for rel, expected in source_hashes.items():
        source = (source_root / str(rel)).resolve()
        try:
            source.relative_to(source_root)
        except ValueError:
            source_failures.append(f"source_path_escape:{rel}")
            continue
        if not source.is_file() or _sha256(source) != str(expected):
            source_failures.append(f"source_hash_mismatch:{rel}")

    if source_failures:
        return {
            "ok": False,
            "status": "blocked",
            "reason": "source_workspace_changed_after_prepare",
            "precondition_failures": source_failures,
            "automatic_apply_used": False,
            "external_api_used": False,
        }

    result = execute_controlled_apply(
        repository_root=patch_contract.get("repository_root"),
        patch_id=patch_contract.get("patch_id"),
        patch_steps=patch_contract.get("patch_steps") or [],
        approved_files=patch_contract.get("approved_files") or [],
        forbidden_files=patch_contract.get("forbidden_files")
        or DEFAULT_FORBIDDEN,
        approval_token=str(approval_token or ""),
        expected_file_hashes=patch_contract.get(
            "expected_file_hashes"
        )
        or {},
        mode="apply",
        max_files=MAX_FILES,
        max_total_changed_lines=4000,
        require_clean_tree=False,
        validation_plan=patch_contract.get("validation_plan") or [],
    )
    return {
        "ok": result.get("transaction_state") == "applied",
        "status": result.get("transaction_state", "blocked"),
        "service_version": SERVICE_VERSION,
        "controlled_apply_result": result,
        "files_changed": result.get("files_changed", []),
        "rollback_id": result.get("rollback_id", ""),
        "rollback_available": bool(result.get("rollback_available")),
        "approval_required": True,
        "automatic_apply_used": False,
        "external_api_used": False,
        "git_operations_used": False,
    }


def rollback_integration(
    *,
    repository_root: str | Path,
    patch_id: str,
    rollback_id: str,
    approval_token: str,
    preview_only: bool = True,
) -> Dict[str, Any]:
    result = rollback_controlled_apply(
        repository_root=str(Path(repository_root).expanduser().resolve()),
        patch_id=str(patch_id),
        rollback_id=str(rollback_id),
        approval_token=str(approval_token or ""),
        mode="rollback_preview" if preview_only else "rollback",
    )
    return {
        "ok": (
            result.get("transaction_state") == "dry_run"
            if preview_only
            else result.get("transaction_state") == "rolled_back"
        ),
        "status": result.get("transaction_state", "blocked"),
        "service_version": SERVICE_VERSION,
        "rollback_result": result,
        "preview_only": bool(preview_only),
        "approval_required": True,
        "automatic_apply_used": False,
        "external_api_used": False,
        "git_operations_used": False,
    }
