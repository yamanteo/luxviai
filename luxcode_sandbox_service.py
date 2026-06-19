from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


SERVICE_VERSION = "luxcode_sandbox_service_v1"
RUNTIME_FOLDER = ".luxcode_runtime"
SANDBOX_FOLDER = "sandboxes"
WORKING_COPY_MANIFEST = "working_copy_manifest.json"
SANDBOX_MANIFEST = "sandbox_manifest.json"
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{3,100}$")
MAX_FILES = 500
MAX_TOTAL_BYTES = 50_000_000


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


def _safe_id(value: str) -> str:
    candidate = str(value or "").strip()
    if candidate and SAFE_ID.fullmatch(candidate):
        return candidate
    digest = hashlib.sha256(
        f"sandbox:{candidate}:{_now()}".encode("utf-8")
    ).hexdigest()[:16]
    return f"sandbox-{digest}"


def get_sandbox_service_status() -> Dict[str, Any]:
    return {
        "service": "sandbox",
        "version": SERVICE_VERSION,
        "status": "ready",
        "service_ready": True,
        "filesystem_isolation_supported": True,
        "process_execution_supported": False,
        "network_access_supported": False,
        "external_api_used": False,
        "source_repository_write_allowed": False,
        "working_copy_write_allowed": False,
    }


def prepare_sandbox(
    repository_root: str | Path,
    working_copy_root: str | Path,
    *,
    sandbox_id: str = "",
    reset_existing: bool = False,
) -> Dict[str, Any]:
    repository = Path(repository_root).expanduser().resolve()
    working = Path(working_copy_root).expanduser().resolve()
    runtime_root = (repository / RUNTIME_FOLDER).resolve()

    if not repository.is_dir():
        raise ValueError("repository_root must be an existing directory")
    if not working.is_dir():
        return {
            "ok": False,
            "status": "blocked",
            "reason": "working_copy_missing",
            "external_api_used": False,
        }
    try:
        working.relative_to(runtime_root / "working_copies")
    except ValueError:
        return {
            "ok": False,
            "status": "blocked",
            "reason": "working_copy_outside_runtime",
            "external_api_used": False,
        }
    if working.is_symlink():
        return {
            "ok": False,
            "status": "blocked",
            "reason": "working_copy_symlink_rejected",
            "external_api_used": False,
        }

    manifest_path = working / WORKING_COPY_MANIFEST
    if not manifest_path.is_file():
        return {
            "ok": False,
            "status": "blocked",
            "reason": "working_copy_manifest_missing",
            "external_api_used": False,
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    if not isinstance(files, dict) or not files:
        return {
            "ok": False,
            "status": "blocked",
            "reason": "working_copy_manifest_empty",
            "external_api_used": False,
        }

    safe_sandbox_id = _safe_id(sandbox_id)
    destination = (
        runtime_root / SANDBOX_FOLDER / safe_sandbox_id
    ).resolve()
    destination.relative_to(runtime_root / SANDBOX_FOLDER)

    if destination.exists():
        if not reset_existing:
            return {
                "ok": False,
                "status": "blocked",
                "reason": "sandbox_already_exists",
                "sandbox_id": safe_sandbox_id,
                "sandbox_root": str(destination),
                "external_api_used": False,
            }
        if destination.is_symlink():
            return {
                "ok": False,
                "status": "blocked",
                "reason": "sandbox_symlink_rejected",
                "external_api_used": False,
            }
        shutil.rmtree(destination)

    destination.mkdir(parents=True, exist_ok=False)
    copied: Dict[str, Any] = {}
    total_bytes = 0
    try:
        for rel, meta in sorted(files.items()):
            if len(copied) >= MAX_FILES:
                raise ValueError("maximum_files_exceeded")
            source = (working / rel).resolve()
            try:
                source.relative_to(working)
            except ValueError:
                raise ValueError(f"path_escape:{rel}")
            if not source.is_file() or source.is_symlink():
                raise ValueError(f"working_copy_file_missing:{rel}")
            if _sha256(source) != str(meta.get("working_copy_sha256") or ""):
                raise ValueError(f"working_copy_hash_mismatch:{rel}")
            size = source.stat().st_size
            total_bytes += size
            if total_bytes > MAX_TOTAL_BYTES:
                raise ValueError("maximum_total_bytes_exceeded")
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied[rel] = {
                "source_sha256": _sha256(source),
                "sandbox_sha256": _sha256(target),
                "size_bytes": size,
            }

        sandbox_manifest = {
            "service_version": SERVICE_VERSION,
            "sandbox_id": safe_sandbox_id,
            "repository_root": str(repository),
            "working_copy_root": str(working),
            "sandbox_root": str(destination),
            "created_at": _now(),
            "files": copied,
            "file_count": len(copied),
            "total_bytes": total_bytes,
            "process_execution_supported": False,
            "network_access_supported": False,
            "source_repository_changed": False,
            "working_copy_changed": False,
            "external_api_used": False,
        }
        _atomic_json(destination / SANDBOX_MANIFEST, sandbox_manifest)
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise

    return {
        "ok": True,
        "status": "ready",
        "sandbox_id": safe_sandbox_id,
        "sandbox_root": str(destination),
        "manifest_path": str(destination / SANDBOX_MANIFEST),
        "files_copied": sorted(copied),
        "file_count": len(copied),
        "process_execution_supported": False,
        "network_access_supported": False,
        "source_repository_changed": False,
        "working_copy_changed": False,
        "external_api_used": False,
    }
