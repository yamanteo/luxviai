from __future__ import annotations

import tkinter as tk

from luxcode_desktop.ui.main_window import LuxCodeDesktopApp


def create_app() -> tuple[tk.Tk, LuxCodeDesktopApp]:
    root = tk.Tk()
    return root, LuxCodeDesktopApp(root)
