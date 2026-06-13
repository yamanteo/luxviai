from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SUPPORTED_MODES = {"plan", "dry_run", "execute", "analyze", "recovery_preview", "rollback_recommendation"}
DEFAULT_MODE = "plan"
ALLOWED_CHECK_TYPES = {
    "py_compile",
    "import_check",
    "endpoint_presence",
    "schema_check",
    "targeted_smoke",
    "segmented_smoke",
    "quick_smoke",
    "validator_script",
    "fallback_check",
    "git_diff_check",
    "manual_ui_required",
}
BLOCKED_CHECK_TYPES = {
    "arbitrary_command",
    "raw_shell",
    "powershell",
    "cmd",
    "bash",
    "package_installation",
    "network_request",
    "deployment",
    "git_commit",
    "git_push",
    "git_reset",
    "git_clean",
    "file_deletion",
}
TEXT_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".md", ".txt", ".json", ".yaml", ".yml", ".toml"}
EXCLUDED_DIRS = {".git", ".hg", ".svn", ".env", ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache", "node_modules", "dist", "build", "coverage", "htmlcov", "logs", "log"}
EXCLUDED_NAMES = {".env", ".env.local", ".env.production", ".env.development"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".sqlite", ".sqlite3", ".db", ".dump", ".cache", ".pem", ".key", ".crt", ".p12", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll"}
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,120}$")
LAYER_RE = re.compile(r"^\d{1,2}(?:-\d{1,2})?(?:,\d{1,2}(?:-\d{1,2})?)*$")
MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
INJECTION_RE = re.compile(r"[|;&`$<>\"'\n\r]")
OUTPUT_LIMIT = 6000
VALID_RECOVERY_DECISIONS = {
    "no_recovery_needed",
    "retry_targeted_check",
    "generate_patch_revision",
    "human_review_required",
    "rollback_recommended",
    "automatic_rollback_allowed",
    "recovery_blocked",
}


def _mode(mode: Optional[str]) -> str:
    candidate = (mode or DEFAULT_MODE).strip()
    return candidate if candidate in SUPPORTED_MODES else DEFAULT_MODE


def _stable_json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _stable_id(prefix: str, *parts: Any) -> str:
    return prefix + hashlib.sha256("\n".join(_stable_json(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _unique(items: Iterable[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def _normalize_root(repository_root: Optional[str]) -> Tuple[Optional[Path], List[str]]:
    raw = (repository_root or os.getcwd()).strip() or os.getcwd()
    try:
        root = Path(raw).expanduser().resolve()
    except OSError as exc:
        return None, [f"repository root could not be resolved: {type(exc).__name__}"]
    if not root.exists() or not root.is_dir():
        return None, [f"repository root is not an existing directory: {raw}"]
    return root, []


def _is_excluded(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return bool(parts & EXCLUDED_DIRS) or path.name.lower() in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES


def _safe_rel_path(root: Path, raw: Any, *, must_exist: bool = True, python_only: bool = False) -> Tuple[Optional[str], Optional[str]]:
    text = str(raw or "").strip().strip("\"'")
    if not text or "\x00" in text:
        return None, "empty or invalid path"
    if INJECTION_RE.search(text) or "*" in text or "?" in text:
        return None, f"unsafe path token rejected: {text}"
    candidate = Path(text)
    if any(part == ".." for part in candidate.parts):
        return None, f"traversal rejected: {text}"
    try:
        resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    except OSError:
        return None, f"path could not be resolved: {text}"
    try:
        rel = resolved.relative_to(root).as_posix()
    except ValueError:
        return None, f"path outside repository rejected: {text}"
    if resolved.is_symlink():
        return None, f"symlink path rejected: {text}"
    if _is_excluded(resolved):
        return None, f"excluded path rejected: {text}"
    if resolved.suffix.lower() not in TEXT_SUFFIXES:
        return None, f"unsupported file type rejected: {text}"
    if python_only and resolved.suffix.lower() != ".py":
        return None, f"python file required: {text}"
    if must_exist and (not resolved.exists() or not resolved.is_file()):
        return None, f"file not found: {text}"
    return rel, None


def _safe_identifier(value: Any, label: str) -> Tuple[Optional[str], Optional[str]]:
    text = str(value or "").strip()
    if not text or not SAFE_ID_RE.match(text) or INJECTION_RE.search(text):
        return None, f"invalid {label}: {text}"
    return text, None


def _redact(text: str) -> str:
    redacted = text or ""
    patterns = [
        re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s]+"),
        re.compile(r"\b[A-Za-z0-9_\-]{24,}\.[A-Za-z0-9_\-]{12,}\.[A-Za-z0-9_\-]{12,}\b"),
        re.compile(r"\b(sk-|pk-)[A-Za-z0-9_\-]{12,}\b", re.I),
    ]
    for pattern in patterns:
        redacted = pattern.sub(lambda m: m.group(0).split("=")[0].split(":")[0] + "=<redacted>", redacted)
    redacted = re.sub(r"(?im)^.*\.env.*$", "<redacted env path line>", redacted)
    return redacted


def _truncate(text: str) -> Tuple[str, bool]:
    redacted = _redact(text)
    if len(redacted) <= OUTPUT_LIMIT:
        return redacted, False
    return redacted[:OUTPUT_LIMIT] + "\n<truncated>", True


def _digest(root: Path, verification_id: str, planned: List[Dict[str, Any]], timeout_seconds: int, max_checks: int) -> str:
    payload = {
        "verification_id": verification_id,
        "repository_root": str(root),
        "planned_checks": [
            {key: item.get(key) for key in ("check_id", "check_type", "args", "affected_files", "manual")}
            for item in planned
        ],
        "timeout_seconds": timeout_seconds,
        "max_checks": max_checks,
    }
    return "lux-verify-" + hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _base_result(mode: str, verification_id: str, root: Optional[Path]) -> Dict[str, Any]:
    return {
        "request_id": _stable_id("luxverify-", mode, verification_id, str(root or "")),
        "mode": mode,
        "verification_id": verification_id,
        "repository_root": str(root or ""),
        "planned_checks": [],
        "verification_digest": "",
        "approval_valid": False,
        "execution_allowed": False,
        "check_results": [],
        "summary": {"passed": 0, "failed": 0, "timed_out": 0, "blocked": 0, "manual_required": 0},
        "failure_analysis": [],
        "recovery_decision": "recovery_blocked",
        "rollback_request": {},
        "safe_next_step": "Prepare an allowlisted verification run before execution.",
        "arbitrary_command_blocked": True,
        "network_access_used": False,
        "external_api_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def _planned_result(check: Dict[str, Any], status: str = "planned", reason: str = "") -> Dict[str, Any]:
    return {
        "check_id": check.get("check_id", ""),
        "check_type": check.get("check_type", ""),
        "command_preview": check.get("command_preview", ""),
        "started_at": "",
        "duration_ms": 0,
        "exit_code": None,
        "status": status,
        "stdout_excerpt": "",
        "stderr_excerpt": reason,
        "timed_out": False,
        "output_truncated": False,
        "affected_files": check.get("affected_files", []),
        "failure_category": "unknown_failure" if status == "blocked" else "",
        "retry_safe": status in {"blocked", "timed_out"},
        "rollback_recommended": False,
    }


def _classify_failure(check_type: str, exit_code: Optional[int], stdout: str, stderr: str, timed_out: bool) -> str:
    text = f"{stdout}\n{stderr}".lower()
    if timed_out:
        return "timeout"
    if "syntaxerror" in text:
        return "syntax_error"
    if "modulenotfounderror" in text or "importerror" in text:
        return "import_error"
    if check_type == "endpoint_presence" and exit_code:
        return "endpoint_missing"
    if check_type == "schema_check" and exit_code:
        return "schema_mismatch"
    if check_type == "validator_script" and exit_code:
        return "validator_failure"
    if "no module named" in text:
        return "dependency_missing"
    if "environment" in text or "not found" in text:
        return "environment_missing"
    if "smoke" in check_type or check_type in {"targeted_smoke", "segmented_smoke", "quick_smoke"}:
        return "smoke_failure"
    return "unknown_failure"


def _empty_env() -> Dict[str, str]:
    keep = {}
    for key in ("SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "COMSPEC", "TEMP", "TMP", "PYTHONPATH"):
        if os.environ.get(key):
            keep[key] = os.environ[key]
    keep["PYTHONIOENCODING"] = "utf-8"
    return keep


def _manual_check(check_id: str) -> Dict[str, Any]:
    return {
        "check_id": check_id,
        "check_type": "manual_ui_required",
        "args": [],
        "command_preview": "manual UI validation required",
        "affected_files": [],
        "manual": True,
    }


def _build_check(root: Path, raw: Dict[str, Any], index: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    check_type = str(raw.get("check_type") or raw.get("type") or "").strip()
    check_id = str(raw.get("check_id") or f"{check_type}_{index}").strip()
    if check_type in BLOCKED_CHECK_TYPES or check_type not in ALLOWED_CHECK_TYPES:
        return None, f"unknown or blocked check type: {check_type}"
    safe_id, err = _safe_identifier(check_id, "check_id")
    if err:
        return None, err
    if check_type == "manual_ui_required":
        return _manual_check(safe_id), None
    if check_type == "py_compile":
        files = raw.get("files") or raw.get("affected_files") or []
        safe_files: List[str] = []
        for item in files:
            rel, reason = _safe_rel_path(root, item, python_only=True)
            if reason:
                return None, reason
            safe_files.append(rel or "")
        if not safe_files:
            return None, "py_compile requires at least one Python file"
        args = [sys.executable, "-m", "py_compile", *safe_files]
    elif check_type == "import_check":
        module = str(raw.get("module") or "").strip()
        if not MODULE_RE.match(module) or INJECTION_RE.search(module):
            return None, f"invalid import module: {module}"
        args = [sys.executable, "-c", f"import importlib, sys; sys.path.insert(0, {str(root)!r}); importlib.import_module({module!r})"]
        safe_files = []
    elif check_type in {"endpoint_presence", "schema_check", "fallback_check"}:
        script = "import app; assert getattr(app, 'app', None) is not None"
        if raw.get("endpoint"):
            endpoint = str(raw["endpoint"])
            if INJECTION_RE.search(endpoint) or not endpoint.startswith("/"):
                return None, f"invalid endpoint: {endpoint}"
            script += f"; assert any(getattr(r, 'path', '') == {endpoint!r} for r in app.app.routes)"
        args = [sys.executable, "-c", script]
        safe_files = ["app.py"]
    elif check_type == "targeted_smoke":
        check_name, err = _safe_identifier(raw.get("check"), "targeted smoke check")
        if err:
            return None, err
        args = [sys.executable, "scripts/smoke_check.py", "--check", check_name]
        safe_files = ["scripts/smoke_check.py"]
    elif check_type == "segmented_smoke":
        layers = str(raw.get("layers") or "").strip()
        if not LAYER_RE.match(layers) or INJECTION_RE.search(layers):
            return None, f"invalid layer range: {layers}"
        args = [sys.executable, "scripts/smoke_check.py", "--layers", layers]
        safe_files = ["scripts/smoke_check.py"]
    elif check_type == "quick_smoke":
        args = [sys.executable, "scripts/smoke_check.py", "--quick"]
        safe_files = ["scripts/smoke_check.py"]
    elif check_type == "validator_script":
        rel, reason = _safe_rel_path(root, raw.get("script"), python_only=True)
        if reason:
            return None, reason
        if not rel.startswith("scripts/") or not Path(rel).name.startswith("validate_"):
            return None, "validator script must be under scripts/ and match validate_*.py"
        args = [sys.executable, rel]
        safe_files = [rel]
    elif check_type == "git_diff_check":
        args = ["git", "diff", "--check"]
        safe_files = []
    else:
        return None, f"unsupported check type: {check_type}"
    preview = " ".join(args)
    return {
        "check_id": safe_id,
        "check_type": check_type,
        "args": args,
        "command_preview": preview,
        "affected_files": _unique(raw.get("affected_files") or safe_files),
        "manual": False,
    }, None


def _plan(
    repository_root: Optional[str],
    verification_id: Optional[str],
    requested_checks: Optional[List[Dict[str, Any]]],
    max_checks: Any,
    timeout_seconds: Any,
) -> Dict[str, Any]:
    root, root_errors = _normalize_root(repository_root)
    vid = str(verification_id or "").strip()
    result = _base_result(DEFAULT_MODE, vid, root)
    if root is None:
        result["check_results"] = [_planned_result({"check_id": "root", "check_type": "repository"}, "blocked", "; ".join(root_errors))]
        result["summary"]["blocked"] = 1
        return result
    if not vid or not SAFE_ID_RE.match(vid):
        result["check_results"].append(_planned_result({"check_id": "verification_id", "check_type": "input"}, "blocked", "verification_id is required"))
    checks = list(requested_checks or [])
    max_count = max(1, min(int(max_checks or 8), 20))
    timeout = max(1, min(int(timeout_seconds or 30), 120))
    if len(checks) > max_count:
        result["check_results"].append(_planned_result({"check_id": "max_checks", "check_type": "input"}, "blocked", f"requested check count exceeds max_checks {max_count}"))
        checks = checks[:max_count]
    planned: List[Dict[str, Any]] = []
    for idx, raw in enumerate(checks, start=1):
        if not isinstance(raw, dict):
            result["check_results"].append(_planned_result({"check_id": f"check_{idx}", "check_type": "input"}, "blocked", "check must be structured"))
            continue
        check, reason = _build_check(root, raw, idx)
        if reason:
            result["check_results"].append(_planned_result({"check_id": raw.get("check_id", f"check_{idx}"), "check_type": raw.get("check_type", "")}, "blocked", reason))
            continue
        planned.append(check or {})
    result["planned_checks"] = planned
    result["verification_digest"] = _digest(root, vid, planned, timeout, max_count) if vid else ""
    result["summary"]["blocked"] = sum(1 for item in result["check_results"] if item["status"] == "blocked")
    result["summary"]["manual_required"] = sum(1 for item in planned if item.get("manual"))
    result["safe_next_step"] = "Review planned checks and submit the verification_digest as approval_token for execute mode."
    return result


def prepare_verification_run(
    repository_root: Optional[str] = None,
    verification_id: Optional[str] = None,
    changed_files: Optional[List[str]] = None,
    requested_checks: Optional[List[Dict[str, Any]]] = None,
    approval_token: Optional[str] = None,
    expected_repository_state: Optional[Dict[str, Any]] = None,
    max_checks: Any = 8,
    timeout_seconds: Any = 30,
    mode: Optional[str] = None,
    rollback_id: Optional[str] = None,
    allow_automatic_rollback: bool = False,
    controlled_apply_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result = _plan(repository_root, verification_id, requested_checks, max_checks, timeout_seconds)
    result["mode"] = _mode(mode)
    if result["mode"] == "execute":
        result["mode"] = "dry_run"
    result["execution_allowed"] = False
    return result


def _run_check(root: Path, check: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    if check.get("manual"):
        item = _planned_result(check, "manual_required", "manual validation required")
        item["failure_category"] = ""
        return item
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()
    timed_out = False
    exit_code: Optional[int] = None
    stdout = ""
    stderr = ""
    try:
        proc = subprocess.run(
            check["args"],
            cwd=str(root),
            env=_empty_env(),
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        stderr += "\nverification timed out"
    duration_ms = int((time.perf_counter() - t0) * 1000)
    out_excerpt, out_trunc = _truncate(stdout)
    err_excerpt, err_trunc = _truncate(stderr)
    status = "timed_out" if timed_out else "passed" if exit_code == 0 else "failed"
    category = "" if status == "passed" else _classify_failure(check["check_type"], exit_code, stdout, stderr, timed_out)
    return {
        "check_id": check["check_id"],
        "check_type": check["check_type"],
        "command_preview": check["command_preview"],
        "started_at": started,
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "status": status,
        "stdout_excerpt": out_excerpt,
        "stderr_excerpt": err_excerpt,
        "timed_out": timed_out,
        "output_truncated": out_trunc or err_trunc,
        "affected_files": check.get("affected_files", []),
        "failure_category": category,
        "retry_safe": status == "timed_out" or category in {"environment_missing", "dependency_missing"},
        "rollback_recommended": category in {"syntax_error", "import_error", "smoke_failure", "validator_failure"},
    }


def _summarize(results: List[Dict[str, Any]]) -> Dict[str, int]:
    return {
        "passed": sum(1 for item in results if item["status"] == "passed"),
        "failed": sum(1 for item in results if item["status"] == "failed"),
        "timed_out": sum(1 for item in results if item["status"] == "timed_out"),
        "blocked": sum(1 for item in results if item["status"] == "blocked"),
        "manual_required": sum(1 for item in results if item["status"] == "manual_required"),
    }


def analyze_verification_results(
    repository_root: Optional[str] = None,
    verification_id: Optional[str] = None,
    changed_files: Optional[List[str]] = None,
    requested_checks: Optional[List[Dict[str, Any]]] = None,
    approval_token: Optional[str] = None,
    expected_repository_state: Optional[Dict[str, Any]] = None,
    max_checks: Any = 8,
    timeout_seconds: Any = 30,
    mode: Optional[str] = None,
    rollback_id: Optional[str] = None,
    allow_automatic_rollback: bool = False,
    controlled_apply_result: Optional[Dict[str, Any]] = None,
    check_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    root, _ = _normalize_root(repository_root)
    result = _base_result(_mode(mode), str(verification_id or ""), root)
    results = list(check_results or [])
    result["check_results"] = results
    result["summary"] = _summarize(results)
    failures = [item for item in results if item.get("status") in {"failed", "timed_out", "blocked"}]
    result["failure_analysis"] = [
        {
            "check_id": item.get("check_id"),
            "failure_category": item.get("failure_category") or "unknown_failure",
            "retry_safe": bool(item.get("retry_safe")),
            "rollback_recommended": bool(item.get("rollback_recommended")),
            "affected_files": item.get("affected_files", []),
        }
        for item in failures
    ]
    result.update(_recovery_decision(failures, changed_files or [], rollback_id, allow_automatic_rollback, controlled_apply_result or {}, expected_repository_state or {}))
    return result


def _recovery_decision(
    failures: List[Dict[str, Any]],
    changed_files: List[str],
    rollback_id: Optional[str],
    allow_auto: bool,
    controlled_apply: Dict[str, Any],
    expected_state: Dict[str, Any],
) -> Dict[str, Any]:
    if not failures:
        return {"recovery_decision": "no_recovery_needed", "rollback_request": {}, "safe_next_step": "No recovery needed."}
    if any(item.get("status") == "timed_out" for item in failures):
        return {"recovery_decision": "retry_targeted_check", "rollback_request": {}, "safe_next_step": "Retry only timed-out targeted checks."}
    severe = any(item.get("rollback_recommended") for item in failures)
    failure_files = {file for item in failures for file in item.get("affected_files", [])}
    changed_set = set(changed_files or controlled_apply.get("files_changed", []))
    unrelated = bool(failure_files and changed_set and not failure_files <= changed_set)
    if severe:
        can_auto = (
            allow_auto
            and bool(controlled_apply.get("rollback_available"))
            and bool(rollback_id or controlled_apply.get("rollback_id"))
            and not unrelated
            and bool(expected_state.get("current_hashes_match_post_apply", True))
        )
        if can_auto:
            rid = rollback_id or controlled_apply.get("rollback_id")
            return {
                "recovery_decision": "automatic_rollback_allowed",
                "rollback_request": {
                    "rollback_id": rid,
                    "patch_id": controlled_apply.get("patch_id", ""),
                    "mode": "rollback_preview",
                    "approval_required": True,
                },
                "safe_next_step": "Submit rollback request to Controlled Apply Engine after explicit approval.",
            }
        return {
            "recovery_decision": "rollback_recommended",
            "rollback_request": {"rollback_id": rollback_id or controlled_apply.get("rollback_id", ""), "mode": "rollback_preview"},
            "safe_next_step": "Review rollback recommendation; automatic rollback is not permitted.",
        }
    if any(item.get("failure_category") in {"syntax_error", "import_error", "schema_mismatch"} for item in failures):
        return {"recovery_decision": "generate_patch_revision", "rollback_request": {}, "safe_next_step": "Generate a targeted patch revision."}
    return {"recovery_decision": "human_review_required", "rollback_request": {}, "safe_next_step": "Review failures before retrying."}


def execute_verification_run(
    repository_root: Optional[str] = None,
    verification_id: Optional[str] = None,
    changed_files: Optional[List[str]] = None,
    requested_checks: Optional[List[Dict[str, Any]]] = None,
    approval_token: Optional[str] = None,
    expected_repository_state: Optional[Dict[str, Any]] = None,
    max_checks: Any = 8,
    timeout_seconds: Any = 30,
    mode: Optional[str] = None,
    rollback_id: Optional[str] = None,
    allow_automatic_rollback: bool = False,
    controlled_apply_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized = _mode(mode)
    prepared = prepare_verification_run(repository_root, verification_id, changed_files, requested_checks, approval_token, expected_repository_state, max_checks, timeout_seconds, normalized, rollback_id, allow_automatic_rollback, controlled_apply_result)
    if normalized != "execute":
        return prepared
    prepared["mode"] = "execute"
    if prepared["summary"]["blocked"]:
        return prepared
    if not approval_token or approval_token != prepared["verification_digest"]:
        prepared["check_results"].append(_planned_result({"check_id": "approval", "check_type": "approval"}, "blocked", "missing or wrong approval token"))
        prepared["summary"] = _summarize(prepared["check_results"])
        return prepared
    prepared["approval_valid"] = True
    prepared["execution_allowed"] = True
    root = Path(prepared["repository_root"])
    timeout = max(1, min(int(timeout_seconds or 30), 120))
    start = time.perf_counter()
    results: List[Dict[str, Any]] = []
    for check in prepared["planned_checks"]:
        if (time.perf_counter() - start) > timeout * max(1, len(prepared["planned_checks"])):
            results.append(_planned_result(check, "blocked", "global duration budget exceeded"))
            continue
        results.append(_run_check(root, check, timeout))
    prepared["check_results"] = results
    prepared["summary"] = _summarize(results)
    analyzed = analyze_verification_results(repository_root, verification_id, changed_files, requested_checks, approval_token, expected_repository_state, max_checks, timeout_seconds, "analyze", rollback_id, allow_automatic_rollback, controlled_apply_result, results)
    prepared["failure_analysis"] = analyzed["failure_analysis"]
    prepared["recovery_decision"] = analyzed["recovery_decision"]
    prepared["rollback_request"] = analyzed["rollback_request"]
    prepared["safe_next_step"] = analyzed["safe_next_step"]
    return prepared


def prepare_recovery_action(
    repository_root: Optional[str] = None,
    verification_id: Optional[str] = None,
    changed_files: Optional[List[str]] = None,
    requested_checks: Optional[List[Dict[str, Any]]] = None,
    approval_token: Optional[str] = None,
    expected_repository_state: Optional[Dict[str, Any]] = None,
    max_checks: Any = 8,
    timeout_seconds: Any = 30,
    mode: Optional[str] = None,
    rollback_id: Optional[str] = None,
    allow_automatic_rollback: bool = False,
    controlled_apply_result: Optional[Dict[str, Any]] = None,
    check_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return analyze_verification_results(repository_root, verification_id, changed_files, requested_checks, approval_token, expected_repository_state, max_checks, timeout_seconds, mode or "recovery_preview", rollback_id, allow_automatic_rollback, controlled_apply_result, check_results)


def get_verification_recovery_schema() -> Dict[str, Any]:
    return {
        "name": "Local Verification Execution & Recovery Engine",
        "status": "schema_ready",
        "supported_modes": sorted(SUPPORTED_MODES),
        "default_mode": DEFAULT_MODE,
        "allowed_verification_types": sorted(ALLOWED_CHECK_TYPES),
        "blocked_verification_types": sorted(BLOCKED_CHECK_TYPES),
        "arbitrary_command_blocked": True,
        "network_access_used": False,
        "external_api_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }


def get_verification_recovery_status() -> Dict[str, Any]:
    return {
        "name": "Local Verification Execution & Recovery Engine",
        "status": "verification_recovery_ready",
        "default_mode": DEFAULT_MODE,
        "shell_false_enforced": True,
        "raw_command_execution_enabled": False,
        "rollback_execution_enabled": False,
        "available_endpoints": [
            "/lux-verification/schema",
            "/lux-verification/prepare",
            "/lux-verification/execute",
            "/lux-verification/analyze",
            "/lux-verification/recovery-preview",
            "/debug/lux-verification-status",
        ],
        "arbitrary_command_blocked": True,
        "network_access_used": False,
        "external_api_used": False,
        "shell_execution_used": False,
        "local_first": True,
    }
