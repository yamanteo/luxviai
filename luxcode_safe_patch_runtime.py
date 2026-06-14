from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SUPPORTED_OPERATIONS = {"replace_text", "insert_before", "insert_after", "create_file"}
FORBIDDEN_OPERATIONS = {"delete_file", "rename_file", "binary_write", "chmod", "symlink", "external_path_write"}
SECRET_MARKERS = ("api_key", "token", "secret", "authorization", "credential", "password", "private_key", "environment_value")
APPLIED_PATCH_DIGESTS: set[str] = set()
SNAPSHOTS: Dict[str, Dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any, prefix: str = "patch") -> str:
    return f"{prefix}-{hashlib.sha256(_stable_json(value).encode('utf-8')).hexdigest()[:24]}"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _safe_failure(message: str, **extra: Any) -> Dict[str, Any]:
    return {"ok": False, "error": message, **extra, "external_api_used": False, "network_access_used": False, "local_first": True}


def _safe_success(**extra: Any) -> Dict[str, Any]:
    return {"ok": True, **extra, "external_api_used": False, "network_access_used": False, "local_first": True}


def _normalize_list(values: Any, limit: int = 80) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        items = [values]
    elif isinstance(values, (list, tuple, set)):
        items = list(values)
    else:
        items = [values]
    out: List[str] = []
    seen = set()
    for item in items:
        text = str(item or "").replace("\\", "/").strip()
        if text and text not in seen:
            out.append(text)
            seen.add(text)
        if len(out) >= limit:
            break
    return out


def _redact(text: str, limit: int = 1200) -> str:
    value = str(text or "").replace("\x00", "")
    if any(marker in value.lower() for marker in SECRET_MARKERS):
        return "[redacted-secret-like-output]"
    if len(value) > limit:
        return value[:limit] + "...[truncated]"
    return value


def _repo_root(repository_root: str) -> Optional[Path]:
    try:
        root = Path(repository_root).resolve()
    except OSError:
        return None
    return root if root.exists() and root.is_dir() else None


def _resolve(root: Path, rel: str) -> Optional[Path]:
    normalized = str(rel or "").replace("\\", "/").strip()
    if not normalized or normalized.startswith("/") or ".." in normalized.split("/"):
        return None
    if ".git" in normalized.split("/") or normalized == ".env" or normalized.endswith("/.env"):
        return None
    try:
        path = (root / normalized).resolve()
        path.relative_to(root)
    except (OSError, ValueError):
        return None
    return path


def _is_binary(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return True
    return b"\x00" in chunk


def _git_read(root: Path, args: List[str]) -> str:
    proc = subprocess.run(["git", *args], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _approval_token(patch_digest: str) -> str:
    return f"APPROVE:{patch_digest}"


def build_patch_contract(
    task_id: str = "",
    repository_root: str = "",
    patch_title: str = "",
    patch_summary: str = "",
    target_files: Optional[List[str]] = None,
    operations: Optional[List[Dict[str, Any]]] = None,
    allowed_files: Optional[List[str]] = None,
    protected_files: Optional[List[str]] = None,
    risk_level: str = "low",
    permission_mode: str = "approval_required",
    expected_repository_head: str = "",
    expected_working_tree_clean: bool = True,
) -> Dict[str, Any]:
    root = _repo_root(repository_root)
    if root is None:
        return _safe_failure("invalid repository_root")
    target_files = _normalize_list(target_files or [])
    allowed_files = _normalize_list(allowed_files or target_files)
    protected_files = _normalize_list(protected_files or [])
    overlap = sorted(set(allowed_files) & set(protected_files))
    if overlap:
        return _safe_failure("allowed/protected conflict", overlap=overlap)
    normalized_ops: List[Dict[str, Any]] = []
    preimage: Dict[str, str] = {}
    for index, raw in enumerate(operations or []):
        op_type = str(raw.get("operation_type") or "").strip()
        file_path = str(raw.get("file_path") or "").replace("\\", "/").strip()
        if op_type in FORBIDDEN_OPERATIONS or op_type not in SUPPORTED_OPERATIONS:
            return _safe_failure("unsupported operation", operation_type=op_type)
        path = _resolve(root, file_path)
        if path is None:
            return _safe_failure("operation path outside repository or excluded", file_path=file_path)
        if file_path not in allowed_files:
            return _safe_failure("operation file not allowed", file_path=file_path)
        if file_path in protected_files:
            return _safe_failure("operation targets protected file", file_path=file_path)
        if _is_binary(path):
            return _safe_failure("binary file rejected", file_path=file_path)
        expected_sha = str(raw.get("expected_file_sha256") or "")
        if path.exists():
            actual_sha = _sha256_file(path)
            preimage[file_path] = actual_sha
            if expected_sha and expected_sha != actual_sha:
                return _safe_failure("expected hash mismatch", file_path=file_path, expected=expected_sha, actual=actual_sha)
        elif op_type != "create_file":
            return _safe_failure("target file missing", file_path=file_path)
        op = {
            "operation_id": str(raw.get("operation_id") or f"op-{index + 1}"),
            "operation_type": op_type,
            "file_path": file_path,
            "expected_file_sha256": expected_sha or preimage.get(file_path, ""),
            "anchor_text": str(raw.get("anchor_text") or ""),
            "old_text": str(raw.get("old_text") or ""),
            "new_text": str(raw.get("new_text") or ""),
            "expected_occurrences": int(raw.get("expected_occurrences", 1) or 1),
            "encoding": str(raw.get("encoding") or "utf-8"),
        }
        op["operation_digest"] = _digest({k: v for k, v in op.items() if k != "operation_digest"}, prefix="op")
        normalized_ops.append(op)
    patch_contract = {
        "patch_id": _digest({"task_id": task_id, "title": patch_title, "operations": normalized_ops}, prefix="patch-id"),
        "task_id": task_id,
        "repository_root": str(root),
        "patch_title": patch_title[:400],
        "patch_summary": patch_summary[:1200],
        "target_files": target_files,
        "operations": normalized_ops,
        "allowed_files": allowed_files,
        "protected_files": protected_files,
        "risk_level": risk_level,
        "permission_mode": permission_mode or "approval_required",
        "approval_required": (permission_mode or "approval_required") == "approval_required",
        "expected_repository_head": expected_repository_head or _git_read(root, ["rev-parse", "HEAD"]),
        "expected_working_tree_clean": bool(expected_working_tree_clean),
        "preimage_digest": _digest(preimage, prefix="preimage"),
        "created_at": _now(),
    }
    patch_contract["patch_digest"] = _digest(
        {
            "task_id": task_id,
            "repository_root": str(root),
            "target_files": target_files,
            "operations": normalized_ops,
            "allowed_files": allowed_files,
            "protected_files": protected_files,
            "expected_repository_head": patch_contract["expected_repository_head"],
        },
        prefix="patch-digest",
    )
    patch_contract["approval_token_hint"] = _approval_token(patch_contract["patch_digest"])
    return _safe_success(patch_contract=patch_contract, patch_id=patch_contract["patch_id"], patch_digest=patch_contract["patch_digest"])


def preview_patch(patch_contract: Dict[str, Any]) -> Dict[str, Any]:
    root = _repo_root(str(patch_contract.get("repository_root") or ""))
    if root is None:
        return _safe_failure("invalid repository_root")
    errors: List[str] = []
    files_to_modify: List[str] = []
    files_to_create: List[str] = []
    risk_flags: List[str] = []
    for op in patch_contract.get("operations", []):
        rel = str(op.get("file_path") or "")
        path = _resolve(root, rel)
        if path is None:
            errors.append(f"external_path:{rel}")
            continue
        if rel in patch_contract.get("protected_files", []):
            errors.append(f"protected_file:{rel}")
            risk_flags.append("protected_surface")
            continue
        if rel not in patch_contract.get("allowed_files", []):
            errors.append(f"not_allowed:{rel}")
            continue
        op_type = op.get("operation_type")
        if op_type == "create_file":
            if path.exists():
                errors.append(f"create_file_overwrite:{rel}")
            else:
                files_to_create.append(rel)
            continue
        if not path.exists():
            errors.append(f"missing_file:{rel}")
            continue
        if _is_binary(path):
            errors.append(f"binary_file:{rel}")
            continue
        actual_sha = _sha256_file(path)
        if op.get("expected_file_sha256") and op.get("expected_file_sha256") != actual_sha:
            errors.append(f"hash_mismatch:{rel}")
            continue
        content = path.read_text(encoding=op.get("encoding") or "utf-8")
        needle = str(op.get("old_text") or op.get("anchor_text") or "")
        if not needle:
            errors.append(f"missing_anchor:{rel}")
            continue
        count = content.count(needle)
        if count != int(op.get("expected_occurrences", 1) or 1):
            errors.append(f"occurrence_mismatch:{rel}:{count}")
            continue
        files_to_modify.append(rel)
    dirty = _git_read(root, ["status", "--short"]) != ""
    if dirty and patch_contract.get("expected_working_tree_clean", True):
        risk_flags.append("dirty_repository")
    protected_surface = "protected_surface" in risk_flags
    approval_required = bool(patch_contract.get("approval_required", True))
    apply_allowed = not errors and not protected_surface and not approval_required and not dirty
    preview = {
        "patch_preview_id": _digest({"patch": patch_contract.get("patch_digest"), "errors": errors}, prefix="preview"),
        "patch_id": patch_contract.get("patch_id", ""),
        "valid": not errors,
        "validation_errors": errors,
        "files_to_modify": sorted(set(files_to_modify)),
        "files_to_create": sorted(set(files_to_create)),
        "operation_count": len(patch_contract.get("operations", [])),
        "expected_diff_summary": {
            "modify": sorted(set(files_to_modify)),
            "create": sorted(set(files_to_create)),
            "operation_count": len(patch_contract.get("operations", [])),
        },
        "risk_flags": sorted(set(risk_flags)),
        "protected_surface_detected": protected_surface,
        "approval_required": approval_required,
        "apply_allowed": apply_allowed,
        "preview_digest": "",
        "external_api_used": False,
        "network_access_used": False,
        "local_first": True,
    }
    preview["preview_digest"] = _digest({k: v for k, v in preview.items() if k != "preview_digest"}, prefix="preview-digest")
    preview["ok"] = True
    return preview


def create_snapshot(patch_contract: Dict[str, Any]) -> Dict[str, Any]:
    root = _repo_root(str(patch_contract.get("repository_root") or ""))
    if root is None:
        return _safe_failure("invalid repository_root")
    snapshot_id = _digest({"patch": patch_contract.get("patch_digest"), "time": _now()}, prefix="snapshot")
    snapshot_root = root / ".luxcode_runtime" / "snapshots" / snapshot_id
    snapshot_root.mkdir(parents=True, exist_ok=True)
    files = []
    for rel in sorted(set(patch_contract.get("target_files", []) + [op.get("file_path", "") for op in patch_contract.get("operations", [])])):
        path = _resolve(root, rel)
        if path is None or rel in patch_contract.get("protected_files", []):
            continue
        copy_path = snapshot_root / rel
        copy_path.parent.mkdir(parents=True, exist_ok=True)
        existed = bool(path.exists())
        digest = _sha256_file(path) if existed else ""
        if existed:
            shutil.copy2(path, copy_path)
        files.append({"file_path": rel, "existed_before": existed, "content_sha256": digest, "snapshot_copy_path": str(copy_path.relative_to(root))})
    snapshot = {
        "snapshot_id": snapshot_id,
        "patch_id": patch_contract.get("patch_id", ""),
        "repository_head": _git_read(root, ["rev-parse", "HEAD"]),
        "files": files,
        "snapshot_root": str(snapshot_root),
        "created_at": _now(),
        "rollback_available": True,
    }
    snapshot["snapshot_digest"] = _digest({k: v for k, v in snapshot.items() if k != "snapshot_digest"}, prefix="snapshot-digest")
    (snapshot_root / "manifest.json").write_text(_stable_json(snapshot), encoding="utf-8")
    SNAPSHOTS[snapshot_id] = snapshot
    return _safe_success(snapshot=snapshot, snapshot_id=snapshot_id)


def _apply_operation(root: Path, op: Dict[str, Any]) -> Dict[str, Any]:
    rel = str(op.get("file_path") or "")
    path = _resolve(root, rel)
    if path is None:
        return {"ok": False, "file_path": rel, "error": "external_path"}
    op_type = op.get("operation_type")
    encoding = op.get("encoding") or "utf-8"
    if op_type == "create_file":
        if path.exists():
            return {"ok": False, "file_path": rel, "error": "create_file_overwrite"}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(op.get("new_text") or ""), encoding=encoding)
        return {"ok": True, "file_path": rel, "operation_type": op_type}
    content = path.read_text(encoding=encoding)
    old = str(op.get("old_text") or op.get("anchor_text") or "")
    new = str(op.get("new_text") or "")
    if content.count(old) != int(op.get("expected_occurrences", 1) or 1):
        return {"ok": False, "file_path": rel, "error": "occurrence_mismatch"}
    if op_type == "replace_text":
        updated = content.replace(old, new, int(op.get("expected_occurrences", 1) or 1))
    elif op_type == "insert_before":
        updated = content.replace(old, new + old, int(op.get("expected_occurrences", 1) or 1))
    elif op_type == "insert_after":
        updated = content.replace(old, old + new, int(op.get("expected_occurrences", 1) or 1))
    else:
        return {"ok": False, "file_path": rel, "error": "unsupported_operation"}
    path.write_text(updated, encoding=encoding)
    return {"ok": True, "file_path": rel, "operation_type": op_type}


def rollback_snapshot(patch_contract: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
    root = _repo_root(str(patch_contract.get("repository_root") or ""))
    if root is None:
        return _safe_failure("invalid repository_root")
    restored = []
    errors = []
    for item in snapshot.get("files", []):
        rel = item.get("file_path", "")
        path = _resolve(root, rel)
        if path is None:
            errors.append(f"external_path:{rel}")
            continue
        copy_path = root / str(item.get("snapshot_copy_path", ""))
        if item.get("existed_before"):
            if not copy_path.exists():
                errors.append(f"snapshot_missing:{rel}")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(copy_path, path)
            if _sha256_file(path) != item.get("content_sha256"):
                errors.append(f"hash_restore_failed:{rel}")
            restored.append(rel)
        else:
            if path.exists():
                path.unlink()
            restored.append(rel)
    result = {
        "rollback_id": _digest({"snapshot": snapshot.get("snapshot_id"), "time": _now()}, prefix="rollback"),
        "snapshot_id": snapshot.get("snapshot_id", ""),
        "restored_files": restored,
        "errors": errors,
        "rollback_performed": not errors,
        "rollback_digest": "",
        "external_api_used": False,
        "network_access_used": False,
        "local_first": True,
    }
    result["rollback_digest"] = _digest(result, prefix="rollback-digest")
    result["ok"] = not errors
    return result


def _allowed_validation_command(step: Dict[str, Any]) -> Tuple[bool, List[str], str]:
    command = step.get("command", [])
    if isinstance(command, str):
        return False, [], "command must be token list"
    tokens = [str(item) for item in command]
    if not tokens:
        return False, [], "empty command"
    lowered = " ".join(tokens).lower()
    forbidden = [";", "&&", "|", "cmd", "/c", "bash", "-c", "pip", "install", "git add", "git commit", "git push", "rm ", "del "]
    if any(item in lowered for item in forbidden):
        return False, [], "forbidden command token"
    if tokens[:3] == [sys.executable, "-m", "py_compile"] or tokens[:3] == ["python", "-m", "py_compile"]:
        return True, tokens, ""
    if tokens[:2] in ([sys.executable, "scripts/smoke_check.py"], ["python", "scripts/smoke_check.py"]) and (("--quick" in tokens) or ("--check" in tokens and len(tokens) <= 4)):
        return True, tokens, ""
    if tokens[:1] == ["git"] and tokens[1:] == ["diff", "--check"]:
        return True, tokens, ""
    if len(tokens) == 2 and tokens[0] in {sys.executable, "python"} and tokens[1].startswith("scripts/validate_") and tokens[1].endswith(".py"):
        return True, tokens, ""
    return False, tokens, "command not allowlisted"


def run_validation_plan(repository_root: str, validation_plan: Dict[str, Any]) -> Dict[str, Any]:
    root = _repo_root(repository_root)
    if root is None:
        return _safe_failure("invalid repository_root")
    steps = validation_plan.get("steps", [])
    results = []
    failed_step_id = ""
    timed_out = False
    for index, step in enumerate(steps):
        step_id = str(step.get("step_id") or f"step-{index + 1}")
        allowed, tokens, reason = _allowed_validation_command(step)
        if not allowed:
            results.append({"step_id": step_id, "passed": False, "blocked": True, "error": reason, "command": tokens})
            failed_step_id = step_id
            if validation_plan.get("stop_on_failure", True):
                break
            continue
        try:
            proc = subprocess.run(tokens, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=int(step.get("timeout_seconds", validation_plan.get("timeout_seconds", 30)) or 30), shell=False)
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            results.append({"step_id": step_id, "passed": False, "timed_out": True, "stdout_summary": _redact(exc.stdout or ""), "stderr_summary": _redact(exc.stderr or "")})
            failed_step_id = step_id
            break
        expected = step.get("expected_exit_codes", [0]) or [0]
        passed = proc.returncode in expected
        results.append({"step_id": step_id, "passed": passed, "exit_code": proc.returncode, "stdout_summary": _redact(proc.stdout), "stderr_summary": _redact(proc.stderr), "command": tokens})
        if not passed:
            failed_step_id = step_id
            if validation_plan.get("stop_on_failure", True):
                break
    passed_all = bool(steps) and all(item.get("passed") for item in results) and not failed_step_id
    result = {
        "validation_result_id": _digest({"steps": results}, prefix="validation-result"),
        "steps": results,
        "passed": passed_all,
        "failed_step_id": failed_step_id,
        "stdout_summary": _redact("\n".join(str(item.get("stdout_summary", "")) for item in results)),
        "stderr_summary": _redact("\n".join(str(item.get("stderr_summary", "")) for item in results)),
        "timed_out": timed_out,
        "artifact_detected": False,
        "validation_digest": "",
        "external_api_used": False,
        "network_access_used": False,
        "local_first": True,
    }
    result["validation_digest"] = _digest(result, prefix="validation-digest")
    result["ok"] = True
    return result


def execute_patch_control(
    patch_contract: Dict[str, Any],
    action: str = "preview",
    approval_confirmed: bool = False,
    approval_token: str = "",
    dry_run: bool = True,
    run_validation: bool = True,
    rollback_on_failure: bool = True,
    validation_plan: Optional[Dict[str, Any]] = None,
    snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    root = _repo_root(str(patch_contract.get("repository_root") or ""))
    if root is None:
        return _safe_failure("invalid repository_root")
    if action == "preview":
        return preview_patch(patch_contract)
    if action == "rollback":
        if not snapshot:
            return _safe_failure("snapshot required")
        return rollback_snapshot(patch_contract, snapshot)
    if action != "apply":
        return _safe_failure("unsupported patch-control action")
    preview = preview_patch(patch_contract)
    if not preview.get("valid"):
        return _safe_failure("patch preview invalid", preview=preview)
    patch_digest = str(patch_contract.get("patch_digest") or "")
    if patch_digest in APPLIED_PATCH_DIGESTS:
        return _safe_failure("duplicate patch apply blocked", patch_digest=patch_digest)
    if dry_run:
        return _safe_success(patch_execution_id=_digest({"patch": patch_digest, "dry_run": True}, prefix="exec"), patch_id=patch_contract.get("patch_id"), execution_state="preview_only", preview=preview, rollback_performed=False)
    if patch_contract.get("approval_required", True):
        if not approval_confirmed or approval_token != _approval_token(patch_digest):
            return _safe_success(patch_execution_id=_digest({"patch": patch_digest, "approval": False}, prefix="exec"), patch_id=patch_contract.get("patch_id"), execution_state="approval_required", preview=preview, rollback_performed=False)
    expected_head = patch_contract.get("expected_repository_head")
    if expected_head and _git_read(root, ["rev-parse", "HEAD"]) != expected_head:
        return _safe_failure("repository head mismatch")
    if patch_contract.get("expected_working_tree_clean", True) and _git_read(root, ["status", "--short"]):
        return _safe_failure("working tree dirty")
    snapshot_result = create_snapshot(patch_contract)
    if not snapshot_result.get("ok"):
        return snapshot_result
    snapshot_data = snapshot_result["snapshot"]
    operation_results = []
    state = "applied"
    for op in patch_contract.get("operations", []):
        result = _apply_operation(root, op)
        operation_results.append(result)
        if not result.get("ok"):
            state = "failed"
            rollback = rollback_snapshot(patch_contract, snapshot_data)
            return _safe_success(patch_execution_id=_digest({"patch": patch_digest, "failed": True}, prefix="exec"), patch_id=patch_contract.get("patch_id"), execution_state="rolled_back" if rollback.get("ok") else "rollback_failed", snapshot_id=snapshot_data["snapshot_id"], operation_results=operation_results, rollback_performed=rollback.get("ok"), rollback_result=rollback)
    validation_result = {}
    rollback_result = {}
    rollback_performed = False
    if run_validation and validation_plan:
        validation_result = run_validation_plan(str(root), validation_plan)
        if not validation_result.get("passed") and rollback_on_failure:
            rollback_result = rollback_snapshot(patch_contract, snapshot_data)
            rollback_performed = bool(rollback_result.get("ok"))
            state = "rolled_back" if rollback_performed else "rollback_failed"
        elif not validation_result.get("passed"):
            state = "validation_failed"
    if state == "applied":
        APPLIED_PATCH_DIGESTS.add(patch_digest)
    result = {
        "patch_execution_id": _digest({"patch": patch_digest, "state": state, "ops": operation_results}, prefix="exec"),
        "patch_id": patch_contract.get("patch_id", ""),
        "execution_state": state,
        "snapshot_id": snapshot_data["snapshot_id"],
        "modified_files": preview.get("files_to_modify", []),
        "created_files": preview.get("files_to_create", []),
        "operation_results": operation_results,
        "validation_result": validation_result,
        "rollback_performed": rollback_performed,
        "rollback_result": rollback_result,
        "diff_summary": {"changed_files": _normalize_list(_git_read(root, ["diff", "--name-only"]).splitlines(), limit=80)},
        "evidence_records": [],
        "started_at": snapshot_data["created_at"],
        "completed_at": _now(),
        "external_api_used": False,
        "network_access_used": False,
        "local_first": True,
    }
    result["execution_digest"] = _digest(result, prefix="exec-digest")
    result["ok"] = True
    return result


def get_safe_patch_runtime_schema() -> Dict[str, Any]:
    return {
        "name": "LuxCode Safe Patch Runtime",
        "status": "ready",
        "supported_operations": sorted(SUPPORTED_OPERATIONS),
        "forbidden_operations": sorted(FORBIDDEN_OPERATIONS),
        "default_dry_run": True,
        "approval_required_default": True,
        "shell_execution_used": False,
        "git_mutation_used": False,
        "external_api_used": False,
        "network_access_used": False,
        "local_first": True,
    }
