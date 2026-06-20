from __future__ import annotations

import os
import sys

from luxcode_desktop.app import create_app
from luxcode_desktop.config import DEFAULT_MAIN_REPOSITORY
from luxcode_runtime_settings import (
    acquire_single_instance_lock,
    apply_persistent_runtime_environment,
    release_single_instance_lock,
    show_single_instance_notice,
)


def requested_ui_mode(environ: dict[str, str] | None = None) -> str:
    env = environ if environ is not None else os.environ
    value = env.get("LUXCODE_UI_MODE", "tkinter").strip().lower()
    return "webview" if value == "webview" else "tkinter"


def should_start_webview(environ: dict[str, str] | None = None) -> bool:
    return requested_ui_mode(environ) == "webview"


def run_tkinter_app() -> None:
    root, app = create_app()
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()


def try_run_webview_app() -> bool:
    try:
        from luxcode_desktop.webview_app import run_webview_app

        run_webview_app(DEFAULT_MAIN_REPOSITORY)
    except Exception as exc:
        print(
            f"LUXCODE WebView could not start; falling back to Tkinter: {exc}",
            file=sys.stderr,
        )
        return False
    return True


def main() -> None:
    apply_persistent_runtime_environment(DEFAULT_MAIN_REPOSITORY)
    instance_lock = acquire_single_instance_lock(DEFAULT_MAIN_REPOSITORY)
    if instance_lock is None:
        show_single_instance_notice()
        return

    try:
        if should_start_webview() and try_run_webview_app():
            return
        run_tkinter_app()
    finally:
        release_single_instance_lock(instance_lock)


if __name__ == "__main__":
    main()
