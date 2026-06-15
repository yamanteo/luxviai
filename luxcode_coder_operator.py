from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time
from typing import Any, Dict, List, Optional, Tuple

from luxcode_coder_session import (
    SESSION_STATES,
    append_coder_step,
    build_run_manifest,
    create_coder_session,
    get_coder_session_output_root,
    load_coder_session,
    record_coder_step,
    save_session_manifest,
    session_output_files,
    update_coder_session_state,
)
from luxcode_minimum_context_builder import build_minimum_context_package
from luxcode_practical_coder_runtime import (
    build_minimum_context_for_coder,
    build_practical_coder_task_plan,
    control_practical_patch,
    create_repository_intake,
    draft_practical_patch,
    targeted_code_search,
    validate_practical_coder,
)
from luxcode_safe_patch_runtime import preview_patch, rollback_snapshot


EXIT_OK = 0
EXIT_INPUT = 2
EXIT_SECURITY = 3
EXIT_RUNTIME_FAILURE = 5
EXIT_TASK_FAILED = 4

ALLOWED_STATES = set(SESSION_STATES)
APPROVAL_TTL_SECONDS = 1200
SECRET_MARKERS = ("api_key", "api-key", "token", "secret", "password", "credential", "authorization", "private_key")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any, prefix: str = "coder-cli") -> str:
    return f"{prefix}-{hashlib.sha256(_stable_json(value).encode('utf-8')).hexdigest()[:24]}"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in SECRET_MARKERS):
            return "[redacted-secret]"
        if ".env" in value.lower() and "=" in value:
            return "[redacted-env]"
        return value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items() if k.lower() not in {"raw_stdout", "raw_stderr", "raw_stdout_summary", "raw_stderr_summary", "traceback"}}
    return value


def _normalize_list(values: Any, limit: int = 120) -> List[str]:
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
        text = str(item).replace("\\", "/").strip()
        if text and text not in seen:
            out.append(text)
            seen.add(text)
        if len(out) >= limit:
            break
    return out


def _safe_repo_root(path_text: Optional[str]) -> Path:
    if not path_text:
        raise OperatorError("repository path is required", "repository_not_found", EXIT_INPUT)
    root = Path(path_text).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise OperatorError("repository does not exist", "repository_not_found", EXIT_INPUT)
    return root


def _is_secret_path(path_text: str) -> bool:
    p = str(path_text or "").lower()
    return any(marker in p for marker in ("/.env", ".env", "credential", "secret", "token", "password"))


def _git(root: Path, args: List[str]) -> Tuple[int, str]:
    proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, timeout=15, shell=False)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _repository_digest(root: Path) -> str:
    code, out = _git(root, ["rev-parse", "HEAD"])
    return out.strip() if code == 0 else ""


def _command_digest(payload: Any) -> str:
    return _digest({"payload": payload, "created_at": _now()}, prefix="command")


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise OperatorError(f"failed to load json file: {exc}", "invalid_json", EXIT_INPUT)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(_redact(payload)), encoding="utf-8")


def _issue_approval_token(patch_digest: str, session_id: str, repository_head: str) -> Tuple[str, str]:
    expires_at = str(int(time()) + APPROVAL_TTL_SECONDS)
    token = f"CODER-APPROVE:{patch_digest}:{session_id}:{repository_head}:{expires_at}"
    digest = _digest({"patch": patch_digest, "session": session_id, "expires": expires_at}, prefix="cli-token")
    token = f"{token}:{digest}"
    return token, _now_ts(int(expires_at))


def _now_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _validate_approval_token(token: str, expected_digest: str, session_id: str, repository_head: str) -> bool:
    if not token or not expected_digest:
        return False
    if not token.startswith("CODER-APPROVE:"):
        return False
    parts = token.split(":")
    if len(parts) < 6:
        return False
    prefix, patch_digest, t_session, t_head, raw_exp, token_digest = parts[:6]
    if prefix != "CODER-APPROVE":
        return False
    if t_session != session_id or t_head != repository_head:
        return False
    if patch_digest != expected_digest:
        return False
    try:
        expiry = int(raw_exp)
    except ValueError:
        return False
    if time() > expiry:
        return False
    expected = _digest({"patch": patch_digest, "session": t_session, "expires": str(expiry)}, prefix="cli-token")
    return expected == token_digest


def _safe_text_files(root: Path, max_count: int = 250) -> List[str]:
    files: List[str] = []
    for item in root.rglob("*"):
        if len(files) >= max_count:
            break
        if not item.is_file():
            continue
        rel = item.relative_to(root).as_posix()
        if rel.startswith(".luxcode_runtime/"):
            continue
        if rel.startswith(".git/") or rel.startswith(".env") or _is_secret_path(rel):
            continue
        files.append(rel)
    return files


def _search_filename(root: Path, query: str, max_results: int = 20, mode: str = "filename") -> List[Dict[str, Any]]:
    q = (query or "").lower()
    results: List[Dict[str, Any]] = []
    for rel in _safe_text_files(root):
        if q in rel.lower():
            results.append({"path": rel, "line": 1, "preview": rel, "symbol": ""})
        if len(results) >= max_results:
            break
    if mode != "filename" and q and len(results) < max_results:
        target = _search_code(root, q, max_results - len(results))
        results.extend(target)
    return results[:max_results]


def _search_code(root: Path, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
    result = targeted_code_search(str(root), query=query, selected_files=_safe_text_files(root), max_results=max_results, case_sensitive=False)
    if not result.get("ok"):
        return []
    results = []
    for item in result.get("results", []):
        preview = str(item.get("preview", ""))
        if ".env" in item.get("path", "") or "token" in preview.lower():
            preview = "[redacted-secret-like-match]"
        results.append({"path": item.get("path"), "line": item.get("line"), "preview": preview, "symbol": ""})
    return results


def _search_match_type(root: Path, query: str, search_type: str, max_results: int = 20) -> List[Dict[str, Any]]:
    search_type = (search_type or "keyword").lower().strip()
    if not query:
        return []
    if search_type in {"filename", "path"}:
        return _search_filename(root, query, max_results=max_results, mode=search_type)
    return _search_code(root, query, max_results=max_results)


def _safe_file(path_text: str, root: Path) -> Optional[Path]:
    candidate = path_text.replace("\\", "/").strip()
    if not candidate or ".." in Path(candidate).parts or candidate.startswith("/"):
        return None
    if _is_secret_path(candidate):
        return None
    p = (root / candidate).resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError:
        return None
    return p


def _coerce_allowlist(values: Optional[List[str]], root: Path, limit: int = 40) -> List[str]:
    out: List[str] = []
    for value in values or []:
        p = _safe_file(str(value), root)
        if p is None:
            continue
        if p.is_file():
            out.append(p.relative_to(root).as_posix())
    return out[:limit]


class OperatorError(Exception):
    def __init__(self, message: str, error_code: str, exit_code: int = EXIT_INPUT) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.exit_code = exit_code


def _build_error_payload(error_code: str, message: str, details: Optional[Dict[str, Any]] = None, exit_code: int = EXIT_INPUT) -> Dict[str, Any]:
    return {
        "ok": False,
        "error_code": error_code,
        "message": message,
        "safe_details": _redact(details or {}),
        "recommended_action": "Adjust command arguments and retry with safe input",
        "error_digest": _digest({"error": message, "code": error_code, "details": details or {}}, prefix="cli-error"),
        "exit_code": exit_code,
        "timestamp": _now(),
    }


class CoderOperator:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.debug = bool(args.debug)
        self.json_output = bool(args.json)
        self.pretty = bool(args.pretty)
        self.no_write_report = bool(args.no_write_report)
        self.repo = _safe_repo_root(args.repo)
        self.head = _repository_digest(self.repo)
        self.session: Dict[str, Any] = {}
        self.session_id = args.session_id
        if args.command != "status":
            self._load_or_create_session()

    def _load_or_create_session(self) -> None:
        if self.session_id:
            loaded = load_coder_session(self.session_id, str(self.repo))
            if loaded.get("ok"):
                self.session = loaded.get("session", {})
                return
        self.session = create_coder_session(
            repository_root=str(self.repo),
            task_summary=str(self.args.task or ""),
            permission_mode=str(self.args.permission_mode or "approval_required"),
            risk_level=str(self.args.risk_level or "normal"),
            max_context_bytes=int(self.args.max_context_bytes or 32000),
            max_file_bytes=int(getattr(self.args, "max_file_bytes", 250000) or 250000),
            allowed_files=_normalize_list(self.args.allowed_file),
            protected_files=_normalize_list(self.args.protected_file),
        )
        self.session["session_state"] = "created"
        self.session["repository_head"] = self.head
        self.session["session_id"] = self.session.get("session_id") or _digest({"repo": str(self.repo), "created_at": _now()}, prefix="coder-session")
        self.session_id = str(self.session["session_id"])
        if self.args.session_id and self.args.session_id != self.session_id:
            self.session["session_id"] = self.args.session_id
            self.session_id = self.args.session_id
        self._persist()

    def _session_root(self) -> Path:
        return get_coder_session_output_root(str(self.repo), self.session_id)

    def _manifest_paths(self) -> Dict[str, str]:
        return session_output_files(self._session_root())

    def _session_output_path(self, name: str) -> Path:
        if self.no_write_report:
            return Path(self._session_root()) / f"{name}.manifest.json"
        if self.args.output:
            return Path(self.args.output).expanduser()
        paths = self._manifest_paths()
        return Path(paths.get(name, str(self._session_root() / f"{name}.manifest.json")))

    def _persist(self) -> None:
        if self.no_write_report or self.args.command == "status":
            return
        self.session["updated_at"] = _now()
        self.session["last_result_digest"] = _digest(self.session, prefix="session")
        update_coder_session_state(self.session, self.session.get("session_state", "created"), command=self.args.command)
        save_session_manifest(self.session, self._session_root() / "session.json")

    def _write_manifest(self, name: str, payload: Dict[str, Any]) -> None:
        if self.no_write_report or self.args.command == "status":
            return
        target = self._session_output_path(name)
        payload = {"ok": True, **payload}
        _write_json(target, payload)

    def _emit(self, payload: Dict[str, Any], command: str) -> Dict[str, Any]:
        if isinstance(payload, dict):
            payload = _redact(payload)
        payload["command"] = command
        payload["success"] = bool(payload.get("ok") is not False)
        payload["session_id"] = self.session.get("session_id", "")
        payload["status_digest"] = _digest(payload, prefix="cli-status")
        payload["status_at"] = _now()
        payload.setdefault("runtime_available", True)
        payload.setdefault("patch_runtime_available", True)
        payload.setdefault("context_builder_available", True)
        payload.setdefault("router_available", True)
        payload["session_count"] = len(list(self._session_root().parent.glob("*"))) if self._session_root().parent.exists() else 0
        payload["active_session_count"] = max(0, payload["session_count"])
        if self.json_output:
            return payload
        if self.pretty:
            lines = [
                "LUXCODE Practical Coder",
                f"Repository: {self.repo}",
                f"State: {self.session.get('session_state', 'unknown')}",
                f"PASS: {'yes' if payload.get('ok') is not False else 'no'}",
            ]
            for key in ("success", "exit_code", "status_digest"):
                if key in payload:
                    lines.append(f"{key}: {payload[key]}")
            print("\n".join(lines))
        else:
            print(_stable_json(payload))
        return {}

    def _print_output(self, payload: Dict[str, Any], command: str, exit_code: int = EXIT_OK) -> int:
        payload["command"] = command
        payload["status_digest"] = _digest(payload, prefix="cli-result")
        payload["status_at"] = _now()
        if self.json_output:
            text = json.dumps(_redact(payload), sort_keys=True, ensure_ascii=True, indent=2 if self.pretty else None)
            print(text)
        else:
            if self.pretty:
                summary = [
                    f"command={command}",
                    f"ok={payload.get('ok', False)}",
                    f"exit={exit_code}",
                ]
                if payload.get("status") in {"ok", "pass", "success"}:
                    summary.append("result=PASS")
                if payload.get("error_code"):
                    summary.append(f"error={payload['error_code']}")
                if payload.get("status_digest"):
                    summary.append(f"digest={payload['status_digest']}")
                print("\n".join(summary))
            else:
                print(_stable_json(_redact(payload)))
        return exit_code

    def _fail(self, error_code: str, message: str, *, details: Optional[Dict[str, Any]] = None, exit_code: int = EXIT_INPUT) -> Dict[str, Any]:
        payload = _build_error_payload(error_code, message, details, exit_code)
        payload["status"] = "failed"
        payload["repository_root"] = str(self.repo)
        payload["command"] = self.args.command
        return payload

    # ----- command implementations -----
    def cmd_status(self) -> Dict[str, Any]:
        try:
            status_code, status_output = _git(self.repo, ["status", "--short"])
            modified = []
            untracked = []
            staged = []
            for line in status_output.splitlines():
                if line.startswith("??"):
                    untracked.append(line)
                elif len(line) >= 2:
                    staged.append(line)
                    modified.append(line)
            runtime = {
                "repository_root": str(self.repo),
                "repository_exists": True,
                "repository_allowed": True,
                "branch": "",
                "head_commit": "",
                "working_tree_clean": not bool(status_output.strip()),
                "staged_area_empty": not bool(staged),
                "modified_files": modified,
                "untracked_files": untracked,
                "runtime_available": True,
                "patch_runtime_available": True,
                "context_builder_available": True,
                "router_available": True,
                "session_count": 0,
                "active_session_count": 0,
                "status": "ready",
                "status_digest": _digest({"repo": str(self.repo), "status": status_output}, prefix="status-digest"),
            }
            code, branch = _git(self.repo, ["branch", "--show-current"])
            if code == 0:
                runtime["branch"] = branch.strip()
            code, head = _git(self.repo, ["rev-parse", "HEAD"])
            if code == 0:
                runtime["head_commit"] = head.strip()
            session_root = self.repo / ".luxcode_runtime" / "coder_sessions"
            if session_root.exists():
                sessions = [p for p in session_root.iterdir() if p.is_dir()]
                runtime["session_count"] = len(sessions)
                runtime["active_session_count"] = sum(1 for p in sessions if (p / "session.json").exists())
            runtime["session_id"] = self.args.session_id or ""
            runtime["status_digest"] = _digest(runtime, prefix="status")
            return runtime
        except Exception as exc:
            raise OperatorError(f"status failed: {exc}", "runtime_contract_error", EXIT_RUNTIME_FAILURE)

    def cmd_intake(self) -> Dict[str, Any]:
        task_summary = str(self.args.task or "")
        allowed_files = _coerce_allowlist(_normalize_list(self.args.allowed_file), self.repo)
        protected_files = _coerce_allowlist(_normalize_list(self.args.protected_file), self.repo)
        if any(item in set(allowed_files) and item in set(protected_files) for item in allowed_files):
            raise OperatorError("allowed/protected conflict", "protected_scope_conflict", EXIT_SECURITY)
        intake = create_repository_intake(
            repository_root=str(self.repo),
            task_summary=task_summary,
            requested_files=allowed_files[:80],
            suspected_files=_coerce_allowlist(_normalize_list(self.args.query), self.repo)[:80],
            max_files=80,
        )
        if not intake.get("ok"):
            raise OperatorError("repository intake failed", "runtime_contract_error", EXIT_INPUT)
        payload = {
            "command": "intake",
            "success": True,
            "intake_id": intake.get("intake_id", ""),
            "intake_state": "ready",
            "intake_state_id": intake.get("intake_state", ""),
            "repository_summary": {
                "repository_root": str(self.repo),
                "repository_name": self.repo.name,
                "branch": self.head,
                "working_tree_clean": not bool(intake.get("repository_dirty")),
            },
            "safety_summary": {
                "repository_allowed": True,
                "approval_mode": str(self.args.permission_mode or "approval_required"),
                "risk_level": str(self.args.risk_level or "normal"),
                "has_allowed_conflict": False,
            },
            "recommended_next_command": "search",
            "result_digest": _digest(intake, prefix="intake"),
            "intake": _redact(intake),
        }
        if payload["intake"]["intake_id"]:
            self.session["intake_id"] = str(payload["intake"]["intake_id"])
        self.session["session_state"] = "intake_complete"
        self.session["last_command"] = "intake"
        self.session["completed_scope"] = []
        self.session["remaining_gap"] = []
        self._persist()
        self._write_manifest("intake", {"intake_result": payload["intake"], "session_id": self.session_id})
        return payload

    def _read_patch_contract(self) -> Tuple[Dict[str, Any], str]:
        patch_path = Path(self.args.patch_file or "")
        if not patch_path.exists():
            raise OperatorError("patch file not found", "input_file_not_found", EXIT_INPUT)
        if patch_path.stat().st_size > 120_000:
            raise OperatorError("patch file exceeds allowed size", "input_file_too_large", EXIT_INPUT)
        if patch_path.suffix.lower() != ".json":
            raise OperatorError("patch file must be JSON", "invalid_json", EXIT_INPUT)
        data = _load_json(patch_path)
        patch_contract = data
        if "patch_contract" in data and isinstance(data["patch_contract"], dict):
            patch_contract = data["patch_contract"]
        if not isinstance(patch_contract, dict):
            raise OperatorError("invalid patch file format", "invalid_patch", EXIT_INPUT)
        if not isinstance(patch_contract.get("repository_root"), str):
            patch_contract["repository_root"] = str(self.repo)
        if patch_contract.get("approval_token_hint") is None:
            patch_contract["approval_token_hint"] = ""
        if patch_contract.get("expected_repository_head") is None:
            patch_contract["expected_repository_head"] = self.head
        return patch_contract, patch_path.stem
    def cmd_search(self) -> Dict[str, Any]:
        query = str(self.args.query or "")
        if not query:
            raise OperatorError("query is required", "invalid_arguments", EXIT_INPUT)
        stype = (str(self.args.type or "keyword")).lower().strip()
        allowed = _coerce_allowlist(_normalize_list(self.args.allowed_file), self.repo)
        search_records = []
        excluded_count = 0
        if stype in {"filename", "path"}:
            search_records = _search_filename(self.repo, query, max_results=int(self.args.max_results or 30), mode=stype)
        elif stype in {"symbol", "keyword", "exact_text", "import", "endpoint", "class_name", "function_name", "test_name"}:
            selected = allowed or _safe_text_files(self.repo)
            base = targeted_code_search(repository_root=str(self.repo), query=query, selected_files=selected, max_results=int(self.args.max_results or 30), case_sensitive=False)
            if base.get("ok"):
                for item in base.get("results", []):
                    path = str(item.get("path", "")).replace("\\", "/")
                    if _is_secret_path(path):
                        continue
                    search_records.append({"path": path, "line": item.get("line"), "preview": _redact(str(item.get("preview", ""))), "symbol": ""})
        else:
            raise OperatorError(f"unsupported search type: {stype}", "invalid_arguments", EXIT_INPUT)
        if len(search_records) > int(self.args.max_results or 30):
            excluded_count = len(search_records) - int(self.args.max_results or 30)
            search_records = search_records[: int(self.args.max_results or 30)]
        payload = {
            "search_id": _digest({"q": query, "t": stype, "c": len(search_records)}, prefix="search"),
            "query": query,
            "search_type": stype,
            "match_count": len(search_records),
            "matches": search_records,
            "truncated": bool(excluded_count),
            "excluded_match_count": excluded_count,
            "recommended_next_command": "context" if search_records else "plan",
            "search_digest": _digest({"query": query, "matches": search_records}, prefix="search-digest"),
        }
        self.session["session_state"] = "analysis_complete"
        self.session["search_ids"] = _normalize_list(list(self.session.get("search_ids", [])) + [payload["search_id"]])
        record_coder_step(self.session, step_type="search", command="search", result=payload)
        self._persist()
        self._write_manifest("search", {"search_result": payload, "session_id": self.session_id})
        return payload

    def cmd_context(self) -> Dict[str, Any]:
        if self.session.get("session_state") not in {"created", "intake_complete", "analysis_complete"}:
            self.session["session_state"] = "analysis_complete"
        task_summary = str(self.args.task or "")
        intake = create_repository_intake(repository_root=str(self.repo), task_summary=task_summary, requested_files=_coerce_allowlist(self.args.allowed_file, self.repo), suspected_files=_coerce_allowlist(self.args.protected_file, self.repo), max_files=80)
        search_records: List[Dict[str, Any]] = []
        if self.args.search_results_file:
            search_payload = _load_json(Path(self.args.search_results_file))
            if not isinstance(search_payload.get("matches"), list):
                raise OperatorError("search-results payload invalid", "invalid_json", EXIT_INPUT)
            search_records = []
            normalized = []
            for item in search_payload.get("matches", []):
                if not isinstance(item, dict):
                    continue
                normalized.append({"path": item.get("path", ""), "line": item.get("line", 1), "symbol_name": item.get("symbol", ""), "content": ""})
            search_records = normalized
        elif self.args.query:
            matched = _search_match_type(self.repo, self.args.query, str(self.args.type or "keyword"), max_results=int(self.args.max_results or 20))
            for item in matched:
                search_records.append({"file_path": item.get("path", ""), "line_start": item.get("line", 1), "line_end": item.get("line", 1), "symbol_name": item.get("symbol", "")})
        package = build_minimum_context_for_coder(
            repository_intake=intake,
            search_results=search_records,
            max_files=int(self.args.max_results or 8),
            max_chars=int(self.args.max_context_bytes or 16000),
        )
        context = build_minimum_context_package(
            task_summary=task_summary,
            repository_intake=intake,
            search_results={"matches": search_records},
            target_files=_normalize_list(package.get("selected_symbols", []) or intake.get("file_inventory", []), limit=8),
            max_files=int(self.args.max_results or 8),
            max_context_bytes=int(self.args.max_context_bytes or 16000),
        )
        payload = {
            "context_package_id": context.get("context_package_id", ""),
            "selected_file_count": len(context.get("selected_files", [])),
            "selected_symbol_count": len(context.get("selected_symbols", [])),
            "selected_snippet_count": len(context.get("selected_snippets", [])),
            "context_bytes": int(context.get("context_bytes", 0) or 0),
            "context_truncated": bool(context.get("context_truncated", False)),
            "excluded_files": _normalize_list(context.get("excluded_files", [])),
            "exclusion_reasons": context.get("exclusion_reasons", {}),
            "output_file": str(self._session_output_path("context")),
            "context_digest": str(context.get("context_digest", "")),
            "recommended_next_command": "plan",
        }
        self.session["session_state"] = "context_ready"
        self.session["context_package_ids"] = _normalize_list(list(self.session.get("context_package_ids", [])) + [payload["context_package_id"]])
        self._persist()
        self._write_manifest("context", {"context_manifest": _redact(context), "session_id": self.session_id})
        return payload

    def cmd_plan(self) -> Dict[str, Any]:
        task_summary = str(self.args.task or "")
        intake = create_repository_intake(
            repository_root=str(self.repo),
            task_summary=task_summary,
            requested_files=_coerce_allowlist(_normalize_list(self.args.allowed_file), self.repo),
            suspected_files=_coerce_allowlist(_normalize_list(self.args.protected_file), self.repo),
            max_files=80,
        )
        plan = build_practical_coder_task_plan(
            repository_intake=intake,
            task_summary=task_summary,
            selected_files=_coerce_allowlist(_normalize_list(self.args.allowed_file), self.repo),
            acceptance_criteria=["compile", "targeted_smoke", "no unrelated writes"],
        )
        if not plan.get("ok"):
            raise OperatorError("plan generation failed", "plan_failed", EXIT_RUNTIME_FAILURE)
        payload = {
            "plan_id": plan.get("coder_plan_id", ""),
            "task_class": plan.get("task_class", "code_change"),
            "risk_level": str(self.args.risk_level or "normal"),
            "target_files": _normalize_list(plan.get("selected_files", []), limit=50),
            "target_symbols": ["class", "function", "constant"],
            "recommended_engine": "zero_cost",
            "recommended_tier": "free_local",
            "deterministic_steps": plan.get("steps", []),
            "patch_required": True,
            "validation_plan": ["py_compile", "targeted_smoke"],
            "approval_points": ["patch_apply"],
            "plan_state": "ready",
            "plan_file": str(self._session_root() / "coder_plan.json"),
            "plan_digest": plan.get("plan_digest", ""),
        }
        self.session["session_state"] = "plan_ready"
        self.session["plan_ids"] = _normalize_list(list(self.session.get("plan_ids", [])) + [payload["plan_id"]])
        self._persist()
        self._write_manifest("plan", {"plan": _redact(plan), "session_id": self.session_id})
        return payload

    def cmd_patch_preview(self) -> Dict[str, Any]:
        patch_contract, patch_name = self._read_patch_contract()
        if not patch_contract.get("patch_id"):
            draft = draft_practical_patch(
                repository_root=str(self.repo),
                task_plan={"selected_files": _normalize_list(patch_contract.get("selected_files", []))},
                operations=_normalize_list(patch_contract.get("operations", [])),
                approved_files=_coerce_allowlist(_normalize_list(self.args.allowed_file), self.repo),
                protected_files=_coerce_allowlist(_normalize_list(self.args.protected_file), self.repo),
            )
            patch_contract = draft.get("patch_contract", {})
        token, expiry_iso = _issue_approval_token(patch_contract.get("patch_digest", ""), self.session_id, self.head)
        preview = preview_patch(patch_contract)
        payload = {
            "patch_id": patch_contract.get("patch_id", ""),
            "valid": bool(preview.get("valid")),
            "files_to_modify": preview.get("files_to_modify", []),
            "files_to_create": preview.get("files_to_create", []),
            "operation_count": int(preview.get("operation_count", 0) or 0),
            "risk_flags": preview.get("risk_flags", []),
            "protected_surface_detected": bool(preview.get("protected_surface_detected", False)),
            "approval_required": True,
            "apply_allowed": bool(preview.get("apply_allowed", False)),
            "approval_token": token,
            "approval_expires_at": expiry_iso,
            "preview_file": str(self._session_root() / "patch_preview.json"),
            "preview_digest": preview.get("preview_digest", ""),
            "patch_file": patch_name,
        }
        if not payload["valid"]:
            raise OperatorError("patch contract invalid", "invalid_patch", EXIT_INPUT)
        self.session["session_state"] = "patch_preview_ready"
        self.session["patch_ids"] = _normalize_list(list(self.session.get("patch_ids", [])) + [payload["patch_id"]])
        record = {"patch_contract": patch_contract, "approval_token": token, "approval_expires_at": expiry_iso}
        self.session["patch_contract"] = _redact(patch_contract)
        self.session["patch_preview_token"] = token
        self._persist()
        self._write_manifest("patch_preview", {"patch_preview": payload, "patch_contract": patch_contract, "session_id": self.session_id})
        return payload

    def cmd_patch_apply(self) -> Dict[str, Any]:
        patch_contract, _ = self._read_patch_contract()
        if not bool(getattr(self.args, "apply", False)):
            preview = preview_patch(patch_contract)
            return {
                "patch_id": patch_contract.get("patch_id", ""),
                "execution_state": "preview_only",
                "preview": preview,
                "status": "blocked",
                "status_message": "preview mode only, use --apply to apply changes",
            }
        if not _validate_approval_token(str(self.args.approval_token), patch_contract.get("patch_digest", ""), self.session_id, self.head):
            raise OperatorError("approval token invalid or expired", "approval_invalid", EXIT_SECURITY)
        if _repository_digest(self.repo) != patch_contract.get("expected_repository_head", self.head):
            raise OperatorError("repository head changed since preview", "head_changed", EXIT_SECURITY)
        if _git(self.repo, ["status", "--short"])[0] != 0:
            raise OperatorError("working tree status unavailable", "runtime_contract_error", EXIT_INPUT)
        validation_plan = self.args.validation_plan
        if not validation_plan:
            validation_plan = None
        result = control_practical_patch(
            patch_contract=patch_contract,
            action="apply",
            approval_confirmed=True,
            approval_token=str(patch_contract.get("approval_token_hint", "")),
            dry_run=False,
            validation_plan=validation_plan,
        )
        if not result.get("ok"):
            self.session["session_state"] = "blocked"
            self._persist()
            raise OperatorError("apply failed", "patch_apply_failed", EXIT_TASK_FAILED)
        self.session["session_state"] = "patch_applied"
        self.session["patch_ids"] = _normalize_list(list(self.session.get("patch_ids", [])) + [result.get("patch_id", "")])
        self.session["execution_ids"] = _normalize_list(list(self.session.get("execution_ids", [])) + [result.get("patch_execution_id", "")])
        self._persist()
        snapshot_id = result.get("snapshot_id", "")
        if snapshot_id:
            self._write_manifest("validation", {"validation_result": result.get("validation_result", {})})
            self._write_manifest("rollback", {"rollback_placeholder": {"snapshot_id": snapshot_id, "available_for_rollback": True}})
        self._write_manifest("patch_preview", {"patch_preview": result, "session_id": self.session_id})
        return {
            "ok": True,
            "execution_state": result.get("execution_state", "applied"),
            "patch_id": result.get("patch_id", ""),
            "patch_execution_id": result.get("patch_execution_id", ""),
            "snapshot_id": snapshot_id,
            "validation_result": result.get("validation_result", {}),
            "validation_digest": result.get("validation_result", {}).get("validation_digest", ""),
            "modified_files": result.get("modified_files", []),
            "created_files": result.get("created_files", []),
            "diff_summary": result.get("diff_summary", {}),
            "status": "pass",
        }

    def cmd_validate(self) -> Dict[str, Any]:
        vplan = self.args.validation_plan
        if not vplan:
            vplan = [{"type": "py_compile", "paths": ["app.py"]}]
        plan_input = _load_json(Path(vplan[0])) if isinstance(vplan, list) and len(vplan) == 1 and str(vplan[0]).endswith(".json") else vplan
        if isinstance(plan_input, dict):
            plan_input = [plan_input]
        validation = validate_practical_coder(repository_root=str(self.repo), validation_plan=plan_input)
        result = {
            "validation_result_id": validation.get("validation_result", {}).get("validation_result_id", validation.get("validation_result_id", "")),
            "step_count": len(plan_input) if isinstance(plan_input, list) else 0,
            "passed_step_count": sum(1 for step in validation.get("validation_result", {}).get("steps", []) if step.get("passed")),
            "failed_step_id": validation.get("validation_result", {}).get("failed_step_id", ""),
            "passed": bool(validation.get("ok", False)),
            "timed_out": bool(validation.get("validation_result", {}).get("timed_out", False)),
            "artifact_detected": bool(validation.get("validation_result", {}).get("artifact_detected", False)),
            "result_file": str(self._session_root() / "validation_result.json"),
            "validation_digest": validation.get("validation_result", {}).get("validation_digest", ""),
            "validation_result": validation,
        }
        if not result["passed"]:
            self.session["session_state"] = "failed"
            self._persist()
            raise OperatorError("validation failed", "validation_failed", EXIT_TASK_FAILED)
        self.session["session_state"] = "validation_complete"
        self.session["validation_ids"] = _normalize_list(list(self.session.get("validation_ids", [])) + [result["validation_result_id"]])
        self._persist()
        self._write_manifest("validation", {"validation_result": validation, "session_id": self.session_id})
        return result

    def cmd_rollback(self) -> Dict[str, Any]:
        manifest_path = Path(self.args.snapshot_manifest)
        if not manifest_path.exists():
            raise OperatorError("snapshot manifest missing", "input_file_not_found", EXIT_INPUT)
        manifest = _load_json(manifest_path)
        patch_contract = manifest.get("patch_contract", manifest.get("patch_contract", {}))
        snapshot = manifest.get("snapshot", manifest.get("snapshot_manifest", {}))
        if not self.args.apply:
            return {
                "ok": True,
                "rollback_mode": "dry_run",
                "snapshot_id": snapshot.get("snapshot_id", ""),
                "restorable": bool(snapshot.get("snapshot_id")),
                "restoration_files": [item.get("file_path") for item in snapshot.get("files", [])],
                "status": "blocked",
            }
        if not isinstance(patch_contract, dict) or not isinstance(snapshot, dict):
            raise OperatorError("snapshot manifest missing required keys", "runtime_contract_error", EXIT_INPUT)
        result = rollback_snapshot(patch_contract, snapshot)
        if not result.get("ok"):
            self.session["session_state"] = "blocked"
            self._persist()
            raise OperatorError("rollback failed", "rollback_failed", EXIT_TASK_FAILED)
        self.session["session_state"] = "rolled_back"
        self.session["snapshot_ids"] = _normalize_list(list(self.session.get("snapshot_ids", [])) + [result.get("snapshot_id", "")])
        self._persist()
        self._write_manifest("rollback", {"rollback_result": result, "session_id": self.session_id})
        return {
            "rollback_id": result.get("rollback_id", ""),
            "rollback_performed": bool(result.get("rollback_performed", False)),
            "snapshot_id": result.get("snapshot_id", ""),
            "restored_files": result.get("restored_files", []),
            "status": "pass" if result.get("ok") is not False else "fail",
        }

    def cmd_run(self) -> Dict[str, Any]:
        if not self.args.task_file:
            raise OperatorError("task_file required", "input_file_not_found", EXIT_INPUT)
        task_file = Path(self.args.task_file)
        if not task_file.exists():
            raise OperatorError("task file not found", "input_file_not_found", EXIT_INPUT)
        task_payload = _load_json(task_file)
        steps = _normalize_list(task_payload.get("actions"), limit=30)
        if not steps:
            steps = ["intake", "search", "context", "plan"]
        allowed_actions = {"intake", "search", "context", "plan", "patch_preview", "patch_apply", "validate", "rollback"}
        unknown = [s for s in steps if s not in allowed_actions]
        if unknown:
            raise OperatorError(f"unsupported action in task: {', '.join(unknown)}", "runtime_contract_error", EXIT_INPUT)
        task_summary = str(task_payload.get("task", task_payload.get("task_summary", ""))
                           or self.args.task or "")
        completed = []
        failed_step = ""
        step_results: List[Dict[str, Any]] = []
        evidence_records: List[Dict[str, Any]] = []
        session_state = "created"
        for index, action in enumerate(steps, start=1):
            try:
                original = self.args.command
                if action == "intake":
                    self.args.task = task_summary
                    step_result = self.cmd_intake()
                elif action == "search":
                    if not self.args.query:
                        self.args.query = task_payload.get("query", task_summary)
                    self.args.type = task_payload.get("type", "keyword")
                    step_result = self.cmd_search()
                elif action == "context":
                    if not self.args.task:
                        self.args.task = task_summary
                    step_result = self.cmd_context()
                elif action == "plan":
                    self.args.task = task_summary
                    self.args.risk_level = task_payload.get("risk_level", self.args.risk_level or "normal")
                    step_result = self.cmd_plan()
                elif action == "patch_preview":
                    self.args.patch_file = task_payload.get("patch_file", "")
                    step_result = self.cmd_patch_preview()
                elif action == "patch_apply":
                    self.args.patch_file = task_payload.get("patch_file", "")
                    self.args.apply = True
                    self.args.approval_token = task_payload.get("approval_token", self.session.get("patch_preview_token", ""))
                    step_result = self.cmd_patch_apply()
                elif action == "validate":
                    self.args.validation_plan = task_payload.get("validation_plan") or [{"type": "py_compile", "paths": ["app.py"]}]
                    step_result = self.cmd_validate()
                else:
                    # rollback
                    self.args.snapshot_manifest = task_payload.get("snapshot_manifest", "")
                    self.args.apply = True
                    step_result = self.cmd_rollback()
                self.args.command = original
                if step_result.get("ok") is False:
                    raise OperatorError("step returned failed result", "runtime_contract_error", EXIT_TASK_FAILED)
                completed.append(action)
                step_results.append({"index": index, "action": action, "ok": True, "result_digest": _digest(step_result, prefix="run-step")})
                evidence_records.append({"action": action, "result_digest": step_results[-1]["result_digest"]})
            except OperatorError as exc:
                failed_step = action
                evidence_records.append({"action": action, "error": exc.message})
                self.session["session_state"] = "failed"
                session_state = "failed"
                self._persist()
                break
        manifest = build_run_manifest(
            self.session,
            run_id=_digest({"task": task_summary, "created": _now()}, prefix="coder-run"),
            task=task_summary,
            steps=step_results,
            completed_steps=completed,
            failed_step=failed_step,
            current_state=session_state,
            evidence_records=evidence_records,
        )
        if not failed_step:
            self.session["session_state"] = "completed"
            self.session["completed_scope"] = steps
        self._persist()
        self._write_manifest("run", {"run_manifest": manifest, "session_id": self.session_id})
        return {
            "run_id": manifest["run_id"],
            "task": task_summary,
            "steps": step_results,
            "completed_steps": completed,
            "failed_step": failed_step,
            "current_state": self.session.get("session_state", session_state),
            "evidence_records": evidence_records,
            "recommended_next_action": "inspect or stop",
            "run_manifest": manifest["run_manifest"],
            "final_digest": manifest["final_digest"],
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python scripts/luxcode_coder.py", description="LUXCODE Practical Coder Operator CLI")
    parser.add_argument("command", nargs="?", help="command")
    parser.add_argument("--repo", required=False)
    parser.add_argument("--json", action="store_true", default=False)
    parser.add_argument("--pretty", action="store_true", default=False)
    parser.add_argument("--debug", action="store_true", default=False)
    parser.add_argument("--no-write-report", action="store_true", default=False)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--permission-mode", default="approval_required")
    parser.add_argument("--risk-level", default="normal")
    parser.add_argument("--allowed-file", action="append")
    parser.add_argument("--protected-file", action="append")
    parser.add_argument("--max-context-bytes", type=int, default=32000)
    parser.add_argument("--max-results", type=int, default=30)
    parser.add_argument("--task", default="")
    parser.add_argument("--task-file", default="")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--validation-plan", default=None)
    parser.add_argument("--query", default="")
    parser.add_argument("--type", default="keyword")
    parser.add_argument("--search-results-file", default="")
    parser.add_argument("--patch-file", default="")
    parser.add_argument("--apply", action="store_true", default=False)
    parser.add_argument("--approval-token", default="")
    parser.add_argument("--snapshot-manifest", default="")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        print("error: command is required", file=sys.stderr)
        return EXIT_INPUT
    if isinstance(args.validation_plan, str) and args.validation_plan:
        try:
            if args.validation_plan.endswith(".json") and Path(args.validation_plan).exists():
                args.validation_plan = json.loads(Path(args.validation_plan).read_text(encoding="utf-8"))
            else:
                args.validation_plan = json.loads(args.validation_plan)
        except Exception:
            args.validation_plan = [{"type": str(args.validation_plan)}]
    try:
        if args.command in {"status", "intake", "search", "context", "plan", "patch-preview", "patch-apply", "validate", "rollback", "run"}:
            operator = CoderOperator(args)
            if args.command == "status":
                payload = operator.cmd_status()
            elif args.command == "intake":
                payload = operator.cmd_intake()
            elif args.command == "search":
                payload = operator.cmd_search()
            elif args.command == "context":
                payload = operator.cmd_context()
            elif args.command == "plan":
                payload = operator.cmd_plan()
            elif args.command == "patch-preview":
                payload = operator.cmd_patch_preview()
            elif args.command == "patch-apply":
                payload = operator.cmd_patch_apply()
            elif args.command == "validate":
                args.command = "validate"
                if args.validation_plan is None:
                    args.validation_plan = []
                payload = operator.cmd_validate()
            elif args.command == "rollback":
                payload = operator.cmd_rollback()
            else:
                payload = operator.cmd_run()
            return operator._print_output(payload, args.command, exit_code=EXIT_OK if payload.get("ok", True) is not False else EXIT_TASK_FAILED)
        print(f"error: unknown command: {args.command}", file=sys.stderr)
        return EXIT_INPUT
    except OperatorError as exc:
        if args.command != "status":
            print(json.dumps(_redact(_build_error_payload(exc.error_code, exc.message, exit_code=exc.exit_code)), sort_keys=True)
            , file=sys.stdout)
        return exc.exit_code
    except Exception as exc:
        if args.command == "status":
            print(f"error: {exc}", file=sys.stderr)
        else:
            payload = _build_error_payload("unexpected_error", str(exc), exit_code=EXIT_RUNTIME_FAILURE)
            if args.command:
                payload["command"] = args.command
            if args.debug:
                payload["traceback"] = traceback.format_exc()
            print(json.dumps(_redact(payload), sort_keys=True), file=sys.stdout)
        return EXIT_RUNTIME_FAILURE


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
