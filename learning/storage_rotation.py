from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from .io_utils import ensure_dir


_ROTATION_LOCK = Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _date_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")


@dataclass
class StorageRotationEngine:
    base_dir: Path
    jsonl_max_size_mb: float = 25.0
    fine_tune_jsonl_max_size_mb: float = 20.0
    max_runs_before_forced_check: int = 12
    min_check_interval_seconds: int = 120

    def __post_init__(self) -> None:
        self._run_counter = 0

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def users_dir(self) -> Path:
        return self.data_dir / "users"

    @property
    def global_dir(self) -> Path:
        return self.data_dir / "global"

    @property
    def archive_root(self) -> Path:
        return self.data_dir / "archive"

    @property
    def archive_users_dir(self) -> Path:
        return self.archive_root / "users"

    @property
    def archive_global_dir(self) -> Path:
        return self.archive_root / "global"

    @property
    def report_path(self) -> Path:
        return self.global_dir / "storage_rotation_report.json"

    def ensure_foundation(self) -> None:
        ensure_dir(self.global_dir)
        ensure_dir(self.archive_global_dir)
        ensure_dir(self.archive_users_dir)
        if not self.report_path.exists():
            self.write_json_safe(
                self.report_path,
                {
                    "updated_at": now_iso(),
                    "last_rotation_at": None,
                    "rotation_needed": False,
                    "archived_files_count": 0,
                    "rotation_errors_count": 0,
                    "active_file_sizes": {},
                    "archive_health": {
                        "archive_root_exists": True,
                        "users_archive_exists": True,
                        "global_archive_exists": True,
                    },
                    "last_run": {
                        "status": "initialized",
                        "trigger": "init",
                        "archived_files": [],
                        "trimmed_files": [],
                        "errors": [],
                    },
                },
            )

    def load_json_safe(self, path: Path, default: Any) -> Any:
        try:
            if not path.exists():
                return default
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def write_json_safe(self, path: Path, data: Any) -> None:
        ensure_dir(path.parent)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def safe_archive_path(self, source_path: Path, archive_dir: Path) -> Path:
        ensure_dir(archive_dir)
        stem = source_path.stem
        suffix = source_path.suffix or ".bak"
        base = archive_dir / f"{stem}_{_timestamp_slug()}{suffix}"
        if not base.exists():
            return base
        for i in range(1, 1000):
            candidate = archive_dir / f"{stem}_{_timestamp_slug()}_{i}{suffix}"
            if not candidate.exists():
                return candidate
        return archive_dir / f"{stem}_{_timestamp_slug()}_{uuid4_fallback()}{suffix}"

    def _report_template(self) -> dict[str, Any]:
        prev = self.load_json_safe(self.report_path, {})
        if not isinstance(prev, dict):
            prev = {}
        return {
            "updated_at": now_iso(),
            "last_rotation_at": prev.get("last_rotation_at"),
            "rotation_needed": bool(prev.get("rotation_needed", False)),
            "archived_files_count": _safe_int(prev.get("archived_files_count", 0)),
            "rotation_errors_count": _safe_int(prev.get("rotation_errors_count", 0)),
            "active_file_sizes": dict(prev.get("active_file_sizes", {})) if isinstance(prev.get("active_file_sizes"), dict) else {},
            "archive_health": dict(prev.get("archive_health", {})) if isinstance(prev.get("archive_health"), dict) else {},
            "last_run": dict(prev.get("last_run", {})) if isinstance(prev.get("last_run"), dict) else {},
        }

    def _iter_user_dirs(self) -> list[Path]:
        if not self.users_dir.exists():
            return []
        out: list[Path] = []
        try:
            for p in self.users_dir.iterdir():
                if p.is_dir():
                    out.append(p)
        except Exception:
            return []
        return out

    def _is_global_file(self, path: Path) -> bool:
        try:
            return str(path.resolve()).startswith(str(self.global_dir.resolve()))
        except Exception:
            return False

    def _archive_dir_for_path(self, path: Path) -> Path:
        if self._is_global_file(path):
            return self.archive_global_dir
        try:
            rel = path.resolve().relative_to(self.users_dir.resolve())
            parts = rel.parts
            if parts:
                return self.archive_users_dir / parts[0]
        except Exception:
            pass
        return self.archive_root / "misc"

    def _file_size(self, path: Path) -> int:
        try:
            return int(path.stat().st_size) if path.exists() else 0
        except Exception:
            return 0

    def _read_jsonl_with_recovery(self, path: Path) -> tuple[list[str], list[str], int]:
        valid_rows: list[str] = []
        raw_rows: list[str] = []
        invalid_count = 0
        if not path.exists():
            return valid_rows, raw_rows, invalid_count
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip("\n")
                    if not line.strip():
                        continue
                    raw_rows.append(line)
                    try:
                        payload = json.loads(line)
                    except Exception:
                        invalid_count += 1
                        continue
                    # normalize line again to keep active file clean/parseable.
                    valid_rows.append(json.dumps(payload, ensure_ascii=False))
        except Exception:
            return [], [], 0
        return valid_rows, raw_rows, invalid_count

    def _write_jsonl_atomic(self, path: Path, lines: list[str]) -> None:
        ensure_dir(path.parent)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            if lines:
                f.write("\n".join(lines) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def rotate_jsonl_file(
        self,
        path: Path,
        archive_dir: Path,
        *,
        max_size_mb: float | None = None,
        keep_recent_lines: int | None = None,
    ) -> dict[str, Any]:
        result = {
            "path": str(path).replace("\\", "/"),
            "rotated": False,
            "archived_path": None,
            "invalid_lines_skipped": 0,
            "kept_lines": 0,
            "source_lines": 0,
            "source_size_bytes": self._file_size(path),
            "error": "",
        }
        if not path.exists():
            return result

        threshold_bytes = int((_safe_float(max_size_mb, 0.0) * 1024 * 1024)) if max_size_mb is not None else None
        valid_rows, raw_rows, invalid_count = self._read_jsonl_with_recovery(path)
        source_lines = len(raw_rows)
        result["source_lines"] = source_lines
        result["invalid_lines_skipped"] = invalid_count

        need_by_size = bool(threshold_bytes and result["source_size_bytes"] >= threshold_bytes)
        need_by_count = bool(keep_recent_lines is not None and source_lines > max(0, keep_recent_lines))
        needs_rotation = need_by_size or need_by_count

        if not needs_rotation and invalid_count == 0:
            # Nothing to do.
            result["kept_lines"] = len(valid_rows)
            return result

        try:
            archive_path = self.safe_archive_path(path, archive_dir)
            # Always archive full source first to avoid data loss.
            shutil.copy2(path, archive_path)

            if keep_recent_lines is None:
                kept = valid_rows
            elif keep_recent_lines <= 0:
                kept = []
            else:
                kept = valid_rows[-keep_recent_lines:]

            self._write_jsonl_atomic(path, kept)

            result["rotated"] = True
            result["archived_path"] = str(archive_path).replace("\\", "/")
            result["kept_lines"] = len(kept)
            return result
        except Exception as e:
            result["error"] = str(e)
            return result

    def trim_json_array_file(
        self,
        path: Path,
        archive_dir: Path,
        *,
        keep_last: int = 500,
        array_key: str = "items",
    ) -> dict[str, Any]:
        result = {
            "path": str(path).replace("\\", "/"),
            "trimmed": False,
            "archived_path": None,
            "array_key": array_key,
            "source_len": 0,
            "kept_len": 0,
            "error": "",
        }
        if not path.exists():
            return result

        try:
            with path.open("r", encoding="utf-8") as f:
                raw_text = f.read()
        except Exception as e:
            result["error"] = f"read_error:{e}"
            return result

        try:
            doc = json.loads(raw_text) if raw_text.strip() else {}
        except Exception as e:
            # Corrupted JSON: archive and preserve as-is, do not overwrite active blindly.
            try:
                archive_path = self.safe_archive_path(path, archive_dir)
                shutil.copy2(path, archive_path)
                result["trimmed"] = True
                result["archived_path"] = str(archive_path).replace("\\", "/")
                result["error"] = f"json_decode_error:{e}"
            except Exception as archive_err:
                result["error"] = f"json_decode_error:{e};archive_error:{archive_err}"
            return result

        if not isinstance(doc, dict):
            return result

        arr = doc.get(array_key)
        if not isinstance(arr, list):
            return result

        result["source_len"] = len(arr)
        if len(arr) <= keep_last:
            result["kept_len"] = len(arr)
            return result

        try:
            archive_path = self.safe_archive_path(path, archive_dir)
            shutil.copy2(path, archive_path)
            doc[array_key] = arr[-keep_last:]
            self.write_json_safe(path, doc)
            result["trimmed"] = True
            result["archived_path"] = str(archive_path).replace("\\", "/")
            result["kept_len"] = len(doc[array_key])
            return result
        except Exception as e:
            result["error"] = str(e)
            return result

    def check_rotation_needed(self) -> dict[str, Any]:
        self.ensure_foundation()
        threshold_global = int(self.jsonl_max_size_mb * 1024 * 1024)
        threshold_ft = int(self.fine_tune_jsonl_max_size_mb * 1024 * 1024)

        active_file_sizes: dict[str, int] = {}
        rotation_targets: list[dict[str, Any]] = []

        global_jsonl_specs = [
            ("fine_tune_candidates.jsonl", threshold_ft),
            ("elite_candidates.jsonl", threshold_ft),
            ("pending_candidates.jsonl", threshold_ft),
            ("rejected_candidates.jsonl", threshold_ft),
            ("analytics_runs.jsonl", threshold_global),
        ]
        for name, threshold in global_jsonl_specs:
            p = self.global_dir / name
            size = self._file_size(p)
            active_file_sizes[str(p).replace("\\", "/")] = size
            if size >= threshold:
                rotation_targets.append({"path": str(p).replace("\\", "/"), "reason": "size", "size_bytes": size})

        for user_dir in self._iter_user_dirs():
            p = user_dir / "conversation_analysis.jsonl"
            size = self._file_size(p)
            if size:
                active_file_sizes[str(p).replace("\\", "/")] = size
            if size >= threshold_global:
                rotation_targets.append({"path": str(p).replace("\\", "/"), "reason": "size", "size_bytes": size})

        needed = bool(rotation_targets)
        return {
            "rotation_needed": needed,
            "targets": rotation_targets[:50],
            "active_file_sizes": active_file_sizes,
            "checked_at": now_iso(),
        }

    def _should_run_now(self, force: bool, report: dict[str, Any]) -> bool:
        if force:
            return True
        self._run_counter += 1
        if self._run_counter >= max(1, self.max_runs_before_forced_check):
            self._run_counter = 0
            return True
        last_rotation_at = report.get("last_rotation_at")
        last_dt = None
        if isinstance(last_rotation_at, str) and last_rotation_at.strip():
            try:
                last_dt = datetime.fromisoformat(last_rotation_at.replace("Z", "+00:00")).astimezone(timezone.utc)
            except Exception:
                last_dt = None
        if last_dt is None:
            return True
        elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
        return elapsed >= max(10, int(self.min_check_interval_seconds))

    def run_storage_rotation(self, *, trigger: str = "background", force: bool = False) -> dict[str, Any]:
        self.ensure_foundation()
        with _ROTATION_LOCK:
            report = self._report_template()

            if not self._should_run_now(force, report):
                status = {
                    "status": "skipped_interval",
                    "trigger": trigger,
                    "rotation_needed": bool(report.get("rotation_needed", False)),
                    "checked_at": now_iso(),
                }
                report["last_run"] = status
                self.write_json_safe(self.report_path, report)
                return status

            check = self.check_rotation_needed()
            archived_files: list[dict[str, Any]] = []
            trimmed_files: list[dict[str, Any]] = []
            errors: list[str] = []
            archived_count = 0

            # Global JSONL rotations
            global_jsonl_ops = [
                (self.global_dir / "fine_tune_candidates.jsonl", self.fine_tune_jsonl_max_size_mb, 2000),
                (self.global_dir / "elite_candidates.jsonl", self.fine_tune_jsonl_max_size_mb, 1000),
                (self.global_dir / "pending_candidates.jsonl", self.fine_tune_jsonl_max_size_mb, 2000),
                (self.global_dir / "rejected_candidates.jsonl", self.fine_tune_jsonl_max_size_mb, 2000),
                (self.global_dir / "analytics_runs.jsonl", self.jsonl_max_size_mb, 4000),
            ]
            for path, max_mb, keep_lines in global_jsonl_ops:
                res = self.rotate_jsonl_file(
                    path,
                    self._archive_dir_for_path(path),
                    max_size_mb=max_mb,
                    keep_recent_lines=keep_lines,
                )
                if res.get("rotated"):
                    archived_files.append(res)
                    archived_count += 1
                if res.get("error"):
                    errors.append(f"{res.get('path')}: {res.get('error')}")

            # User data rotations
            for user_dir in self._iter_user_dirs():
                user_archive_dir = self._archive_dir_for_path(user_dir / "performance.json")
                perf_res = self.trim_json_array_file(
                    user_dir / "performance.json",
                    user_archive_dir,
                    keep_last=500,
                    array_key="history",
                )
                if perf_res.get("trimmed"):
                    trimmed_files.append(perf_res)
                    archived_count += 1
                if perf_res.get("error"):
                    errors.append(f"{perf_res.get('path')}: {perf_res.get('error')}")

                hybrid_res = self.trim_json_array_file(
                    user_dir / "hybrid_questions.json",
                    user_archive_dir,
                    keep_last=500,
                    array_key="items",
                )
                if hybrid_res.get("trimmed"):
                    trimmed_files.append(hybrid_res)
                    archived_count += 1
                if hybrid_res.get("error"):
                    errors.append(f"{hybrid_res.get('path')}: {hybrid_res.get('error')}")

                ca_path = user_dir / "conversation_analysis.jsonl"
                ca_res = self.rotate_jsonl_file(
                    ca_path,
                    self._archive_dir_for_path(ca_path),
                    max_size_mb=self.jsonl_max_size_mb,
                    keep_recent_lines=1000,
                )
                if ca_res.get("rotated"):
                    archived_files.append(ca_res)
                    archived_count += 1
                if ca_res.get("error"):
                    errors.append(f"{ca_res.get('path')}: {ca_res.get('error')}")

            latest_check = self.check_rotation_needed()
            report["updated_at"] = now_iso()
            report["last_rotation_at"] = now_iso()
            report["rotation_needed"] = bool(latest_check.get("rotation_needed", False))
            report["archived_files_count"] = _safe_int(report.get("archived_files_count", 0)) + archived_count
            report["rotation_errors_count"] = _safe_int(report.get("rotation_errors_count", 0)) + len(errors)
            report["active_file_sizes"] = latest_check.get("active_file_sizes", {})
            report["archive_health"] = {
                "archive_root_exists": self.archive_root.exists(),
                "users_archive_exists": self.archive_users_dir.exists(),
                "global_archive_exists": self.archive_global_dir.exists(),
                "users_archive_dirs": len([p for p in self.archive_users_dir.iterdir() if p.is_dir()]) if self.archive_users_dir.exists() else 0,
                "global_archive_files": len([p for p in self.archive_global_dir.iterdir() if p.is_file()]) if self.archive_global_dir.exists() else 0,
            }
            report["last_run"] = {
                "status": "ok" if not errors else "completed_with_errors",
                "trigger": trigger,
                "archived_files": archived_files[:100],
                "trimmed_files": trimmed_files[:100],
                "errors": errors[:100],
                "rotation_needed_before": bool(check.get("rotation_needed", False)),
                "rotation_needed_after": bool(latest_check.get("rotation_needed", False)),
            }
            self.write_json_safe(self.report_path, report)
            return dict(report["last_run"])

    def build_storage_rotation_report(self) -> dict[str, Any]:
        self.ensure_foundation()
        report = self.load_json_safe(self.report_path, {})
        if not isinstance(report, dict):
            report = {}
        check = self.check_rotation_needed()
        return {
            "updated_at": now_iso(),
            "last_rotation_at": report.get("last_rotation_at"),
            "rotation_needed": bool(check.get("rotation_needed", False)),
            "archived_files_count": _safe_int(report.get("archived_files_count", 0)),
            "rotation_errors_count": _safe_int(report.get("rotation_errors_count", 0)),
            "active_file_sizes": check.get("active_file_sizes", {}),
            "archive_health": report.get("archive_health", {}),
            "last_run": report.get("last_run", {}),
        }


def uuid4_fallback() -> str:
    # Keep module self-contained without adding an extra import in the hot path.
    import uuid

    return uuid.uuid4().hex[:10]

