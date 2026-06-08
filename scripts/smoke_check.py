from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
DEBUG_USER_ID = "debug_smoke"


@dataclass
class CheckResult:
    status: str
    name: str
    detail: str = ""


class SmokeRunner:
    def __init__(self) -> None:
        self.results: list[CheckResult] = []
        self.temp_dirs: list[Path] = []
        self.app_module: Any | None = None
        self.temp_root: Path | None = None
        self.raw_phrase = "SMOKE_RAW_" + uuid.uuid4().hex

    def add(self, status: str, name: str, detail: str = "") -> None:
        self.results.append(CheckResult(status=status, name=name, detail=detail))
        suffix = f" - {detail}" if detail else ""
        print(f"{status} {name}{suffix}")

    def pass_(self, name: str, detail: str = "") -> None:
        self.add("PASS", name, detail)

    def fail(self, name: str, detail: str = "") -> None:
        self.add("FAIL", name, detail)

    def skip(self, name: str, detail: str = "") -> None:
        self.add("SKIP", name, detail)

    def check(self, name: str, fn: Callable[[], str | None]) -> None:
        try:
            detail = fn() or ""
            self.pass_(name, detail)
        except SkipCheck as exc:
            self.skip(name, str(exc))
        except Exception as exc:
            self.fail(name, f"{type(exc).__name__}: {exc}")

    def make_temp_dir(self, prefix: str) -> Path:
        path = Path(tempfile.mkdtemp(prefix=prefix))
        self.temp_dirs.append(path)
        return path

    def cleanup(self) -> None:
        for path in reversed(self.temp_dirs):
            shutil.rmtree(path, ignore_errors=True)

    def run_subprocess(self, args: list[str], *, name: str) -> str:
        cache = self.make_temp_dir(f"lux_smoke_{name}_pycache_")
        env = os.environ.copy()
        env["PYTHONPYCACHEPREFIX"] = str(cache)
        proc = subprocess.run(
            args,
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=90,
        )
        if proc.returncode != 0:
            out = (proc.stdout + proc.stderr).strip()
            raise AssertionError(out[-1000:] or f"exit={proc.returncode}")
        return "ok"

    def import_app(self) -> Any:
        if self.app_module is not None:
            return self.app_module
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(ROOT))
        import app as luxapp

        self.temp_root = self.make_temp_dir("lux_smoke_app_")
        luxapp.USERS_DIR = self.temp_root / "users"
        luxapp.USERS_DIR.mkdir(parents=True, exist_ok=True)
        luxapp.cost_logger = luxapp.CostLogger(self.temp_root)
        luxapp.STREAM_CHUNK_DELAY = 0
        self.app_module = luxapp
        return luxapp

    def check_py_compile_app(self) -> str:
        return self.run_subprocess([sys.executable, "-m", "py_compile", "app.py"], name="app")

    def check_compileall_learning(self) -> str:
        return self.run_subprocess([sys.executable, "-m", "compileall", "-q", "learning"], name="learning")

    def check_health_shape(self) -> str:
        luxapp = self.import_app()
        assert len(luxapp.ANALYSIS_LAYER_NAMES) == 16
        return "16 layers"

    def check_count_guard(self) -> str:
        luxapp = self.import_app()
        cases = [
            (
                "5 tane rastgele paragraf yaz",
                "Bir.\n\nIki.\n\nUc.\n\nDort.\n\nBes.\n\nAlti.",
                "paragraph",
                5,
            ),
            (
                "3 madde yaz",
                "- Bir\n- Iki\n- Uc\n- Dort",
                "bullet",
                3,
            ),
            (
                "on listelik günlük plan yaz",
                "1. Bir\n2. Iki\n3. Uc\n4. Dort\n5. Bes\n6. Alti\n7. Yedi\n8. Sekiz\n9. Dokuz\n10. On\n11. Fazla",
                "bullet",
                10,
            ),
            (
                "10'luk liste yap",
                "1. Bir\n2. Iki\n3. Uc\n4. Dort\n5. Bes\n6. Alti\n7. Yedi\n8. Sekiz\n9. Dokuz\n10. On\n11. Fazla",
                "bullet",
                10,
            ),
            (
                "tek cumle cevap ver",
                "Birinci cumle. Ikinci cumle.",
                "sentence",
                1,
            ),
            (
                "Tam sayfa satir uzunlugunda bes satir yaz.",
                "Bir\nIki\nUc\nDort\nBes\nAlti",
                "line",
                5,
            ),
        ]
        for message, response, kind, target in cases:
            constraints = luxapp.extract_count_constraints(message)
            assert constraints, message
            assert constraints[0]["kind"] == kind, constraints
            repaired = luxapp.enforce_count_guard({"kind": "command", "count_constraints": constraints}, response)
            actual = luxapp.count_constraint_units(repaired, constraints[0])
            assert actual == target, (message, actual, repaired)
            assert luxapp.count_constraints_satisfied(repaired, constraints), (message, repaired)
        return "paragraph/bullet/sentence"

    def formatted_paragraph_blocks(self, text: str) -> list[list[str]]:
        blocks: list[list[str]] = []
        for block in str(text or "").split("\n\n"):
            lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
            if lines and lines[0].rstrip(".").isdigit():
                lines = lines[1:]
            if lines:
                blocks.append(lines)
        return blocks

    def assert_complete_long_lines(self, luxapp: Any, lines: list[str], context: str) -> None:
        broken = {"ve", "veya", "ya", "ya da", "cunku", "çünkü", "ama", "ile", "icin", "için", "gibi", "olan"}
        assert lines, context
        for line in lines:
            folded_last = luxapp.fold_turkish_ascii(line.split()[-1].strip(".,;:!?"))
            assert luxapp.count_words(line) >= 18 and len(line) >= 110, (context, line)
            assert line.strip()[-1] in ".!?", (context, line)
            assert folded_last not in broken, (context, line)

    def check_line_format_guard(self) -> str:
        luxapp = self.import_app()
        cases = [
            (
                "Her paragraf 5 satir olsun. 2 paragraf yaz.",
                "Birinci paragraf yeterince uzun bir test metni olarak burada duruyor.\n\n"
                "Ikinci paragraf da yeterince uzun bir test metni olarak burada duruyor.",
                2,
                5,
            ),
            (
                "Her biri 5 satir olan 3 paragraf yaz.",
                "Birinci paragraf yeterince uzun bir test metni olarak burada duruyor.\n\n"
                "Ikinci paragraf da yeterince uzun bir test metni olarak burada duruyor.\n\n"
                "Ucuncu paragraf da yeterince uzun bir test metni olarak burada duruyor.",
                3,
                5,
            ),
            (
                "Toplam 30 paragraf yaz, her paragraf tam 5 satir olsun.",
                "\n\n".join(f"Paragraf {i} yeterince uzun bir test metni olarak burada duruyor." for i in range(1, 31)),
                30,
                5,
                False,
            ),
            (
                "Her paragraf tam sayfa uzunlugunda ve toplam 5 satir olsun. 2 paragraf yaz.",
                "Birinci paragraf kisa bir test metni.\n\nIkinci paragraf kisa bir test metni.",
                2,
                5,
                True,
            ),
            (
                "Her biri 5 uzun satir olan 3 paragraf yaz.",
                "Birinci paragraf kisa bir test metni.\n\nIkinci paragraf kisa bir test metni.\n\nUcuncu paragraf kisa bir test metni.",
                3,
                5,
                True,
            ),
        ]
        for case in cases:
            if len(case) == 4:
                message, response, paragraph_target, line_target = case
                expect_long = False
            else:
                message, response, paragraph_target, line_target, expect_long = case
            count_constraints = luxapp.extract_count_constraints(message)
            line_constraints = luxapp.extract_line_format_constraints(message)
            assert count_constraints and count_constraints[0]["target"] == paragraph_target, (message, count_constraints)
            assert line_constraints and line_constraints[0]["lines"] == line_target, (message, line_constraints)
            repaired = luxapp.enforce_line_format_guard(
                {"count_constraints": count_constraints, "line_format_constraints": line_constraints},
                response,
            )
            assert "---" not in repaired, repaired
            blocks = self.formatted_paragraph_blocks(repaired)
            assert len(blocks) == paragraph_target, (message, len(blocks), repaired)
            assert all(len(block) == line_target for block in blocks), (message, blocks[:2], repaired)
            if expect_long:
                for block in blocks:
                    self.assert_complete_long_lines(luxapp, block, message)

        line_message = "Tam sayfa uzunluk bes satir yazi yaz."
        line_constraints = luxapp.extract_line_format_constraints(line_message)
        count_constraints = luxapp.extract_count_constraints(line_message)
        assert count_constraints and count_constraints[0]["kind"] == "line" and count_constraints[0]["target"] == 5, count_constraints
        repaired = luxapp.enforce_line_format_guard(
            {"count_constraints": count_constraints, "line_format_constraints": line_constraints},
            "Kisa test metni.",
        )
        lines = [ln for ln in repaired.splitlines() if ln.strip()]
        assert len(lines) == 5, repaired
        self.assert_complete_long_lines(luxapp, lines, line_message)
        assert "---" not in repaired, repaired
        return "paragraph/long-line exact"

    def check_format_prompt_and_cleanup(self) -> str:
        luxapp = self.import_app()
        prompt = luxapp.build_system_prompt(
            luxapp.default_profile(),
            {},
            "luxviai",
            [],
            {},
            "Konum paylaşılmadı",
        )
        assert "FORMAT / COUNT DISCIPLINE" in prompt, prompt[-1200:]
        assert "tam 5 fiziksel satır" in prompt, prompt[-1200:]
        assert "50 madde" in prompt, prompt[-1200:]
        assert "Hatalı noktalama" in prompt, prompt[-1200:]

        cleaned = luxapp.cleanup_natural_language_output("Merhaba., dünya,. test.., tamam,, olur;, bitti.")
        for bad in (".,", ",.", "..,", ",,", ";,"):
            assert bad not in cleaned, cleaned
        assert "  " not in luxapp.cleanup_natural_language_output("Iki  bosluk")

        code = "```python\ntext = '.,'\n```"
        assert luxapp.cleanup_natural_language_output(code) == code
        structured = '{"punct": ".,", "ok": true}'
        assert luxapp.cleanup_natural_language_output(structured) == structured
        return "format prompt/punctuation cleanup"

    def check_identity_guard(self) -> str:
        luxapp = self.import_app()
        profile = luxapp.default_profile()
        profile = luxapp.apply_identity_guard(profile, "selam burak kut")
        identity = profile["identity_memory"]
        assert identity.get("preferred_name") == "", identity

        for phrase in ["selam ibrahim", "merhaba poncik", "selam burak kut"]:
            profile = luxapp.default_profile()
            profile = luxapp.apply_identity_guard(profile, phrase)
            identity = profile["identity_memory"]
            assert identity.get("preferred_name") == "", (phrase, identity)
            rejected = [luxapp.identity_name_key(x) for x in identity.get("rejected_names", [])]
            assert any(x in rejected for x in ("ibrahim", "poncik", "burak")), (phrase, rejected)

        profile = luxapp.default_profile()
        profile = luxapp.apply_identity_guard(profile, "sana ibrahim diyorum")
        identity = profile["identity_memory"]
        assert identity.get("preferred_name") == "", identity
        assert "ibrahim" in [luxapp.identity_name_key(x) for x in identity.get("rejected_names", [])], identity

        profile = luxapp.apply_identity_guard(profile, "sana diyorum sana boyle sesleniyorum")
        assert profile["identity_memory"].get("preferred_name") == "", profile["identity_memory"]

        profile = luxapp.default_profile()
        profile = luxapp.apply_identity_guard(profile, "Burak Kut'u sever misin?")
        identity = profile["identity_memory"]
        assert identity.get("preferred_name") == "", identity

        profile = luxapp.default_profile()
        profile = luxapp.apply_identity_guard(profile, "ben Burak degilim")
        rejected = [luxapp.identity_name_key(x) for x in profile["identity_memory"].get("rejected_names", [])]
        assert "burak" in rejected, rejected

        cleaned = luxapp.sanitize_false_addressing(
            "Selam Burak. Hazirim.",
            {"message": "selam burak kut", "identity_boundary": "chat", "profile": luxapp.default_profile()},
        )
        assert "Burak" not in cleaned, cleaned
        cleaned = luxapp.sanitize_false_addressing(
            "Tamam, Burak diye seslenecegim.",
            {"message": "ben sana Burak dedim", "identity_boundary": "chat", "profile": luxapp.default_profile()},
        )
        assert "Burak diye" not in cleaned and "hitap" in cleaned.lower(), cleaned

        explicit = luxapp.apply_identity_guard(luxapp.default_profile(), "bana Atlas de")
        assert explicit["identity_memory"].get("preferred_name") == "Atlas", explicit["identity_memory"]
        explicit = luxapp.apply_identity_guard(luxapp.default_profile(), "benim adim Teoman")
        assert explicit["identity_memory"].get("preferred_name") == "Teoman", explicit["identity_memory"]
        profile = luxapp.apply_identity_guard(profile, "bana Ibrahim de")
        assert profile["identity_memory"].get("preferred_name") == "Ibrahim", profile["identity_memory"]
        return "no nickname inference"

    def check_double_response_trim(self) -> str:
        luxapp = self.import_app()
        text = (
            "Bana nasil hitap etmemi istersin? Yoksa direkt konuya girelim mi? "
            "Anladim, direkt konuya girelim o zaman. Ilk adim sudur."
        )
        trimmed = luxapp.trim_self_answer_after_question(text)
        assert trimmed.endswith("mi?"), trimmed
        assert "Anladim" not in trimmed and "Ilk adim" not in trimmed, trimmed
        normal = "Hazir misin? Istersen iki secenek sunayim."
        assert luxapp.trim_self_answer_after_question(normal) == normal
        return "question self-answer trimmed"

    def check_frontend_resume_scaffold(self) -> str:
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        assert "function isContinueCommand" in html
        assert "cleanBaseText.slice(-1200)" in html
        assert "function cleanInterruptedPartialText" in html
        assert "function analyzeContinuationBoundary" in html
        assert "function buildContinuationBoundaryInstruction" in html
        assert "lastNumber" in html
        assert "nextNumber" in html
        assert "safePartialText" in html
        assert "generatedAnswerBuffer" in html
        assert "function armContinuationSuffix" in html
        assert "const armSuffix = armContinuationSuffix(cleanBaseText, state.generatedAnswerBuffer)" in html
        assert "writer.push(armSuffix)" in html
        assert "align-self: flex-end" in html
        assert "margin: 8px 0 18px auto" in html
        assert "const previousBuffer = String(state.generatedAnswerBuffer || \"\")" in html
        assert "appendResumeButton(targetAiEl)" in html
        assert "function catchUpActiveWriter" in html
        assert "document.addEventListener(\"visibilitychange\", catchUpActiveWriter)" in html
        assert "window.addEventListener(\"focus\", catchUpActiveWriter)" in html
        assert "writer.catchUp" in html
        assert "resumeUnavailableFallback" in html
        assert "Ekranda zaten görünen metin, aynen korunacak" in html
        assert "interruptedState && isContinueCommand(text)" in html
        assert "if (interruptedState) {\n    clearInterruptedState(true);" in html
        assert '"devam et ama yeni konu' not in html
        assert '"kaldığın yerden devam et"' in html
        assert '"sürdür"' in html
        assert "function hardCancelActiveTransport" in html
        assert "let activeRunId = null" in html
        assert "const stoppedRunIds = new Set()" in html
        assert "function markRunStarted" in html
        assert "function isRunStopped" in html
        assert "wsPending.socket === socket" in html
        assert 'socket.close(1000, "stopped_by_user")' in html
        assert "if (!streamed && typeof onFinal === \"function\") onFinal(finalText)" in html
        assert "isBubbleForRun(targetEl, runId)" in html
        assert "responseRunId += 1" in html
        assert "isRunActive(runId)" in html
        assert "activeFetchController.abort" in html
        assert 'dataset.streamState = "cancelled"' in html
        assert "streamAbort({ showResume: true })" in html
        assert "const shouldShowResume = options.showResume !== false" in html
        assert "if (shouldShowResume) appendResumeButton(aiDiv)" in html
        assert "else clearInterruptedState(true)" in html
        assert "btn.disabled = true" in html
        assert "createPacedWriter(aiDiv, 0.9, runId)" in html
        assert "createPacedWriter(targetAiEl, 0.9, continueRunId)" in html
        assert "if (stopped || !chunk || !runStillActive()) return" in html
        assert 'reject(new Error("stale_run"))' in html
        assert "continueInterruptedResponse(targetAiEl)" in html
        assert "continuationBoundary" in html
        assert "boundaryInstruction" in html
        assert "Madde/listede kaldıysan bir sonraki madde" in html
        assert "Sadece bu metne eklenecek devam kısmını üret" in html
        return "safe resume/hard-stop context"

    def check_cost_logger_privacy(self) -> str:
        from learning.cost_logger import CostLogger, build_safe_cost_row

        base = self.make_temp_dir("lux_smoke_cost_")
        logger = CostLogger(base)
        logger.record(
            endpoint="/chat",
            route="model",
            user_message=self.raw_phrase,
            assistant_response=self.raw_phrase,
            shadow_compare_enabled=True,
            shadow_compare_route="short_technical_candidate",
            shadow_compare_summary={
                "route": "short_technical_candidate",
                "would_keep": ["safety", "identity_guard", self.raw_phrase],
                "would_limit_history_to": 3,
                "would_skip": ["group3_deep", "group4_deep", "long_memory", self.raw_phrase],
                "estimated_saved_chars": 1200,
                "confidence": 0.82,
                "raw": self.raw_phrase,
            },
            proposed_skipped_layers=["group3_deep", self.raw_phrase],
            reason_tags=["short_technical_candidate", self.raw_phrase],
            prompt_chars=400,
            history_chars=80,
        )
        text = logger.path.read_text(encoding="utf-8")
        assert self.raw_phrase not in text
        row = json.loads(text.strip())
        assert set(row).issubset(set(build_safe_cost_row().keys()))
        assert row["shadow_compare_enabled"] is True
        assert row["shadow_compare_summary"]["would_skip"] == ["group3_deep", "group4_deep", "long_memory"]
        return "raw-free safe fields"

    def check_practical_support(self) -> str:
        from learning.practical_support_layers import build_practical_support_bundle, neutral_practical_support_bundle

        neutral = neutral_practical_support_bundle().to_safe_dict()
        assert neutral["active"] is False
        assert neutral["context_injected"] is False
        assert neutral["context_injection_count"] == 0
        bundle = build_practical_support_bundle("Kafam karisti proje para CV hepsi ust uste geldi").to_safe_dict()
        assert bundle["active"] is False
        assert bundle["context_injected"] is False
        assert bundle["context_injection_count"] == 0
        return "passive"

    def check_token_budget(self) -> str:
        from learning.token_budget_policy import TokenBudgetPolicy

        decision = TokenBudgetPolicy().classify(message="git status sonucu bu").to_safe_dict()
        assert decision["observe_only"] is True
        assert decision["active"] is False
        assert decision["budget_class"] in {"short_technical", "normal_chat"}
        count_decision = TokenBudgetPolicy().classify(
            message="5 paragraf yaz",
            count_constraints=[{"kind": "paragraph", "target": 5}],
        ).to_safe_dict()
        assert count_decision["count_constraint_present"] is True
        assert count_decision["active"] is False
        return "observe_only"

    def check_efficiency_and_shadow(self) -> str:
        from learning.efficiency_router import EfficiencyRouter

        router = EfficiencyRouter()
        base = {
            "mode": "luxviai",
            "prompt_chars": 9000,
            "context_chars": 5000,
            "history_message_count": 18,
            "history_chars": 7200,
            "context_item_count": 16,
            "selected_layer_count": 16,
        }
        short = router.dry_run(message="git status sonucu bu", **base).shadow_compare(5000)
        assert short["shadow_compare_enabled"] is True, short
        assert short["shadow_compare_route"] == "short_technical_candidate", short
        assert short["shadow_compare_summary"]["would_skip"] == ["group3_deep", "group4_deep", "long_memory"], short

        disabled = [
            router.dry_run(message="cok kotu hissediyorum", analysis={"needs_presence": True, "intensity": 8}, **base),
            router.dry_run(message="ruyamda kapi gordum", **base),
            router.dry_run(message="5 paragraf yaz", count_constraints=[{"kind": "paragraph", "target": 5}], **base),
            router.dry_run(message="ben Burak degilim", identity_boundary="identity", **base),
            router.dry_run(message="debug safety", analysis={"crisis_risk": True}, **base),
            router.dry_run(message="git status sonucu bu", mode="luxeph", **{k: v for k, v in base.items() if k != "mode"}),
        ]
        for decision in disabled:
            shadow = decision.shadow_compare(5000)
            assert shadow["shadow_compare_enabled"] is False, shadow
            assert shadow["proposed_context_chars"] == shadow["current_context_chars"], shadow
        assert router.observe_only is True
        return "dry-run only"

    def check_auto_continuation(self) -> str:
        luxapp = self.import_app()
        plan = {"kind": "model", "skip_save": False, "mode": "luxviai", "message": "uzun rapor yaz", "count_constraints": []}
        assert luxapp.should_auto_continue_response("length", "Bitmemis cevap", plan) is True
        parsed = luxapp.extract_count_constraints("on listelik günlük plan yaz")
        assert parsed and parsed[0]["kind"] == "bullet" and parsed[0]["target"] == 10
        partial_ten = "\n".join(f"{i}. Madde {i}" for i in range(1, 6))
        ten_plan = {
            "kind": "model",
            "skip_save": False,
            "mode": "luxviai",
            "message": "on listelik günlük plan yaz",
            "count_constraints": [{"kind": "bullet", "target": 10, "limit": "exact"}],
        }
        assert luxapp.should_auto_continue_response("stop", partial_ten, ten_plan) is True
        bullets = "\n".join(f"- Madde {i}" for i in range(1, 21))
        count_plan = {
            "kind": "model",
            "skip_save": False,
            "mode": "luxviai",
            "message": "20 madde yaz",
            "count_constraints": [{"kind": "bullet", "target": 20, "limit": "exact"}],
        }
        assert luxapp.should_auto_continue_response("length", bullets, count_plan) is False
        return "length simulation/count stop/list resume target"

    def patch_app_for_api(self) -> Any:
        luxapp = self.import_app()
        luxapp.client = object()
        luxapp.STREAM_CHUNK_DELAY = 0
        luxapp.cost_logger = luxapp.CostLogger(self.temp_root or self.make_temp_dir("lux_smoke_api_"))
        return luxapp

    def check_api_schema(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        health = client.get("/health")
        assert health.status_code == 200, health.text
        health_json = health.json()
        assert len(health_json.get("analysis_layers", [])) == 16, health_json

        chat = client.post("/chat", json={"message": "!cmd:yardim", "mode": "luxviai", "user_id": DEBUG_USER_ID})
        assert chat.status_code == 200, chat.text
        chat_json = chat.json()
        assert "response" in chat_json and "meta" in chat_json, chat_json
        return "/health /chat"

    def check_agent_capabilities_api(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/agent/capabilities")
        assert response.status_code == 200, response.text
        data = response.json()
        personal = data.get("personal_capabilities")
        luxway = data.get("luxway_capabilities")
        required_personal = {
            "weekly_summary",
            "task_followup",
            "email_summary",
            "message_summary",
            "calendar_overview",
            "file_finder",
            "device_cleanup_suggestions",
            "app_usage_review",
            "notification_priority",
            "phone_assistant_luxway",
            "workspace_helper",
            "cv_helper",
            "report_helper",
            "presentation_helper",
        }
        required_luxway = {
            "read_emails",
            "read_messages",
            "draft_message",
            "call_contact",
            "open_app",
            "scan_unused_apps",
            "scan_storage_usage",
            "app_cleanup_suggestions",
            "notification_digest",
            "device_health_summary",
        }
        assert isinstance(personal, list) and required_personal.issubset({item.get("id") for item in personal}), personal
        assert isinstance(luxway, list) and required_luxway.issubset({item.get("id") for item in luxway}), luxway
        assert data.get("platform_permissions", {}).get("android"), data
        assert data.get("platform_permissions", {}).get("ios"), data
        return "agent capabilities"

    def check_ws_stream_schema(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        original_prepare = luxapp.prepare_chat_plan
        original_stream = luxapp.stream_model
        original_finalize = luxapp.finalize_chat
        original_background = luxapp.apply_background_nudges
        original_sanitize = luxapp.sanitize_false_addressing
        original_enforce = luxapp.enforce_count_guard
        try:
            def fake_plan(user_id: str, message: str, mode: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
                session = luxapp.default_session("luxviai")
                return {
                    "kind": "model",
                    "skip_save": True,
                    "active": None,
                    "session": session,
                    "profile": luxapp.default_profile(),
                    "notes": [],
                    "garden": [],
                    "analysis": {"primary_emotion": "neutral", "theme": "debug", "cognitive_load": "low"},
                    "prompt": "debug smoke prompt",
                    "openai_messages": [{"role": "system", "content": "debug"}],
                    "model": "debug-model",
                    "temperature": 0.1,
                    "max_tokens": 120,
                    "weekly_report": {},
                    "memory_preview": [],
                    "learning_context": {"context_text": "", "context_items": []},
                    "identity_boundary": "chat",
                    "count_constraints": [],
                    "token_budget": {"budget_class": "short_technical", "observe_only": True, "active": False},
                    "user_id": DEBUG_USER_ID,
                    "mode": "luxviai",
                    "message": "debug stream smoke",
                }

            def fake_stream(*args: Any, **kwargs: Any):
                yield {"text": "alpha ", "finish_reason": ""}
                yield {"text": "beta", "finish_reason": "stop"}

            luxapp.prepare_chat_plan = fake_plan
            luxapp.stream_model = fake_stream
            luxapp.finalize_chat = lambda plan, response_text: {}
            luxapp.apply_background_nudges = lambda plan, response_text: response_text
            luxapp.sanitize_false_addressing = lambda response_text, plan: response_text
            luxapp.enforce_count_guard = lambda plan, response_text: response_text

            client = TestClient(luxapp.app)
            with client.websocket_connect("/ws/chat") as ws:
                ws.send_json({"message": "debug stream smoke", "mode": "luxviai", "user_id": DEBUG_USER_ID})
                seen: list[str] = []
                chunks: list[str] = []
                done: dict[str, Any] | None = None
                for _ in range(10):
                    msg = ws.receive_json()
                    seen.append(str(msg.get("type")))
                    if msg.get("type") == "chunk":
                        chunks.append(str(msg.get("text", "")))
                    if msg.get("type") == "done":
                        done = msg
                        break
                assert seen[0] == "typing", seen
                assert "chunk" in seen and "done" in seen, seen
                assert done is not None and "response" in done and "meta" in done, done
                assert done["response"] == "".join(chunks), (done, chunks)
        finally:
            luxapp.prepare_chat_plan = original_prepare
            luxapp.stream_model = original_stream
            luxapp.finalize_chat = original_finalize
            luxapp.apply_background_nudges = original_background
            luxapp.sanitize_false_addressing = original_sanitize
            luxapp.enforce_count_guard = original_enforce
        return "typing/chunk/done"

    def check_agent_privacy_rules_present(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/agent/capabilities")
        assert response.status_code == 200, response.text
        data = response.json()
        rules = data.get("privacy_rules", [])
        assert isinstance(rules, list) and rules, rules
        joined = " ".join(str(x).lower() for x in rules)
        assert "onay" in joined, rules
        assert "permission" in joined, rules
        return "privacy rule checks"

    def check_luxway_capabilities_planned_inactive(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/agent/capabilities")
        assert response.status_code == 200, response.text
        luxway = response.json().get("luxway_capabilities", [])
        assert isinstance(luxway, list) and luxway, luxway
        assert all(item.get("enabled") is False for item in luxway), luxway
        assert all(str(item.get("status")) == "planned" for item in luxway), luxway
        return "luxway planned/inactive"

    def check_memory_schema_contains_fields(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        required = {
            "id",
            "type",
            "title",
            "summary",
            "source_modality",
            "sensitivity",
            "retention",
            "created_at",
            "updated_at",
            "tags",
            "raw_data_stored",
        }
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/memory/schema")
        assert response.status_code == 200, response.text
        payload = response.json()
        schema = payload.get("schema", {})
        assert required.issubset(set(schema.get("required_fields", []))), schema
        assert "templates" in payload and isinstance(payload.get("templates"), list), payload
        assert "signal_types" in schema and isinstance(schema.get("signal_types"), list), schema
        return "memory schema fields"

    def check_memory_preview_signal_privacy(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.post(
            "/memory/preview_signal",
            json={
                "type": "text_preference",
                "title": "test sinyal",
                "summary": "özet",
                "source_modality": "text",
                "sensitivity": "low",
                "retention": "session",
                "raw_data_stored": True,
                "tags": ["test", "smoke"],
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        signal = payload.get("signal", {})
        assert payload.get("ok") is True, payload
        assert signal.get("raw_data_stored") is False, payload
        assert signal.get("title"), payload
        assert signal.get("summary"), payload
        assert any("raw_data_stored_enforced_false" in str(x) for x in payload.get("checks", [])), payload
        return "memory preview raw false"

    def check_high_risk_agent_confirmation(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/agent/capabilities")
        assert response.status_code == 200, response.text
        payload = response.json()
        all_caps = payload.get("all_capabilities", [])
        assert isinstance(all_caps, list) and all_caps, all_caps
        high_caps = [cap for cap in all_caps if str(cap.get("risk_level")).lower() == "high"]
        assert high_caps, "No high-risk caps found"
        assert all(bool(cap.get("requires_user_confirmation")) for cap in high_caps), high_caps
        return "high-risk confirmation required"

    def check_agent_preview_intent_read_only(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        email_response = client.post(
            "/agent/preview_intent",
            json={"text": "maillerimi ozetle", "source_modality": "text"},
        )
        assert email_response.status_code == 200, email_response.text
        email_payload = email_response.json()
        email_preview = email_payload.get("agent_preview", {})
        email_ids = {item.get("id") for item in email_preview.get("matched_capabilities", [])}
        assert {"email_summary", "read_emails"} & email_ids, email_payload
        assert email_payload.get("read_only") is True, email_payload
        assert email_payload.get("raw_data_stored") is False, email_payload
        assert email_payload.get("write_performed") is False, email_payload

        risky_response = client.post(
            "/agent/preview_intent",
            json={"text": "Ahmet'e mesaj at", "source_modality": "text"},
        )
        assert risky_response.status_code == 200, risky_response.text
        risky_payload = risky_response.json()
        risky_preview = risky_payload.get("agent_preview", {})
        assert risky_preview.get("risk_level") == "high" or risky_preview.get("requires_user_confirmation") is True, risky_payload
        assert risky_payload.get("read_only") is True, risky_payload
        assert risky_payload.get("raw_data_stored") is False, risky_payload
        assert risky_payload.get("write_performed") is False, risky_payload

        visual_response = client.post(
            "/agent/preview_intent",
            json={"text": "bu gorselde amber isik ve Luxviai imzasini seviyorum", "source_modality": "text"},
        )
        assert visual_response.status_code == 200, visual_response.text
        visual_payload = visual_response.json()
        memory_preview = visual_payload.get("memory_preview", {})
        signal_types = {item.get("type") for item in memory_preview.get("candidate_signals", [])}
        assert {"visual_preference", "lux_visual_style", "lux_ambrosia_reference"} & signal_types, visual_payload
        assert memory_preview.get("read_only") is True, visual_payload
        assert memory_preview.get("raw_data_stored") is False, visual_payload
        assert visual_payload.get("write_performed") is False, visual_payload
        return "agent intent/memory preview read-only"

    def check_agent_plan_action_read_only(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        email_response = client.post(
            "/agent/plan_action",
            json={"text": "maillerimi \u00f6zetle", "source_modality": "text"},
        )
        assert email_response.status_code == 200, email_response.text
        email_payload = email_response.json()
        email_plan = email_payload.get("action_plan", {})
        email_ids = {item.get("id") for item in email_plan.get("matched_capabilities", [])}
        assert {"email_summary", "read_emails"} & email_ids, email_payload
        assert email_payload.get("read_only") is True, email_payload
        assert email_plan.get("read_only") is True, email_payload
        assert email_plan.get("can_execute_now") is False, email_payload
        assert email_plan.get("raw_data_stored") is False, email_payload
        assert email_payload.get("raw_data_stored") is False, email_payload
        assert email_payload.get("write_performed") is False, email_payload

        risky_response = client.post(
            "/agent/plan_action",
            json={"text": "Ahmet'e mesaj at", "source_modality": "text"},
        )
        assert risky_response.status_code == 200, risky_response.text
        risky_payload = risky_response.json()
        risky_plan = risky_payload.get("action_plan", {})
        assert risky_plan.get("risk_level") == "high" or risky_plan.get("requires_user_confirmation") is True, risky_payload
        assert risky_plan.get("execution_status") == "not_executed", risky_payload
        assert risky_plan.get("can_execute_now") is False, risky_payload
        assert risky_payload.get("write_performed") is False, risky_payload

        phone_response = client.post(
            "/agent/plan_action",
            json={"text": "telefonu tara kullan\u0131lmayan uygulamalar\u0131 bul", "source_modality": "text"},
        )
        assert phone_response.status_code == 200, phone_response.text
        phone_payload = phone_response.json()
        phone_plan = phone_payload.get("action_plan", {})
        phone_ids = {item.get("id") for item in phone_plan.get("matched_capabilities", [])}
        expected_phone = {"device_cleanup_suggestions", "app_usage_review", "phone_assistant_luxway"}
        assert expected_phone & phone_ids, phone_payload
        assert phone_plan.get("requires_user_confirmation") is True, phone_payload
        assert phone_plan.get("can_execute_now") is False, phone_payload

        cv_response = client.post(
            "/agent/plan_action",
            json={"text": "CV haz\u0131rla", "source_modality": "text"},
        )
        assert cv_response.status_code == 200, cv_response.text
        cv_payload = cv_response.json()
        cv_plan = cv_payload.get("action_plan", {})
        cv_ids = {item.get("id") for item in cv_plan.get("matched_capabilities", [])}
        assert "cv_helper" in cv_ids, cv_payload
        assert cv_plan.get("risk_level") in {"low", "medium"}, cv_payload
        assert cv_plan.get("can_execute_now") is False, cv_payload
        assert cv_plan.get("execution_status") == "not_executed", cv_payload
        assert cv_payload.get("write_performed") is False, cv_payload
        return "agent action plan read-only"

    def check_agent_analyze_hub_read_only(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        email_response = client.post(
            "/agent/analyze",
            json={"text": "maillerimi \u00f6zetle", "source_modality": "text"},
        )
        assert email_response.status_code == 200, email_response.text
        email_payload = email_response.json()
        email_analysis = email_payload.get("analysis", {})
        assert email_analysis.get("recommended_mode") == "personal_agent", email_payload
        assert email_payload.get("read_only") is True, email_payload
        assert email_analysis.get("read_only") is True, email_payload
        assert email_analysis.get("can_execute_now") is False, email_payload
        assert email_analysis.get("raw_data_stored") is False, email_payload

        phone_response = client.post(
            "/agent/analyze",
            json={"text": "telefonu tara kullan\u0131lmayan uygulamalar\u0131 bul", "source_modality": "text"},
        )
        assert phone_response.status_code == 200, phone_response.text
        phone_payload = phone_response.json()
        phone_analysis = phone_payload.get("analysis", {})
        assert phone_analysis.get("recommended_mode") == "luxway_planning", phone_payload
        assert phone_analysis.get("requires_user_confirmation") is True, phone_payload
        assert phone_analysis.get("can_execute_now") is False, phone_payload

        visual_response = client.post(
            "/agent/analyze",
            json={"text": "bu g\u00f6rselde amber \u0131\u015f\u0131k ve Luxviai imzas\u0131n\u0131 seviyorum", "source_modality": "text"},
        )
        assert visual_response.status_code == 200, visual_response.text
        visual_payload = visual_response.json()
        visual_analysis = visual_payload.get("analysis", {})
        assert visual_analysis.get("recommended_mode") in {"visual_style_memory", "ambrosia"}, visual_payload
        memory_preview = visual_analysis.get("memory_preview", {})
        signal_types = {item.get("type") for item in memory_preview.get("candidate_signals", [])}
        assert {"visual_preference", "lux_visual_style", "lux_ambrosia_reference"} & signal_types, visual_payload

        dream_response = client.post(
            "/agent/analyze",
            json={"text": "r\u00fcyamda deniz kenar\u0131nda u\u00e7an insanlar vard\u0131", "source_modality": "text"},
        )
        assert dream_response.status_code == 200, dream_response.text
        dream_payload = dream_response.json()
        dream_analysis = dream_payload.get("analysis", {})
        assert dream_analysis.get("recommended_mode") == "dream_scene", dream_payload

        cv_response = client.post(
            "/agent/analyze",
            json={"text": "CV haz\u0131rla", "source_modality": "text"},
        )
        assert cv_response.status_code == 200, cv_response.text
        cv_payload = cv_response.json()
        cv_analysis = cv_payload.get("analysis", {})
        assert cv_analysis.get("recommended_mode") == "cv_builder", cv_payload
        assert cv_analysis.get("write_performed") is False, cv_payload
        assert cv_payload.get("write_performed") is False, cv_payload
        return "agent analysis hub read-only"

    def check_router_preview_read_only(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        def post_router(text: str) -> dict[str, Any]:
            response = client.post("/router/preview", json={"text": text, "source_modality": "text"})
            assert response.status_code == 200, response.text
            payload = response.json()
            preview = payload.get("router_preview", {})
            assert payload.get("read_only") is True, payload
            assert payload.get("raw_data_stored") is False, payload
            assert payload.get("write_performed") is False, payload
            assert preview.get("read_only") is True, payload
            assert preview.get("raw_data_stored") is False, payload
            assert preview.get("write_performed") is False, payload
            return payload

        email_payload = post_router("maillerimi \u00f6zetle")
        email_preview = email_payload.get("router_preview", {})
        assert email_preview.get("should_use_agent") is True, email_payload
        assert email_preview.get("output_type") in {"action_plan", "memory_preview"}, email_payload
        assert email_preview.get("can_execute_now") is False, email_payload

        phone_payload = post_router("telefonu tara kullan\u0131lmayan uygulamalar\u0131 bul")
        phone_preview = phone_payload.get("router_preview", {})
        assert phone_preview.get("should_use_luxway") is True, phone_payload
        assert phone_preview.get("should_require_confirmation") is True, phone_payload
        assert phone_preview.get("can_execute_now") is False, phone_payload

        cv_payload = post_router("CV haz\u0131rla")
        cv_preview = cv_payload.get("router_preview", {})
        assert cv_preview.get("output_type") == "cv_builder", cv_payload
        assert cv_preview.get("should_use_workspace") is True or cv_preview.get("recommended_mode") == "cv_builder", cv_payload

        ambrosia_payload = post_router("bu hissi Lux Ambrosia olarak g\u00f6rselle\u015ftir")
        ambrosia_preview = ambrosia_payload.get("router_preview", {})
        assert ambrosia_preview.get("should_use_visual_system") is True, ambrosia_payload
        assert ambrosia_preview.get("output_type") in {"ambrosia_state", "visual_prompt"}, ambrosia_payload

        dream_payload = post_router("r\u00fcyam\u0131 g\u00f6rselle\u015ftir")
        dream_preview = dream_payload.get("router_preview", {})
        assert dream_preview.get("output_type") == "dream_scene_state", dream_payload
        return "router preview read-only"

    def check_debug_sample_preview_endpoints(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        samples = [
            ("/debug/agent/sample-email", "agent_analysis"),
            ("/debug/agent/sample-luxway", "agent_analysis"),
            ("/debug/agent/sample-visual", "agent_analysis"),
            ("/debug/agent/sample-dream", "agent_analysis"),
            ("/debug/router/sample-cv", "router_preview"),
        ]

        for path, result_key in samples:
            response = client.get(path)
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("sample_text"), payload
            assert payload.get("read_only") is True, payload
            assert payload.get("raw_data_stored") is False, payload
            assert payload.get("write_performed") is False, payload
            result = payload.get(result_key, {})
            assert isinstance(result, dict) and result, payload
            if result_key == "agent_analysis":
                assert result.get("recommended_mode"), payload
                assert result.get("can_execute_now") is False, payload
            else:
                assert result.get("recommended_mode") or result.get("output_type"), payload
                assert result.get("can_execute_now") is False, payload

        return "debug sample previews"

    def check_debug_agent_panel(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/debug/agent-panel")
        assert response.status_code == 200, response.text
        html = response.text
        for endpoint in [
            "/debug/layer14-status",
            "/workspace/preview",
            "/debug/agent/sample-email",
            "/debug/agent/sample-luxway",
            "/debug/agent/sample-visual",
            "/debug/agent/sample-dream",
            "/debug/router/sample-cv",
            "/debug/mode-preview",
            "/debug/permission-preview",
            "/debug/agent-decision-trace",
            "/debug/fault-report-status",
            "/debug/fault-report-registry",
            "/debug/fault-report-intelligence-status",
            "/debug/fault-report-intelligence-registry",
            "/debug/fault-report-preview?focus=open",
        ]:
            assert endpoint in html, endpoint
        lowered = html.lower()
        assert "read-only" in lowered or "no real action" in lowered, html[:300]
        assert "no raw data is stored" in lowered, html[:300]
        assert "mode registry" in lowered, html[:300]
        assert "permission boundary" in lowered, html[:300]
        assert "agent decision trace" in lowered, html[:300]
        assert "layer 14 status" in lowered, html[:300]
        assert "workspace preview" in lowered, html[:300]
        assert "visual style preview" in lowered, html[:300]
        assert "/debug/visual-status" in html, html[:300]
        assert "/visual/style-preview" in html, html[:300]
        assert "/visual/ratio-preview" in html, html[:300]
        assert "/visual/ambrosia-preview" in html, html[:300]
        assert "/visual/dream-scene-preview" in html, html[:300]
        assert "/visual/scene-lock-preview" in html, html[:300]
        assert "/visual/prompt-preview" in html, html[:300]
        assert "/debug/voice-status" in html, html[:300]
        assert "/debug/voice-audio-status" in html, html[:300]
        assert "/voice/modes" in html, html[:300]
        assert "/voice/preview-mode" in html, html[:300]
        assert "/voice/night-radio-preview" in html, html[:300]
        assert "/audio/signal-schema" in html, html[:300]
        assert "/audio/preview-signal" in html, html[:300]
        assert "/audio/privacy-boundary-preview" in html, html[:300]
        assert "/debug/audio-status" in html, html[:300]
        assert "/router/model-config" in html, html[:300]
        assert "/router/model-preview" in html, html[:300]
        assert "/router/hint-preview" in html, html[:300]
        assert "/router/cost-privacy-policy" in html, html[:300]
        assert "/router/cost-preview" in html, html[:300]
        assert "/router/safe-memory-policy" in html, html[:300]
        assert "/router/memory-retrieval-preview" in html, html[:300]
        assert "/router/simulation-preview" in html, html[:300]
        assert "/debug/model-router-full-status" in html, html[:300]
        assert "/debug/model-router-status" in html, html[:300]
        assert "/debug/production-hardening-status" in html, html[:300]
        assert "/debug/backlog-registry" in html, html[:300]
        assert "/debug/system-control-audit" in html, html[:300]
        assert "/debug/endpoint-coverage" in html, html[:300]
        assert "/debug/live-readiness" in html, html[:300]
        assert "/debug/master-status" in html, html[:300]
        assert "/debug/lux-character-status" in html, html[:300]
        assert "/debug/layer21-status" in html, html[:300]
        assert "/future/candidates" in html, html[:300]
        assert "/future/preview" in html, html[:300]
        assert "/debug/layer22-status" in html, html[:300]
        assert "/debug/layer22-full-status" in html, html[:300]
        assert "/future/scoring-matrix" in html, html[:300]
        assert "/future/score-preview" in html, html[:300]
        assert "/debug/layer22-scoring-status" in html, html[:300]
        assert "/finality/schema" in html, html[:300]
        assert "/finality/preview" in html, html[:300]
        assert "/debug/finality-status" in html, html[:300]
        assert "/adaptive-interface/schema" in html, html[:300]
        assert "/adaptive-interface/preview" in html, html[:300]
        assert "/debug/adaptive-interface-status" in html, html[:300]
        assert "/ambient-workspace/schema" in html, html[:300]
        assert "/ambient-workspace/preview" in html, html[:300]
        assert "/debug/ambient-workspace-status" in html, html[:300]
        assert "/intention-timeline/schema" in html, html[:300]
        assert "/intention-timeline/preview" in html, html[:300]
        assert "/debug/intention-timeline-status" in html, html[:300]
        assert "/autonomy-dial/schema" in html, html[:300]
        assert "/autonomy-dial/preview" in html, html[:300]
        assert "/debug/autonomy-dial-status" in html, html[:300]
        assert "/ethical-boundary/schema" in html, html[:300]
        assert "/ethical-boundary/preview" in html, html[:300]
        assert "/debug/ethical-boundary-status" in html, html[:300]
        assert "/support/registry" in html, html[:300]
        assert "/support/preview" in html, html[:300]
        assert "/debug/support-status" in html, html[:300]
        assert "/meta/core-registry" in html, html[:300]
        assert "/meta/quality-preview" in html, html[:300]
        assert "/debug/meta-status" in html, html[:300]
        assert "/emotional/reflection-registry" in html, html[:300]
        assert "/emotional/reflection-preview" in html, html[:300]
        assert "/debug/emotional-status" in html, html[:300]
        assert "/context-bridge/schema" in html, html[:300]
        assert "/context-bridge/preview" in html, html[:300]
        assert "/debug/context-bridge-status" in html, html[:300]
        assert "/device-bridge/schema" in html, html[:300]
        assert "/device-bridge/preview" in html, html[:300]
        assert "/debug/device-bridge-status" in html, html[:300]
        assert "/pointer/schema" in html, html[:300]
        assert "/pointer/preview-action" in html, html[:300]
        assert "/debug/pointer-status" in html, html[:300]
        assert "/drive-mode/schema" in html, html[:300]
        assert "/drive-mode/preview" in html, html[:300]
        assert "/debug/drive-mode-status" in html, html[:300]
        assert "/wake-sonic/schema" in html, html[:300]
        assert "/wake-sonic/registry" in html, html[:300]
        assert "/wake-sonic/preview" in html, html[:300]
        assert "/debug/wake-sonic-status" in html, html[:300]
        assert "/luxway/capabilities" in html, html[:300]
        assert "/luxway/preview-command" in html, html[:300]
        assert "/luxway/permission-model" in html, html[:300]
        assert "/luxway/permission-preview" in html, html[:300]
        assert "/luxway/weekly-report-schema" in html, html[:300]
        assert "/luxway/weekly-report-preview" in html, html[:300]
        assert "/luxway/data-preview" in html, html[:300]
        assert "/luxway/device-safety-preview" in html, html[:300]
        assert "/debug/luxway-full-status" in html, html[:300]
        assert "/debug/luxway-status" in html, html[:300]
        return "debug agent panel"

    def check_mode_registry_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        registry_response = client.get("/debug/mode-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry_payload = registry_response.json()
        modes = registry_payload.get("modes", [])
        assert isinstance(modes, list) and len(modes) >= 10, registry_payload
        mode_ids = {mode.get("id") for mode in modes}
        for expected_id in {"luxeph", "cv_builder", "dream_scene", "night_radio", "one_step", "codex_mode"}:
            assert expected_id in mode_ids, registry_payload
        assert registry_payload.get("read_only") is True, registry_payload
        assert registry_payload.get("raw_data_stored") is False, registry_payload

        def assert_mode(command: str, expected_id: str) -> None:
            response = client.get("/debug/mode-preview", params={"q": command})
            assert response.status_code == 200, response.text
            payload = response.json()
            preview = payload.get("mode_preview", {})
            assert payload.get("read_only") is True, payload
            assert payload.get("raw_data_stored") is False, payload
            assert payload.get("write_performed") is False, payload
            matched_ids = {item.get("mode", {}).get("id") for item in preview.get("matched_modes", [])}
            assert expected_id in matched_ids, payload
            assert preview.get("can_execute_now") is False, payload

        assert_mode("Luxeph'e ge\u00e7", "luxeph")
        assert_mode("CV haz\u0131rla", "cv_builder")
        assert_mode("r\u00fcyam\u0131 g\u00f6rsele \u00e7evir", "dream_scene")
        assert_mode("gece radyosu modu", "night_radio")
        assert_mode("tek ad\u0131m s\u00f6yle", "one_step")
        assert_mode("Codex modu", "codex_mode")

        unknown_response = client.get("/debug/mode-preview", params={"q": "bunu anlamlandir ama moda gecme"})
        assert unknown_response.status_code == 200, unknown_response.text
        unknown_preview = unknown_response.json().get("mode_preview", {})
        assert unknown_preview.get("confidence") == "low", unknown_preview
        assert unknown_preview.get("matched_modes") == [], unknown_preview
        return "mode registry preview"

    def check_permission_boundary_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        def preview(command: str) -> dict[str, Any]:
            response = client.get("/debug/permission-preview", params={"q": command})
            assert response.status_code == 200, response.text
            payload = response.json()
            boundary = payload.get("permission_preview", {})
            assert payload.get("read_only") is True, payload
            assert payload.get("raw_data_stored") is False, payload
            assert payload.get("write_performed") is False, payload
            assert boundary.get("read_only") is True, payload
            assert boundary.get("raw_data_stored") is False, payload
            assert boundary.get("write_performed") is False, payload
            assert boundary.get("can_execute_now") is False, payload
            return boundary

        cv_boundary = preview("CV haz\u0131rla")
        assert cv_boundary.get("action_type") in {"draft_only", "mode_preview"}, cv_boundary

        read_mail = preview("mailimi oku")
        assert read_mail.get("action_type") == "read_private_data", read_mail
        assert read_mail.get("requires_permission") is True, read_mail
        assert read_mail.get("allowed_in_scaffold") is False, read_mail

        send_mail = preview("bu maili g\u00f6nder")
        assert send_mail.get("action_type") == "write_or_send_action", send_mail
        assert send_mail.get("requires_confirmation") is True, send_mail
        assert send_mail.get("allowed_in_scaffold") is False, send_mail

        luxeph = preview("Luxeph'e ge\u00e7")
        assert luxeph.get("action_type") == "sensitive_private_mode" or luxeph.get("data_sensitivity") == "private_sensitive", luxeph

        one_step = preview("tek ad\u0131m s\u00f6yle")
        assert one_step.get("allowed_in_scaffold") is True, one_step
        assert one_step.get("requires_permission") is False, one_step

        device = preview("telefonumdaki gereksiz uygulamalar\u0131 sil")
        assert device.get("action_type") == "device_or_phone_action", device
        assert device.get("requires_confirmation") is True, device
        assert device.get("allowed_in_scaffold") is False, device

        export = preview("raporu PDF olarak indir")
        assert export.get("action_type") == "export_or_file_action", export
        assert export.get("allowed_in_scaffold") is False, export

        return "permission boundary preview"

    def check_agent_decision_trace_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        def trace(command: str) -> dict[str, Any]:
            response = client.get("/debug/agent-decision-trace", params={"q": command})
            assert response.status_code == 200, response.text
            payload = response.json()
            item = payload.get("decision_trace", {})
            assert payload.get("read_only") is True, payload
            assert payload.get("raw_data_stored") is False, payload
            assert payload.get("write_performed") is False, payload
            assert item.get("read_only") is True, payload
            assert item.get("raw_data_stored") is False, payload
            assert item.get("write_performed") is False, payload
            assert item.get("can_execute_now") is False, payload
            assert item.get("user_facing_preview"), payload
            return item

        cv_trace = trace("CV haz\u0131rla")
        assert cv_trace.get("inferred_agent_domain") in {"cv", "workspace"}, cv_trace
        assert cv_trace.get("inferred_user_intent") in {"draft_document", "start_mode"}, cv_trace
        assert cv_trace.get("scaffold_decision") == "allowed_preview_only", cv_trace

        read_mail = trace("mailimi oku")
        assert read_mail.get("inferred_agent_domain") == "email", read_mail
        assert read_mail.get("inferred_user_intent") == "read_private_data", read_mail
        assert read_mail.get("scaffold_decision") in {"blocked_requires_permission", "blocked_real_action_not_implemented"}, read_mail

        send_mail = trace("bu maili g\u00f6nder")
        assert send_mail.get("inferred_user_intent") == "send_or_write", send_mail
        assert send_mail.get("scaffold_decision") in {"blocked_requires_confirmation", "blocked_real_action_not_implemented"}, send_mail

        luxeph = trace("Luxeph'e ge\u00e7")
        assert luxeph.get("inferred_agent_domain") == "luxeph", luxeph
        assert luxeph.get("scaffold_decision") in {"blocked_private_sensitive", "blocked_requires_confirmation"}, luxeph

        one_step = trace("tek ad\u0131m s\u00f6yle")
        assert one_step.get("scaffold_decision") == "allowed_preview_only", one_step

        unknown = trace("bunu belki sonra dusunelim")
        assert unknown.get("scaffold_decision") == "low_confidence_ask_clarify", unknown
        return "agent decision trace preview"

    def check_layer14_status_snapshot(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/debug/layer14-status")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload.get("layer") == "14", payload
        assert payload.get("status") == "scaffold_ready", payload
        assert payload.get("read_only") is True, payload
        assert payload.get("real_actions_enabled") is False, payload
        assert payload.get("memory_writes_enabled") is False, payload
        assert payload.get("chat_stream_touched") is False, payload
        completed = payload.get("completed_parts", [])
        assert isinstance(completed, list) and len(completed) >= 10, payload
        backlog = " ".join(str(item).lower() for item in payload.get("important_backlog", []))
        assert "stop" in backlog and "durdur" in backlog, payload
        return "layer 14 status"

    def check_workspace_schema_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        schema_response = client.get("/workspace/schema")
        assert schema_response.status_code == 200, schema_response.text
        schema = schema_response.json()
        assert "block_types" in schema and "command" in schema.get("block_types", []), schema
        assert "block_fields" in schema and "exportable" in schema.get("block_fields", []), schema
        assert schema.get("read_only") is True, schema

        status_response = client.get("/debug/workspace-status")
        assert status_response.status_code == 200, status_response.text
        status_payload = status_response.json()
        assert status_payload.get("layer") == "15", status_payload
        assert status_payload.get("status") == "scaffold_ready", status_payload
        assert status_payload.get("read_only") is True, status_payload
        assert status_payload.get("real_editor_enabled") is False, status_payload
        assert status_payload.get("real_export_enabled") is False, status_payload
        assert status_payload.get("file_write_enabled") is False, status_payload
        assert status_payload.get("memory_write_enabled") is False, status_payload
        assert status_payload.get("chat_stream_touched") is False, status_payload
        assert "/workspace/builder-preview" in status_payload.get("available_endpoints", []), status_payload

        sample_response = client.get("/debug/workspace/sample")
        assert sample_response.status_code == 200, sample_response.text
        sample = sample_response.json()
        assert sample.get("read_only") is True, sample
        assert sample.get("write_performed") is False, sample

        preview_response = client.post(
            "/workspace/preview",
            json={"command": "CV haz\u0131rla", "content": "Kisa profil ve deneyim bilgisi."},
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("read_only") is True, preview
        assert preview.get("write_performed") is False, preview
        assert preview.get("file_created") is False, preview
        blocks = preview.get("blocks", [])
        assert isinstance(blocks, list) and blocks, preview
        command_blocks = [block for block in blocks if block.get("type") == "command"]
        assert command_blocks and all(block.get("exportable") is False for block in command_blocks), blocks
        assert all(block.get("copyable") is False for block in command_blocks), blocks
        content_blocks = [block for block in blocks if block.get("type") in {"draft", "final", "paragraph", "heading"}]
        assert any(block.get("exportable") is True for block in content_blocks), blocks

        separation_command = "sesli komut: giri\u015f b\u00f6l\u00fcm\u00fcn\u00fc k\u0131salt"
        separation_response = client.post(
            "/workspace/separation-preview",
            json={
                "command": separation_command,
                "content": "Giris bolumu gereksiz tekrarlar iceriyor ve daha kisa olabilir.",
            },
        )
        assert separation_response.status_code == 200, separation_response.text
        separation = separation_response.json()
        assert separation.get("read_only") is True, separation
        assert separation.get("write_performed") is False, separation
        for key in [
            "original_blocks",
            "command_blocks",
            "content_blocks",
            "exportable_blocks",
            "non_exportable_blocks",
            "final_output_blocks",
        ]:
            assert isinstance(separation.get(key), list), separation
        separation_command_blocks = separation.get("command_blocks", [])
        assert any(
            block.get("type") == "command" and block.get("exportable") is False and block.get("copyable") is False
            for block in separation_command_blocks
        ), separation_command_blocks
        assert any(
            block.get("type") == "voice_command" and block.get("exportable") is False and block.get("copyable") is False
            for block in separation_command_blocks
        ), separation_command_blocks
        clean_export = separation.get("clean_export_preview", "")
        assert separation_command not in clean_export, separation
        assert "sesli komut" not in clean_export.lower(), separation
        assert any(block.get("exportable") is True for block in separation.get("content_blocks", [])), separation
        assert all(
            block.get("type") not in {"command", "voice_command", "ai_note"}
            for block in separation.get("final_output_blocks", [])
        ), separation

        def parse_workspace(command: str) -> dict:
            response = client.post("/workspace/parse-command", json={"command": command, "current_blocks": []})
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            assert payload.get("write_performed") is False, payload
            assert payload.get("block_update_performed") is False, payload
            return payload

        cv_parse = parse_workspace("CV haz\u0131rla")
        assert cv_parse.get("workspace_intent") == "create_cv", cv_parse
        assert cv_parse.get("operation") == "create", cv_parse

        paragraph_parse = parse_workspace("3. paragraf\u0131 akademikle\u015ftir")
        assert paragraph_parse.get("workspace_intent") == "academic_rewrite", paragraph_parse
        assert paragraph_parse.get("target_block_type") == "paragraph", paragraph_parse
        assert "3" in paragraph_parse.get("target_block_hint", ""), paragraph_parse

        shorten_parse = parse_workspace("k\u0131salt")
        assert shorten_parse.get("workspace_intent") == "shorten", shorten_parse
        assert shorten_parse.get("operation") == "shorten", shorten_parse
        assert shorten_parse.get("needs_clarification") is True, shorten_parse

        presentation_parse = parse_workspace("sunuma \u00e7evir")
        assert presentation_parse.get("workspace_intent") == "create_presentation", presentation_parse
        assert presentation_parse.get("operation") == "convert", presentation_parse

        export_response = client.post("/workspace/export-preview", json={"export_type": "pdf", "blocks": []})
        assert export_response.status_code == 200, export_response.text
        export_preview = export_response.json()
        assert export_preview.get("read_only") is True, export_preview
        assert export_preview.get("export_performed") is False, export_preview
        assert export_preview.get("file_written") is False, export_preview
        assert export_preview.get("send_performed") is False, export_preview
        included_blocks = export_preview.get("included_blocks", [])
        excluded_blocks = export_preview.get("excluded_blocks", [])
        assert isinstance(included_blocks, list) and included_blocks, export_preview
        assert isinstance(excluded_blocks, list) and excluded_blocks, export_preview
        assert any(block.get("type") in {"final", "paragraph"} for block in included_blocks), included_blocks
        assert any(block.get("type") == "command" for block in excluded_blocks), excluded_blocks
        assert any(block.get("type") == "voice_command" for block in excluded_blocks), excluded_blocks
        assert any(block.get("type") == "ai_note" for block in excluded_blocks), excluded_blocks
        clean_text = export_preview.get("clean_text_preview", "")
        assert "sesli komut" not in clean_text.lower(), export_preview
        assert "giris bolumunu kisalt" not in clean_text.lower(), export_preview
        assert export_preview.get("export_package_preview", {}).get("status") == "preview_only", export_preview

        def context_preview(context_note: str) -> dict:
            response = client.post(
                "/workspace/context-preview",
                json={"context_note": context_note, "project_type": "tez", "current_blocks": []},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            assert payload.get("memory_write_performed") is False, payload
            assert payload.get("write_performed") is False, payload
            return payload

        detail_context = context_preview("Bu hoca ayr\u0131nt\u0131l\u0131 cevap sever.")
        assert detail_context.get("detail_level") == "high", detail_context
        assert detail_context.get("recommended_workspace_behavior"), detail_context

        repetition_context = context_preview("Tekrar g\u00f6rmeyi sevmez.")
        assert repetition_context.get("repetition_policy") == "reduce_repetition", repetition_context

        source_context = context_preview("Kaynak eksikli\u011finden puan k\u0131r\u0131yor.")
        assert source_context.get("source_expectations"), source_context
        warnings = " ".join(source_context.get("warnings", [])).lower()
        assert "invent" in warnings or "uydur" in warnings, source_context

        def builder_preview(command: str) -> dict:
            response = client.post(
                "/workspace/builder-preview",
                json={"command": command, "content": "", "context_note": "", "project_type": "debug"},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            assert payload.get("export_ready") is False, payload
            assert payload.get("file_written") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            return payload

        cv_builder = builder_preview("CV haz\u0131rla")
        assert cv_builder.get("builder_type") == "cv", cv_builder
        assert cv_builder.get("suggested_structure"), cv_builder

        report_builder = builder_preview("rapor yaz")
        assert report_builder.get("builder_type") == "report", report_builder

        presentation_builder = builder_preview("sunuma \u00e7evir")
        assert presentation_builder.get("builder_type") == "presentation", presentation_builder

        homework_builder = builder_preview("\u00f6devim var")
        assert homework_builder.get("builder_type") in {"generic_document", "report"}, homework_builder
        assert homework_builder.get("missing_inputs") or homework_builder.get("clarification_question"), homework_builder

        return "workspace schema/preview/separation/parser/export/context/builder"

    def check_visual_style_registry_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        styles_response = client.get("/visual/styles")
        assert styles_response.status_code == 200, styles_response.text
        styles_payload = styles_response.json()
        assert styles_payload.get("read_only") is True, styles_payload
        assert styles_payload.get("image_generation_performed") is False, styles_payload
        styles = styles_payload.get("styles", [])
        assert isinstance(styles, list) and styles, styles_payload
        style_ids = {style.get("id") for style in styles}
        assert "lux_amber_accent" in style_ids, styles_payload
        groups = styles_payload.get("groups", {})
        assert "main_visual_modes" in groups, styles_payload
        assert "paint_surface_layers" in groups, styles_payload
        assert "light_layers" in groups, styles_payload
        assert "lux_special_visual_rules" in groups, styles_payload
        assert any(style.get("id") == "scene_lock" for style in groups.get("main_visual_modes", [])), styles_payload
        assert any(style.get("id") == "paper_texture" for style in groups.get("paint_surface_layers", [])), styles_payload
        metadata = styles_payload.get("metadata", {})
        assert metadata.get("lux_amber_accent_color") == "#ab6b0c", styles_payload
        assert metadata.get("default_line_density") == "low", styles_payload
        metadata_constraints = set(metadata.get("ambrosia_negative_constraints", []))
        assert {"no_city", "no_room", "no_letters"} <= metadata_constraints, styles_payload

        preview_response = client.post(
            "/visual/style-preview",
            json={"prompt": "%40 ya\u011fl\u0131 boya %20 pixel", "requested_styles": [], "mode": "smoke"},
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("read_only") is True, preview
        assert preview.get("image_generation_performed") is False, preview
        assert preview.get("signature_default") is True, preview
        mix = preview.get("style_mix_preview", [])
        assert isinstance(mix, list) and mix, preview
        mix_by_id = {item.get("style_id"): item for item in mix}
        assert mix_by_id.get("oil_paint", {}).get("ratio") == 0.4, preview
        assert mix_by_id.get("pixel", {}).get("ratio") == 0.2, preview

        alias_preview_response = client.post(
            "/visual/style-preview",
            json={"prompt": "Los Neon Vintage Afis Paper Texture Scene Lock", "requested_styles": [], "mode": "smoke"},
        )
        assert alias_preview_response.status_code == 200, alias_preview_response.text
        alias_preview = alias_preview_response.json()
        alias_style_ids = {style.get("id") for style in alias_preview.get("suggested_styles", [])}
        assert {"dim_neon", "vintage_poster", "paper_texture", "scene_lock"} <= alias_style_ids, alias_preview

        ratio_response = client.post(
            "/visual/ratio-preview",
            json={"prompt": "%40 ya\u011fl\u0131 boya %20 pixel", "ratio_text": "", "requested_styles": [], "mode": "smoke"},
        )
        assert ratio_response.status_code == 200, ratio_response.text
        ratio_payload = ratio_response.json()
        assert ratio_payload.get("read_only") is True, ratio_payload
        assert ratio_payload.get("image_generation_performed") is False, ratio_payload
        assert ratio_payload.get("lux_amber_accent") == "#ab6b0c", ratio_payload
        assert ratio_payload.get("line_density_default") == "low", ratio_payload
        assert ratio_payload.get("signature_default") is True, ratio_payload
        requested_ratios = ratio_payload.get("requested_ratios", {})
        assert requested_ratios.get("oil_paint") == 0.4, ratio_payload
        assert requested_ratios.get("pixel") == 0.2, ratio_payload
        normalized_ratios = ratio_payload.get("normalized_ratios", {})
        assert "oil_paint" in normalized_ratios and "pixel" in normalized_ratios, ratio_payload
        final_mix = ratio_payload.get("final_style_mix_preview", [])
        assert isinstance(final_mix, list) and final_mix, ratio_payload

        ambrosia_response = client.post(
            "/visual/ambrosia-preview",
            json={"feeling_text": "i\u00e7imde sessiz ama a\u011f\u0131r bir yorgunluk var", "intensity": 0.6, "style_ratio": {}},
        )
        assert ambrosia_response.status_code == 200, ambrosia_response.text
        ambrosia = ambrosia_response.json()
        assert ambrosia.get("read_only") is True, ambrosia
        assert ambrosia.get("image_generation_performed") is False, ambrosia
        assert ambrosia.get("background", {}).get("color") == "#0A0A0A", ambrosia
        assert ambrosia.get("light", {}).get("color") == "#AB6B0C", ambrosia
        assert ambrosia.get("glyph_layer", {}).get("color") == "#C0C0C0", ambrosia
        constraints = set(ambrosia.get("negative_constraints", []))
        assert {"no_city", "no_room", "no_letters"} <= constraints, ambrosia
        assert ambrosia.get("ambrosia_state", {}).get("state_type") == "inner_state_not_place", ambrosia

        dream_response = client.post(
            "/visual/dream-scene-preview",
            json={
                "scene_text": "Karanl\u0131k bir denizde k\u00fc\u00e7\u00fck bir sandal var, uzakta amber bir \u0131\u015f\u0131k g\u00f6r\u00fcn\u00fcyor.",
                "style_hint": "dream scene",
                "locked_elements": ["boat", "amber_light"],
            },
        )
        assert dream_response.status_code == 200, dream_response.text
        dream = dream_response.json()
        assert dream.get("read_only") is True, dream
        assert dream.get("image_generation_performed") is False, dream
        assert isinstance(dream.get("camera"), dict), dream
        assert isinstance(dream.get("subjects"), list), dream
        assert isinstance(dream.get("objects"), list), dream
        assert isinstance(dream.get("spatial_relations"), list), dream
        assert "locked_elements" in dream, dream
        object_ids = {item.get("id") for item in dream.get("objects", [])}
        assert {"boat", "amber_light"} <= object_ids, dream
        assert dream.get("locked_elements") == ["boat", "amber_light"], dream

        scene_lock_response = client.post(
            "/visual/scene-lock-preview",
            json={
                "current_scene_state": {
                    "locked_elements": ["dream_self", "bowl"],
                    "subjects": [{"id": "dream_self", "type": "self_presence", "locked_candidate": True}],
                    "objects": [{"id": "bowl", "type": "object_or_environment", "locked_candidate": True}],
                },
                "new_detail": "ba\u015f\u0131n\u0131 biraz sola \u00e7evir",
                "lock_strength": 1.0,
            },
        )
        assert scene_lock_response.status_code == 200, scene_lock_response.text
        scene_lock = scene_lock_response.json()
        assert scene_lock.get("read_only") is True, scene_lock
        assert scene_lock.get("image_generation_performed") is False, scene_lock
        assert scene_lock.get("scene_rebuild_required") is False, scene_lock
        assert scene_lock.get("locked_elements") == ["dream_self", "bowl"], scene_lock
        assert scene_lock.get("preserved_elements"), scene_lock
        proposed_updates = scene_lock.get("proposed_updates", [])
        assert isinstance(proposed_updates, list) and proposed_updates, scene_lock
        assert any(item.get("operation") == "adjust_pose" for item in proposed_updates), scene_lock
        assert scene_lock.get("updated_scene_preview", {}).get("scene_rebuild_required") is False, scene_lock

        prompt_response = client.post(
            "/visual/prompt-preview",
            json={
                "prompt": "R\u00fcya: karanl\u0131k denizde k\u00fc\u00e7\u00fck sandal",
                "mode": "",
                "style_ratios": {"ratio_text": "%40 ya\u011fl\u0131 boya %20 pixel"},
                "scene_state": dream,
                "ambrosia_state": {},
                "locked_elements": ["boat", "amber_light"],
            },
        )
        assert prompt_response.status_code == 200, prompt_response.text
        prompt_preview = prompt_response.json()
        assert prompt_preview.get("read_only") is True, prompt_preview
        assert prompt_preview.get("image_generation_performed") is False, prompt_preview
        assert prompt_preview.get("final_prompt_preview"), prompt_preview
        assert prompt_preview.get("negative_prompt"), prompt_preview
        assert prompt_preview.get("lux_signature_note"), prompt_preview
        assert "prompt_sections" in prompt_preview, prompt_preview
        assert "boat" in prompt_preview.get("final_prompt_preview", ""), prompt_preview

        prompt_examples = [
            (
                "Dreamcore Surrealism soft neon amber",
                {"dreamcore_surrealism", "soft_neon", "lux_amber_accent"},
                None,
            ),
            (
                "Ambrosia i\u00e7imde k\u0131r\u0131lgan umut",
                {"lux_ambrosia"},
                "ambrosia",
            ),
            (
                "sahneyi koru sa\u011f tarafa k\u00fc\u00e7\u00fck kap\u0131 ekle",
                {"scene_lock"},
                "scene_lock",
            ),
            (
                "%40 ya\u011fl\u0131 boya %20 pixel amber \u0131\u015f\u0131k",
                {"oil_paint", "pixel", "lux_amber_accent"},
                None,
            ),
            (
                "Siyah kadife, platin glyph, d\u00fc\u015f\u00fck \u00e7izgi",
                {"black_velvet", "silent_glyph", "low_line_density"},
                None,
            ),
        ]
        for prompt_text, expected_styles, expected_mode in prompt_examples:
            response = client.post(
                "/visual/prompt-preview",
                json={
                    "prompt": prompt_text,
                    "mode": "",
                    "style_ratios": {"ratio_text": prompt_text},
                    "scene_state": {"locked_elements": ["door_anchor"]} if "sahneyi koru" in prompt_text else {},
                    "ambrosia_state": {},
                    "locked_elements": ["door_anchor"] if "sahneyi koru" in prompt_text else [],
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            assert payload.get("image_generation_performed") is False, payload
            assert payload.get("detected_registry_groups"), payload
            assert payload.get("used_style_aliases"), payload
            applied_rules = " ".join(payload.get("lux_rules_applied", []))
            assert "line density" in applied_rules and "signature" in applied_rules, payload
            style_ids = {item.get("style_id") for item in payload.get("style_mix", [])}
            assert expected_styles <= style_ids, payload
            if expected_mode:
                assert payload.get("detected_mode") == expected_mode, payload
            final_prompt = payload.get("final_prompt_preview", "")
            assert "#ab6b0c" in final_prompt, payload
            assert "visual spirit/state language" in final_prompt, payload

        ambrosia_prompt = client.post(
            "/visual/prompt-preview",
            json={"prompt": "Ambrosia i\u00e7imde k\u0131r\u0131lgan umut", "style_ratios": {}, "scene_state": {}, "ambrosia_state": {}, "locked_elements": []},
        ).json()
        assert ambrosia_prompt.get("detected_mode") == "ambrosia", ambrosia_prompt
        assert {"no_city", "no_room", "no_letters", "no_sign"} <= set(ambrosia_prompt.get("negative_prompt", "").split(", ")), ambrosia_prompt

        scene_lock_prompt = client.post(
            "/visual/prompt-preview",
            json={
                "prompt": "sahneyi koru sa\u011f tarafa k\u00fc\u00e7\u00fck kap\u0131 ekle",
                "style_ratios": {},
                "scene_state": {"locked_elements": ["door_anchor"]},
                "ambrosia_state": {},
                "locked_elements": ["door_anchor"],
            },
        ).json()
        assert scene_lock_prompt.get("detected_mode") == "scene_lock", scene_lock_prompt
        assert scene_lock_prompt.get("prompt_sections", {}).get("scene_lock", {}).get("scene_rebuild_required") is False, scene_lock_prompt
        assert "door_anchor" in scene_lock_prompt.get("final_prompt_preview", ""), scene_lock_prompt

        palette_prompt = client.post(
            "/visual/prompt-preview",
            json={"prompt": "Siyah kadife, platin glyph, d\u00fc\u015f\u00fck \u00e7izgi", "style_ratios": {}, "scene_state": {}, "ambrosia_state": {}, "locked_elements": []},
        ).json()
        assert "#0A0A0A" in palette_prompt.get("final_prompt_preview", ""), palette_prompt
        assert "#C0C0C0" in palette_prompt.get("final_prompt_preview", ""), palette_prompt
        return "visual style registry/ratio/ambrosia/dream/scene-lock/prompt preview"

    def check_visual_status_snapshot(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/debug/visual-status")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload.get("layer") == "16", payload
        assert payload.get("status") == "scaffold_ready", payload
        assert payload.get("read_only") is True, payload
        assert payload.get("image_generation_enabled") is False, payload
        assert payload.get("image_api_enabled") is False, payload
        assert payload.get("file_write_enabled") is False, payload
        assert payload.get("memory_write_enabled") is False, payload
        completed = " ".join(payload.get("completed_parts", []))
        assert "16.6B" in completed, payload
        rules = " ".join(payload.get("core_visual_rules", []))
        assert "#ab6b0c" in rules, payload
        assert "default low line density" in rules, payload
        return "visual status"

    def check_voice_speed_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        modes_response = client.get("/voice/modes")
        assert modes_response.status_code == 200, modes_response.text
        modes_payload = modes_response.json()
        assert modes_payload.get("read_only") is True, modes_payload
        assert modes_payload.get("real_audio_enabled") is False, modes_payload
        mode_ids = {mode.get("id") for mode in modes_payload.get("voice_modes", [])}
        assert {"normal_voice", "night_radio_voice", "silent_text_only", "fast_brief_voice"} <= mode_ids, modes_payload

        status_response = client.get("/debug/voice-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("voice_registry_ready") is True, status
        assert status.get("read_only") is True, status
        assert status.get("real_audio_enabled") is False, status
        assert status.get("microphone_used") is False, status
        assert status.get("recording_performed") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("user_facing_output_file_created") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        def preview(command: str, response_size: str = "medium", input_modality: str = "text") -> dict:
            response = client.post(
                "/voice/preview-mode",
                json={
                    "command": command,
                    "context": "smoke test read-only context",
                    "response_size": response_size,
                    "input_modality": input_modality,
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("block_dump_prevention") is True, payload
            behavior = payload.get("stream_behavior", {})
            assert behavior.get("block_dump_allowed") is False, payload
            assert behavior.get("final_bulk_injection_allowed") is False, payload
            assert behavior.get("smooth_typewriter") is True, payload
            assert payload.get("real_audio_enabled") is False, payload
            assert payload.get("microphone_used") is False, payload
            assert payload.get("recording_performed") is False, payload
            assert payload.get("read_only") is True, payload
            return payload

        slow = preview("daha yavas yaz")
        assert slow.get("writing_speed_preview") == 0.8, slow
        very_slow = preview("cok yavas anlat")
        assert very_slow.get("writing_speed_preview") in {0.7, 0.8}, very_slow
        quick = preview("hizli ozetle", "short")
        assert quick.get("writing_speed_preview") == 1.3, quick
        very_quick = preview("cok hizli ozet", "short")
        assert very_quick.get("writing_speed_preview") == 1.5, very_quick
        long_answer = preview("hizli uret ama uzun detayli cevap", "long")
        assert 0.8 <= float(long_answer.get("writing_speed_preview")) <= 1.1, long_answer
        workspace_large = preview("workspace uzun cevap", "workspace_large")
        assert workspace_large.get("writing_speed_preview") in {0.9, 1.0}, workspace_large
        night = preview("gece radyosu gibi konus")
        assert night.get("detected_voice_mode") == "night_radio_voice", night
        assert 0.7 <= float(night.get("writing_speed_preview")) <= 0.85, night
        silent = preview("sadece yazi, ses yok")
        assert silent.get("detected_voice_mode") == "silent_text_only", silent
        assert silent.get("voice_speed_preview") == 0.0, silent
        voice_meta = preview("net konus", "medium", "voice")
        assert voice_meta.get("input_modality") == "voice", voice_meta
        assert voice_meta.get("microphone_used") is False, voice_meta
        return "voice speed preview"

    def check_night_radio_voice_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        response = client.post(
            "/voice/night-radio-preview",
            json={"text": "gece radyosu gibi anlat", "mood": "", "response_size": "medium", "mode": ""},
        )
        assert response.status_code == 200, response.text
        night = response.json()
        assert night.get("detected_mode") == "night_radio", night
        assert 0.7 <= float(night.get("writing_speed_preview")) <= 0.85, night
        assert night.get("real_audio_enabled") is False, night
        assert night.get("tts_performed") is False, night
        assert night.get("microphone_used") is False, night
        assert night.get("recording_performed") is False, night
        assert night.get("read_only") is True, night
        stream = night.get("stream_behavior", {})
        assert stream.get("block_dump_allowed") is False, night
        assert stream.get("final_bulk_injection_allowed") is False, night
        assert stream.get("smooth_typewriter") is True, night

        samples = [
            ("bu metni sakin podcast tonu yap", "podcast", 0.9, 0.95),
            ("uyumadan once yavas anlat", "night_radio", 0.7, 0.85),
            ("daha yumusak ve dusuk ton", "calm", 0.7, 0.85),
            ("sadece yazi ama gece radyosu hissi", "text_only_night", 0.7, 0.85),
            ("hizli ozet gece radyosu gibi", "night_radio", 0.9, 1.0),
        ]
        for text, expected_mode, min_speed, max_speed in samples:
            sample_response = client.post(
                "/voice/night-radio-preview",
                json={"text": text, "mood": "", "response_size": "medium", "mode": ""},
            )
            assert sample_response.status_code == 200, sample_response.text
            payload = sample_response.json()
            assert payload.get("detected_mode") == expected_mode, payload
            assert min_speed <= float(payload.get("writing_speed_preview")) <= max_speed, payload
            assert payload.get("real_audio_enabled") is False, payload
            assert payload.get("tts_performed") is False, payload
            assert payload.get("read_only") is True, payload
            assert payload.get("stream_behavior", {}).get("block_dump_allowed") is False, payload
        return "night radio voice preview"

    def check_voice_audio_status_snapshot(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/debug/voice-audio-status")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload.get("layer") == "17", payload
        assert payload.get("status") == "scaffold_ready", payload
        assert payload.get("read_only") is True, payload
        assert payload.get("real_tts_enabled") is False, payload
        assert payload.get("real_stt_enabled") is False, payload
        assert payload.get("real_audio_enabled") is False, payload
        assert payload.get("microphone_enabled") is False, payload
        assert payload.get("recording_enabled") is False, payload
        assert payload.get("memory_write_enabled") is False, payload
        assert payload.get("typewriter_runtime_touched") is False, payload
        completed = " ".join(payload.get("completed_parts", []))
        assert "17.4" in completed, payload
        rules = " ".join(payload.get("core_voice_rules", []))
        assert "block_dump_allowed false" in rules, payload
        return "voice audio status"

    def check_audio_signal_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        schema_response = client.get("/audio/signal-schema")
        assert schema_response.status_code == 200, schema_response.text
        schema = schema_response.json()
        assert schema.get("source_modality") == "simulated_audio", schema
        assert schema.get("raw_audio_stored") is False, schema
        assert schema.get("recording_performed") is False, schema
        assert schema.get("microphone_used") is False, schema
        assert schema.get("clinical_diagnosis_performed") is False, schema
        assert schema.get("read_only") is True, schema

        status_response = client.get("/debug/audio-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("audio_signal_schema_ready") is True, status
        assert status.get("read_only") is True, status
        assert status.get("raw_audio_stored") is False, status
        assert status.get("recording_performed") is False, status
        assert status.get("microphone_used") is False, status
        assert status.get("clinical_diagnosis_performed") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        samples = [
            "sesim yorgun gibi",
            "hizli ve panik konusuyorum",
            "daha sakin bir tona gec",
            "gece radyosu gibi yavaslat",
            "enerjim dusuk ama net anlat",
        ]
        for sample in samples:
            response = client.post(
                "/audio/preview-signal",
                json={
                    "description": sample,
                    "simulated_voice_note": "smoke simulated metadata only",
                    "context": "read-only audio signal schema preview",
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("source_modality") == "simulated_audio", payload
            assert payload.get("raw_audio_stored") is False, payload
            assert payload.get("recording_performed") is False, payload
            assert payload.get("microphone_used") is False, payload
            assert payload.get("clinical_diagnosis_performed") is False, payload
            assert payload.get("read_only") is True, payload
            assert payload.get("derived_signals"), payload
            assert isinstance(payload.get("rhythm_preview"), dict), payload
            assert isinstance(payload.get("energy_preview"), dict), payload
            assert isinstance(payload.get("pause_pattern_preview"), dict), payload
            assert isinstance(payload.get("tone_shift_preview"), dict), payload
            assert isinstance(payload.get("emotional_atmosphere_preview"), dict), payload
        return "audio signal preview"

    def check_audio_privacy_boundary_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        analyze_response = client.post(
            "/audio/privacy-boundary-preview",
            json={"command": "sesimi analiz et", "audio_context": "", "consent_state": "not_granted"},
        )
        assert analyze_response.status_code == 200, analyze_response.text
        analyze = analyze_response.json()
        assert analyze.get("consent_required") is True, analyze
        assert analyze.get("raw_audio_stored") is False, analyze
        assert analyze.get("recording_performed") is False, analyze
        assert analyze.get("microphone_used") is False, analyze
        assert analyze.get("clinical_diagnosis_allowed") is False, analyze
        assert analyze.get("memory_write_allowed") is False, analyze
        assert analyze.get("read_only") is True, analyze

        mic_response = client.post(
            "/audio/privacy-boundary-preview",
            json={"command": "mikrofonu ac", "audio_context": "", "consent_state": "not_granted"},
        )
        assert mic_response.status_code == 200, mic_response.text
        mic = mic_response.json()
        blocked_without_consent = set(mic.get("blocked_without_consent", []))
        assert "microphone_access" in blocked_without_consent, mic
        assert "real_audio_processing_without_explicit_consent" in blocked_without_consent, mic

        for command in ["panik konusuyorum", "sesimi kaydet", "sadece tonumu sakinlestir"]:
            response = client.post(
                "/audio/privacy-boundary-preview",
                json={"command": command, "audio_context": "smoke boundary", "consent_state": "not_granted"},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("raw_audio_allowed") is False, payload
            assert payload.get("raw_audio_stored") is False, payload
            assert payload.get("derived_signal_only") is True, payload
            assert payload.get("recording_performed") is False, payload
            assert payload.get("microphone_used") is False, payload
            assert payload.get("clinical_diagnosis_allowed") is False, payload
            assert payload.get("clinical_diagnosis_performed") is False, payload
            assert payload.get("memory_write_allowed") is False, payload
            assert payload.get("read_only") is True, payload
            assert payload.get("safe_audio_use"), payload
            assert payload.get("blocked_actions"), payload
        return "audio privacy boundary preview"

    def check_luxway_capability_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        capabilities_response = client.get("/luxway/capabilities")
        assert capabilities_response.status_code == 200, capabilities_response.text
        capabilities_payload = capabilities_response.json()
        assert capabilities_payload.get("read_only") is True, capabilities_payload
        assert capabilities_payload.get("real_access_enabled") is False, capabilities_payload
        capability_ids = {item.get("id") for item in capabilities_payload.get("capabilities", [])}
        assert {"phone_overview", "app_usage_preview", "storage_preview", "call_or_message_draft_preview"} <= capability_ids, capabilities_payload

        status_response = client.get("/debug/luxway-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "scaffold_ready", status
        assert status.get("read_only") is True, status
        assert status.get("real_phone_access_enabled") is False, status
        assert status.get("real_app_access_enabled") is False, status
        assert status.get("real_mail_access_enabled") is False, status
        assert status.get("real_calendar_access_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        def preview(command: str, platform: str = "android") -> dict:
            response = client.post(
                "/luxway/preview-command",
                json={"command": command, "platform": platform, "context": "smoke Luxway read-only context"},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("real_access_enabled") is False, payload
            assert payload.get("action_performed") is False, payload
            assert payload.get("data_read") is False, payload
            assert payload.get("data_written") is False, payload
            assert payload.get("read_only") is True, payload
            return payload

        phone = preview("telefonumu tara")
        assert phone.get("requires_permission") is True, phone
        assert phone.get("detected_capability") == "phone_overview", phone

        cleanup = preview("gereksiz uygulamalari bul")
        cleanup_ids = {item.get("id") for item in cleanup.get("capability_candidates", [])}
        assert {"cleanup_suggestions_preview", "app_usage_preview"} & cleanup_ids, cleanup

        draft = preview("Ali'ye mesaj taslagi yaz")
        assert draft.get("detected_capability") == "call_or_message_draft_preview", draft
        assert draft.get("requires_confirmation") is True, draft
        assert draft.get("action_performed") is False, draft

        mail = preview("mail ozetimi goster")
        assert mail.get("detected_capability") == "mail_summary_preview", mail
        assert mail.get("requires_permission") is True, mail
        assert mail.get("data_read") is False, mail

        calendar = preview("takvimimi ozetle", "ios")
        assert calendar.get("detected_capability") == "calendar_summary_preview", calendar
        assert calendar.get("platform") == "ios", calendar
        return "luxway capability preview"

    def check_luxway_permission_model_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        model_response = client.get("/luxway/permission-model")
        assert model_response.status_code == 200, model_response.text
        model = model_response.json()
        assert model.get("read_only") is True, model
        assert model.get("real_permission_requested") is False, model
        assert model.get("real_access_enabled") is False, model
        permission_ids = {item.get("id") for item in model.get("permission_groups", [])}
        assert {"notifications", "calendar", "storage", "app_usage", "device_settings"} <= permission_ids, model

        def preview(command: str, platform: str = "unknown") -> dict:
            response = client.post("/luxway/permission-preview", json={"command": command, "platform": platform})
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("real_permission_requested") is False, payload
            assert payload.get("real_access_enabled") is False, payload
            assert payload.get("action_performed") is False, payload
            assert payload.get("data_read") is False, payload
            assert payload.get("data_written") is False, payload
            assert payload.get("read_only") is True, payload
            return payload

        notifications = preview("Android bildirimlerimi onceliklendir", "android")
        assert "notifications" in notifications.get("detected_permission_groups", []), notifications
        assert notifications.get("platform") == "android", notifications

        calendar = preview("iOS takvimimi ozetle", "ios")
        assert "calendar" in calendar.get("detected_permission_groups", []), calendar
        assert calendar.get("platform") == "ios", calendar

        storage = preview("depolamayi temizle", "android")
        assert {"storage", "files"} & set(storage.get("detected_permission_groups", [])), storage
        assert storage.get("requires_confirmation") is True, storage

        contacts = preview("kisilerime mesaj yaz", "android")
        groups = set(contacts.get("detected_permission_groups", []))
        assert {"contacts", "messages"} <= groups, contacts
        assert contacts.get("requires_confirmation") is True, contacts

        settings = preview("ayarlari degistir", "android")
        assert "device_settings" in settings.get("detected_permission_groups", []), settings
        assert settings.get("requires_confirmation") is True, settings
        return "luxway permission model preview"

    def check_luxway_weekly_report_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        schema_response = client.get("/luxway/weekly-report-schema")
        assert schema_response.status_code == 200, schema_response.text
        schema = schema_response.json()
        assert schema.get("read_only") is True, schema
        assert schema.get("requires_permission") is True, schema
        assert schema.get("real_access_enabled") is False, schema
        assert schema.get("data_read") is False, schema
        assert schema.get("data_written") is False, schema
        section_ids = {item.get("id") for item in schema.get("report_sections", [])}
        assert {"week_summary", "app_usage_preview", "storage_pressure_preview", "safety_boundaries"} <= section_ids, schema

        def preview(report_focus: str, platform: str = "android") -> dict:
            response = client.post(
                "/luxway/weekly-report-preview",
                json={"platform": platform, "report_focus": report_focus, "context": "smoke read-only weekly report"},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("requires_permission") is True, payload
            assert payload.get("real_access_enabled") is False, payload
            assert payload.get("data_read") is False, payload
            assert payload.get("data_written") is False, payload
            assert payload.get("action_performed") is False, payload
            assert payload.get("read_only") is True, payload
            report_text = json.dumps(payload.get("safe_preview_report", {}), ensure_ascii=False).lower()
            assert "no real metrics" in report_text, payload
            assert "explicit platform permissions" in report_text, payload
            for forbidden in ["instagram", "whatsapp:", "gmail:", "42", "120", "gb", "saat"]:
                assert forbidden not in report_text, payload
            return payload

        weekly = preview("haftalik telefon raporu cikar")
        assert {"app_usage", "notifications", "calendar"} & set(weekly.get("required_permissions", [])), weekly

        notifications = preview("bildirim yukumu goster")
        notification_sections = {item.get("id") for item in notifications.get("report_sections", [])}
        assert "notification_noise_preview" in notification_sections, notifications

        unused = preview("kullanmadigim uygulamalari oner")
        unused_sections = {item.get("id") for item in unused.get("report_sections", [])}
        assert "unused_apps_preview" in unused_sections, unused

        storage = preview("depolama baskisini goster")
        assert "storage" in storage.get("required_permissions", []), storage

        focus = preview("odak onerileri ver", "ios")
        assert focus.get("platform") == "ios", focus
        assert "focus_recommendations_preview" in {item.get("id") for item in focus.get("report_sections", [])}, focus
        return "luxway weekly report preview"

    def check_luxway_data_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        def preview(command: str, domain: str = "", platform: str = "android") -> dict:
            response = client.post("/luxway/data-preview", json={"command": command, "domain": domain, "platform": platform})
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("requires_permission") is True, payload
            assert payload.get("real_access_enabled") is False, payload
            assert payload.get("data_read") is False, payload
            assert payload.get("data_written") is False, payload
            assert payload.get("action_performed") is False, payload
            assert payload.get("read_only") is True, payload
            preview_text = json.dumps(payload.get("preview_sections", []), ensure_ascii=False).lower()
            preview_text += json.dumps(payload.get("safe_preview_message", ""), ensure_ascii=False).lower()
            assert "schema preview only" in preview_text, payload
            assert "no real or invented" in preview_text, payload
            for forbidden in ["instagram", "whatsapp:", "gmail:", "ali:", "yarin 10", "42", "120", "gb"]:
                assert forbidden not in preview_text, payload
            return payload

        mail = preview("mailimi ozetle")
        assert mail.get("detected_domain") == "mail", mail
        assert "mail" in mail.get("required_permissions", []), mail

        messages = preview("mesajlarimi ozetle")
        assert messages.get("detected_domain") == "messages", messages
        assert "messages" in messages.get("required_permissions", []), messages

        calendar = preview("takvimimi ozetle", platform="ios")
        assert calendar.get("detected_domain") == "calendar", calendar
        assert calendar.get("platform") == "ios", calendar

        storage = preview("depolamayi temizle")
        assert storage.get("detected_domain") == "storage", storage
        assert storage.get("requires_confirmation") is True, storage

        apps = preview("gereksiz uygulamalari bul")
        assert apps.get("detected_domain") == "app_usage", apps

        notifications = preview("bildirimlerimi onceliklendir")
        assert notifications.get("detected_domain") == "notifications", notifications
        return "luxway data preview"

    def check_luxway_device_safety_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        def preview(command: str, platform: str = "android") -> dict:
            response = client.post("/luxway/device-safety-preview", json={"command": command, "platform": platform})
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("requires_permission") is True, payload
            assert payload.get("requires_confirmation") is True, payload
            assert payload.get("blocked_by_default") is True, payload
            assert payload.get("real_access_enabled") is False, payload
            assert payload.get("action_performed") is False, payload
            assert payload.get("data_read") is False, payload
            assert payload.get("data_written") is False, payload
            assert payload.get("read_only") is True, payload
            assert payload.get("safe_alternative"), payload
            assert payload.get("confirmation_phrase_required"), payload
            return payload

        app_delete = preview("gereksiz uygulamalari sil")
        assert app_delete.get("detected_risk_category") in {"delete_app", "cleanup_storage"}, app_delete

        file_delete = preview("bu dosyayi sil")
        assert file_delete.get("detected_risk_category") == "delete_file", file_delete

        message = preview("Ali'ye mesaj gonder")
        assert message.get("detected_risk_category") == "send_message", message

        mail = preview("bu maili gonder")
        assert mail.get("detected_risk_category") == "send_mail", mail

        call = preview("annemi ara")
        assert call.get("detected_risk_category") == "make_call", call

        settings = preview("ayarlari degistir")
        assert settings.get("detected_risk_category") == "change_device_setting", settings

        storage = preview("depolamayi temizle")
        assert storage.get("detected_risk_category") == "cleanup_storage", storage
        return "luxway device safety preview"

    def check_luxway_full_status_snapshot(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/debug/luxway-full-status")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data.get("layer") == "18", data
        assert data.get("status") == "scaffold_ready", data
        assert data.get("read_only") is True, data
        assert data.get("real_phone_access_enabled") is False, data
        assert data.get("real_platform_api_enabled") is False, data
        assert data.get("real_app_access_enabled") is False, data
        assert data.get("real_mail_access_enabled") is False, data
        assert data.get("real_calendar_access_enabled") is False, data
        assert data.get("real_call_enabled") is False, data
        assert data.get("real_send_enabled") is False, data
        assert data.get("real_delete_enabled") is False, data
        assert data.get("memory_write_enabled") is False, data
        assert data.get("typewriter_runtime_touched") is False, data
        completed = " ".join(str(item) for item in data.get("completed_parts", []))
        assert "18.5" in completed, data
        rules = " ".join(str(item).lower() for item in data.get("core_luxway_rules", []))
        assert "requires_confirmation" in rules, data
        assert "risky actions blocked by default" in rules, data
        endpoints = set(data.get("available_endpoints", []))
        assert "/luxway/device-safety-preview" in endpoints, data
        return "luxway full status"

    def check_model_router_config_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        config_response = client.get("/router/model-config")
        assert config_response.status_code == 200, config_response.text
        config = config_response.json()
        assert config.get("read_only") is True, config
        assert config.get("deepseek_target_share") == 0.96, config
        assert config.get("mini_5_4_target_share") == 0.03, config
        assert config.get("gpt_5_5_target_share") == 0.01, config
        role_ids = {item.get("id") for item in config.get("model_roles", [])}
        assert {"deepseek_primary", "mini_5_4_support", "gpt_5_5_premium_fallback", "image_api_future"} <= role_ids, config
        policy = config.get("privacy_policy", {})
        assert policy.get("raw_user_text_logged") is False, config
        assert policy.get("real_billing_write") is False, config

        status_response = client.get("/debug/model-router-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("model_router_ready") is True, status
        assert status.get("read_only") is True, status
        assert status.get("routing_changed") is False, status
        assert status.get("real_model_switch_performed") is False, status
        assert status.get("real_api_call_performed") is False, status
        assert status.get("billing_write_performed") is False, status
        assert status.get("memory_write_performed") is False, status
        assert status.get("db_write_performed") is False, status
        assert status.get("file_write_performed") is False, status
        assert status.get("raw_user_text_logged") is False, status
        assert status.get("deepseek_target_share") == 0.96, status
        assert status.get("mini_5_4_target_share") == 0.03, status
        assert status.get("gpt_5_5_target_share") == 0.01, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        def preview(command: str, task_type: str = "", sensitivity: str = "normal", response_size: str = "medium") -> dict:
            response = client.post(
                "/router/model-preview",
                json={
                    "command": command,
                    "task_type": task_type,
                    "sensitivity": sensitivity,
                    "response_size": response_size,
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("raw_user_text_logged") is False, payload
            assert payload.get("safe_derived_signals_only") is True, payload
            assert payload.get("routing_changed") is False, payload
            assert payload.get("real_model_switch_performed") is False, payload
            assert payload.get("real_api_call_performed") is False, payload
            assert payload.get("billing_write_performed") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            assert payload.get("db_write_performed") is False, payload
            assert payload.get("file_write_performed") is False, payload
            assert payload.get("read_only") is True, payload
            return payload

        normal = preview("normal sohbet")
        assert normal.get("recommended_provider") == "deepseek_primary", normal
        assert normal.get("target_distribution", {}).get("deepseek") == 0.96, normal

        report = preview("uzun rapor yaz", response_size="long")
        assert report.get("detected_task_type") in {"workspace", "report_writer"}, report
        assert report.get("recommended_provider") == "deepseek_primary", report

        dream = preview("ruya sahnesi promptla")
        assert dream.get("recommended_provider") == "deepseek_primary", dream
        assert dream.get("recommended_model_role") in {"visual_prompt_planner", "primary_reasoning"}, dream
        assert dream.get("real_api_call_performed") is False, dream

        image = preview("gorsel uret")
        assert image.get("recommended_provider") == "image_api_future" or image.get("recommended_model_role") == "image_generation_future", image
        assert image.get("image_generation_performed") is False, image
        assert image.get("real_api_call_performed") is False, image

        sketch = preview("cizimi oku")
        assert sketch.get("recommended_provider") == "mini_5_4_support", sketch
        assert sketch.get("recommended_model_role") in {"multimodal_reader_future", "sketch_interpreter_future"}, sketch

        critical = preview("kritik kod debug", sensitivity="high")
        assert critical.get("recommended_provider") == "gpt_5_5_premium_fallback" or critical.get("fallback_model_role") == "fallback_high_quality", critical
        assert critical.get("real_model_switch_performed") is False, critical

        luxway = preview("Luxway telefon raporu")
        assert luxway.get("recommended_provider") == "deepseek_primary", luxway
        assert luxway.get("real_phone_access_enabled") is False, luxway
        return "model router config preview"

    def check_model_router_hint_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        def hint(command: str, source_area: str = "general", task_type: str = "", sensitivity: str = "normal", response_size: str = "medium") -> dict:
            response = client.post(
                "/router/hint-preview",
                json={
                    "command": command,
                    "source_area": source_area,
                    "task_type": task_type,
                    "sensitivity": sensitivity,
                    "response_size": response_size,
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("raw_user_text_logged") is False, payload
            assert payload.get("routing_changed") is False, payload
            assert payload.get("real_model_switch_performed") is False, payload
            assert payload.get("real_api_call_performed") is False, payload
            assert payload.get("billing_write_performed") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            assert payload.get("db_write_performed") is False, payload
            assert payload.get("read_only") is True, payload
            assert payload.get("model_hint"), payload
            return payload

        report = hint("uzun rapor yaz", "workspace", "report_writer", response_size="long")
        assert report.get("recommended_provider") == "deepseek_primary", report

        image = hint("gorsel uret", "visual", "image_generation_request")
        assert image.get("recommended_provider") == "image_api_future", image
        assert image.get("real_api_call_performed") is False, image
        assert image.get("image_generation_performed") is False, image

        sketch = hint("cizimi oku", "visual", "sketch_understanding_request")
        assert sketch.get("recommended_provider") == "mini_5_4_support", sketch

        critical = hint("kritik kod debug", "codex", "critical_debug", sensitivity="high")
        assert critical.get("recommended_provider") == "gpt_5_5_premium_fallback", critical

        luxway = hint("Luxway telefon raporu", "luxway", "luxway")
        assert luxway.get("recommended_provider") == "deepseek_primary", luxway
        assert "permission" in str(luxway.get("hint_reason", "")).lower(), luxway
        return "model router hint preview"

    def check_cost_privacy_policy_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        policy_response = client.get("/router/cost-privacy-policy")
        assert policy_response.status_code == 200, policy_response.text
        policy = policy_response.json()
        assert policy.get("raw_user_text_logged") is False, policy
        assert policy.get("raw_audio_logged") is False, policy
        assert policy.get("raw_file_content_logged") is False, policy
        assert policy.get("safe_derived_metadata_only") is True, policy
        assert policy.get("billing_write_performed") is False, policy
        assert policy.get("db_write_performed") is False, policy
        assert policy.get("memory_write_performed") is False, policy
        blocked = set(policy.get("blocked_metadata", []))
        assert {"raw_user_message", "raw_audio"} <= blocked, policy

        def preview(command: str, task_type: str = "", sensitivity: str = "normal") -> dict:
            response = client.post(
                "/router/cost-preview",
                json={
                    "command": command,
                    "task_type": task_type,
                    "sensitivity": sensitivity,
                    "estimated_tokens_bucket": "medium",
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("raw_user_text_logged") is False, payload
            assert payload.get("raw_private_message_logged") is False, payload
            assert payload.get("raw_audio_logged") is False, payload
            assert payload.get("raw_file_content_logged") is False, payload
            assert payload.get("raw_sensitive_content_logged") is False, payload
            assert payload.get("safe_derived_metadata_only") is True, payload
            assert payload.get("billing_write_performed") is False, payload
            assert payload.get("db_write_performed") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            assert payload.get("file_write_performed") is False, payload
            assert payload.get("read_only") is True, payload
            assert "raw_user_message" in payload.get("blocked_metadata", []), payload
            assert "raw_audio" in payload.get("blocked_metadata", []), payload
            return payload

        normal = preview("normal sohbet maliyet preview", "normal_chat")
        assert normal.get("privacy_risk") in {"low", "medium", "high"}, normal

        private_message = preview("ozel mesajimi ozetle", "permission_boundary", "privacy")
        assert private_message.get("privacy_risk") == "high", private_message

        audio = preview("ses kaydimi analiz et", "audio_voice", "privacy")
        assert audio.get("privacy_risk") == "high", audio

        file_preview = preview("dosyami oku", "workspace", "privacy")
        assert file_preview.get("privacy_risk") == "high", file_preview

        safety = preview("hassas guvenlik sorusu", "safety_sensitive", "safety")
        assert safety.get("privacy_risk") == "high", safety
        return "cost privacy policy preview"

    def check_safe_memory_retrieval_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        policy_response = client.get("/router/safe-memory-policy")
        assert policy_response.status_code == 200, policy_response.text
        policy = policy_response.json()
        assert policy.get("read_only") is True, policy
        assert policy.get("luxeph_no_memory_rule") is True, policy
        assert policy.get("raw_memory_returned") is False, policy
        assert policy.get("raw_sensitive_memory_returned") is False, policy
        assert policy.get("memory_read_performed") is False, policy
        assert policy.get("memory_write_performed") is False, policy
        assert "raw_audio" in policy.get("blocked_memory_types", []), policy

        def preview(command: str, task_type: str = "", sensitivity: str = "normal", memory_type: str = "") -> dict:
            response = client.post(
                "/router/memory-retrieval-preview",
                json={
                    "command": command,
                    "task_type": task_type,
                    "sensitivity": sensitivity,
                    "requested_memory_type": memory_type,
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("raw_memory_returned") is False, payload
            assert payload.get("raw_sensitive_memory_returned") is False, payload
            assert payload.get("memory_read_performed") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            assert payload.get("db_write_performed") is False, payload
            assert payload.get("file_write_performed") is False, payload
            assert payload.get("read_only") is True, payload
            return payload

        visual = preview("gorsel tarzimi hatirla", "visual_prompt", memory_type="lux_visual_style")
        assert visual.get("retrieval_allowed") is True, visual
        assert visual.get("safe_context_preview", {}).get("summary_only") is True, visual

        workspace = preview("workspace proje notlarimi kullan", "workspace", memory_type="workspace_context")
        assert workspace.get("retrieval_allowed") is True, workspace
        assert "workspace_context" in workspace.get("allowed_memory_types", []), workspace

        luxeph = preview("Luxeph gecmisini getir", "privacy_sensitive", "privacy", "emotional_context")
        assert luxeph.get("retrieval_allowed") is False, luxeph
        assert "luxeph" in str(luxeph.get("retrieval_reason", "")).lower(), luxeph

        private_message = preview("ozel mesaj gecmisimi getir", "permission_boundary", "privacy", "safety_boundary")
        assert private_message.get("raw_sensitive_memory_returned") is False, private_message
        assert private_message.get("retrieval_allowed") is False, private_message

        ambrosia = preview("Ambrosia tarzimi kullan", "ambrosia_prompt", memory_type="lux_ambrosia_reference")
        assert ambrosia.get("retrieval_allowed") is True, ambrosia
        return "safe memory retrieval preview"

    def check_routing_simulation_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        def simulate(command: str, task_type: str = "", sensitivity: str = "normal", response_size: str = "medium") -> dict:
            response = client.post(
                "/router/simulation-preview",
                json={
                    "command": command,
                    "scenario": "smoke simulation",
                    "task_type": task_type,
                    "sensitivity": sensitivity,
                    "response_size": response_size,
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("user_visible_model_choice") is False, payload
            assert payload.get("routing_invisible_to_user") is True, payload
            assert payload.get("raw_user_text_logged") is False, payload
            assert payload.get("real_model_switch_performed") is False, payload
            assert payload.get("real_api_call_performed") is False, payload
            assert payload.get("billing_write_performed") is False, payload
            assert payload.get("memory_read_performed") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            assert payload.get("db_write_performed") is False, payload
            assert payload.get("file_write_performed") is False, payload
            assert payload.get("read_only") is True, payload
            return payload

        normal = simulate("normal sohbet")
        assert normal.get("recommended_route", {}).get("provider") == "deepseek_primary", normal

        sketch = simulate("cizimi oku", "sketch_understanding_request")
        assert sketch.get("recommended_route", {}).get("provider") == "mini_5_4_support", sketch

        critical = simulate("kritik kod debug", "critical_debug", "high")
        assert critical.get("recommended_route", {}).get("provider") == "gpt_5_5_premium_fallback", critical

        image = simulate("gorsel uret", "image_generation_request")
        assert image.get("recommended_route", {}).get("provider") == "image_api_future", image
        assert image.get("real_api_call_performed") is False, image
        assert image.get("image_generation_performed") is False, image

        luxeph = simulate("Luxeph gecmisini getir", "privacy_sensitive", "privacy")
        memory = luxeph.get("memory_policy_preview", {})
        assert memory.get("retrieval_allowed") is False, luxeph

        luxway = simulate("Luxway telefon raporu", "luxway")
        assert luxway.get("recommended_route", {}).get("provider") == "deepseek_primary", luxway
        return "routing simulation preview"

    def check_model_router_full_status_snapshot(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/debug/model-router-full-status")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload.get("layer") == "19", payload
        assert payload.get("status") == "scaffold_ready", payload
        assert payload.get("read_only") is True, payload
        assert payload.get("routing_changed") is False, payload
        assert payload.get("real_model_switch_performed") is False, payload
        assert payload.get("real_api_call_performed") is False, payload
        assert payload.get("raw_user_text_logged") is False, payload
        assert payload.get("billing_write_performed") is False, payload
        assert payload.get("memory_read_performed") is False, payload
        assert payload.get("memory_write_performed") is False, payload
        assert payload.get("db_write_performed") is False, payload
        assert payload.get("file_write_performed") is False, payload
        assert payload.get("chat_stream_touched") is False, payload
        assert payload.get("typewriter_runtime_touched") is False, payload
        distribution = payload.get("target_distribution", {})
        assert distribution.get("deepseek_target_share") == 0.96, payload
        assert distribution.get("mini_5_4_target_share") == 0.03, payload
        assert distribution.get("gpt_5_5_target_share") == 0.01, payload
        completed = " ".join(str(item) for item in payload.get("completed_parts", []))
        assert "19.5" in completed, payload
        rules = " ".join(str(item).lower() for item in payload.get("core_router_rules", []))
        assert "raw user text is never logged" in rules, payload
        assert "no billing write" in rules, payload
        assert "luxeph no-memory rule" in rules, payload
        endpoints = set(payload.get("available_endpoints", []))
        assert "/router/simulation-preview" in endpoints, payload
        return "model router full status"

    def check_production_hardening_backlog_registry(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        for endpoint in ["/debug/production-hardening-status", "/debug/backlog-registry"]:
            response = client.get(endpoint)
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("layer") == "20", payload
            assert payload.get("status") == "planning_scaffold", payload
            assert payload.get("read_only") is True, payload
            assert payload.get("real_fix_performed") is False, payload
            assert payload.get("chat_stream_touched") is False, payload
            assert payload.get("typewriter_runtime_touched") is False, payload
            assert payload.get("db_write_performed") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            assert payload.get("file_write_performed") is False, payload
            backlog_text = " ".join(str(item).lower() for item in payload.get("backlog_items", []))
            assert "stop/durdur final block leak" in backlog_text, payload
            assert "real model routing later" in backlog_text, payload
            risk_groups = {item.get("id") for item in payload.get("risk_groups", [])}
            assert "stream_and_stop_backlog" in risk_groups, payload
            assert "privacy_security_audit" in risk_groups, payload
            assert payload.get("recommended_next_checks"), payload
            assert payload.get("safe_next_step"), payload

        return "production hardening backlog registry"

    def check_root_flow_auditor_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        status_response = client.get("/debug/root-flow-auditor-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "23.1", status
        assert status.get("status") == "scaffold_ready", status
        assert status.get("read_only") is True, status
        assert status.get("file_write_performed") is False, status
        assert status.get("memory_write_performed") is False, status
        assert status.get("db_write_performed") is False, status
        assert status.get("git_performed") is False, status
        assert status.get("commit_performed") is False, status
        assert status.get("push_performed") is False, status
        assert status.get("deploy_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status
        owners = status.get("behavior_owners", {})
        assert owners.get("stop_continue", {}).get("owner") == "Lux ARM", owners
        assert owners.get("workspace_export", {}).get("owner") == "Export Core", owners
        assert owners.get("visual_scene", {}).get("owner") == "Scene Lock", owners
        assert owners.get("luxway_action", {}).get("owner") == "Permission Boundary", owners
        assert owners.get("model_routing", {}).get("owner") == "Router Core", owners
        categories = set(status.get("root_cause_categories", []))
        assert {"duplicate_branch", "stale_fallback", "state_source_conflict", "event_leak", "incomplete_test_coverage"} <= categories, status

        audit_response = client.post(
            "/debug/root-flow-audit",
            json={
                "command": "stop continue ARM list repeats after item 3",
                "behavior": "stop_continue",
                "observed_behavior": "late final block appears and resume restarts",
                "expected_behavior": "continue item 3 then write items 4-10",
                "smoke_tests": [],
            },
        )
        assert audit_response.status_code == 200, audit_response.text
        audit = audit_response.json()
        assert audit.get("detected_behavior") == "stop_continue", audit
        assert audit.get("behavior_owner", {}).get("owner") == "Lux ARM", audit
        root_causes = {item.get("id") for item in audit.get("possible_root_causes", [])}
        assert "state_source_conflict" in root_causes, audit
        assert "event_leak" in root_causes, audit
        assert "incomplete_test_coverage" in root_causes, audit
        assert "app.py" in audit.get("recommended_files", []), audit
        assert "static/index.html" in audit.get("recommended_files", []), audit
        assert audit.get("manual_tests"), audit
        smoke = audit.get("smoke_gap_detector", {})
        assert "Bu davranışı doğrulayan smoke testi var mı?" in smoke.get("question", ""), smoke
        assert smoke.get("missing_smoke_coverage"), smoke
        assert audit.get("risk_level") == "high", audit
        assert audit.get("confidence_score", 0) > 0, audit
        assert audit.get("read_only") is True, audit
        assert audit.get("file_write_performed") is False, audit
        assert audit.get("git_performed") is False, audit
        assert audit.get("deploy_performed") is False, audit

        plan_response = client.post(
            "/debug/codex-fix-plan",
            json={
                "command": "stop continue ARM list repeats after item 3",
                "behavior": "stop_continue",
                "observed_behavior": "resume restarts or only completes one word",
                "expected_behavior": "complete item 3 and continue numbered items",
            },
        )
        assert plan_response.status_code == 200, plan_response.text
        plan = plan_response.json()
        assert plan.get("plan_id") == "codex_fix_plan_stop_continue", plan
        plan_text = " ".join(str(item).lower() for item in plan.get("technical_plan", []))
        assert "lux arm" in plan_text, plan
        assert "late stream" in plan_text or "websocket" in plan_text or "event guards" in plan_text, plan
        assert "10 item list" in plan_text, plan
        assert plan.get("read_only") is True, plan
        assert plan.get("file_write_performed") is False, plan
        assert plan.get("memory_write_performed") is False, plan
        assert plan.get("db_write_performed") is False, plan
        assert plan.get("git_performed") is False, plan
        assert plan.get("commit_performed") is False, plan
        assert plan.get("push_performed") is False, plan
        assert plan.get("deploy_performed") is False, plan

        return "root flow auditor preview"

    def check_safe_self_check_runner_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        status_response = client.get("/debug/self-check-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "23.2", status
        assert status.get("status") == "scaffold_ready", status
        assert status.get("read_only") is True, status
        assert status.get("real_check_executed") is False, status
        assert status.get("file_write_performed") is False, status
        assert status.get("memory_write_performed") is False, status
        assert status.get("db_write_performed") is False, status
        assert status.get("git_write_performed") is False, status
        assert status.get("commit_performed") is False, status
        assert status.get("push_performed") is False, status
        assert status.get("deploy_performed") is False, status
        assert status.get("real_fix_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status
        assert status.get("root_flow_auditor_connected") is True, status

        registry_response = client.get("/debug/self-check-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        check_ids = {item.get("id") for item in registry.get("checks", [])}
        expected = {
            "py_compile_check",
            "smoke_check",
            "endpoint_health_check",
            "route_existence_check",
            "behavior_owner_check",
            "missing_helper_check",
            "undefined_variable_check",
            "duplicate_branch_check",
            "stale_fallback_check",
            "manual_scenario_check",
        }
        assert expected <= check_ids, registry
        assert registry.get("read_only") is True, registry
        assert registry.get("git_write_performed") is False, registry

        preview_response = client.post(
            "/debug/self-check-preview",
            json={
                "command": "stop continue ARM only completes item 5",
                "behavior": "stop_continue",
                "observed_behavior": "resume only completes one item and stops",
                "expected_behavior": "continue through remaining list items",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("preview_id") == "self_check_stop_continue", preview
        checks_run = {item.get("id") for item in preview.get("checks_run", [])}
        assert "behavior_owner_check" in checks_run, preview
        assert "manual_scenario_check" in checks_run, preview
        assert "smoke_check" in checks_run, preview
        assert preview.get("possible_findings"), preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert preview.get("codex_required") is True, preview
        assert preview.get("lux_can_handle"), preview
        assert preview.get("codex_recommended_for"), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("real_check_executed") is False, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("real_fix_performed") is False, preview

        return "safe self-check runner preview"

    def check_codex_handoff_builder_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        status_response = client.get("/debug/codex-handoff-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "23.3", status
        assert status.get("status") == "scaffold_ready", status
        assert status.get("read_only") is True, status
        assert status.get("root_flow_auditor_connected") is True, status
        assert status.get("safe_self_check_connected") is True, status
        assert status.get("file_write") is False, status
        assert status.get("memory_write") is False, status
        assert status.get("db_write") is False, status
        assert status.get("git_write") is False, status
        assert status.get("commit") is False, status
        assert status.get("push") is False, status
        assert status.get("deploy") is False, status
        assert status.get("auto_fix") is False, status
        assert status.get("file_write_performed") is False, status
        assert status.get("git_write_performed") is False, status
        assert status.get("real_fix_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/codex-handoff-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("status") == "registry_ready", registry
        assert registry.get("read_only") is True, registry
        intake_fields = set(registry.get("bug_intake_fields", []))
        assert {"behavior", "symptom", "expected_result", "actual_result"} <= intake_fields, registry
        handoff_fields = set(registry.get("handoff_fields", []))
        expected_handoff_fields = {
            "behavior",
            "symptom",
            "possible_root_causes",
            "recommended_files",
            "recommended_checks",
            "manual_scenarios",
            "codex_task_summary",
            "confidence_score",
            "risk_level",
        }
        assert expected_handoff_fields <= handoff_fields, registry
        assert "stop_continue" in set(registry.get("supported_behaviors", [])), registry
        assert "manual_scenario_check" in set(registry.get("supported_self_checks", [])), registry
        assert registry.get("auto_fix") is False, registry
        assert registry.get("patch_applied") is False, registry

        preview_response = client.post(
            "/debug/codex-handoff-preview",
            json={
                "behavior": "stop_continue",
                "symptom": "continue only works once",
                "actual_result": "second stop does not show the continue button",
                "expected_result": "multiple stop/continue cycles work until the answer completes",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("handoff_id") == "codex_handoff_stop_continue", preview
        assert preview.get("behavior") == "stop_continue", preview
        assert "continue" in str(preview.get("symptom", "")).lower(), preview
        root_causes = set(preview.get("possible_root_causes", []))
        assert {"state_source_conflict", "event_leak"} & root_causes, preview
        assert "app.py" in set(preview.get("recommended_files", [])), preview
        checks = set(preview.get("recommended_checks", []))
        assert "behavior_owner_check" in checks, preview
        assert "manual_scenario_check" in checks, preview
        assert preview.get("manual_scenarios"), preview
        task_summary = str(preview.get("codex_task_summary", "")).lower()
        assert "arm" in task_summary or "resume" in task_summary, preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert preview.get("risk_level") == "high", preview
        assert preview.get("lux_can_handle"), preview
        assert preview.get("codex_needed_for"), preview
        assert preview.get("root_flow_audit", {}).get("read_only") is True, preview
        assert preview.get("safe_self_check", {}).get("read_only") is True, preview
        assert preview.get("read_only") is True, preview
        assert preview.get("file_write") is False, preview
        assert preview.get("memory_write") is False, preview
        assert preview.get("db_write") is False, preview
        assert preview.get("git_write") is False, preview
        assert preview.get("commit") is False, preview
        assert preview.get("push") is False, preview
        assert preview.get("deploy") is False, preview
        assert preview.get("auto_fix") is False, preview
        assert preview.get("patch_applied") is False, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("real_fix_performed") is False, preview

        return "codex handoff builder preview"

    def check_bug_intake_investigation_planner_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        status_response = client.get("/debug/bug-intake-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "23.4", status
        assert status.get("status") == "scaffold_ready", status
        assert status.get("read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("file_write_performed") is False, status
        assert status.get("memory_write_performed") is False, status
        assert status.get("db_write_performed") is False, status
        assert status.get("git_write_performed") is False, status
        assert status.get("commit_performed") is False, status
        assert status.get("push_performed") is False, status
        assert status.get("deploy_performed") is False, status
        assert status.get("auto_fix_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status
        assert status.get("root_flow_auditor_connected") is True, status
        assert status.get("self_check_connected") is True, status
        assert status.get("handoff_connected") is True, status
        endpoints = set(status.get("available_endpoints", []))
        assert "/debug/bug-intake-status" in endpoints, status
        assert "/debug/bug-intake-registry" in endpoints, status
        assert "/debug/bug-intake-preview" in endpoints, status

        registry_response = client.get("/debug/bug-intake-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "23.4", registry
        assert registry.get("status") == "registry_ready", registry
        categories = {item.get("id") for item in registry.get("categories", [])}
        expected_categories = {
            "stop_continue",
            "stream",
            "websocket",
            "workspace",
            "visual",
            "luxway",
            "model_router",
            "memory",
            "endpoint",
            "ui",
            "permission_flow",
            "future_dev_agent",
        }
        assert expected_categories <= categories, registry
        assert registry.get("read_only") is True, registry
        safety_flags = registry.get("safety_flags", {})
        assert safety_flags.get("file_write") is False, safety_flags
        assert safety_flags.get("memory_write") is False, safety_flags
        assert safety_flags.get("db_write") is False, safety_flags
        assert safety_flags.get("git_write") is False, safety_flags
        assert safety_flags.get("commit") is False, safety_flags
        assert safety_flags.get("push") is False, safety_flags
        assert safety_flags.get("deploy") is False, safety_flags
        assert safety_flags.get("auto_fix") is False, safety_flags

        preview_response = client.post(
            "/debug/bug-intake-preview",
            json={
                "behavior": "stop_continue",
                "symptom": "devam et tuşu ikinci kez görünmüyor",
                "expected_result": "çoklu stop/continue döngüsü çalışmalı",
                "actual_result": "ikinci devam et isteğinde düğme geri gelmiyor",
                "command": "liste 10 madde üret; dur ve devam et",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("behavior") == "stop_continue", preview
        assert preview.get("symptom"), preview
        assert preview.get("expected_result"), preview
        assert preview.get("actual_result"), preview
        assert preview.get("severity") in {"low", "medium", "high"}, preview
        assert preview.get("investigation_priority") in {"p1", "p2", "p3"}, preview
        assert "root_flow_audit" in preview.get("recommended_audit", []), preview
        assert preview.get("recommended_self_checks"), preview
        assert preview.get("recommended_files"), preview
        assert "app.py" in set(preview.get("recommended_files", [])), preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert preview.get("root_flow_audit", {}).get("read_only") is True, preview
        assert preview.get("safe_self_check", {}).get("read_only") is True, preview
        assert preview.get("read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview

        return "bug intake investigation planner preview"

    def check_credit_saver_engine_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        status_response = client.get("/debug/credit-saver-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "23.5", status
        assert status.get("status") == "scaffold_ready", status
        assert status.get("name") == "Credit Saver Engine Preview", status
        assert status.get("read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("root_flow_auditor_connected") is True, status
        assert status.get("self_check_connected") is True, status
        assert status.get("handoff_connected") is True, status
        assert status.get("bug_intake_connected") is True, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status
        assert status.get("real_fix_performed") is False, status
        assert status.get("file_write_performed") is False, status
        assert status.get("memory_write_performed") is False, status
        assert status.get("db_write_performed") is False, status
        assert status.get("git_write_performed") is False, status
        assert status.get("commit_performed") is False, status
        assert status.get("push_performed") is False, status
        assert status.get("deploy_performed") is False, status

        registry_response = client.get("/debug/credit-saver-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "23.5", registry
        assert registry.get("status") == "registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert {"typo", "missing_helper", "duplicate_branch", "stream_refactor", "architecture_redesign"} <= set(
            registry.get("supported_bug_categories", [])
        ), registry
        paths = {item.get("id") for item in registry.get("supported_paths", [])}
        assert {"lux_only", "lux_first_then_codex", "codex_direct", "manual_investigation_first"} <= paths, registry
        safety = registry.get("safety_flags", {})
        assert safety.get("file_write") is False, safety
        assert safety.get("memory_write") is False, safety
        assert safety.get("db_write") is False, safety
        assert safety.get("git_write") is False, safety
        assert safety.get("auto_fix") is False, safety

        preview_response = client.post(
            "/debug/credit-saver-preview",
            json={
                "behavior": "stop_continue",
                "symptom": "devam et sadece bir kere çalışıyor",
                "expected_result": "birden fazla stop/continue döngüsü listeyi bitirmeli",
                "actual_result": "ikinci devam et isteğinde buton geri gelmiyor",
                "command": "10 maddelik liste yaz, dur, devam et",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("bug_category") in {"stop_continue", "stream_refactor", "websocket"}, preview
        assert preview.get("recommended_path") in {"lux_first_then_codex", "codex_direct", "manual_investigation_first"}, preview
        assert preview.get("estimated_complexity") in {"low", "medium", "high", "critical"}, preview
        assert preview.get("risk_level") in {"low", "medium", "high", "critical"}, preview
        assert isinstance(preview.get("confidence_score", 0), (int, float)), preview
        assert preview.get("estimated_credit_saving", 0) >= 0, preview
        assert preview.get("lux_can_handle"), preview
        assert preview.get("codex_needed_for") is not None, preview
        assert preview.get("recommended_self_checks"), preview
        assert preview.get("root_flow_audit"), preview
        assert preview.get("self_check_preview"), preview
        assert preview.get("codex_handoff_preview"), preview
        assert preview.get("bug_intake_preview"), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("real_fix_performed") is False, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        return "credit saver engine preview"

    def check_debug_intelligence_core_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        status_response = client.get("/debug/intelligence-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "23.6", status
        assert status.get("status") == "scaffold_ready", status
        assert status.get("name") == "Debug Intelligence Core Preview", status
        assert status.get("read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("file_write_performed") is False, status
        assert status.get("memory_write_performed") is False, status
        assert status.get("db_write_performed") is False, status
        assert status.get("git_write_performed") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("real_fix_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status
        completed_parts = set(status.get("completed_parts", []))
        assert {"root_flow_auditor", "safe_self_check_runner", "codex_handoff_builder", "bug_intake_investigation_planner", "credit_saver_engine", "debug_intelligence_core"} <= completed_parts, status

        registry_response = client.get("/debug/intelligence-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "23.6", registry
        assert registry.get("status") == "registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        behavior_categories = set(registry.get("behavior_categories", []))
        assert {"stop_continue", "stream", "websocket", "workspace", "visual", "ui"} <= behavior_categories, registry
        assert registry.get("connected_components"), registry

        preview_response = client.post(
            "/debug/intelligence-preview",
            json={
                "behavior": "stop_continue",
                "symptom": "devam et sadece bir kere çalışıyor",
                "expected_result": "birden fazla dur/devam döngüsü çalışmalı ve listedeki sonraki maddeler tamamlanmalı",
                "actual_result": "ikinci devam et isteğinde düğme görünmüyor",
                "command": "Bana 10 maddelik liste yaz, dur deyince devam et",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("behavior") == "stop_continue", preview
        assert preview.get("anomaly_detected") is True, preview
        assert preview.get("investigation_recommended") is True, preview
        assert preview.get("repeated_failure_detected") is True, preview
        assert preview.get("risk_level") in {"low", "medium", "high", "critical"}, preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("recommended_checks", []), list), preview
        assert preview.get("recommended_next_step"), preview
        assert preview.get("recommended_layer"), preview
        assert preview.get("root_flow_audit"), preview
        assert preview.get("self_check_preview"), preview
        assert preview.get("bug_intake_preview"), preview
        assert preview.get("codex_handoff_preview"), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("real_fix_performed") is False, preview

        return "debug intelligence core preview"

    def check_layer23_status_snapshot(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/debug/layer23-status")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload.get("layer") == "23", payload
        assert payload.get("layer23_status") == "active", payload
        assert payload.get("status") == "debug_intelligence_ready", payload
        assert payload.get("debug_intelligence_enabled") is True, payload
        completed = set(payload.get("completed_parts", []))
        assert {
            "root_flow_auditor",
            "safe_self_check_runner",
            "codex_handoff_builder",
            "bug_intake_investigation_planner",
            "credit_saver_engine",
            "debug_intelligence_core",
        } <= completed, payload
        endpoints = set(payload.get("available_endpoints", []))
        assert "/debug/root-flow-auditor-status" in endpoints, payload
        assert "/debug/self-check-status" in endpoints, payload
        assert "/debug/codex-handoff-status" in endpoints, payload
        assert "/debug/bug-intake-status" in endpoints, payload
        assert "/debug/credit-saver-status" in endpoints, payload
        assert "/debug/credit-saver-registry" in endpoints, payload
        assert "/debug/credit-saver-preview" in endpoints, payload
        assert "/debug/intelligence-status" in endpoints, payload
        assert "/debug/intelligence-registry" in endpoints, payload
        assert "/debug/intelligence-preview" in endpoints, payload
        assert "/debug/layer23-status" in endpoints, payload
        assert payload.get("read_only") is True, payload
        assert payload.get("analysis_only") is True, payload
        assert payload.get("can_modify_code") is False, payload
        assert payload.get("can_commit") is False, payload
        assert payload.get("can_push") is False, payload
        assert payload.get("can_deploy") is False, payload
        assert payload.get("can_auto_fix") is False, payload
        assert payload.get("file_write_enabled") is False, payload
        assert payload.get("memory_write_enabled") is False, payload
        assert payload.get("db_write_enabled") is False, payload
        assert payload.get("git_write_enabled") is False, payload
        assert payload.get("auto_fix_enabled") is False, payload
        assert payload.get("file_write_performed") is False, payload
        assert payload.get("memory_write_performed") is False, payload
        assert payload.get("db_write_performed") is False, payload
        assert payload.get("git_write_performed") is False, payload
        assert payload.get("commit_performed") is False, payload
        assert payload.get("push_performed") is False, payload
        assert payload.get("deploy_performed") is False, payload
        assert payload.get("real_fix_performed") is False, payload
        assert payload.get("chat_stream_touched") is False, payload
        assert payload.get("typewriter_runtime_touched") is False, payload
        assert payload.get("next_recommended_layer"), payload
        future = " ".join(str(item).lower() for item in payload.get("future_direction", []))
        assert "23.6" in future, payload

        return "layer 23 status snapshot"

    def check_lux_fault_report_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/fault-report-status")
        assert status_response.status_code == 200, status_response.text
        status_payload = status_response.json()
        assert status_payload.get("layer") == "24", status_payload
        assert status_payload.get("name") == "Lux Fault Report", status_payload
        assert status_payload.get("status") == "read_only_preview", status_payload
        assert status_payload.get("read_only") is True, status_payload
        assert status_payload.get("real_fix_performed") is False, status_payload
        assert status_payload.get("chat_stream_touched") is False, status_payload
        assert status_payload.get("typewriter_runtime_touched") is False, status_payload
        summary = status_payload.get("summary_cards", {})
        assert isinstance(summary.get("open_issues"), int), status_payload
        assert isinstance(summary.get("under_review"), int), status_payload
        assert isinstance(summary.get("resolved"), int), status_payload
        assert isinstance(summary.get("deferred"), int), status_payload
        assert summary["open_issues"] >= 1, status_payload
        assert summary["resolved"] >= 1, status_payload
        assert summary["deferred"] >= 1, status_payload

        registry_response = client.get("/debug/fault-report-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "24", registry
        assert registry.get("status") == "registry_ready", registry
        sections = registry.get("sections", {})
        assert set(sections) >= {
            "open_issues",
            "deferred_issues",
            "resolved_issues",
            "issue_archive",
        }, registry
        assert isinstance(sections["open_issues"], list), registry
        assert isinstance(sections["deferred_issues"], list), registry
        assert isinstance(sections["resolved_issues"], list), registry
        assert isinstance(sections["issue_archive"], list), registry
        preview = client.get(
            "/debug/fault-report-preview",
            params={"focus": "critical", "status": "kritik", "command": "önceki stop continue sorunu"},
        )
        assert preview.status_code == 200, preview.text
        preview_payload = preview.json()
        assert preview_payload.get("read_only") is True, preview_payload
        assert preview_payload.get("real_action_performed") is False, preview_payload
        assert preview_payload.get("real_db_write_performed") is False, preview_payload
        assert preview_payload.get("safe_next_step"), preview_payload
        preview_sections = preview_payload.get("sections", {})
        assert isinstance(preview_sections, dict), preview_payload
        assert set(preview_sections) >= {"open_issues", "deferred_issues", "resolved_issues", "issue_archive"}, preview_payload
        post_preview = client.post(
            "/debug/fault-report-preview",
            json={
                "focus": "open",
                "status": "inceleniyor",
                "related_layer": "layer23",
                "command": "dur devam testleri",
            },
        )
        assert post_preview.status_code == 200, post_preview.text
        post_payload = post_preview.json()
        assert post_payload.get("raw_command"), post_payload
        assert post_payload.get("focus") == "open", post_payload
        assert isinstance(post_payload.get("sections", {}).get("open_issues", []), list), post_payload

        intelligence_status_response = client.get("/debug/fault-report-intelligence-status")
        assert intelligence_status_response.status_code == 200, intelligence_status_response.text
        intelligence_status = intelligence_status_response.json()
        assert intelligence_status.get("status") == "preview_ready", intelligence_status
        assert intelligence_status.get("read_only") is True, intelligence_status
        assert intelligence_status.get("analysis_only") is True, intelligence_status
        assert intelligence_status.get("connected_layer") == "23", intelligence_status
        assert intelligence_status.get("file_write_enabled") is False, intelligence_status
        assert intelligence_status.get("memory_write_enabled") is False, intelligence_status
        assert intelligence_status.get("db_write_enabled") is False, intelligence_status
        assert intelligence_status.get("chat_stream_touched") is False, intelligence_status
        assert intelligence_status.get("typewriter_runtime_touched") is False, intelligence_status

        intelligence_registry_response = client.get("/debug/fault-report-intelligence-registry")
        assert intelligence_registry_response.status_code == 200, intelligence_registry_response.text
        intelligence_registry = intelligence_registry_response.json()
        assert intelligence_registry.get("layer") == "24.1", intelligence_registry
        assert intelligence_registry.get("status") == "intelligence_link_ready", intelligence_registry
        assert intelligence_registry.get("read_only") is True, intelligence_registry
        assert intelligence_registry.get("issue_count", 0) >= 1, intelligence_registry
        assert "/debug/root-flow-audit" in intelligence_registry.get("related_endpoints", {}).get("recommended", []), intelligence_registry

        intelligence_preview_response = client.post(
            "/debug/fault-report-intelligence-preview",
            json={
                "issue_title": "Dur/Devam sistemi",
                "behavior": "stop_continue",
                "command": "Dur/Devam sistemi",
            },
        )
        assert intelligence_preview_response.status_code == 200, intelligence_preview_response.text
        intelligence_preview = intelligence_preview_response.json()
        assert intelligence_preview.get("read_only") is True, intelligence_preview
        assert intelligence_preview.get("analysis_only") is True, intelligence_preview
        assert intelligence_preview.get("real_action_performed") is False, intelligence_preview
        assert intelligence_preview.get("real_file_write_performed") is False, intelligence_preview
        assert intelligence_preview.get("real_db_write_performed") is False, intelligence_preview
        assert intelligence_preview.get("real_memory_write_performed") is False, intelligence_preview
        assert intelligence_preview.get("selected_issue", {}).get("title"), intelligence_preview
        assert intelligence_preview.get("son_analiz"), intelligence_preview
        assert intelligence_preview.get("recommended_checks"), intelligence_preview
        assert intelligence_preview.get("recommended_files"), intelligence_preview
        assert intelligence_preview.get("recommended_tests"), intelligence_preview
        assert intelligence_preview.get("behavior_owner", {}).get("owner"), intelligence_preview
        return "lux fault report preview"

    def check_system_control_audit_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/debug/system-control-audit")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload.get("system_name") == "Luxviai", payload
        assert payload.get("status") == "scaffold_audit_ready", payload
        assert payload.get("read_only") is True, payload
        assert payload.get("real_fix_performed") is False, payload
        checked_layers = {
            str(item.get("layer"))
            for item in payload.get("checked_layers", [])
            if isinstance(item, dict)
        }
        assert {"14", "15", "16", "17", "18", "19", "20"} <= checked_layers, payload
        endpoints = set(payload.get("available_status_endpoints", []))
        assert "/debug/layer14-status" in endpoints, payload
        assert "/debug/model-router-full-status" in endpoints, payload
        assert "/debug/backlog-registry" in endpoints, payload
        backlog_summary = payload.get("backlog_summary", {})
        backlog_text = " ".join(str(item).lower() for item in backlog_summary.get("items", []))
        assert "stop/durdur final block leak" in backlog_text, payload
        assert backlog_summary.get("stop_durdur_status") == "backlog_only", payload
        future = " ".join(str(item).lower() for item in payload.get("missing_or_future_integrations", []))
        assert "real image api later" in future, payload
        assert "real model routing later" in future, payload
        assert payload.get("chat_stream_touched") is False, payload
        assert payload.get("typewriter_runtime_touched") is False, payload
        assert payload.get("db_write_performed") is False, payload
        assert payload.get("memory_write_performed") is False, payload
        assert payload.get("file_write_performed") is False, payload
        return "system control audit"

    def check_endpoint_coverage_matrix_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/debug/endpoint-coverage")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload.get("status") == "coverage_preview_ready", payload
        assert payload.get("read_only") is True, payload
        assert payload.get("real_fix_performed") is False, payload
        groups = payload.get("endpoint_groups", {})
        expected_groups = {
            "agent_layer_14",
            "workspace_layer_15",
            "visual_layer_16",
            "voice_audio_layer_17",
            "luxway_layer_18",
            "model_router_layer_19",
            "production_layer_20",
            "development_layer_24",
        }
        assert expected_groups <= set(groups), payload
        assert payload.get("total_endpoint_count", 0) >= len(expected_groups), payload
        assert payload.get("smoke_covered_count", 0) > 0, payload
        assert payload.get("read_only_count") == payload.get("total_endpoint_count"), payload
        assert payload.get("future_integration_count", 0) > 0, payload
        backlog = " ".join(str(item).lower() for item in payload.get("backlog_related", []))
        assert "stop/durdur final block leak" in backlog, payload
        manual = " ".join(str(item).lower() for item in payload.get("uncovered_or_manual_check", []))
        assert "/ws/chat" in manual, payload
        assert payload.get("chat_stream_touched") is False, payload
        assert payload.get("typewriter_runtime_touched") is False, payload
        production_paths = {item.get("path") for item in groups.get("production_layer_20", [])}
        assert "/debug/endpoint-coverage" in production_paths, payload
        development_paths = {item.get("path") for item in groups.get("development_layer_24", [])}
        assert "/debug/fault-report-intelligence-status" in development_paths, payload
        assert "/debug/fault-report-intelligence-registry" in development_paths, payload
        assert "/debug/fault-report-intelligence-preview" in development_paths, payload
        return "endpoint coverage matrix"

    def check_live_readiness_checklist_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/debug/live-readiness")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload.get("status") == "readiness_preview_ready", payload
        assert payload.get("read_only") is True, payload
        assert payload.get("real_fix_performed") is False, payload
        backlog = " ".join(str(item).lower() for item in payload.get("known_backlog_items", []))
        assert "stop/durdur final block leak" in backlog, payload
        preview = " ".join(str(item).lower() for item in payload.get("preview_only_items", []))
        assert "real image api not enabled" in preview, payload
        assert "real voice not enabled" in preview, payload
        assert "real luxway platform not enabled" in preview, payload
        assert "real model routing not enabled" in preview, payload
        manual = " ".join(str(item).lower() for item in payload.get("manual_check_items", []))
        assert "live /health" in manual, payload
        assert "live /debug/live-readiness" in manual, payload
        blocked = " ".join(str(item).lower() for item in payload.get("blocked_for_real_launch_items", []))
        assert "real export not enabled" in blocked, payload
        assert payload.get("chat_stream_touched") is False, payload
        assert payload.get("typewriter_runtime_touched") is False, payload
        assert payload.get("db_write_performed") is False, payload
        assert payload.get("memory_write_performed") is False, payload
        assert payload.get("file_write_performed") is False, payload
        return "live readiness checklist"

    def check_master_status_summary_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/debug/master-status")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload.get("system_name") == "Luxviai", payload
        assert payload.get("status") == "layer_1_20_scaffold_complete", payload
        assert payload.get("read_only") is True, payload
        assert payload.get("real_fix_performed") is False, payload
        assert payload.get("completed_layer_range") == "1-20", payload
        layers = " ".join(str(item) for item in payload.get("completed_major_layers", []))
        for layer_id in ["Layer 14", "Layer 15", "Layer 16", "Layer 17", "Layer 18", "Layer 19", "Layer 20"]:
            assert layer_id in layers, payload
        assert payload.get("next_recommended_phase") == "Post-Layer Support Intelligence", payload
        assert payload.get("next_recommended_layer") == "Layer 21.1 Background Support Intelligence Registry", payload
        backlog = " ".join(str(item).lower() for item in payload.get("active_backlog", []))
        assert "stop/durdur final block leak" in backlog, payload
        assert "real model routing later" in backlog, payload
        preview = " ".join(str(item).lower() for item in payload.get("preview_only_integrations", []))
        assert "workspace export preview" in preview, payload
        assert "model router preview" in preview, payload
        safety = " ".join(str(item).lower() for item in payload.get("safety_boundaries", []))
        assert "no raw user text logging" in safety, payload
        assert "no real image generation yet" in safety, payload
        assert payload.get("chat_stream_touched") is False, payload
        assert payload.get("typewriter_runtime_touched") is False, payload
        assert payload.get("db_write_performed") is False, payload
        assert payload.get("memory_write_performed") is False, payload
        assert payload.get("file_write_performed") is False, payload
        return "master status summary"

    def check_lux_character_status(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/debug/lux-character-status")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload.get("lux_character_core_version") == "21.0", payload
        assert payload.get("continuous_analysis_core_enabled") is True, payload
        assert payload.get("analysis_layer_count") == 16, payload
        assert len(payload.get("analysis_layers", [])) == 16, payload
        for key in [
            "theory_lens_blending_enabled",
            "jung_in_general_lenses",
            "freud_in_general_lenses",
            "dream_priority_stack_enabled",
            "analysis_to_action_bridge_enabled",
            "personal_agent_learning_rules_enabled",
            "visual_ambrosia_rules_enabled",
            "premium_agent_voice_enabled",
            "format_count_discipline_enabled",
            "exact_transfer_discipline_enabled",
            "command_first_mindset_enabled",
            "background_support_reflexes_enabled",
            "future_layer_awareness_enabled",
            "emotional_analysis_preserved",
            "voice_analysis_future_ready",
            "clinical_claims_blocked",
        ]:
            assert payload.get(key) is True, (key, payload)
        assert payload.get("real_actions_enabled") is False, payload
        assert payload.get("chat_stream_touched") is False, payload
        assert payload.get("static_ui_touched") is False, payload

        assert "Sigmund Freud" in luxapp.THEORY_LENSES, luxapp.THEORY_LENSES
        assert "Carl Gustav Jung" in luxapp.THEORY_LENSES, luxapp.THEORY_LENSES
        dream_lenses = luxapp.infer_theory_lenses(
            "Ruyamda golge, kapi ve deniz vardi",
            {"primary_emotion": "kaygı", "theme": "belirsiz", "symbolic_density": "yüksek"},
        )
        dream_names = [item.get("name") for item in dream_lenses]
        assert "Carl Gustav Jung" in dream_names, dream_lenses
        assert "Sigmund Freud" in dream_names, dream_lenses

        prompt = luxapp.build_system_prompt(luxapp.default_profile(), {}, "luxviai", [], {}, "Konum paylaşılmadı")
        for token in [
            "CONTINUOUS ANALYSIS",
            "THEORY LENS",
            "Jung",
            "Freud",
            "LUX AMBROSIA",
            "ANALYSIS TO ACTION",
            "FORMAT / COUNT",
            "EXACTNESS",
            "COMMAND-FIRST",
            "BACKGROUND SUPPORT",
            "DO NOT INVENT",
            "LuxWorkspace",
            "Device Bridge",
            "Context Bridge",
            "Drive Mode",
            "Wake Mode",
        ]:
            assert token in prompt, token

        fallback = luxapp.fallback_reply("luxviai", {"theme": "proje", "primary_emotion": "nötr"}).lower()
        assert any(x in fallback for x in ["tek adım", "netleştir", "plan", "düzeltiyorum", "doğru sırayla"]), fallback
        assert {"luxviai", "luxching", "luxdream", "luxta", "luxeph"}.issubset(luxapp.ALLOWED_MODES), luxapp.ALLOWED_MODES
        return "lux character core/status"

    def check_location_weather_context(self) -> str:
        luxapp = self.patch_app_for_api()
        request = luxapp.ChatRequest(
            message="günaydın",
            location="Netherlands North Holland Amsterdam",
            location_latitude=52.3676,
            location_longitude=4.9041,
            location_timezone="Europe/Amsterdam",
        )
        assert request.location_latitude == 52.3676, request
        assert request.location_longitude == 4.9041, request
        assert request.location_timezone == "Europe/Amsterdam", request

        profile = luxapp.ensure_profile_shape(luxapp.default_profile())
        weather = {
            "available": True,
            "source": "open-meteo",
            "location_label": "Netherlands North Holland Amsterdam",
            "timezone": "Europe/Amsterdam",
            "local_time": "2026-06-07T09:15",
            "temperature_c": 2.0,
            "apparent_temperature_c": 0.0,
            "daily_min_c": 1.0,
            "daily_max_c": 4.0,
            "precipitation_mm": 3.5,
            "snowfall_cm": 0.0,
            "precipitation_probability": 90.0,
            "wind_gusts_kmh": 26.0,
            "weather_code": 61,
            "condition_tr": "yağmurlu",
            "significant": True,
        }
        hint = luxapp.build_weather_runtime_hint("günaydın", profile, weather)
        assert "Amsterdam" in hint, hint
        assert "2.0°C" in hint, hint
        assert "yağmurlu" in hint, hint
        assert "Koordinatları kullanıcıya yazma" in hint, hint
        assert "Aynı yağmur/şemsiye cümlesini tekrar etme" in hint, hint

        repeated = luxapp.build_weather_runtime_hint("günaydın", profile, weather)
        assert repeated == "", repeated

        explicit = luxapp.build_weather_runtime_hint("hava nasıl", profile, weather)
        assert "Amsterdam" in explicit and "yağmurlu" in explicit, explicit

        unavailable = luxapp.fetch_weather_context(None, None, "Konum paylaşılmadı", "")
        assert unavailable.get("available") is False, unavailable
        assert luxapp.weather_context_requested("dışarı çıkacağım hava nasıl") is True
        assert luxapp.weather_context_greeting("günaydın") is True
        return "permission-based weather context"

    def check_conversation_summary_command(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        user_id = f"{DEBUG_USER_ID}_summary"
        active, session = luxapp.create_new_session(user_id, "luxviai")
        samples = [
            ("user", "Layer 20 status snapshot nerede kalmıştı?"),
            ("assistant", "Layer 20 master status ile kapanmıştı."),
            ("user", "Şimdi sohbet özeti özelliği istiyorum."),
            ("assistant", "Aktif konuşma ve son mesaj kapsamı eklenebilir."),
            ("user", "Sonra tekrar Layer 20 konusuna dönebiliriz."),
            ("assistant", "Dönüş noktası ayrıca özetlenebilir."),
        ]
        for role, content in samples:
            luxapp.add_message(session, role, content, {"smoke": True})
        luxapp.save_session(user_id, active, session)

        assert luxapp.is_conversation_summary_command("son 20 mesajı özetle") is True
        assert luxapp.parse_conversation_summary_limit("son 20 mesajı özetle") == 20
        text = luxapp.get_command_response(user_id, "son 20 mesajı özetle")
        assert text and "SOHBET ÖZETİ" in text, text
        assert "Başlangıç konusu" in text, text
        assert "Önemli anlar" in text, text
        assert "Konu akışı" in text, text
        assert "Son odak" in text, text

        client = TestClient(luxapp.app)
        response = client.post("/conversation/summary", json={"user_id": user_id, "limit": 20, "scope": "smoke"})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload.get("read_only") is True, payload
        assert payload.get("memory_write_performed") is False, payload
        assert payload.get("db_write_performed") is False, payload
        assert "SOHBET ÖZETİ" in payload.get("summary", ""), payload
        return "conversation summary command"

    def check_layer21_status_snapshot(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/debug/layer21-status")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload.get("layer") == "21", payload
        assert payload.get("status") == "layer_21_preview_complete", payload
        assert payload.get("read_only") is True, payload
        completed = payload.get("completed_items", [])
        assert len(completed) == 8, payload
        assert "wake_sonic_registry" in completed, payload
        assert "background_support_registry" in completed, payload
        assert "drive_mode_preview" in completed, payload
        commits = payload.get("completed_commits", {})
        assert "21.8" in commits and "wake sonic" in commits["21.8"].lower(), payload
        endpoint_groups = payload.get("endpoint_groups", {})
        assert "21.8_wake_sonic" in endpoint_groups, payload
        assert "GET /wake-sonic/registry" in endpoint_groups.get("21.8_wake_sonic", []), payload
        safety = payload.get("safety_boundaries", {})
        assert safety.get("read_only") is True, payload
        assert safety.get("real_action_enabled") is False, payload
        assert safety.get("action_performed") is False, payload
        assert safety.get("real_send_performed") is False, payload
        assert safety.get("real_export_performed") is False, payload
        assert safety.get("real_print_performed") is False, payload
        assert safety.get("real_file_created") is False, payload
        assert safety.get("real_device_control_performed") is False, payload
        assert safety.get("real_cross_page_read_performed") is False, payload
        assert safety.get("real_screen_read_performed") is False, payload
        assert safety.get("real_vehicle_connection_performed") is False, payload
        assert safety.get("real_microphone_recording_performed") is False, payload
        assert safety.get("real_wake_detection_performed") is False, payload
        assert safety.get("memory_write_performed") is False, payload
        assert safety.get("db_write_performed") is False, payload
        assert safety.get("raw_sensitive_content_returned") is False, payload
        summary = payload.get("layer21_capability_summary", "").lower()
        assert "invisible intelligent support layer" in summary, payload
        assert "Layer 22" in payload.get("next_recommended_step", ""), payload
        future = " ".join(payload.get("future_candidates", []))
        assert "Lux Time Twin" in future, payload
        return "layer 21 status snapshot"

    def check_layer22_future_candidates_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        registry_response = client.get("/future/candidates")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "22", registry
        assert registry.get("status") == "future_candidates_ready", registry
        assert registry.get("candidate_count") == 20, registry
        assert registry.get("read_only") is True, registry
        assert registry.get("real_action_enabled") is False, registry
        candidate_names = {item.get("name") for item in registry.get("candidates", [])}
        assert "Lux Time Twin" in candidate_names, registry
        assert "Finality Sense" in candidate_names, registry

        status_response = client.get("/debug/layer22-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "22", status
        assert status.get("status") == "future_candidates_ready", status
        assert status.get("candidate_count") == 20, status
        assert status.get("read_only") is True, status
        safety = status.get("safety_boundaries", {})
        assert safety.get("real_action_enabled") is False, status
        assert safety.get("action_performed") is False, status
        assert safety.get("memory_write_performed") is False, status
        assert safety.get("db_write_performed") is False, status
        assert safety.get("file_created") is False, status
        assert safety.get("export_performed") is False, status
        assert safety.get("device_control_performed") is False, status
        assert safety.get("chat_stream_touched") is False, status
        assert safety.get("typewriter_runtime_touched") is False, status

        preview_response = client.post(
            "/future/preview",
            json={
                "command": "Time Twin fikrini ac",
                "candidate_id": "",
                "category": "",
                "user_goal": "smoke preview",
                "risk_level": "",
                "implementation_depth": "registry_preview_only",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("read_only") is True, preview
        assert preview.get("real_action_enabled") is False, preview
        assert preview.get("action_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("file_created") is False, preview
        assert preview.get("export_performed") is False, preview
        assert preview.get("device_control_performed") is False, preview
        matched = preview.get("matched_candidate") or {}
        assert matched.get("name") == "Lux Time Twin", preview

        ranking_response = client.post("/future/preview", json={"command": "Reklam degeri yuksek fikirleri goster"})
        assert ranking_response.status_code == 200, ranking_response.text
        ranking = ranking_response.json().get("candidate_ranking_preview", [])
        assert ranking, ranking_response.json()
        return "layer 22 future candidates"

    def check_layer22_full_status_snapshot(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        response = client.get("/debug/layer22-full-status")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload.get("layer") == "22", payload
        assert payload.get("status") == "layer_22_preview_complete", payload
        assert payload.get("read_only") is True, payload

        completed = payload.get("completed_items", [])
        assert len(completed) == 8, payload
        assert "ethical_boundary_soul_preview" in completed, payload
        assert "future_candidates_registry" in completed, payload
        assert payload.get("future_candidate_count") == 20, payload

        implemented = payload.get("implemented_preview_candidates", [])
        assert "Finality Sense" in implemented, payload
        assert "Ethical Boundary Soul" in implemented, payload

        safety = payload.get("safety_boundaries", {})
        assert safety.get("read_only") is True, payload
        assert safety.get("real_action_enabled") is False, payload
        assert safety.get("action_performed") is False, payload
        assert safety.get("memory_write_performed") is False, payload
        assert safety.get("db_write_performed") is False, payload
        assert safety.get("raw_sensitive_content_returned") is False, payload
        assert safety.get("real_send_performed") is False, payload
        assert safety.get("real_export_performed") is False, payload
        assert safety.get("real_device_control_performed") is False, payload
        assert safety.get("real_screen_read_performed") is False, payload
        assert safety.get("real_microphone_recording_performed") is False, payload
        assert safety.get("real_location_read_performed") is False, payload

        groups = payload.get("endpoint_groups", {})
        assert "22.8_ethical_boundary" in groups, payload
        assert "GET /debug/ethical-boundary-status" in groups.get("22.8_ethical_boundary", []), payload
        assert "Layer 23" in payload.get("recommended_next_step", ""), payload
        return "layer 22 full status snapshot"

    def check_layer22_candidate_scoring_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        matrix_response = client.get("/future/scoring-matrix")
        assert matrix_response.status_code == 200, matrix_response.text
        matrix = matrix_response.json()
        assert matrix.get("layer") == "22.2", matrix
        assert matrix.get("status") == "scoring_matrix_ready", matrix
        assert matrix.get("candidate_count") == 20, matrix
        assert matrix.get("read_only") is True, matrix
        assert matrix.get("real_action_enabled") is False, matrix
        items = matrix.get("items", [])
        names = {item.get("name") for item in items}
        assert "Finality Sense" in names, matrix
        assert "Lux Time Twin" in names, matrix
        for item in items:
            assert item.get("read_only") is True, item
            scores = item.get("scores", {})
            for score_name in [
                "practicality_score",
                "daily_use_score",
                "premium_identity_score",
                "wow_factor_score",
                "marketing_demo_score",
                "technical_complexity_score",
                "privacy_risk_score",
                "safety_risk_score",
                "dependency_score",
                "scaffold_readiness_score",
                "first_build_priority_score",
            ]:
                assert score_name in scores, item
                assert 0 <= scores[score_name] <= 10, item

        status_response = client.get("/debug/layer22-scoring-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "scoring_matrix_ready", status
        assert status.get("candidate_count") == 20, status
        assert status.get("read_only") is True, status
        safety = status.get("safety_boundaries", {})
        assert safety.get("real_action_enabled") is False, status
        assert safety.get("action_performed") is False, status
        assert safety.get("memory_write_performed") is False, status
        assert safety.get("db_write_performed") is False, status
        assert safety.get("file_created") is False, status
        assert safety.get("export_performed") is False, status
        assert safety.get("device_control_performed") is False, status

        def score_preview(command: str, focus: str = "", candidate_id: str = "") -> dict:
            response = client.post(
                "/future/score-preview",
                json={
                    "command": command,
                    "candidate_id": candidate_id,
                    "focus": focus,
                    "risk_tolerance": "normal",
                    "implementation_goal": "smoke",
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            assert payload.get("real_action_enabled") is False, payload
            assert payload.get("action_performed") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            assert payload.get("db_write_performed") is False, payload
            assert payload.get("file_created") is False, payload
            assert payload.get("export_performed") is False, payload
            assert payload.get("device_control_performed") is False, payload
            return payload

        practical = score_preview("En pratik fikirleri sirala", "practical")
        assert practical.get("focus") == "practical", practical
        assert practical.get("ranking"), practical

        marketing = score_preview("Reklam degeri yuksek olanlari goster", "marketing")
        assert marketing.get("focus") == "marketing", marketing
        assert marketing.get("ranking"), marketing

        first_build = score_preview("Ilk scaffold icin en mantikli uc fikri sec", "fastest_scaffold")
        assert first_build.get("recommended_first_build"), first_build

        risk = score_preview("Riskli fikirleri ayir", "privacy_review")
        assert risk.get("high_risk_candidates"), risk

        finality = score_preview("Finality Sense puanini goster", candidate_id="finality_sense")
        assert (finality.get("matched_candidate") or {}).get("name") == "Finality Sense", finality
        return "layer 22 candidate scoring matrix"

    def check_finality_sense_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        schema_response = client.get("/finality/schema")
        assert schema_response.status_code == 200, schema_response.text
        schema = schema_response.json()
        assert schema.get("layer") == "22.3", schema
        assert schema.get("status") == "schema_ready", schema
        assert schema.get("read_only") is True, schema
        assert "ready_to_ship" in schema.get("finality_states", []), schema
        assert "codex_output" in schema.get("artifact_types", []), schema

        status_response = client.get("/debug/finality-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "finality_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("real_action_enabled") is False, status
        assert status.get("action_performed") is False, status
        assert status.get("task_completed_performed") is False, status
        assert status.get("message_sent") is False, status
        assert status.get("file_created") is False, status
        assert status.get("export_performed") is False, status
        assert status.get("calendar_write_performed") is False, status
        assert status.get("memory_write_performed") is False, status
        assert status.get("db_write_performed") is False, status
        assert status.get("device_control_performed") is False, status

        def preview(command: str, artifact_type: str = "unknown", context_text: str = "") -> dict:
            response = client.post(
                "/finality/preview",
                json={
                    "command": command,
                    "context_text": context_text or "smoke finality preview context only",
                    "artifact_type": artifact_type,
                    "project_stage": "smoke",
                    "user_goal": "safe closeout",
                    "risk_level": "normal",
                    "desired_depth": "concise",
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            assert payload.get("real_action_enabled") is False, payload
            assert payload.get("action_performed") is False, payload
            assert payload.get("task_completed_performed") is False, payload
            assert payload.get("message_sent") is False, payload
            assert payload.get("file_created") is False, payload
            assert payload.get("export_performed") is False, payload
            assert payload.get("calendar_write_performed") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            assert payload.get("db_write_performed") is False, payload
            assert payload.get("device_control_performed") is False, payload
            score = payload.get("completion_score")
            assert isinstance(score, int) and 0 <= score <= 100, payload
            assert payload.get("detected_finality_state"), payload
            assert payload.get("recommended_next_step"), payload
            return payload

        complete = preview("Bu is tamam mi?")
        assert complete.get("detected_finality_state") in {"almost_complete", "complete", "needs_review"}, complete

        next_step = preview("Siradaki adim ne?")
        assert next_step.get("next_step_needed") is True or next_step.get("recommended_next_step"), next_step

        codex = preview(
            "Bu Codex ciktisi yeterli mi?",
            artifact_type="codex_output",
            context_text="commit var, degisen dosyalar var, endpointler var, test sonucu PASS, chat/stream typewriter dokunulmadi, static/index dokunulmadi",
        )
        assert codex.get("detected_artifact_type") == "codex_output", codex
        assert codex.get("detected_finality_state") in {"ready_to_ship", "needs_review", "risk_check_needed"}, codex

        missing = preview("Eksik bir sey kaldi mi?")
        assert missing.get("missing_items"), missing

        overbuilt = preview("Bunu artik uzatmayalim")
        assert overbuilt.get("detected_finality_state") in {"overbuilt", "should_pause"}, overbuilt

        ship = preview("Ship edilebilir mi?")
        assert ship.get("detected_finality_state") in {"ready_to_ship", "risk_check_needed", "needs_review"}, ship
        assert ship.get("ship_ready") is True or ship.get("risk_check_needed") is True, ship
        return "finality sense preview"

    def check_adaptive_interface_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        schema_response = client.get("/adaptive-interface/schema")
        assert schema_response.status_code == 200, schema_response.text
        schema = schema_response.json()
        assert schema.get("layer") == "22.4", schema
        assert schema.get("status") == "schema_ready", schema
        assert schema.get("read_only") is True, schema
        assert "workspace_surface" in schema.get("adaptive_surfaces", []), schema
        assert "minimal" in schema.get("ui_densities", []), schema
        assert "contextual_bubble" in schema.get("interaction_styles", []), schema

        status_response = client.get("/debug/adaptive-interface-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "adaptive_interface_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("real_ui_changed") is False, status
        assert status.get("frontend_runtime_modified") is False, status
        assert status.get("css_modified") is False, status
        assert status.get("dom_modified") is False, status
        assert status.get("static_index_modified") is False, status
        assert status.get("real_action_enabled") is False, status
        assert status.get("action_performed") is False, status
        assert status.get("memory_write_performed") is False, status
        assert status.get("db_write_performed") is False, status
        assert status.get("file_created") is False, status
        assert status.get("export_performed") is False, status
        assert status.get("device_control_performed") is False, status

        def preview(command: str, task_type: str = "", **extra: str) -> dict:
            response = client.post(
                "/adaptive-interface/preview",
                json={
                    "command": command,
                    "user_context": "smoke adaptive interface preview",
                    "task_type": task_type,
                    "energy_state": extra.get("energy_state", ""),
                    "attention_state": extra.get("attention_state", ""),
                    "device_context": extra.get("device_context", ""),
                    "environment": extra.get("environment", ""),
                    "risk_level": extra.get("risk_level", "normal"),
                    "desired_output": extra.get("desired_output", ""),
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            assert payload.get("real_ui_changed") is False, payload
            assert payload.get("frontend_runtime_modified") is False, payload
            assert payload.get("css_modified") is False, payload
            assert payload.get("dom_modified") is False, payload
            assert payload.get("static_index_modified") is False, payload
            assert payload.get("real_action_enabled") is False, payload
            assert payload.get("action_performed") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            assert payload.get("db_write_performed") is False, payload
            assert payload.get("file_created") is False, payload
            assert payload.get("export_performed") is False, payload
            assert payload.get("device_control_performed") is False, payload
            assert payload.get("recommended_surface"), payload
            assert payload.get("ui_density"), payload
            assert payload.get("interaction_style"), payload
            return payload

        compact = preview("Bunu sade ekranda goster", "compact_summary")
        assert compact.get("ui_density") in {"minimal", "ultra_minimal"}, compact
        assert compact.get("recommended_surface") == "compact_summary_surface", compact

        workspace = preview("Workspace gibi duzenle", "workspace")
        assert workspace.get("recommended_surface") == "workspace_surface", workspace
        assert workspace.get("interaction_style") == "workspace_blocks", workspace

        night = preview("Gece sakin modda cevapla", "night_calm", environment="night")
        assert night.get("recommended_surface") == "night_calm_surface", night

        drive = preview("Suruste kullanilacak yuzeyi goster", "drive", attention_state="driving")
        assert drive.get("recommended_surface") == "drive_minimal_surface", drive
        assert drive.get("ui_density") == "ultra_minimal", drive

        finality = preview("Bu is bitti mi ekrani gibi goster", "finality")
        assert finality.get("recommended_surface") == "finality_closure_surface", finality
        return "adaptive interface preview"

    def check_ambient_workspace_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        schema_response = client.get("/ambient-workspace/schema")
        assert schema_response.status_code == 200, schema_response.text
        schema = schema_response.json()
        assert schema.get("layer") == "22.5", schema
        assert schema.get("status") == "schema_ready", schema
        assert schema.get("read_only") is True, schema
        assert "report_workspace" in schema.get("workspace_modes", []), schema
        assert "block_stack" in schema.get("ambient_layouts", []), schema
        assert "command_block_hidden_from_export" in schema.get("block_priorities", []), schema

        status_response = client.get("/debug/ambient-workspace-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "ambient_workspace_preview_ready", status
        assert status.get("read_only") is True, status
        for key in [
            "real_workspace_modified",
            "real_editor_changed",
            "real_ui_changed",
            "frontend_runtime_modified",
            "static_index_modified",
            "file_created",
            "export_performed",
            "send_performed",
            "print_performed",
            "memory_write_performed",
            "db_write_performed",
            "action_performed",
        ]:
            assert status.get(key) is False, status

        def preview(command: str, artifact_type: str = "", **extra: str) -> dict:
            response = client.post(
                "/ambient-workspace/preview",
                json={
                    "command": command,
                    "workspace_context": "smoke ambient workspace preview",
                    "artifact_type": artifact_type,
                    "user_goal": "quiet organization",
                    "current_blocks": [],
                    "desired_output": extra.get("desired_output", ""),
                    "risk_level": extra.get("risk_level", "normal"),
                    "focus_mode": extra.get("focus_mode", ""),
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            for key in [
                "real_workspace_modified",
                "real_editor_changed",
                "real_ui_changed",
                "frontend_runtime_modified",
                "static_index_modified",
                "file_created",
                "export_performed",
                "send_performed",
                "print_performed",
                "memory_write_performed",
                "db_write_performed",
                "action_performed",
            ]:
                assert payload.get(key) is False, payload
            assert payload.get("detected_workspace_mode"), payload
            assert payload.get("recommended_layout"), payload
            assert payload.get("block_priorities"), payload
            return payload

        report = preview("Bu rapor icin Workspace'i duzenle", "report")
        assert report.get("detected_workspace_mode") == "report_workspace" or report.get("recommended_layout") == "block_stack", report

        cv = preview("CV icin temiz bir calisma alani oner", "cv")
        assert cv.get("detected_workspace_mode") == "cv_workspace", cv

        codex = preview("Codex ciktisini kontrol edecegim, alani ona gore hazirla", "codex")
        assert codex.get("detected_workspace_mode") == "codex_review_workspace", codex

        visual = preview("Gorsel prompt yaziyorum, stil alanlarini one cikar", "visual")
        assert visual.get("detected_workspace_mode") == "visual_prompt_workspace" or visual.get("recommended_layout") == "visual_style_panel", visual

        source = preview("Kaynak uydurmayi engelleyen alani goster")
        assert source.get("source_guard_needed") is True, source

        export = preview("Export'e girmeyecek komut bloklarini ayir")
        hidden = export.get("hidden_from_export_blocks", [])
        assert "command_block_hidden_from_export" in hidden, export
        assert "ai_note_hidden_from_export" in hidden, export
        return "ambient workspace preview"

    def check_intention_timeline_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        schema_response = client.get("/intention-timeline/schema")
        assert schema_response.status_code == 200, schema_response.text
        schema = schema_response.json()
        assert schema.get("layer") == "22.6", schema
        assert schema.get("status") == "schema_ready", schema
        assert schema.get("read_only") is True, schema
        assert "park_for_later" in schema.get("timeline_intents", []), schema
        assert "today" in schema.get("timeline_slots", []), schema

        status_response = client.get("/debug/intention-timeline-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "intention_timeline_preview_ready", status
        assert status.get("read_only") is True, status
        for key in [
            "real_calendar_write_performed",
            "real_reminder_created",
            "real_task_created",
            "real_memory_write_performed",
            "db_write_performed",
            "file_created",
            "export_performed",
            "send_performed",
            "print_performed",
            "action_performed",
        ]:
            assert status.get(key) is False, status

        def preview(command: str, **extra: str) -> dict:
            response = client.post(
                "/intention-timeline/preview",
                json={
                    "command": command,
                    "context_text": "smoke read-only intention timeline preview",
                    "project_name": extra.get("project_name", "Layer 22"),
                    "user_goal": "plan without real writes",
                    "current_stage": extra.get("current_stage", "preview"),
                    "desired_timeframe": extra.get("desired_timeframe", ""),
                    "energy_state": extra.get("energy_state", ""),
                    "priority_level": extra.get("priority_level", ""),
                    "risk_level": "normal",
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            for key in [
                "real_calendar_write_performed",
                "real_reminder_created",
                "real_task_created",
                "real_memory_write_performed",
                "db_write_performed",
                "file_created",
                "export_performed",
                "send_performed",
                "print_performed",
                "action_performed",
            ]:
                assert payload.get(key) is False, payload
            assert payload.get("detected_timeline_intent"), payload
            assert payload.get("detected_time_slot"), payload
            assert payload.get("next_step"), payload
            assert "resume_trigger" in payload, payload
            assert "parked_context" in payload, payload
            return payload

        parked = preview("Bunu sonra devam etmek uzere park et")
        assert parked.get("detected_timeline_intent") == "park_for_later" or parked.get("detected_time_slot") == "parked", parked

        next_step = preview("Siradaki adimi zaman cizgisine koy")
        assert next_step.get("detected_timeline_intent") == "plan_next_step", next_step

        today = preview("Bugun sadece buna odaklanalim", desired_timeframe="today")
        assert today.get("detected_timeline_intent") == "today_focus" or today.get("detected_time_slot") == "today", today

        decision = preview("Karar vermem gereken noktayi isaretle")
        assert decision.get("detected_timeline_intent") == "decision_checkpoint", decision

        energy = preview("Enerjim dusuk, buna gore planla", energy_state="low")
        assert energy.get("detected_timeline_intent") == "energy_based_planning", energy

        follow = preview("Takip gerekiyor mu?")
        assert follow.get("detected_timeline_intent") == "follow_up_needed" or follow.get("follow_up_needed") is True, follow
        return "intention timeline preview"

    def check_autonomy_dial_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        schema_response = client.get("/autonomy-dial/schema")
        assert schema_response.status_code == 200, schema_response.text
        schema = schema_response.json()
        assert schema.get("layer") == "22.7", schema
        assert schema.get("status") == "schema_ready", schema
        assert schema.get("read_only") is True, schema
        assert "suggest_only" in schema.get("autonomy_levels", []), schema
        assert "email_send" in schema.get("risk_domains", []), schema

        status_response = client.get("/debug/autonomy-dial-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "autonomy_dial_preview_ready", status
        assert status.get("read_only") is True, status
        for key in [
            "real_action_enabled",
            "action_performed",
            "message_sent",
            "email_sent",
            "file_created",
            "export_performed",
            "print_performed",
            "calendar_write_performed",
            "reminder_created",
            "task_created",
            "memory_write_performed",
            "db_write_performed",
            "device_control_performed",
            "screen_control_performed",
            "microphone_access_performed",
            "location_read_performed",
        ]:
            assert status.get(key) is False, status

        def preview(command: str, **extra: str) -> dict:
            response = client.post(
                "/autonomy-dial/preview",
                json={
                    "command": command,
                    "task_type": extra.get("task_type", "smoke"),
                    "requested_action": extra.get("requested_action", command),
                    "user_permission_state": extra.get("user_permission_state", "not_granted"),
                    "risk_domain": extra.get("risk_domain", ""),
                    "desired_autonomy_level": extra.get("desired_autonomy_level", ""),
                    "context_text": "smoke read-only autonomy dial preview",
                    "sensitivity": extra.get("sensitivity", "normal"),
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            for key in [
                "real_action_enabled",
                "action_performed",
                "message_sent",
                "email_sent",
                "file_created",
                "export_performed",
                "print_performed",
                "calendar_write_performed",
                "reminder_created",
                "task_created",
                "memory_write_performed",
                "db_write_performed",
                "device_control_performed",
                "screen_control_performed",
                "microphone_access_performed",
                "location_read_performed",
            ]:
                assert payload.get(key) is False, payload
            assert payload.get("recommended_autonomy_level"), payload
            assert payload.get("detected_risk_domain"), payload
            assert payload.get("safe_alternative"), payload
            return payload

        suggest = preview("Sadece oner, hicbir sey hazirlama")
        assert suggest.get("recommended_autonomy_level") == "suggest_only", suggest

        draft = preview("Taslak hazirla ama gonderme")
        assert draft.get("recommended_autonomy_level") == "draft_only", draft

        prepare = preview("Gondermeye hazirla, son onayi benden al", risk_domain="message_send")
        assert prepare.get("recommended_autonomy_level") == "prepare_with_confirmation", prepare
        assert prepare.get("final_confirmation_required") is True, prepare

        guided = preview("Bana adim adim yaptir")
        assert guided.get("recommended_autonomy_level") == "guided_step_by_step", guided

        mail = preview("Bu maili gonder")
        assert mail.get("recommended_autonomy_level") == "blocked_requires_permission" or mail.get("detected_risk_domain") in {"email_send", "message_send"}, mail
        assert mail.get("permission_required") is True, mail
        assert mail.get("final_confirmation_required") is True, mail

        memory = preview("Hafizaya kaydet")
        assert memory.get("detected_risk_domain") == "memory_write" or memory.get("recommended_autonomy_level") == "blocked_requires_permission", memory
        assert memory.get("permission_required") is True, memory
        assert memory.get("final_confirmation_required") is True, memory
        return "autonomy dial preview"

    def check_ethical_boundary_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        schema_response = client.get("/ethical-boundary/schema")
        assert schema_response.status_code == 200, schema_response.text
        schema = schema_response.json()
        assert schema.get("layer") == "22.8", schema
        assert schema.get("status") == "schema_ready", schema
        assert schema.get("read_only") is True, schema
        assert "no_memory_required" in schema.get("boundary_categories", []), schema
        assert "critical" in schema.get("risk_levels", []), schema
        assert "privacy_first" in schema.get("boundary_response_styles", []), schema

        status_response = client.get("/debug/ethical-boundary-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "ethical_boundary_preview_ready", status
        assert status.get("read_only") is True, status
        for key in [
            "real_action_enabled",
            "action_performed",
            "message_sent",
            "email_sent",
            "file_created",
            "export_performed",
            "print_performed",
            "calendar_write_performed",
            "reminder_created",
            "task_created",
            "memory_write_performed",
            "db_write_performed",
            "device_control_performed",
            "screen_read_performed",
            "microphone_access_performed",
            "location_read_performed",
        ]:
            assert status.get(key) is False, status

        def preview(command: str, **extra: str) -> dict:
            response = client.post(
                "/ethical-boundary/preview",
                json={
                    "command": command,
                    "context_text": "smoke read-only ethical boundary preview",
                    "requested_action": extra.get("requested_action", command),
                    "data_type": extra.get("data_type", ""),
                    "sensitivity": extra.get("sensitivity", "normal"),
                    "mode_hint": extra.get("mode_hint", ""),
                    "user_permission_state": "not_granted",
                    "autonomy_level": "preview_only",
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            for key in [
                "real_action_enabled",
                "action_performed",
                "message_sent",
                "email_sent",
                "file_created",
                "export_performed",
                "print_performed",
                "calendar_write_performed",
                "reminder_created",
                "task_created",
                "memory_write_performed",
                "db_write_performed",
                "device_control_performed",
                "screen_read_performed",
                "microphone_access_performed",
                "location_read_performed",
            ]:
                assert payload.get(key) is False, payload
            assert payload.get("detected_boundary_category"), payload
            assert payload.get("risk_level"), payload
            assert payload.get("boundary_response_style"), payload
            assert payload.get("safe_alternative"), payload
            assert payload.get("suggested_lux_response"), payload
            return payload

        memory = preview("Bunu hafizaya kaydet")
        assert memory.get("detected_boundary_category") in {"no_memory_required", "permission_required", "privacy_sensitive"}, memory

        mail = preview("Bu maili direkt gonder")
        assert mail.get("detected_boundary_category") == "final_confirmation_required" or mail.get("final_confirmation_required") is True, mail
        assert mail.get("email_sent") is False, mail

        screen = preview("Ekrani oku ve tikla")
        assert screen.get("detected_boundary_category") in {"device_control_boundary", "screen_mic_location_boundary"}, screen

        mic = preview("Mikrofonu arka planda acik tut")
        assert mic.get("detected_boundary_category") == "screen_mic_location_boundary", mic

        luxeph = preview("Bunu Luxeph modunda konusalim", mode_hint="luxeph")
        assert luxeph.get("no_memory_required") is True, luxeph
        assert luxeph.get("no_export_required") is True, luxeph
        assert luxeph.get("no_copy_required") is True, luxeph

        diagnosis = preview("Bana teshis koy", sensitivity="high")
        assert diagnosis.get("detected_boundary_category") in {"clinical_claim_blocked", "emotional_support_boundary"}, diagnosis

        safe = preview("Sadece guvenli alternatif ver")
        assert safe.get("safe_alternative"), safe
        return "ethical boundary preview"

    def check_background_support_registry_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        registry_response = client.get("/support/registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("read_only") is True, registry
        assert registry.get("real_action_enabled") is False, registry
        assert registry.get("support_count") == 20, registry
        support_names = {item.get("name") for item in registry.get("supports", [])}
        assert "Before You Send" in support_names, registry
        assert "Micro-Brief" in support_names, registry

        status_response = client.get("/debug/support-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "scaffold_ready", status
        assert status.get("support_count") == 20, status
        assert status.get("read_only") is True, status
        assert status.get("real_action_enabled") is False, status
        assert status.get("message_sent") is False, status
        assert status.get("memory_write_performed") is False, status
        assert status.get("db_write_performed") is False, status

        def preview(command: str, expected_name: str, source_area: str = "general") -> dict:
            response = client.post(
                "/support/preview",
                json={
                    "command": command,
                    "context": "smoke read-only support preview",
                    "source_area": source_area,
                    "sensitivity": "normal",
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            assert payload.get("real_action_enabled") is False, payload
            assert payload.get("action_performed") is False, payload
            assert payload.get("message_sent") is False, payload
            assert payload.get("data_saved") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            assert payload.get("db_write_performed") is False, payload
            recommended = payload.get("recommended_support", {})
            assert recommended.get("name") == expected_name, payload
            assert payload.get("detected_supports"), payload
            return payload

        preview("bunu göndermeden kontrol et", "Before You Send", "message")
        preview("nazik hayır yaz", "Polite No Generator", "message")
        preview("tek nefeslik özet çıkar", "One Breath Summary", "workspace")
        preview("micro brief yap", "Micro-Brief", "workspace")
        preview("enerjim düşük kolay plan yap", "Energy-Safe Plan", "general")
        preview("şuna isim bul", "Name This Thing", "workspace")
        return "background support registry"

    def check_meta_intelligence_core_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        registry_response = client.get("/meta/core-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("read_only") is True, registry
        assert registry.get("real_pipeline_change") is False, registry
        assert registry.get("memory_write_performed") is False, registry
        assert registry.get("db_write_performed") is False, registry
        assert registry.get("core_count") == 20, registry
        core_names = {item.get("name") for item in registry.get("cores", [])}
        assert "Lux Priority Lock" in core_names, registry
        assert "Lux Do Not Invent Guard" in core_names, registry

        status_response = client.get("/debug/meta-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "scaffold_ready", status
        assert status.get("core_count") == 20, status
        assert status.get("read_only") is True, status
        assert status.get("real_pipeline_change") is False, status
        assert status.get("memory_write_performed") is False, status
        assert status.get("db_write_performed") is False, status

        def preview(command: str, expected_names: set[str], source_area: str = "general", priority: str = "") -> dict:
            response = client.post(
                "/meta/quality-preview",
                json={
                    "command": command,
                    "draft_output": "smoke read-only meta preview",
                    "source_area": source_area,
                    "user_priority": priority,
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            assert payload.get("real_pipeline_change") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            assert payload.get("db_write_performed") is False, payload
            assert payload.get("file_write_performed") is False, payload
            detected = {item.get("name") for item in payload.get("detected_meta_cores", [])}
            assert expected_names & detected, payload
            return payload

        preview("eksiksiz aktar", {"Lux Priority Lock", "Lux Professional Memory Pack"}, "workspace", "complete")
        preview("sahneyi bozma", {"Lux Rebuild Prevention"}, "visual")
        source_guard = preview("kaynak uydurma", {"Lux Do Not Invent Guard"}, "workspace", "low_risk")
        assert source_guard.get("truthfulness_guard", {}).get("do_not_invent_guard_active") is True, source_guard
        preview("CV hazırla", {"Lux Intent Depth", "Lux Minimal Question Engine"}, "workspace")
        burden = preview("çok soru sorma", {"Lux User Burden Meter", "Lux Minimal Question Engine"}, "support", "low_stress")
        assert burden.get("user_burden_preview", {}).get("active") is True, burden
        preview("bu çıktı temiz mi", {"Lux Output Cleanliness Score"}, "general")
        return "meta intelligence core"

    def check_emotional_reflection_support_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        registry_response = client.get("/emotional/reflection-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("read_only") is True, registry
        assert registry.get("clinical_diagnosis_allowed") is False, registry
        assert registry.get("therapy_claim_made") is False, registry
        assert registry.get("memory_write_performed") is False, registry
        assert registry.get("db_write_performed") is False, registry
        assert registry.get("support_count") == 12, registry
        support_names = {item.get("name") for item in registry.get("supports", [])}
        assert "Emotional Signal Map" in support_names, registry
        assert "İç Ses Editörü" in support_names, registry
        assert "Değer Pusulası" in support_names, registry

        status_response = client.get("/debug/emotional-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "scaffold_ready", status
        assert status.get("support_count") == 12, status
        assert status.get("read_only") is True, status
        assert status.get("clinical_diagnosis_performed") is False, status
        assert status.get("therapy_claim_made") is False, status
        assert status.get("memory_write_performed") is False, status
        assert status.get("db_write_performed") is False, status

        def preview(command: str, expected_names: set[str], source_area: str = "general") -> dict:
            response = client.post(
                "/emotional/reflection-preview",
                json={
                    "command": command,
                    "context": "smoke read-only emotional reflection preview",
                    "source_area": source_area,
                    "sensitivity": "normal",
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            assert payload.get("clinical_diagnosis_performed") is False, payload
            assert payload.get("therapy_claim_made") is False, payload
            assert payload.get("crisis_handling_performed") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            assert payload.get("db_write_performed") is False, payload
            assert payload.get("file_write_performed") is False, payload
            detected = {item.get("name") for item in payload.get("detected_supports", [])}
            assert expected_names & detected, payload
            assert payload.get("safe_next_step"), payload
            return payload

        energy = preview("enerjim düşük", {"Emotional Signal Map"}, "general")
        assert energy.get("energy_signal_preview", {}).get("active") is True, energy
        preview("iç sesim çok sert", {"İç Ses Editörü"}, "voice")
        value = preview("hız mı kalite mi bilmiyorum", {"Değer Pusulası"}, "workspace")
        assert value.get("value_conflict_preview", {}).get("active") is True, value
        preview("bugün ne yaptım toparla", {"Reflection Layer"}, "general")
        preview("hep aynı yerde takılıyorum", {"Personal Pattern Review"}, "general")
        preview("rüyamdaki sembol ne hissettiriyor", {"Rüya / Sembol / İç Durum Bağlantısı"}, "visual")
        return "emotional reflection support"

    def check_context_bridge_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        schema_response = client.get("/context-bridge/schema")
        assert schema_response.status_code == 200, schema_response.text
        schema = schema_response.json()
        assert schema.get("status") == "context_bridge_schema_ready", schema
        assert schema.get("read_only") is True, schema
        assert schema.get("retrieval_allowed") is False, schema
        mode_ids = {item.get("id") for item in schema.get("transfer_modes", [])}
        assert {
            "silent_continue",
            "compact_summary",
            "detailed_transfer",
            "exact_full_transfer_request",
            "topic_specific_retrieval",
            "whole_page_transfer",
            "scattered_topic_extraction",
        } <= mode_ids, schema

        status_response = client.get("/debug/context-bridge-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "scaffold_ready", status
        assert status.get("read_only") is True, status
        assert status.get("real_cross_page_read_performed") is False, status
        assert status.get("memory_read_performed") is False, status
        assert status.get("memory_write_performed") is False, status
        assert status.get("raw_sensitive_content_returned") is False, status

        def preview(command: str, expected_mode: set[str], topic: str = "") -> dict:
            response = client.post(
                "/context-bridge/preview",
                json={
                    "command": command,
                    "source_label": "smoke source page",
                    "target_topic": topic,
                    "transfer_mode": "",
                    "sensitivity": "normal",
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            assert payload.get("retrieval_allowed") is False, payload
            assert payload.get("real_cross_page_read_performed") is False, payload
            assert payload.get("memory_read_performed") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            assert payload.get("raw_sensitive_content_returned") is False, payload
            assert payload.get("db_write_performed") is False, payload
            assert payload.get("file_write_performed") is False, payload
            mode = payload.get("detected_transfer_mode", {}).get("id")
            assert mode in expected_mode, payload
            assert payload.get("safe_transfer_plan", {}).get("steps"), payload
            assert payload.get("privacy_boundary", {}).get("no_hidden_history_search") is True, payload
            return payload

        preview("eksiksiz aktar", {"exact_full_transfer_request", "detailed_transfer"})
        preview("gorsel stil kararlarini kisa ozetle", {"compact_summary"})
        luxway = preview("sadece Luxway kismini getir", {"topic_specific_retrieval"})
        assert luxway.get("target_topic") == "Luxway", luxway
        preview("ozetleme sadece oku ve devam et", {"silent_continue"})
        preview("Layer 16 gorsel kurallarini cikar", {"scattered_topic_extraction", "topic_specific_retrieval"})
        return "context bridge preview"

    def check_device_bridge_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        schema_response = client.get("/device-bridge/schema")
        assert schema_response.status_code == 200, schema_response.text
        schema = schema_response.json()
        assert schema.get("status") == "device_bridge_schema_ready", schema
        assert schema.get("read_only") is True, schema
        assert schema.get("can_execute_now") is False, schema
        capability_ids = {item.get("id") for item in schema.get("capability_groups", [])}
        assert {
            "phone_to_pc_session",
            "youtube_video_follow",
            "live_stream_follow",
            "extract_notes",
            "one_page_summary",
            "report_builder",
            "send_ready_preview",
            "export_ready_preview",
            "print_ready_preview",
            "nearby_printer_preview",
            "app_handoff_preview",
        } <= capability_ids, schema

        status_response = client.get("/debug/device-bridge-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "scaffold_ready", status
        assert status.get("read_only") is True, status
        assert status.get("real_device_control_performed") is False, status
        assert status.get("real_pairing_performed") is False, status
        assert status.get("real_screen_read_performed") is False, status
        assert status.get("real_video_read_performed") is False, status
        assert status.get("real_file_created") is False, status
        assert status.get("real_export_performed") is False, status
        assert status.get("real_send_performed") is False, status
        assert status.get("real_print_performed") is False, status
        assert status.get("memory_read_performed") is False, status
        assert status.get("memory_write_performed") is False, status

        def preview(command: str, expected_ids: set[str]) -> dict:
            response = client.post(
                "/device-bridge/preview",
                json={
                    "command": command,
                    "source_device": "smoke phone",
                    "target_device": "",
                    "surface_type": "",
                    "content_type": "",
                    "requested_output": "smoke prepared-state",
                    "risk_level": "normal",
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            assert payload.get("can_execute_now") is False, payload
            assert payload.get("real_device_control_performed") is False, payload
            assert payload.get("real_pairing_performed") is False, payload
            assert payload.get("real_screen_read_performed") is False, payload
            assert payload.get("real_video_read_performed") is False, payload
            assert payload.get("real_file_created") is False, payload
            assert payload.get("real_export_performed") is False, payload
            assert payload.get("real_send_performed") is False, payload
            assert payload.get("real_print_performed") is False, payload
            assert payload.get("memory_read_performed") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            detected = set(payload.get("detected_bridge_intent", {}).get("capability_ids", []))
            assert expected_ids & detected, payload
            assert payload.get("safe_device_plan", {}).get("steps"), payload
            assert payload.get("prepared_state", {}).get("file_created") is False, payload
            return payload

        preview("YouTube videosunu takip et ve not cikar", {"youtube_video_follow", "extract_notes"})
        preview("Canli yayindan tek sayfalik rapor hazirla", {"live_stream_follow", "one_page_summary", "report_builder"})
        preview("Mail olarak gondermeye hazirla ama gonderme", {"send_ready_preview"})
        preview("Yakindaki yazicidan cikti almaya hazirla", {"print_ready_preview", "nearby_printer_preview"})
        preview("Telefondan bilgisayardaki Lux oturumunu yonet", {"phone_to_pc_session"})
        preview("Bilgisayarda acik sayfayi telefondan devam ettir", {"app_handoff_preview", "browser_surface"})
        return "device bridge preview"

    def check_pointer_context_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        schema_response = client.get("/pointer/schema")
        assert schema_response.status_code == 200, schema_response.text
        schema = schema_response.json()
        assert schema.get("status") == "pointer_schema_ready", schema
        assert schema.get("read_only") is True, schema
        assert schema.get("can_execute_now") is False, schema
        type_ids = {item.get("id") for item in schema.get("detected_types", [])}
        assert {"text_selection", "table_region", "error_message", "email_or_message", "address", "map_location"} <= type_ids, schema
        action_ids = {item.get("id") for item in schema.get("suggested_action_groups", [])}
        assert {"explain", "summarize", "create_reply_draft", "export_ready_preview", "print_ready_preview"} <= action_ids, schema
        assert schema.get("real_screen_read_performed") is False, schema
        assert schema.get("real_click_performed") is False, schema
        assert schema.get("real_control_performed") is False, schema

        status_response = client.get("/debug/pointer-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "scaffold_ready", status
        assert status.get("read_only") is True, status
        assert status.get("real_screen_read_performed") is False, status
        assert status.get("real_click_performed") is False, status
        assert status.get("real_control_performed") is False, status
        assert status.get("real_send_performed") is False, status
        assert status.get("real_export_performed") is False, status
        assert status.get("real_print_performed") is False, status
        assert status.get("real_file_created") is False, status
        assert status.get("memory_read_performed") is False, status
        assert status.get("memory_write_performed") is False, status

        def preview(command: str, expected_types: set[str], expected_actions: set[str], selected_text: str = "", context_hint: str = "") -> dict:
            response = client.post(
                "/pointer/preview-action",
                json={
                    "command": command,
                    "selected_text": selected_text,
                    "context_hint": context_hint,
                    "surface_type": "",
                    "source_app": "smoke surface",
                    "target_intent": "",
                    "sensitivity": "normal",
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            assert payload.get("can_execute_now") is False, payload
            assert payload.get("real_screen_read_performed") is False, payload
            assert payload.get("real_click_performed") is False, payload
            assert payload.get("real_control_performed") is False, payload
            assert payload.get("real_send_performed") is False, payload
            assert payload.get("real_export_performed") is False, payload
            assert payload.get("real_print_performed") is False, payload
            assert payload.get("real_file_created") is False, payload
            assert payload.get("memory_read_performed") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            detected_type = payload.get("detected_type", {}).get("id")
            assert detected_type in expected_types, payload
            detected_actions = {item.get("id") for item in payload.get("suggested_actions", [])}
            assert expected_actions & detected_actions, payload
            assert payload.get("privacy_boundary", {}).get("no_silent_screen_scraping") is True, payload
            assert payload.get("safe_pointer_plan", {}).get("steps"), payload
            return payload

        preview("Bu hata ne demek?", {"error_message"}, {"troubleshoot", "explain"}, context_hint="error message")
        preview("Bu tabloyu ozetle", {"table_region"}, {"summarize"}, context_hint="table region")
        preview("Bu mesaja cevap taslagi yaz", {"email_or_message"}, {"create_reply_draft"}, context_hint="message")
        preview("Bu adrese yol tarifi hazirla", {"address", "map_location"}, {"navigation_ready_preview"}, context_hint="address")
        preview("Bunu PDF'e hazirla ama export etme", {"pdf_region", "text_selection", "paragraph"}, {"export_ready_preview"}, selected_text="Secili metin")
        preview("Bunu yazdirmaya hazirla ama yazdirma", {"text_selection", "paragraph"}, {"print_ready_preview"}, selected_text="Secili cikti metni")
        return "pointer context preview"

    def check_drive_mode_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        schema_response = client.get("/drive-mode/schema")
        assert schema_response.status_code == 200, schema_response.text
        schema = schema_response.json()
        assert schema.get("status") == "drive_mode_schema_ready", schema
        assert schema.get("read_only") is True, schema
        assert schema.get("can_execute_now") is False, schema
        intent_ids = {item.get("id") for item in schema.get("intent_groups", [])}
        assert {
            "drive_safe_minimal_response",
            "voice_note_capture_preview",
            "message_reply_draft_preview",
            "call_prepare_preview",
            "unsafe_visual_task_block",
            "arrival_resume_context",
        } <= intent_ids, schema
        assert schema.get("real_vehicle_connection_performed") is False, schema
        assert schema.get("real_location_read_performed") is False, schema
        assert schema.get("real_microphone_recording_performed") is False, schema
        assert schema.get("real_message_sent") is False, schema
        assert schema.get("real_call_started") is False, schema

        status_response = client.get("/debug/drive-mode-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "scaffold_ready", status
        assert status.get("read_only") is True, status
        assert status.get("real_vehicle_connection_performed") is False, status
        assert status.get("real_location_read_performed") is False, status
        assert status.get("real_microphone_recording_performed") is False, status
        assert status.get("real_message_sent") is False, status
        assert status.get("real_call_started") is False, status
        assert status.get("real_device_control_performed") is False, status
        assert status.get("real_file_created") is False, status
        assert status.get("memory_read_performed") is False, status
        assert status.get("memory_write_performed") is False, status
        assert status.get("motion_ui_rules", {}).get("long_text_blocked") is True, status
        assert status.get("motion_ui_rules", {}).get("list_ui_blocked") is True, status
        assert status.get("motion_ui_rules", {}).get("scroll_ui_blocked") is True, status

        def preview(command: str, expected_ids: set[str]) -> dict:
            response = client.post(
                "/drive-mode/preview",
                json={
                    "command": command,
                    "vehicle_state": "smoke vehicle",
                    "motion_state": "moving",
                    "user_attention_state": "driving",
                    "requested_action": "",
                    "risk_level": "normal",
                    "surface_type": "minimal drive surface",
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            assert payload.get("can_execute_now") is False, payload
            assert payload.get("long_text_blocked") is True, payload
            assert payload.get("list_ui_blocked") is True, payload
            assert payload.get("scroll_ui_blocked") is True, payload
            assert payload.get("real_vehicle_connection_performed") is False, payload
            assert payload.get("real_location_read_performed") is False, payload
            assert payload.get("real_microphone_recording_performed") is False, payload
            assert payload.get("real_message_sent") is False, payload
            assert payload.get("real_call_started") is False, payload
            assert payload.get("real_device_control_performed") is False, payload
            assert payload.get("real_file_created") is False, payload
            assert payload.get("memory_read_performed") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            detected = set(payload.get("detected_drive_intent", {}).get("intent_ids", []))
            assert expected_ids & detected, payload
            assert payload.get("minimal_ui_state", {}).get("large_text_allowed") is False, payload
            assert payload.get("safe_drive_plan", {}).get("not_navigation_app") is True, payload
            return payload

        preview("Surus modunu ac", {"drive_safe_minimal_response"})
        preview("Bunu not al, varinca devam edelim", {"voice_note_capture_preview", "arrival_resume_context"})
        preview("Bu mesaja cevap taslagi hazirla", {"message_reply_draft_preview", "two_step_confirmation_preview"})
        preview("Simdi uzun raporu goster", {"unsafe_visual_task_block"})
        preview("Arama hazirligi yap ama arama baslatma", {"call_prepare_preview"})
        return "drive mode preview"

    def check_wake_sonic_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)

        schema_response = client.get("/wake-sonic/schema")
        assert schema_response.status_code == 200, schema_response.text
        schema = schema_response.json()
        assert schema.get("status") == "wake_sonic_schema_ready", schema
        assert schema.get("read_only") is True, schema
        wake_ids = {item.get("id") for item in schema.get("wake_modes", [])}
        assert {"off", "app_open_wake_phrase", "permissioned_background_wake_phrase"} <= wake_ids, schema
        safety = schema.get("wake_safety_flags", {})
        assert safety.get("microphone_access_enabled") is False, schema
        assert safety.get("real_wake_detection_performed") is False, schema
        assert safety.get("continuous_recording_performed") is False, schema
        assert safety.get("hidden_recording_allowed") is False, schema
        assert safety.get("audio_recorded") is False, schema
        assert safety.get("audio_transcribed") is False, schema
        assert safety.get("audio_played") is False, schema
        assert safety.get("background_listening_enabled") is False, schema

        registry_response = client.get("/wake-sonic/registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("status") == "wake_sonic_registry_ready", registry
        family_ids = {item.get("id") for item in registry.get("sonic_family", [])}
        assert {"lux_wake", "lux_listen", "lux_confirm", "lux_hold", "lux_soft_error", "lux_night"} <= family_ids, registry
        assert "warm_amber_halo" in registry.get("sonic_signature", {}).get("style_tags", []), registry
        assert registry.get("microphone_access_enabled") is False, registry

        status_response = client.get("/debug/wake-sonic-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("status") == "scaffold_ready", status
        assert status.get("read_only") is True, status
        assert status.get("microphone_access_enabled") is False, status
        assert status.get("real_wake_detection_performed") is False, status
        assert status.get("continuous_recording_performed") is False, status
        assert status.get("hidden_recording_allowed") is False, status
        assert status.get("audio_recorded") is False, status
        assert status.get("audio_transcribed") is False, status
        assert status.get("audio_played") is False, status
        assert status.get("background_listening_enabled") is False, status
        assert status.get("memory_read_performed") is False, status
        assert status.get("memory_write_performed") is False, status

        def preview(command: str, expected_wake: set[str] | None = None, expected_sonic: set[str] | None = None) -> dict:
            response = client.post(
                "/wake-sonic/preview",
                json={
                    "command": command,
                    "wake_mode": "",
                    "sonic_event": "",
                    "environment": "smoke",
                    "sensitivity": "normal",
                    "user_permission_state": "not_granted",
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload.get("read_only") is True, payload
            assert payload.get("microphone_access_enabled") is False, payload
            assert payload.get("real_wake_detection_performed") is False, payload
            assert payload.get("continuous_recording_performed") is False, payload
            assert payload.get("hidden_recording_allowed") is False, payload
            assert payload.get("audio_recorded") is False, payload
            assert payload.get("audio_transcribed") is False, payload
            assert payload.get("audio_played") is False, payload
            assert payload.get("background_listening_enabled") is False, payload
            assert payload.get("memory_read_performed") is False, payload
            assert payload.get("memory_write_performed") is False, payload
            if expected_wake:
                assert payload.get("detected_wake_mode", {}).get("id") in expected_wake, payload
            if expected_sonic:
                assert payload.get("sonic_family_item", {}).get("id") in expected_sonic, payload
            assert payload.get("safety_boundary", {}).get("no_hidden_recording") is True, payload
            return payload

        preview("Wake mode kapali olsun", {"off"}, None)
        preview("Uygulama acikken Hey Lux ile uyansin", {"app_open_wake_phrase"}, None)
        preview("Arka planda izinli wake phrase fikrini goster", {"permissioned_background_wake_phrase"}, None)
        preview("Lux'un acilis sesini tarif et", None, {"lux_wake"})
        preview("Onay sesi premium olsun", None, {"lux_confirm"})
        preview("Gece modu sesi daha sakin olsun", None, {"lux_night"})
        return "wake sonic preview"

    def check_live_server_health(self) -> str:
        base_url = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        try:
            with urlopen(base_url + "/health", timeout=1.0) as resp:
                assert resp.status == 200, resp.status
        except (URLError, OSError, TimeoutError) as exc:
            raise SkipCheck(f"no live server at {base_url}: {type(exc).__name__}")
        return base_url

    def check_local_privacy_scan(self) -> str:
        scan_roots = [
            ROOT / "data",
            ROOT / "data" / "global",
            ROOT / "data" / "fine-tune",
            ROOT / "data" / "fine_tune",
        ]
        hits: list[str] = []
        for root in scan_roots:
            if not root.exists():
                continue
            if root.is_file():
                paths = [root]
            else:
                paths = [p for p in root.rglob("*") if p.is_file()]
            for path in paths:
                try:
                    if self.raw_phrase in path.read_text(encoding="utf-8", errors="ignore"):
                        hits.append(str(path.relative_to(ROOT)))
                except Exception:
                    continue
        assert not hits, hits
        return "raw phrase absent"

    def run(self) -> int:
        print(f"ROOT {ROOT}")
        checks: list[tuple[str, Callable[[], str | None]]] = [
            ("py_compile_app", self.check_py_compile_app),
            ("compileall_learning", self.check_compileall_learning),
            ("health_shape_16_layers", self.check_health_shape),
            ("count_guard", self.check_count_guard),
            ("line_format_guard", self.check_line_format_guard),
            ("format_prompt_cleanup", self.check_format_prompt_and_cleanup),
            ("identity_guard", self.check_identity_guard),
            ("double_response_trim", self.check_double_response_trim),
            ("frontend_resume_scaffold", self.check_frontend_resume_scaffold),
            ("cost_logger_privacy", self.check_cost_logger_privacy),
            ("practical_support_passive", self.check_practical_support),
            ("token_budget_observe_only", self.check_token_budget),
            ("efficiency_router_shadow", self.check_efficiency_and_shadow),
            ("auto_continuation", self.check_auto_continuation),
            ("api_schema_in_process", self.check_api_schema),
            ("agent_capabilities_schema", self.check_agent_capabilities_api),
            ("agent_privacy_rules", self.check_agent_privacy_rules_present),
            ("luxway_status_inactive", self.check_luxway_capabilities_planned_inactive),
            ("memory_schema_fields", self.check_memory_schema_contains_fields),
            ("memory_preview_raw_data", self.check_memory_preview_signal_privacy),
            ("agent_high_risk_confirmation", self.check_high_risk_agent_confirmation),
            ("agent_preview_intent_read_only", self.check_agent_preview_intent_read_only),
            ("agent_plan_action_read_only", self.check_agent_plan_action_read_only),
            ("agent_analyze_hub_read_only", self.check_agent_analyze_hub_read_only),
            ("router_preview_read_only", self.check_router_preview_read_only),
            ("debug_sample_preview_endpoints", self.check_debug_sample_preview_endpoints),
            ("debug_agent_panel", self.check_debug_agent_panel),
            ("mode_registry_preview", self.check_mode_registry_preview),
            ("permission_boundary_preview", self.check_permission_boundary_preview),
            ("agent_decision_trace_preview", self.check_agent_decision_trace_preview),
            ("layer14_status_snapshot", self.check_layer14_status_snapshot),
            ("workspace_schema_preview", self.check_workspace_schema_preview),
            ("visual_style_registry_preview", self.check_visual_style_registry_preview),
            ("visual_status_snapshot", self.check_visual_status_snapshot),
            ("voice_speed_preview", self.check_voice_speed_preview),
            ("night_radio_voice_preview", self.check_night_radio_voice_preview),
            ("voice_audio_status_snapshot", self.check_voice_audio_status_snapshot),
            ("audio_signal_preview", self.check_audio_signal_preview),
            ("audio_privacy_boundary_preview", self.check_audio_privacy_boundary_preview),
            ("model_router_config_preview", self.check_model_router_config_preview),
            ("model_router_hint_preview", self.check_model_router_hint_preview),
            ("cost_privacy_policy_preview", self.check_cost_privacy_policy_preview),
            ("safe_memory_retrieval_preview", self.check_safe_memory_retrieval_preview),
            ("routing_simulation_preview", self.check_routing_simulation_preview),
            ("model_router_full_status_snapshot", self.check_model_router_full_status_snapshot),
            ("production_hardening_backlog_registry", self.check_production_hardening_backlog_registry),
            ("root_flow_auditor_preview", self.check_root_flow_auditor_preview),
            ("safe_self_check_runner_preview", self.check_safe_self_check_runner_preview),
            ("codex_handoff_builder_preview", self.check_codex_handoff_builder_preview),
            ("bug_intake_investigation_planner_preview", self.check_bug_intake_investigation_planner_preview),
            ("credit_saver_engine_preview", self.check_credit_saver_engine_preview),
            ("debug_intelligence_core_preview", self.check_debug_intelligence_core_preview),
            ("layer23_status_snapshot", self.check_layer23_status_snapshot),
            ("lux_fault_report_preview", self.check_lux_fault_report_preview),
            ("system_control_audit_preview", self.check_system_control_audit_preview),
            ("endpoint_coverage_matrix_preview", self.check_endpoint_coverage_matrix_preview),
            ("live_readiness_checklist_preview", self.check_live_readiness_checklist_preview),
            ("master_status_summary_preview", self.check_master_status_summary_preview),
            ("lux_character_status", self.check_lux_character_status),
            ("location_weather_context", self.check_location_weather_context),
            ("conversation_summary_command", self.check_conversation_summary_command),
            ("layer21_status_snapshot", self.check_layer21_status_snapshot),
            ("layer22_future_candidates_preview", self.check_layer22_future_candidates_preview),
            ("layer22_full_status_snapshot", self.check_layer22_full_status_snapshot),
            ("layer22_candidate_scoring_preview", self.check_layer22_candidate_scoring_preview),
            ("finality_sense_preview", self.check_finality_sense_preview),
            ("adaptive_interface_preview", self.check_adaptive_interface_preview),
            ("ambient_workspace_preview", self.check_ambient_workspace_preview),
            ("intention_timeline_preview", self.check_intention_timeline_preview),
            ("autonomy_dial_preview", self.check_autonomy_dial_preview),
            ("ethical_boundary_preview", self.check_ethical_boundary_preview),
            ("background_support_registry_preview", self.check_background_support_registry_preview),
            ("meta_intelligence_core_preview", self.check_meta_intelligence_core_preview),
            ("emotional_reflection_support_preview", self.check_emotional_reflection_support_preview),
            ("context_bridge_preview", self.check_context_bridge_preview),
            ("device_bridge_preview", self.check_device_bridge_preview),
            ("pointer_context_preview", self.check_pointer_context_preview),
            ("drive_mode_preview", self.check_drive_mode_preview),
            ("wake_sonic_preview", self.check_wake_sonic_preview),
            ("luxway_capability_preview", self.check_luxway_capability_preview),
            ("luxway_permission_model_preview", self.check_luxway_permission_model_preview),
            ("luxway_weekly_report_preview", self.check_luxway_weekly_report_preview),
            ("luxway_data_preview", self.check_luxway_data_preview),
            ("luxway_device_safety_preview", self.check_luxway_device_safety_preview),
            ("luxway_full_status_snapshot", self.check_luxway_full_status_snapshot),
            ("ws_stream_schema_in_process", self.check_ws_stream_schema),
            ("live_server_health", self.check_live_server_health),
            ("local_privacy_scan", self.check_local_privacy_scan),
        ]
        try:
            for name, fn in checks:
                self.check(name, fn)
        finally:
            self.cleanup()

        counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
        for result in self.results:
            counts[result.status] = counts.get(result.status, 0) + 1
        print(f"SUMMARY PASS={counts['PASS']} FAIL={counts['FAIL']} SKIP={counts['SKIP']}")
        return 1 if counts["FAIL"] else 0


class SkipCheck(Exception):
    pass


if __name__ == "__main__":
    raise SystemExit(SmokeRunner().run())
