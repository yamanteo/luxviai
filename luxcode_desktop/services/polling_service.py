from __future__ import annotations

import threading
import time
from collections.abc import Callable

from luxcode_desktop.api.client import LuxCodeApiClient
from luxcode_desktop.state import TaskState


class PollingService:
    def __init__(self, client: LuxCodeApiClient, on_state: Callable[[TaskState], None], on_error: Callable[[str], None]) -> None:
        self.client = client
        self.on_state = on_state
        self.on_error = on_error
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, task_id: str) -> None:
        self.stop()
        stop_event = threading.Event()
        self._stop = stop_event
        self._thread = threading.Thread(
            target=self._run,
            args=(task_id, stop_event),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.5)
        self._thread = None

    def _run(self, task_id: str, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                state = TaskState.from_payload(self.client.get_task(task_id))
                self.on_state(state)
                if state.is_terminal:
                    return
            except Exception as exc:
                if not stop_event.is_set():
                    self.on_error(str(exc))
                return
            stop_event.wait(1.0)
