from __future__ import annotations

import unittest
from pathlib import Path

from luxcode_desktop.main import requested_ui_mode, should_start_webview


ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "static" / "luxcode_v1" / "index.html"
API_JS = ROOT / "static" / "luxcode_v1" / "luxcode_api.js"
STATE_JS = ROOT / "static" / "luxcode_v1" / "luxcode_state.js"


class LuxCodeWebViewTaskAdvanceContractTests(unittest.TestCase):
    def html(self) -> str:
        return HTML.read_text(encoding="utf-8")

    def api(self) -> str:
        return API_JS.read_text(encoding="utf-8")

    def state(self) -> str:
        return STATE_JS.read_text(encoding="utf-8")

    def test_advance_api_function_exists(self) -> None:
        source = self.api()
        self.assertIn("function advanceLuxCodeTask", source)
        self.assertIn("advanceLuxCodeTask,", source)

    def test_real_advance_endpoint_is_used(self) -> None:
        source = self.api()
        self.assertIn('requestJson("/luxcode-task/advance"', source)
        self.assertIn("task_id: taskId", source)
        self.assertIn('action: payload.action || "next"', source)
        self.assertNotIn("/luxcode-task/advance/", source)

    def test_second_concurrent_advance_is_blocked(self) -> None:
        source = self.state()
        self.assertIn("advanceInFlight", source)
        self.assertIn("!state.advanceInFlight", source)
        self.assertIn("if (!state.autoAdvanceActive || state.advanceInFlight) return", source)

    def test_same_state_unbounded_repeats_are_blocked(self) -> None:
        source = self.state()
        self.assertIn("lastAdvancedState", source)
        self.assertIn("lastAdvanceDigest", source)
        self.assertIn("advance_repeated_state", source)
        self.assertIn("state.lastAdvancedState === taskStatus(task)", source)

    def test_maximum_advance_limit_exists(self) -> None:
        source = self.state()
        self.assertIn("MAX_ADVANCE_ATTEMPTS", source)
        self.assertIn("advanceAttemptCount", source)
        self.assertIn("advance_attempt_limit", source)

    def test_terminal_state_stops_auto_advance(self) -> None:
        source = self.state()
        self.assertIn('["cancelled", "blocked", "failed", "completed"]', source)
        self.assertIn("isTerminalTaskState(status)", source)
        self.assertIn("stopAutoAdvance();", source)

    def test_approval_state_stops_auto_advance(self) -> None:
        source = self.state()
        self.assertIn('"awaiting_approval"', source)
        self.assertIn("USER_ACTION_STATES.has(status)", source)
        self.assertIn("task.requires_user_approval === true", source)

    def test_blocked_state_stops_auto_advance(self) -> None:
        source = self.state()
        self.assertIn('"blocked"', source)
        self.assertIn("Array.isArray(task.blocked_reasons)", source)
        self.assertIn("blocked_reasons.length > 0", source)

    def test_beforeunload_aborts_polling_and_advance(self) -> None:
        html = self.html()
        state = self.state()
        self.assertIn('window.addEventListener("beforeunload"', html)
        self.assertIn("stopTaskPolling()", html)
        self.assertIn("stopAutoAdvance()", html)
        self.assertIn("advanceAbortController.abort()", state)

    def test_polling_and_advance_state_are_separate(self) -> None:
        source = self.state()
        self.assertIn("pollingActive", source)
        self.assertIn("pollingTimer", source)
        self.assertIn("advanceInFlight", source)
        self.assertIn("autoAdvanceActive", source)
        self.assertIn("autoAdvanceTimer", source)
        self.assertIn("advanceAbortController", source)

    def test_approval_backend_is_not_bound(self) -> None:
        combined = self.html() + self.api() + self.state()
        self.assertNotIn("/luxcode-task/approve", combined)
        self.assertIn("Onay baglantisi hazirlaniyor", combined)

    def test_cancel_backend_is_not_bound(self) -> None:
        combined = self.html() + self.api() + self.state()
        self.assertNotIn("/luxcode-task/cancel", combined)
        self.assertNotIn("cancelLuxCodeTask", combined)

    def test_fake_progress_is_not_generated(self) -> None:
        html = self.html()
        self.assertIn("progressFromTask(task)", html)
        self.assertIn("task?.progress_percent", html)
        self.assertNotIn("Math.random", html)
        self.assertNotIn("7 PASS", html)
        self.assertNotIn("services/fault_report.py", html)

    def test_tkinter_fallback_is_unchanged(self) -> None:
        self.assertEqual(requested_ui_mode({}), "tkinter")
        self.assertFalse(should_start_webview({}))
        self.assertTrue(should_start_webview({"LUXCODE_UI_MODE": "webview"}))

    def test_alert_is_not_used(self) -> None:
        combined = self.html() + self.api() + self.state()
        self.assertNotIn("alert(", combined)


if __name__ == "__main__":
    unittest.main()
