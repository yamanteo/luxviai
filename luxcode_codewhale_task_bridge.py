from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Sequence


ENGINE_ID = "whale"
RUNTIME_ID = "codewhale_cli"
EXACT_APPROVAL_TEXT = "I APPROVE CODEWHALE MANUAL RUN"
MAX_TARGET_FILES = 4
MAX_FILE_BYTES = 300_000
MAX_CONTEXT_CHARS = 12_000
MAX_OUTPUT_BYTES = 1_000_000
MAX_TIMEOUT_SECONDS = 180

FORBIDDEN_TEXT_HINTS = (
    ".env",
    "api_key",
    "authorization:",
    "bearer ",
    "rm -rf",
    "format c:",
    "del /s",
    "powershell -enc",
)


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def _digest(value: Any, prefix: str) -> str:
    raw = _stable_json(value).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:32]}"


def _safe_text(value: Any, limit: int = 4000) -> str:
    text = str(value or "")
    lowered = text.lower()
    if any(marker in lowered for marker in ("api_key", "authorization:", "bearer ", "sk-")):
        return "[redacted]"
    return text[:limit]


def resolve_codewhale_executable() -> str:
    candidates = (
        "codewhale.cmd",
        "codewhale.exe",
        "codewhale",
    )
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return ""


def _run_process(
    command: Sequence[str],
    *,
    cwd: str,
    timeout_seconds: int,
) -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=max(1, min(int(timeout_seconds), MAX_TIMEOUT_SECONDS)),
            shell=False,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "state": "timeout",
            "returncode": None,
            "stdout": _safe_text(exc.stdout),
            "stderr": _safe_text(exc.stderr),
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "process_started": True,
        }
    except OSError as exc:
        return {
            "ok": False,
            "state": "launch_failed",
            "returncode": None,
            "stdout": "",
            "stderr": _safe_text(exc),
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "process_started": False,
        }

    stdout = (proc.stdout or "")[:MAX_OUTPUT_BYTES]
    stderr = (proc.stderr or "")[:20_000]
    return {
        "ok": proc.returncode == 0,
        "state": "completed" if proc.returncode == 0 else "process_failed",
        "returncode": int(proc.returncode),
        "stdout": stdout,
        "stderr": _safe_text(stderr, 20_000),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "process_started": True,
    }


def inspect_codewhale_readiness(
    *,
    repository_root: str,
    runner: Callable[..., Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    root = str(Path(repository_root).expanduser().resolve())
    executable = resolve_codewhale_executable()
    blockers = []
    warnings = []
    if not executable:
        blockers.append("codewhale_not_found")
        return {
            "status": "BLOCKED",
            "blockers": blockers,
            "warnings": warnings,
            "command_present": False,
            "workspace": root,
            "manual_only": True,
            "auto_mode_allowed": False,
            "file_tools_allowed": False,
            "secret_read_by_luxcode": False,
        }

    call = runner or _run_process
    doctor = call(
        [executable, "doctor", "--json"],
        cwd=root,
        timeout_seconds=30,
    )
    if not doctor.get("ok"):
        blockers.append("doctor_failed")
        return {
            "status": "BLOCKED",
            "blockers": blockers,
            "warnings": warnings,
            "command_present": True,
            "executable": executable,
            "workspace": root,
            "doctor": {
                "state": doctor.get("state"),
                "returncode": doctor.get("returncode"),
                "stderr": _safe_text(doctor.get("stderr")),
            },
            "manual_only": True,
            "auto_mode_allowed": False,
            "file_tools_allowed": False,
            "secret_read_by_luxcode": False,
        }

    try:
        data = json.loads(str(doctor.get("stdout") or ""))
    except json.JSONDecodeError:
        data = {}
        blockers.append("doctor_json_invalid")

    config_present = bool(data.get("config_present"))
    api_source = str((data.get("api_key") or {}).get("source") or "")
    provider = str((data.get("capability") or {}).get("resolved_provider") or "")
    model = str((data.get("capability") or {}).get("resolved_model") or "")
    sandbox_available = bool((data.get("sandbox") or {}).get("available"))
    tls_verified = bool((data.get("tls") or {}).get("certificate_verification"))
    reported_workspace = str(data.get("workspace") or "")

    if not config_present:
        blockers.append("config_missing")
    if not api_source:
        blockers.append("configured_api_key_missing")
    if not provider:
        blockers.append("provider_unresolved")
    if not model:
        blockers.append("model_unresolved")
    if not tls_verified:
        blockers.append("tls_verification_disabled")
    if not sandbox_available:
        warnings.append("sandbox_unavailable_auto_mode_forbidden")
    if reported_workspace and Path(reported_workspace).resolve() != Path(root).resolve():
        warnings.append("doctor_workspace_differs_from_requested_workspace")

    return {
        "status": "READY_FOR_TASK_APPROVAL" if not blockers else "BLOCKED",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "command_present": True,
        "executable": executable,
        "version": str(data.get("version") or ""),
        "config_present": config_present,
        "configured_api_key_source": api_source,
        "provider": provider,
        "model_id": model,
        "base_url": str(data.get("base_url") or ""),
        "workspace": root,
        "reported_workspace": reported_workspace,
        "sandbox_available": sandbox_available,
        "strict_tool_mode_enabled": bool(
            (data.get("strict_tool_mode") or {}).get("enabled")
        ),
        "tls_certificate_verification": tls_verified,
        "manual_only": True,
        "plain_exec_only": True,
        "auto_mode_allowed": False,
        "continue_mode_allowed": False,
        "file_tools_allowed": False,
        "secret_read_by_luxcode": False,
        "live_connectivity_checked": bool(
            (data.get("api_connectivity") or {}).get("checked")
        ),
        "cost_class": "paid_or_unknown_manual_agent",
    }


def build_codewhale_runtime_configuration(
    environ: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    data = os.environ if environ is None else environ
    flags = {
        "engine_enabled": data.get("LUXCODE_CODEWHALE_ENABLED") == "1",
        "real_requests_enabled": (
            data.get("LUXCODE_CODEWHALE_REAL_REQUESTS_ENABLED") == "1"
        ),
        "manual_only_confirmed": (
            data.get("LUXCODE_CODEWHALE_MANUAL_ONLY_CONFIRMED") == "1"
        ),
        "paid_model_acknowledged": (
            data.get("LUXCODE_CODEWHALE_PAID_MODEL_ACKNOWLEDGED") == "1"
        ),
    }
    blockers = [name for name, allowed in flags.items() if not allowed]
    return {
        "status": "READY_FOR_TASK_APPROVAL" if not blockers else "BLOCKED",
        "blockers": blockers,
        "flags": flags,
        "manual_only": True,
        "auto_mode_allowed": False,
        "continue_mode_allowed": False,
        "file_tools_allowed": False,
        "api_key_argument_allowed": False,
        "auto_apply_allowed": False,
    }


def build_codewhale_task_approval(
    *,
    task_id: str,
    repository_root: str,
    target_files: Sequence[str],
) -> Dict[str, Any]:
    payload = {
        "task_id": str(task_id),
        "repository_root": str(Path(repository_root).expanduser().resolve()),
        "target_files": sorted(
            {
                str(item).replace("\\", "/").strip()
                for item in target_files
                if str(item).strip()
            }
        )[:MAX_TARGET_FILES],
        "confirmation_text": EXACT_APPROVAL_TEXT,
        "single_request_only": True,
        "manual_only": True,
        "plain_exec_only": True,
        "auto_mode_allowed": False,
        "continue_mode_allowed": False,
        "file_tools_allowed": False,
        "auto_apply_allowed": False,
        "provider_cost_unbounded_by_cli": True,
    }
    payload["approval_digest"] = _digest(payload, "codewhale-approval")
    return payload


def validate_codewhale_task_approval(
    *,
    approval: Mapping[str, Any] | None,
    task_id: str,
    repository_root: str,
    target_files: Sequence[str],
) -> Dict[str, Any]:
    expected = build_codewhale_task_approval(
        task_id=task_id,
        repository_root=repository_root,
        target_files=target_files,
    )
    blockers = []
    if not bool((approval or {}).get("approved")):
        blockers.append("manual_agent_not_approved")
    if str((approval or {}).get("approval_digest") or "") != expected["approval_digest"]:
        blockers.append("approval_digest_mismatch")
    if str((approval or {}).get("confirmation_text") or "") != EXACT_APPROVAL_TEXT:
        blockers.append("approval_text_mismatch")
    if bool((approval or {}).get("consumed")):
        blockers.append("single_request_approval_already_consumed")
    return {
        "allowed": not blockers,
        "blockers": blockers,
        "expected": expected,
    }


def _safe_repository_files(
    repository_root: str,
    target_files: Sequence[str],
    minimum_context: Mapping[str, str],
) -> tuple[list[str], Dict[str, str], Dict[str, str]]:
    root = Path(repository_root).expanduser().resolve()
    targets: list[str] = []
    context: Dict[str, str] = {}
    hashes: Dict[str, str] = {}
    total = 0

    for item in target_files:
        rel = str(item).replace("\\", "/").strip()
        if (
            not rel
            or rel.startswith(("/", "../"))
            or ".." in Path(rel).parts
            or rel == ".env"
            or rel in targets
        ):
            continue
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size > MAX_FILE_BYTES
        ):
            continue
        raw = path.read_bytes()
        text = str(minimum_context.get(rel) or raw.decode("utf-8", errors="replace"))
        remaining = MAX_CONTEXT_CHARS - total
        if remaining <= 0:
            break
        context[rel] = text[:remaining]
        total += len(context[rel])
        targets.append(rel)
        hashes[rel] = hashlib.sha256(raw).hexdigest()
        if len(targets) >= MAX_TARGET_FILES:
            break
    return targets, context, hashes


def build_codewhale_prompt(
    *,
    task_summary: str,
    target_files: Sequence[str],
    minimum_context: Mapping[str, str],
) -> str:
    contract = {
        "analysis_summary": "short string",
        "patch_operations": [
            {
                "operation_type": "replace_text",
                "file_path": "must be one of target_files",
                "old_text": "exact text occurring once",
                "new_text": "replacement text",
                "expected_occurrences": 1,
                "reason": "short reason",
            }
        ],
        "validation_recommendations": ["safe local checks only"],
        "remaining_gap": "",
        "failure_reason": "",
    }
    payload = {
        "instruction": (
            "Return exactly one JSON object and no markdown. "
            "Do not use tools, do not edit files, do not run commands, do not browse, "
            "and do not request secrets. Propose only exact replace_text operations."
        ),
        "task_summary": _safe_text(task_summary, 2000),
        "target_files": list(target_files),
        "minimum_context": dict(minimum_context),
        "required_contract": contract,
    }
    return _stable_json(payload)[:MAX_CONTEXT_CHARS]


def build_codewhale_command(
    *,
    executable: str,
    repository_root: str,
    prompt: str,
) -> list[str]:
    # Deliberately no --auto, --continue, --api-key or sandbox override.
    return [
        executable,
        "-C",
        str(Path(repository_root).expanduser().resolve()),
        "exec",
        "--json",
        prompt,
    ]


def _walk_for_text(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        texts.append(value)
    elif isinstance(value, dict):
        preferred = (
            "content",
            "response",
            "output",
            "message",
            "text",
            "result",
            "summary",
        )
        for key in preferred:
            if key in value:
                texts.extend(_walk_for_text(value[key]))
        for key, item in value.items():
            if key not in preferred:
                texts.extend(_walk_for_text(item))
    elif isinstance(value, list):
        for item in value:
            texts.extend(_walk_for_text(item))
    return texts


def _extract_single_json_object(text: str) -> Dict[str, Any] | None:
    cleaned = str(text or "").strip()
    if not cleaned:
        return None
    try:
        direct = json.loads(cleaned)
        if isinstance(direct, dict):
            if "patch_operations" in direct:
                return direct
            for candidate in _walk_for_text(direct):
                nested = _extract_single_json_object(candidate)
                if nested is not None:
                    return nested
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(cleaned)):
        char = cleaned[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start:index + 1]
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    return None
                return parsed if isinstance(parsed, dict) else None
    return None


def _validate_patch_steps(
    *,
    repository_root: str,
    target_files: Sequence[str],
    response: Mapping[str, Any],
) -> Dict[str, Any]:
    root = Path(repository_root).expanduser().resolve()
    allowed = set(target_files)
    operations = response.get("patch_operations")
    if not isinstance(operations, list) or not operations:
        return {
            "ok": False,
            "state": "no_patch_operations",
            "issues": ["no_patch_operations"],
        }

    steps: list[Dict[str, Any]] = []
    files_to_modify: list[str] = []
    expected_hashes: Dict[str, str] = {}
    issues: list[str] = []

    for index, item in enumerate(operations[:8], 1):
        if not isinstance(item, dict):
            issues.append(f"operation_{index}_not_object")
            continue
        operation_type = str(item.get("operation_type") or "")
        rel = str(item.get("file_path") or "").replace("\\", "/").strip()
        old_text = str(item.get("old_text") or "")
        new_text = str(item.get("new_text") or "")
        try:
            expected_occurrences = int(item.get("expected_occurrences", 1) or 1)
        except (TypeError, ValueError):
            expected_occurrences = -1

        if operation_type != "replace_text":
            issues.append(f"operation_{index}_unsupported_type")
            continue
        if rel not in allowed or rel.startswith(("/", "../")) or ".." in Path(rel).parts:
            issues.append(f"operation_{index}_scope_violation")
            continue
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            issues.append(f"operation_{index}_path_escape")
            continue
        if not path.is_file() or path.is_symlink():
            issues.append(f"operation_{index}_missing_file")
            continue
        current = path.read_text(encoding="utf-8", errors="replace")
        if not old_text or expected_occurrences != 1 or current.count(old_text) != 1:
            issues.append(f"operation_{index}_anchor_mismatch")
            continue
        combined = f"{old_text}\n{new_text}".lower()
        if any(marker in combined for marker in FORBIDDEN_TEXT_HINTS):
            issues.append(f"operation_{index}_forbidden_instruction")
            continue
        if old_text == new_text:
            issues.append(f"operation_{index}_no_change")
            continue

        expected_hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        if rel not in files_to_modify:
            files_to_modify.append(rel)
        steps.append(
            {
                "step_id": f"codewhale-step-{index}",
                "operation_type": "replace_text",
                "file_path": rel,
                "old_text": old_text,
                "new_text": new_text,
                "expected_occurrences": 1,
                "reason": _safe_text(item.get("reason"), 500),
                "apply_allowed": False,
                "approval_required": True,
            }
        )

    return {
        "ok": bool(steps) and not issues,
        "state": "validated" if bool(steps) and not issues else "invalid_patch",
        "issues": issues,
        "patch_steps": steps,
        "files_to_modify": files_to_modify,
        "expected_file_hashes": expected_hashes,
    }


def execute_codewhale_task_bridge(
    *,
    task_id: str,
    repository_root: str,
    task_summary: str,
    target_files: Sequence[str],
    minimum_context: Mapping[str, str],
    approval: Mapping[str, Any] | None,
    environ: Mapping[str, str] | None = None,
    runner: Callable[..., Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    root = str(Path(repository_root).expanduser().resolve())
    runtime = build_codewhale_runtime_configuration(environ)
    readiness = inspect_codewhale_readiness(
        repository_root=root,
        runner=runner,
    )
    targets, context, before_hashes = _safe_repository_files(
        root,
        target_files,
        minimum_context,
    )
    approval_check = validate_codewhale_task_approval(
        approval=approval,
        task_id=task_id,
        repository_root=root,
        target_files=targets,
    )
    blockers = (
        list(runtime.get("blockers", []))
        + list(readiness.get("blockers", []))
        + list(approval_check.get("blockers", []))
    )
    if not targets:
        blockers.append("no_safe_target_files")
    if blockers:
        return {
            "ok": False,
            "state": "blocked",
            "blockers": sorted(set(blockers)),
            "readiness": readiness,
            "runtime": runtime,
            "approval": approval_check,
            "external_api_used": False,
            "process_started": False,
            "file_write_blocked": True,
            "auto_mode_used": False,
            "provider_cost": "unavailable_manual_agent",
        }

    executable = str(readiness.get("executable") or "")
    prompt = build_codewhale_prompt(
        task_summary=task_summary,
        target_files=targets,
        minimum_context=context,
    )
    command = build_codewhale_command(
        executable=executable,
        repository_root=root,
        prompt=prompt,
    )
    call = runner or _run_process
    result = call(
        command,
        cwd=root,
        timeout_seconds=MAX_TIMEOUT_SECONDS,
    )

    after_hashes = {}
    for rel in targets:
        path = Path(root) / rel
        if path.is_file():
            after_hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    files_changed = before_hashes != after_hashes
    if files_changed:
        return {
            "ok": False,
            "state": "unsafe_file_change_detected",
            "blockers": ["codewhale_changed_files_in_plain_exec_mode"],
            "process": {
                "state": result.get("state"),
                "returncode": result.get("returncode"),
                "duration_ms": result.get("duration_ms"),
            },
            "external_api_used": bool(result.get("process_started")),
            "process_started": bool(result.get("process_started")),
            "file_write_blocked": False,
            "auto_mode_used": False,
            "provider_cost": "unavailable_manual_agent",
        }

    if not result.get("ok"):
        return {
            "ok": False,
            "state": str(result.get("state") or "process_failed"),
            "blockers": [],
            "process": {
                "returncode": result.get("returncode"),
                "stderr": _safe_text(result.get("stderr"), 4000),
                "duration_ms": result.get("duration_ms"),
            },
            "readiness": readiness,
            "external_api_used": bool(result.get("process_started")),
            "process_started": bool(result.get("process_started")),
            "file_write_blocked": True,
            "auto_mode_used": False,
            "provider_cost": "unavailable_manual_agent",
        }

    response = _extract_single_json_object(str(result.get("stdout") or ""))
    if not isinstance(response, dict):
        return {
            "ok": False,
            "state": "schema_invalid",
            "blockers": ["structured_json_not_found"],
            "process": {
                "returncode": result.get("returncode"),
                "duration_ms": result.get("duration_ms"),
            },
            "external_api_used": True,
            "process_started": True,
            "file_write_blocked": True,
            "auto_mode_used": False,
            "provider_cost": "unavailable_manual_agent",
        }

    validation = _validate_patch_steps(
        repository_root=root,
        target_files=targets,
        response=response,
    )
    evidence = {
        "evidence_id": _digest(
            {
                "task_id": task_id,
                "provider": readiness.get("provider"),
                "model_id": readiness.get("model_id"),
                "response": response,
                "validation": validation,
            },
            "codewhale-evidence",
        ),
        "engine_id": ENGINE_ID,
        "runtime_id": RUNTIME_ID,
        "provider": readiness.get("provider"),
        "model_id": readiness.get("model_id"),
        "manual_only": True,
        "auto_mode_used": False,
        "file_tools_used": False,
        "file_write_detected": False,
        "provider_cost": "unavailable_manual_agent",
    }
    return {
        "ok": bool(validation.get("ok")),
        "state": str(validation.get("state") or "invalid_patch"),
        "model_id": str(readiness.get("model_id") or ""),
        "provider_id": str(readiness.get("provider") or ""),
        "model_response": response,
        "patch_steps": list(validation.get("patch_steps", [])),
        "files_to_modify": list(validation.get("files_to_modify", [])),
        "expected_file_hashes": dict(
            validation.get("expected_file_hashes", {})
        ),
        "validation": validation,
        "evidence": evidence,
        "process": {
            "returncode": result.get("returncode"),
            "duration_ms": result.get("duration_ms"),
        },
        "external_api_used": True,
        "process_started": True,
        "file_write_blocked": True,
        "auto_mode_used": False,
        "provider_cost": "unavailable_manual_agent",
        "approval_required_for_apply": True,
    }
