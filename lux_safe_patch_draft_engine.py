from __future__ import annotations

import difflib
import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SUPPORTED_MODES = {
    "preview",
    "unified_diff_draft",
    "selective_edit_plan",
    "verification_only",
    "full_patch_preview",
}
DEFAULT_MODE = "full_patch_preview"
DEFAULT_MAX_PATCH_FILES = 4
MAX_PATCH_FILES_LIMIT = 12
DEFAULT_MAX_HUNKS_PER_FILE = 3
MAX_HUNKS_PER_FILE_LIMIT = 8
MAX_FILE_BYTES = 1_500_000
MAX_DRAFT_BYTES = 80_000

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".env",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "htmlcov",
    "logs",
    "log",
}

EXCLUDED_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "quick_smoke.txt",
    "quick_smoke_run.txt",
    "quick_smoke_utf8.txt",
    "klasor_haritasi.txt",
    "tum_proje_baglami.txt",
    "tum_proje_kodlari.txt",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".dump",
    ".cache",
    ".pem",
    ".key",
    ".crt",
    ".p12",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".exe",
    ".dll",
}

TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
}

DESTRUCTIVE_TERMS = {
    "delete",
    "remove file",
    "drop table",
    "truncate",
    "rmtree",
    "unlink",
    "destructive",
    "migration",
    "auth",
    "secret",
    "deploy",
    "deployment",
}

SENSITIVE_TERMS = {
    "auth",
    "oauth",
    "token",
    "secret",
    "password",
    "permission",
    "security",
    "database",
    "migration",
    "schema migration",
    "deploy",
    "websocket",
    "stream",
}


def _normalize_text(value: Optional[str], limit: int = 12000) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())[:limit]


def _normalize_mode(mode: Optional[str]) -> str:
    candidate = (mode or DEFAULT_MODE).strip()
    return candidate if candidate in SUPPORTED_MODES else DEFAULT_MODE


def _clamp_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(low, min(parsed, high))


def _stable_request_id(*parts: Any) -> str:
    source = "\n".join(str(part or "") for part in parts)
    return "luxpatch-" + hashlib.sha1(source.encode("utf-8", "ignore")).hexdigest()[:12]


def _resolve_repository_root(repository_root: Optional[str]) -> Tuple[Optional[Path], List[str]]:
    raw_root = (repository_root or os.getcwd()).strip() or os.getcwd()
    try:
        root = Path(raw_root).expanduser().resolve()
    except OSError as exc:
        return None, [f"Repository root could not be resolved: {type(exc).__name__}"]
    if not root.exists() or not root.is_dir():
        return None, [f"Repository root is not an existing directory: {raw_root}"]
    return root, []


def _is_excluded_path(path: Path) -> bool:
    lowered_parts = {part.lower() for part in path.parts}
    if lowered_parts & EXCLUDED_DIRS:
        return True
    name = path.name.lower()
    if name in EXCLUDED_FILE_NAMES:
        return True
    if name.startswith("zzz") and path.suffix.lower() in {".txt", ".log"}:
        return True
    return path.suffix.lower() in EXCLUDED_SUFFIXES


def _safe_candidate(root: Path, raw_path: str, must_exist: bool = True) -> Tuple[Optional[Path], Optional[str]]:
    if not raw_path or "\x00" in raw_path:
        return None, "empty or invalid path"
    cleaned = str(raw_path).strip().strip("\"'")
    if not cleaned:
        return None, "empty path"
    candidate = Path(cleaned)
    if any(part == ".." for part in candidate.parts):
        return None, f"traversal rejected: {raw_path}"
    try:
        resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    except OSError:
        return None, f"path could not be resolved: {raw_path}"
    try:
        resolved.relative_to(root)
    except ValueError:
        return None, f"path outside repository rejected: {raw_path}"
    if resolved.suffix.lower() in EXCLUDED_SUFFIXES:
        return None, f"binary or unsafe file type rejected: {raw_path}"
    if _is_excluded_path(resolved):
        return None, f"excluded path rejected: {raw_path}"
    if resolved.suffix.lower() not in TEXT_SUFFIXES:
        return None, f"unsupported or binary file type: {raw_path}"
    if must_exist and (not resolved.exists() or not resolved.is_file()):
        return None, f"file not found: {raw_path}"
    return resolved, None


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _unique(items: Iterable[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def _extract_context_path(item: Any) -> Optional[str]:
    if isinstance(item, dict):
        for key in ("relative_path", "target_file", "path", "file"):
            value = item.get(key)
            if value:
                return str(value)
    elif item:
        return str(item)
    return None


def _collect_evidence_for_file(relative_path: str, selected_context: List[Any], hypotheses: List[Any]) -> List[str]:
    evidence: List[str] = []
    for item in selected_context:
        if not isinstance(item, dict):
            continue
        if _extract_context_path(item) == relative_path:
            evidence.extend(str(reason) for reason in item.get("reasons", [])[:3])
            if item.get("traceback_line_excerpt"):
                evidence.append("traceback line excerpt available")
            if item.get("excerpt"):
                evidence.append("selected local context excerpt available")
    for cause in hypotheses:
        if not isinstance(cause, dict):
            continue
        related = [str(path) for path in cause.get("related_files", [])]
        if relative_path in related or not related:
            if cause.get("title"):
                evidence.append(f"root cause hypothesis: {cause['title']}")
            evidence.extend(str(item) for item in cause.get("evidence", [])[:2])
    return _unique(evidence)[:6] or ["User request and selected local context indicate this file may need a focused edit."]


def _target_region(path: Path, context_item: Optional[Dict[str, Any]]) -> str:
    if context_item:
        start = context_item.get("line_start") or context_item.get("start_line")
        end = context_item.get("line_end") or context_item.get("end_line")
        if start and end:
            return f"lines {start}-{end}"
        if start:
            return f"around line {start}"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "targeted local region"
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith(("def ", "class ", "@app.", "async def ")):
            return f"around line {index}"
    return "top-level focused region"


def _intent_for_file(relative_path: str, issue_summary: str, change_intent: str) -> Tuple[str, str]:
    text = f"{issue_summary} {change_intent}".lower()
    if relative_path == "app.py" or "endpoint" in text or "route" in text:
        return "endpoint_or_integration_update", "Add or adjust the narrow route/model integration needed by the diagnosed issue."
    if relative_path.endswith("endpoint_coverage_matrix.py"):
        return "coverage_metadata_update", "Add or adjust only the endpoint coverage entries required by the new integration."
    if relative_path.endswith("scripts/smoke_check.py"):
        return "targeted_validation_update", "Add or adjust a targeted smoke check and registry entry for the changed behavior."
    if relative_path.endswith(".py"):
        return "python_logic_update", "Apply a focused Python logic/schema correction at the selected region."
    if relative_path.endswith((".json", ".yaml", ".yml", ".toml")):
        return "configuration_review", "Prepare a minimal config/schema edit for explicit human review."
    if relative_path.endswith((".html", ".css", ".js", ".ts", ".tsx", ".jsx")):
        return "ui_or_client_update", "Prepare a minimal client-side edit and manual scenario validation."
    return "documentation_or_text_update", "Prepare a focused textual update tied to the issue evidence."


def _classify_risk(relative_path: str, purpose: str, issue_summary: str, change_intent: str) -> Tuple[str, List[str]]:
    text = f"{relative_path} {purpose} {issue_summary} {change_intent}".lower()
    reasons: List[str] = []
    if any(term in text for term in DESTRUCTIVE_TERMS):
        reasons.append("destructive or sensitive operation mentioned")
        return "blocked", reasons
    if any(term in text for term in SENSITIVE_TERMS):
        reasons.append("security, runtime, deployment, stream, or data-sensitive surface")
        return "high_risk", reasons
    if relative_path.endswith(("requirements.txt", "render.yaml", ".toml", ".yaml", ".yml", ".json")):
        reasons.append("dependency/config/schema surface needs explicit review")
        return "high_risk", reasons
    if relative_path in {"app.py", "scripts/smoke_check.py", "endpoint_coverage_matrix.py"}:
        reasons.append("shared integration or validation surface")
        return "medium_risk", reasons
    reasons.append("focused source edit with local validation path")
    return "low_risk", reasons


def _validation_for_file(relative_path: str, purpose: str, issue_summary: str) -> List[str]:
    checks = ["git diff --check"]
    if relative_path.endswith(".py"):
        checks.append(f"python -m py_compile {relative_path}")
        checks.append(f"import/endpoint shape test for {relative_path}")
    if "endpoint" in purpose or relative_path == "app.py" or "endpoint" in issue_summary.lower():
        checks.append("endpoint presence check")
        checks.append("targeted smoke for affected endpoint")
    if relative_path.endswith("scripts/smoke_check.py"):
        checks.append("python scripts/smoke_check.py --check <targeted_check>")
        checks.append("python scripts/smoke_check.py --quick")
    if "schema" in purpose or "schema" in issue_summary.lower():
        checks.append("schema validation")
    if relative_path.endswith((".html", ".css", ".js", ".ts", ".tsx", ".jsx")):
        checks.append("manual UI scenario")
    if relative_path.endswith(("requirements.txt", "render.yaml", ".toml", ".yaml", ".yml", ".json")):
        checks.append("explicit human review for config/dependency impact")
    return _unique(checks)


def _rollback_for_file(relative_path: str) -> str:
    return f"Before applying, keep this as a draft; rollback would remove the approved hunk from {relative_path} and rerun targeted validation."


def _build_draft_lines(path: Path, relative_path: str, purpose: str, proposed_change: str) -> Optional[List[str]]:
    try:
        stat = path.stat()
    except OSError:
        return None
    if stat.st_size > MAX_FILE_BYTES:
        return None
    try:
        original = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    except OSError:
        return None
    if not original:
        original = []
    line_ending = "\r\n" if any(line.endswith("\r\n") for line in original[:40]) else "\n"
    draft_marker = f"# DRAFT ONLY: {proposed_change}" if relative_path.endswith(".py") else f"<!-- DRAFT ONLY: {proposed_change} -->"
    if relative_path.endswith((".json", ".yaml", ".yml", ".toml", ".txt", ".md")):
        draft_marker = f"# DRAFT ONLY: {proposed_change}"
    insertion = [draft_marker[:220] + line_ending]
    if relative_path.endswith(".py"):
        for index, line in enumerate(original):
            if line.strip().startswith(("def ", "class ", "async def ", "@app.")):
                return original[:index] + insertion + original[index:]
    return insertion + original


def _unified_diff_for_step(root: Path, step: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    relative_path = step["target_file"]
    path = root / relative_path
    try:
        original = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    except OSError as exc:
        return "", f"diff unavailable for {relative_path}: {type(exc).__name__}"
    draft = _build_draft_lines(path, relative_path, step["purpose"], step["proposed_change"])
    if draft is None:
        return "", f"diff unavailable for {relative_path}: oversized or unreadable file"
    diff = "".join(
        difflib.unified_diff(
            original,
            draft,
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path} (DRAFT ONLY)",
            lineterm="",
        )
    )
    if len(diff.encode("utf-8", "ignore")) > MAX_DRAFT_BYTES:
        return "", f"oversized patch rejected for {relative_path}"
    return diff, None


def _recommended_handoff(steps: List[Dict[str, Any]], blocked_items: List[Dict[str, Any]], issue_summary: str) -> str:
    if blocked_items or any(step.get("risk") == "blocked" for step in steps):
        return "human"
    if any(step.get("risk") == "high_risk" for step in steps):
        return "codex"
    if len(steps) >= 6 or "broad" in issue_summary.lower() or "refactor" in issue_summary.lower():
        return "gemini_cline"
    if len(steps) >= 4:
        return "whale"
    return "local"


def _base_safety() -> Dict[str, Any]:
    return {
        "approval_required": True,
        "can_apply_now": False,
        "destructive_action_blocked": True,
        "file_write_blocked": True,
        "real_execution_blocked": True,
        "read_only": True,
        "external_api_used": False,
        "local_first": True,
    }


def get_safe_patch_draft_schema() -> Dict[str, Any]:
    return {
        "name": "Safe Patch Draft Engine",
        "status": "schema_ready",
        "supported_modes": sorted(SUPPORTED_MODES),
        "default_mode": DEFAULT_MODE,
        "input_fields": [
            "issue_summary",
            "root_cause_hypotheses",
            "selected_context",
            "requested_files",
            "forbidden_files",
            "repository_root",
            "change_intent",
            "mode",
            "max_patch_files",
            "max_hunks_per_file",
        ],
        "output_fields": [
            "request_id",
            "mode",
            "repository_root",
            "issue_summary",
            "patch_targets",
            "patch_steps",
            "unified_diff_draft",
            "blocked_items",
            "forbidden_files_respected",
            "verification_plan",
            "rollback_plan",
            "recommended_handoff",
            "safe_next_step",
        ],
        "draft_only": True,
        "target_files_written": False,
        "terminal_execution_enabled": False,
        "github_action_enabled": False,
        "deployment_enabled": False,
        **_base_safety(),
    }


def get_safe_patch_draft_status() -> Dict[str, Any]:
    return {
        "name": "Safe Patch Draft Engine",
        "status": "safe_patch_draft_ready",
        "real_patch_application_enabled": False,
        "target_file_write_enabled": False,
        "terminal_execution_enabled": False,
        "github_action_enabled": False,
        "deployment_enabled": False,
        "env_file_access_enabled": False,
        "available_endpoints": [
            "/lux-safe-patch/schema",
            "/lux-safe-patch/preview",
            "/debug/lux-safe-patch-status",
        ],
        "safety_note": "Local-first draft engine only proposes structured patch drafts and validation plans. It never applies patches or writes target files.",
        **_base_safety(),
    }


def build_safe_patch_draft(
    issue_summary: Optional[str] = None,
    root_cause_hypotheses: Optional[List[Any]] = None,
    selected_context: Optional[List[Any]] = None,
    requested_files: Optional[List[str]] = None,
    forbidden_files: Optional[List[str]] = None,
    repository_root: Optional[str] = None,
    change_intent: Optional[str] = None,
    mode: Optional[str] = None,
    max_patch_files: Any = DEFAULT_MAX_PATCH_FILES,
    max_hunks_per_file: Any = DEFAULT_MAX_HUNKS_PER_FILE,
) -> Dict[str, Any]:
    normalized_issue = _normalize_text(issue_summary)
    normalized_intent = _normalize_text(change_intent or issue_summary)
    normalized_mode = _normalize_mode(mode)
    hypotheses = list(root_cause_hypotheses or [])
    context = list(selected_context or [])
    requested = [str(item) for item in (requested_files or []) if item]
    forbidden = [str(item) for item in (forbidden_files or []) if item]
    max_files = _clamp_int(max_patch_files, DEFAULT_MAX_PATCH_FILES, 1, MAX_PATCH_FILES_LIMIT)
    max_hunks = _clamp_int(max_hunks_per_file, DEFAULT_MAX_HUNKS_PER_FILE, 1, MAX_HUNKS_PER_FILE_LIMIT)
    root, missing = _resolve_repository_root(repository_root)
    request_id = _stable_request_id(
        normalized_issue,
        normalized_intent,
        requested,
        forbidden,
        normalized_mode,
        max_files,
        max_hunks,
    )

    if root is None:
        return {
            "request_id": request_id,
            "mode": normalized_mode,
            "repository_root": repository_root or "",
            "issue_summary": normalized_issue,
            "patch_targets": [],
            "patch_steps": [],
            "unified_diff_draft": "",
            "blocked_items": [{"target_file": "", "reason": item, "risk": "blocked"} for item in missing],
            "forbidden_files_respected": True,
            "verification_plan": ["Provide a valid repository_root before drafting a patch."],
            "rollback_plan": ["No rollback needed; no patch can be drafted without a valid root."],
            "recommended_handoff": "human",
            "safe_next_step": "Provide a valid repository root and rerun draft generation.",
            **_base_safety(),
        }

    blocked_items: List[Dict[str, Any]] = [{"target_file": "", "reason": item, "risk": "blocked"} for item in missing]
    forbidden_paths: set[str] = set()
    for raw in forbidden:
        safe, reason = _safe_candidate(root, raw, must_exist=False)
        if safe:
            forbidden_paths.add(_relative(root, safe))
        else:
            blocked_items.append({"target_file": raw, "reason": reason, "risk": "blocked"})

    raw_targets = _unique([*requested, *[_extract_context_path(item) for item in context]])
    for cause in hypotheses:
        if isinstance(cause, dict):
            raw_targets.extend(str(item) for item in cause.get("related_files", []) if item)
    raw_targets = _unique(raw_targets)

    if not normalized_issue:
        blocked_items.append({"target_file": "", "reason": "issue_summary is empty; draft falls back to verification-only guidance", "risk": "blocked"})
    if len(raw_targets) > max_files:
        blocked_items.append(
            {
                "target_file": "",
                "reason": f"requested target count {len(raw_targets)} exceeds max_patch_files {max_files}",
                "risk": "blocked",
            }
        )

    targets: List[Dict[str, Any]] = []
    for raw in raw_targets:
        if len(targets) >= max_files:
            break
        safe, reason = _safe_candidate(root, str(raw))
        if not safe:
            blocked_items.append({"target_file": str(raw), "reason": reason, "risk": "blocked"})
            continue
        rel = _relative(root, safe)
        if rel in forbidden_paths or rel in {Path(item).as_posix() for item in forbidden}:
            blocked_items.append({"target_file": rel, "reason": "forbidden file excluded from patch targets", "risk": "blocked"})
            continue
        try:
            if safe.stat().st_size > MAX_FILE_BYTES:
                blocked_items.append({"target_file": rel, "reason": "oversized file rejected", "risk": "blocked"})
                continue
        except OSError:
            blocked_items.append({"target_file": rel, "reason": "file stat unavailable", "risk": "blocked"})
            continue
        targets.append(
            {
                "target_file": rel,
                "absolute_path": str(safe),
                "selected_by": "explicit_or_evidence",
                "hunk_budget": max_hunks,
                "draft_only": True,
            }
        )

    if not targets and not blocked_items:
        blocked_items.append({"target_file": "", "reason": "no explicit or evidence-backed patch target was provided", "risk": "blocked"})

    steps: List[Dict[str, Any]] = []
    for target in targets:
        rel = target["target_file"]
        path = root / rel
        context_item = next((item for item in context if isinstance(item, dict) and _extract_context_path(item) == rel), None)
        purpose, proposed = _intent_for_file(rel, normalized_issue, normalized_intent)
        risk, risk_reasons = _classify_risk(rel, purpose, normalized_issue, normalized_intent)
        if risk == "blocked":
            blocked_items.append({"target_file": rel, "reason": "; ".join(risk_reasons), "risk": "blocked"})
        step = {
            "target_file": rel,
            "target_region": _target_region(path, context_item),
            "purpose": purpose,
            "proposed_change": proposed,
            "change_type": "selective_edit",
            "evidence": _collect_evidence_for_file(rel, context, hypotheses),
            "risk": risk,
            "risk_reasons": risk_reasons,
            "dependencies": _unique(["app.py"] if rel != "app.py" and "endpoint" in purpose else []),
            "approval_required": True,
            "validation_after_change": _validation_for_file(rel, purpose, normalized_issue),
            "rollback_hint": _rollback_for_file(rel),
        }
        steps.append(step)

    diff_parts: List[str] = ["# DRAFT ONLY - DO NOT APPLY WITHOUT USER APPROVAL\n"]
    if normalized_mode in {"unified_diff_draft", "full_patch_preview", "preview"}:
        for step in steps:
            if step.get("risk") == "blocked":
                continue
            diff, reason = _unified_diff_for_step(root, step)
            if reason:
                blocked_items.append({"target_file": step["target_file"], "reason": reason, "risk": "blocked"})
                continue
            if diff:
                diff_parts.append(diff)
                if not diff.endswith("\n"):
                    diff_parts.append("\n")
    unified_diff = "" if normalized_mode == "verification_only" else "".join(diff_parts)
    if len(unified_diff.encode("utf-8", "ignore")) > MAX_DRAFT_BYTES:
        unified_diff = "# DRAFT ONLY - oversized unified diff rejected\n"
        blocked_items.append({"target_file": "", "reason": "combined unified diff draft exceeded size budget", "risk": "blocked"})

    verification_plan = _unique(check for step in steps for check in step["validation_after_change"])
    if not verification_plan:
        verification_plan = ["Provide explicit target files, then run py_compile and targeted smoke for affected surfaces."]
    if len(steps) > 3:
        verification_plan.append("broad change review plus git diff --check")
    rollback_plan = _unique([step["rollback_hint"] for step in steps]) or ["No patch target selected; no rollback action drafted."]
    handoff = _recommended_handoff(steps, blocked_items, normalized_issue)

    return {
        "request_id": request_id,
        "mode": normalized_mode,
        "repository_root": str(root),
        "issue_summary": normalized_issue,
        "patch_targets": targets,
        "patch_steps": steps,
        "unified_diff_draft": unified_diff,
        "blocked_items": blocked_items,
        "forbidden_files_respected": all(target["target_file"] not in forbidden_paths for target in targets),
        "verification_plan": verification_plan,
        "rollback_plan": rollback_plan,
        "recommended_handoff": handoff,
        "safe_next_step": "Review the draft, confirm target files and risk level, then request an explicit apply step in a separate approval turn.",
        **_base_safety(),
    }
