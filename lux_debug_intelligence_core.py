from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SUPPORTED_MODES = {
    "diagnose",
    "root_cause",
    "patch_plan",
    "verification_plan",
    "full_debug_preview",
}

DEFAULT_MODE = "full_debug_preview"
DEFAULT_MAX_FILES = 8
MAX_FILES_LIMIT = 20
PER_FILE_CHAR_BUDGET = 3600
MAX_SCAN_FILES = 260
MAX_SCAN_FILE_BYTES = 512_000

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
}

CODE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".md", ".txt", ".json", ".yaml", ".yml"}
TRACEBACK_FILE_RE = re.compile(r'File\s+"([^"]+)",\s+line\s+(\d+)')
FILENAME_RE = re.compile(r"[\w./\\-]+\.(?:py|js|ts|tsx|jsx|html|css|json|md|txt|yaml|yml)")
SYMBOL_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b")

MUST_NOT_TOUCH = [
    "static/index.html",
    ".env",
    ".git",
    "__pycache__",
    "*.pyc",
    "generated dumps",
    "logs",
    "deployment files",
    "GitHub automation",
]


def _clamp_max_files(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_MAX_FILES
    return max(1, min(parsed, MAX_FILES_LIMIT))


def _normalize_mode(mode: Optional[str]) -> str:
    candidate = (mode or DEFAULT_MODE).strip()
    return candidate if candidate in SUPPORTED_MODES else DEFAULT_MODE


def _normalize_text(text: Optional[str], limit: int = 12000) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:limit]


def _stable_request_id(*parts: Any) -> str:
    source = "\n".join(str(part or "") for part in parts)
    return "luxdebug-" + hashlib.sha1(source.encode("utf-8", "ignore")).hexdigest()[:12]


def _resolve_repository_root(repository_root: Optional[str]) -> Tuple[Optional[Path], List[str]]:
    missing: List[str] = []
    raw_root = (repository_root or os.getcwd()).strip()
    if not raw_root:
        raw_root = os.getcwd()
    try:
        root = Path(raw_root).expanduser().resolve()
    except OSError as exc:
        return None, [f"Repository root could not be resolved: {type(exc).__name__}"]
    if not root.exists() or not root.is_dir():
        return None, [f"Repository root is not an existing directory: {raw_root}"]
    return root, missing


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


def _safe_candidate(root: Path, raw_path: str) -> Tuple[Optional[Path], Optional[str]]:
    if not raw_path or "\x00" in raw_path:
        return None, "empty or invalid path"
    cleaned = raw_path.strip().strip("\"'")
    if not cleaned:
        return None, "empty path"
    candidate = Path(cleaned)
    if any(part == ".." for part in candidate.parts):
        return None, f"traversal rejected: {raw_path}"
    if candidate.is_absolute():
        try:
            resolved = candidate.resolve()
        except OSError:
            return None, f"path could not be resolved: {raw_path}"
    else:
        try:
            resolved = (root / candidate).resolve()
        except OSError:
            return None, f"path could not be resolved: {raw_path}"
    try:
        resolved.relative_to(root)
    except ValueError:
        return None, f"path outside repository rejected: {raw_path}"
    if _is_excluded_path(resolved):
        return None, f"excluded path rejected: {raw_path}"
    if not resolved.exists() or not resolved.is_file():
        return None, f"file not found: {raw_path}"
    if resolved.suffix.lower() not in CODE_SUFFIXES:
        return None, f"unsupported file type: {raw_path}"
    return resolved, None


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _add_candidate(
    candidates: Dict[str, Dict[str, Any]],
    root: Path,
    path: Path,
    reason: str,
    category: str,
    signal: str,
) -> None:
    rel = _relative(root, path)
    item = candidates.setdefault(
        rel,
        {
            "path": path,
            "relative_path": rel,
            "reasons": [],
            "categories": [],
            "matched_signals": [],
            "priority": 0,
        },
    )
    if reason not in item["reasons"]:
        item["reasons"].append(reason)
    if category not in item["categories"]:
        item["categories"].append(category)
    if signal and signal not in item["matched_signals"]:
        item["matched_signals"].append(signal[:160])
    item["priority"] += {
        "suspected_file": 100,
        "traceback": 95,
        "changed_file": 80,
        "issue_match": 60,
        "related_file": 45,
        "import_neighbor": 35,
        "fallback": 10,
    }.get(category, 10)


def _iter_bounded_code_files(root: Path) -> Iterable[Path]:
    scanned = 0
    preferred_roots = [root, root / "scripts", root / "tests", root / "static"]
    seen: set[Path] = set()
    for base in preferred_roots:
        if not base.exists() or not base.is_dir():
            continue
        for path in base.rglob("*"):
            if scanned >= MAX_SCAN_FILES:
                return
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            if _is_excluded_path(path) or path.suffix.lower() not in CODE_SUFFIXES:
                continue
            try:
                if path.stat().st_size > MAX_SCAN_FILE_BYTES:
                    continue
            except OSError:
                continue
            scanned += 1
            yield path


def _extract_traceback_files(traceback_text: str) -> List[Tuple[str, str]]:
    matches: List[Tuple[str, str]] = []
    for file_path, line_no in TRACEBACK_FILE_RE.findall(traceback_text or ""):
        matches.append((file_path, line_no))
    for file_path in FILENAME_RE.findall(traceback_text or ""):
        if not any(existing == file_path for existing, _ in matches):
            matches.append((file_path, ""))
    return matches


def _extract_issue_tokens(issue_text: str) -> Tuple[List[str], List[str]]:
    filenames = list(dict.fromkeys(FILENAME_RE.findall(issue_text or "")))
    symbols = [
        token
        for token in dict.fromkeys(SYMBOL_RE.findall(issue_text or ""))
        if len(token) >= 4 and token.lower() not in {"this", "that", "with", "from", "error", "hata"}
    ][:24]
    return filenames, symbols


def _read_excerpt(path: Path, limit: int = PER_FILE_CHAR_BUDGET) -> Tuple[str, bool]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", False
    return text[:limit], len(text) > limit


def _line_window(path: Path, line_no: str, window: int = 8) -> str:
    if not line_no or not line_no.isdigit():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    index = max(0, int(line_no) - 1)
    start = max(0, index - window)
    end = min(len(lines), index + window + 1)
    return "\n".join(f"{number + 1}: {lines[number]}" for number in range(start, end))


def _maybe_add_related_files(candidates: Dict[str, Dict[str, Any]], root: Path) -> None:
    selected_names = set(candidates)
    related_map = {
        "app.py": ["endpoint_coverage_matrix.py", "scripts/smoke_check.py"],
        "endpoint_coverage_matrix.py": ["app.py", "scripts/smoke_check.py"],
        "scripts/smoke_check.py": ["app.py", "endpoint_coverage_matrix.py"],
    }
    for rel, related in related_map.items():
        if rel in selected_names:
            for related_rel in related:
                safe, _ = _safe_candidate(root, related_rel)
                if safe:
                    _add_candidate(candidates, root, safe, f"Related validation surface for {rel}", "related_file", rel)
    for rel in list(selected_names):
        if rel.endswith("_preview.py") or rel.endswith("_core.py"):
            for related_rel in ["app.py", "endpoint_coverage_matrix.py", "scripts/smoke_check.py"]:
                safe, _ = _safe_candidate(root, related_rel)
                if safe:
                    _add_candidate(candidates, root, safe, f"Integration surface for {rel}", "related_file", rel)


def _maybe_add_import_neighbors(candidates: Dict[str, Dict[str, Any]], root: Path) -> None:
    import_targets: set[str] = set()
    for item in list(candidates.values()):
        path = item["path"]
        if path.suffix.lower() != ".py":
            continue
        excerpt, _ = _read_excerpt(path, 9000)
        for match in re.findall(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", excerpt, flags=re.MULTILINE):
            import_targets.add(match)
    for target in sorted(import_targets)[:18]:
        safe, _ = _safe_candidate(root, f"{target}.py")
        if safe:
            _add_candidate(candidates, root, safe, f"Local import neighbor referenced by selected context: {target}", "import_neighbor", target)


def _select_context(
    root: Optional[Path],
    issue_text: str,
    traceback_text: str,
    suspected_files: Iterable[str],
    changed_files: Iterable[str],
    max_files: int,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    missing: List[str] = []
    if root is None:
        return [], ["Repository root is required before local context can be selected."]

    candidates: Dict[str, Dict[str, Any]] = {}

    for raw in suspected_files or []:
        safe, reason = _safe_candidate(root, str(raw))
        if safe:
            _add_candidate(candidates, root, safe, "User provided suspected file", "suspected_file", str(raw))
        elif reason:
            missing.append(reason)

    for raw, line_no in _extract_traceback_files(traceback_text):
        safe, reason = _safe_candidate(root, raw)
        if safe:
            detail = f"Traceback references line {line_no}" if line_no else "Traceback references this file"
            _add_candidate(candidates, root, safe, detail, "traceback", raw)
        elif reason:
            missing.append(reason)

    for raw in changed_files or []:
        safe, reason = _safe_candidate(root, str(raw))
        if safe:
            _add_candidate(candidates, root, safe, "Recently changed file", "changed_file", str(raw))
        elif reason:
            missing.append(reason)

    filename_tokens, symbols = _extract_issue_tokens(issue_text)
    for raw in filename_tokens:
        safe, reason = _safe_candidate(root, raw)
        if safe:
            _add_candidate(candidates, root, safe, "Issue text names this file", "issue_match", raw)
        elif reason:
            missing.append(reason)

    lowered_issue = issue_text.lower()
    endpoint_words = {"endpoint", "route", "api", "schema", "smoke", "coverage", "debug", "router"}
    if endpoint_words & set(re.findall(r"[a-zA-Z_]+", lowered_issue)):
        for rel in ["app.py", "endpoint_coverage_matrix.py", "scripts/smoke_check.py"]:
            safe, _ = _safe_candidate(root, rel)
            if safe:
                _add_candidate(candidates, root, safe, "Issue text points to route/coverage/smoke alignment", "issue_match", rel)

    if symbols:
        lowered_symbols = [symbol.lower() for symbol in symbols]
        for path in _iter_bounded_code_files(root):
            rel = _relative(root, path)
            if rel in candidates:
                continue
            try:
                preview = path.read_text(encoding="utf-8", errors="ignore")[:12000].lower()
            except OSError:
                continue
            hits = [symbol for symbol in lowered_symbols if symbol in preview]
            if hits:
                _add_candidate(candidates, root, path, "Issue symbol match in bounded local scan", "issue_match", ", ".join(hits[:5]))

    _maybe_add_related_files(candidates, root)
    _maybe_add_import_neighbors(candidates, root)

    if not candidates:
        for rel in ["app.py", "endpoint_coverage_matrix.py", "scripts/smoke_check.py"]:
            safe, _ = _safe_candidate(root, rel)
            if safe:
                _add_candidate(candidates, root, safe, "Fallback context because issue details were not specific", "fallback", rel)
        missing.append("Provide traceback_text, suspected_files, or changed_files for more precise diagnosis.")

    ordered = sorted(candidates.values(), key=lambda item: (-item["priority"], item["relative_path"]))[:max_files]
    selected: List[Dict[str, Any]] = []
    for item in ordered:
        path = item["path"]
        excerpt, truncated = _read_excerpt(path)
        traceback_lines = []
        for raw, line_no in _extract_traceback_files(traceback_text):
            safe, _ = _safe_candidate(root, raw)
            if safe and safe == path:
                window = _line_window(path, line_no)
                if window:
                    traceback_lines.append(window[:1600])
        try:
            size_bytes = path.stat().st_size
        except OSError:
            size_bytes = 0
        selected.append(
            {
                "relative_path": item["relative_path"],
                "reasons": item["reasons"],
                "categories": item["categories"],
                "matched_signals": item["matched_signals"],
                "size_bytes": size_bytes,
                "excerpt": excerpt,
                "traceback_line_excerpt": traceback_lines[:2],
                "excerpt_truncated": truncated,
                "read_only": True,
            }
        )
    return selected, missing


def _make_root_causes(issue_text: str, traceback_text: str, selected_context: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    causes: List[Dict[str, Any]] = []
    selected_files = [item["relative_path"] for item in selected_context]
    has_traceback = bool(_extract_traceback_files(traceback_text))
    if has_traceback:
        evidence = ["Traceback file references were found and selected as primary context."]
        causes.append(
            {
                "title": "Traceback-localized failure",
                "explanation": "The strongest signal is the traceback path/line reference. Inspect the selected line window first, then verify caller assumptions around it.",
                "evidence": evidence,
                "related_files": selected_files[:5],
                "confidence": 0.76,
                "validation_needed": ["Reproduce with targeted smoke or import test", "Check the failing line and immediate caller"],
                "likely_scope": "localized",
                "is_confirmed": False,
            }
        )
    lower_issue = issue_text.lower()
    if any(word in lower_issue for word in ["endpoint", "route", "schema", "smoke", "coverage", "api"]):
        causes.append(
            {
                "title": "Endpoint, schema, and smoke alignment drift",
                "explanation": "The issue text points to integration surfaces where app routes, endpoint coverage records, and smoke checks can drift apart.",
                "evidence": [file for file in selected_files if file in {"app.py", "endpoint_coverage_matrix.py", "scripts/smoke_check.py"}],
                "related_files": [file for file in selected_files if file in {"app.py", "endpoint_coverage_matrix.py", "scripts/smoke_check.py"}],
                "confidence": 0.68,
                "validation_needed": ["Endpoint presence check", "Targeted smoke check", "Schema check"],
                "likely_scope": "integration",
                "is_confirmed": False,
            }
        )
    if any("ImportError" in text or "ModuleNotFoundError" in text for text in [issue_text, traceback_text]):
        causes.append(
            {
                "title": "Import mismatch or missing module exposure",
                "explanation": "The error signal suggests a module, function name, or app import may not match the implementation.",
                "evidence": ["Import error keyword present in issue or traceback"],
                "related_files": selected_files[:6],
                "confidence": 0.7,
                "validation_needed": ["py_compile", "direct import test"],
                "likely_scope": "module boundary",
                "is_confirmed": False,
            }
        )
    if not causes:
        causes.append(
            {
                "title": "Insufficiently localized debug signal",
                "explanation": "The request needs a traceback, suspected file, changed file, or failing command before a specific root cause can be confirmed.",
                "evidence": ["No precise traceback path or explicit source file was provided"],
                "related_files": selected_files[:5],
                "confidence": 0.42,
                "validation_needed": ["Collect failing command output", "Add suspected_files or traceback_text"],
                "likely_scope": "unknown",
                "is_confirmed": False,
            }
        )
    return causes[:4]


def _make_adjacent_issues(issue_text: str, selected_context: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    selected = {item["relative_path"] for item in selected_context}
    lower_issue = issue_text.lower()
    checks = [
        ("missing endpoint coverage", "endpoint_coverage_matrix.py", "likely_related", "Route work should have a matching endpoint coverage record."),
        ("missing smoke", "scripts/smoke_check.py", "likely_related", "New read-only/debug behavior should have a targeted smoke check."),
        ("import mismatch", "app.py", "directly_related", "App imports must match the core public function names."),
        ("request/schema mismatch", "app.py", "directly_related", "Request model fields should match the core analyzer inputs."),
        ("stale status info", "app.py", "likely_related", "Status endpoint should reflect the current local-first safety boundary."),
        ("duplicated routing logic", "luxcode_master_router_preview.py", "optional_improvement", "Router logic should remain separate from debug diagnosis logic."),
        ("inconsistent safety flags", "", "directly_related", "Safety invariants must stay true on every response."),
        ("missing fallback", "", "likely_related", "Unknown or underspecified requests need a safe fallback diagnosis."),
        ("missing validation", "scripts/validate_lux_debug_intelligence.py", "directly_related", "Local validator should cover schema, selection, safety, and planner output."),
        ("unrelated modified files", "", "out_of_scope", "Dirty tree state should be audited before committing any debug-core work."),
        ("likely regression risks", "", "likely_related", "Changing app, smoke, and coverage together can regress route availability."),
    ]
    issues: List[Dict[str, Any]] = []
    for title, file_hint, classification, why in checks:
        direct_hit = file_hint in selected if file_hint else any(word in lower_issue for word in title.split())
        issues.append(
            {
                "title": title,
                "classification": classification if direct_hit or classification in {"directly_related", "out_of_scope"} else "optional_improvement",
                "evidence": [file_hint] if file_hint and file_hint in selected else [],
                "explanation": why,
                "recommended_action": "Check during the proposed verification plan; do not edit unrelated files.",
            }
        )
    return issues


def _make_patch_plan(selected_context: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not selected_context:
        return [
            {
                "target_file": "TBD",
                "purpose": "Collect enough context before proposing a patch.",
                "proposed_change": "Ask for traceback_text, suspected_files, changed_files, or the failing command output.",
                "risk": "low",
                "dependencies": [],
                "approval_required": True,
                "validation_after_change": ["Re-run targeted validation once a target file is known"],
                "must_not_touch": MUST_NOT_TOUCH,
            }
        ]
    plan: List[Dict[str, Any]] = []
    for item in selected_context[:8]:
        rel = item["relative_path"]
        plan.append(
            {
                "target_file": rel,
                "purpose": "Address only the confirmed failure surface after validation.",
                "proposed_change": "Prepare a selective, minimal edit based on the confirmed root cause; avoid full-file replacement unless the file is generated and explicitly approved.",
                "risk": "medium" if rel in {"app.py", "scripts/smoke_check.py", "endpoint_coverage_matrix.py"} else "low",
                "dependencies": [reason for reason in item.get("reasons", [])],
                "approval_required": True,
                "validation_after_change": ["py_compile", "targeted smoke", "git diff --check"],
                "must_not_touch": MUST_NOT_TOUCH,
            }
        )
    return plan


def _make_verification_plan(selected_context: List[Dict[str, Any]], mode: str) -> List[Dict[str, Any]]:
    selected = {item["relative_path"] for item in selected_context}
    plan = [
        {"check": "py_compile", "command": "python -m py_compile <changed python files>", "reason": "Catch syntax/import boundary errors early.", "required": True},
        {"check": "targeted smoke", "command": "python scripts/smoke_check.py --check <relevant_check>", "reason": "Verify the smallest affected behavior.", "required": True},
        {"check": "segmented smoke", "command": "python scripts/smoke_check.py --layer <layer>", "reason": "Use only when a layer-specific surface changed.", "required": False},
        {"check": "quick smoke", "command": "python scripts/smoke_check.py --quick", "reason": "Broad lightweight regression scan after integration edits.", "required": bool({"app.py", "scripts/smoke_check.py"} & selected)},
        {"check": "import test", "command": "python -c \"import <module>\"", "reason": "Confirm public symbols load locally.", "required": True},
        {"check": "endpoint presence check", "command": "GET affected endpoint with TestClient", "reason": "Confirm FastAPI route is registered.", "required": "app.py" in selected},
        {"check": "schema check", "command": "GET schema/status endpoint", "reason": "Confirm request and response contracts.", "required": "app.py" in selected},
        {"check": "fallback test", "command": "Call analyzer/router with unknown input", "reason": "Confirm safe fallback path.", "required": True},
        {"check": "git diff --check", "command": "git diff --check", "reason": "Catch whitespace conflict markers before commit.", "required": True},
        {"check": "manual UI test", "command": "Manual browser check", "reason": "Only needed if a UI route changed.", "required": False},
        {"check": "full smoke", "command": "python scripts/smoke_check.py", "reason": "Use only for high-risk cross-cutting changes or release readiness.", "required": False},
    ]
    if mode == "verification_plan":
        return plan
    return plan


def _recommended_handoff(selected_context: List[Dict[str, Any]], root_causes: List[Dict[str, Any]]) -> str:
    files = {item["relative_path"] for item in selected_context}
    if not files:
        return "human"
    if any(cause.get("confidence", 0) >= 0.72 for cause in root_causes):
        return "codex"
    if len(files) > 10:
        return "gemini_cline"
    if any(file.endswith((".html", ".css", ".js", ".tsx", ".jsx")) for file in files):
        return "codex"
    return "local"


def _base_safety() -> Dict[str, bool]:
    return {
        "read_only": True,
        "real_execution_blocked": True,
        "file_write_blocked": True,
        "external_api_used": False,
        "local_first": True,
    }


def get_lux_debug_schema() -> Dict[str, Any]:
    return {
        "name": "Lux Debug Intelligence Core",
        "status": "local_first_read_only_mvp",
        "supported_modes": sorted(SUPPORTED_MODES),
        "input_fields": [
            "issue_text",
            "traceback_text",
            "suspected_files",
            "changed_files",
            "repository_root",
            "max_files",
            "mode",
        ],
        "output_fields": [
            "request_id",
            "mode",
            "normalized_issue",
            "repository_root",
            "selected_context",
            "root_cause_hypotheses",
            "adjacent_issues",
            "patch_plan",
            "verification_plan",
            "missing_information",
            "recommended_handoff",
            "safe_next_step",
            "confidence",
            "read_only",
            "real_execution_blocked",
            "file_write_blocked",
            "external_api_used",
            "local_first",
        ],
        "safety_boundary": "Local repository read-only diagnosis only. No patch application, terminal execution, GitHub, deployment, external API, or .env access.",
        "excluded_paths": sorted(EXCLUDED_DIRS | EXCLUDED_FILE_NAMES),
        "must_not_touch": MUST_NOT_TOUCH,
        **_base_safety(),
    }


def analyze_lux_debug_request(
    issue_text: str = "",
    traceback_text: str = "",
    suspected_files: Optional[List[str]] = None,
    changed_files: Optional[List[str]] = None,
    repository_root: Optional[str] = None,
    max_files: int = DEFAULT_MAX_FILES,
    mode: str = DEFAULT_MODE,
) -> Dict[str, Any]:
    normalized_issue = _normalize_text(issue_text, 8000)
    normalized_traceback = traceback_text or ""
    normalized_mode = _normalize_mode(mode)
    bounded_max_files = _clamp_max_files(max_files)
    root, root_missing = _resolve_repository_root(repository_root)
    selected_context, selection_missing = _select_context(
        root,
        normalized_issue,
        normalized_traceback,
        suspected_files or [],
        changed_files or [],
        bounded_max_files,
    )
    root_causes = _make_root_causes(normalized_issue, normalized_traceback, selected_context)
    adjacent_issues = _make_adjacent_issues(normalized_issue, selected_context)
    patch_plan = _make_patch_plan(selected_context)
    verification_plan = _make_verification_plan(selected_context, normalized_mode)
    confidence = max([cause.get("confidence", 0.0) for cause in root_causes] or [0.35])
    handoff = _recommended_handoff(selected_context, root_causes)
    missing_information = list(dict.fromkeys(root_missing + selection_missing))
    if not normalized_issue:
        missing_information.append("issue_text is empty; diagnosis is based on fallback context only.")

    response: Dict[str, Any] = {
        "request_id": _stable_request_id(normalized_issue, normalized_traceback, suspected_files, changed_files, str(root), bounded_max_files, normalized_mode),
        "mode": normalized_mode,
        "normalized_issue": normalized_issue,
        "repository_root": str(root) if root else None,
        "selected_context": selected_context,
        "root_cause_hypotheses": root_causes,
        "adjacent_issues": adjacent_issues,
        "patch_plan": patch_plan,
        "verification_plan": verification_plan,
        "missing_information": missing_information,
        "recommended_handoff": handoff,
        "safe_next_step": "Review selected context and confirm any code edit before patching. This core will not write files or execute commands.",
        "confidence": round(float(confidence), 2),
        **_base_safety(),
    }
    return response


def get_lux_debug_status() -> Dict[str, Any]:
    return {
        "status": "ready",
        "name": "Lux Debug Intelligence Core",
        "supported_modes": sorted(SUPPORTED_MODES),
        "context_selector": "bounded_local_repository_read_only",
        "patch_application_enabled": False,
        "terminal_execution_enabled": False,
        "github_action_enabled": False,
        "deployment_enabled": False,
        "env_file_access_enabled": False,
        **_base_safety(),
    }
