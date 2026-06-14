from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SECRET_MARKERS = (
    "api_key",
    "token",
    "secret",
    "authorization",
    "credential",
    "password",
    "private_key",
    "environment_value",
)
EXCLUDED_PARTS = {".git", ".env", ".luxcode_runtime", ".luxcode_snapshots", "luxcode_backups", "__pycache__"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: Any, prefix: str = "lux-context") -> str:
    return f"{prefix}-{hashlib.sha256(_stable_json(value).encode('utf-8')).hexdigest()[:24]}"


def _text_digest(value: str, prefix: str = "snippet") -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:24]}"


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


def _safe_failure(message: str, **extra: Any) -> Dict[str, Any]:
    return {"ok": False, "error": message, **extra, "external_api_used": False, "network_access_used": False, "local_first": True}


def _is_excluded(path: str) -> bool:
    normalized = path.replace("\\", "/")
    parts = set(part for part in normalized.split("/") if part)
    lower = normalized.lower()
    if parts & EXCLUDED_PARTS:
        return True
    return any(marker in lower for marker in (".env", "secret", "credential", "token", "password")) or lower.endswith((".pyc", ".db", ".sqlite", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".exe"))


def _redact(text: str) -> str:
    value = text.replace("\x00", "")
    for marker in SECRET_MARKERS:
        if marker in value.lower():
            return "[redacted-secret-like-line]"
    return value


def _resolve_repo_path(root: Path, rel: str) -> Optional[Path]:
    try:
        candidate = (root / rel).resolve()
        candidate.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    if _is_excluded(str(candidate.relative_to(root)).replace("\\", "/")):
        return None
    return candidate


def _line_window(path: Path, line_start: int, line_end: int, lines_before: int, lines_after: int, max_bytes: int) -> Tuple[int, int, str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 1, 1, ""
    start = max(1, int(line_start or 1) - max(0, lines_before))
    end = min(len(lines), int(line_end or line_start or 1) + max(0, lines_after))
    content_lines = [_redact(line) for line in lines[start - 1 : end]]
    content = "\n".join(content_lines)
    while len(content.encode("utf-8")) > max_bytes and content_lines:
        content_lines.pop()
        content = "\n".join(content_lines)
        end = max(start, end - 1)
    return start, end, content


def _repo_root_from_intake(repository_intake: Dict[str, Any]) -> Optional[Path]:
    root_text = str(repository_intake.get("repository_root") or "")
    if not root_text:
        return None
    try:
        root = Path(root_text).resolve()
    except OSError:
        return None
    return root if root.exists() and root.is_dir() else None


def build_minimum_context_package(
    task_summary: str = "",
    repository_intake: Optional[Dict[str, Any]] = None,
    search_results: Optional[Dict[str, Any]] = None,
    target_files: Optional[List[str]] = None,
    target_symbols: Optional[List[str]] = None,
    failure_signatures: Optional[List[Dict[str, Any]]] = None,
    completed_scope: Optional[List[str]] = None,
    remaining_gap: Optional[Dict[str, Any]] = None,
    max_context_bytes: int = 24_000,
    max_files: int = 8,
    lines_before: int = 8,
    lines_after: int = 12,
) -> Dict[str, Any]:
    repository_intake = repository_intake or {}
    search_results = search_results or {}
    remaining_gap = remaining_gap or {}
    completed = set(_normalize_list(completed_scope or []))
    root = _repo_root_from_intake(repository_intake)
    if root is None:
        return _safe_failure("valid repository_intake.repository_root is required")

    max_context_bytes = max(1000, min(int(max_context_bytes or 24_000), 120_000))
    max_files = max(1, min(int(max_files or 8), 30))
    target_file_set = set(_normalize_list(target_files or []))
    for file_path in _normalize_list(remaining_gap.get("remaining_files", [])):
        target_file_set.add(file_path)
    selected_symbols = _normalize_list(target_symbols or [])

    snippets: List[Dict[str, Any]] = []
    excluded_files: List[str] = []
    exclusion_reasons: Dict[str, str] = {}
    candidates: List[Tuple[str, int, int, str, str]] = []

    for match in search_results.get("matches", []) if isinstance(search_results, dict) else []:
        rel = str(match.get("file_path") or "").replace("\\", "/")
        if not rel or rel in completed:
            continue
        if target_file_set and rel not in target_file_set and rel not in remaining_gap.get("remaining_files", []):
            continue
        candidates.append((rel, int(match.get("line_start") or 1), int(match.get("line_end") or match.get("line_start") or 1), str(match.get("symbol_name") or ""), "search_match"))

    for rel in sorted(target_file_set):
        if rel in completed:
            excluded_files.append(rel)
            exclusion_reasons[rel] = "completed_scope"
            continue
        if not any(item[0] == rel for item in candidates):
            candidates.append((rel, 1, 80, "", "target_file"))

    seen = set()
    current_bytes = 0
    for rel, line_start, line_end, symbol, reason in sorted(candidates, key=lambda item: (item[0], item[1], item[3]))[: max_files * 4]:
        if len({snippet["file_path"] for snippet in snippets}) >= max_files and rel not in {snippet["file_path"] for snippet in snippets}:
            excluded_files.append(rel)
            exclusion_reasons[rel] = "file_cap"
            continue
        if _is_excluded(rel):
            excluded_files.append(rel)
            exclusion_reasons[rel] = "excluded_path_or_secret"
            continue
        path = _resolve_repo_path(root, rel)
        if path is None or not path.exists() or not path.is_file():
            excluded_files.append(rel)
            exclusion_reasons[rel] = "missing_or_outside_repository"
            continue
        size = path.stat().st_size
        snippet_budget = max(500, min(4000, max_context_bytes - current_bytes))
        start, end, content = _line_window(path, line_start, line_end, lines_before, lines_after, snippet_budget)
        if not content:
            excluded_files.append(rel)
            exclusion_reasons[rel] = "empty_or_unreadable"
            continue
        key = (rel, start, end, symbol)
        if key in seen:
            continue
        seen.add(key)
        snippet = {
            "file_path": rel,
            "symbol_name": symbol,
            "line_start": start,
            "line_end": end,
            "content": content,
            "content_digest": _text_digest(content),
            "selection_reason": reason if size > snippet_budget else f"{reason};snippet_preferred",
        }
        size_bytes = len(content.encode("utf-8"))
        if current_bytes + size_bytes > max_context_bytes:
            excluded_files.append(rel)
            exclusion_reasons[rel] = "context_byte_cap"
            break
        snippets.append(snippet)
        current_bytes += size_bytes

    package = {
        "context_package_id": _digest(
            {
                "task_summary": task_summary,
                "repo": repository_intake.get("intake_digest"),
                "snippets": [(s["file_path"], s["line_start"], s["line_end"], s["content_digest"]) for s in snippets],
                "remaining_gap": remaining_gap,
            },
            prefix="context",
        ),
        "task_summary": task_summary[:2000],
        "repository_metadata": {
            "repository_name": repository_intake.get("repository_name", ""),
            "branch": repository_intake.get("branch", ""),
            "head_commit": repository_intake.get("head_commit", ""),
            "intake_digest": repository_intake.get("intake_digest", ""),
        },
        "selected_files": sorted({item["file_path"] for item in snippets}),
        "selected_symbols": selected_symbols,
        "selected_snippets": snippets,
        "excluded_files": sorted(set(excluded_files)),
        "exclusion_reasons": exclusion_reasons,
        "completed_scope": sorted(completed),
        "remaining_gap": remaining_gap,
        "known_failed_approaches": [
            {
                "failure_signature_id": item.get("failure_signature_id", ""),
                "failure_category": item.get("failure_category", ""),
                "failure_digest": item.get("failure_digest", ""),
            }
            for item in (failure_signatures or [])
            if isinstance(item, dict)
        ][:20],
        "validation_commands": repository_intake.get("preferred_validation", []) or repository_intake.get("available_validation_tools", []),
        "context_bytes": current_bytes,
        "context_truncated": bool(excluded_files) or current_bytes >= max_context_bytes,
        "created_at": _now(),
        "external_api_used": False,
        "network_access_used": False,
        "local_first": True,
    }
    package["context_digest"] = _digest(
        {
            "task_summary": package["task_summary"],
            "files": package["selected_files"],
            "snippets": [(s["file_path"], s["line_start"], s["line_end"], s["content_digest"]) for s in snippets],
            "remaining_gap": package["remaining_gap"],
            "known_failed_approaches": package["known_failed_approaches"],
        },
        prefix="context-digest",
    )
    package["ok"] = True
    return package


def get_minimum_context_builder_schema() -> Dict[str, Any]:
    return {
        "name": "LuxCode Minimum Context Builder",
        "status": "ready",
        "snippet_first": True,
        "full_repository_context": False,
        "secret_exclusion": True,
        "external_api_used": False,
        "network_access_used": False,
        "local_first": True,
    }
