from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List


DENIED_COMMAND_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\brm\s+-rf\b",
        r"\bformat\b",
        r"\bmkfs\b",
        r":\(\)\s*\{",
        r">\s*/dev/null",
        r"\bdel\s+/s\b",
        r"\brmdir\s+/s\b",
    )
]


class ToolRegistry:
    def __init__(self, workspace_root: str | Path, command_timeout_seconds: int = 30) -> None:
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        self.command_timeout_seconds = int(command_timeout_seconds)
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, path: str | Path) -> Path:
        candidate = (self.workspace_root / Path(path)).resolve() if not Path(path).is_absolute() else Path(path).resolve()
        try:
            candidate.relative_to(self.workspace_root)
        except ValueError as exc:
            raise ValueError(f"path_outside_workspace:{path}") from exc
        return candidate

    def filesystem_read(self, path: str) -> Dict[str, Any]:
        target = self._safe_path(path)
        if not target.is_file():
            return {"ok": False, "error": "file_not_found", "path": str(target)}
        return {"ok": True, "path": str(target), "content": target.read_text(encoding="utf-8")}

    def filesystem_write(self, path: str, content: str) -> Dict[str, Any]:
        target = self._safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        backup = ""
        if target.exists():
            backup_path = target.with_suffix(target.suffix + ".backup")
            backup_path.write_bytes(target.read_bytes())
            backup = str(backup_path)
        fd, temp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=str(target.parent))
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        return {"ok": True, "path": str(target), "backup": backup, "bytes": target.stat().st_size}

    def filesystem_list(self, directory: str = ".", max_entries: int = 200) -> Dict[str, Any]:
        root = self._safe_path(directory)
        if not root.is_dir():
            return {"ok": False, "error": "directory_not_found", "path": str(root)}
        entries: List[Dict[str, Any]] = []
        for path in sorted(root.rglob("*")):
            if len(entries) >= max_entries:
                break
            if ".git" in path.parts:
                continue
            rel = path.relative_to(self.workspace_root).as_posix()
            entries.append({"path": rel, "type": "dir" if path.is_dir() else "file", "size": path.stat().st_size if path.is_file() else 0})
        return {"ok": True, "root": str(root), "entries": entries}

    def bash_execute(self, command: str, timeout: int | None = None) -> Dict[str, Any]:
        command = str(command or "").strip()
        if not command:
            return {"ok": False, "error": "empty_command"}
        for pattern in DENIED_COMMAND_PATTERNS:
            if pattern.search(command):
                return {"ok": False, "error": "denied_command", "pattern": pattern.pattern}
        limit = min(max(int(timeout or self.command_timeout_seconds), 1), 300)
        completed = subprocess.run(
            command,
            cwd=str(self.workspace_root),
            shell=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=limit,
        )
        if completed.returncode == 0:
            status_ok = True
        else:
            status_ok = False
        return {
            "ok": status_ok,
            "command": command,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if name == "filesystem_read":
                return self.filesystem_read(str(arguments.get("path") or ""))
            if name == "filesystem_write":
                return self.filesystem_write(str(arguments.get("path") or ""), str(arguments.get("content") or ""))
            if name == "filesystem_list":
                return self.filesystem_list(str(arguments.get("dir") or arguments.get("directory") or "."))
            if name == "bash_execute":
                return self.bash_execute(str(arguments.get("command") or ""), arguments.get("timeout"))
            return {"ok": False, "error": "unknown_tool", "tool": name}
        except subprocess.TimeoutExpired as exc:
            return {"ok": False, "error": "command_timeout", "command": str(exc.cmd), "timeout": exc.timeout}
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except OSError as exc:
            return {"ok": False, "error": "os_error", "detail": str(exc)}
