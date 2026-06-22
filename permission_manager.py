from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parent
LOG_PATH = PROJECT_ROOT / "logs" / "coder_actions.log"

DENIED_COMMAND_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\brm\s+-rf\b",
        r"\bformat\b",
        r"\bmkfs\b",
        r"\bdel\s+/s\b",
        r"\brmdir\s+/s\b",
        r"\bshutdown\b",
        r"\brestart-computer\b",
        r"\bremove-item\b.*\s-recurse\b.*\s-force\b",
        r":\(\)\s*\{",
    )
]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _jsonable(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def log_action(action: str, success: bool, detail: Optional[Dict[str, Any]] = None) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": _now(),
        "action": action,
        "success": bool(success),
        "detail": detail or {},
    }
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(_jsonable(entry) + "\n")


def result(success: bool, result_value: Any = "", error: str = "", **extra: Any) -> Dict[str, Any]:
    payload = {"success": bool(success), "result": result_value, "error": str(error or "")}
    payload.update(extra)
    return payload


def resolve_safe_path(path: str | Path, *, base_root: str | Path | None = None, must_exist: bool = False) -> Path:
    root = Path(base_root).expanduser().resolve() if base_root else PROJECT_ROOT
    raw = str(path or "").strip().strip("\"'")
    if not raw or "\x00" in raw:
        raise ValueError("empty_or_invalid_path")
    candidate = Path(raw)
    if any(part == ".." for part in candidate.parts):
        raise ValueError("path_traversal_blocked")
    resolved = candidate.expanduser().resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("path_outside_project_root") from exc
    if must_exist and not resolved.exists():
        raise FileNotFoundError(str(resolved))
    return resolved


def is_command_allowed(command: str) -> Dict[str, Any]:
    text = str(command or "").strip()
    if not text:
        return result(False, error="empty_command")
    for pattern in DENIED_COMMAND_PATTERNS:
        if pattern.search(text):
            return result(False, error="dangerous_command_blocked", pattern=pattern.pattern)
    return result(True, result_value="allowed")


def requires_user_approval(operation: str, *, file_count: int = 1, command: str = "") -> bool:
    op = str(operation or "").lower()
    if op in {"delete_file", "bulk_edit", "system_command"}:
        return True
    if op == "run_command":
        command_text = command.lower()
        return any(token in command_text for token in ("git push", "git commit", "pip install", "npm install", "deploy"))
    return file_count > 5

