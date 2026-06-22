from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from permission_manager import PROJECT_ROOT, log_action, result


SESSIONS_ROOT = PROJECT_ROOT / "sessions"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _session_path(session_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(session_id or "default"))
    return SESSIONS_ROOT / f"session_{safe}.json"


def scan_project(workspace_root: str | Path | None = None, max_entries: int = 300) -> Dict[str, Any]:
    root = Path(workspace_root).expanduser().resolve() if workspace_root else PROJECT_ROOT
    entries: List[Dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if len(entries) >= max_entries:
            break
        if any(part in {".git", "__pycache__", ".venv", "venv", "node_modules"} for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        entries.append({"path": rel, "type": "directory" if path.is_dir() else "file", "size": path.stat().st_size if path.is_file() else 0})
    return {"root": str(root), "entries": entries, "count": len(entries)}


def start_session(session_id: str = "default", workspace_root: str | Path | None = None) -> Dict[str, Any]:
    SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)
    path = _session_path(session_id)
    if path.exists():
        session = json.loads(path.read_text(encoding="utf-8"))
    else:
        session = {
            "session_id": session_id,
            "created_at": _now(),
            "workspace_root": str(Path(workspace_root).expanduser().resolve() if workspace_root else PROJECT_ROOT),
            "messages": [],
            "changes": [],
            "project_scan": scan_project(workspace_root),
            "summary": "",
        }
        save_session(session)
    log_action("start_session", True, {"session_id": session_id})
    return result(True, session)


def save_session(session: Dict[str, Any]) -> Dict[str, Any]:
    SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)
    session["updated_at"] = _now()
    path = _session_path(str(session.get("session_id") or "default"))
    path.write_text(json.dumps(session, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    log_action("save_session", True, {"session_id": session.get("session_id"), "path": str(path)})
    return result(True, str(path))


def append_message(session: Dict[str, Any], role: str, content: str) -> Dict[str, Any]:
    message = {"role": role, "content": content, "at": _now()}
    session.setdefault("messages", []).append(message)
    session.setdefault("conversation_history", []).append({"role": role, "content": content})
    if len(session["messages"]) % 5 == 0:
        save_session(session)
    return session


def record_change(session: Dict[str, Any], tool: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    session.setdefault("changes", []).append({"tool": tool, "payload": payload, "at": _now()})
    return session


def end_session(session: Dict[str, Any], summary: str = "") -> Dict[str, Any]:
    session["summary"] = summary or f"{len(session.get('messages', []))} messages, {len(session.get('changes', []))} tool changes."
    session["ended_at"] = _now()
    return save_session(session)
