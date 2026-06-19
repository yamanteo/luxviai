from __future__ import annotations

import os
import subprocess as sp
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import TextIO

from luxcode_desktop.api.client import LuxCodeApiClient
from luxcode_desktop.config import DEFAULT_MAIN_REPOSITORY, LOG_DIR
from luxcode_runtime_settings import (
    build_runtime_environment,
    get_backend_runtime_policy,
)


class BackendProcessService:
    def __init__(
        self,
        client: LuxCodeApiClient,
        repository_root: Path = DEFAULT_MAIN_REPOSITORY,
    ) -> None:
        self.client = client
        self.repository_root = repository_root
        self.process: sp.Popen[str] | None = None
        self._process_lock = threading.Lock()
        self._watchdog_stop = threading.Event()
        self._watchdog_thread: threading.Thread | None = None
        self._restart_times: deque[float] = deque()
        self._log_stream: TextIO | None = None

    @property
    def backend_log_path(self) -> Path:
        return LOG_DIR / "backend.log"

    def ensure_running(self, wait_seconds: float = 8.0) -> dict[str, str]:
        with self._process_lock:
            if self._is_healthy():
                self._ensure_watchdog_started()
                return {
                    "Backend": "connected",
                    "Started": "false",
                    "Reason": "already_running",
                    "Log": str(self.backend_log_path),
                }

            self._stop_stale_backend_if_present()
            env = build_runtime_environment(
                os.environ.copy(),
                self.repository_root,
            )
            env.setdefault("PORT", "5000")
            env["LUXVIAI_RELOAD"] = "0"
            creationflags = 0
            startupinfo = None
            if os.name == "nt":
                creationflags = getattr(sp, "CREATE_NO_WINDOW", 0)
                startupinfo = sp.STARTUPINFO()
                startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW

            self._close_log_stream()
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            self._rotate_log_if_needed()
            self._log_stream = self.backend_log_path.open(
                "a",
                encoding="utf-8",
                buffering=1,
            )
            self._log_stream.write(
                "\n=== LuxCode backend start "
                + time.strftime("%Y-%m-%d %H:%M:%S")
                + " ===\n"
            )

            self.process = sp.Popen(
                [sys.executable, "app.py"],
                cwd=str(self.repository_root),
                env=env,
                stdout=self._log_stream,
                stderr=sp.STDOUT,
                stdin=sp.DEVNULL,
                text=True,
                creationflags=creationflags,
                startupinfo=startupinfo,
            )

            deadline = time.monotonic() + wait_seconds
            while time.monotonic() < deadline:
                if self._is_healthy():
                    self._ensure_watchdog_started()
                    return {
                        "Backend": "connected",
                        "Started": "true",
                        "Reason": "auto_started",
                        "Log": str(self.backend_log_path),
                    }
                if self.process.poll() is not None:
                    return {
                        "Backend": "disconnected",
                        "Started": "false",
                        "Reason": f"exited_{self.process.returncode}",
                        "Log": str(self.backend_log_path),
                    }
                time.sleep(0.25)

            self._ensure_watchdog_started()
            return {
                "Backend": "starting",
                "Started": "true",
                "Reason": "health_wait_timeout",
                "Log": str(self.backend_log_path),
            }

    def stop_watchdog(self) -> None:
        self._watchdog_stop.set()
        thread = self._watchdog_thread
        if (
            thread
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=1.0)
        self._watchdog_thread = None
        self._close_log_stream()

    def _ensure_watchdog_started(self) -> None:
        policy = get_backend_runtime_policy(self.repository_root)
        if not policy["watchdog_enabled"]:
            return
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            return
        self._watchdog_stop.clear()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="luxcode-backend-watchdog",
        )
        self._watchdog_thread.start()

    def _watchdog_loop(self) -> None:
        consecutive_failures = 0
        while not self._watchdog_stop.is_set():
            policy = get_backend_runtime_policy(self.repository_root)
            if self._watchdog_stop.wait(
                float(policy["watchdog_interval_seconds"])
            ):
                return

            if self._is_healthy():
                consecutive_failures = 0
                continue

            consecutive_failures += 1
            if consecutive_failures < 2:
                continue
            consecutive_failures = 0

            now = time.monotonic()
            window = float(policy["restart_window_seconds"])
            while self._restart_times and now - self._restart_times[0] > window:
                self._restart_times.popleft()
            if len(self._restart_times) >= int(
                policy["maximum_restarts_per_window"]
            ):
                continue

            self._restart_times.append(now)
            try:
                self.ensure_running(wait_seconds=6.0)
            except Exception:
                continue

    def _is_healthy(self) -> bool:
        try:
            health = self.client.health()
        except Exception:
            return False
        return health.get("status") == "ok"

    def _rotate_log_if_needed(self) -> None:
        path = self.backend_log_path
        try:
            if path.is_file() and path.stat().st_size > 5_000_000:
                rotated = path.with_suffix(".previous.log")
                rotated.unlink(missing_ok=True)
                path.replace(rotated)
        except OSError:
            return

    def _close_log_stream(self) -> None:
        stream = self._log_stream
        self._log_stream = None
        if stream is not None:
            try:
                stream.flush()
                stream.close()
            except Exception:
                pass

    def _stop_stale_backend_if_present(self) -> None:
        if os.name != "nt":
            return
        command = (
            "$conn = Get-NetTCPConnection -LocalPort 5000 -State Listen "
            "-ErrorAction SilentlyContinue | Select-Object -First 1; "
            "if ($conn) { "
            "$p = Get-CimInstance Win32_Process "
            "-Filter \"ProcessId=$($conn.OwningProcess)\"; "
            "if ($p.CommandLine -like '*app.py*') { "
            "Stop-Process -Id $conn.OwningProcess -Force "
            "} "
            "}"
        )
        try:
            sp.run(
                ["powershell", "-NoProfile", "-Command", command],
                cwd=str(self.repository_root),
                stdout=sp.DEVNULL,
                stderr=sp.DEVNULL,
                timeout=5,
                creationflags=getattr(sp, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            return
