from __future__ import annotations

import ast
import unittest
from pathlib import Path

from luxcode_desktop.api.schemas import TaskSubmitPayload
from luxcode_desktop.config import CENTER_TABS, LEFT_TABS, RIGHT_TABS
from luxcode_desktop.state import TaskState


ROOT = Path(__file__).resolve().parents[2]


class LuxCodeDesktopContractTests(unittest.TestCase):
    def test_required_tabs_are_declared(self) -> None:
        self.assertEqual(LEFT_TABS, ("Dosyalar", "Modeller", "Görevler", "Alan"))
        for tab in ("Çalışma", "Yapılan/Kalan", "Araçlar", "Plan", "Ayarlar", "Yama", "Test", "Geçmiş"):
            self.assertIn(tab, CENTER_TABS)
        self.assertNotIn("Sohbet", CENTER_TABS)
        self.assertNotIn("Model Contribution", CENTER_TABS)
        self.assertEqual(RIGHT_TABS, ("Durum", "İzinler", "Yama", "Test", "Entegrasyon", "Kanıt"))

    def test_payload_defaults_are_safe(self) -> None:
        payload = TaskSubmitPayload(task_summary="x", main_repository_root="repo").to_backend_payload()
        self.assertTrue(payload["pilot_mode"])
        self.assertTrue(payload["local_worker_enabled"])
        self.assertTrue(payload["free_gemini_enabled"])
        self.assertTrue(payload["free_cloud_enabled"])
        self.assertFalse(payload["live_external_enabled"])
        self.assertFalse(payload["paid_escalation_allowed"])
        self.assertFalse(payload["auto_apply"])
        self.assertEqual(payload["workspace_mode"], "sandbox_copy")

    def test_task_state_terminal_detection(self) -> None:
        self.assertTrue(TaskState(status="completed").is_terminal)
        self.assertTrue(TaskState(status="blocked").is_terminal)
        self.assertFalse(TaskState(status="running").is_terminal)

    def test_ui_uses_panedwindow_and_notebook(self) -> None:
        source = (ROOT / "luxcode_desktop" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("ttk.Panedwindow", source)
        self.assertIn("ttk.Notebook", source)
        self.assertIn("Sol Panel", source)
        self.assertIn("Sağ Panel", source)
        self.assertIn("Düzeni Sıfırla", source)
        self.assertIn("send_chat_message", source)
        self.assertIn("_build_conversation_stream", source)
        self.assertIn("input_shell", source)
        self.assertIn("input_area", source)
        self.assertIn("input_plus_item", source)
        self.assertIn("primary_task_button = tk.Button", source)
        self.assertIn("_enter_send_action", source)
        self.assertIn('bind("<Return>"', source)
        self.assertIn("_create_rounded_rect", source)
        self.assertIn("_resize_input_shell", source)
        self.assertIn("completed_summary", source)
        self.assertIn("remaining_summary", source)
        self.assertNotIn("_triple_status(parent)", source)

    def test_chat_runs_without_blocking_task_flow(self) -> None:
        source = (ROOT / "luxcode_desktop" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("self.chat_sending", source)
        self.assertIn("self.pending_chat_messages", source)
        self.assertIn("threading.Thread(target=worker, daemon=True).start()", source)
        self.assertIn("self.client.chat(outgoing)", source)
        self.assertIn("self.client.submit_task(payload)", source)
        self.assertIn("self._finish_chat_message(answer)", source)
        self.assertIn("_looks_like_task_request", source)
        self.assertIn("directed=True", source)

    def test_input_and_scrollbars_are_desktop_sized(self) -> None:
        source = (ROOT / "luxcode_desktop" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("height=122", source)
        self.assertIn("height=3", source)
        self.assertIn("width=760", source)
        self.assertIn("height=98", source)
        self.assertIn("INPUT_BG", source)
        self.assertIn("_dark_scrollbar", source)
        self.assertIn("width=6", source)
        self.assertIn("Erişim", source)
        self.assertIn("🎙", source)
        self.assertIn('bg="#0f1720"', source)
        self.assertIn("bg=ACCENT", source)
        self.assertIn("_build_done_remaining_tab", source)

    def test_backend_and_tools_do_not_block_ui_thread(self) -> None:
        source = (ROOT / "luxcode_desktop" / "ui" / "main_window.py").read_text(encoding="utf-8")
        backend_source = (ROOT / "luxcode_desktop" / "services" / "backend_process_service.py").read_text(encoding="utf-8")
        self.assertIn("ensure_backend_ready", source)
        self.assertIn("BackendProcessService", source)
        self.assertIn("_finish_control_action", source)
        self.assertIn("threading.Thread(target=worker, daemon=True).start()", source)
        self.assertIn("app.py", backend_source)
        self.assertIn("LUXVIAI_RELOAD", backend_source)
        self.assertIn("_stop_stale_backend_if_present", backend_source)
        self.assertIn("Get-NetTCPConnection", backend_source)

    def test_attachments_are_deduplicated_and_scoped(self) -> None:
        source = (ROOT / "luxcode_desktop" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("self.attachment_keys", source)
        self.assertIn("_begin_attachment_pick", source)
        self.assertIn("_register_attachment", source)
        self.assertIn("_append_allowed_file", source)
        self.assertIn("_safe_relative_path", source)
        self.assertIn("attachments=list(self.attachments)", source)

    def test_old_web_control_actions_are_moved_to_desktop(self) -> None:
        source = (ROOT / "luxcode_desktop" / "ui" / "main_window.py").read_text(encoding="utf-8")
        for endpoint in [
            "/luxcode-control/status",
            "/luxcode-control/repository/diagnostics",
            "/luxcode-control/search",
            "/luxcode-control/context",
            "/luxcode-control/task-plan",
            "/luxcode-control/safe-patch/preview",
            "/luxcode-control/controlled-apply/prepare",
            "/luxcode-control/validation/run",
            "/luxcode-control/approvals",
            "/luxcode-control/deferred-queue",
            "/luxcode-control/deferred-queue/resume",
            "/luxcode-control/evidence-board",
            "/luxcode-control/motor-status",
            "/luxcode-control/settings",
        ]:
            self.assertIn(endpoint, source)
        self.assertIn("run_control_action", source)
        self.assertIn("auto_apply\": False", source)

        payload_tree = ast.parse(source)
        paid_escalation_flags = []
        for node in ast.walk(payload_tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "TaskSubmitPayload":
                continue
            for keyword in node.keywords:
                if keyword.arg != "paid_escalation_allowed":
                    continue
                self.assertIsInstance(keyword.value, ast.Constant)
                paid_escalation_flags.append(keyword.value.value)

        self.assertEqual(paid_escalation_flags, [False])

    def test_old_luxcode_web_surface_is_retired(self) -> None:
        html = (ROOT / "static" / "luxcode" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Desktop'a taşındı", html)
        self.assertIn("python run_desktop.py", html)
        self.assertNotIn("/luxcode-control/first-usable/run", html)
        self.assertNotIn("id=\"taskSummary\"", html)

    def test_forbidden_desktop_behaviors_are_absent(self) -> None:
        desktop_sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "luxcode_desktop").rglob("*.py")
            if "tests" not in path.parts
        )
        forbidden = [
            "api.deepseek.com",
            "api.openai.com",
            "openrouter.ai",
            "Authorization",
            "subprocess.Popen",
            "git push",
            "git commit",
            "YOUR_API_KEY",
            "_get_tetris_fallback_code",
            "_get_snake_fallback_code",
            "_get_generic_fallback_code",
        ]
        for token in forbidden:
            self.assertNotIn(token, desktop_sources)

    def test_python_sources_parse(self) -> None:
        for path in (ROOT / "luxcode_desktop").rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


if __name__ == "__main__":
    unittest.main()
