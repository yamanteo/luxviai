from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from luxcode_minimum_context_builder import build_minimum_context_package
from luxcode_safe_patch_runtime import build_patch_contract, execute_patch_control, preview_patch
from luxcode_zero_cost_execution_router import route_zero_cost_task


EXCLUDED_DIRS = {".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache", ".luxcode_runtime", ".luxcode_snapshots", "luxcode_backups"}
EXCLUDED_FILES = {".env", ".env.local", ".env.production", "luxcode_tasks.db"}
SECRET_RE = re.compile(r"(?i)(api[_-]?key|secret|token|password|credential|authorization)\s*[:=]\s*([^\s]+)")
TEXT_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".md", ".txt", ".yaml", ".yml", ".toml", ".ini", ".css", ".html"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any, prefix: str = "coder") -> str:
    return f"{prefix}-{hashlib.sha256(_stable_json(value).encode('utf-8')).hexdigest()[:24]}"


def _redact(text: str) -> str:
    return SECRET_RE.sub(lambda match: f"{match.group(1)}=<redacted>", str(text or ""))


def _normalize_list(values: Any, limit: int = 80) -> List[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    out: List[str] = []
    seen = set()
    for value in values:
        item = str(value).replace("\\", "/").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def _repo_root(repository_root: Optional[str]) -> Path:
    root = Path(repository_root or ".").expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError("repository_root must be an existing directory")
    return root


def _relative_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _is_excluded(rel: str) -> bool:
    parts = Path(rel).parts
    if any(part in EXCLUDED_DIRS for part in parts):
        return True
    name = parts[-1] if parts else rel
    return name in EXCLUDED_FILES or name.startswith(".env")


def _safe_file(root: Path, rel: str) -> Optional[Path]:
    rel = rel.replace("\\", "/").strip().lstrip("/")
    if not rel or _is_excluded(rel) or ".." in Path(rel).parts:
        return None
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if not path.exists() or not path.is_file():
        return None
    if path.suffix.lower() not in TEXT_EXTENSIONS and path.stat().st_size > 4096:
        return None
    if path.stat().st_size > 250_000:
        return None
    return path


def _read_text(path: Path, limit: int = 160_000) -> str:
    data = path.read_bytes()[:limit]
    if b"\x00" in data:
        return ""
    return data.decode("utf-8", errors="replace")


def _git(root: Path, args: List[str]) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, timeout=10, shell=False)
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _normalize_validation_plan(validation_plan: Any) -> Dict[str, Any]:
    raw_steps = validation_plan.get("steps", []) if isinstance(validation_plan, dict) else validation_plan or []
    steps: List[Dict[str, Any]] = []
    for index, raw in enumerate(raw_steps if isinstance(raw_steps, list) else []):
        if not isinstance(raw, dict):
            continue
        if "command" in raw:
            steps.append(raw)
            continue
        step_type = str(raw.get("type") or "").strip()
        if step_type == "py_compile":
            paths = _normalize_list(raw.get("paths") or raw.get("files"), 30)
            steps.append({"step_id": raw.get("step_id") or f"py-compile-{index + 1}", "command": ["python", "-m", "py_compile", *paths], "timeout_seconds": int(raw.get("timeout_seconds", 30) or 30)})
        elif step_type == "smoke_check_targeted":
            check_name = str(raw.get("check") or raw.get("name") or "").strip()
            steps.append({"step_id": raw.get("step_id") or f"smoke-{index + 1}", "command": ["python", "scripts/smoke_check.py", "--check", check_name], "timeout_seconds": int(raw.get("timeout_seconds", 60) or 60)})
        elif step_type:
            steps.append({"step_id": raw.get("step_id") or f"blocked-{index + 1}", "command": [step_type], "timeout_seconds": 5})
    return {
        "steps": steps,
        "stop_on_failure": bool(validation_plan.get("stop_on_failure", True)) if isinstance(validation_plan, dict) else True,
        "timeout_seconds": int(validation_plan.get("timeout_seconds", 30) or 30) if isinstance(validation_plan, dict) else 30,
    }


def _walk_files(root: Path, limit: int = 500) -> List[str]:
    files: List[str] = []
    for path in root.rglob("*"):
        if len(files) >= limit:
            break
        if not path.is_file():
            continue
        rel = _relative_path(root, path)
        if _safe_file(root, rel):
            files.append(rel)
    return sorted(files)


def get_practical_coder_schema() -> Dict[str, Any]:
    endpoints = [
        "GET /luxcode-coder/schema",
        "GET /luxcode-coder/registry",
        "POST /luxcode-coder/repository-intake",
        "POST /luxcode-coder/search",
        "POST /luxcode-coder/minimum-context",
        "POST /luxcode-coder/task-plan",
        "POST /luxcode-coder/patch-draft",
        "POST /luxcode-coder/patch-control",
        "POST /luxcode-coder/validate",
        "GET /debug/luxcode-coder-status",
    ]
    return {
        "name": "LuxCode Practical Coder Runtime",
        "status": "ready",
        "endpoint_count": len(endpoints),
        "endpoints": endpoints,
        "local_first": True,
        "external_api_used": False,
        "network_access_used": False,
        "arbitrary_shell_used": False,
        "live_repository_patch_allowed": False,
    }


def get_practical_coder_registry() -> Dict[str, Any]:
    return {
        "runtime_id": "luxcode_practical_coder_runtime",
        "capabilities": [
            "safe_repository_intake",
            "targeted_code_search",
            "minimum_context_building",
            "task_plan_generation",
            "patch_contract_drafting",
            "approval_gated_patch_control",
            "allowlisted_validation",
        ],
        "excluded_paths": sorted(EXCLUDED_DIRS | EXCLUDED_FILES),
        "supported_patch_operations": ["replace_text", "insert_before", "insert_after", "create_file"],
        "validation_allowlist": ["py_compile", "smoke_check_targeted"],
        "external_api_used": False,
        "network_access_used": False,
    }


def create_repository_intake(
    repository_root: Optional[str],
    task_summary: str = "",
    requested_files: Optional[List[str]] = None,
    suspected_files: Optional[List[str]] = None,
    max_files: int = 80,
) -> Dict[str, Any]:
    root = _repo_root(repository_root)
    requested = _normalize_list(requested_files, 80)
    suspected = _normalize_list(suspected_files, 80)
    safe_requested = [rel for rel in requested if _safe_file(root, rel)]
    safe_suspected = [rel for rel in suspected if _safe_file(root, rel)]
    file_inventory = sorted(set(safe_requested + safe_suspected + _walk_files(root, max_files)))[:max_files]
    git_status = _git(root, ["status", "--short"])
    intake = {
        "ok": True,
        "intake_id": "",
        "repository_root": str(root),
        "task_summary": _redact(task_summary)[:2000],
        "branch": _git(root, ["branch", "--show-current"]) or "unknown",
        "head": _git(root, ["rev-parse", "HEAD"]) or "",
        "git_status_short": _redact(git_status),
        "repository_dirty": bool(git_status.strip()),
        "requested_files": safe_requested,
        "suspected_files": safe_suspected,
        "file_inventory": file_inventory,
        "excluded_path_count": len(requested) + len(suspected) - len(safe_requested) - len(safe_suspected),
        "created_at": _now(),
        "external_api_used": False,
        "network_access_used": False,
        "local_first": True,
    }
    intake["intake_id"] = _digest(intake, "intake")
    intake["intake_digest"] = _digest(intake, "intake-digest")
    return intake


def targeted_code_search(
    repository_root: Optional[str],
    query: str,
    selected_files: Optional[List[str]] = None,
    max_results: int = 30,
    case_sensitive: bool = False,
) -> Dict[str, Any]:
    root = _repo_root(repository_root)
    needle = str(query or "")
    if not needle:
        return {"ok": False, "error": "query_required", "results": []}
    files = _normalize_list(selected_files, 200) or _walk_files(root, 500)
    results: List[Dict[str, Any]] = []
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(needle), flags)
    for rel in files:
        path = _safe_file(root, rel)
        if not path:
            continue
        text = _read_text(path)
        if not text:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                results.append({"path": rel, "line": line_no, "preview": _redact(line.strip())[:500]})
                if len(results) >= max_results:
                    break
        if len(results) >= max_results:
            break
    return {
        "ok": True,
        "query": _redact(needle),
        "result_count": len(results),
        "results": results,
        "search_digest": _digest({"query": needle, "results": results}, "search"),
        "external_api_used": False,
        "network_access_used": False,
    }


def build_practical_coder_task_plan(
    repository_intake: Dict[str, Any],
    task_summary: str,
    selected_files: Optional[List[str]] = None,
    acceptance_criteria: Optional[List[str]] = None,
) -> Dict[str, Any]:
    selected = _normalize_list(selected_files or repository_intake.get("suspected_files") or repository_intake.get("requested_files"), 30)
    criteria = _normalize_list(acceptance_criteria, 30) or ["py_compile passes", "targeted smoke passes", "no unrelated file changes"]
    route = route_zero_cost_task(
        task_id=repository_intake.get("intake_id", "coder-task"),
        title="Practical coder task",
        description=task_summary,
        required_capabilities=["inspection", "patch_draft", "validation"],
        selected_files=selected,
        risk_level="medium" if len(selected) > 3 else "low",
        user_requires_free_only=True,
    )
    plan = {
        "ok": True,
        "coder_plan_id": "",
        "intake_id": repository_intake.get("intake_id", ""),
        "task_summary": _redact(task_summary)[:2000],
        "selected_files": selected,
        "acceptance_criteria": criteria,
        "steps": [
            {"step": "repository_intake", "state": "complete"},
            {"step": "targeted_search", "state": "planned"},
            {"step": "minimum_context", "state": "planned"},
            {"step": "patch_draft", "state": "planned"},
            {"step": "approval_gated_apply", "state": "requires_approval"},
            {"step": "allowlisted_validation", "state": "planned"},
        ],
        "router_decision": route,
        "live_patch_allowed": False,
        "external_api_used": False,
        "network_access_used": False,
    }
    plan["coder_plan_id"] = _digest(plan, "coder-plan")
    plan["plan_digest"] = _digest(plan, "coder-plan-digest")
    return plan


def draft_practical_patch(
    repository_root: Optional[str],
    task_plan: Dict[str, Any],
    operations: Optional[List[Dict[str, Any]]] = None,
    approved_files: Optional[List[str]] = None,
    protected_files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    ops = operations or []
    contract = build_patch_contract(
        task_id=task_plan.get("coder_plan_id") or task_plan.get("task_id") or "coder-task",
        repository_root=repository_root or "",
        patch_title="Practical coder patch",
        patch_summary=task_plan.get("task_summary", ""),
        target_files=approved_files or task_plan.get("selected_files", []),
        operations=ops,
        allowed_files=approved_files or task_plan.get("selected_files", []),
        protected_files=protected_files or [".env", "luxcode_tasks.db", ".luxcode_runtime"],
        expected_working_tree_clean=False,
    )
    if not contract.get("ok"):
        return contract
    patch_contract = contract.get("patch_contract", contract)
    preview = preview_patch(patch_contract)
    return {
        "ok": True,
        "patch_id": patch_contract.get("patch_id"),
        "patch_contract": patch_contract,
        "approval_token": patch_contract.get("approval_token_hint", ""),
        "preview": preview,
        "requires_approval": True,
        "live_repository_patch_allowed": False,
        "external_api_used": False,
        "network_access_used": False,
    }


def control_practical_patch(
    patch_contract: Dict[str, Any],
    action: str = "preview",
    approval_confirmed: bool = False,
    approval_token: str = "",
    dry_run: bool = True,
    validation_plan: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    normalized_plan = _normalize_validation_plan(validation_plan or [])
    return execute_patch_control(
        patch_contract,
        action=action,
        approval_confirmed=approval_confirmed,
        approval_token=approval_token,
        dry_run=dry_run,
        validation_plan=normalized_plan,
    )


def validate_practical_coder(repository_root: Optional[str], validation_plan: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    from luxcode_safe_patch_runtime import run_validation_plan

    root = _repo_root(repository_root)
    plan = _normalize_validation_plan(validation_plan or [{"type": "py_compile", "paths": ["app.py"]}])
    result = run_validation_plan(str(root), plan)
    return {
        "ok": bool(result.get("passed")),
        "validation_result": result,
        "validation_plan_id": _digest(plan, "validation-plan"),
        "external_api_used": False,
        "network_access_used": False,
    }


def build_coder_final_result(
    repository_intake: Dict[str, Any],
    task_plan: Dict[str, Any],
    patch_result: Dict[str, Any],
    validation_result: Dict[str, Any],
) -> Dict[str, Any]:
    complete = bool(patch_result.get("ok")) and bool(validation_result.get("ok"))
    result = {
        "ok": complete,
        "coder_result_id": "",
        "intake_id": repository_intake.get("intake_id", ""),
        "coder_plan_id": task_plan.get("coder_plan_id", ""),
        "patch_execution_state": patch_result.get("execution_state") or patch_result.get("preview", {}).get("state", "preview"),
        "validation_state": "passed" if validation_result.get("ok") else "failed",
        "remaining_gap": [] if complete else ["manual_review_or_failed_validation"],
        "handoff_ready": not complete,
        "external_api_used": False,
        "network_access_used": False,
        "completed_at": _now(),
    }
    result["coder_result_id"] = _digest(result, "coder-result")
    return result


def get_practical_coder_status(task_id: str = "") -> Dict[str, Any]:
    return {
        "ok": True,
        "runtime_id": "luxcode_practical_coder_runtime",
        "task_id": task_id,
        "status": "ready",
        "local_first": True,
        "read_only_by_default": True,
        "approval_required_for_apply": True,
        "external_api_used": False,
        "network_access_used": False,
        "arbitrary_shell_used": False,
        "live_repository_patch_allowed": False,
        "updated_at": _now(),
    }


def build_minimum_context_for_coder(
    repository_intake: Dict[str, Any],
    search_results: Optional[List[Dict[str, Any]]] = None,
    max_files: int = 8,
    max_chars: int = 16_000,
) -> Dict[str, Any]:
    matches = [
        {
            "file_path": item.get("path", ""),
            "line_start": item.get("line", 1),
            "line_end": item.get("line", 1),
            "symbol_name": "",
        }
        for item in (search_results or [])
        if isinstance(item, dict)
    ]
    return build_minimum_context_package(
        task_summary=repository_intake.get("task_summary", ""),
        repository_intake=repository_intake,
        search_results={"matches": matches},
        target_files=repository_intake.get("suspected_files") or repository_intake.get("requested_files") or [],
        max_files=max_files,
        max_context_bytes=max_chars,
    )
