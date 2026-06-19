from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .errors import BackendConnectionError, BackendResponseError
from .schemas import TaskSubmitPayload


class LuxCodeApiClient:
    def __init__(self, base_url: str, timeout_seconds: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None, timeout_seconds: int | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds or self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BackendConnectionError(f"BACKEND CONNECTION REQUIRED: {exc}") from exc
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise BackendResponseError("Backend returned non-JSON response") from exc
        if not isinstance(parsed, dict):
            raise BackendResponseError("Backend returned unsupported JSON shape")
        return parsed

    def status(self, repository_root: str | None = None) -> dict[str, Any]:
        suffix = ""
        if repository_root:
            suffix = "?repository_root=" + urllib.parse.quote(repository_root)
        return self._request("GET", f"/luxcode-control/status{suffix}", timeout_seconds=4)

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health", timeout_seconds=3)

    def submit_task(self, payload: TaskSubmitPayload) -> dict[str, Any]:
        selected_files = list(dict.fromkeys(
            payload.selected_files
            + payload.target_files
            + payload.allowed_files
            + [
                item.get("path", "")
                for item in payload.attachments
                if isinstance(item, dict) and item.get("path")
            ]
        ))

        create_payload = {
            "original_request": payload.task_summary,
            "repository_root": payload.main_repository_root,
            "suspected_files": payload.suspected_files,
            "changed_files": [],
            "mode": (
                "read_only_analysis"
                if any(
                    marker in payload.task_summary.lower()
                    for marker in (
                        "yalnız analiz",
                        "yalnızca analiz",
                        "sadece analiz",
                        "hiçbir dosyayı değiştirme",
                        "dosya değiştirme",
                        "yama uygulama",
                        "read only",
                        "read-only",
                        "do not modify",
                        "no file changes",
                    )
                )
                else payload.execution_mode
            ),
            "traceback_text": "",
            "selected_files": selected_files,
            "requested_files": payload.target_files or payload.allowed_files,
            "forbidden_files": payload.excluded_paths,
            "permission_mode": (
                "approval_required"
                if payload.access_level != "full"
                else "session_allowed"
            ),
            "scope_items": [],
            "selected_folders": [
                item.get("path", "")
                for item in payload.attachments
                if isinstance(item, dict)
                and item.get("type") == "folder"
                and item.get("path")
            ],
            "autonomy_budgets": {
                "maximum_cost": payload.budget_limit,
                "maximum_calls": payload.call_limit,
                "maximum_seconds": payload.time_limit_seconds,
            },
        }

        return self._request(
            "POST",
            "/luxcode-task/create",
            create_payload,
        )

    def chat(self, message: str, mode: str = "luxviai") -> dict[str, Any]:
        return self._request("POST", "/chat", {
            "message": message,
            "user_id": "luxcode_desktop_user",
            "mode": mode,
            "ghost_hesitation": False,
            "location": "Konum paylaşılmadı",
            "location_latitude": None,
            "location_longitude": None,
            "location_timezone": "",
            "client_signals": {"surface": "luxcode_desktop"},
            "force_new_session": False,
        }, timeout_seconds=60)

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"/luxcode-task/{urllib.parse.quote(task_id)}")

    def endpoint(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request(method, path, payload)
