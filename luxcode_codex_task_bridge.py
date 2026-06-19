from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Sequence


ENGINE_ID = "codex"
RUNTIME_ID = "codex_cli"
EXACT_APPROVAL_TEXT = "I APPROVE CODEX EMERGENCY READ-ONLY RUN"

MAX_TARGET_FILES = 4
MAX_FILE_BYTES = 300_000
MAX_CONTEXT_CHARS = 12_000
MAX_OUTPUT_BYTES = 1_000_000
MAX_TIMEOUT_SECONDS = 300

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
    if any(
        marker in lowered
        for marker in ("api_key", "authorization:", "bearer ", "sk-")
    ):
        return "[redacted]"
    return text[:limit]


def resolve_codex_executable() -> str:
    for candidate in ("codex.cmd", "codex.exe", "codex"):
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
            "stdout": _safe_text(exc.stdout, MAX_OUTPUT_BYTES),
            "stderr": _safe_text(exc.stderr, 20_000),
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

    return {
        "ok": proc.returncode == 0,
        "state": "completed" if proc.returncode == 0 else "process_failed",
        "returncode": int(proc.returncode),
        "stdout": (proc.stdout or "")[:MAX_OUTPUT_BYTES],
        "stderr": _safe_text(proc.stderr or "", 20_000),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "process_started": True,
    }


def inspect_codex_readiness(
    *,
    repository_root: str,
    runner: Callable[..., Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    root = str(Path(repository_root).expanduser().resolve())
    executable = resolve_codex_executable()
    blockers = []

    if not executable:
        return {
            "status": "BLOCKED",
            "blockers": ["codex_not_found"],
            "command_present": False,
            "workspace": root,
            "manual_only": True,
            "emergency_only": True,
            "sandbox_mode": "read-only",
            "approval_policy": "never",
            "secret_read_by_luxcode": False,
        }

    call = runner or _run_process
    version_result = call(
        [executable, "--version"],
        cwd=root,
        timeout_seconds=20,
    )
    login_result = call(
        [executable, "login", "status"],
        cwd=root,
        timeout_seconds=20,
    )

    if not version_result.get("ok"):
        blockers.append("version_check_failed")
    if not login_result.get("ok"):
        blockers.append("login_status_failed")

    version = str(version_result.get("stdout") or "").strip()
    login_text = (
        str(login_result.get("stdout") or "")
        + "\n"
        + str(login_result.get("stderr") or "")
    ).strip()
    logged_in = "logged in" in login_text.lower()
    if not logged_in:
        blockers.append("not_logged_in")

    return {
        "status": "READY_FOR_TASK_APPROVAL" if not blockers else "BLOCKED",
        "blockers": sorted(set(blockers)),
        "command_present": True,
        "executable": executable,
        "version": version,
        "login_status": "logged_in" if logged_in else "not_logged_in",
        "workspace": root,
        "manual_only": True,
        "emergency_only": True,
        "plain_exec_only": True,
        "sandbox_mode": "read-only",
        "approval_policy": "never",
        "dangerous_bypass_allowed": False,
        "workspace_write_allowed": False,
        "full_access_allowed": False,
        "model_override_allowed": False,
        "continue_mode_allowed": False,
        "auto_apply_allowed": False,
        "secret_read_by_luxcode": False,
        "cost_class": "chatgpt_plan_credit_or_unknown_manual_agent",
    }


def build_codex_runtime_configuration(
    environ: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    data = os.environ if environ is None else environ
    flags = {
        "engine_enabled": data.get("LUXCODE_CODEX_ENABLED") == "1",
        "real_requests_enabled": (
            data.get("LUXCODE_CODEX_REAL_REQUESTS_ENABLED") == "1"
        ),
        "manual_only_confirmed": (
            data.get("LUXCODE_CODEX_MANUAL_ONLY_CONFIRMED") == "1"
        ),
        "emergency_only_confirmed": (
            data.get("LUXCODE_CODEX_EMERGENCY_ONLY_CONFIRMED") == "1"
        ),
        "credit_usage_acknowledged": (
            data.get("LUXCODE_CODEX_CREDIT_USAGE_ACKNOWLEDGED") == "1"
        ),
    }
    blockers = [name for name, allowed in flags.items() if not allowed]
    return {
        "status": "READY_FOR_TASK_APPROVAL" if not blockers else "BLOCKED",
        "blockers": blockers,
        "flags": flags,
        "manual_only": True,
        "emergency_only": True,
        "sandbox_mode": "read-only",
        "approval_policy": "never",
        "dangerous_bypass_allowed": False,
        "workspace_write_allowed": False,
        "auto_apply_allowed": False,
    }


def build_codex_task_approval(
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
        "emergency_only": True,
        "sandbox_mode": "read-only",
        "approval_policy": "never",
        "dangerous_bypass_allowed": False,
        "workspace_write_allowed": False,
        "auto_apply_allowed": False,
        "provider_credit_usage_unbounded_by_luxcode": True,
    }
    payload["approval_digest"] = _digest(payload, "codex-approval")
    return payload


def validate_codex_task_approval(
    *,
    approval: Mapping[str, Any] | None,
    task_id: str,
    repository_root: str,
    target_files: Sequence[str],
) -> Dict[str, Any]:
    expected = build_codex_task_approval(
        task_id=task_id,
        repository_root=repository_root,
        target_files=target_files,
    )
    blockers = []
    if not bool((approval or {}).get("approved")):
        blockers.append("codex_not_approved")
    if str((approval or {}).get("approval_digest") or "") != expected[
        "approval_digest"
    ]:
        blockers.append("approval_digest_mismatch")
    if str((approval or {}).get("confirmation_text") or "") != (
        EXACT_APPROVAL_TEXT
    ):
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
        text = str(
            minimum_context.get(rel)
            or raw.decode("utf-8", errors="replace")
        )
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


def build_codex_prompt(
    *,
    task_summary: str,
    target_files: Sequence[str],
    minimum_context: Mapping[str, str],
) -> str:
    payload = {
        "instruction": (
            "Return only the JSON object required by the supplied output schema. "
            "The workspace is read-only. Do not edit files, do not request secrets, "
            "do not use network tools, and do not propose shell commands. "
            "Propose only exact replace_text operations for the listed target files."
        ),
        "task_summary": _safe_text(task_summary, 2000),
        "target_files": list(target_files),
        "minimum_context": dict(minimum_context),
    }
    return _stable_json(payload)[:MAX_CONTEXT_CHARS]


def build_codex_output_schema() -> Dict[str, Any]:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "analysis_summary": {"type": "string"},
            "patch_operations": {
                "type": "array",
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "operation_type": {
                            "type": "string",
                            "enum": ["replace_text"],
                        },
                        "file_path": {"type": "string"},
                        "old_text": {"type": "string"},
                        "new_text": {"type": "string"},
                        "expected_occurrences": {
                            "type": "integer",
                            "enum": [1],
                        },
                        "reason": {"type": "string"},
                    },
                    "required": [
                        "operation_type",
                        "file_path",
                        "old_text",
                        "new_text",
                        "expected_occurrences",
                        "reason",
                    ],
                },
            },
            "validation_recommendations": {
                "type": "array",
                "items": {"type": "string"},
            },
            "remaining_gap": {"type": "string"},
            "failure_reason": {"type": "string"},
        },
        "required": [
            "analysis_summary",
            "patch_operations",
            "validation_recommendations",
            "remaining_gap",
            "failure_reason",
        ],
    }


def build_codex_command(
    *,
    executable: str,
    repository_root: str,
    prompt: str,
    schema_path: str,
    output_path: str,
) -> list[str]:
    return [
        executable,
        "exec",
        "-s",
        "read-only",
        "-a",
        "never",
        "-C",
        str(Path(repository_root).expanduser().resolve()),
        "--json",
        "--output-schema",
        schema_path,
        "-o",
        output_path,
        prompt,
    ]


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
            expected_occurrences = int(
                item.get("expected_occurrences", 1) or 1
            )
        except (TypeError, ValueError):
            expected_occurrences = -1

        if operation_type != "replace_text":
            issues.append(f"operation_{index}_unsupported_type")
            continue
        if (
            rel not in allowed
            or rel.startswith(("/", "../"))
            or ".." in Path(rel).parts
        ):
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
        if (
            not old_text
            or expected_occurrences != 1
            or current.count(old_text) != 1
        ):
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
                "step_id": f"codex-step-{index}",
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
        "state": (
            "validated"
            if bool(steps) and not issues
            else "invalid_patch"
        ),
        "issues": issues,
        "patch_steps": steps,
        "files_to_modify": files_to_modify,
        "expected_file_hashes": expected_hashes,
    }


def execute_codex_task_bridge(
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
    runtime = build_codex_runtime_configuration(environ)
    readiness = inspect_codex_readiness(
        repository_root=root,
        runner=runner,
    )
    targets, context, before_hashes = _safe_repository_files(
        root,
        target_files,
        minimum_context,
    )
    approval_check = validate_codex_task_approval(
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
            "sandbox_mode": "read-only",
            "approval_policy": "never",
            "dangerous_bypass_used": False,
            "provider_cost": (
                "chatgpt_plan_credit_or_unknown_manual_agent"
            ),
        }

    executable = str(readiness.get("executable") or "")
    prompt = build_codex_prompt(
        task_summary=task_summary,
        target_files=targets,
        minimum_context=context,
    )

    with tempfile.TemporaryDirectory(prefix="luxcode_codex_bridge_") as tmp:
        temp_root = Path(tmp)
        schema_path = temp_root / "response.schema.json"
        output_path = temp_root / "last_message.json"
        schema_path.write_text(
            json.dumps(build_codex_output_schema(), sort_keys=True),
            encoding="utf-8",
        )

        command = build_codex_command(
            executable=executable,
            repository_root=root,
            prompt=prompt,
            schema_path=str(schema_path),
            output_path=str(output_path),
        )
        call = runner or _run_process
        result = call(
            command,
            cwd=root,
            timeout_seconds=MAX_TIMEOUT_SECONDS,
        )

        output_text = ""
        if output_path.is_file():
            output_text = output_path.read_text(
                encoding="utf-8",
                errors="replace",
            )[:MAX_OUTPUT_BYTES]

    after_hashes = {}
    for rel in targets:
        path = Path(root) / rel
        if path.is_file():
            after_hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()

    if before_hashes != after_hashes:
        return {
            "ok": False,
            "state": "unsafe_file_change_detected",
            "blockers": ["codex_changed_files_in_read_only_mode"],
            "process": {
                "state": result.get("state"),
                "returncode": result.get("returncode"),
                "duration_ms": result.get("duration_ms"),
            },
            "external_api_used": bool(result.get("process_started")),
            "process_started": bool(result.get("process_started")),
            "file_write_blocked": False,
            "sandbox_mode": "read-only",
            "approval_policy": "never",
            "dangerous_bypass_used": False,
            "provider_cost": (
                "chatgpt_plan_credit_or_unknown_manual_agent"
            ),
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
            "sandbox_mode": "read-only",
            "approval_policy": "never",
            "dangerous_bypass_used": False,
            "provider_cost": (
                "chatgpt_plan_credit_or_unknown_manual_agent"
            ),
        }

    try:
        response = json.loads(output_text)
    except json.JSONDecodeError:
        response = None

    if not isinstance(response, dict):
        return {
            "ok": False,
            "state": "schema_invalid",
            "blockers": ["structured_last_message_not_found"],
            "process": {
                "returncode": result.get("returncode"),
                "duration_ms": result.get("duration_ms"),
            },
            "external_api_used": True,
            "process_started": True,
            "file_write_blocked": True,
            "sandbox_mode": "read-only",
            "approval_policy": "never",
            "dangerous_bypass_used": False,
            "provider_cost": (
                "chatgpt_plan_credit_or_unknown_manual_agent"
            ),
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
                "response": response,
                "validation": validation,
            },
            "codex-evidence",
        ),
        "engine_id": ENGINE_ID,
        "runtime_id": RUNTIME_ID,
        "manual_only": True,
        "emergency_only": True,
        "sandbox_mode": "read-only",
        "approval_policy": "never",
        "dangerous_bypass_used": False,
        "workspace_write_used": False,
        "file_write_detected": False,
        "provider_cost": (
            "chatgpt_plan_credit_or_unknown_manual_agent"
        ),
    }

    return {
        "ok": bool(validation.get("ok")),
        "state": str(validation.get("state") or "invalid_patch"),
        "model_response": response,
        "patch_steps": list(validation.get("patch_steps", [])),
        "files_to_modify": list(
            validation.get("files_to_modify", [])
        ),
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
        "sandbox_mode": "read-only",
        "approval_policy": "never",
        "dangerous_bypass_used": False,
        "provider_cost": (
            "chatgpt_plan_credit_or_unknown_manual_agent"
        ),
        "approval_required_for_apply": True,
    }
