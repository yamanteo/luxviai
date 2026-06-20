from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from luxcode_desktop.api.client import LuxCodeApiClient
from luxcode_desktop.config import DEFAULT_BACKEND_URL, DEFAULT_MAIN_REPOSITORY
from luxcode_desktop.services.backend_process_service import BackendProcessService


WEBVIEW_URL = "http://127.0.0.1:5000/luxcode-v1/"
WEBVIEW_TITLE = "LUXCODE"
WEBVIEW_WIDTH = 1440
WEBVIEW_HEIGHT = 900
WEBVIEW_MIN_SIZE = (1280, 760)


class WebViewLaunchError(RuntimeError):
    pass


def wait_for_backend(
    client: LuxCodeApiClient,
    timeout_seconds: float = 15.0,
    interval_seconds: float = 0.25,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            health = client.health()
        except Exception as exc:
            last_error = str(exc)
        else:
            if health.get("status") == "ok":
                return health
            last_error = f"unexpected health payload: {health!r}"
        time.sleep(interval_seconds)
    raise WebViewLaunchError(f"backend health check timed out: {last_error}")


def run_webview_app(
    repository_root: Path = DEFAULT_MAIN_REPOSITORY,
    url: str = WEBVIEW_URL,
) -> None:
    try:
        import webview
    except Exception as exc:  # pragma: no cover - covered with mocked import failure
        raise WebViewLaunchError(f"pywebview is not available: {exc}") from exc

    client = LuxCodeApiClient(DEFAULT_BACKEND_URL)
    backend = BackendProcessService(client, repository_root)
    try:
        readiness = backend.ensure_running()
        if readiness.get("Backend") not in {"connected", "starting"}:
            raise WebViewLaunchError(f"backend could not start: {readiness}")
        wait_for_backend(client)
        webview.create_window(
            WEBVIEW_TITLE,
            url,
            width=WEBVIEW_WIDTH,
            height=WEBVIEW_HEIGHT,
            min_size=WEBVIEW_MIN_SIZE,
        )
        webview.start()
    except WebViewLaunchError:
        raise
    except Exception as exc:
        raise WebViewLaunchError(f"webview launch failed: {exc}") from exc
    finally:
        backend.stop_watchdog()
