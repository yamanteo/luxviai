from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


SERVICE_VERSION = "luxcode_working_copy_service_v1"
RUNTIME_FOLDER = ".luxcode_runtime"
WORKING_COPIES_FOLDER = "working_copies"
MANIFEST_NAME = "working_copy_manifest.json"
MAX_FILES = 500
MAX_TOTAL_BYTES = 50_000_000
MAX_SINGLE_FILE_BYTES = 2_000_000

SUPPORTED_TEXT_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css",
    ".md", ".txt", ".json", ".yaml", ".yml", ".toml",
}
EXCLUDED_PARTS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", "dist", "build", ".luxcode_runtime",
}
EXCLUDED_NAMES = {
    ".env", ".env.local", ".env.production", ".env.development",
}
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{3,100}$")


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _safe_id(value: str, prefix: str) -> str:
    candidate = str(value or "").strip()
    if candidate and SAFE_ID.fullmatch(candidate):
        return candidate
    digest = hashlib.sha256(
        f"{prefix}:{candidate}:{_now()}".encode("utf-8")
    ).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _resolve_root(repository_root: str | Path) -> Path:
    root = Path(repository_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("repository_root must be an existing directory")
    return root


def _is_excluded(path: Path) -> bool:
    if path.name.lower() in EXCLUDED_NAMES:
        return True
    lowered_parts = {part.lower() for part in path.parts}
    return bool(lowered_parts & EXCLUDED_PARTS)


def _safe_source(root: Path, raw: str) -> tuple[Path | None, str | None]:
    value = str(raw or "").replace("\\", "/").strip()
    if not value or value.startswith("/") or ".." in Path(value).parts:
        return None, "invalid_relative_path"
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, "path_escape"
    if candidate.is_symlink():
        return None, "symlink_rejected"
    if not candidate.is_file():
        return None, "file_missing"
    if _is_excluded(candidate):
        return None, "excluded_path"
    if candidate.suffix.lower() not in SUPPORTED_TEXT_SUFFIXES:
        return None, "unsupported_file_type"
    if candidate.stat().st_size > MAX_SINGLE_FILE_BYTES:
        return None, "file_too_large"
    return candidate, None


def _discover_files(root: Path) -> List[str]:
    items: List[str] = []
    total_bytes = 0
    for path in sorted(root.rglob("*")):
        if len(items) >= MAX_FILES:
            break
        if not path.is_file() or path.is_symlink() or _is_excluded(path):
            continue
        if path.suffix.lower() not in SUPPORTED_TEXT_SUFFIXES:
            continue
        size = path.stat().st_size
        if size > MAX_SINGLE_FILE_BYTES:
            continue
        if total_bytes + size > MAX_TOTAL_BYTES:
            break
        items.append(path.relative_to(root).as_posix())
        total_bytes += size
    return items


def get_working_copy_service_status() -> Dict[str, Any]:
    return {
        "service": "working_copy",
        "version": SERVICE_VERSION,
        "status": "ready",
        "service_ready": True,
        "real_copy_supported": True,
        "git_operations_used": False,
        "external_api_used": False,
        "source_repository_write_allowed": False,
        "symlinks_allowed": False,
        "secret_files_allowed": False,
        "maximum_files": MAX_FILES,
        "maximum_total_bytes": MAX_TOTAL_BYTES,
    }


def prepare_working_copy(
    repository_root: str | Path,
    *,
    workspace_id: str = "",
    selected_files: Sequence[str] | None = None,
    discover_when_empty: bool = False,
    reset_existing: bool = False,
) -> Dict[str, Any]:
    root = _resolve_root(repository_root)
    safe_workspace_id = _safe_id(workspace_id, "working-copy")
    destination = (
        root
        / RUNTIME_FOLDER
        / WORKING_COPIES_FOLDER
        / safe_workspace_id
    ).resolve()
    runtime_root = (root / RUNTIME_FOLDER).resolve()
    destination.relative_to(runtime_root)

    requested = [
        str(item).replace("\\", "/").strip()
        for item in (selected_files or [])
        if str(item).strip()
    ]
    if not requested and discover_when_empty:
        requested = _discover_files(root)
    if not requested:
        return {
            "ok": False,
            "status": "blocked",
            "reason": "selected_files_required",
            "workspace_id": safe_workspace_id,
            "working_copy_root": str(destination),
            "source_repository_changed": False,
            "external_api_used": False,
        }

    if destination.exists():
        if not reset_existing:
            return {
                "ok": False,
                "status": "blocked",
                "reason": "working_copy_already_exists",
                "workspace_id": safe_workspace_id,
                "working_copy_root": str(destination),
                "source_repository_changed": False,
                "external_api_used": False,
            }
        if destination.is_symlink():
            return {
                "ok": False,
                "status": "blocked",
                "reason": "working_copy_symlink_rejected",
                "workspace_id": safe_workspace_id,
                "working_copy_root": str(destination),
                "source_repository_changed": False,
                "external_api_used": False,
            }
        shutil.rmtree(destination)

    safe_files: List[tuple[str, Path]] = []
    blocked: List[Dict[str, str]] = []
    total_bytes = 0
    for raw in dict.fromkeys(requested):
        source, reason = _safe_source(root, raw)
        if reason or source is None:
            blocked.append({"file": raw, "reason": reason or "invalid"})
            continue
        size = source.stat().st_size
        if len(safe_files) >= MAX_FILES:
            blocked.append({"file": raw, "reason": "maximum_files_exceeded"})
            continue
        if total_bytes + size > MAX_TOTAL_BYTES:
            blocked.append({"file": raw, "reason": "maximum_total_bytes_exceeded"})
            continue
        rel = source.relative_to(root).as_posix()
        safe_files.append((rel, source))
        total_bytes += size

    if not safe_files:
        return {
            "ok": False,
            "status": "blocked",
            "reason": "no_safe_files",
            "blocked_files": blocked,
            "workspace_id": safe_workspace_id,
            "working_copy_root": str(destination),
            "source_repository_changed": False,
            "external_api_used": False,
        }

    destination.mkdir(parents=True, exist_ok=False)
    manifest_files: Dict[str, Any] = {}
    try:
        for rel, source in safe_files:
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            manifest_files[rel] = {
                "source_sha256": _sha256(source),
                "working_copy_sha256": _sha256(target),
                "size_bytes": target.stat().st_size,
            }

        manifest = {
            "service_version": SERVICE_VERSION,
            "workspace_id": safe_workspace_id,
            "repository_root": str(root),
            "working_copy_root": str(destination),
            "created_at": _now(),
            "files": manifest_files,
            "blocked_files": blocked,
            "file_count": len(manifest_files),
            "total_bytes": total_bytes,
            "source_repository_changed": False,
            "git_operations_used": False,
            "external_api_used": False,
        }
        _atomic_json(destination / MANIFEST_NAME, manifest)
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise

    return {
        "ok": True,
        "status": "ready",
        "workspace_id": safe_workspace_id,
        "working_copy_root": str(destination),
        "manifest_path": str(destination / MANIFEST_NAME),
        "files_copied": sorted(manifest_files),
        "file_count": len(manifest_files),
        "blocked_files": blocked,
        "source_repository_changed": False,
        "git_operations_used": False,
        "external_api_used": False,
    }
