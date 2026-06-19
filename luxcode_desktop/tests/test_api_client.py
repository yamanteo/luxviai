from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from luxcode_desktop.api.client import LuxCodeApiClient
from luxcode_desktop.api.errors import BackendConnectionError
from luxcode_desktop.api.schemas import TaskSubmitPayload


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class LuxCodeApiClientTests(unittest.TestCase):
    def test_status_uses_repository_root_query(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            return _FakeResponse({"ok": True})

        with patch("urllib.request.urlopen", fake_urlopen):
            result = LuxCodeApiClient("http://backend").status("C:/repo with space")

        self.assertTrue(result["ok"])
        self.assertIn("/luxcode-control/status?repository_root=C%3A/repo%20with%20space", captured["url"])
        self.assertEqual(captured["timeout"], 4)

    def test_submit_task_posts_safe_payload(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return _FakeResponse({"task_id": "task-1", "status": "preview"})

        payload = TaskSubmitPayload(task_summary="do work", main_repository_root="C:/repo")
        with patch("urllib.request.urlopen", fake_urlopen):
            result = LuxCodeApiClient("http://backend").submit_task(payload)

        self.assertEqual(result["task_id"], "task-1")
        self.assertEqual(captured["method"], "POST")
        self.assertTrue(captured["url"].endswith("/luxcode-task/create"))
        self.assertEqual(captured["body"]["original_request"], "do work")
        self.assertEqual(captured["body"]["repository_root"], "C:/repo")
        self.assertEqual(captured["body"]["permission_mode"], "approval_required")

    def test_connection_failure_is_classified(self) -> None:
        def fake_urlopen(_request, timeout=None):
            raise OSError("offline")

        with patch("urllib.request.urlopen", fake_urlopen):
            with self.assertRaises(BackendConnectionError):
                LuxCodeApiClient("http://backend").status()

    def test_chat_uses_normal_chat_endpoint(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return _FakeResponse({"response": "merhaba"})

        with patch("urllib.request.urlopen", fake_urlopen):
            result = LuxCodeApiClient("http://backend").chat("selam")

        self.assertEqual(result["response"], "merhaba")
        self.assertTrue(captured["url"].endswith("/chat"))
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["body"]["message"], "selam")
        self.assertEqual(captured["body"]["mode"], "luxviai")


if __name__ == "__main__":
    unittest.main()
