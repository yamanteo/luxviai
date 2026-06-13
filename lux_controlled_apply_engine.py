from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SUPPORTED_MODES = {"dry_run", "prepare", "apply", "verify", "rollback_preview", "rollback"}
DEFAULT_MODE = "dry_run"
SAFE_CHANGE_TYPES = {"replace_exact", "insert_before_exact", "insert_after_exact", "create_new_text_file"}
BLOCKED_CHANGE_TYPES = {"delete_file", "rename_file", "move_file", "chmod", "binary_patch", "directory_operation"}
TEXT_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".md", ".txt", ".json", ".yaml", ".yml", ".toml"}
EXCLUDED_DIRS = {".git", ".hg", ".svn", ".env", ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache", "node_modules", "dist", "build", "coverage", "htmlcov", "logs", "log"}
EXCLUDED_FILE_NAMES = {".env", ".env.local", ".env.production", ".env.development"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".sqlite", ".sqlite3", ".db", ".dump", ".cache", ".pem", ".key", ".crt", ".p12", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll"}
MAX_FILES_LIMIT = 20
MAX_CHANGED_LINES_LIMIT = 4000


def _normalize_mode(mode: Optional[str]) -> str:
    candidate = (mode or DEFAULT_MODE).strip()
    return candidate if candidate in SUPPORTED_MODES else DEFAULT_MODE


def _clamp_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(low, min(parsed, high))


def _jsonable(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _stable_id(prefix: str, *parts: Any) -> str:
    return prefix + hashlib.sha256("\n".join(_jsonable(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _resolve_root(repository_root: Optional[str]) -> Tuple[Optional[Path], List[str]]:
    raw = (repository_root or os.getcwd()).strip() or os.getcwd()
    try:
        root = Path(raw).expanduser().resolve()
    except OSError as exc:
        return None, [f"repository root could not be resolved: {type(exc).__name__}"]
    if not root.exists() or not root.is_dir():
        return None, [f"repository root is not an existing directory: {raw}"]
    return root, []


def _is_excluded(path: Path) -> bool:
    lowered = {part.lower() for part in path.parts}
    if lowered & EXCLUDED_DIRS:
        return True
    name = path.name.lower()
    return name in EXCLUDED_FILE_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES


def _safe_path(root: Path, raw_path: Any, *, must_exist: bool) -> Tuple[Optional[Path], Optional[str]]:
    raw = str(raw_path or "").strip().strip("\"'")
    if not raw or "\x00" in raw:
        return None, "empty or invalid path"
    candidate = Path(raw)
    if "*" in raw or "?" in raw:
        return None, f"wildcard target rejected: {raw}"
    if any(part == ".." for part in candidate.parts):
        return None, f"traversal rejected: {raw}"
    try:
        resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    except OSError:
        return None, f"path could not be resolved: {raw}"
    try:
        resolved.relative_to(root)
    except ValueError:
        return None, f"path outside repository rejected: {raw}"
    if resolved.is_symlink():
        return None, f"symlink target rejected: {raw}"
    if resolved.suffix.lower() in EXCLUDED_SUFFIXES:
        return None, f"binary or unsafe file rejected: {raw}"
    if _is_excluded(resolved):
        return None, f"excluded path rejected: {raw}"
    if resolved.suffix.lower() not in TEXT_SUFFIXES:
        return None, f"unsupported file type rejected: {raw}"
    if must_exist and (not resolved.exists() or not resolved.is_file()):
        return None, f"file not found: {raw}"
    if resolved.exists() and not resolved.is_file():
        return None, f"directory operation rejected: {raw}"
    return resolved, None


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _unique(items: Iterable[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def _canonical_steps(patch_steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    fields = [
        "target_file",
        "change_type",
        "expected_original_text",
        "expected_original_hash",
        "replacement_text",
        "target_region",
        "anchor",
        "purpose",
        "validation_after_change",
    ]
    return [{key: step.get(key) for key in fields if key in step} for step in patch_steps]


def _approval_digest(patch_id: str, root: Path, approved_files: List[str], patch_steps: List[Dict[str, Any]], expected_hashes: Dict[str, str]) -> str:
    payload = {
        "patch_id": patch_id,
        "repository_root": str(root),
        "approved_files": sorted(approved_files),
        "patch_steps": _canonical_steps(patch_steps),
        "expected_file_hashes": {key: expected_hashes[key] for key in sorted(expected_hashes)},
    }
    return "lux-approve-" + hashlib.sha256(_jsonable(payload).encode("utf-8")).hexdigest()


def _base_result(
    *,
    mode: str,
    patch_id: str,
    root: Optional[Path],
    approved_files: List[str],
    patch_steps: List[Dict[str, Any]],
    expected_hashes: Dict[str, str],
    validation_plan: List[Any],
) -> Dict[str, Any]:
    root_text = str(root) if root else ""
    digest = _approval_digest(patch_id, root, approved_files, patch_steps, expected_hashes) if root and patch_id else ""
    return {
        "request_id": _stable_id("luxapply-", mode, patch_id, root_text, approved_files, patch_steps, expected_hashes),
        "mode": mode,
        "patch_id": patch_id,
        "repository_root": root_text,
        "approval_digest": digest,
        "approval_phrase": f"APPROVE {patch_id} {digest}" if digest else "",
        "approval_valid": False,
        "preconditions_passed": False,
        "transaction_state": "dry_run" if mode in {"dry_run", "verify"} else "prepared" if mode == "prepare" else "blocked",
        "approved_files": approved_files,
        "files_planned": [],
        "files_changed": [],
        "blocked_items": [],
        "precondition_failures": [],
        "file_hashes_before": {},
        "file_hashes_after": {},
        "rollback_id": "",
        "rollback_available": False,
        "rollback_manifest": {},
        "validation_plan": validation_plan,
        "validation_execution_blocked": True,
        "safe_next_step": "Review blocked items or submit the exact approval digest for apply.",
        "approval_required": True,
        "scope_expansion_blocked": True,
        "destructive_action_blocked": True,
        "external_api_used": False,
        "local_first": True,
        "recommended_handoff": "local",
    }


def _normalize_inputs(
    repository_root: Optional[str],
    patch_id: Optional[str],
    patch_steps: Optional[List[Dict[str, Any]]],
    approved_files: Optional[List[str]],
    forbidden_files: Optional[List[str]],
    expected_file_hashes: Optional[Dict[str, str]],
    mode: Optional[str],
    validation_plan: Optional[List[Any]],
) -> Tuple[str, str, List[Dict[str, Any]], List[str], List[str], Dict[str, str], List[Any], Optional[Path], List[str]]:
    normalized_mode = _normalize_mode(mode)
    normalized_patch_id = str(patch_id or "").strip()
    steps = [dict(step) for step in (patch_steps or []) if isinstance(step, dict)]
    approved = sorted(_unique(str(item).replace("\\", "/").strip() for item in (approved_files or []) if item))
    forbidden = sorted(_unique(str(item).replace("\\", "/").strip() for item in (forbidden_files or []) if item))
    hashes = {str(key).replace("\\", "/"): str(value) for key, value in (expected_file_hashes or {}).items()}
    validations = list(validation_plan or [])
    root, root_errors = _resolve_root(repository_root)
    return normalized_mode, normalized_patch_id, steps, approved, forbidden, hashes, validations, root, root_errors


def _validate_plan(
    root: Path,
    patch_id: str,
    patch_steps: List[Dict[str, Any]],
    approved_files: List[str],
    forbidden_files: List[str],
    expected_hashes: Dict[str, str],
    max_files: int,
    max_total_changed_lines: int,
    *,
    require_clean_tree: bool,
    repository_state_clean: Optional[bool],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str], Dict[str, str]]:
    blocked: List[Dict[str, Any]] = []
    failures: List[str] = []
    normalized_steps: List[Dict[str, Any]] = []
    before_hashes: Dict[str, str] = {}
    if not patch_id:
        blocked.append({"target_file": "", "reason": "patch_id is required", "risk": "blocked"})
    if not patch_steps:
        blocked.append({"target_file": "", "reason": "patch_steps are required", "risk": "blocked"})
    if require_clean_tree and repository_state_clean is not True:
        failures.append("clean tree required but only caller-provided repository_state_clean can verify it")
    if len(approved_files) > max_files:
        blocked.append({"target_file": "", "reason": f"approved file count exceeds max_files {max_files}", "risk": "blocked"})
    if len({item.lower() for item in approved_files}) != len(approved_files):
        blocked.append({"target_file": "", "reason": "case-insensitive approved file ambiguity rejected", "risk": "blocked"})
    approved_set = set(approved_files)
    forbidden_set = set(forbidden_files)
    seen_targets: set[str] = set()
    changed_lines = 0
    for raw_forbidden in forbidden_files:
        safe, reason = _safe_path(root, raw_forbidden, must_exist=False)
        if safe:
            forbidden_set.add(_relative(root, safe))
        else:
            forbidden_set.add(str(raw_forbidden).replace("\\", "/"))
    for step in patch_steps:
        raw_target = step.get("target_file")
        change_type = str(step.get("change_type") or "").strip()
        must_exist = change_type != "create_new_text_file"
        safe, reason = _safe_path(root, raw_target, must_exist=must_exist)
        rel = _relative(root, safe) if safe else str(raw_target or "")
        if reason:
            blocked.append({"target_file": rel, "reason": reason, "risk": "blocked"})
            continue
        assert safe is not None
        if change_type in BLOCKED_CHANGE_TYPES or change_type not in SAFE_CHANGE_TYPES:
            blocked.append({"target_file": rel, "reason": f"unsupported or destructive change_type rejected: {change_type}", "risk": "blocked"})
            continue
        if rel in seen_targets:
            blocked.append({"target_file": rel, "reason": "duplicate/conflicting target rejected", "risk": "blocked"})
            continue
        seen_targets.add(rel)
        if rel not in approved_set:
            blocked.append({"target_file": rel, "reason": "target file not in approved_files allowlist", "risk": "blocked"})
        if rel in forbidden_set:
            blocked.append({"target_file": rel, "reason": "target file is forbidden", "risk": "blocked"})
        replacement = str(step.get("replacement_text") or "")
        expected_text = step.get("expected_original_text")
        anchor = step.get("anchor") or expected_text
        changed_lines += max(1, replacement.count("\n") + 1)
        if changed_lines > max_total_changed_lines:
            blocked.append({"target_file": rel, "reason": f"changed-line budget exceeds max_total_changed_lines {max_total_changed_lines}", "risk": "blocked"})
        if change_type == "create_new_text_file":
            if safe.exists():
                blocked.append({"target_file": rel, "reason": "create_new_text_file target already exists", "risk": "blocked"})
            before_hashes[rel] = ""
        else:
            data = safe.read_bytes()
            before_hashes[rel] = _sha256_bytes(data)
            expected_file_hash = expected_hashes.get(rel)
            if expected_file_hash and expected_file_hash != before_hashes[rel]:
                failures.append(f"precondition SHA mismatch for {rel}")
            if step.get("expected_original_hash"):
                source_hash = _sha256_bytes(str(expected_text or "").encode("utf-8"))
                if source_hash != step.get("expected_original_hash"):
                    failures.append(f"expected_original_hash mismatch for {rel}")
            text = safe.read_text(encoding="utf-8", errors="replace")
            if change_type == "replace_exact":
                needle = str(expected_text or "")
                count = text.count(needle)
                if not needle:
                    failures.append(f"expected_original_text required for {rel}")
                elif count != 1:
                    failures.append(f"expected_original_text must occur exactly once for {rel}; found {count}")
            elif change_type in {"insert_before_exact", "insert_after_exact"}:
                needle = str(anchor or "")
                count = text.count(needle)
                if not needle:
                    failures.append(f"anchor required for {rel}")
                elif count != 1:
                    failures.append(f"anchor must occur exactly once for {rel}; found {count}")
        normalized = dict(step)
        normalized["target_file"] = rel
        normalized_steps.append(normalized)
    if len(seen_targets) > max_files:
        blocked.append({"target_file": "", "reason": f"patch target count exceeds max_files {max_files}", "risk": "blocked"})
    return normalized_steps, blocked, failures, before_hashes


def _apply_step_to_text(original: str, step: Dict[str, Any]) -> str:
    change_type = step["change_type"]
    replacement = str(step.get("replacement_text") or "")
    if change_type == "replace_exact":
        return original.replace(str(step.get("expected_original_text") or ""), replacement, 1)
    anchor = str(step.get("anchor") or step.get("expected_original_text") or "")
    if change_type == "insert_before_exact":
        return original.replace(anchor, replacement + anchor, 1)
    if change_type == "insert_after_exact":
        return original.replace(anchor, anchor + replacement, 1)
    if change_type == "create_new_text_file":
        return replacement
    raise ValueError(f"unsupported change_type: {change_type}")


def _build_new_contents(root: Path, steps: List[Dict[str, Any]]) -> Dict[str, bytes]:
    contents: Dict[str, bytes] = {}
    for step in steps:
        rel = step["target_file"]
        path = root / rel
        original = "" if step["change_type"] == "create_new_text_file" else path.read_text(encoding="utf-8", errors="replace")
        contents[rel] = _apply_step_to_text(original, step).encode("utf-8")
    return contents


def _create_rollback(root: Path, patch_id: str, approved_files: List[str], before_hashes: Dict[str, str], steps: List[Dict[str, Any]]) -> Tuple[str, Path, Dict[str, Any]]:
    rollback_id = _stable_id("rollback-", patch_id, approved_files, before_hashes, datetime.now(timezone.utc).isoformat())
    rollback_dir = root / ".luxcode_runtime" / "rollback" / rollback_id
    files_dir = rollback_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "rollback_id": rollback_id,
        "patch_id": patch_id,
        "approved_files": approved_files,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "original_hashes": before_hashes,
        "post_apply_hashes": {},
        "files": {},
        "transaction_status": "snapshot_created",
        "patch_steps": _canonical_steps(steps),
    }
    for rel, digest in before_hashes.items():
        source = root / rel
        snapshot_name = hashlib.sha256(rel.encode("utf-8")).hexdigest() + ".bin"
        snapshot = files_dir / snapshot_name
        if source.exists():
            snapshot.write_bytes(source.read_bytes())
            existed = True
        else:
            snapshot.write_bytes(b"")
            existed = False
        manifest["files"][rel] = {"snapshot": f"files/{snapshot_name}", "sha256": digest, "existed": existed}
    (rollback_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return rollback_id, rollback_dir, manifest


def _write_manifest(rollback_dir: Path, manifest: Dict[str, Any]) -> None:
    (rollback_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _restore_from_manifest(root: Path, rollback_dir: Path, manifest: Dict[str, Any], *, verify_post_hash: bool) -> Tuple[bool, List[str]]:
    failures: List[str] = []
    for rel, meta in manifest.get("files", {}).items():
        target = root / rel
        if verify_post_hash:
            expected_post = manifest.get("post_apply_hashes", {}).get(rel)
            if expected_post and target.exists() and _sha256_file(target) != expected_post:
                failures.append(f"current file changed after apply: {rel}")
                continue
        snapshot = rollback_dir / meta["snapshot"]
        if meta.get("existed"):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(snapshot.read_bytes())
        elif target.exists():
            failures.append(f"rollback would delete newly created file and is blocked: {rel}")
    return not failures, failures


def prepare_controlled_apply(
    repository_root: Optional[str] = None,
    patch_id: Optional[str] = None,
    patch_steps: Optional[List[Dict[str, Any]]] = None,
    approved_files: Optional[List[str]] = None,
    forbidden_files: Optional[List[str]] = None,
    approval_token: Optional[str] = None,
    expected_file_hashes: Optional[Dict[str, str]] = None,
    mode: Optional[str] = None,
    max_files: Any = 5,
    max_total_changed_lines: Any = 400,
    require_clean_tree: bool = False,
    validation_plan: Optional[List[Any]] = None,
    rollback_id: Optional[str] = None,
    repository_state_clean: Optional[bool] = None,
) -> Dict[str, Any]:
    normalized_mode, patch_id_text, steps, approved, forbidden, hashes, validations, root, root_errors = _normalize_inputs(
        repository_root, patch_id, patch_steps, approved_files, forbidden_files, expected_file_hashes, mode, validation_plan
    )
    if normalized_mode == "apply":
        normalized_mode = "prepare"
    result = _base_result(mode=normalized_mode, patch_id=patch_id_text, root=root, approved_files=approved, patch_steps=steps, expected_hashes=hashes, validation_plan=validations)
    if root is None:
        result["blocked_items"].extend({"target_file": "", "reason": err, "risk": "blocked"} for err in root_errors)
        result["transaction_state"] = "blocked"
        return result
    normalized_steps, blocked, failures, before_hashes = _validate_plan(
        root,
        patch_id_text,
        steps,
        approved,
        forbidden,
        hashes,
        _clamp_int(max_files, 5, 1, MAX_FILES_LIMIT),
        _clamp_int(max_total_changed_lines, 400, 1, MAX_CHANGED_LINES_LIMIT),
        require_clean_tree=require_clean_tree,
        repository_state_clean=repository_state_clean,
    )
    result["files_planned"] = [step["target_file"] for step in normalized_steps]
    result["blocked_items"].extend(blocked)
    result["precondition_failures"].extend(failures)
    result["file_hashes_before"] = before_hashes
    result["approval_digest"] = _approval_digest(patch_id_text, root, approved, normalized_steps, hashes)
    result["approval_phrase"] = f"APPROVE {patch_id_text} {result['approval_digest']}"
    result["safe_next_step"] = "Submit this exact approval_digest as approval_token only after reviewing the exact patch and file allowlist."
    if blocked or failures:
        result["transaction_state"] = "blocked"
        result["recommended_handoff"] = "human"
    return result


def execute_controlled_apply(
    repository_root: Optional[str] = None,
    patch_id: Optional[str] = None,
    patch_steps: Optional[List[Dict[str, Any]]] = None,
    approved_files: Optional[List[str]] = None,
    forbidden_files: Optional[List[str]] = None,
    approval_token: Optional[str] = None,
    expected_file_hashes: Optional[Dict[str, str]] = None,
    mode: Optional[str] = None,
    max_files: Any = 5,
    max_total_changed_lines: Any = 400,
    require_clean_tree: bool = False,
    validation_plan: Optional[List[Any]] = None,
    rollback_id: Optional[str] = None,
    repository_state_clean: Optional[bool] = None,
) -> Dict[str, Any]:
    normalized_mode = _normalize_mode(mode)
    if normalized_mode in {"dry_run", "prepare", "verify"}:
        return prepare_controlled_apply(repository_root, patch_id, patch_steps, approved_files, forbidden_files, approval_token, expected_file_hashes, normalized_mode, max_files, max_total_changed_lines, require_clean_tree, validation_plan, rollback_id, repository_state_clean)
    if normalized_mode != "apply":
        return prepare_controlled_apply(repository_root, patch_id, patch_steps, approved_files, forbidden_files, approval_token, expected_file_hashes, normalized_mode, max_files, max_total_changed_lines, require_clean_tree, validation_plan, rollback_id, repository_state_clean)
    prepared = prepare_controlled_apply(repository_root, patch_id, patch_steps, approved_files, forbidden_files, approval_token, expected_file_hashes, "prepare", max_files, max_total_changed_lines, require_clean_tree, validation_plan, rollback_id, repository_state_clean)
    prepared["mode"] = "apply"
    prepared["transaction_state"] = "blocked"
    if prepared["blocked_items"] or prepared["precondition_failures"]:
        return prepared
    expected_digest = prepared["approval_digest"]
    if not approval_token:
        prepared["blocked_items"].append({"target_file": "", "reason": "missing approval token", "risk": "blocked"})
        return prepared
    if approval_token != expected_digest:
        prepared["blocked_items"].append({"target_file": "", "reason": "wrong approval token or altered patch authorization", "risk": "blocked"})
        return prepared
    prepared["approval_valid"] = True
    prepared["preconditions_passed"] = True
    root = Path(prepared["repository_root"])
    steps = [dict(step, target_file=step["target_file"].replace("\\", "/")) for step in _canonical_steps(patch_steps or [])]
    # Reuse normalized target paths from preparation to avoid caller path spelling drift.
    normalized_steps, _, _, before_hashes = _validate_plan(root, prepared["patch_id"], patch_steps or [], prepared["approved_files"], forbidden_files or [], expected_file_hashes or {}, max_files, max_total_changed_lines, require_clean_tree=require_clean_tree, repository_state_clean=repository_state_clean)
    new_contents = _build_new_contents(root, normalized_steps)
    try:
        rollback_id_text, rollback_dir, manifest = _create_rollback(root, prepared["patch_id"], prepared["approved_files"], before_hashes, normalized_steps)
    except OSError as exc:
        prepared["transaction_state"] = "blocked"
        prepared["blocked_items"].append({"target_file": "", "reason": f"rollback snapshot creation failed: {type(exc).__name__}", "risk": "blocked"})
        return prepared
    written: List[str] = []
    try:
        for rel, data in new_contents.items():
            if any(step.get("simulate_write_failure") for step in (patch_steps or []) if step.get("target_file") == rel):
                raise OSError("simulated write failure")
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, target)
            finally:
                temp_path = Path(temp_name)
                if temp_path.exists():
                    temp_path.unlink()
            written.append(rel)
        manifest["post_apply_hashes"] = {rel: _sha256_file(root / rel) for rel in new_contents}
        manifest["transaction_status"] = "applied"
        _write_manifest(rollback_dir, manifest)
        prepared["transaction_state"] = "applied"
        prepared["files_changed"] = written
        prepared["file_hashes_after"] = manifest["post_apply_hashes"]
        prepared["rollback_id"] = rollback_id_text
        prepared["rollback_available"] = True
        prepared["rollback_manifest"] = manifest
        prepared["safe_next_step"] = "Run the recommended validation externally; the engine does not execute validation commands."
        return prepared
    except Exception as exc:
        ok, restore_failures = _restore_from_manifest(root, rollback_dir, manifest, verify_post_hash=False)
        manifest["transaction_status"] = "transaction_failed_restored" if ok else "transaction_failed_restore_failed"
        manifest["failure"] = f"{type(exc).__name__}: {exc}"
        manifest["restore_failures"] = restore_failures
        _write_manifest(rollback_dir, manifest)
        prepared["transaction_state"] = "transaction_failed"
        prepared["rollback_id"] = rollback_id_text
        prepared["rollback_available"] = True
        prepared["rollback_manifest"] = manifest
        prepared["blocked_items"].append({"target_file": "", "reason": f"transaction failed and rollback attempted: {type(exc).__name__}", "risk": "blocked"})
        prepared["precondition_failures"].extend(restore_failures)
        return prepared


def rollback_controlled_apply(
    repository_root: Optional[str] = None,
    patch_id: Optional[str] = None,
    patch_steps: Optional[List[Dict[str, Any]]] = None,
    approved_files: Optional[List[str]] = None,
    forbidden_files: Optional[List[str]] = None,
    approval_token: Optional[str] = None,
    expected_file_hashes: Optional[Dict[str, str]] = None,
    mode: Optional[str] = None,
    max_files: Any = 5,
    max_total_changed_lines: Any = 400,
    require_clean_tree: bool = False,
    validation_plan: Optional[List[Any]] = None,
    rollback_id: Optional[str] = None,
    repository_state_clean: Optional[bool] = None,
) -> Dict[str, Any]:
    normalized_mode, patch_id_text, steps, approved, forbidden, hashes, validations, root, root_errors = _normalize_inputs(
        repository_root, patch_id, patch_steps, approved_files, forbidden_files, expected_file_hashes, mode, validation_plan
    )
    result = _base_result(mode=normalized_mode, patch_id=patch_id_text, root=root, approved_files=approved, patch_steps=steps, expected_hashes=hashes, validation_plan=validations)
    result["transaction_state"] = "blocked" if normalized_mode == "rollback" else "dry_run"
    if root is None:
        result["blocked_items"].extend({"target_file": "", "reason": err, "risk": "blocked"} for err in root_errors)
        return result
    if not rollback_id:
        result["blocked_items"].append({"target_file": "", "reason": "rollback_id is required", "risk": "blocked"})
        return result
    rollback_dir = root / ".luxcode_runtime" / "rollback" / str(rollback_id)
    manifest_path = rollback_dir / "manifest.json"
    if not manifest_path.exists():
        result["blocked_items"].append({"target_file": "", "reason": "rollback manifest not found", "risk": "blocked"})
        return result
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result["rollback_id"] = str(rollback_id)
    result["rollback_available"] = True
    result["rollback_manifest"] = manifest
    result["approval_digest"] = _approval_digest(manifest.get("patch_id", patch_id_text), root, manifest.get("approved_files", approved), manifest.get("patch_steps", steps), manifest.get("original_hashes", hashes))
    if normalized_mode == "rollback_preview":
        result["transaction_state"] = "dry_run"
        result["safe_next_step"] = "Submit rollback mode with matching approval token after checking the manifest."
        return result
    if approval_token not in {result["approval_digest"], manifest.get("approval_digest")}:
        result["blocked_items"].append({"target_file": "", "reason": "missing or wrong rollback approval token", "risk": "blocked"})
        return result
    ok, failures = _restore_from_manifest(root, rollback_dir, manifest, verify_post_hash=True)
    if not ok:
        result["precondition_failures"].extend(failures)
        result["recommended_handoff"] = "human"
        return result
    manifest["transaction_status"] = "rolled_back"
    manifest["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
    _write_manifest(rollback_dir, manifest)
    result["approval_valid"] = True
    result["preconditions_passed"] = True
    result["transaction_state"] = "rolled_back"
    result["files_changed"] = list(manifest.get("files", {}).keys())
    result["file_hashes_after"] = {rel: _sha256_file(root / rel) for rel in manifest.get("files", {}) if (root / rel).exists()}
    result["rollback_manifest"] = manifest
    result["safe_next_step"] = "Run external validation after rollback."
    return result


def get_controlled_apply_schema() -> Dict[str, Any]:
    return {
        "name": "Approval-Gated Controlled Apply Engine",
        "status": "schema_ready",
        "supported_modes": sorted(SUPPORTED_MODES),
        "default_mode": DEFAULT_MODE,
        "safe_change_types": sorted(SAFE_CHANGE_TYPES),
        "blocked_change_types": sorted(BLOCKED_CHANGE_TYPES),
        "input_fields": ["repository_root", "patch_id", "patch_steps", "approved_files", "forbidden_files", "approval_token", "expected_file_hashes", "mode", "max_files", "max_total_changed_lines", "require_clean_tree", "validation_plan", "rollback_id"],
        "approval_required": True,
        "validation_execution_blocked": True,
        "scope_expansion_blocked": True,
        "destructive_action_blocked": True,
        "external_api_used": False,
        "local_first": True,
    }


def get_controlled_apply_status() -> Dict[str, Any]:
    return {
        "name": "Approval-Gated Controlled Apply Engine",
        "status": "controlled_apply_ready",
        "default_mode": DEFAULT_MODE,
        "real_apply_requires_approval_digest": True,
        "shell_execution_enabled": False,
        "external_api_used": False,
        "local_first": True,
        "validation_execution_blocked": True,
        "rollback_storage_warning": ".luxcode_runtime/rollback must be excluded from commits before production activation.",
        "available_endpoints": ["/lux-controlled-apply/schema", "/lux-controlled-apply/prepare", "/lux-controlled-apply/execute", "/lux-controlled-apply/rollback", "/debug/lux-controlled-apply-status"],
        "approval_required": True,
        "scope_expansion_blocked": True,
        "destructive_action_blocked": True,
    }
