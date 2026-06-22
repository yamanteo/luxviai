from __future__ import annotations

import builtins
import hashlib
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from luxcode_desktop.main import requested_ui_mode, should_start_webview, try_run_webview_app
from luxcode_desktop.webview_app import WEBVIEW_TITLE, WEBVIEW_URL, WebViewLaunchError


ROOT = Path(__file__).resolve().parents[2]


class LuxCodeWebViewContractTests(unittest.TestCase):
    def test_new_html_asset_exists(self) -> None:
        html = ROOT / "static" / "luxcode_v1" / "index.html"
        self.assertTrue(html.is_file())
        source = html.read_text(encoding="utf-8")
        self.assertIn("<title>LUXCODE", source)
        self.assertIn("id=\"rightPanel\"", source)
        self.assertIn("id=\"dockedTerminalTray\"", source)

    def test_webview_panel_labels_and_order(self) -> None:
        source = (ROOT / "static" / "luxcode_v1" / "index.html").read_text(encoding="utf-8")
        tabs = re.findall(r'data-panel-tab="([^"]+)">([^<]+)</button>', source)
        self.assertEqual(
            tabs[:7],
            [
                ("integrations", "Modeller"),
                ("review", "İncele"),
                ("files", "Dosyalar"),
                ("tests", "Testler"),
                ("browser", "Tarayıcı"),
                ("evidence", "Kanıtlar"),
                ("environment", "Ortam"),
            ],
        )
        self.assertIn('<div class="connection-menu-label">ARAÇLAR</div>', source)
        self.assertIn('<div class="panel-section-kicker">MODELLER</div>', source)
        self.assertNotIn(">Bağlantılar<", source)
        self.assertNotIn("MODEL BAĞLANTILARI", source)

    def test_luxcode_v1_route_is_declared(self) -> None:
        source = (ROOT / "luxviai_pages.py").read_text(encoding="utf-8")
        self.assertTrue(
            '@router.get("/luxcode-v1/")' in source
            or '@router.api_route("/luxcode-v1/", methods=["GET", "HEAD"])' in source
        )
        self.assertIn('static_dir / "luxcode_v1" / "index.html"', source)
        self.assertTrue(
            '@router.get("/luxcode")' in source
            or '@router.api_route("/luxcode", methods=["GET", "HEAD"])' in source
        )

    def test_feature_flag_defaults_to_tkinter(self) -> None:
        self.assertEqual(requested_ui_mode({}), "tkinter")
        self.assertFalse(should_start_webview({}))
        self.assertEqual(requested_ui_mode({"LUXCODE_UI_MODE": "tkinter"}), "tkinter")

    def test_webview_mode_can_be_selected(self) -> None:
        env = {"LUXCODE_UI_MODE": "webview"}
        self.assertEqual(requested_ui_mode(env), "webview")
        self.assertTrue(should_start_webview(env))

    def test_webview_import_failure_selects_tkinter_fallback(self) -> None:
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "webview":
                raise ModuleNotFoundError("No module named 'webview'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            with patch("sys.stderr"):
                self.assertFalse(try_run_webview_app())

    def test_webview_contract_constants(self) -> None:
        self.assertEqual(WEBVIEW_URL, "http://127.0.0.1:5000/luxcode-v1/")
        self.assertEqual(WEBVIEW_TITLE, "LUXCODE")

    def test_webview_app_has_no_js_bridge(self) -> None:
        source = (ROOT / "luxcode_desktop" / "webview_app.py").read_text(encoding="utf-8")
        self.assertNotIn("js_api", source)
        self.assertNotIn("expose", source)
        self.assertNotIn("evaluate_js", source)

    def test_old_luxcode_page_is_unchanged(self) -> None:
        old_page = ROOT / "static" / "luxcode" / "index.html"
        digest = hashlib.sha256(old_page.read_bytes()).hexdigest().upper()
        self.assertEqual(
            digest,
            "1CCA895F5DA3DFB9CAC6069A2E519D13FC39D6C9A8AFFAEE09AD2BF575F88ED7",
        )

    def test_launch_error_is_explicit(self) -> None:
        self.assertTrue(issubclass(WebViewLaunchError, RuntimeError))


if __name__ == "__main__":
    unittest.main()
