from __future__ import annotations

import re
import unittest
from pathlib import Path

from luxcode_desktop.main import requested_ui_mode, should_start_webview


ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "static" / "luxcode_v1" / "index.html"
API_JS = ROOT / "static" / "luxcode_v1" / "luxcode_api.js"
STATE_JS = ROOT / "static" / "luxcode_v1" / "luxcode_state.js"


class LuxCodeWebViewTaskFlowContractTests(unittest.TestCase):
    def source(self) -> str:
        return HTML.read_text(encoding="utf-8")

    def test_task_flow_assets_exist_and_are_loaded_in_order(self) -> None:
        self.assertTrue(API_JS.is_file())
        self.assertTrue(STATE_JS.is_file())
        source = self.source()
        api_tag = '<script src="/static/luxcode_v1/luxcode_api.js"></script>'
        state_tag = '<script src="/static/luxcode_v1/luxcode_state.js"></script>'
        self.assertIn(api_tag, source)
        self.assertIn(state_tag, source)
        self.assertLess(source.index(api_tag), source.index(state_tag))
        self.assertLess(source.index(state_tag), source.index("<script>\n        const terminalTray"))

    def test_api_layer_owns_create_and_polling_fetches(self) -> None:
        api = API_JS.read_text(encoding="utf-8")
        html = self.source()
        self.assertIn("function createLuxCodeTask", api)
        self.assertIn('"/luxcode-task/create"', api)
        self.assertIn("function getLuxCodeTask", api)
        self.assertIn('`/luxcode-task/${encodeURIComponent(taskId)}`', api)
        self.assertIn("AbortController", api)
        self.assertIn("invalid_json", api)
        self.assertIn("normalizeApiError", api)
        self.assertNotIn("fetch(", html)

    def test_create_payload_uses_backend_contract_fields(self) -> None:
        source = self.source()
        payload_match = re.search(r"function buildCreatePayload\(taskText\) \{(?P<body>.*?)\n        \}", source, re.S)
        self.assertIsNotNone(payload_match)
        body = payload_match.group("body")
        for field in [
            "original_request",
            "mode",
            "permission_mode",
            "suspected_files",
            "changed_files",
            "traceback_text",
            "selected_files",
            "requested_files",
            "forbidden_files",
            "scope_items",
            "selected_folders",
            "autonomy_budgets",
        ]:
            self.assertIn(field, body)
        for fake_field in ["branch", "project", "active_model", "working_scope", "access_mode"]:
            self.assertNotIn(fake_field, body)

    def test_demo_task_and_alerts_are_removed(self) -> None:
        combined = self.source() + API_JS.read_text(encoding="utf-8") + STATE_JS.read_text(encoding="utf-8")
        self.assertNotIn("Fix the fault report preview chain", combined)
        self.assertNotIn("services/fault_report.py", combined)
        self.assertNotIn("7 PASS", combined)
        self.assertNotIn("alert(", combined)
        self.assertNotIn("/luxcode-conversation/", combined)

    def test_legacy_eventsource_reconnect_is_stopped(self) -> None:
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('"text/event-stream" in accept.lower()', app_source)
        self.assertIn("status_code=204", app_source)
        self.assertIn("legacy_endpoint_removed", app_source)

    def test_empty_task_is_blocked_before_create(self) -> None:
        source = self.source()
        self.assertIn("if (!task)", source)
        self.assertIn("Once bir gorev yazin", source)
        self.assertIn("setSubmitBusy(true)", source)
        self.assertIn("setSubmitBusy(false)", source)

    def test_state_layer_prevents_multiple_polling_loops(self) -> None:
        state = STATE_JS.read_text(encoding="utf-8")
        self.assertIn("currentTaskId", state)
        self.assertIn("pollingTimer", state)
        self.assertIn("pollingActive", state)
        self.assertIn("if (state.pollingActive && state.currentTaskId === safeTaskId) return", state)
        self.assertIn("window.clearTimeout(state.pollingTimer)", state)

    def test_terminal_state_stops_polling(self) -> None:
        state = STATE_JS.read_text(encoding="utf-8")
        self.assertIn('["cancelled", "blocked", "failed", "completed"]', state)
        self.assertIn("isTerminalTaskState", state)
        self.assertIn("stopTaskPolling();", state)
        self.assertIn("luxcode:task-terminal", state)

    def test_approval_state_shows_existing_card_without_backend_binding(self) -> None:
        source = self.source()
        self.assertIn('id="approvalCard"', source)
        self.assertIn('status === "awaiting_approval"', source)
        self.assertIn('setTaskState("approval")', source)
        self.assertIn("Onay baglantisi hazirlaniyor", source)
        self.assertNotIn("/luxcode-task/approve", source)

    def test_completion_uses_real_payload_without_fake_report_values(self) -> None:
        source = self.source()
        self.assertIn("function renderFinalReport(task)", source)
        self.assertIn("task.changed_files", source)
        self.assertIn("task.verification_summary", source)
        self.assertNotIn('document.getElementById("finalFiles").textContent = "1"', source)
        self.assertNotIn('document.getElementById("finalTests").textContent = "7 PASS"', source)
        self.assertNotIn("Timeout davran", source)

    def test_tkinter_fallback_contract_is_unchanged(self) -> None:
        self.assertEqual(requested_ui_mode({}), "tkinter")
        self.assertFalse(should_start_webview({}))
        self.assertTrue(should_start_webview({"LUXCODE_UI_MODE": "webview"}))


if __name__ == "__main__":
    unittest.main()
