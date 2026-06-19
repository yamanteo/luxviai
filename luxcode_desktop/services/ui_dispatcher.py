from __future__ import annotations

import queue
import tkinter as tk
from collections.abc import Callable


class UiDispatcher:
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self._queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._closed = False

    def post(self, callback: Callable[[], None]) -> None:
        if not self._closed:
            self._queue.put(callback)

    def pump(self) -> None:
        while not self._queue.empty():
            callback = self._queue.get_nowait()
            callback()
        if not self._closed:
            self.root.after(80, self.pump)

    def close(self) -> None:
        self._closed = True
