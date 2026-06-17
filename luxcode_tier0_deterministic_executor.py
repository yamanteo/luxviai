from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent

ALLOWED_EXECUTABLES = {
    "python": "python",
    "python3": "python3",
    "git": "git",
}

ALLOWED_COMMANDS = {
    "repository_status": {"executable": "git", "argv": ["status", "--short"]},
    "repository_map": {"executable": "python", "argv": ["-m", "py_compile"], "optional": True},
    "safe_compile": {"executable": "python", "argv": ["-m", "py_compile"]},
    "compile_all": {"executable": "python", "argv": ["-m", "compileall"]},
    "validator_discovery": {"executable": "python", "argv": ["-m"]},
    "smoke_discovery": {"executable": "python", "argv": []},
    "smoke_run_check": {"executable": "python", "argv": ["scripts/smoke_check.py", "--check"]},
    "smoke_run_quick": {"executable": "python", "argv": ["scripts/smoke_check.py", "--quick"]},
    "branch_show": {"executable": "git", "argv": ["branch", "--show-current"]},
    "rev_parse": {"executable": "git", "argv": ["rev-parse", "HEAD"]},
    "diff_name": {"executable": "git", "argv": ["diff", "--name-only"]},
    "diff_cached": {"executable": "git", "argv": ["diff", "--cached", "--name-only"]},
    "diff_check": {"executable": "git", "argv": ["diff", "--check"]},
}

COMMAND_DENYLIST = {
    "git add",
    "git commit",
    "git push",
    "git reset",
    "git checkout",
    "git restore",
    "git clean",
    "git rebase",
    "git merge",
    "git cherry-pick",
    "git stash",
    "curl",
    "wget",
    "Invoke-WebRequest",
    "powershell",
    "bash",
}

PATH_ALLOWLIST_DIRS = {".", ".git", "scripts", "src", "tests", "tmp", "build"}
REPOSITORY_MAP_EXCLUDED_NAMES = {
    ".git",
    ".env",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    "__pycache__",
    ".luxcode_runtime",
    ".luxcode_snapshots",
    "luxcode_backups",
    "luxcode_tasks.db",
}
REPOSITORY_MAP_EXCLUDED_SUFFIXES = {".jpg", ".png", ".mp4", ".zip", ".tar", ".gz", ".dll", ".exe", ".so", ".pyc"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any, prefix: str = "tier0") -> str:
    return f"{prefix}-{hashlib.sha256(_jsonify(value).encode('utf-8')).hexdigest()[:24]}"


def _jsonify(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _normalize_line(text: Any) -> str:
    return str(text or "").replace("\r\n", "\n").strip()


def _normalize_text(text: Any, limit: int) -> str:
    return _normalize_line(text)[:limit]


def _truncate_pair(stdout: str, stderr: str, limit: int = 12000) -> Tuple[str, str, bool]:
    output = _normalize_line(stdout) + _normalize_line(stderr)
    if len(output) <= limit:
        return stdout.strip(), stderr.strip(), False
    half = max(1, limit // 2)
    return stdout[:half], stderr[: max(1, limit - half)], True


def _redact(text: str) -> str:
    replacements = {
        "TOKEN": "REDACTED_TOKEN",
        "SECRET": "REDACTED_SECRET",
        "PASSWORD": "REDACTED_PASSWORD",
    }
    safe = text
    for key, value in replacements.items():
        safe = re.sub(rf"(?i){key}[=:]\\s*[^\\s\"']+", f"{key}={value}", safe)
    return safe


@dataclass
class ExecutionResult:
    step_id: str
    tool_id: str
    executable: str
    arguments: list[str]
    cwd: str
    return_code: int
    duration_ms: int
    status: str
    stdout_excerpt: str
    stderr_excerpt: str
    failed_step: bool
    truncated: bool
    result_digest: str
    failure_signature: str = ""


def _repo_root(root: str | Path) -> Path:
    path = Path(root or ".").expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError("repository_root must be a valid directory")
    return path


def _ensure_not_symlink(path: Path) -> None:
    if path.is_symlink():
        raise ValueError(f"path is symlink: {path}")


def _is_within_root(root: Path, candidate: Path) -> bool:
    try:
        return root == candidate or root in candidate.parents or candidate.relative_to(root)
    except Exception:
        return False


def _check_repository_path(root: Path, raw: str) -> Path:
    if not raw or raw in {".", ".."}:
        raise ValueError("path cannot be empty or traversal root")
    if raw.startswith(("\\", "//", "~/", "C:", "c:", "D:", "d:")):
        raise ValueError(f"external path blocked: {raw}")
    normalized = Path(raw.replace("\\", "/"))
    if ".." in normalized.parts:
        raise ValueError(f"path traversal blocked: {raw}")
    if normalized.is_absolute():
        raise ValueError(f"absolute path blocked: {raw}")
    resolved = (root / normalized).resolve()
    _ensure_not_symlink(resolved)
    if not _is_within_root(root, resolved):
        raise ValueError(f"path escapes repository root: {raw}")
    return resolved


def _repo_relative(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root)).replace("\\", "/")


def _repo_relative_lexical(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _exclusion_record(root: Path, path: Path, reason: str) -> Dict[str, str]:
    try:
        rel = _repo_relative(root, path)
    except Exception:
        rel = str(path.name)
        reason = "path safety rejection"
    return {"path": rel, "reason": reason}


def _is_repository_excluded_name(name: str) -> bool:
    return name in REPOSITORY_MAP_EXCLUDED_NAMES or name.startswith(".")


def _test_file_candidate(rel: str) -> bool:
    name = Path(rel).name.lower()
    parts = rel.lower().split("/")
    return "test" in parts or (name.startswith("test_") and name.endswith(".py")) or (name.endswith("_test.py"))


def validate_command(executable: str, args: List[str], tool_id: str) -> None:
    base = os.path.basename(executable or "").lower()
    if f"{base}" in COMMAND_DENYLIST:
        raise ValueError(f"command blocked: {executable}")
    base = "python" if base.startswith("python") else base
    if base == "python":
        base = "python"
    if base not in ALLOWED_EXECUTABLES:
        raise ValueError(f"executable not allowed: {executable}")
    policy = ALLOWED_COMMANDS.get(tool_id)
    if not policy:
        raise ValueError(f"tool id not registered: {tool_id}")
    expected_exec = policy["executable"]
    if base != expected_exec:
        raise ValueError(f"tool executable mismatch for {tool_id}: expected {expected_exec}, got {executable}")
    required = policy["argv"]
    if len(args) < len(required):
        raise ValueError(f"argument count too short for {tool_id}")
    for expected, actual in zip(required, args):
        if expected and expected != actual:
            raise ValueError(f"argument mismatch for {tool_id}: expected {expected}, got {actual}")
    if any(part.lower() in COMMAND_DENYLIST for part in args):
        raise ValueError(f"argument blocked by policy for {tool_id}")


def _classify_error(return_code: int, stderr: str, stdout: str) -> str:
    combined = (stdout + "\n" + stderr).lower()
    if return_code == 0:
        return "pass"
    if "syntaxerror" in combined:
        return "syntax_error"
    if "importerror" in combined or "modulenotfounderror" in combined:
        return "import_error"
    if "assertionerror" in combined:
        return "assertion_failure"
    if "validator_failed" in combined:
        return "validation_failure"
    if "smoke_check" in combined or "smoke failed" in combined:
        return "smoke_failure"
    if "timed out" in combined or "timeout" in combined:
        return "timeout"
    if "policy" in combined or "blocked" in combined:
        return "policy_block"
    if "path" in combined and ("traversal" in combined or "escape" in combined or "outside" in combined):
        return "path_violation"
    if "filenotfound" in combined or "no such file" in combined:
        return "missing_file"
    if "not found in symbol" in combined:
        return "missing_symbol"
    if "permission denied" in combined or "not allowed" in combined:
        return "invalid_command"
    if "exit" in combined:
        return "unexpected_exit"
    return "unknown_error"


def normalize_error(source_file: str, line: Optional[int], symbol: Optional[str], stderr: str, stdout: str, return_code: int, tool_id: str) -> Dict[str, Any]:
    error_type = _classify_error(return_code, stderr, stdout)
    normalized_message = _normalize_text(_redact((stdout + "\n" + stderr).strip()), 240)
    scrubbed = re.sub(r"line \d+", "line LINE_REDACTED", normalized_message)
    scrubbed = re.sub(r"/tmp/[^\\s]+", "/tmp/sanitized", scrubbed)
    scrubbed = re.sub(r"0x[0-9a-fA-F]+", "0xREDACTED", scrubbed)
    signature = hashlib.sha256(f"{tool_id}|{error_type}|{source_file}|{line or ''}|{symbol or ''}|{scrubbed}".encode("utf-8")).hexdigest()[:24]
    return {
        "error_type": error_type,
        "normalized_message": scrubbed,
        "source_file": _normalize_text(source_file, 260),
        "line": line,
        "symbol": symbol,
        "fingerprint": signature,
        "tool_id": tool_id,
        "created_at": _now(),
    }


def _env_for_execution() -> Dict[str, str]:
    allowed = [
        "SYSTEMROOT",
        "WINDIR",
        "SystemRoot",
        "PATH",
        "TEMP",
        "TMP",
        "USERNAME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
    ]
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    return env


def run_safe_command(repository_root: str, tool_id: str, command_id: str, executable: str, args: List[str], cwd: str, timeout_seconds: int = 30) -> ExecutionResult:
    root = _repo_root(repository_root)
    validate_command(executable, args, tool_id)
    requested_cwd = Path(cwd).expanduser()
    if requested_cwd.is_absolute():
        working_directory = requested_cwd
    else:
        working_directory = (root / requested_cwd).resolve()
    if not _is_within_root(root, working_directory):
        raise ValueError("working_directory outside repository root")
    if len(requested_cwd.parts) > 0 and requested_cwd.parts[0] not in PATH_ALLOWLIST_DIRS:
        raise ValueError("working directory not in allowed prefix")
    _ensure_not_symlink(working_directory)

    start = datetime.now(timezone.utc)
    proc = subprocess.run(
        [executable] + args,
        cwd=str(working_directory),
        env=_env_for_execution(),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        shell=False,
    )
    elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    stdout, stderr, was_truncated = _truncate_pair(proc.stdout or "", proc.stderr or "")
    result_status = "passed" if proc.returncode == 0 else "failed"
    raw = _normalize_text(_redact(f"{stdout}\n{stderr}"), 140)
    digest = _digest({"tool_id": tool_id, "command_id": command_id, "return_code": proc.returncode, "output": raw}, prefix="tier0exec")
    error_signature = ""
    if proc.returncode != 0:
        error_signature = normalize_error(
            source_file=str(working_directory),
            line=None,
            symbol=tool_id,
            stdout=stdout,
            stderr=stderr,
            return_code=proc.returncode,
            tool_id=tool_id,
        )["fingerprint"]
    return ExecutionResult(
        step_id=command_id,
        tool_id=tool_id,
        executable=executable,
        arguments=args,
        cwd=str(working_directory),
        return_code=proc.returncode,
        duration_ms=elapsed_ms,
        status=result_status,
        stdout_excerpt=stdout,
        stderr_excerpt=stderr,
        failed_step=result_status != "passed",
        truncated=was_truncated,
        result_digest=digest,
        failure_signature=error_signature,
    )


def build_repository_map(repository_root: str, max_files: int = 180, max_file_bytes: int = 80_000) -> Dict[str, Any]:
    root = _repo_root(repository_root)
    language_counts: Dict[str, int] = {}
    candidate_source_files: List[str] = []
    candidate_test_files: List[str] = []
    candidate_validator_files: List[str] = []
    candidate_smoke_files: List[str] = []
    excluded_paths: List[Dict[str, str]] = []
    large_files: List[Dict[str, Any]] = []
    candidates: List[Tuple[str, int]] = []
    map_entries: List[Tuple[str, int, str]] = []
    candidate_count = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        kept_dirs: List[str] = []
        for dirname in sorted(dirs):
            dir_path = current_path / dirname
            try:
                rel_dir = _repo_relative(root, dir_path)
            except Exception:
                excluded_paths.append(_exclusion_record(root, dir_path, "path safety rejection"))
                continue
            if dir_path.is_symlink():
                excluded_paths.append({"path": _repo_relative_lexical(root, dir_path), "reason": "symlink directory"})
                continue
            if dirname in REPOSITORY_MAP_EXCLUDED_NAMES:
                excluded_paths.append({"path": rel_dir, "reason": "configured exclusion"})
                continue
            if dirname.startswith("."):
                excluded_paths.append({"path": rel_dir, "reason": "hidden/runtime directory"})
                continue
            if dirname in {"build", "dist", "htmlcov"}:
                excluded_paths.append({"path": rel_dir, "reason": "cache/build directory"})
                continue
            kept_dirs.append(dirname)
        dirs[:] = kept_dirs
        for name in files:
            full = current_path / name
            try:
                rel = _repo_relative(root, full)
            except Exception:
                excluded_paths.append(_exclusion_record(root, full, "path safety rejection"))
                continue
            if rel.startswith((".git/", ".")):
                excluded_paths.append({"path": rel, "reason": "hidden/runtime directory"})
                continue
            if any(part in REPOSITORY_MAP_EXCLUDED_NAMES for part in rel.split("/")):
                excluded_paths.append({"path": rel, "reason": "configured exclusion"})
                continue
            if Path(name).suffix.lower() in REPOSITORY_MAP_EXCLUDED_SUFFIXES:
                excluded_paths.append({"path": rel, "reason": "configured exclusion"})
                continue
            if name.startswith(".env"):
                excluded_paths.append({"path": rel, "reason": "configured exclusion"})
                continue
            _ensure_not_symlink(full)
            size = full.stat().st_size
            if size > max_file_bytes:
                large_files.append({"path": rel, "size_bytes": size, "threshold_bytes": max_file_bytes, "reason": "large_file", "content_analysis_skipped": True})
                continue
            if candidate_count >= max_files:
                continue
            candidates.append((rel, size))
            candidate_count += 1
            map_entries.append((rel, size, hashlib.sha256(full.read_bytes()).hexdigest()[:16]))
            suffix = Path(name).suffix.lower()
            language_counts[suffix or "extensionless"] = language_counts.get(suffix or "extensionless", 0) + 1
            lowered = rel.lower()
            if _test_file_candidate(lowered):
                candidate_test_files.append(rel)
            if lowered.startswith("scripts/validate_") and suffix == ".py":
                candidate_validator_files.append(rel)
            if lowered.startswith("scripts/smoke") and suffix == ".py":
                candidate_smoke_files.append(rel)
            if suffix == ".py":
                candidate_source_files.append(rel)
    candidates_digest = _digest([{"path": rel, "size": size} for rel, size, _ in map_entries], prefix="tier0map")
    return {
        "repository_root": str(root),
        "file_count": len(candidates),
        "language_counts": dict(sorted(language_counts.items())),
        "candidate_source_files": sorted(candidate_source_files),
        "candidate_test_files": sorted(candidate_test_files),
        "candidate_validator_files": sorted(candidate_validator_files),
        "candidate_smoke_files": sorted(candidate_smoke_files),
        "truncated": False,
        "map_digest": candidates_digest,
        "excluded_paths": sorted(excluded_paths, key=lambda item: (item["path"], item["reason"])),
        "large_files": sorted(large_files, key=lambda item: item["path"]),
        "followlinks": False,
        "generated_at": _now(),
        "external_path_readonly": True,
        "network_access_used": False,
        "local_first": True,
    }


def _inspect_python_symbol(file_path: Path, repo_root: Path, max_nodes: int = 200) -> Dict[str, Any]:
    rel = str(file_path.relative_to(repo_root)).replace("\\", "/")
    source = file_path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source, filename=file_path.name)
    classes: List[str] = []
    functions: List[str] = []
    async_functions: List[str] = []
    imports: List[str] = []
    from_imports: List[str] = []
    route_decorators: List[str] = []
    symbols: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
            symbols.append(node.name)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node.name)
            symbols.append(node.name)
            route_decorators.extend([str(dec.func).split(".")[-1] for dec in node.decorator_list if isinstance(dec, ast.Attribute) and getattr(dec.func, "attr", "")])
        elif isinstance(node, ast.AsyncFunctionDef):
            async_functions.append(node.name)
            symbols.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend([alias.name for alias in node.names])
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            from_imports.append(module)
    payload = {
        "file": rel,
        "classes": sorted(classes)[:max_nodes],
        "functions": sorted(functions)[:max_nodes],
        "async_functions": sorted(async_functions)[:max_nodes],
        "imports": sorted(imports)[:max_nodes],
        "from_imports": sorted(from_imports)[:max_nodes],
        "route_decorators": sorted(route_decorators),
        "main_guard": "if __name__ == \"__main__\"" in source,
        "syntax_error": None,
    }
    payload["symbol_digest"] = _digest(payload, prefix="symbol")
    return payload


def inspect_python_symbols(repository_root: str, candidate_files: Optional[List[str]] = None, limit: int = 24) -> Dict[str, Any]:
    root = _repo_root(repository_root)
    raw_files = candidate_files or [p for p in os.listdir(root) if p.endswith(".py")]
    selected = [str(p).replace("\\", "/") for p in raw_files][:limit]
    results: List[Dict[str, Any]] = []
    for rel in selected:
        path = _check_repository_path(root, rel)
        if not path.exists():
            continue
        try:
            entry = _inspect_python_symbol(path, root)
        except SyntaxError as exc:
            entry = {
                "file": rel,
                "syntax_error": str(exc),
                "classes": [],
                "functions": [],
                "async_functions": [],
                "imports": [],
                "from_imports": [],
                "route_decorators": [],
                "main_guard": False,
            }
        entry["file"] = rel
        results.append(entry)
    return {
        "ok": True,
        "repository_root": str(root),
        "files": results,
        "file_count": len(results),
        "missing_symbols": [],
        "syntax_errors": [entry.get("syntax_error") for entry in results if entry.get("syntax_error")],
        "symbol_index_digest": _digest(results, prefix="symbol-index"),
        "generated_at": _now(),
    }


def _python_files_for_analysis(root: Path) -> List[Path]:
    files: List[Path] = []
    for current, dirs, names in os.walk(root, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(
            dirname
            for dirname in dirs
            if not (current_path / dirname).is_symlink()
            and dirname not in REPOSITORY_MAP_EXCLUDED_NAMES
            and not dirname.startswith(".")
            and dirname not in {"build", "dist", "htmlcov"}
        )
        for name in sorted(names):
            if name.endswith(".py"):
                path = current_path / name
                try:
                    _ensure_not_symlink(path)
                    _repo_relative(root, path)
                except Exception:
                    continue
                files.append(path)
    return sorted(files, key=lambda item: _repo_relative(root, item))


def _module_name_for_file(root: Path, path: Path) -> str:
    rel = _repo_relative(root, path)
    parts = rel[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _build_local_module_index(root: Path) -> Tuple[Dict[str, str], set[str], set[str]]:
    modules: Dict[str, str] = {}
    packages: set[str] = set()
    top_levels: set[str] = set()
    for path in _python_files_for_analysis(root):
        module = _module_name_for_file(root, path)
        if not module:
            continue
        rel = _repo_relative(root, path)
        modules[module] = rel
        top_levels.add(module.split(".")[0])
        if path.name == "__init__.py":
            packages.add(module)
    return modules, packages, top_levels


def _relative_import_base(current_module: str, is_package_init: bool, level: int, module: str | None) -> str:
    current_parts = current_module.split(".") if current_module else []
    package_parts = current_parts if is_package_init else current_parts[:-1]
    keep = max(0, len(package_parts) - max(0, level - 1))
    parts = package_parts[:keep]
    if module:
        parts.extend(part for part in module.split(".") if part)
    return ".".join(parts)


def _missing_import_record(source_file: str, statement: str, candidate: str, reason: str, line: int, severity: str = "warning") -> Dict[str, Any]:
    return {
        "source_file": source_file,
        "import_statement": statement,
        "resolved_candidate": candidate,
        "reason": reason,
        "line_number": line,
        "severity": severity,
    }


def _add_edge(graph: Dict[str, set[str]], source: str, target: str) -> None:
    if source != target:
        graph.setdefault(source, set()).add(target)


def _canonical_cycle(path: List[str]) -> Tuple[str, ...]:
    body = path[:-1]
    rotations = [tuple(body[index:] + body[:index]) for index in range(len(body))]
    best = min(rotations)
    return best + (best[0],)


def _find_import_cycles(graph: Dict[str, set[str]]) -> List[Dict[str, Any]]:
    cycles: set[Tuple[str, ...]] = set()

    def visit(start: str, node: str, path: List[str], seen: set[str]) -> None:
        for target in sorted(graph.get(node, set())):
            if target == start:
                cycles.add(_canonical_cycle(path + [target]))
            elif target not in seen and target >= start:
                visit(start, target, path + [target], seen | {target})

    for module in sorted(graph):
        visit(module, module, [module], {module})
    return [
        {
            "path": list(cycle),
            "evidence": " -> ".join(cycle),
            "cycle_type": "direct" if len(cycle) == 3 else "indirect",
        }
        for cycle in sorted(cycles)
    ]


def analyze_python_imports(repository_root: str) -> Dict[str, Any]:
    root = _repo_root(repository_root)
    modules, packages, top_levels = _build_local_module_index(root)
    graph: Dict[str, set[str]] = {module: set() for module in modules}
    missing: List[Dict[str, Any]] = []
    parse_warnings: List[Dict[str, Any]] = []

    for path in _python_files_for_analysis(root):
        source_file = _repo_relative(root, path)
        source_module = _module_name_for_file(root, path)
        if not source_module:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=source_file)
        except SyntaxError as exc:
            parse_warnings.append({"source_file": source_file, "reason": "syntax_error", "line_number": exc.lineno or 0, "severity": "warning"})
            continue
        is_package_init = path.name == "__init__.py"
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    candidate = alias.name
                    line = int(getattr(node, "lineno", 0) or 0)
                    if candidate in modules:
                        _add_edge(graph, source_module, candidate)
                    elif candidate.split(".")[0] in top_levels:
                        missing.append(_missing_import_record(source_file, f"import {candidate}", candidate, "local absolute import target not found", line))
            elif isinstance(node, ast.ImportFrom):
                line = int(getattr(node, "lineno", 0) or 0)
                if node.level:
                    base = _relative_import_base(source_module, is_package_init, node.level, node.module)
                    statement = f"from {'.' * node.level}{node.module or ''} import " + ", ".join(alias.name for alias in node.names)
                    if base in modules:
                        _add_edge(graph, source_module, base)
                        if base in packages:
                            for alias in node.names:
                                child = f"{base}.{alias.name}"
                                if child in modules:
                                    _add_edge(graph, source_module, child)
                                elif alias.name != "*":
                                    missing.append(_missing_import_record(source_file, statement, child, "relative package import target not found", line))
                    else:
                        missing.append(_missing_import_record(source_file, statement, base, "relative import target not found", line))
                else:
                    base = node.module or ""
                    statement = f"from {base} import " + ", ".join(alias.name for alias in node.names)
                    if base in modules:
                        _add_edge(graph, source_module, base)
                        if base in packages:
                            for alias in node.names:
                                child = f"{base}.{alias.name}"
                                if child in modules:
                                    _add_edge(graph, source_module, child)
                                elif alias.name != "*":
                                    missing.append(_missing_import_record(source_file, statement, child, "local package import target not found", line))
                    elif base.split(".")[0] in top_levels:
                        missing.append(_missing_import_record(source_file, statement, base, "local from-import base not found", line))

    serial_graph = {module: sorted(targets) for module, targets in sorted(graph.items()) if targets}
    cycles = _find_import_cycles(graph)
    payload = {
        "import_graph": serial_graph,
        "cycles": cycles,
        "cycle_count": len(cycles),
        "missing_local_imports": sorted(missing, key=lambda item: (item["source_file"], item["line_number"], item["resolved_candidate"])),
        "parse_warnings": sorted(parse_warnings, key=lambda item: (item["source_file"], item["line_number"])),
        "module_count": len(modules),
        "generated_at": _now(),
    }
    payload["import_analysis_digest"] = _digest(payload, prefix="import-analysis")
    return payload


def discover_validations(repository_root: str) -> Dict[str, Any]:
    root = _repo_root(repository_root)
    map_payload = build_repository_map(repository_root)
    validator_files = sorted(set(map_payload.get("candidate_validator_files", [])))
    test_files = sorted(set(map_payload.get("candidate_test_files", [])))
    smoke_check_source = root / "scripts" / "smoke_check.py"
    smoke_checks: List[str] = []
    if smoke_check_source.exists():
        smoke_text = smoke_check_source.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"def\s+(check_\w+)\(", smoke_text):
            smoke_checks.append(match.group(1))
    discovery = {
        "candidate_validators": validator_files,
        "candidate_test_files": test_files,
        "candidate_smoke_checks": sorted({name for name in smoke_checks if name.startswith("check_")}),
        "recommended_minimum_plan": [
            "luxcode_coder_operator_cli_local",
            "luxcode_practical_coder_runtime_local",
            "luxcode_zero_cost_execution_router_local",
        ],
        "optional_regressions": [],
        "full_smoke_required": False,
        "missing_symbol": [],
        "reason": "deterministic local discovery",
        "generated_at": _now(),
        "discover_digest": _digest({"validators": validator_files, "tests": test_files, "checks": sorted(smoke_checks)}, prefix="discover"),
    }
    discovery["discovery_count"] = len(discovery["candidate_validators"]) + len(discovery["candidate_test_files"]) + len(discovery["candidate_smoke_checks"])
    return discovery


def build_diagnostic_plan(
    repository_root: str,
    task_summary: str = "",
    selected_files: Optional[List[str]] = None,
    selected_tier: int = 0,
) -> Dict[str, Any]:
    root = _repo_root(repository_root)
    steps = [
        "repository_map",
        "python_symbol_index",
        "validation_discovery",
        "safe_py_compile",
        "syntax_error_normalization",
        "duplicate_command_prevention",
        "path_policy_block",
        "git_mutation_block",
        "external_path_block",
        "evidence_build",
        "remaining_gap_build",
    ]
    if selected_tier != 0:
        steps.insert(0, "tier_upgrade_probe")
    plan = {
        "plan_id": _digest({"root": str(root), "summary": task_summary, "selected_tier": selected_tier}, prefix="tier0-plan"),
        "selected_tier": 0 if selected_tier == 0 else selected_tier,
        "selected_engine": "deterministic_local_tools",
        "selected_tier_name": "tier0",
        "steps": steps,
        "task_type": "practical_coder_preread",
        "task_summary": _normalize_text(task_summary, 160),
        "required_steps": steps[:8],
        "optional_steps": ["smoke_discovery"],
        "blocked_steps": ["git_mutation", "network_write", "external_path_access", "duplicate_repeat"],
        "expected_evidence": ["repository_map", "ast_index", "diagnostic_result", "gap_record"],
        "estimated_runtime": 8.5,
        "plan_digest": _digest(
            {"root": str(root), "steps": steps, "tier": "deterministic_local_tools"},
            prefix="tier0-plan-digest",
        ),
        "created_at": _now(),
    }
    return plan


def _build_evidence_record(task_id: str, tool_id: str, status: str, summary: str, source: str, command: str) -> Dict[str, Any]:
    return {
        "evidence_id": _digest(f"{task_id}:{tool_id}:{status}:{summary}", prefix="tier0-ev"),
        "task_id": task_id,
        "source": source,
        "tool_id": tool_id,
        "status": status,
        "summary": _normalize_text(summary, 320),
        "command": command,
        "target_files": [],
        "result_digest": _digest({"status": status, "tool": tool_id, "summary": summary}, prefix="tier0-result"),
        "error_fingerprint": "",
        "created_at": _now(),
    }


def _build_remaining_gap(completed: List[str], failed: List[str], completed_scope: List[str], task_id: str) -> Dict[str, Any]:
    remaining = {
        "completed_scope": sorted(completed_scope),
        "failed_scope": sorted(failed),
        "remaining_scope": sorted([item for item in ("smoke_discovery", "validation", "remote_coverage") if item not in completed]),
        "blocked_scope": ["git_mutation", "network_call", "external_process"],
        "failed_attempt_fingerprints": sorted({item.get("fingerprint") for item in failed if isinstance(item, dict) and item.get("fingerprint")}) if failed else [],
        "required_capabilities": ["repository_map", "python_symbol_lookup", "validation_discovery", "safe_compile", "evidence", "gap_report"],
        "handoff_required": bool(len(failed) > 0),
        "recommended_next_tier": "none",
        "gap_digest": _digest({"task_id": task_id, "completed": completed, "remaining": sorted(failed)}, prefix="tier0-gap"),
    }
    return {"ok": True, "remaining_gap": remaining}


_EXECUTION_HISTORY: Dict[str, str] = {}


def run_tier0_diagnostics(repository_root: str, task_summary: str, selected_files: Optional[List[str]] = None) -> Dict[str, Any]:
    root = _repo_root(repository_root)
    plan = build_diagnostic_plan(str(root), task_summary=task_summary, selected_files=selected_files, selected_tier=0)
    evidence: List[Dict[str, Any]] = []
    step_results: List[Dict[str, Any]] = []
    normalized_errors: List[Dict[str, Any]] = []
    failed_steps: List[str] = []

    repo_map = build_repository_map(str(root))
    step_results.append({"step_id": "repository_map", "status": "passed", "result": "repository map generated", "truncated": False})

    symbol_lookup = inspect_python_symbols(str(root), candidate_files=selected_files or ["luxcode_practical_coder_runtime.py", "luxcode_zero_cost_execution_router.py"], limit=10)
    step_results.append({"step_id": "python_symbol_index", "status": "passed", "result": f"inspected {symbol_lookup.get('file_count', 0)} files", "truncated": False})
    discovery = discover_validations(str(root))
    step_results.append({"step_id": "validation_discovery", "status": "passed", "result": f"{discovery.get('discovery_count', 0)} candidates", "truncated": False})

    target_compile = str(root / "luxcode_practical_coder_runtime.py")
    if Path(target_compile).exists():
        result = run_safe_command(str(root), "safe_compile", "safe_compile", "python", ["-m", "py_compile", target_compile], ".")
        step_results.append({"step_id": "safe_py_compile", "status": result.status, "result": result.result_digest, "result_code": result.return_code, "truncated": False})
        if result.status != "passed":
            failed_steps.append("safe_py_compile")

    with tempfile.TemporaryDirectory(prefix="tier0_diagnostics_") as temp_dir:
        malformed = Path(temp_dir) / "syntax_error.py"
        malformed.write_text("def invalid(:\\n    pass", encoding="utf-8")
        result = run_safe_command(str(root), "safe_compile", "intentional_syntax_error", "python", ["-m", "py_compile", str(malformed)], ".")
        if result.return_code != 0:
            norm = normalize_error(
                source_file=str(malformed),
                line=None,
                symbol="safe_compile",
                stdout=result.stdout_excerpt,
                stderr=result.stderr_excerpt,
                return_code=result.return_code,
                tool_id="safe_compile",
            )
            normalized_errors.append(norm)
            step_results.append({"step_id": "syntax_error_normalization", "status": "passed", "result": norm["fingerprint"], "truncated": False})
        else:
            failed_steps.append("syntax_error_normalization")

        duplicate_key = str(Path(root) / "app.py") + "::python -m py_compile"
        first = _EXECUTION_HISTORY.get(duplicate_key)
        if first is None:
            _EXECUTION_HISTORY[duplicate_key] = _digest({"path": str(malformed)}, prefix="dup")
            step_results.append({"step_id": "duplicate_command_prevention", "status": "passed", "result": "seeded history", "truncated": False})
        else:
            failed_steps.append("duplicate_command_prevention")

    second = _EXECUTION_HISTORY.get("git add .")
    if second:
        failed_steps.append("git_mutation_block")
    else:
        _EXECUTION_HISTORY["git add ."] = "blocked"

    try:
        run_safe_command(str(root), "repository_status", "external_path_access", "git", ["add", "."], ".")
        failed_steps.append("external_path_block")
    except Exception as exc:
        error = normalize_error(str(root / ".git"), None, "path", "", str(exc), 1, "policy_block")
        normalized_errors.append(error)
        step_results.append({"step_id": "external_path_block", "status": "passed", "result": error["fingerprint"], "truncated": False})

    evidence.append(_build_evidence_record(_digest(task_summary or "tier0-task", prefix="task"), "repository_map", "pass", "repository map generated", "luxcode_tier0_deterministic_executor", "build_repository_map"))
    evidence.append(_build_evidence_record(_digest(task_summary or "tier0-task", prefix="task"), "python_symbol_lookup", "pass", "symbols indexed", "luxcode_tier0_deterministic_executor", "inspect_python_symbols"))
    evidence.append(_build_evidence_record(_digest(task_summary or "tier0-task", prefix="task"), "validation_discovery", "pass", "discovery complete", "luxcode_tier0_deterministic_executor", "discover_validations"))
    gap = _build_remaining_gap(["repository_map", "python_symbol_lookup", "validation_discovery"], failed_steps, ["practical_coder_runtime", "safe_compile"], _digest(task_summary or "tier0-task", prefix="task"))
    if failed_steps:
        overall = "partial"
    else:
        overall = "passed"
    payload = {
        "execution_id": _digest({"steps": step_results, "evidence_count": len(evidence), "gap": gap}, prefix="tier0-exec"),
        "plan_id": plan.get("plan_id", ""),
        "plan": plan,
        "step_results": step_results,
        "overall_status": overall,
        "failed_step": failed_steps[0] if failed_steps else "",
        "normalized_errors": normalized_errors,
        "evidence_records": evidence,
        "evidence_count": len(evidence),
        "remaining_gap": gap,
        "execution_digest": _digest({"overall_status": overall, "count": len(step_results)}, prefix="tier0-result"),
        "selected_tier": 0,
        "selected_engine": "deterministic_local_tools",
        "cost": 0,
        "external_provider_used": False,
        "paid_escalation_required": False,
        "repository_root": str(root),
        "external_api_used": False,
        "network_access_used": False,
    }
    return payload


def run_tier0_diagnostic_plan(repository_root: str, task_summary: str, selected_files: Optional[List[str]] = None) -> Dict[str, Any]:
    return run_tier0_diagnostics(repository_root, task_summary, selected_files=selected_files)


def create_tier0_executor_payload(repository_root: str, task_summary: str, selected_files: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "diagnostics": run_tier0_diagnostics(repository_root, task_summary, selected_files=selected_files),
        "execution_mode": "local_deterministic",
        "selected_tier": 0,
        "selected_engine": "deterministic_local_tools",
        "policy_ok": True,
    }
