from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from permission_manager import is_command_allowed, log_action, resolve_safe_path, result


PROJECT_ROOT = Path(__file__).resolve().parent


def _ok(action: str, value: Any = "", **extra: Any) -> Dict[str, Any]:
    payload = result(True, value, "", **extra)
    log_action(action, True, payload)
    return payload


def _fail(action: str, error: str, **extra: Any) -> Dict[str, Any]:
    payload = result(False, "", error, **extra)
    log_action(action, False, payload)
    return payload


def _safe(path: str | Path, *, must_exist: bool = False, workspace_root: str | Path | None = None) -> Path:
    return resolve_safe_path(path, base_root=workspace_root or PROJECT_ROOT, must_exist=must_exist)


def read_file(path: str, workspace_root: str | Path | None = None) -> Dict[str, Any]:
    try:
        target = _safe(path, must_exist=True, workspace_root=workspace_root)
        if not target.is_file():
            return _fail("read_file", "not_a_file", path=str(target))
        return _ok("read_file", target.read_text(encoding="utf-8", errors="replace"), path=str(target))
    except Exception as exc:
        return _fail("read_file", str(exc), path=str(path))


def backup_file(path: str, workspace_root: str | Path | None = None) -> Dict[str, Any]:
    try:
        target = _safe(path, must_exist=True, workspace_root=workspace_root)
        if not target.is_file():
            return _fail("backup_file", "not_a_file", path=str(target))
        backup = target.with_name(target.name + ".backup")
        counter = 1
        while backup.exists():
            backup = target.with_name(f"{target.name}.backup.{counter}")
            counter += 1
        shutil.copy2(target, backup)
        return _ok("backup_file", str(backup), path=str(target), backup=str(backup))
    except Exception as exc:
        return _fail("backup_file", str(exc), path=str(path))


def write_file(path: str, content: str, workspace_root: str | Path | None = None) -> Dict[str, Any]:
    try:
        target = _safe(path, workspace_root=workspace_root)
        backup = ""
        if target.exists():
            backup_result = backup_file(str(target), workspace_root=workspace_root)
            if not backup_result.get("success"):
                return backup_result
            backup = str(backup_result.get("result") or "")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(str(content), encoding="utf-8", newline="")
        os.replace(tmp, target)
        return _ok("write_file", True, path=str(target), backup=backup, bytes=target.stat().st_size)
    except Exception as exc:
        return _fail("write_file", str(exc), path=str(path))


def edit_file(path: str, old_text: str, new_text: str, workspace_root: str | Path | None = None) -> Dict[str, Any]:
    try:
        target = _safe(path, must_exist=True, workspace_root=workspace_root)
        text = target.read_text(encoding="utf-8", errors="replace")
        if old_text not in text:
            return _fail("edit_file", "old_text_not_found", path=str(target))
        backup_result = backup_file(str(target), workspace_root=workspace_root)
        if not backup_result.get("success"):
            return backup_result
        target.write_text(text.replace(old_text, new_text, 1), encoding="utf-8", newline="")
        return _ok("edit_file", True, path=str(target), backup=backup_result.get("result"))
    except Exception as exc:
        return _fail("edit_file", str(exc), path=str(path))


def append_file(path: str, content: str, workspace_root: str | Path | None = None) -> Dict[str, Any]:
    try:
        target = _safe(path, workspace_root=workspace_root)
        backup = ""
        if target.exists():
            backup_result = backup_file(str(target), workspace_root=workspace_root)
            if not backup_result.get("success"):
                return backup_result
            backup = str(backup_result.get("result") or "")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8", newline="") as handle:
            handle.write(str(content))
        return _ok("append_file", True, path=str(target), backup=backup, bytes=target.stat().st_size)
    except Exception as exc:
        return _fail("append_file", str(exc), path=str(path))


def delete_file(path: str, workspace_root: str | Path | None = None) -> Dict[str, Any]:
    try:
        target = _safe(path, must_exist=True, workspace_root=workspace_root)
        if not target.is_file():
            return _fail("delete_file", "not_a_file", path=str(target))
        backup_result = backup_file(str(target), workspace_root=workspace_root)
        if not backup_result.get("success"):
            return backup_result
        target.unlink()
        return _ok("delete_file", True, path=str(target), backup=backup_result.get("result"))
    except Exception as exc:
        return _fail("delete_file", str(exc), path=str(path))


def create_directory(path: str, workspace_root: str | Path | None = None) -> Dict[str, Any]:
    try:
        target = _safe(path, workspace_root=workspace_root)
        target.mkdir(parents=True, exist_ok=True)
        return _ok("create_directory", True, path=str(target))
    except Exception as exc:
        return _fail("create_directory", str(exc), path=str(path))


def list_directory(path: str = ".", workspace_root: str | Path | None = None) -> Dict[str, Any]:
    try:
        target = _safe(path, must_exist=True, workspace_root=workspace_root)
        if not target.is_dir():
            return _fail("list_directory", "not_a_directory", path=str(target))
        entries: List[Dict[str, Any]] = []
        root = Path(workspace_root).expanduser().resolve() if workspace_root else PROJECT_ROOT
        for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            entries.append({
                "name": child.name,
                "path": child.resolve().relative_to(root).as_posix(),
                "type": "directory" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else 0,
            })
        return _ok("list_directory", entries, path=str(target))
    except Exception as exc:
        return _fail("list_directory", str(exc), path=str(path))


def file_exists(path: str, workspace_root: str | Path | None = None) -> Dict[str, Any]:
    try:
        target = _safe(path, workspace_root=workspace_root)
        return _ok("file_exists", target.exists(), path=str(target))
    except Exception as exc:
        return _fail("file_exists", str(exc), path=str(path))


def search_in_files(directory: str, pattern: str, workspace_root: str | Path | None = None) -> Dict[str, Any]:
    try:
        root = _safe(directory, must_exist=True, workspace_root=workspace_root)
        if not root.is_dir():
            return _fail("search_in_files", "not_a_directory", path=str(root))
        matches: List[Dict[str, Any]] = []
        workspace = Path(workspace_root).expanduser().resolve() if workspace_root else PROJECT_ROOT
        for file_path in root.rglob("*"):
            if len(matches) >= 200:
                break
            if not file_path.is_file() or ".git" in file_path.parts or file_path.suffix.lower() in {".pyc", ".png", ".jpg", ".zip", ".exe"}:
                continue
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            for line_no, line in enumerate(text.splitlines(), start=1):
                if pattern in line:
                    matches.append({"path": file_path.relative_to(workspace).as_posix(), "line": line_no, "text": line[:300]})
                    break
        return _ok("search_in_files", matches, directory=str(root), pattern=pattern)
    except Exception as exc:
        return _fail("search_in_files", str(exc), directory=str(directory), pattern=pattern)


def get_file_info(path: str, workspace_root: str | Path | None = None) -> Dict[str, Any]:
    try:
        target = _safe(path, must_exist=True, workspace_root=workspace_root)
        stat = target.stat()
        return _ok("get_file_info", {
            "path": str(target),
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "is_file": target.is_file(),
            "is_directory": target.is_dir(),
        })
    except Exception as exc:
        return _fail("get_file_info", str(exc), path=str(path))


def run_command(command: str, workspace_root: str | Path | None = None, timeout: int = 30) -> Dict[str, Any]:
    allowed = is_command_allowed(command)
    if not allowed.get("success"):
        return _fail("run_command", str(allowed.get("error")), command=command)
    try:
        root = Path(workspace_root).expanduser().resolve() if workspace_root else PROJECT_ROOT
        root = _safe(".", must_exist=True, workspace_root=root)
        completed = subprocess.run(
            command,
            cwd=str(root),
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(1, min(int(timeout), 300)),
        )
        payload = {
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        if completed.returncode != 0:
            return _fail("run_command", "command_failed", command=command, **payload)
        return _ok("run_command", payload, command=command)
    except subprocess.TimeoutExpired as exc:
        return _fail("run_command", "command_timeout", command=command, timeout=exc.timeout)
    except Exception as exc:
        return _fail("run_command", str(exc), command=command)


def run_python(code: str, workspace_root: str | Path | None = None, timeout: int = 30) -> Dict[str, Any]:
    try:
        root = Path(workspace_root).expanduser().resolve() if workspace_root else PROJECT_ROOT
        root = _safe(".", must_exist=True, workspace_root=root)
        completed = subprocess.run(
            [sys.executable, "-c", str(code or "")],
            cwd=str(root),
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(1, min(int(timeout), 300)),
        )
        payload = {
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        if completed.returncode != 0:
            return _fail("run_python", "python_failed", **payload)
        return _ok("run_python", payload)
    except subprocess.TimeoutExpired as exc:
        return _fail("run_python", "python_timeout", timeout=exc.timeout)
    except Exception as exc:
        return _fail("run_python", str(exc))


def execute_tool(tool: str, params: Dict[str, Any], workspace_root: str | Path | None = None) -> Dict[str, Any]:
    params = dict(params or {})
    if tool in {"read_file", "file_exists", "get_file_info", "backup_file", "delete_file"}:
        return globals()[tool](params.get("path", ""), workspace_root=workspace_root)
    if tool == "write_file":
        return write_file(params.get("path", ""), params.get("content", ""), workspace_root=workspace_root)
    if tool == "edit_file":
        return edit_file(params.get("path", ""), params.get("old_text", ""), params.get("new_text", ""), workspace_root=workspace_root)
    if tool == "append_file":
        return append_file(params.get("path", ""), params.get("content", ""), workspace_root=workspace_root)
    if tool == "create_directory":
        return create_directory(params.get("path", ""), workspace_root=workspace_root)
    if tool == "list_directory":
        return list_directory(params.get("path", params.get("directory", ".")), workspace_root=workspace_root)
    if tool == "search_in_files":
        return search_in_files(params.get("directory", "."), params.get("pattern", ""), workspace_root=workspace_root)
    if tool == "run_command":
        return run_command(params.get("command", ""), workspace_root=workspace_root, timeout=int(params.get("timeout", 30)))
    if tool == "run_python":
        return run_python(params.get("code", ""), workspace_root=workspace_root, timeout=int(params.get("timeout", 30)))
    return _fail("execute_tool", "unknown_tool", tool=tool)
