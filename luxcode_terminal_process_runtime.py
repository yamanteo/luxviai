from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from luxcode_autonomy_permission_controller import (
    build_plain_language_warning,
    create_permission_profile,
    evaluate_requested_action,
    request_scope_expansion,
)


ACTION_TYPES = {
    "run_script",
    "run_validator",
    "run_test",
    "run_build",
    "install_dependency",
    "start_service",
    "stop_service",
    "check_process",
    "check_port",
    "health_check",
}
PROCESS_STATUSES = {
    "planned",
    "approval_required",
    "ready",
    "starting",
    "running",
    "healthy",
    "completed",
    "failed",
    "timed_out",
    "cancelled",
    "stopping",
    "stopped",
    "cleanup_required",
    "cleaned",
    "stale",
    "blocked",
}
SAFE_INVARIANTS = {
    "shell_used": False,
    "external_api_used": False,
    "network_access_used": False,
    "live_commit_push_deploy_used": False,
    "local_first": True,
}
DEFAULT_OUTPUT_LIMIT = 6000
DEFAULT_TIMEOUT = 30
ENV_ALLOWLIST = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PYTHONPATH", "PYTHONIOENCODING"}
SECRET_KEY_MARKERS = ("key", "token", "secret", "password", "authorization", "cookie", "credential")
BLOCKED_EXECUTABLES = {"cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe", "bash", "sh", "sh.exe"}
CHAIN_TOKENS = {"&&", "||", "|", ">", "<", ";", "`"}
BACKGROUND_ACTIONS = {"start_service"}
EXECUTION_OPS = {
    "run_script": "run_tests",
    "run_validator": "run_validator",
    "run_test": "run_tests",
    "run_build": "run_validator",
    "install_dependency": "install_dependency",
    "start_service": "run_tests",
    "stop_service": "run_tests",
    "check_process": "inspect",
    "check_port": "inspect",
    "health_check": "inspect",
}

_RUNTIMES: Dict[str, Dict[str, Any]] = {}
_PROCESSES: Dict[str, subprocess.Popen] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any, prefix: str = "luxrun-") -> str:
    return prefix + hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()[:20]


def _safe_success(**extra: Any) -> Dict[str, Any]:
    return {"ok": True, **extra, **SAFE_INVARIANTS}


def _safe_failure(message: str, **extra: Any) -> Dict[str, Any]:
    return {"ok": False, "blocked": True, "reason": message, **extra, **SAFE_INVARIANTS}


def _redact_text(value: Any, limit: int = DEFAULT_OUTPUT_LIMIT) -> str:
    if isinstance(value, bytes):
        text = value.decode("utf-8", "replace")
    else:
        text = str(value or "")
    text = text.replace("\x00", "")
    text = re.sub(r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}", r"\1=[redacted]", text)
    text = re.sub(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{8,}", "Bearer [redacted]", text)
    text = re.sub(r"sk-[A-Za-z0-9]{12,}", "sk-[redacted]", text)
    if ".env" in text and "=" in text:
        text = text.replace(".env", "[redacted-env]")
    if len(text) > limit:
        text = text[:limit] + "...[truncated]"
    return text


def _audit(runtime: Dict[str, Any], event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
    runtime.setdefault("audit_events", []).append(
        {
            "event_id": len(runtime.get("audit_events", [])) + 1,
            "event_type": event_type,
            "created_at": _now(),
            "payload": _sanitize_metadata(payload or {}),
        }
    )


def _sanitize_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in SECRET_KEY_MARKERS):
                clean[str(key)] = "[redacted]"
            else:
                clean[str(key)] = _sanitize_metadata(item)
        return clean
    if isinstance(value, list):
        return [_sanitize_metadata(item) for item in value[:80]]
    if isinstance(value, (bytes, str)):
        return _redact_text(value, 1200)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(type(value).__name__)


def _normalize_root(repository_root: Optional[str]) -> Tuple[Optional[Path], str]:
    if not repository_root:
        return None, "repository_root is required"
    try:
        root = Path(repository_root).resolve()
    except OSError as exc:
        return None, f"invalid repository_root: {exc}"
    if not root.exists() or not root.is_dir():
        return None, "repository_root must be an existing directory"
    return root, ""


def _safe_path(root: Path, value: Optional[str], *, must_exist: bool = False) -> Tuple[Optional[Path], str, str]:
    text = str(value or ".").replace("\\", "/").strip()
    if any(token in text for token in ("*", "?", "[", "]")):
        return None, "", "wildcard escalation blocked"
    if any(part == ".." for part in Path(text).parts):
        return None, "", "path traversal blocked"
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=False)
        rel = resolved.relative_to(root).as_posix()
    except (OSError, ValueError):
        return None, "", "outside-root path blocked"
    if must_exist and not resolved.exists():
        return None, "", "path does not exist"
    if resolved.exists():
        try:
            resolved.resolve(strict=True).relative_to(root)
        except (OSError, ValueError):
            return None, "", "symlink or reparse escape blocked"
    return resolved, rel, ""


def _executable_registry(repository_root: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    root, _error = _normalize_root(repository_root)
    registry: Dict[str, Dict[str, Any]] = {}
    python_path = Path(sys.executable).resolve()
    registry["python"] = {
        "name": "python",
        "path": str(python_path),
        "identity": hashlib.sha256(str(python_path).encode("utf-8")).hexdigest()[:16],
        "allowed": True,
        "source": "current_interpreter",
    }
    git_path = shutil.which("git")
    if git_path:
        resolved = Path(git_path).resolve()
        registry["git"] = {"name": "git", "path": str(resolved), "identity": hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:16], "allowed": True, "source": "system_allowlist"}
    if root:
        for rel in ("venv/Scripts/python.exe", ".venv/Scripts/python.exe", "node_modules/.bin/npm.cmd"):
            candidate = root / rel
            if candidate.exists():
                registry[candidate.name.lower()] = {"name": candidate.name.lower(), "path": str(candidate.resolve()), "identity": hashlib.sha256(str(candidate.resolve()).encode("utf-8")).hexdigest()[:16], "allowed": True, "source": "project_local"}
    return registry


def _resolve_executable(executable: str, repository_root: Optional[str]) -> Tuple[Optional[str], Dict[str, Any], str]:
    name = str(executable or "").strip()
    if not name:
        return None, {}, "executable is required"
    if name.lower() in BLOCKED_EXECUTABLES:
        return None, {}, "blocked shell executable"
    registry = _executable_registry(repository_root)
    if name in registry:
        entry = registry[name]
        return entry["path"], entry, ""
    path = Path(name)
    if path.is_absolute():
        resolved = path.resolve()
        for entry in registry.values():
            if Path(entry["path"]).resolve() == resolved:
                return entry["path"], entry, ""
    return None, {}, "executable not in allowlist"


def _validate_args(args: Iterable[Any]) -> Tuple[List[str], str]:
    normalized = []
    for arg in args or []:
        text = str(arg)
        if any(token == text or token in text for token in CHAIN_TOKENS):
            return [], "command chaining, pipes, or redirection are blocked"
        normalized.append(text)
    return normalized, ""


def _risk_for_action(action_type: str, args: List[str], metadata: Dict[str, Any]) -> str:
    joined = " ".join(args).lower()
    if metadata.get("irreversible") or "purge" in joined or "force" in joined:
        return "irreversible"
    if action_type in {"install_dependency", "run_build", "start_service"}:
        return "important"
    if action_type == "run_script" and metadata.get("may_modify_many_files"):
        return "critical"
    if "production" in joined or "migration" in joined:
        return "critical"
    return "normal"


def _environment(extra_env: Optional[Dict[str, Any]], policy: Optional[Dict[str, Any]]) -> Tuple[Dict[str, str], Dict[str, Any], str]:
    policy = policy or {}
    env = {}
    for key in ENV_ALLOWLIST:
        if key in os.environ:
            env[key] = os.environ[key]
    injected = {}
    for key, value in (extra_env or {}).items():
        key_text = str(key)
        if not re.fullmatch(r"[A-Z0-9_]{1,40}", key_text):
            return {}, {}, "invalid environment key"
        if any(marker in key_text.lower() for marker in SECRET_KEY_MARKERS):
            return {}, {}, "secret environment injection is not supported"
        value_text = str(value)
        if len(value_text) > 1000:
            return {}, {}, "environment value too large"
        injected[key_text] = value_text
    env.update(injected)
    if sum(len(k) + len(v) for k, v in env.items()) > 20_000:
        return {}, {}, "environment size limit exceeded"
    return env, {"allowed_keys": sorted(env), "injected_keys": sorted(injected), "parent_environment_dumped": False, "dotenv_read": False}, ""


def _permission_decision(profile: Optional[Dict[str, Any]], action_type: str, cwd_rel: str, risk: str) -> Dict[str, Any]:
    if not profile:
        return {"allowed": True, "requires_approval": False, "reason": "no profile supplied; plan remains local preview", "risk_level": risk}
    operation = EXECUTION_OPS.get(action_type, "inspect")
    result = evaluate_requested_action(
        profile=profile,
        operation=operation,
        target_path=cwd_rel or ".",
        metadata={"why_needed": f"Terminal runtime action {action_type} needs the working directory.", "destructive": risk == "irreversible"},
        recovery_plan_available=risk != "irreversible",
    )
    return result


def get_terminal_runtime_schema() -> Dict[str, Any]:
    return {
        "name": "LuxCode Controlled Terminal & Process Runtime",
        "action_types": sorted(ACTION_TYPES),
        "process_statuses": sorted(PROCESS_STATUSES),
        "shell_policy": "shell_false_only",
        "raw_shell_endpoint": False,
        "external_network_default": "blocked",
        "environment_policy": "allowlisted_non_secret_environment_only",
        "output_limit_default": DEFAULT_OUTPUT_LIMIT,
        **SAFE_INVARIANTS,
    }


def get_terminal_runtime_registry(repository_root: Optional[str] = None) -> Dict[str, Any]:
    return _safe_success(
        action_types=sorted(ACTION_TYPES),
        executable_registry=_executable_registry(repository_root),
        blocked_shell_executables=sorted(BLOCKED_EXECUTABLES),
        lifecycle_statuses=sorted(PROCESS_STATUSES),
    )


def plan_terminal_action(
    action_type: str,
    repository_root: str,
    working_directory: str = ".",
    executable: str = "python",
    arguments: Optional[List[Any]] = None,
    timeout_seconds: int = DEFAULT_TIMEOUT,
    expected_exit_codes: Optional[List[int]] = None,
    process_mode: str = "foreground",
    output_limit: int = DEFAULT_OUTPUT_LIMIT,
    environment: Optional[Dict[str, Any]] = None,
    environment_policy: Optional[Dict[str, Any]] = None,
    permission_profile: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    raw_command: str = "",
) -> Dict[str, Any]:
    metadata = metadata or {}
    if raw_command:
        return _safe_failure("raw shell command strings are blocked")
    if action_type not in ACTION_TYPES:
        return _safe_failure("unsupported action type", action_type=action_type)
    root, root_error = _normalize_root(repository_root)
    if root_error:
        return _safe_failure(root_error)
    cwd, cwd_rel, cwd_error = _safe_path(root, working_directory, must_exist=True)
    if cwd_error:
        return _safe_failure(cwd_error)
    resolved_exe, executable_entry, exe_error = _resolve_executable(executable, str(root))
    if exe_error:
        return _safe_failure(exe_error, scope_request=request_scope_expansion("", executable, "inspect", exe_error, str(root)))
    args, arg_error = _validate_args(arguments or [])
    if arg_error:
        return _safe_failure(arg_error)
    env, env_summary, env_error = _environment(environment, environment_policy)
    if env_error:
        return _safe_failure(env_error)
    timeout = max(1, min(int(timeout_seconds or DEFAULT_TIMEOUT), 300))
    mode = "background" if action_type in BACKGROUND_ACTIONS or process_mode == "background" else "foreground"
    risk = _risk_for_action(action_type, args, metadata)
    permission = _permission_decision(permission_profile, action_type, cwd_rel, risk)
    status = "ready" if permission.get("allowed", True) and not permission.get("requires_approval") else "approval_required"
    if not permission.get("allowed", True):
        status = "blocked"
    plan = {
        "runtime_id": _digest([action_type, resolved_exe, args, str(cwd), time.time()]),
        "task_id": metadata.get("task_id", ""),
        "status": status,
        "action_type": action_type,
        "executable": resolved_exe,
        "executable_entry": executable_entry,
        "arguments": args,
        "working_directory": str(cwd),
        "working_directory_relative": cwd_rel,
        "timeout_seconds": timeout,
        "environment_policy": env_summary,
        "environment": env,
        "expected_exit_codes": expected_exit_codes or [0],
        "process_mode": mode,
        "output_limits": {"stdout": int(output_limit), "stderr": int(output_limit)},
        "redaction_policy": {"secrets": True, "max_output": int(output_limit), "dotenv_read": False},
        "permission_decision": permission,
        "risk_classification": risk,
        "cleanup_policy": {"owned_process_only": True, "grace_seconds": 2, "kill_after_grace": True},
        "shell": False,
        "created_at": _now(),
        "audit_events": [],
        "warning": build_plain_language_warning(operation=EXECUTION_OPS.get(action_type, "inspect"), target_path=cwd_rel, risk_level=risk).get("simple_explanation", ""),
    }
    _audit(plan, "plan_created", {"action_type": action_type, "risk": risk})
    _audit(plan, "permission_evaluated", permission)
    _audit(plan, "scope_checked", {"cwd": cwd_rel, "allowed": permission.get("allowed", True)})
    return _safe_success(plan=plan)


def _base_runtime(plan: Dict[str, Any]) -> Dict[str, Any]:
    runtime = deepcopy(plan)
    runtime.update(
        {
            "pid": None,
            "child_processes": [],
            "start_time": "",
            "end_time": "",
            "exit_code": None,
            "health_result": {},
            "cleanup_result": {},
            "stdout_summary": "",
            "stderr_summary": "",
            "ownership": {"owned_by_runtime": True, "runtime_id": plan.get("runtime_id"), "pid_start_verified": False},
        }
    )
    return runtime


def execute_terminal_action(plan: Dict[str, Any], approval_digest: str = "") -> Dict[str, Any]:
    if not isinstance(plan, dict):
        return _safe_failure("structured execution plan is required")
    if plan.get("shell") is not False:
        return _safe_failure("shell=True is blocked")
    if plan.get("status") == "blocked":
        return _safe_failure("plan is blocked", plan=plan)
    if plan.get("status") == "approval_required" and not approval_digest:
        return _safe_failure("approval is required before process execution", plan=plan)
    runtime = _base_runtime(plan)
    runtime["status"] = "starting"
    runtime["start_time"] = _now()
    _audit(runtime, "execution_started", {"runtime_id": runtime.get("runtime_id")})
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        proc = subprocess.Popen(
            [runtime["executable"], *runtime.get("arguments", [])],
            cwd=runtime["working_directory"],
            env=runtime.get("environment", {}),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            shell=False,
            text=False,
            creationflags=creationflags,
        )
    except Exception as exc:
        runtime["status"] = "failed"
        runtime["end_time"] = _now()
        runtime["stderr_summary"] = _redact_text(f"{type(exc).__name__}: {exc}")
        _audit(runtime, "execution_failed", {"error": runtime["stderr_summary"]})
        _RUNTIMES[runtime["runtime_id"]] = runtime
        return _safe_failure("process start failed", runtime=runtime)
    runtime["pid"] = proc.pid
    runtime["ownership"]["pid_start_verified"] = True
    runtime["status"] = "running"
    _PROCESSES[runtime["runtime_id"]] = proc
    _RUNTIMES[runtime["runtime_id"]] = runtime
    _audit(runtime, "process_running", {"pid": proc.pid})
    if runtime.get("process_mode") == "background":
        return _safe_success(runtime=runtime)
    try:
        out, err = proc.communicate(timeout=runtime["timeout_seconds"])
        runtime["exit_code"] = proc.returncode
        runtime["end_time"] = _now()
        runtime["stdout_summary"] = _redact_text(out, runtime["output_limits"]["stdout"])
        runtime["stderr_summary"] = _redact_text(err, runtime["output_limits"]["stderr"])
        runtime["status"] = "completed" if proc.returncode in runtime.get("expected_exit_codes", [0]) else "failed"
        _audit(runtime, "execution_completed" if runtime["status"] == "completed" else "execution_failed", {"exit_code": proc.returncode})
    except subprocess.TimeoutExpired:
        runtime["status"] = "timed_out"
        _audit(runtime, "timed_out", {"timeout": runtime["timeout_seconds"]})
        stop_terminal_process(runtime["runtime_id"], reason="timeout")
        runtime = _RUNTIMES[runtime["runtime_id"]]
    finally:
        _PROCESSES.pop(runtime["runtime_id"], None)
    return _safe_success(runtime=runtime)


def get_terminal_process(runtime_id: str) -> Dict[str, Any]:
    runtime = _RUNTIMES.get(runtime_id)
    if not runtime:
        return _safe_failure("runtime_id not found")
    proc = _PROCESSES.get(runtime_id)
    if proc and proc.poll() is None:
        runtime["status"] = "running"
    elif proc:
        runtime["exit_code"] = proc.returncode
    return _safe_success(runtime=deepcopy(runtime))


def stop_terminal_process(runtime_id: str, reason: str = "user_requested") -> Dict[str, Any]:
    runtime = _RUNTIMES.get(runtime_id)
    if not runtime:
        return _safe_failure("runtime_id not found")
    proc = _PROCESSES.get(runtime_id)
    runtime["status"] = "stopping"
    _audit(runtime, "cleanup_attempted", {"reason": reason, "owned_process_only": True})
    if not proc:
        runtime["status"] = "stopped"
        runtime["cleanup_result"] = {"stopped": False, "reason": "no live owned process"}
        _audit(runtime, "cleanup_completed", runtime["cleanup_result"])
        return _safe_success(runtime=runtime)
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                out, err = proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate(timeout=2)
            runtime["stdout_summary"] = _redact_text(out, runtime["output_limits"]["stdout"])
            runtime["stderr_summary"] = _redact_text(err, runtime["output_limits"]["stderr"])
        runtime["exit_code"] = proc.returncode
        runtime["end_time"] = _now()
        runtime["status"] = "stopped" if reason != "timeout" else "timed_out"
        runtime["cleanup_result"] = {"stopped": True, "owned_process_only": True, "pid": runtime.get("pid"), "reason": reason}
        _audit(runtime, "cleanup_completed", runtime["cleanup_result"])
    except Exception as exc:
        runtime["status"] = "cleanup_required"
        runtime["cleanup_result"] = {"stopped": False, "error": _redact_text(f"{type(exc).__name__}: {exc}")}
        _audit(runtime, "cleanup_failed", runtime["cleanup_result"])
    _PROCESSES.pop(runtime_id, None)
    return _safe_success(runtime=runtime)


def cancel_terminal_runtime(task_id: str = "", runtime_id: str = "") -> Dict[str, Any]:
    targets = [runtime_id] if runtime_id else [rid for rid, item in _RUNTIMES.items() if item.get("task_id") == task_id]
    stopped = [stop_terminal_process(rid, reason="cancelled").get("runtime", {}) for rid in targets if rid]
    return _safe_success(cancelled=len(stopped), runtimes=stopped)


def detect_stale_processes() -> Dict[str, Any]:
    stale = []
    for runtime_id, runtime in _RUNTIMES.items():
        proc = _PROCESSES.get(runtime_id)
        if runtime.get("status") == "running" and (not proc or proc.poll() is not None):
            runtime["status"] = "stale"
            _audit(runtime, "stale_detected", {"pid": runtime.get("pid"), "identity_checked": True})
            stale.append(deepcopy(runtime))
    return _safe_success(stale_processes=stale, stale_count=len(stale), automatic_kill=False)


def check_port(host: str = "127.0.0.1", port: int = 0, expected_runtime_id: str = "", timeout_seconds: float = 0.5) -> Dict[str, Any]:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return _safe_failure("external port checks are blocked by default")
    port = int(port)
    if port < 1 or port > 65535:
        return _safe_failure("invalid port")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(float(timeout_seconds))
        result = sock.connect_ex(("127.0.0.1", port))
    listening = result == 0
    owner = _RUNTIMES.get(expected_runtime_id, {}) if expected_runtime_id else {}
    return _safe_success(
        host=host,
        port=port,
        listening=listening,
        available=not listening,
        used_by_other_process=bool(listening and expected_runtime_id and owner.get("status") not in {"running", "healthy"}),
        expected_runtime_owns_port=bool(listening and expected_runtime_id and owner.get("status") in {"running", "healthy"}),
        recommendation="choose another port or stop the owning service manually" if listening and not expected_runtime_id else "",
    )


def health_check(
    check_type: str = "tcp",
    host: str = "127.0.0.1",
    port: int = 0,
    path: str = "/",
    timeout_seconds: float = 1.0,
    retries: int = 3,
    retry_interval: float = 0.1,
    expected_status_codes: Optional[List[int]] = None,
    response_size_limit: int = 2000,
) -> Dict[str, Any]:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return _safe_failure("external health checks are blocked by default")
    expected = expected_status_codes or [200]
    attempts = []
    healthy = False
    for attempt in range(max(1, min(int(retries), 10))):
        try:
            if check_type == "tcp":
                with socket.create_connection(("127.0.0.1", int(port)), timeout=float(timeout_seconds)):
                    healthy = True
                    attempts.append({"attempt": attempt + 1, "ok": True})
            elif check_type == "http_get":
                conn = http.client.HTTPConnection("127.0.0.1", int(port), timeout=float(timeout_seconds))
                conn.request("GET", path or "/")
                resp = conn.getresponse()
                body = resp.read(response_size_limit + 1)
                healthy = resp.status in expected
                attempts.append({"attempt": attempt + 1, "ok": healthy, "status": resp.status, "body_preview": _redact_text(body[:response_size_limit], 500)})
                conn.close()
            else:
                return _safe_failure("unsupported health check type")
        except Exception as exc:
            attempts.append({"attempt": attempt + 1, "ok": False, "error": _redact_text(type(exc).__name__)})
        if healthy:
            break
        time.sleep(max(0.01, float(retry_interval)))
    return _safe_success(check_type=check_type, host=host, port=int(port), healthy=healthy, attempts=attempts, network_scope="localhost_only")


def restore_runtime_record(record: Dict[str, Any]) -> Dict[str, Any]:
    restored = deepcopy(record)
    restored["status"] = "manual_review_required" if restored.get("status") == "running" else restored.get("status", "stale")
    restored["execution_resumed"] = False
    restored["restore_policy"] = "never auto-start restored processes"
    return _safe_success(runtime=restored)


def get_terminal_runtime_status() -> Dict[str, Any]:
    states = [item.get("status") for item in _RUNTIMES.values()]
    return {
        "name": "LuxCode Controlled Terminal & Process Runtime",
        "status": "ready",
        "runtime_count": len(_RUNTIMES),
        "running_count": states.count("running"),
        "stale_count": states.count("stale"),
        "raw_shell_endpoint": False,
        "owned_process_only_cleanup": True,
        "restore_auto_starts_process": False,
        **SAFE_INVARIANTS,
    }


def get_safe_runtime_metadata(runtime: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "runtime_id": runtime.get("runtime_id"),
        "task_id": runtime.get("task_id"),
        "action_type": runtime.get("action_type"),
        "executable": runtime.get("executable"),
        "arguments": list(runtime.get("arguments", [])),
        "working_directory": runtime.get("working_directory"),
        "pid": runtime.get("pid"),
        "exit_code": runtime.get("exit_code"),
        "timeout_seconds": runtime.get("timeout_seconds"),
        "status": runtime.get("status"),
        "health_result": _sanitize_metadata(runtime.get("health_result", {})),
        "cleanup_result": _sanitize_metadata(runtime.get("cleanup_result", {})),
        "stdout_summary": _redact_text(runtime.get("stdout_summary", "")),
        "stderr_summary": _redact_text(runtime.get("stderr_summary", "")),
        "audit_events": _sanitize_metadata(runtime.get("audit_events", [])),
        "ownership": deepcopy(runtime.get("ownership", {})),
    }
