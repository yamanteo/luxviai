from __future__ import annotations

import argparse
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEBUG_USER_ID = "debug_smoke"

SMOKE_MODE = "full"
SELECTED_LAYER = None  # int | None
SELECTED_LAYER_RANGE = None  # tuple[int, int] | None
SELECTED_CHECK = None  # str | None
QUICK_MODE = False


@dataclass
class CheckDef:
    name: str
    fn: Callable[[], str | None]
    layer: int | None = None
    category: str = "core"


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
            "/debug/knowledge-extractor-status",
            "/debug/knowledge-extractor-registry",
            "/debug/repeated-pattern-status",
            "/debug/repeated-pattern-registry",
            "/debug/investigation-starter-status",
            "/debug/investigation-starter-registry",
            "/debug/investigation-priority-status",
            "/debug/investigation-priority-registry",
            "/debug/task-planner-status",
            "/debug/task-planner-registry",
            "/debug/dev-agent-explorer-status",
            "/debug/dev-agent-explorer-registry",
            "/debug/dependency-mapper-status",
            "/debug/dependency-mapper-registry",
            "/debug/impact-analyzer-status",
            "/debug/impact-analyzer-registry",
            "/debug/change-boundary-status",
            "/debug/change-boundary-registry",
            "/debug/patch-planner-status",
            "/debug/patch-planner-registry",
            "/debug/verification-planner-status",
            "/debug/verification-planner-registry",
            "/debug/dev-agent-readiness-status",
            "/debug/dev-agent-readiness-registry",
            "/debug/layer25-status",
            "/debug/constitution-status",
            "/debug/constitution-registry",
            "/debug/project-rules-status",
            "/debug/project-rules-registry",
            "/debug/explorer-agent-status",
            "/debug/explorer-agent-registry",
            "/debug/planner-agent-status",
            "/debug/planner-agent-registry",
            "/debug/verifier-agent-status",
            "/debug/verifier-agent-registry",
            "/debug/evidence-store-status",
            "/debug/evidence-store-registry",
            "/debug/coordinator-status",
            "/debug/coordinator-registry",
            "/debug/root-cause-status",
            "/debug/root-cause-registry",
            "/debug/root-cause-preview",
            "/debug/change-memory-status",
            "/debug/change-memory-registry",
            "/debug/change-memory-preview",
            "/debug/failed-change-status",
            "/debug/failed-change-registry",
            "/debug/failed-change-preview",
            "/debug/change-planning-status",
            "/debug/change-planning-registry",
            "/debug/change-planning-preview",
            "/debug/clone-workspace-status",
            "/debug/clone-workspace-registry",
            "/debug/clone-workspace-preview",
            "/debug/sandbox-repair-status",
            "/debug/sandbox-repair-registry",
            "/debug/sandbox-repair-preview",
            "/debug/verification-status",
            "/debug/verification-registry",
            "/debug/verification-preview",
            "/debug/delivery-readiness-status",
            "/debug/delivery-readiness-registry",
            "/debug/delivery-readiness-preview",
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
        assert "/debug/layer32-status" in html, html[:300]
        assert "/debug/layer32-full-status" in html, html[:300]
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

    def check_investigation_context_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/investigation-context-status")
        assert status_response.status_code == 200, status_response.text
        status_payload = status_response.json()
        assert status_payload.get("layer") == "24.2", status_payload
        assert status_payload.get("name") == "Active Investigation Context Preview", status_payload
        assert status_payload.get("status") == "preview_ready", status_payload
        assert status_payload.get("read_only") is True, status_payload
        assert status_payload.get("analysis_only") is True, status_payload
        assert status_payload.get("real_file_write_performed") is False, status_payload
        assert status_payload.get("real_memory_write_performed") is False, status_payload
        assert status_payload.get("real_db_write_performed") is False, status_payload
        assert status_payload.get("chat_stream_touched") is False, status_payload
        assert status_payload.get("typewriter_runtime_touched") is False, status_payload

        registry_response = client.get("/debug/investigation-context-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "24.2", registry
        assert registry.get("status") == "registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert registry.get("task_count", 0) >= 5, registry
        tasks = registry.get("tasks", [])
        assert isinstance(tasks, list), registry
        assert any(item.get("active_task") for item in tasks), registry

        preview_response = client.post(
            "/debug/investigation-context-preview",
            json={
                "active_task": "stop_continue",
                "goal": "multiple continue cycles support",
                "command": "dur 3. maddede devam et",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("active_task") == "stop_continue", preview
        assert preview.get("goal"), preview
        assert preview.get("risk_level"), preview
        assert isinstance(preview.get("current_findings"), list), preview
        assert isinstance(preview.get("completed_steps"), list), preview
        assert isinstance(preview.get("remaining_steps"), list), preview
        assert isinstance(preview.get("do_not_touch"), list), preview
        assert preview.get("recommended_next_step"), preview
        assert isinstance(preview.get("confidence_score"), (int, float)), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("real_action_performed") is False, preview
        assert preview.get("real_file_write_performed") is False, preview
        assert preview.get("real_memory_write_performed") is False, preview
        assert preview.get("real_db_write_performed") is False, preview

        return "investigation context preview"

    def check_investigation_timeline_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/investigation-timeline-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "24.3", status
        assert status.get("name") == "Investigation Timeline Preview", status
        assert status.get("status") == "timeline_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("real_action_performed") is False, status
        assert status.get("real_file_write_performed") is False, status
        assert status.get("real_memory_write_performed") is False, status
        assert status.get("real_db_write_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status
        related_layers = set(status.get("related_layers", []))
        assert {"/debug/bug-intake-status", "/debug/root-flow-auditor-status", "/debug/self-check-status"} <= related_layers, status

        registry_response = client.get("/debug/investigation-timeline-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "24.3", registry
        assert registry.get("name") == "Investigation Timeline Registry", registry
        assert registry.get("status") == "timeline_registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert registry.get("timeline_issue_count", 0) >= 1, registry
        assert len(registry.get("timeline_event_types", [])) >= 10, registry

        preview_response = client.post(
            "/debug/investigation-timeline-preview",
            json={
                "issue_title": "Dur/Devam sistemi",
                "command": "dur 3. maddede devam et",
                "current_status": "Inceleniyor",
                "command_behavior": "stop_continue",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("issue_title") == "Dur/Devam sistemi", preview
        assert isinstance(preview.get("current_status"), str), preview
        assert preview.get("current_status"), preview
        timeline_entries = preview.get("timeline_entries", [])
        assert isinstance(timeline_entries, list), preview
        assert len(timeline_entries) >= 1, preview
        event_types = {entry.get("event") for entry in timeline_entries}
        assert {"issue_created", "audit_started"} <= event_types, preview
        assert preview.get("latest_finding"), preview
        assert preview.get("recommended_next_step"), preview
        assert isinstance(preview.get("related_layers"), list), preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("active_investigation_context"), dict), preview
        assert preview.get("active_investigation_context", {}).get("active_task"), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("real_action_performed") is False, preview
        assert preview.get("real_file_write_performed") is False, preview
        assert preview.get("real_memory_write_performed") is False, preview
        assert preview.get("real_db_write_performed") is False, preview

        return "investigation timeline preview"

    def check_knowledge_extractor_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/knowledge-extractor-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "24.4", status
        assert status.get("name") == "Knowledge Extractor Preview", status
        assert status.get("status") == "knowledge_extractor_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("real_action_performed") is False, status
        assert status.get("real_file_write_performed") is False, status
        assert status.get("real_memory_write_performed") is False, status
        assert status.get("real_db_write_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/knowledge-extractor-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "24.4", registry
        assert registry.get("name") == "Knowledge Extractor Registry", registry
        assert registry.get("status") == "knowledge_registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert registry.get("knowledge_item_count", 0) >= 1, registry
        assert isinstance(registry.get("knowledge_items"), list), registry

        preview_response = client.post(
            "/debug/knowledge-extractor-preview",
            json={
                "issue_title": "ARM Stop Continue",
                "resolution_summary": "duplicate resume branch kaldirildi",
                "command": "ARM stop continue",
                "related_layer": "Layer 23",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("issue_title") == "ARM Stop Continue", preview
        assert preview.get("resolution_summary"), preview
        assert isinstance(preview.get("lessons_learned"), list), preview
        assert preview.get("lessons_learned"), preview
        assert "duplicate_branch_check" in preview.get("recommended_future_checks", []), preview
        assert "resume_flow" in preview.get("related_patterns", []), preview
        assert isinstance(preview.get("recommended_layers"), list), preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("timeline_source_preview"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("real_action_performed") is False, preview
        assert preview.get("real_file_write_performed") is False, preview
        assert preview.get("real_memory_write_performed") is False, preview
        assert preview.get("real_db_write_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "resolved"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        resolved = report.get("sections", {}).get("resolved_issues", [])
        assert resolved, report
        assert isinstance(resolved[0].get("knowledge_extraction"), dict), report
        assert resolved[0]["knowledge_extraction"].get("lessons_learned") is not None, report

        return "knowledge extractor preview"

    def check_repeated_pattern_detector_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/repeated-pattern-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "24.5", status
        assert status.get("name") == "Repeated Pattern Detector Preview", status
        assert status.get("status") == "repeated_pattern_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("real_action_performed") is False, status
        assert status.get("real_file_write_performed") is False, status
        assert status.get("real_memory_write_performed") is False, status
        assert status.get("real_db_write_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status
        supported = set(status.get("supported_patterns", []))
        assert {"duplicate_branch", "state_source_conflict", "event_leak"} <= supported, status

        registry_response = client.get("/debug/repeated-pattern-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "24.5", registry
        assert registry.get("name") == "Repeated Pattern Detector Registry", registry
        assert registry.get("status") == "repeated_pattern_registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert registry.get("pattern_count", 0) >= 10, registry
        assert isinstance(registry.get("patterns"), list), registry

        preview_response = client.post(
            "/debug/repeated-pattern-preview",
            json={
                "pattern_name": "duplicate_branch",
                "command": "dur devam duplicate branch",
                "issue_title": "Dur/Devam sistemi",
                "related_layer": "Layer 23",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("pattern_name") == "duplicate_branch", preview
        assert preview.get("occurrence_count", 0) >= 1, preview
        assert isinstance(preview.get("related_issues"), list), preview
        assert isinstance(preview.get("related_layers"), list), preview
        assert preview.get("risk_trend"), preview
        assert preview.get("recommended_attention_level") in {"low", "medium", "high"}, preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("timeline_signal_preview"), dict), preview
        assert isinstance(preview.get("knowledge_signal_preview"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("real_action_performed") is False, preview
        assert preview.get("real_file_write_performed") is False, preview
        assert preview.get("real_memory_write_performed") is False, preview
        assert preview.get("real_db_write_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "resolved"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        repeated = report.get("sections", {}).get("repeated_patterns", [])
        assert repeated, report
        assert repeated[0].get("pattern_name"), report

        return "repeated pattern detector preview"

    def check_investigation_starter_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/investigation-starter-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "24.6", status
        assert status.get("name") == "Suggested Investigation Starter Preview", status
        assert status.get("status") == "investigation_starter_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("real_action_performed") is False, status
        assert status.get("real_file_write_performed") is False, status
        assert status.get("real_memory_write_performed") is False, status
        assert status.get("real_db_write_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/investigation-starter-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "24.6", registry
        assert registry.get("name") == "Suggested Investigation Starter Registry", registry
        assert registry.get("status") == "investigation_starter_registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert registry.get("starter_count", 0) >= 1, registry
        assert isinstance(registry.get("starters"), list), registry

        preview_response = client.post(
            "/debug/investigation-starter-preview",
            json={
                "issue_title": "stop_continue",
                "symptom": "continue only works once",
                "command": "dur devam tekrar bozuluyor",
                "related_layer": "Layer 23",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("issue_title") == "stop_continue", preview
        assert "root_flow_audit" in preview.get("recommended_starting_checks", []), preview
        assert "ARM Stop Continue" in preview.get("similar_previous_issues", []), preview
        assert "Layer 23" in preview.get("recommended_layers", []), preview
        assert "duplicate_branch" in preview.get("recommended_patterns_to_check", []), preview
        assert "app.py" in preview.get("recommended_files", []), preview
        tests_text = " ".join(str(item).lower() for item in preview.get("recommended_tests", []))
        assert "10 maddelik liste" in tests_text, preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("pattern_signal_preview"), dict), preview
        assert isinstance(preview.get("knowledge_signal_preview"), dict), preview
        assert isinstance(preview.get("timeline_signal_preview"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("real_action_performed") is False, preview
        assert preview.get("real_file_write_performed") is False, preview
        assert preview.get("real_memory_write_performed") is False, preview
        assert preview.get("real_db_write_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "resolved"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        starters = report.get("sections", {}).get("investigation_starters", [])
        assert starters, report
        assert starters[0].get("recommended_starting_checks"), report

        return "investigation starter preview"

    def check_investigation_priority_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/investigation-priority-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "24.7", status
        assert status.get("name") == "Investigation Priority Engine Preview", status
        assert status.get("status") == "investigation_priority_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("real_action_performed") is False, status
        assert status.get("real_file_write_performed") is False, status
        assert status.get("real_memory_write_performed") is False, status
        assert status.get("real_db_write_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status
        assert {"critical", "high", "medium", "low"} <= set(status.get("priority_categories", [])), status

        registry_response = client.get("/debug/investigation-priority-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "24.7", registry
        assert registry.get("name") == "Investigation Priority Registry", registry
        assert registry.get("status") == "investigation_priority_registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert registry.get("priority_item_count", 0) >= 1, registry
        assert isinstance(registry.get("priority_items"), list), registry

        preview_response = client.post(
            "/debug/investigation-priority-preview",
            json={
                "issue_title": "stop_continue",
                "symptom": "continue only works once",
                "command": "dur devam tekrar bozuluyor",
                "related_layer": "Layer 23",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("issue_title") == "stop_continue", preview
        assert preview.get("priority_score", 0) >= 90, preview
        assert preview.get("priority_level") == "critical", preview
        assert preview.get("reasoning_summary"), preview
        assert preview.get("recommended_order") == 1, preview
        assert preview.get("risk_score", 0) > 0, preview
        assert preview.get("impact_score", 0) > 0, preview
        assert preview.get("frequency_score", 0) > 0, preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("criteria_scores"), dict), preview
        assert isinstance(preview.get("repeated_pattern_signal"), dict), preview
        assert isinstance(preview.get("investigation_starter_signal"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("real_action_performed") is False, preview
        assert preview.get("real_file_write_performed") is False, preview
        assert preview.get("real_memory_write_performed") is False, preview
        assert preview.get("real_db_write_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        priorities = report.get("sections", {}).get("priority_engine", [])
        assert priorities, report
        assert priorities[0].get("priority_score") is not None, report
        assert priorities[0].get("priority_level"), report

        return "investigation priority preview"

    def check_task_planner_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/task-planner-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "24.8", status
        assert status.get("name") == "Investigation Task Planner Preview", status
        assert status.get("status") == "task_planner_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("real_action_performed") is False, status
        assert status.get("real_file_write_performed") is False, status
        assert status.get("real_memory_write_performed") is False, status
        assert status.get("real_db_write_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/task-planner-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "24.8", registry
        assert registry.get("name") == "Investigation Task Planner Registry", registry
        assert registry.get("status") == "task_planner_registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert registry.get("plan_count", 0) >= 1, registry
        assert isinstance(registry.get("plans"), list), registry

        preview_response = client.post(
            "/debug/task-planner-preview",
            json={
                "issue_title": "stop_continue",
                "symptom": "continue only works once",
                "command": "dur devam tekrar bozuluyor",
                "related_layer": "Layer 23",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("issue_title") == "stop_continue", preview
        assert preview.get("priority_level") == "critical", preview
        assert "root_flow_audit" in preview.get("recommended_task_order", []), preview
        assert "manual_scenario_test" in preview.get("recommended_task_order", []), preview
        assert preview.get("recommended_checks"), preview
        assert preview.get("recommended_tests"), preview
        assert preview.get("recommended_layers"), preview
        assert preview.get("estimated_complexity") == "medium", preview
        assert preview.get("recommended_codex_usage") == "only_if_manual_tests_fail", preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("priority_signal"), dict), preview
        assert isinstance(preview.get("starter_signal"), dict), preview
        assert isinstance(preview.get("knowledge_signal"), dict), preview
        assert isinstance(preview.get("pattern_signal"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("real_action_performed") is False, preview
        assert preview.get("real_file_write_performed") is False, preview
        assert preview.get("real_memory_write_performed") is False, preview
        assert preview.get("real_db_write_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        plans = report.get("sections", {}).get("task_plans", [])
        assert plans, report
        assert plans[0].get("recommended_task_order"), report
        assert plans[0].get("recommended_codex_usage"), report

        return "task planner preview"

    def check_dev_agent_explorer_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/dev-agent-explorer-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "25.1", status
        assert status.get("name") == "Dev Agent Explorer Preview", status
        assert status.get("status") == "dev_agent_explorer_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/dev-agent-explorer-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "25.1", registry
        assert registry.get("name") == "Dev Agent Explorer Registry", registry
        assert registry.get("status") == "dev_agent_explorer_registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("strict_read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert registry.get("area_count", 0) >= 1, registry
        assert isinstance(registry.get("project_areas"), list), registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry

        preview_response = client.post(
            "/debug/dev-agent-explorer-preview",
            json={
                "project_area": "stop_continue",
                "command": "dur devam arm typewriter iliskisi",
                "related_layer": "Layer 24",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("project_area") == "stop_continue", preview
        assert "ARM" in preview.get("known_components", []), preview
        assert "Layer 24" in preview.get("known_layers", []), preview
        assert "/debug/root-flow-audit" in preview.get("known_endpoints", []), preview
        assert preview.get("known_relationships"), preview
        assert "app.py" in preview.get("suggested_entry_points", []), preview
        assert preview.get("complexity_score") == "medium", preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("task_planner_signal"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("repo_scan_performed") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        explorer = report.get("sections", {}).get("dev_agent_explorer", [])
        assert explorer, report
        assert explorer[0].get("known_components"), report
        assert explorer[0].get("suggested_entry_points"), report

        return "dev agent explorer preview"

    def check_dependency_mapper_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/dependency-mapper-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "25.2", status
        assert status.get("name") == "Dependency Mapper Preview", status
        assert status.get("status") == "dependency_mapper_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("real_file_scan_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/dependency-mapper-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "25.2", registry
        assert registry.get("name") == "Dependency Mapper Registry", registry
        assert registry.get("status") == "dependency_mapper_registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("strict_read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert registry.get("mapping_count", 0) >= 1, registry
        assert isinstance(registry.get("dependency_mappings"), list), registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry
        assert registry.get("safety_flags", {}).get("real_file_scan") is False, registry

        preview_response = client.post(
            "/debug/dependency-mapper-preview",
            json={
                "component_name": "stop_continue",
                "command": "dur devam arm typewriter bagimliliklari",
                "related_layer": "Layer 24",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("component_name") == "stop_continue", preview
        assert "ARM" in preview.get("related_components", []), preview
        assert "Layer 24" in preview.get("related_layers", []), preview
        assert "/debug/root-flow-audit" in preview.get("related_endpoints", []), preview
        assert "resume_flow" in preview.get("related_behaviors", []), preview
        assert preview.get("dependency_risk") == "medium", preview
        assert preview.get("complexity_score") == "medium", preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("explorer_signal"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("real_file_scan_performed") is False, preview
        assert preview.get("repo_scan_performed") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        dependency_map = report.get("sections", {}).get("dependency_map", [])
        assert dependency_map, report
        assert dependency_map[0].get("related_components"), report
        assert dependency_map[0].get("related_behaviors"), report
        assert dependency_map[0].get("dependency_risk"), report

        return "dependency mapper preview"

    def check_impact_analyzer_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/impact-analyzer-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "25.3", status
        assert status.get("name") == "Impact Analyzer Preview", status
        assert status.get("status") == "impact_analyzer_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("real_file_scan_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/impact-analyzer-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "25.3", registry
        assert registry.get("name") == "Impact Analyzer Registry", registry
        assert registry.get("status") == "impact_analyzer_registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("strict_read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert registry.get("impact_item_count", 0) >= 1, registry
        assert isinstance(registry.get("impact_items"), list), registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry
        assert registry.get("safety_flags", {}).get("real_file_scan") is False, registry

        preview_response = client.post(
            "/debug/impact-analyzer-preview",
            json={
                "target_component": "stop_continue",
                "command": "dur devam arm typewriter etkisi",
                "related_layer": "Layer 24",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("target_component") == "stop_continue", preview
        assert "ARM" in preview.get("potentially_affected_components", []), preview
        assert "Layer 24" in preview.get("potentially_affected_layers", []), preview
        assert "/debug/root-flow-audit" in preview.get("potentially_affected_endpoints", []), preview
        assert "resume_flow" in preview.get("potentially_affected_behaviors", []), preview
        assert preview.get("impact_risk") == "medium", preview
        assert preview.get("recommended_caution_level") == "high", preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("dependency_signal"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("real_file_scan_performed") is False, preview
        assert preview.get("repo_scan_performed") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        impact = report.get("sections", {}).get("impact_analysis", [])
        assert impact, report
        assert impact[0].get("potentially_affected_components"), report
        assert impact[0].get("potentially_affected_behaviors"), report
        assert impact[0].get("impact_risk"), report
        assert impact[0].get("recommended_caution_level"), report

        return "impact analyzer preview"

    def check_change_boundary_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/change-boundary-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "25.4", status
        assert status.get("name") == "Safe Change Boundary Preview", status
        assert status.get("status") == "change_boundary_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status
        assert {"open", "protected", "critical", "restricted"} <= set(status.get("boundary_levels", [])), status
        assert "stop_continue" in status.get("critical_areas", []), status

        registry_response = client.get("/debug/change-boundary-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "25.4", registry
        assert registry.get("name") == "Safe Change Boundary Registry", registry
        assert registry.get("status") == "change_boundary_registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("strict_read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert registry.get("boundary_count", 0) >= 1, registry
        assert isinstance(registry.get("boundaries"), list), registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry

        preview_response = client.post(
            "/debug/change-boundary-preview",
            json={
                "target_area": "stop_continue",
                "command": "dur devam core runtime boundary",
                "related_layer": "Layer 25",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("target_area") == "stop_continue", preview
        assert preview.get("boundary_level") == "protected", preview
        assert preview.get("user_approval_required") is True, preview
        assert preview.get("criticality_level") == "high", preview
        assert "analysis" in preview.get("allowed_actions", []), preview
        assert "auto_patch" in preview.get("blocked_actions", []), preview
        assert preview.get("risk_reason"), preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("impact_signal"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("repo_scan_performed") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        boundaries = report.get("sections", {}).get("change_boundary", [])
        assert boundaries, report
        assert boundaries[0].get("boundary_level"), report
        assert boundaries[0].get("criticality_level"), report
        assert boundaries[0].get("blocked_actions"), report

        return "change boundary preview"

    def check_patch_planner_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/patch-planner-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "25.5", status
        assert status.get("name") == "Safe Patch Planner Preview", status
        assert status.get("status") == "patch_planner_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/patch-planner-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "25.5", registry
        assert registry.get("name") == "Safe Patch Planner Registry", registry
        assert registry.get("status") == "patch_planner_registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("strict_read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert registry.get("plan_count", 0) >= 1, registry
        assert isinstance(registry.get("patch_plans"), list), registry
        assert registry.get("safety_flags", {}).get("patch_apply") is False, registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry

        preview_response = client.post(
            "/debug/patch-planner-preview",
            json={
                "target_issue": "stop_continue",
                "command": "dur devam resume flow patch plan",
                "related_layer": "Layer 25",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("target_issue") == "stop_continue", preview
        assert "resume_flow" in preview.get("recommended_change_areas", []), preview
        assert preview.get("recommended_patch_scope") == "small", preview
        assert preview.get("risk_assessment") == "medium", preview
        assert "smoke_check" in preview.get("required_tests", []), preview
        assert "py_compile" in preview.get("required_tests", []), preview
        assert "root_flow_audit" in preview.get("recommended_validation_steps", []), preview
        assert preview.get("approval_required") is True, preview
        assert preview.get("estimated_complexity") == "medium", preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("boundary_signal"), dict), preview
        assert isinstance(preview.get("impact_signal"), dict), preview
        assert isinstance(preview.get("dependency_signal"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("repo_scan_performed") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        plans = report.get("sections", {}).get("patch_plans", [])
        assert plans, report
        assert plans[0].get("recommended_change_areas"), report
        assert plans[0].get("required_tests"), report
        assert plans[0].get("approval_required") is not None, report

        return "patch planner preview"

    def check_verification_planner_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/verification-planner-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "25.6", status
        assert status.get("name") == "Verification Planner Preview", status
        assert status.get("status") == "verification_planner_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/verification-planner-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "25.6", registry
        assert registry.get("name") == "Verification Planner Registry", registry
        assert registry.get("status") == "verification_planner_registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("strict_read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert registry.get("plan_count", 0) >= 1, registry
        assert isinstance(registry.get("verification_plans"), list), registry
        assert registry.get("safety_flags", {}).get("test_execution") is False, registry
        assert registry.get("safety_flags", {}).get("patch_apply") is False, registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry

        preview_response = client.post(
            "/debug/verification-planner-preview",
            json={
                "target_issue": "stop_continue",
                "command": "dur devam resume flow verification plan",
                "related_layer": "Layer 25",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("target_issue") == "stop_continue", preview
        assert "smoke_check" in preview.get("recommended_smoke_tests", []), preview
        assert "py_compile" in preview.get("recommended_smoke_tests", []), preview
        manual = " ".join(str(item).lower() for item in preview.get("recommended_manual_tests", []))
        assert "3. maddede dur" in manual, preview
        assert "tekrar devam et" in manual, preview
        assert "resume_flow" in preview.get("recommended_regression_checks", []), preview
        assert "liste kaldigi yerden tamamlanmali" in preview.get("success_criteria", []), preview
        assert preview.get("estimated_validation_effort") == "medium", preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("patch_plan_signal"), dict), preview
        assert isinstance(preview.get("boundary_signal"), dict), preview
        assert isinstance(preview.get("impact_signal"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("test_execution_performed") is False, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("repo_scan_performed") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        plans = report.get("sections", {}).get("verification_plans", [])
        assert plans, report
        assert plans[0].get("recommended_smoke_tests"), report
        assert plans[0].get("recommended_manual_tests"), report
        assert plans[0].get("success_criteria"), report

        return "verification planner preview"

    def check_dev_agent_readiness_snapshot(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/dev-agent-readiness-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "25.7", status
        assert status.get("name") == "Dev Agent Readiness Snapshot", status
        assert status.get("status") == "dev_agent_foundation_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("completed_layers") == ["25.1", "25.2", "25.3", "25.4", "25.5", "25.6"], status
        assert "exploration" in status.get("available_capabilities", []), status
        assert "verification_planning" in status.get("available_capabilities", []), status
        assert "constitution_engine" in status.get("missing_capabilities", []), status
        assert status.get("readiness_score") == 78, status
        assert status.get("safe_for_patch_planning") is True, status
        assert status.get("safe_for_write_operations") is False, status
        assert status.get("recommended_next_layer") == "layer_26_multi_agent_system", status
        assert status.get("confidence_score", 0) > 0, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/dev-agent-readiness-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "25.7", registry
        assert registry.get("name") == "Dev Agent Readiness Registry", registry
        assert registry.get("status") == "dev_agent_readiness_registry_ready", registry
        assert len(registry.get("component_statuses", [])) == 6, registry
        gates = registry.get("readiness_gates", {})
        assert gates.get("patch_planning_ready") is True, registry
        assert gates.get("verification_planning_ready") is True, registry
        assert gates.get("write_operations_ready") is False, registry
        assert registry.get("safety_flags", {}).get("patch_apply") is False, registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry

        layer25_response = client.get("/debug/layer25-status")
        assert layer25_response.status_code == 200, layer25_response.text
        layer25 = layer25_response.json()
        assert layer25.get("layer25_status") == "foundation_complete", layer25
        assert layer25.get("can_plan_patches") is True, layer25
        assert layer25.get("can_apply_patches") is False, layer25
        assert layer25.get("can_modify_code") is False, layer25
        assert layer25.get("can_commit") is False, layer25
        assert layer25.get("can_push") is False, layer25
        assert layer25.get("can_deploy") is False, layer25
        assert layer25.get("next_recommended_layer") == "layer_26_multi_agent_system", layer25

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        readiness = report.get("sections", {}).get("dev_agent_readiness", {})
        assert readiness.get("readiness_score") == 78, report
        assert readiness.get("safe_for_patch_planning") is True, report
        assert readiness.get("safe_for_write_operations") is False, report
        assert "verification_planning" in readiness.get("available_capabilities", []), report

        return "dev agent readiness snapshot"

    def check_agent_constitution_engine_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/constitution-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "26.1", status
        assert status.get("name") == "Agent Constitution Engine Preview", status
        assert status.get("status") == "constitution_engine_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert len(status.get("hierarchy", [])) == 6, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/constitution-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "26.1", registry
        assert registry.get("name") == "Agent Constitution Registry", registry
        assert registry.get("status") == "constitution_registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("strict_read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert registry.get("default_resolution", {}).get("selected_rule") == "read_only_mode", registry
        assert registry.get("safety_flags", {}).get("file_write") is False, registry
        assert registry.get("safety_flags", {}).get("patch_apply") is False, registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry

        preview_response = client.post(
            "/debug/constitution-preview",
            json={
                "command": "modify chat runtime but strict read only mode",
                "target_area": "chat",
                "conflicting_rules": ["modify_chat_runtime", "read_only_mode"],
                "rule_source": "project_rules",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("rule_source") == "constitution_rules", preview
        assert preview.get("rule_priority") == 1, preview
        assert "modify_chat_runtime" in preview.get("conflicting_rules", []), preview
        assert "read_only_mode" in preview.get("conflicting_rules", []), preview
        assert preview.get("selected_rule") in {"read_only_mode", "protect_runtime"}, preview
        assert preview.get("resolution_reason") in {"constitution_read_only_boundary", "protected_runtime_boundary"}, preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("boundary_signal"), dict), preview
        assert preview.get("readiness_signal", {}).get("safe_for_write_operations") is False, preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("repo_scan_performed") is False, preview
        assert preview.get("chat_stream_touched") is False, preview
        assert preview.get("typewriter_runtime_touched") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        constitution = report.get("sections", {}).get("constitution_engine", {})
        assert constitution.get("selected_rule") in {"read_only_mode", "protect_runtime"}, report
        assert constitution.get("rule_priority") == 1, report
        assert constitution.get("hierarchy"), report

        return "agent constitution engine preview"

    def check_project_rules_loader_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/project-rules-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "26.2", status
        assert status.get("name") == "Project Rules Loader Preview", status
        assert status.get("status") == "project_rules_loader_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("real_file_read_performed") is False, status
        assert "protected_runtime" in status.get("rule_categories", []), status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/project-rules-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "26.2", registry
        assert registry.get("name") == "Project Rules Registry", registry
        assert registry.get("status") == "project_rules_registry_ready", registry
        assert registry.get("read_only") is True, registry
        assert registry.get("strict_read_only") is True, registry
        assert registry.get("analysis_only") is True, registry
        assert registry.get("real_file_read_performed") is False, registry
        categories = {item.get("project_rule_category") for item in registry.get("rules", [])}
        assert "protected_runtime" in categories, registry
        assert "required_tests" in categories, registry
        assert registry.get("safety_flags", {}).get("real_file_read") is False, registry
        assert registry.get("safety_flags", {}).get("patch_apply") is False, registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry

        preview_response = client.post(
            "/debug/project-rules-preview",
            json={
                "command": "protect chat stream websocket typewriter stop continue",
                "project_rule_category": "protected_runtime",
                "target_area": "stop_continue",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("project_rule_category") == "protected_runtime", preview
        assert preview.get("rule_name") == "stop_continue_protection", preview
        assert preview.get("rule_priority") == "high", preview
        assert "chat" in preview.get("protected_areas", []), preview
        assert "stream" in preview.get("protected_areas", []), preview
        assert "smoke_check" in preview.get("required_checks", []), preview
        assert "manual_scenario" in preview.get("required_checks", []), preview
        assert "auto_patch" in preview.get("blocked_actions", []), preview
        assert "auto_commit" in preview.get("blocked_actions", []), preview
        assert isinstance(preview.get("constitution_signal"), dict), preview
        assert preview.get("constitution_signal", {}).get("selected_rule") in {"read_only_mode", "protect_runtime"}, preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("real_file_read_performed") is False, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("repo_scan_performed") is False, preview
        assert preview.get("chat_stream_touched") is False, preview
        assert preview.get("typewriter_runtime_touched") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        rules = report.get("sections", {}).get("project_rules", [])
        assert rules, report
        first_rule = rules[0]
        assert first_rule.get("project_rule_category"), report
        assert first_rule.get("protected_areas"), report
        assert first_rule.get("required_checks"), report
        assert first_rule.get("blocked_actions"), report

        return "project rules loader preview"

    def check_explorer_agent_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/explorer-agent-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "26.3", status
        assert status.get("name") == "Explorer Agent Preview", status
        assert status.get("status") == "explorer_agent_preview_ready", status
        assert status.get("agent_role") == "explorer", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert "exploration" in status.get("allowed_capabilities", []), status
        assert "relationship_mapping" in status.get("allowed_capabilities", []), status
        assert "patch_generation" in status.get("blocked_capabilities", []), status
        assert "commit" in status.get("blocked_capabilities", []), status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("test_execution_enabled") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/explorer-agent-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "26.3", registry
        assert registry.get("name") == "Explorer Agent Registry", registry
        assert registry.get("status") == "explorer_agent_registry_ready", registry
        assert registry.get("agent_role") == "explorer", registry
        assert registry.get("role_contract", {}).get("can_explore") is True, registry
        assert registry.get("role_contract", {}).get("can_write_code") is False, registry
        assert registry.get("role_contract", {}).get("can_generate_patch") is False, registry
        assert registry.get("role_contract", {}).get("can_run_tests") is False, registry
        assert registry.get("safety_flags", {}).get("real_repo_scan") is False, registry
        assert registry.get("safety_flags", {}).get("patch_apply") is False, registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry

        preview_response = client.post(
            "/debug/explorer-agent-preview",
            json={
                "command": "stop continue arm typewriter iliskilerini kesfet",
                "project_area": "stop_continue",
                "related_layer": "Layer 26",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("agent_role") == "explorer", preview
        assert "exploration" in preview.get("allowed_capabilities", []), preview
        assert "entry_point_suggestion" in preview.get("allowed_capabilities", []), preview
        assert "patch_generation" in preview.get("blocked_capabilities", []), preview
        assert "test_execution" in preview.get("blocked_capabilities", []), preview
        assert preview.get("recommended_entry_points"), preview
        assert preview.get("recommended_related_systems"), preview
        assert preview.get("investigation_focus") == "resume_flow_dependency_analysis", preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("constitution_signal"), dict), preview
        assert isinstance(preview.get("project_rules_signal"), dict), preview
        assert isinstance(preview.get("explorer_signal"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("repo_scan_performed") is False, preview
        assert preview.get("test_execution_performed") is False, preview
        assert preview.get("chat_stream_touched") is False, preview
        assert preview.get("typewriter_runtime_touched") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        explorer = report.get("sections", {}).get("explorer_agent", {})
        assert explorer.get("agent_role") == "explorer", report
        assert explorer.get("allowed_capabilities"), report
        assert explorer.get("blocked_capabilities"), report
        assert explorer.get("recommended_entry_points"), report
        assert explorer.get("investigation_focus"), report

        return "explorer agent preview"

    def check_planner_agent_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/planner-agent-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "26.4", status
        assert status.get("name") == "Planner Agent Preview", status
        assert status.get("status") == "planner_agent_preview_ready", status
        assert status.get("agent_role") == "planner", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert "task_planning" in status.get("allowed_capabilities", []), status
        assert "risk_analysis" in status.get("allowed_capabilities", []), status
        assert "validation_planning" in status.get("allowed_capabilities", []), status
        assert "patch_execution" in status.get("blocked_capabilities", []), status
        assert "test_execution" in status.get("blocked_capabilities", []), status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("test_execution_enabled") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/planner-agent-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "26.4", registry
        assert registry.get("name") == "Planner Agent Registry", registry
        assert registry.get("status") == "planner_agent_registry_ready", registry
        assert registry.get("agent_role") == "planner", registry
        assert registry.get("role_contract", {}).get("can_create_solution_plan") is True, registry
        assert registry.get("role_contract", {}).get("can_apply_patch") is False, registry
        assert registry.get("role_contract", {}).get("can_run_tests") is False, registry
        assert registry.get("role_contract", {}).get("can_commit") is False, registry
        assert registry.get("safety_flags", {}).get("patch_apply") is False, registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry

        preview_response = client.post(
            "/debug/planner-agent-preview",
            json={
                "command": "stop continue icin cozum plani ve dogrulama stratejisi olustur",
                "project_area": "stop_continue",
                "related_layer": "Layer 26",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("agent_role") == "planner", preview
        assert "task_planning" in preview.get("allowed_capabilities", []), preview
        assert "patch_execution" in preview.get("blocked_capabilities", []), preview
        assert "test_execution" in preview.get("blocked_capabilities", []), preview
        assert preview.get("recommended_plan"), preview
        assert preview.get("recommended_task_order"), preview
        assert isinstance(preview.get("risk_considerations"), dict), preview
        assert isinstance(preview.get("recommended_validation_strategy"), dict), preview
        assert preview.get("recommended_validation_strategy", {}).get("recommended_manual_tests"), preview
        assert isinstance(preview.get("constitution_signal"), dict), preview
        assert isinstance(preview.get("project_rules_signal"), dict), preview
        assert isinstance(preview.get("explorer_signal"), dict), preview
        assert isinstance(preview.get("patch_plan_signal"), dict), preview
        assert isinstance(preview.get("verification_signal"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("repo_scan_performed") is False, preview
        assert preview.get("test_execution_performed") is False, preview
        assert preview.get("chat_stream_touched") is False, preview
        assert preview.get("typewriter_runtime_touched") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        planner = report.get("sections", {}).get("planner_agent", {})
        assert planner.get("agent_role") == "planner", report
        assert planner.get("recommended_plan"), report
        assert planner.get("recommended_task_order"), report
        assert planner.get("risk_considerations"), report
        assert planner.get("recommended_validation_strategy"), report

        return "planner agent preview"

    def check_verifier_agent_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/verifier-agent-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "26.5", status
        assert status.get("name") == "Verifier Agent Preview", status
        assert status.get("status") == "verifier_agent_preview_ready", status
        assert status.get("agent_role") == "verifier", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert "verification_planning" in status.get("allowed_capabilities", []), status
        assert "regression_review" in status.get("allowed_capabilities", []), status
        assert "success_validation" in status.get("allowed_capabilities", []), status
        assert "patch_execution" in status.get("blocked_capabilities", []), status
        assert "test_execution" in status.get("blocked_capabilities", []), status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("test_execution_enabled") is False, status
        assert status.get("real_test_run_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/verifier-agent-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "26.5", registry
        assert registry.get("name") == "Verifier Agent Registry", registry
        assert registry.get("status") == "verifier_agent_registry_ready", registry
        assert registry.get("agent_role") == "verifier", registry
        assert registry.get("role_contract", {}).get("can_plan_verification") is True, registry
        assert registry.get("role_contract", {}).get("can_review_regressions") is True, registry
        assert registry.get("role_contract", {}).get("can_apply_patch") is False, registry
        assert registry.get("role_contract", {}).get("can_run_tests") is False, registry
        assert registry.get("safety_flags", {}).get("test_execution") is False, registry
        assert registry.get("safety_flags", {}).get("real_test_run") is False, registry

        preview_response = client.post(
            "/debug/verifier-agent-preview",
            json={
                "command": "stop continue icin dogrulama ve regresyon kontrolu yap",
                "project_area": "stop_continue",
                "related_layer": "Layer 26",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("agent_role") == "verifier", preview
        assert "verification_planning" in preview.get("allowed_capabilities", []), preview
        assert "patch_execution" in preview.get("blocked_capabilities", []), preview
        assert "test_execution" in preview.get("blocked_capabilities", []), preview
        assert preview.get("recommended_verification_steps"), preview
        assert preview.get("recommended_regression_checks"), preview
        assert preview.get("recommended_success_criteria"), preview
        assert preview.get("risk_validation_focus"), preview
        assert isinstance(preview.get("constitution_signal"), dict), preview
        assert isinstance(preview.get("project_rules_signal"), dict), preview
        assert isinstance(preview.get("planner_signal"), dict), preview
        assert isinstance(preview.get("verification_plan_signal"), dict), preview
        assert isinstance(preview.get("boundary_signal"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("test_execution_performed") is False, preview
        assert preview.get("real_test_run_performed") is False, preview
        assert preview.get("chat_stream_touched") is False, preview
        assert preview.get("typewriter_runtime_touched") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        verifier = report.get("sections", {}).get("verifier_agent", {})
        assert verifier.get("agent_role") == "verifier", report
        assert verifier.get("recommended_verification_steps"), report
        assert verifier.get("recommended_regression_checks"), report
        assert verifier.get("recommended_success_criteria"), report
        assert verifier.get("risk_validation_focus"), report

        return "verifier agent preview"

    def check_evidence_store_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/evidence-store-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "26.6", status
        assert status.get("name") == "Evidence Store Preview", status
        assert status.get("status") == "evidence_store_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("real_storage_performed") is False, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("real_data_stored") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/evidence-store-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "26.6", registry
        assert registry.get("name") == "Evidence Store Registry", registry
        assert registry.get("status") == "evidence_store_registry_ready", registry
        assert registry.get("finding_count", 0) >= 4, registry
        assert "explorer" in registry.get("related_agents", []), registry
        assert registry.get("safety_flags", {}).get("real_data_storage") is False, registry
        assert registry.get("safety_flags", {}).get("file_write") is False, registry
        assert registry.get("safety_flags", {}).get("memory_write") is False, registry

        preview_response = client.post(
            "/debug/evidence-store-preview",
            json={
                "finding": "state_source_conflict",
                "command": "stop continue state source conflict kanitlarini goster",
                "project_area": "stop_continue",
                "related_layer": "Layer 26",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("finding") == "state_source_conflict", preview
        assert preview.get("evidence_items"), preview
        assert preview.get("supporting_signals"), preview
        assert "explorer" in preview.get("related_agents", []), preview
        assert "planner" in preview.get("related_agents", []), preview
        assert "verifier" in preview.get("related_agents", []), preview
        assert preview.get("confidence_reasoning"), preview
        assert preview.get("risk_reasoning"), preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("constitution_signal"), dict), preview
        assert isinstance(preview.get("project_rules_signal"), dict), preview
        assert isinstance(preview.get("explorer_signal"), dict), preview
        assert isinstance(preview.get("planner_signal"), dict), preview
        assert isinstance(preview.get("verifier_signal"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("real_storage_performed") is False, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("real_data_stored") is False, preview
        assert preview.get("chat_stream_touched") is False, preview
        assert preview.get("typewriter_runtime_touched") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        evidence = report.get("sections", {}).get("evidence_store", {})
        assert evidence.get("finding") == "state_source_conflict", report
        assert evidence.get("evidence_items"), report
        assert evidence.get("supporting_signals"), report
        assert evidence.get("related_agents"), report
        assert evidence.get("confidence_reasoning"), report
        assert evidence.get("risk_reasoning"), report

        return "evidence store preview"

    def check_coordinator_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/coordinator-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "26.7", status
        assert status.get("name") == "Multi-Agent Coordinator Preview", status
        assert status.get("status") == "coordinator_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert "agent_output_collection" in status.get("allowed_capabilities", []), status
        assert "patch_execution" in status.get("blocked_capabilities", []), status
        assert "test_execution" in status.get("blocked_capabilities", []), status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("test_execution_enabled") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/coordinator-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "26.7", registry
        assert registry.get("name") == "Multi-Agent Coordinator Registry", registry
        assert registry.get("status") == "coordinator_registry_ready", registry
        assert "explorer" in registry.get("participating_agents", []), registry
        assert "planner" in registry.get("participating_agents", []), registry
        assert "verifier" in registry.get("participating_agents", []), registry
        assert registry.get("agent_contribution_templates", {}).get("explorer"), registry
        assert registry.get("safety_flags", {}).get("file_write") is False, registry
        assert registry.get("safety_flags", {}).get("test_execution") is False, registry

        preview_response = client.post(
            "/debug/coordinator-preview",
            json={
                "command": "stop continue icin ajan ciktilarini koordine et",
                "project_area": "stop_continue",
                "related_layer": "Layer 26",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("participating_agents") == ["explorer", "planner", "verifier"], preview
        assert preview.get("agent_contributions", {}).get("explorer"), preview
        assert preview.get("coordination_flow"), preview
        assert preview.get("combined_findings"), preview
        assert preview.get("combined_risks"), preview
        assert preview.get("combined_recommendations"), preview
        assert preview.get("overall_confidence", 0) > 0, preview
        assert isinstance(preview.get("constitution_signal"), dict), preview
        assert isinstance(preview.get("project_rules_signal"), dict), preview
        assert isinstance(preview.get("agent_status_signals"), dict), preview
        assert isinstance(preview.get("evidence_signal"), dict), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("test_execution_performed") is False, preview
        assert preview.get("chat_stream_touched") is False, preview
        assert preview.get("typewriter_runtime_touched") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        coordinator = report.get("sections", {}).get("coordinator", {})
        assert "explorer" in coordinator.get("participating_agents", []), report
        assert coordinator.get("agent_contributions"), report
        assert coordinator.get("coordination_flow"), report
        assert coordinator.get("combined_findings"), report
        assert coordinator.get("combined_risks"), report
        assert coordinator.get("combined_recommendations"), report

        return "multi-agent coordinator preview"

    def check_patch_draft_engine_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/patch-draft-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "27.1", status
        assert status.get("name") == "Patch Draft Engine Preview", status
        assert status.get("status") == "patch_draft_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("draft_only") is True, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/patch-draft-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "27.1", registry
        assert registry.get("name") == "Patch Draft Registry", registry
        assert registry.get("status") == "patch_draft_registry_ready", registry
        assert registry.get("draft_count", 0) >= 1, registry
        assert isinstance(registry.get("drafts"), list), registry
        assert registry.get("safety_flags", {}).get("file_write") is False, registry
        assert registry.get("safety_flags", {}).get("memory_write") is False, registry
        assert registry.get("safety_flags", {}).get("db_write") is False, registry
        assert registry.get("safety_flags", {}).get("git_write") is False, registry
        assert registry.get("safety_flags", {}).get("patch_apply") is False, registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry

        preview_response = client.post(
            "/debug/patch-draft-preview",
            json={
                "target_issue": "stop_continue",
                "command": "dur devam resume flow patch draft",
                "project_area": "stop_continue",
                "related_layer": "Layer 27.1",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("target_issue") == "stop_continue", preview
        assert "app.py" in preview.get("recommended_files", []), preview
        assert preview.get("draft_change_summary") == "resume flow consolidation", preview
        assert "identify duplicate owner" in preview.get("draft_patch_steps", []), preview
        assert preview.get("risk_assessment") == "medium", preview
        assert preview.get("approval_required") is True, preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("change_scope"), dict), preview
        assert isinstance(preview.get("risk_and_rationale"), dict), preview
        assert isinstance(preview.get("integration_signals"), dict), preview
        assert preview.get("integration_signals", {}).get("patch_planner"), preview
        assert preview.get("integration_signals", {}).get("evidence_store"), preview
        assert preview.get("integration_signals", {}).get("safe_change_boundary"), preview
        assert preview.get("integration_signals", {}).get("multi_agent_coordinator"), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("draft_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("repo_scan_performed") is False, preview
        assert preview.get("chat_stream_touched") is False, preview
        assert preview.get("typewriter_runtime_touched") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        patch_draft = report.get("sections", {}).get("patch_draft", [])
        assert patch_draft, report
        assert patch_draft[0].get("Hedef Sorun"), report
        assert patch_draft[0].get("Önerilen Dosyalar"), report
        assert patch_draft[0].get("Değişiklik Özeti"), report
        assert patch_draft[0].get("Taslak Adımlar"), report
        assert patch_draft[0].get("Risk"), report
        assert patch_draft[0].get("Onay Gereksinimi") is not None, report

        return "patch draft engine preview"

    def check_change_preview_engine(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/change-preview-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "27.2", status
        assert status.get("name") == "Change Preview Engine", status
        assert status.get("status") == "change_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("preview_only") is True, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/change-preview-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "27.2", registry
        assert registry.get("name") == "Change Preview Registry", registry
        assert registry.get("status") == "change_preview_registry_ready", registry
        assert registry.get("preview_count", 0) >= 1, registry
        assert isinstance(registry.get("previews"), list), registry
        assert registry.get("safety_flags", {}).get("file_write") is False, registry
        assert registry.get("safety_flags", {}).get("memory_write") is False, registry
        assert registry.get("safety_flags", {}).get("db_write") is False, registry
        assert registry.get("safety_flags", {}).get("git_write") is False, registry
        assert registry.get("safety_flags", {}).get("patch_apply") is False, registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry

        preview_response = client.post(
            "/debug/change-preview",
            json={
                "target_issue": "stop_continue",
                "command": "dur devam resume flow change preview",
                "project_area": "stop_continue",
                "related_layer": "Layer 27.2",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("target_issue") == "stop_continue", preview
        assert "resume_flow" in preview.get("affected_areas", []), preview
        assert "runtime_state" in preview.get("affected_areas", []), preview
        assert preview.get("before_summary") == "multiple resume paths", preview
        assert preview.get("after_summary") == "single owner flow", preview
        assert "reduced duplication" in preview.get("predicted_effects", []), preview
        assert "stream_runtime" in preview.get("risk_areas", []), preview
        assert preview.get("approval_required") is True, preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("integration_signals"), dict), preview
        assert preview.get("integration_signals", {}).get("patch_draft"), preview
        assert preview.get("integration_signals", {}).get("multi_agent_coordinator"), preview
        assert preview.get("integration_signals", {}).get("evidence_store"), preview
        assert preview.get("integration_signals", {}).get("safe_change_boundary"), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("preview_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("repo_scan_performed") is False, preview
        assert preview.get("chat_stream_touched") is False, preview
        assert preview.get("typewriter_runtime_touched") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        change_preview = report.get("sections", {}).get("change_preview", [])
        assert change_preview, report
        assert change_preview[0].get("Etkilenen Alanlar"), report
        assert change_preview[0].get("Önce Özeti"), report
        assert change_preview[0].get("Sonra Özeti"), report
        assert change_preview[0].get("Tahmini Etkiler"), report
        assert change_preview[0].get("Risk Alanları"), report
        assert change_preview[0].get("Onay Gereksinimi") is not None, report

        return "change preview engine"

    def check_diff_preview_engine(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/diff-preview-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "27.3", status
        assert status.get("name") == "Diff Preview Engine", status
        assert status.get("status") == "diff_preview_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("preview_only") is True, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/diff-preview-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "27.3", registry
        assert registry.get("name") == "Diff Preview Registry", registry
        assert registry.get("status") == "diff_preview_registry_ready", registry
        assert registry.get("diff_count", 0) >= 1, registry
        assert isinstance(registry.get("diffs"), list), registry
        assert registry.get("safety_flags", {}).get("file_write") is False, registry
        assert registry.get("safety_flags", {}).get("memory_write") is False, registry
        assert registry.get("safety_flags", {}).get("db_write") is False, registry
        assert registry.get("safety_flags", {}).get("git_write") is False, registry
        assert registry.get("safety_flags", {}).get("patch_apply") is False, registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry

        preview_response = client.post(
            "/debug/diff-preview",
            json={
                "target_issue": "stop_continue",
                "command": "dur devam resume flow diff preview",
                "project_area": "stop_continue",
                "related_layer": "Layer 27.3",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("target_issue") == "stop_continue", preview
        assert "app.py" in preview.get("affected_files", []), preview
        assert preview.get("before_code_summary") == "multiple resume_owner paths with scattered validation", preview
        assert preview.get("after_code_summary") == "single resume_owner path with consolidated validation", preview
        assert preview.get("diff_hunks_expected", 0) >= 1, preview
        assert "resume_flow" in preview.get("risk_areas", []), preview
        assert preview.get("approval_required") is True, preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("integration_signals"), dict), preview
        assert preview.get("integration_signals", {}).get("patch_draft"), preview
        assert preview.get("integration_signals", {}).get("change_preview"), preview
        assert preview.get("integration_signals", {}).get("multi_agent_coordinator"), preview
        assert preview.get("integration_signals", {}).get("evidence_store"), preview
        assert preview.get("integration_signals", {}).get("safe_change_boundary"), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("preview_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("repo_scan_performed") is False, preview
        assert preview.get("chat_stream_touched") is False, preview
        assert preview.get("typewriter_runtime_touched") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        diff_preview_section = report.get("sections", {}).get("diff_preview", [])
        assert diff_preview_section, report
        assert diff_preview_section[0].get("Hedef Sorun"), report
        assert diff_preview_section[0].get("Etkilenen Dosyalar"), report
        assert diff_preview_section[0].get("Önce Kod Özeti"), report
        assert diff_preview_section[0].get("Sonra Kod Özeti"), report
        assert diff_preview_section[0].get("Tahmini Hunk Sayısı"), report
        assert diff_preview_section[0].get("Risk Alanları"), report
        assert diff_preview_section[0].get("Onay Gereksinimi") is not None, report

        return "diff preview engine"

    def check_patch_risk_matrix_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/patch-risk-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "27.4", status
        assert status.get("name") == "Patch Risk Matrix Preview", status
        assert status.get("status") == "patch_risk_matrix_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("preview_only") is True, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/patch-risk-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "27.4", registry
        assert registry.get("name") == "Patch Risk Registry", registry
        assert registry.get("status") == "patch_risk_registry_ready", registry
        assert registry.get("risk_count", 0) >= 1, registry
        assert isinstance(registry.get("risks"), list), registry
        risk_summary = registry.get("risk_level_summary", {})
        assert isinstance(risk_summary.get("high"), int), registry
        assert isinstance(risk_summary.get("medium"), int), registry
        assert isinstance(risk_summary.get("low"), int), registry
        assert registry.get("safety_flags", {}).get("file_write") is False, registry
        assert registry.get("safety_flags", {}).get("memory_write") is False, registry
        assert registry.get("safety_flags", {}).get("db_write") is False, registry
        assert registry.get("safety_flags", {}).get("git_write") is False, registry
        assert registry.get("safety_flags", {}).get("patch_apply") is False, registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry

        preview_response = client.post(
            "/debug/patch-risk-preview",
            json={
                "target_issue": "stop_continue",
                "command": "dur devam resume flow patch risk",
                "project_area": "stop_continue",
                "related_layer": "Layer 27.4",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("target_issue") == "stop_continue", preview
        assert preview.get("target_component") == "resume_flow", preview
        assert "app.py" in preview.get("affected_files", []), preview
        assert "legacy_chat_runtime" in preview.get("affected_layers", []), preview
        assert "/chat" in preview.get("affected_endpoints", []), preview
        assert preview.get("risk_score", 0) >= 1, preview
        assert preview.get("risk_level") == "medium", preview
        assert "duplicate resume_owner logic" in preview.get("risk_reasons", []), preview
        assert preview.get("dependency_risk") == "low", preview
        assert preview.get("runtime_risk") == "high", preview
        assert preview.get("regression_risk") == "medium", preview
        assert preview.get("boundary_risk") == "medium", preview
        assert preview.get("verification_required") is True, preview
        assert "resume after stop via /chat" in preview.get("recommended_tests", []), preview
        assert preview.get("approval_required") is True, preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("integration_signals"), dict), preview
        assert preview.get("integration_signals", {}).get("patch_draft"), preview
        assert preview.get("integration_signals", {}).get("change_preview"), preview
        assert preview.get("integration_signals", {}).get("diff_preview"), preview
        assert preview.get("integration_signals", {}).get("multi_agent_coordinator"), preview
        assert preview.get("integration_signals", {}).get("evidence_store"), preview
        assert preview.get("integration_signals", {}).get("safe_patch_planner"), preview
        assert preview.get("integration_signals", {}).get("verification_planner"), preview
        assert preview.get("integration_signals", {}).get("safe_change_boundary"), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("preview_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("repo_scan_performed") is False, preview
        assert preview.get("chat_stream_touched") is False, preview
        assert preview.get("typewriter_runtime_touched") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        risk_section = report.get("sections", {}).get("patch_risk_matrix", [])
        assert risk_section, report
        assert risk_section[0].get("Hedef Sorun"), report
        assert risk_section[0].get("Hedef Bileşen"), report
        assert risk_section[0].get("Etkilenen Dosyalar"), report
        assert risk_section[0].get("Etkilenen Layer'lar"), report
        assert risk_section[0].get("Etkilenen Endpoint'ler"), report
        assert risk_section[0].get("Risk Skoru") is not None, report
        assert risk_section[0].get("Risk Seviyesi"), report
        assert risk_section[0].get("Risk Sebepleri"), report
        assert risk_section[0].get("Bağımlılık Riski"), report
        assert risk_section[0].get("Çalışma Zamanı Riski"), report
        assert risk_section[0].get("Regresyon Riski"), report
        assert risk_section[0].get("Sınır Riski"), report
        assert risk_section[0].get("Doğrulama Gerekli") is not None, report
        assert risk_section[0].get("Önerilen Testler"), report
        assert risk_section[0].get("Onay Gereksinimi") is not None, report

        return "patch risk matrix preview"

    def check_patch_approval_engine_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/patch-approval-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "27.5", status
        assert status.get("name") == "Patch Approval Engine Preview", status
        assert status.get("status") == "patch_approval_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("preview_only") is True, status
        assert status.get("file_write_enabled") is False, status
        assert status.get("memory_write_enabled") is False, status
        assert status.get("db_write_enabled") is False, status
        assert status.get("git_write_enabled") is False, status
        assert status.get("commit_enabled") is False, status
        assert status.get("push_enabled") is False, status
        assert status.get("deploy_enabled") is False, status
        assert status.get("auto_fix_enabled") is False, status
        assert status.get("patch_apply_enabled") is False, status
        assert status.get("subprocess_execution_enabled") is False, status
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/patch-approval-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "27.5", registry
        assert registry.get("name") == "Patch Approval Registry", registry
        assert registry.get("status") == "patch_approval_registry_ready", registry
        assert registry.get("approval_count", 0) >= 1, registry
        assert isinstance(registry.get("approvals"), list), registry
        approval_summary = registry.get("approval_level_summary", {})
        assert isinstance(approval_summary.get("strict"), int), registry
        assert isinstance(approval_summary.get("standard"), int), registry
        assert isinstance(approval_summary.get("low"), int), registry
        assert isinstance(registry.get("blocked_count"), int), registry
        assert isinstance(registry.get("human_review_count"), int), registry
        assert isinstance(registry.get("safe_to_continue_count"), int), registry
        assert registry.get("safety_flags", {}).get("file_write") is False, registry
        assert registry.get("safety_flags", {}).get("memory_write") is False, registry
        assert registry.get("safety_flags", {}).get("db_write") is False, registry
        assert registry.get("safety_flags", {}).get("git_write") is False, registry
        assert registry.get("safety_flags", {}).get("patch_apply") is False, registry
        assert registry.get("safety_flags", {}).get("subprocess_execution") is False, registry

        preview_response = client.post(
            "/debug/patch-approval-preview",
            json={
                "target_issue": "stop_continue",
                "command": "dur devam resume flow patch approval",
                "project_area": "stop_continue",
                "related_layer": "Layer 27.5",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("target_issue") == "stop_continue", preview
        assert preview.get("target_component") == "resume_flow", preview
        assert preview.get("approval_required") is True, preview
        assert preview.get("approval_level") == "standard", preview
        assert "consolidated resume_owner" in preview.get("approval_reason", ""), preview
        assert preview.get("approval_source") == "patch_risk_matrix", preview
        assert preview.get("human_review_required") is True, preview
        assert preview.get("blocked_by_boundary") is False, preview
        assert preview.get("safe_to_continue") is True, preview
        assert "resume_flow consolidation" in preview.get("recommended_next_action", ""), preview
        assert "dev_review" in preview.get("recommended_approval_path", ""), preview
        assert "resume after stop" in preview.get("required_validations", []), preview
        assert "unit: resume flow" in preview.get("required_tests", []), preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("integration_signals"), dict), preview
        assert preview.get("integration_signals", {}).get("patch_draft"), preview
        assert preview.get("integration_signals", {}).get("change_preview"), preview
        assert preview.get("integration_signals", {}).get("diff_preview"), preview
        assert preview.get("integration_signals", {}).get("patch_risk_matrix"), preview
        assert preview.get("integration_signals", {}).get("multi_agent_coordinator"), preview
        assert preview.get("integration_signals", {}).get("evidence_store"), preview
        assert preview.get("integration_signals", {}).get("verification_planner"), preview
        assert preview.get("integration_signals", {}).get("safe_patch_planner"), preview
        assert preview.get("integration_signals", {}).get("safe_change_boundary"), preview
        assert preview.get("read_only") is True, preview
        assert preview.get("strict_read_only") is True, preview
        assert preview.get("analysis_only") is True, preview
        assert preview.get("preview_only") is True, preview
        assert preview.get("file_write_performed") is False, preview
        assert preview.get("memory_write_performed") is False, preview
        assert preview.get("db_write_performed") is False, preview
        assert preview.get("git_write_performed") is False, preview
        assert preview.get("commit_performed") is False, preview
        assert preview.get("push_performed") is False, preview
        assert preview.get("deploy_performed") is False, preview
        assert preview.get("auto_fix_performed") is False, preview
        assert preview.get("patch_apply_performed") is False, preview
        assert preview.get("subprocess_execution_performed") is False, preview
        assert preview.get("repo_scan_performed") is False, preview
        assert preview.get("chat_stream_touched") is False, preview
        assert preview.get("typewriter_runtime_touched") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        approval_section = report.get("sections", {}).get("patch_approval", [])
        assert approval_section, report
        assert approval_section[0].get("Hedef Sorun"), report
        assert approval_section[0].get("Hedef Bileşen"), report
        assert approval_section[0].get("Onay Gerekli") is not None, report
        assert approval_section[0].get("Onay Seviyesi"), report
        assert approval_section[0].get("Onay Sebebi"), report
        assert approval_section[0].get("Onay Kaynağı"), report
        assert approval_section[0].get("İnsan İncelemesi Gerekli") is not None, report
        assert approval_section[0].get("Sınır Engelli") is not None, report
        assert approval_section[0].get("Devam Etmek Güvenli") is not None, report
        assert approval_section[0].get("Önerilen Sonraki Adım"), report
        assert approval_section[0].get("Önerilen Onay Yolu"), report
        assert approval_section[0].get("Gerekli Doğrulamalar"), report
        assert approval_section[0].get("Gerekli Testler"), report

        return "patch approval engine preview"

    def check_patch_execution_readiness_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/patch-execution-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "27.6", status
        assert status.get("name") == "Patch Execution Readiness Preview", status
        assert status.get("status") == "patch_execution_readiness_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        assert status.get("analysis_only") is True, status
        assert status.get("preview_only") is True, status
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled",
                     "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled",
                     "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert status.get(flag) is False, f"{flag} should be False"
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/patch-execution-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "27.6", registry
        assert registry.get("name") == "Patch Execution Readiness Registry", registry
        assert registry.get("status") == "patch_execution_registry_ready", registry
        assert registry.get("execution_count", 0) >= 1, registry
        assert isinstance(registry.get("executions"), list), registry
        go_no_go = registry.get("go_no_go_summary", {})
        assert isinstance(go_no_go.get("go"), int), registry
        assert isinstance(go_no_go.get("no_go"), int), registry
        assert isinstance(registry.get("ready_count"), int), registry
        assert isinstance(registry.get("blocked_count"), int), registry
        assert isinstance(registry.get("rollback_required_count"), int), registry
        for flag in ["file_write", "memory_write", "db_write", "git_write",
                     "commit", "push", "deploy", "auto_fix", "patch_apply", "subprocess_execution"]:
            assert registry.get("safety_flags", {}).get(flag) is False, f"safety flag {flag}"

        preview_response = client.post(
            "/debug/patch-execution-preview",
            json={
                "target_issue": "stop_continue",
                "command": "dur devam resume flow execution readiness",
                "project_area": "stop_continue",
                "related_layer": "Layer 27.6",
            },
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("target_issue") == "stop_continue", preview
        assert preview.get("target_component") == "resume_flow", preview
        assert preview.get("execution_ready") is True, preview
        assert preview.get("readiness_score", 0) >= 50, preview
        assert preview.get("go_no_go_status") == "go", preview
        assert preview.get("blockers") == [], preview
        assert "dev_review" in preview.get("required_approvals", []), preview
        assert "resume after stop" in preview.get("required_validations", []), preview
        assert "unit: resume flow" in preview.get("required_tests", []), preview
        assert preview.get("verification_ready") is True, preview
        assert preview.get("rollback_required") is False, preview
        assert "git revert" in preview.get("rollback_strategy", ""), preview
        assert "apply_patch" in preview.get("execution_path", ""), preview
        assert "proceed" in preview.get("recommended_next_action", ""), preview
        assert preview.get("confidence_score", 0) > 0, preview
        assert isinstance(preview.get("integration_signals"), dict), preview
        for sig in ["patch_draft", "change_preview", "diff_preview", "patch_risk_matrix",
                     "patch_approval", "multi_agent_coordinator", "evidence_store",
                     "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert preview.get("integration_signals", {}).get(sig), f"missing integration signal: {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed",
                     "git_write_performed", "commit_performed", "push_performed", "deploy_performed",
                     "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert preview.get(flag) is False, f"{flag} should be False"
        assert preview.get("repo_scan_performed") is False, preview
        assert preview.get("chat_stream_touched") is False, preview
        assert preview.get("typewriter_runtime_touched") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        exec_section = report.get("sections", {}).get("patch_execution_readiness", [])
        assert exec_section, report
        for field in ["Hedef Sorun", "Hedef Bileşen", "Çalıştırmaya Hazır", "Hazırlık Skoru",
                      "Go/No-Go Durumu", "Engeller", "Eksik Gereksinimler", "Gerekli Onaylar",
                      "Gerekli Doğrulamalar", "Gerekli Testler", "Doğrulama Hazır",
                      "Geri Alma Gerekli", "Geri Alma Stratejisi", "Çalıştırma Yolu",
                      "Önerilen Sonraki Adım"]:
            assert exec_section[0].get(field) is not None or exec_section[0].get(field) == [], f"missing field: {field}"

        return "patch execution readiness preview"

    def check_layer27_status_snapshot(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        response = client.get("/debug/layer27-status")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload.get("snapshot_status") == "layer_27_snapshot_ready", payload
        assert payload.get("layer_27_complete") is True, payload
        assert payload.get("layer_count") == 6, payload
        assert payload.get("endpoint_count") == 18, payload
        assert payload.get("integration_count") >= 1, payload
        implemented = payload.get("implemented_layers", [])
        assert len(implemented) == 6, payload
        for layer_name in ["27.1", "27.2", "27.3", "27.4", "27.5", "27.6"]:
            found = any(layer_name in str(item) for item in implemented)
            assert found, f"missing {layer_name} in implemented_layers"
        statuses = payload.get("layer_statuses", {})
        for layer_id in ["27.1", "27.2", "27.3", "27.4", "27.5", "27.6"]:
            assert layer_id in statuses, f"missing {layer_id}"
            assert statuses[layer_id].get("read_only") is True, f"{layer_id} not read_only"
        assert payload.get("all_read_only") is True, payload
        safety = payload.get("safety_summary", {})
        for flag in ["file_write", "memory_write", "db_write", "git_write",
                     "commit", "push", "deploy", "auto_fix", "patch_apply", "subprocess_execution"]:
            assert safety.get(flag) is False, f"safety {flag}"
        readiness = payload.get("development_readiness", {})
        assert readiness.get("all_layers_implemented") is True, payload
        assert readiness.get("all_endpoints_documented") is True, payload
        assert readiness.get("smoke_tests_implemented") is True, payload
        assert readiness.get("fault_report_integrated") is True, payload
        assert isinstance(payload.get("future_direction"), list), payload
        assert payload.get("read_only") is True, payload
        assert payload.get("chat_stream_touched") is False, payload
        assert payload.get("typewriter_runtime_touched") is False, payload

        full_response = client.get("/debug/layer27-full-status")
        assert full_response.status_code == 200, full_response.text
        full = full_response.json()
        assert full.get("layer_27_complete") is True, full
        details = full.get("full_details", {})
        for layer_id in ["27.1", "27.2", "27.3", "27.4", "27.5", "27.6"]:
            assert layer_id in details, f"missing {layer_id}"
            assert details[layer_id].get("read_only") is True
            assert isinstance(details[layer_id].get("available_endpoints"), list)
            assert isinstance(details[layer_id].get("connected_layers"), list)
        assert full.get("total_integrations_across_layers", 0) >= 6, full
        assert full.get("total_endpoints_across_layers", 0) >= 18, full

        return "layer 27 status snapshot"

    def check_safe_patch_application_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        status_response = client.get("/debug/safe-patch-status")
        assert status_response.status_code == 200, status_response.text
        status = status_response.json()
        assert status.get("layer") == "28.1", status
        assert status.get("name") == "Safe Patch Application Preview", status
        assert status.get("status") == "safe_patch_application_ready", status
        assert status.get("read_only") is True, status
        assert status.get("strict_read_only") is True, status
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled",
                     "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled",
                     "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert status.get(flag) is False, f"{flag}"
        assert status.get("repo_scan_performed") is False, status
        assert status.get("chat_stream_touched") is False, status
        assert status.get("typewriter_runtime_touched") is False, status

        registry_response = client.get("/debug/safe-patch-registry")
        assert registry_response.status_code == 200, registry_response.text
        registry = registry_response.json()
        assert registry.get("layer") == "28.1", registry
        assert registry.get("name") == "Safe Patch Application Registry", registry
        assert registry.get("status") == "safe_patch_registry_ready", registry
        assert registry.get("patch_count", 0) >= 1, registry
        assert isinstance(registry.get("patches"), list), registry
        assert isinstance(registry.get("ready_count"), int), registry
        assert isinstance(registry.get("blocked_count"), int), registry
        for flag in ["file_write", "memory_write", "db_write", "git_write",
                     "commit", "push", "deploy", "auto_fix", "patch_apply", "subprocess_execution"]:
            assert registry.get("safety_flags", {}).get(flag) is False, f"safety {flag}"

        preview_response = client.post("/debug/safe-patch-preview", json={
            "target_issue": "stop_continue",
            "command": "dur devam resume flow safe patch application",
            "project_area": "stop_continue",
            "related_layer": "Layer 28.1",
        })
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("target_issue") == "stop_continue", preview
        assert preview.get("target_component") == "resume_flow", preview
        assert preview.get("patch_plan_id") == "SP-001", preview
        assert preview.get("application_ready") is True, preview
        assert len(preview.get("application_steps", [])) >= 2, preview
        assert "app.py" in preview.get("affected_files", []), preview
        assert "resume_owner" in preview.get("affected_functions", []), preview
        assert len(preview.get("pre_checks", [])) >= 1, preview
        assert len(preview.get("post_checks", [])) >= 1, preview
        assert "git revert" in preview.get("rollback_plan", ""), preview
        assert preview.get("approval_required") is True, preview
        assert preview.get("verification_required") is True, preview
        assert preview.get("risk_level") == "medium", preview
        assert preview.get("confidence_score", 0) > 0, preview
        sigs = preview.get("integration_signals", {})
        for sig in ["patch_draft", "change_preview", "diff_preview", "patch_risk_matrix",
                     "patch_approval", "patch_execution_readiness", "multi_agent_coordinator",
                     "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed",
                     "git_write_performed", "commit_performed", "push_performed", "deploy_performed",
                     "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert preview.get(flag) is False, f"{flag}"
        assert preview.get("chat_stream_touched") is False, preview
        assert preview.get("typewriter_runtime_touched") is False, preview

        report_response = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        section = report.get("sections", {}).get("safe_patch_application", [])
        assert section, report
        for field in ["Hedef Sorun", "Hedef Bileşen", "Patch Plan ID", "Uygulamaya Hazır",
                      "Uygulama Adımları", "Etkilenen Dosyalar", "Etkilenen Fonksiyonlar",
                      "Ön Kontroller", "Son Kontroller", "Geri Alma Planı",
                      "Onay Gerekli", "Doğrulama Gerekli", "Risk Seviyesi"]:
            assert section[0].get(field) is not None or section[0].get(field) == [], f"missing {field}"

        return "safe patch application preview"

    def check_patch_rollback_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/patch-rollback-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "28.2", st
        assert st.get("name") == "Patch Rollback Preview", st
        assert st.get("status") == "patch_rollback_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled",
                     "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled",
                     "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/patch-rollback-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "28.2", rg
        assert rg.get("status") == "patch_rollback_registry_ready", rg
        assert rg.get("rollback_count", 0) >= 1, rg
        assert isinstance(rg.get("mandatory_count"), int), rg
        assert isinstance(rg.get("ready_count"), int), rg
        p = client.post("/debug/patch-rollback-preview", json={
            "target_issue": "websocket_stream", "command": "stream rollback test",
            "project_area": "websocket_stream", "related_layer": "Layer 28.2"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("target_issue") == "websocket_stream", pv
        assert pv.get("rollback_required") is True, pv
        assert pv.get("rollback_level") == "mandatory", pv
        assert "high runtime risk" in pv.get("rollback_reason", ""), pv
        assert len(pv.get("rollback_steps", [])) >= 2, pv
        assert pv.get("rollback_risk_level") == "high", pv
        assert pv.get("rollback_readiness") is False, pv
        assert pv.get("confidence_score", 0) > 0, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["safe_patch_application", "patch_execution_readiness", "patch_approval",
                     "patch_risk_matrix", "diff_preview", "change_preview", "patch_draft",
                     "multi_agent_coordinator", "evidence_store", "verification_planner",
                     "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed",
                     "git_write_performed", "commit_performed", "push_performed", "deploy_performed",
                     "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("patch_rollback", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Rollback Gerekli", "Rollback Seviyesi", "Rollback Adımları",
                     "Rollback Risk Seviyesi", "Kurtarma Planı", "Rollback Hazır"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "patch rollback preview"

    def check_patch_validation_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/patch-validation-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "28.3", st
        assert st.get("status") == "patch_validation_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled",
                     "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled",
                     "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/patch-validation-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "28.3", rg
        assert rg.get("status") == "patch_validation_registry_ready", rg
        assert rg.get("validation_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("pending_count"), int), rg
        p = client.post("/debug/patch-validation-preview", json={
            "target_issue": "websocket_stream", "command": "stream validation test",
            "project_area": "websocket_stream", "related_layer": "Layer 28.3"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("target_issue") == "websocket_stream", pv
        assert pv.get("validation_required") is True, pv
        assert pv.get("validation_status") == "blocked", pv
        assert "manual-first" in pv.get("validation_strategy", ""), pv
        assert len(pv.get("validation_steps", [])) >= 2, pv
        assert pv.get("validation_risk_level") == "high", pv
        assert len(pv.get("required_tests", [])) >= 2, pv
        assert len(pv.get("success_criteria", [])) >= 2, pv
        assert len(pv.get("failure_criteria", [])) >= 2, pv
        assert "rollback" in pv.get("rollback_trigger", ""), pv
        assert pv.get("confidence_score", 0) > 0, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["patch_rollback", "safe_patch_application", "patch_execution_readiness",
                     "patch_approval", "patch_risk_matrix", "diff_preview", "change_preview",
                     "patch_draft", "multi_agent_coordinator", "evidence_store",
                     "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed",
                     "git_write_performed", "commit_performed", "push_performed", "deploy_performed",
                     "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("patch_validation", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Doğrulama Gerekli", "Doğrulama Durumu", "Doğrulama Stratejisi",
                     "Başarı Kriterleri", "Rollback Tetikleyici"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "patch validation preview"

    def check_patch_recovery_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/patch-recovery-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "28.4", st
        assert st.get("status") == "patch_recovery_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled",
                     "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled",
                     "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/patch-recovery-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "28.4", rg
        assert rg.get("status") == "patch_recovery_registry_ready", rg
        assert rg.get("recovery_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("pending_count"), int), rg
        p = client.post("/debug/patch-recovery-preview", json={
            "target_issue": "websocket_stream", "command": "stream recovery test",
            "project_area": "websocket_stream", "related_layer": "Layer 28.4"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("target_issue") == "websocket_stream", pv
        assert pv.get("failure_type") == "runtime_stream_corruption", pv
        assert pv.get("recovery_required") is True, pv
        assert pv.get("recovery_strategy") is not None, pv
        assert len(pv.get("recovery_steps", [])) >= 2, pv
        assert pv.get("recovery_risk_level") == "high", pv
        assert pv.get("confidence_score", 0) > 0, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["patch_validation", "patch_rollback", "safe_patch_application",
                     "patch_execution_readiness", "patch_approval", "patch_risk_matrix",
                     "diff_preview", "change_preview", "patch_draft", "multi_agent_coordinator",
                     "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed",
                     "git_write_performed", "commit_performed", "push_performed", "deploy_performed",
                     "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("patch_recovery", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hata Türü", "Kurtarma Gerekli", "Kurtarma Stratejisi",
                     "Kurtarma Adımları", "Kurtarma Risk Seviyesi", "Önerilen Sonraki Adım"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "patch recovery preview"

    def check_patch_audit_trail_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/patch-audit-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "28.5", st
        assert st.get("status") == "patch_audit_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/patch-audit-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "28.5", rg
        assert rg.get("status") == "patch_audit_registry_ready", rg
        assert rg.get("audit_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("pending_count"), int), rg
        p = client.post("/debug/patch-audit-preview", json={"target_issue": "websocket_stream", "command": "stream audit test", "project_area": "websocket_stream", "related_layer": "Layer 28.5"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("target_issue") == "websocket_stream", pv
        assert pv.get("audit_id") == "websocket_stream", pv
        assert pv.get("audit_completeness") == "comprehensive", pv
        assert pv.get("audit_readiness") is True, pv
        assert len(pv.get("timeline_events", [])) >= 5, pv
        assert pv.get("confidence_score", 0) > 0, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["patch_recovery", "patch_validation", "patch_rollback", "safe_patch_application", "patch_execution_readiness", "patch_approval", "patch_risk_matrix", "diff_preview", "change_preview", "patch_draft", "multi_agent_coordinator", "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("patch_audit_trail", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hedef Bileşen", "Audit ID", "Olay Sayısı", "Etkilenen Katmanlar", "Karar Zinciri", "Denetim Hazır"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "patch audit trail preview"

    def check_patch_lifecycle_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/patch-lifecycle-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "28.6", st
        assert st.get("status") == "patch_lifecycle_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/patch-lifecycle-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "28.6", rg
        assert rg.get("status") == "patch_lifecycle_registry_ready", rg
        assert rg.get("lifecycle_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("pending_count"), int), rg
        p = client.post("/debug/patch-lifecycle-preview", json={"target_issue": "websocket_stream", "command": "stream lifecycle test", "project_area": "websocket_stream", "related_layer": "Layer 28.6"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("target_issue") == "websocket_stream", pv
        assert pv.get("lifecycle_id") == "websocket_stream", pv
        assert pv.get("current_stage") == "approval", pv
        assert pv.get("lifecycle_readiness") is False, pv
        assert pv.get("completion_score", 0) < 1.0, pv
        assert len(pv.get("completed_stages", [])) >= 2, pv
        assert len(pv.get("remaining_stages", [])) >= 2, pv
        assert pv.get("confidence_score", 0) > 0, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["patch_audit_trail", "patch_recovery", "patch_validation", "patch_rollback", "safe_patch_application", "patch_execution_readiness", "patch_approval", "patch_risk_matrix", "diff_preview", "change_preview", "patch_draft", "multi_agent_coordinator", "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("patch_lifecycle", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hedef Bileşen", "Lifecycle ID", "Mevcut Aşama", "Tamamlanan Aşamalar", "Yaşam Döngüsü Hazır", "Tamamlanma Skoru"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "patch lifecycle preview"

    def check_layer28_status_snapshot(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/layer28-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("snapshot_status") == "layer_28_snapshot_ready", st
        assert st.get("layer_28_complete") is True, st
        assert len(st.get("implemented_layers", [])) == 6, st
        assert st.get("endpoint_count", 0) >= 18, st
        assert st.get("all_read_only") is True, st
        for flag in ["file_write", "memory_write", "db_write", "git_write", "commit", "push", "deploy", "auto_fix", "patch_apply", "subprocess_execution"]:
            assert st.get("safety_summary", {}).get(flag) is False, f"safety {flag}"
        assert len(st.get("read_only_guards", [])) >= 2, st
        assert st.get("read_only") is True, st
        assert st.get("chat_stream_touched") is False, st
        assert st.get("typewriter_runtime_touched") is False, st
        f = client.get("/debug/layer28-full-status")
        assert f.status_code == 200, f.text
        ft = f.json()
        assert ft.get("snapshot_status") == "layer_28_snapshot_ready", ft
        assert "full_details" in ft, ft
        assert len(ft.get("full_details", {})) == 6, ft
        assert ft.get("total_integrations_across_layers", 0) >= 60, ft
        assert ft.get("total_endpoints_across_layers", 0) >= 18, ft
        assert ft.get("real_action_performed") is False, ft
        assert ft.get("chat_stream_touched") is False, ft
        assert ft.get("typewriter_runtime_touched") is False, ft
        return "layer 28 status snapshot"

    def check_layer29_status_snapshot(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/layer29-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("snapshot_status") == "layer_29_snapshot_ready", st
        assert st.get("layer_29_complete") is True, st
        assert len(st.get("implemented_layers", [])) == 8, st
        assert st.get("endpoint_count", 0) >= 24, st
        assert st.get("all_read_only") is True, st
        for flag in ["file_write", "memory_write", "db_write", "git_write", "commit", "push", "deploy", "auto_fix", "patch_apply", "subprocess_execution"]:
            assert st.get("safety_summary", {}).get(flag) is False, f"safety {flag}"
        assert len(st.get("read_only_guards", [])) >= 2, st
        assert st.get("read_only") is True, st
        assert st.get("chat_stream_touched") is False, st
        assert st.get("typewriter_runtime_touched") is False, st
        f = client.get("/debug/layer29-full-status")
        assert f.status_code == 200, f.text
        ft = f.json()
        assert ft.get("snapshot_status") == "layer_29_snapshot_ready", ft
        assert "full_details" in ft, ft
        assert len(ft.get("full_details", {})) == 8, ft
        assert ft.get("total_integrations_across_layers", 0) >= 130, ft
        assert ft.get("total_endpoints_across_layers", 0) >= 24, ft
        assert ft.get("real_action_performed") is False, ft
        assert ft.get("chat_stream_touched") is False, ft
        assert ft.get("typewriter_runtime_touched") is False, ft
        return "layer 29 status snapshot"

    def check_layer30_status_snapshot(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/layer30-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("snapshot_status") == "layer_30_snapshot_ready", st
        assert st.get("layer_30_complete") is True, st
        assert len(st.get("implemented_layers", [])) == 5, st
        assert st.get("endpoint_count", 0) >= 15, st
        assert st.get("all_read_only") is True, st
        for flag in ["file_write", "memory_write", "db_write", "git_write", "commit", "push", "deploy", "auto_fix", "patch_apply", "subprocess_execution"]:
            assert st.get("safety_summary", {}).get(flag) is False, f"safety {flag}"
        assert len(st.get("read_only_guards", [])) >= 2, st
        assert st.get("read_only") is True, st
        assert st.get("chat_stream_touched") is False, st
        assert st.get("typewriter_runtime_touched") is False, st
        f = client.get("/debug/layer30-full-status")
        assert f.status_code == 200, f.text
        ft = f.json()
        assert ft.get("snapshot_status") == "layer_30_snapshot_ready", ft
        assert "full_details" in ft, ft
        assert len(ft.get("full_details", {})) == 5, ft
        assert ft.get("total_integrations_across_layers", 0) >= 100, ft
        assert ft.get("total_endpoints_across_layers", 0) >= 15, ft
        assert ft.get("real_action_performed") is False, ft
        assert ft.get("chat_stream_touched") is False, ft
        assert ft.get("typewriter_runtime_touched") is False, ft
        return "layer 30 status snapshot"

    def check_production_readiness_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/production-readiness-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "30.1", st
        assert st.get("status") == "production_readiness_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/production-readiness-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "30.1", rg
        assert rg.get("status") == "production_readiness_registry_ready", rg
        assert rg.get("readiness_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        p = client.post("/debug/production-readiness-preview", json={"target_issue": "websocket_stream", "command": "stream readiness test", "project_area": "websocket_stream", "related_layer": "Layer 30.1"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("readiness_id") == "websocket_stream", pv
        assert pv.get("readiness_status") == "violation", pv
        assert pv.get("production_ready") is False, pv
        assert len(pv.get("readiness_blockers", [])) >= 1, pv
        assert len(pv.get("required_actions", [])) >= 1, pv
        assert pv.get("readiness_score", 0) < 0.5, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["layer29_status_snapshot", "patch_confidence", "patch_assurance", "patch_accountability", "patch_oversight", "patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement", "patch_lifecycle", "patch_audit_trail", "patch_recovery", "patch_validation", "patch_rollback", "safe_patch_application", "patch_execution_readiness", "patch_approval", "patch_risk_matrix", "multi_agent_coordinator", "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("production_readiness", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hedef Bileşen", "Hazırlık Kategorisi", "Hazırlık Durumu", "Hazırlık Skoru", "Gereksinimler", "Bulgular", "Engelleyiciler", "Risk Seviyesi", "Öneriler", "Üretime Hazır"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "production readiness preview"

    def check_operational_readiness_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/operational-readiness-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "30.2", st
        assert st.get("status") == "operational_readiness_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/operational-readiness-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "30.2", rg
        assert rg.get("status") == "operational_readiness_registry_ready", rg
        assert rg.get("operational_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        p = client.post("/debug/operational-readiness-preview", json={"target_issue": "websocket_stream", "command": "stream ops readiness test", "project_area": "websocket_stream", "related_layer": "Layer 30.2"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("operational_id") == "websocket_stream", pv
        assert pv.get("operational_status") == "violation", pv
        assert pv.get("operational_readiness") is False, pv
        assert len(pv.get("operational_blockers", [])) >= 1, pv
        assert len(pv.get("required_actions", [])) >= 1, pv
        assert pv.get("operational_score", 0) < 0.5, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["production_readiness", "patch_confidence", "patch_assurance", "patch_accountability", "patch_oversight", "patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement", "patch_lifecycle", "patch_audit_trail", "patch_recovery", "patch_validation", "patch_rollback", "safe_patch_application", "patch_execution_readiness", "patch_approval", "patch_risk_matrix", "multi_agent_coordinator", "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("operational_readiness", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hedef Bileşen", "Operasyonel Kategori", "Operasyonel Durum", "Operasyonel Skor", "Gereksinimler", "Bulgular", "Engelleyiciler", "Risk Seviyesi", "Öneriler", "Operasyonel Hazır"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "operational readiness preview"

    def check_system_readiness_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/system-readiness-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "30.3", st
        assert st.get("status") == "system_readiness_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/system-readiness-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "30.3", rg
        assert rg.get("status") == "system_readiness_registry_ready", rg
        assert rg.get("system_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        p = client.post("/debug/system-readiness-preview", json={"target_issue": "websocket_stream", "command": "stream system readiness test", "project_area": "websocket_stream", "related_layer": "Layer 30.3"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("system_id") == "websocket_stream", pv
        assert pv.get("system_status") == "violation", pv
        assert pv.get("system_readiness") is False, pv
        assert len(pv.get("system_blockers", [])) >= 1, pv
        assert len(pv.get("required_actions", [])) >= 1, pv
        assert pv.get("system_score", 0) < 0.5, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["operational_readiness", "production_readiness", "patch_confidence", "patch_assurance", "patch_accountability", "patch_oversight", "patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement", "patch_lifecycle", "patch_audit_trail", "patch_recovery", "patch_validation", "patch_rollback", "safe_patch_application", "patch_execution_readiness", "patch_approval", "patch_risk_matrix", "multi_agent_coordinator", "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("system_readiness", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hedef Bileşen", "Sistem Kategorisi", "Sistem Durumu", "Sistem Skoru", "Gereksinimler", "Bulgular", "Engelleyiciler", "Risk Seviyesi", "Öneriler", "Sistem Hazır"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "system readiness preview"

    def check_validation_readiness_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/validation-readiness-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "30.4", st
        assert st.get("status") == "validation_readiness_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/validation-readiness-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "30.4", rg
        assert rg.get("status") == "validation_readiness_registry_ready", rg
        assert rg.get("validation_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        p = client.post("/debug/validation-readiness-preview", json={"target_issue": "websocket_stream", "command": "stream validation readiness test", "project_area": "websocket_stream", "related_layer": "Layer 30.4"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("validation_id") == "websocket_stream", pv
        assert pv.get("validation_status") == "violation", pv
        assert pv.get("validation_readiness") is False, pv
        assert len(pv.get("validation_blockers", [])) >= 1, pv
        assert len(pv.get("required_actions", [])) >= 1, pv
        assert pv.get("validation_score", 0) < 0.5, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["system_readiness", "operational_readiness", "production_readiness", "patch_confidence", "patch_assurance", "patch_accountability", "patch_oversight", "patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement", "patch_lifecycle", "patch_audit_trail", "patch_recovery", "patch_validation", "patch_rollback", "safe_patch_application", "patch_execution_readiness", "patch_approval", "patch_risk_matrix", "multi_agent_coordinator", "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("validation_readiness", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hedef Bileşen", "Doğrulama Kategorisi", "Doğrulama Durumu", "Doğrulama Skoru", "Gereksinimler", "Bulgular", "Engelleyiciler", "Risk Seviyesi", "Öneriler", "Doğrulama Hazır"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "validation readiness preview"

    def check_release_readiness_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/release-readiness-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "30.5", st
        assert st.get("status") == "release_readiness_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/release-readiness-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "30.5", rg
        assert rg.get("status") == "release_readiness_registry_ready", rg
        assert rg.get("release_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        p = client.post("/debug/release-readiness-preview", json={"target_issue": "websocket_stream", "command": "stream release readiness test", "project_area": "websocket_stream", "related_layer": "Layer 30.5"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("release_id") == "websocket_stream", pv
        assert pv.get("release_status") == "violation", pv
        assert pv.get("release_readiness") is False, pv
        assert len(pv.get("release_blockers", [])) >= 1, pv
        assert len(pv.get("required_actions", [])) >= 1, pv
        assert pv.get("release_score", 0) < 0.5, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["validation_readiness", "system_readiness", "operational_readiness", "production_readiness", "patch_confidence", "patch_assurance", "patch_accountability", "patch_oversight", "patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement", "patch_lifecycle", "patch_audit_trail", "patch_recovery", "patch_validation", "patch_rollback", "safe_patch_application", "patch_execution_readiness", "patch_approval", "patch_risk_matrix", "multi_agent_coordinator", "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("release_readiness", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hedef Bileşen", "Sürüm Kategorisi", "Sürüm Durumu", "Sürüm Skoru", "Gereksinimler", "Bulgular", "Engelleyiciler", "Risk Seviyesi", "Öneriler", "Sürüm Hazır"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "release readiness preview"

    def check_system_health_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/system-health-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "31.1", st
        assert st.get("status") == "system_health_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/system-health-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "31.1", rg
        assert rg.get("status") == "system_health_intelligence_registry_ready", rg
        assert rg.get("health_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("overall_health_score"), float), rg
        p = client.post("/debug/system-health-preview", json={"target_issue": "websocket_stream", "command": "stream health test", "project_area": "websocket_stream", "related_layer": "Layer 31.1"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("health_id") == "websocket_stream", pv
        assert pv.get("health_status") == "degraded", pv
        assert len(pv.get("health_blockers", [])) >= 1, pv
        assert len(pv.get("health_warnings", [])) >= 1, pv
        assert len(pv.get("required_actions", [])) >= 1, pv
        assert pv.get("health_score", 0) < 0.5, pv
        assert pv.get("health_risk_level") == "high", pv
        sigs = pv.get("integration_signals", {})
        for sig in ["layer30_status_snapshot", "layer29_status_snapshot", "patch_confidence", "patch_assurance", "patch_accountability", "patch_oversight", "patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("system_health_intelligence", [])
        assert sec, rep.text
        for fld in ["Hedef Bileşen", "Sağlık ID", "Sağlık Kategorisi", "Sağlık Durumu", "Sağlık Skoru", "Bulgular", "Uyarılar", "Engelleyiciler", "Risk Seviyesi", "Öneriler"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "system health intelligence preview"

    def check_runtime_stability_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/runtime-stability-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "31.2", st
        assert st.get("status") == "runtime_stability_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/runtime-stability-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "31.2", rg
        assert rg.get("status") == "runtime_stability_intelligence_registry_ready", rg
        assert rg.get("stability_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("overall_stability_score"), float), rg
        p = client.post("/debug/runtime-stability-preview", json={"target_issue": "websocket_stream", "command": "stream stability test", "project_area": "websocket_stream", "related_layer": "Layer 31.2"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("stability_id") == "websocket_stream", pv
        assert pv.get("stability_status") == "degraded", pv
        assert len(pv.get("stability_blockers", [])) >= 1, pv
        assert len(pv.get("stability_warnings", [])) >= 1, pv
        assert len(pv.get("required_actions", [])) >= 1, pv
        assert pv.get("stability_score", 0) < 0.5, pv
        assert pv.get("stability_risk_level") == "high", pv
        sigs = pv.get("runtime_signals", {})
        for sig in ["layer30_status_snapshot", "layer29_status_snapshot", "patch_confidence", "patch_assurance", "patch_accountability", "patch_oversight", "patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("runtime_stability_intelligence", [])
        assert sec, rep.text
        for fld in ["Hedef Bileşen", "Kararlılık ID", "Kararlılık Kategorisi", "Kararlılık Durumu", "Kararlılık Skoru", "Bulgular", "Uyarılar", "Engelleyiciler", "Risk Seviyesi", "Öneriler"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "runtime stability intelligence preview"

    def check_runtime_risk_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/runtime-risk-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "31.3", st
        assert st.get("status") == "runtime_risk_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/runtime-risk-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "31.3", rg
        assert rg.get("status") == "runtime_risk_intelligence_registry_ready", rg
        assert rg.get("risk_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("overall_risk_score"), float), rg
        p = client.post("/debug/runtime-risk-preview", json={"target_issue": "api_failure_risk", "command": "api risk test", "project_area": "api_failure_risk", "related_layer": "Layer 31.3"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("risk_id") == "api_failure_risk", pv
        assert pv.get("risk_status") == "degraded", pv
        assert len(pv.get("risk_blockers", [])) >= 1, pv
        assert len(pv.get("risk_warnings", [])) >= 1, pv
        assert len(pv.get("required_actions", [])) >= 1, pv
        assert pv.get("risk_score", 0) < 0.5, pv
        assert pv.get("risk_level") == "high", pv
        sigs = pv.get("risk_signals", {})
        for sig in ["layer30_status_snapshot", "layer29_status_snapshot", "patch_confidence", "patch_assurance", "patch_accountability", "patch_oversight", "patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("runtime_risk_intelligence", [])
        assert sec, rep.text
        for fld in ["Hedef Bileşen", "Risk ID", "Risk Kategorisi", "Risk Durumu", "Risk Skoru", "Bulgular", "Uyarılar", "Engelleyiciler", "Risk Seviyesi", "Öneriler"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "runtime risk intelligence preview"

    def check_runtime_drift_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/runtime-drift-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "31.4", st
        assert st.get("status") == "runtime_drift_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/runtime-drift-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "31.4", rg
        assert rg.get("status") == "runtime_drift_intelligence_registry_ready", rg
        assert rg.get("drift_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("overall_drift_score"), float), rg
        p = client.post("/debug/runtime-drift-preview", json={"target_issue": "config_drift", "command": "config drift test", "project_area": "config_drift", "related_layer": "Layer 31.4"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("drift_id") == "config_drift", pv
        assert pv.get("drift_status") == "warning", pv
        assert len(pv.get("drift_warnings", [])) >= 1, pv
        assert pv.get("drift_score", 1) < 0.7, pv
        assert pv.get("drift_risk_level") == "medium", pv
        sigs = pv.get("drift_signals", {})
        for sig in ["layer30_status_snapshot", "layer29_status_snapshot", "patch_confidence", "patch_assurance", "patch_accountability", "patch_oversight", "patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("runtime_drift_intelligence", [])
        assert sec, rep.text
        for fld in ["Hedef Bileşen", "Sapma ID", "Sapma Kategorisi", "Sapma Durumu", "Sapma Skoru", "Bulgular", "Uyarılar", "Engelleyiciler", "Risk Seviyesi", "Öneriler"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "runtime drift intelligence preview"

    def check_runtime_recovery_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/runtime-recovery-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "31.5", st
        assert st.get("status") == "runtime_recovery_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/runtime-recovery-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "31.5", rg
        assert rg.get("status") == "runtime_recovery_intelligence_registry_ready", rg
        assert rg.get("recovery_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("overall_recovery_score"), float), rg
        p = client.post("/debug/runtime-recovery-preview", json={"target_issue": "dependency_recovery", "command": "dep recovery test", "project_area": "dependency_recovery", "related_layer": "Layer 31.5"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("recovery_id") == "dependency_recovery", pv
        assert pv.get("recovery_status") == "degraded", pv
        assert len(pv.get("recovery_blockers", [])) >= 1, pv
        assert len(pv.get("recovery_warnings", [])) >= 1, pv
        assert len(pv.get("required_actions", [])) >= 1, pv
        assert pv.get("recovery_score", 1) < 0.5, pv
        assert pv.get("recovery_risk_level") == "high", pv
        sigs = pv.get("recovery_signals", {})
        for sig in ["layer30_status_snapshot", "layer29_status_snapshot", "patch_confidence", "patch_assurance", "patch_accountability", "patch_oversight", "patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("runtime_recovery_intelligence", [])
        assert sec, rep.text
        for fld in ["Hedef Bileşen", "Kurtarma ID", "Kurtarma Kategorisi", "Kurtarma Durumu", "Kurtarma Skoru", "Bulgular", "Uyarılar", "Engelleyiciler", "Risk Seviyesi", "Öneriler"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "runtime recovery intelligence preview"

    def check_runtime_anomaly_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/runtime-anomaly-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "32.1", st
        assert st.get("status") == "runtime_anomaly_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/runtime-anomaly-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "32.1", rg
        assert rg.get("status") == "runtime_anomaly_intelligence_registry_ready", rg
        assert rg.get("anomaly_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("overall_anomaly_score"), float), rg
        p = client.post("/debug/runtime-anomaly-preview", json={"target_issue": "performance_anomaly", "command": "perf anomaly test", "project_area": "performance_anomaly", "related_layer": "Layer 32.1"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("anomaly_id") == "performance_anomaly", pv
        assert pv.get("anomaly_status") == "warning", pv
        assert pv.get("anomaly_score", 1) < 1.0, pv
        assert pv.get("anomaly_risk_level") == "medium", pv
        assert len(pv.get("anomaly_warnings", [])) >= 1, pv
        assert len(pv.get("anomaly_recommendations", [])) >= 1, pv
        sigs = pv.get("runtime_signals", {})
        for sig in ["layer31_status_snapshot", "layer30_status_snapshot", "layer29_status_snapshot", "system_health_intelligence", "runtime_stability_intelligence", "runtime_risk_intelligence", "runtime_drift_intelligence", "runtime_recovery_intelligence", "patch_confidence", "patch_assurance", "patch_accountability", "patch_oversight", "patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("runtime_anomaly_intelligence", [])
        assert sec, rep.text
        for fld in ["Hedef Bileşen", "Anomali ID", "Anomali Kategorisi", "Anomali Durumu", "Anomali Skoru", "Bulgular", "Uyarılar", "Engelleyiciler", "Risk Seviyesi", "Öneriler"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "runtime anomaly intelligence preview"

    def check_regression_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/regression-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "32.2", st
        assert st.get("status") == "regression_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/regression-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "32.2", rg
        assert rg.get("status") == "regression_intelligence_registry_ready", rg
        assert rg.get("regression_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("overall_regression_score"), float), rg
        p = client.post("/debug/regression-preview", json={"target_issue": "behavior_regression", "command": "behavior regression test", "project_area": "behavior_regression", "related_layer": "Layer 32.2"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("regression_id") == "behavior_regression", pv
        assert pv.get("regression_status") == "degraded", pv
        assert pv.get("regression_score", 1) < 1.0, pv
        assert pv.get("regression_risk_level") == "high", pv
        assert len(pv.get("regression_warnings", [])) >= 1, pv
        assert len(pv.get("regression_recommendations", [])) >= 1, pv
        sigs = pv.get("runtime_signals", {})
        for sig in ["layer32_1_anomaly_intelligence", "layer31_status_snapshot", "layer30_status_snapshot", "layer29_status_snapshot", "system_health_intelligence", "runtime_stability_intelligence", "runtime_risk_intelligence", "runtime_drift_intelligence", "runtime_recovery_intelligence", "patch_confidence", "patch_assurance", "patch_accountability", "patch_oversight", "patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("regression_intelligence", [])
        assert sec, rep.text
        for fld in ["Hedef Bileşen", "Regresyon ID", "Regresyon Kategorisi", "Regresyon Durumu", "Regresyon Skoru", "Bulgular", "Uyarılar", "Engelleyiciler", "Risk Seviyesi", "Öneriler"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "regression intelligence preview"

    def check_failure_memory_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/failure-memory-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "32.3", st
        assert st.get("status") == "failure_memory_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/failure-memory-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "32.3", rg
        assert rg.get("status") == "failure_memory_intelligence_registry_ready", rg
        assert rg.get("failure_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("overall_failure_score"), float), rg
        assert isinstance(rg.get("overall_failure_risk_level"), str), rg
        p = client.post("/debug/failure-memory-preview", json={"target_issue": "connection_failure", "command": "conn failure test", "project_area": "connection_failure", "related_layer": "Layer 32.3"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("failure_id") == "connection_failure", pv
        assert pv.get("failure_status") == "degraded", pv
        assert pv.get("failure_score", 1) < 1.0, pv
        assert pv.get("failure_risk_level") == "high", pv
        assert len(pv.get("failure_patterns", [])) >= 1, pv
        assert len(pv.get("similar_failures", [])) >= 1, pv
        assert len(pv.get("successful_resolutions", [])) >= 1, pv
        assert len(pv.get("failed_resolutions", [])) >= 1, pv
        sigs = pv.get("runtime_signals", {})
        for sig in ["layer32_2_regression_intelligence", "layer32_1_anomaly_intelligence", "layer31_status_snapshot", "layer30_status_snapshot", "layer29_status_snapshot"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("failure_memory_intelligence", [])
        assert sec, rep.text
        for fld in ["Hedef Bileşen", "Hata ID", "Hata Kategorisi", "Hata Durumu", "Hata Skoru", "Bulgular", "Tekrar Eden Desenler", "Tekrarlama Seviyesi", "Risk Seviyesi", "Hata Özeti"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "failure memory intelligence preview"

    def check_dependency_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/dependency-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "32.5", st
        assert st.get("status") == "dependency_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/dependency-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "32.5", rg
        assert rg.get("status") == "dependency_intelligence_registry_ready", rg
        assert rg.get("dependency_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("overall_dependency_score"), float), rg
        p = client.post("/debug/dependency-preview", json={"target_issue": "file_dependency", "command": "file dep test", "project_area": "file_dependency", "related_layer": "Layer 32.5"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("dependency_id") == "file_dependency", pv
        assert pv.get("dependency_status") == "warning", pv
        assert pv.get("dependency_score", 1) < 1.0, pv
        assert pv.get("dependency_risk_level") == "medium", pv
        assert len(pv.get("affected_files", [])) >= 1, pv
        assert len(pv.get("affected_modules", [])) >= 1, pv
        assert len(pv.get("affected_systems", [])) >= 1, pv
        assert len(pv.get("triggered_systems", [])) >= 1, pv
        assert len(pv.get("impacted_by_systems", [])) >= 1, pv
        sigs = pv.get("runtime_signals", {})
        for sig in ["layer32_3_failure_memory_intelligence", "layer32_2_regression_intelligence", "layer32_1_anomaly_intelligence", "layer31_status_snapshot", "layer30_status_snapshot"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("dependency_intelligence", [])
        assert sec, rep.text
        for fld in ["Hedef Bileşen", "Bağımlılık ID", "Bağımlılık Kategorisi", "Bağımlılık Türü", "Bağımlılık Durumu", "Bağımlılık Skoru", "Etkilenen Dosyalar", "Etkilenen Modüller", "Etkilenen Sistemler"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "dependency intelligence preview"

    def check_root_cause_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/root-cause-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "32.4", st
        assert st.get("status") == "root_cause_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/root-cause-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "32.4", rg
        assert rg.get("status") == "root_cause_intelligence_registry_ready", rg
        assert rg.get("root_cause_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("overall_root_cause_score"), float), rg
        p = client.post("/debug/root-cause-preview", json={"target_issue": "dependency_root_cause", "command": "root cause test", "project_area": "dependency_root_cause", "related_layer": "Layer 32.4"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("root_cause_id") == "dependency_root_cause", pv
        assert pv.get("root_cause_status") == "degraded", pv
        assert pv.get("root_cause_score", 1) < 1.0, pv
        assert pv.get("root_cause_risk_level") == "high", pv
        assert len(pv.get("root_cause_findings", [])) >= 1, pv
        assert len(pv.get("probable_causes", [])) >= 1, pv
        assert len(pv.get("contributing_factors", [])) >= 1, pv
        assert len(pv.get("dependency_links", [])) >= 1, pv
        assert len(pv.get("trigger_chain", [])) >= 1, pv
        sigs = pv.get("runtime_signals", {})
        for sig in ["layer32_5_dependency_intelligence", "layer32_3_failure_memory_intelligence", "layer32_2_regression_intelligence", "layer32_1_anomaly_intelligence", "layer31_status_snapshot", "layer30_status_snapshot", "layer29_status_snapshot"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("root_cause_intelligence", [])
        assert sec, rep.text
        for fld in ["Kök Neden ID", "Kök Neden Kategorisi", "Kök Neden Durumu", "Kök Neden Skoru", "Bulgular", "Olası Nedenler", "Katkıda Bulunan Faktörler", "Bağımlılık Bağlantıları", "Tetikleyici Zinciri"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "root cause intelligence preview"

    def check_change_memory_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/change-memory-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "33.1", st
        assert st.get("status") == "change_memory_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/change-memory-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "33.1", rg
        assert rg.get("status") == "change_memory_intelligence_registry_ready", rg
        assert rg.get("change_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("overall_change_score"), float), rg
        p = client.post("/debug/change-memory-preview", json={"target_issue": "repair_change", "command": "change memory test", "project_area": "repair_change", "related_layer": "Layer 33.1"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("change_id") == "repair_change", pv
        assert pv.get("change_status") == "warning", pv
        assert pv.get("change_score", 1) < 1.0, pv
        assert pv.get("change_risk_level") == "medium", pv
        assert len(pv.get("change_patterns", [])) >= 1, pv
        assert len(pv.get("similar_changes", [])) >= 1, pv
        sigs = pv.get("runtime_signals", {})
        for sig in ["layer32_5_dependency_intelligence", "layer32_4_root_cause_intelligence", "layer32_3_failure_memory_intelligence", "layer32_2_regression_intelligence", "layer32_1_anomaly_intelligence", "layer31_status_snapshot", "layer30_status_snapshot", "layer29_status_snapshot"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("change_memory_intelligence", [])
        assert sec, rep.text
        for fld in ["Değişiklik ID", "Değişiklik Kategorisi", "Değişiklik Türü", "Değişiklik Durumu", "Değişiklik Skoru", "Bulgular", "Desenler", "Benzer Değişiklikler"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "change memory intelligence preview"

    def check_failed_change_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/failed-change-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "33.2", st
        assert st.get("status") == "failed_change_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/failed-change-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "33.2", rg
        assert rg.get("status") == "failed_change_intelligence_registry_ready", rg
        assert rg.get("failed_change_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("overall_failed_change_score"), float), rg
        ld = rg.get("loop_detection_summary", {})
        assert isinstance(ld.get("total_loops"), int), rg
        p = client.post("/debug/failed-change-preview", json={"target_issue": "repair_failure", "command": "failed change test", "project_area": "repair_failure", "related_layer": "Layer 33.2"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("failed_change_id") == "repair_failure", pv
        assert pv.get("failed_change_status") == "degraded", pv
        assert pv.get("failed_change_score", 1) < 1.0, pv
        assert pv.get("failure_risk_level") == "high", pv
        assert len(pv.get("failed_change_patterns", [])) >= 1, pv
        assert len(pv.get("repeated_failures", [])) >= 1, pv
        assert len(pv.get("avoidance_recommendations", [])) >= 1, pv
        sigs = pv.get("runtime_signals", {})
        for sig in ["layer33_1_change_memory_intelligence", "layer32_5_dependency_intelligence", "layer32_4_root_cause_intelligence", "layer32_3_failure_memory_intelligence", "layer32_2_regression_intelligence", "layer32_1_anomaly_intelligence", "layer31_status_snapshot", "layer30_status_snapshot", "layer29_status_snapshot"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("failed_change_intelligence", [])
        assert sec, rep.text
        for fld in ["Başarısız Değişiklik ID", "Başarısız Değişiklik Kategorisi", "Başarısız Değişiklik Türü", "Başarısız Değişiklik Durumu", "Başarısız Değişiklik Skoru", "Bulgular", "Başarısız Desenler", "Benzer Başarısızlıklar"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "failed change intelligence preview"

    def check_change_planning_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/change-planning-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "33.3", st
        assert st.get("status") == "change_planning_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/change-planning-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "33.3", rg
        assert rg.get("status") == "change_planning_intelligence_registry_ready", rg
        assert rg.get("plan_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("overall_plan_score"), float), rg
        p = client.post("/debug/change-planning-preview", json={"target_issue": "repair_plan", "command": "planning test", "project_area": "repair_plan", "related_layer": "Layer 33.3"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("plan_id") == "repair_plan", pv
        assert pv.get("plan_status") == "degraded", pv
        assert pv.get("plan_score", 1) < 1.0, pv
        assert pv.get("estimated_risk") == "high", pv
        assert len(pv.get("recommended_strategy", "")) > 10, pv
        assert len(pv.get("alternative_strategies", [])) >= 1, pv
        assert len(pv.get("avoided_strategies", [])) >= 1, pv
        assert len(pv.get("validation_steps", [])) >= 1, pv
        assert len(pv.get("required_files", [])) >= 1, pv
        sigs = pv.get("runtime_signals", {})
        for sig in ["layer33_2_failed_change_intelligence", "layer33_1_change_memory_intelligence", "layer32_5_dependency_intelligence", "layer32_4_root_cause_intelligence", "layer32_3_failure_memory_intelligence", "layer32_2_regression_intelligence", "layer32_1_anomaly_intelligence", "layer31_status_snapshot", "layer30_status_snapshot", "layer29_status_snapshot"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("change_planning_intelligence", [])
        assert sec, rep.text
        for fld in ["Plan ID", "Plan Türü", "Plan Durumu", "Plan Skoru", "Önerilen Strateji", "Alternatif Stratejiler", "Kaçınılacak Stratejiler"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "change planning intelligence preview"

    def check_clone_workspace_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/clone-workspace-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "33.4", st
        assert st.get("status") == "clone_workspace_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/clone-workspace-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "33.4", rg
        assert rg.get("status") == "clone_workspace_intelligence_registry_ready", rg
        assert rg.get("workspace_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("avg_sync_score"), float), rg
        assert isinstance(rg.get("avg_integrity_score"), float), rg
        p = client.post("/debug/clone-workspace-preview", json={"target_issue": "master_clone_sync", "command": "clone test", "project_area": "master_clone_sync", "related_layer": "Layer 33.4"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("workspace_id") == "master_clone_sync", pv
        assert pv.get("workspace_status") == "warning", pv
        assert pv.get("sync_score", 1) > 0, pv
        assert pv.get("clone_integrity_score", 1) > 0, pv
        assert pv.get("clone_health_score", 1) > 0, pv
        sigs = pv.get("runtime_signals", {})
        for sig in ["layer33_3_change_planning_intelligence", "layer33_2_failed_change_intelligence", "layer33_1_change_memory_intelligence", "layer32_5_dependency_intelligence", "layer32_4_root_cause_intelligence"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("clone_workspace_intelligence", [])
        assert sec, rep.text
        for fld in ["Çalışma Alanı ID", "Çalışma Alanı Türü", "Çalışma Alanı Durumu", "Ana Klon Durumu", "Çalışma Klonu Durumu", "Senkronizasyon Durumu", "Senkronizasyon Skoru"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "clone workspace intelligence preview"

    def check_sandbox_repair_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/sandbox-repair-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "33.5", st
        assert st.get("status") == "sandbox_repair_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/sandbox-repair-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "33.5", rg
        assert rg.get("status") == "sandbox_repair_intelligence_registry_ready", rg
        assert rg.get("repair_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("overall_repair_score"), float), rg
        assert isinstance(rg.get("avg_sandbox_integrity"), float), rg
        p = client.post("/debug/sandbox-repair-preview", json={"target_issue": "repair_change", "command": "sandbox repair test", "project_area": "repair_change", "related_layer": "Layer 33.5"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("repair_id") == "repair_change", pv
        assert pv.get("repair_status") == "degraded", pv
        assert pv.get("repair_score", 1) < 1.0, pv
        assert pv.get("repair_risk_level") == "high", pv
        assert len(pv.get("repair_steps", [])) >= 1, pv
        sigs = pv.get("runtime_signals", {})
        for sig in ["layer33_4_clone_workspace_intelligence", "layer33_3_change_planning_intelligence", "layer33_2_failed_change_intelligence", "layer33_1_change_memory_intelligence", "layer32_5_dependency_intelligence", "layer32_4_root_cause_intelligence"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("sandbox_repair_intelligence", [])
        assert sec, rep.text
        for fld in ["Onarım ID", "Onarım Türü", "Onarım Durumu", "Onarım Skoru", "Strateji", "Adımlar", "Çalışma Klonu Durumu", "Sandbox Durumu"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "sandbox repair intelligence preview"

    def check_verification_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/verification-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "33.6", st
        assert st.get("status") == "verification_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/verification-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "33.6", rg
        assert rg.get("status") == "verification_intelligence_registry_ready", rg
        assert rg.get("verification_count", 0) >= 1, rg
        assert isinstance(rg.get("pass_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("overall_verification_score"), float), rg
        assert isinstance(rg.get("all_gates_passed_count"), int), rg
        p = client.post("/debug/verification-preview", json={"target_issue": "sandbox_verification", "command": "verification test", "project_area": "sandbox_verification", "related_layer": "Layer 33.6"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("verification_id") == "sandbox_verification", pv
        assert pv.get("verification_status") == "pass", pv
        assert pv.get("verification_score", 1) > 0, pv
        assert pv.get("verification_risk_level") == "low", pv
        sigs = pv.get("runtime_signals", {})
        for sig in ["layer33_5_sandbox_repair_intelligence", "layer33_4_clone_workspace_intelligence", "layer33_3_change_planning_intelligence", "layer33_2_failed_change_intelligence", "layer33_1_change_memory_intelligence", "layer32_5_dependency_intelligence", "layer32_4_root_cause_intelligence"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("verification_intelligence", [])
        assert sec, rep.text
        for fld in ["Doğrulama ID", "Doğrulama Türü", "Doğrulama Durumu", "Doğrulama Skoru", "Özet", "Sandbox Doğrulama", "Bağımlılık Doğrulama", "Entegrasyon Doğrulama"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "verification intelligence preview"

    def check_delivery_readiness_intelligence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/delivery-readiness-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "33.7", st
        assert st.get("status") == "delivery_readiness_intelligence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/delivery-readiness-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "33.7", rg
        assert rg.get("status") == "delivery_readiness_intelligence_registry_ready", rg
        assert rg.get("delivery_count", 0) >= 1, rg
        assert isinstance(rg.get("overall_delivery_score"), float), rg
        p = client.post("/debug/delivery-readiness-preview", json={"target_issue": "ready", "command": "delivery test", "project_area": "ready", "related_layer": "Layer 33.7"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("delivery_id") == "ready", pv
        assert pv.get("delivery_status") == "ready", pv
        assert pv.get("delivery_score", 1) > 0, pv
        assert pv.get("delivery_risk_level") == "low", pv
        assert len(pv.get("release_blockers", [])) == 0, pv
        sigs = pv.get("runtime_signals", {})
        for sig in ["layer33_6_verification_intelligence", "layer33_5_sandbox_repair_intelligence", "layer33_4_clone_workspace_intelligence", "layer33_3_change_planning_intelligence", "layer33_2_failed_change_intelligence", "layer33_1_change_memory_intelligence"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("delivery_readiness_intelligence", [])
        assert sec, rep.text
        for fld in ["Teslimat ID", "Teslimat Durumu", "Teslimat Skoru", "Özet", "Güven", "Risk Seviyesi", "Hazırlık"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "delivery readiness intelligence preview"

    def check_layer31_status_snapshot(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/layer31-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("snapshot_status") == "layer_31_snapshot_ready", st
        assert st.get("layer_31_complete") is True, st
        assert st.get("layer_count") == 5, st
        assert st.get("endpoint_count", 0) >= 17, st
        assert st.get("overall_runtime_score", 0) > 0, st
        assert isinstance(st.get("health_summary"), str), st
        for key in ["health_summary", "stability_summary", "risk_summary", "drift_summary", "recovery_summary"]:
            assert isinstance(st.get(key), str), f"missing {key}"
        ff = client.get("/debug/layer31-full-status")
        assert ff.status_code == 200, ff.text
        ffj = ff.json()
        assert "full_details" in ffj, ffj
        for lid in ["31.1", "31.2", "31.3", "31.4", "31.5"]:
            assert lid in ffj.get("full_details", {}), f"missing {lid}"
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("layer31_status_snapshot", [])
        assert sec, rep.text
        for fld in ["Genel Runtime Skoru", "Genel Runtime Durumu", "Sağlık Skoru", "Stabilite Skoru", "Risk Skoru", "Sapma Skoru", "Kurtarma Skoru"]:
            assert sec[0].get(fld) is not None, f"missing {fld}"
        return "layer 31 status snapshot"

    def check_layer32_status_snapshot(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/layer32-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("snapshot_status") == "layer_32_snapshot_ready", st
        assert st.get("layer_32_complete") is True, st
        assert st.get("layer_count") == 5, st
        assert st.get("endpoint_count", 0) >= 17, st
        assert st.get("overall_layer32_score", 0) > 0, st
        assert isinstance(st.get("anomaly_summary"), str), st
        for key in ["anomaly_summary", "regression_summary", "failure_memory_summary", "root_cause_summary", "dependency_summary"]:
            assert isinstance(st.get(key), str), f"missing {key}"
        ff = client.get("/debug/layer32-full-status")
        assert ff.status_code == 200, ff.text
        ffj = ff.json()
        assert "full_details" in ffj, ffj
        for lid in ["32.1", "32.2", "32.3", "32.4", "32.5"]:
            assert lid in ffj.get("full_details", {}), f"missing {lid}"
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("layer32_status_snapshot", [])
        assert sec, rep.text
        for fld in ["Genel Layer32 Skoru", "Genel Layer32 Durumu", "Anomali Skoru", "Regresyon Skoru", "Hata Hafıza Skoru", "Kök Neden Skoru", "Bağımlılık Skoru"]:
            assert sec[0].get(fld) is not None, f"missing {fld}"
        return "layer 32 status snapshot"

    def check_patch_permission_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/patch-permission-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "29.1", st
        assert st.get("status") == "patch_permission_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/patch-permission-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "29.1", rg
        assert rg.get("status") == "patch_permission_registry_ready", rg
        assert rg.get("permission_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("pending_count"), int), rg
        p = client.post("/debug/patch-permission-preview", json={"target_issue": "websocket_stream", "command": "stream permission test", "project_area": "websocket_stream", "related_layer": "Layer 29.1"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("permission_level") == "elevated", pv
        assert pv.get("permission_readiness") is False, pv
        assert len(pv.get("allowed_actions", [])) >= 3, pv
        assert len(pv.get("blocked_actions", [])) >= 3, pv
        assert pv.get("confidence_score", 0) > 0, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["patch_lifecycle", "patch_audit_trail", "patch_recovery", "patch_validation", "patch_rollback", "safe_patch_application", "patch_execution_readiness", "patch_approval", "patch_risk_matrix", "diff_preview", "change_preview", "patch_draft", "multi_agent_coordinator", "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("patch_permission_enforcement", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hedef Bileşen", "İzin Seviyesi", "İzin Verilenler", "Engellenenler", "İzin Risk Seviyesi", "İzin Hazır"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "patch permission preview"

    def check_patch_policy_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/patch-policy-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "29.2", st
        assert st.get("status") == "patch_policy_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/patch-policy-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "29.2", rg
        assert rg.get("status") == "patch_policy_registry_ready", rg
        assert rg.get("policy_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("pending_count"), int), rg
        p = client.post("/debug/patch-policy-preview", json={"target_issue": "websocket_stream", "command": "stream policy test", "project_area": "websocket_stream", "related_layer": "Layer 29.2"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("policy_id") == "websocket_stream", pv
        assert pv.get("policy_category") == "runtime_stream_mutation", pv
        assert pv.get("policy_result") == "block", pv
        assert pv.get("policy_readiness") is False, pv
        assert len(pv.get("policy_requirements", [])) >= 2, pv
        assert pv.get("confidence_score", 0) > 0, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["patch_permission_enforcement", "patch_lifecycle", "patch_audit_trail", "patch_recovery", "patch_validation", "patch_rollback", "safe_patch_application", "patch_execution_readiness", "patch_approval", "patch_risk_matrix", "diff_preview", "change_preview", "patch_draft", "multi_agent_coordinator", "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("patch_policy_evaluation", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hedef Bileşen", "Politika Kategorisi", "Politika Sonucu", "Politika Sebebi", "Politika Risk Seviyesi", "Politika Hazır"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "patch policy preview"

    def check_patch_compliance_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/patch-compliance-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "29.3", st
        assert st.get("status") == "patch_compliance_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/patch-compliance-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "29.3", rg
        assert rg.get("status") == "patch_compliance_registry_ready", rg
        assert rg.get("compliance_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("pending_count"), int), rg
        p = client.post("/debug/patch-compliance-preview", json={"target_issue": "websocket_stream", "command": "stream compliance test", "project_area": "websocket_stream", "related_layer": "Layer 29.3"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("compliance_id") == "websocket_stream", pv
        assert pv.get("compliance_status") == "violation", pv
        assert pv.get("compliance_readiness") is False, pv
        assert len(pv.get("compliance_violations", [])) >= 1, pv
        assert len(pv.get("required_actions", [])) >= 1, pv
        assert pv.get("confidence_score", 0) > 0, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["patch_policy_evaluation", "patch_permission_enforcement", "patch_lifecycle", "patch_audit_trail", "patch_recovery", "patch_validation", "patch_rollback", "safe_patch_application", "patch_execution_readiness", "patch_approval", "patch_risk_matrix", "diff_preview", "change_preview", "patch_draft", "multi_agent_coordinator", "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("patch_compliance", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hedef Bileşen", "Uyum Kategorisi", "Uyum Durumu", "Uyum Gereksinimleri", "Uyum İhlalleri", "Uyum Risk Seviyesi", "Uyum Hazır"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "patch compliance preview"

    def check_patch_governance_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/patch-governance-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "29.4", st
        assert st.get("status") == "patch_governance_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/patch-governance-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "29.4", rg
        assert rg.get("status") == "patch_governance_registry_ready", rg
        assert rg.get("governance_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("pending_count"), int), rg
        p = client.post("/debug/patch-governance-preview", json={"target_issue": "websocket_stream", "command": "stream governance test", "project_area": "websocket_stream", "related_layer": "Layer 29.4"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("governance_id") == "websocket_stream", pv
        assert pv.get("governance_status") == "violation", pv
        assert pv.get("governance_readiness") is False, pv
        assert len(pv.get("governance_controls", [])) >= 1, pv
        assert len(pv.get("required_actions", [])) >= 1, pv
        assert pv.get("confidence_score", 0) > 0, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement", "patch_lifecycle", "patch_audit_trail", "patch_recovery", "patch_validation", "patch_rollback", "safe_patch_application", "patch_execution_readiness", "patch_approval", "patch_risk_matrix", "diff_preview", "change_preview", "patch_draft", "multi_agent_coordinator", "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("patch_governance", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hedef Bileşen", "Yönetişim Kategorisi", "Yönetişim Durumu", "Yönetişim Gereksinimleri", "Yönetişim Kontrolleri", "Yönetişim Risk Seviyesi", "Yönetişim Hazır"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "patch governance preview"

    def check_patch_oversight_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/patch-oversight-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "29.5", st
        assert st.get("status") == "patch_oversight_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/patch-oversight-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "29.5", rg
        assert rg.get("status") == "patch_oversight_registry_ready", rg
        assert rg.get("oversight_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("pending_count"), int), rg
        p = client.post("/debug/patch-oversight-preview", json={"target_issue": "websocket_stream", "command": "stream oversight test", "project_area": "websocket_stream", "related_layer": "Layer 29.5"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("oversight_id") == "websocket_stream", pv
        assert pv.get("oversight_status") == "violation", pv
        assert pv.get("oversight_readiness") is False, pv
        assert len(pv.get("oversight_controls", [])) >= 1, pv
        assert len(pv.get("required_actions", [])) >= 1, pv
        assert pv.get("confidence_score", 0) > 0, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement", "patch_lifecycle", "patch_audit_trail", "patch_recovery", "patch_validation", "patch_rollback", "safe_patch_application", "patch_execution_readiness", "patch_approval", "patch_risk_matrix", "diff_preview", "change_preview", "patch_draft", "multi_agent_coordinator", "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("patch_oversight", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hedef Bileşen", "Gözetim Kategorisi", "Gözetim Durumu", "Gözetim Bulguları", "Gözetim Kontrolleri", "Gözetim Risk Seviyesi", "Gözetim Hazır"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "patch oversight preview"

    def check_patch_accountability_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/patch-accountability-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "29.6", st
        assert st.get("status") == "patch_accountability_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/patch-accountability-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "29.6", rg
        assert rg.get("status") == "patch_accountability_registry_ready", rg
        assert rg.get("accountability_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("pending_count"), int), rg
        p = client.post("/debug/patch-accountability-preview", json={"target_issue": "websocket_stream", "command": "stream accountability test", "project_area": "websocket_stream", "related_layer": "Layer 29.6"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("accountability_id") == "websocket_stream", pv
        assert pv.get("accountability_status") == "violation", pv
        assert pv.get("accountability_readiness") is False, pv
        assert len(pv.get("accountability_findings", [])) >= 1, pv
        assert len(pv.get("required_actions", [])) >= 1, pv
        assert pv.get("confidence_score", 0) > 0, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["patch_oversight", "patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement", "patch_lifecycle", "patch_audit_trail", "patch_recovery", "patch_validation", "patch_rollback", "safe_patch_application", "patch_execution_readiness", "patch_approval", "patch_risk_matrix", "diff_preview", "change_preview", "patch_draft", "multi_agent_coordinator", "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("patch_accountability", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hedef Bileşen", "Hesap Verebilirlik Kategorisi", "Hesap Verebilirlik Durumu", "Sahip", "Kapsam", "Bulgular", "Gereksinimler", "Risk Seviyesi", "Hazır"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "patch accountability preview"

    def check_patch_assurance_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/patch-assurance-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "29.7", st
        assert st.get("status") == "patch_assurance_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/patch-assurance-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "29.7", rg
        assert rg.get("status") == "patch_assurance_registry_ready", rg
        assert rg.get("assurance_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("pending_count"), int), rg
        p = client.post("/debug/patch-assurance-preview", json={"target_issue": "websocket_stream", "command": "stream assurance test", "project_area": "websocket_stream", "related_layer": "Layer 29.7"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("assurance_id") == "websocket_stream", pv
        assert pv.get("assurance_status") == "violation", pv
        assert pv.get("assurance_readiness") is False, pv
        assert len(pv.get("assurance_findings", [])) >= 1, pv
        assert len(pv.get("required_actions", [])) >= 1, pv
        assert pv.get("confidence_score", 0) > 0, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["patch_accountability", "patch_oversight", "patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement", "patch_lifecycle", "patch_audit_trail", "patch_recovery", "patch_validation", "patch_rollback", "safe_patch_application", "patch_execution_readiness", "patch_approval", "patch_risk_matrix", "diff_preview", "change_preview", "patch_draft", "multi_agent_coordinator", "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("patch_assurance", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hedef Bileşen", "Güvence Kategorisi", "Güvence Durumu", "Kapsam", "Bulgular", "Kontroller", "Gereksinimler", "Risk Seviyesi", "Hazır", "Güvence Skoru"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "patch assurance preview"

    def check_patch_confidence_preview(self) -> str:
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        luxapp = self.patch_app_for_api()
        client = TestClient(luxapp.app)
        s = client.get("/debug/patch-confidence-status")
        assert s.status_code == 200, s.text
        st = s.json()
        assert st.get("layer") == "29.8", st
        assert st.get("status") == "patch_confidence_ready", st
        for flag in ["file_write_enabled", "memory_write_enabled", "db_write_enabled", "git_write_enabled", "commit_enabled", "push_enabled", "deploy_enabled", "auto_fix_enabled", "patch_apply_enabled", "subprocess_execution_enabled"]:
            assert st.get(flag) is False, flag
        r = client.get("/debug/patch-confidence-registry")
        assert r.status_code == 200, r.text
        rg = r.json()
        assert rg.get("layer") == "29.8", rg
        assert rg.get("status") == "patch_confidence_registry_ready", rg
        assert rg.get("confidence_count", 0) >= 1, rg
        assert isinstance(rg.get("ready_count"), int), rg
        assert isinstance(rg.get("blocked_count"), int), rg
        assert isinstance(rg.get("pending_count"), int), rg
        p = client.post("/debug/patch-confidence-preview", json={"target_issue": "websocket_stream", "command": "stream confidence test", "project_area": "websocket_stream", "related_layer": "Layer 29.8"})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv.get("confidence_id") == "websocket_stream", pv
        assert pv.get("confidence_status") == "violation", pv
        assert pv.get("confidence_readiness") is False, pv
        assert len(pv.get("confidence_findings", [])) >= 1, pv
        assert len(pv.get("required_actions", [])) >= 1, pv
        assert pv.get("confidence_score", 0) < 0.5, pv
        sigs = pv.get("integration_signals", {})
        for sig in ["patch_assurance", "patch_accountability", "patch_oversight", "patch_governance", "patch_compliance", "patch_policy_evaluation", "patch_permission_enforcement", "patch_lifecycle", "patch_audit_trail", "patch_recovery", "patch_validation", "patch_rollback", "safe_patch_application", "patch_execution_readiness", "patch_approval", "patch_risk_matrix", "diff_preview", "change_preview", "patch_draft", "multi_agent_coordinator", "evidence_store", "verification_planner", "safe_patch_planner", "safe_change_boundary"]:
            assert sig in sigs, f"missing {sig}"
        for flag in ["file_write_performed", "memory_write_performed", "db_write_performed", "git_write_performed", "commit_performed", "push_performed", "deploy_performed", "auto_fix_performed", "patch_apply_performed", "subprocess_execution_performed"]:
            assert pv.get(flag) is False, flag
        rep = client.get("/debug/fault-report-preview", params={"focus": "open"})
        assert rep.status_code == 200, rep.text
        sec = rep.json().get("sections", {}).get("patch_confidence", [])
        assert sec, rep.text
        for fld in ["Hedef Sorun", "Hedef Bileşen", "Güven Kategorisi", "Güven Durumu", "Güven Skoru", "Güven Faktörleri", "Bulgular", "Gereksinimler", "Risk Seviyesi", "Hazır", "Gerekçe"]:
            assert sec[0].get(fld) is not None or sec[0].get(fld) == [], f"missing {fld}"
        return "patch confidence preview"

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
        assert "/debug/investigation-context-status" in development_paths, payload
        assert "/debug/investigation-context-registry" in development_paths, payload
        assert "/debug/investigation-context-preview" in development_paths, payload
        assert "/debug/investigation-timeline-status" in development_paths, payload
        assert "/debug/investigation-timeline-registry" in development_paths, payload
        assert "/debug/investigation-timeline-preview" in development_paths, payload
        assert "/debug/knowledge-extractor-status" in development_paths, payload
        assert "/debug/knowledge-extractor-registry" in development_paths, payload
        assert "/debug/knowledge-extractor-preview" in development_paths, payload
        assert "/debug/repeated-pattern-status" in development_paths, payload
        assert "/debug/repeated-pattern-registry" in development_paths, payload
        assert "/debug/repeated-pattern-preview" in development_paths, payload
        assert "/debug/investigation-starter-status" in development_paths, payload
        assert "/debug/investigation-starter-registry" in development_paths, payload
        assert "/debug/investigation-starter-preview" in development_paths, payload
        assert "/debug/investigation-priority-status" in development_paths, payload
        assert "/debug/investigation-priority-registry" in development_paths, payload
        assert "/debug/investigation-priority-preview" in development_paths, payload
        assert "/debug/task-planner-status" in development_paths, payload
        assert "/debug/task-planner-registry" in development_paths, payload
        assert "/debug/task-planner-preview" in development_paths, payload
        dev_agent_paths = {item.get("path") for item in groups.get("dev_agent_layer_25", [])}
        assert "/debug/dev-agent-explorer-status" in dev_agent_paths, payload
        assert "/debug/dev-agent-explorer-registry" in dev_agent_paths, payload
        assert "/debug/dev-agent-explorer-preview" in dev_agent_paths, payload
        assert "/debug/dependency-mapper-status" in dev_agent_paths, payload
        assert "/debug/dependency-mapper-registry" in dev_agent_paths, payload
        assert "/debug/dependency-mapper-preview" in dev_agent_paths, payload
        assert "/debug/impact-analyzer-status" in dev_agent_paths, payload
        assert "/debug/impact-analyzer-registry" in dev_agent_paths, payload
        assert "/debug/impact-analyzer-preview" in dev_agent_paths, payload
        assert "/debug/change-boundary-status" in dev_agent_paths, payload
        assert "/debug/change-boundary-registry" in dev_agent_paths, payload
        assert "/debug/change-boundary-preview" in dev_agent_paths, payload
        assert "/debug/patch-planner-status" in dev_agent_paths, payload
        assert "/debug/patch-planner-registry" in dev_agent_paths, payload
        assert "/debug/patch-planner-preview" in dev_agent_paths, payload
        assert "/debug/verification-planner-status" in dev_agent_paths, payload
        assert "/debug/verification-planner-registry" in dev_agent_paths, payload
        assert "/debug/verification-planner-preview" in dev_agent_paths, payload
        assert "/debug/dev-agent-readiness-status" in dev_agent_paths, payload
        assert "/debug/dev-agent-readiness-registry" in dev_agent_paths, payload
        assert "/debug/layer25-status" in dev_agent_paths, payload
        multi_agent_paths = {item.get("path") for item in groups.get("multi_agent_layer_26", [])}
        assert "/debug/constitution-status" in multi_agent_paths, payload
        assert "/debug/constitution-registry" in multi_agent_paths, payload
        assert "/debug/constitution-preview" in multi_agent_paths, payload
        assert "/debug/project-rules-status" in multi_agent_paths, payload
        assert "/debug/project-rules-registry" in multi_agent_paths, payload
        assert "/debug/project-rules-preview" in multi_agent_paths, payload
        assert "/debug/explorer-agent-status" in multi_agent_paths, payload
        assert "/debug/explorer-agent-registry" in multi_agent_paths, payload
        assert "/debug/explorer-agent-preview" in multi_agent_paths, payload
        assert "/debug/planner-agent-status" in multi_agent_paths, payload
        assert "/debug/planner-agent-registry" in multi_agent_paths, payload
        assert "/debug/planner-agent-preview" in multi_agent_paths, payload
        assert "/debug/verifier-agent-status" in multi_agent_paths, payload
        assert "/debug/verifier-agent-registry" in multi_agent_paths, payload
        assert "/debug/verifier-agent-preview" in multi_agent_paths, payload
        assert "/debug/evidence-store-status" in multi_agent_paths, payload
        assert "/debug/evidence-store-registry" in multi_agent_paths, payload
        assert "/debug/evidence-store-preview" in multi_agent_paths, payload
        assert "/debug/coordinator-status" in multi_agent_paths, payload
        assert "/debug/coordinator-registry" in multi_agent_paths, payload
        assert "/debug/coordinator-preview" in multi_agent_paths, payload
        patch_draft_paths = {item.get("path") for item in groups.get("patch_draft_layer_27", [])}
        assert "/debug/patch-draft-status" in patch_draft_paths, payload
        assert "/debug/patch-draft-registry" in patch_draft_paths, payload
        assert "/debug/patch-draft-preview" in patch_draft_paths, payload
        assert "/debug/change-preview-status" in patch_draft_paths, payload
        assert "/debug/change-preview-registry" in patch_draft_paths, payload
        assert "/debug/change-preview" in patch_draft_paths, payload
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

    def check_layer37_architecture_previews(self) -> str:
        """Verify all 37.x endpoints return 200 with read-only safety flags."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)

        modules = [
            ("github-project-intelligence", "37.0"),
            ("terminal-intelligence", "37.1"),
            ("render-deployment-intelligence", "37.2"),
            ("project-intelligence-core", "37.3"),
            ("multi-project-intelligence", "37.4"),
            ("workspace-agent", "37.5"),
            ("deployment-agent", "37.6"),
            ("github-bridge-consolidation", "37.7"),
        ]

        for name, layer in modules:
            # status endpoint
            s = client.get(f"/{name}/status")
            assert s.status_code == 200, f"/{name}/status returned {s.status_code}"
            data = s.json()
            assert data.get("read_only") is True, f"/{name}/status read_only not True"
            assert data.get("real_action_enabled") is False, f"/{name}/status real_action_enabled not False"
            assert data.get("layer") == layer, f"/{name}/status layer mismatch: {data.get('layer')}"

            # capabilities endpoint
            c = client.get(f"/{name}/capabilities")
            assert c.status_code == 200, f"/{name}/capabilities returned {c.status_code}"

            # preview endpoint
            p = client.post(f"/{name}/preview", json={"command": "test command"})
            assert p.status_code == 200, f"/{name}/preview returned {p.status_code}"
            pdata = p.json()
            assert pdata.get("read_only") is True, f"/{name}/preview read_only not True"
            assert pdata.get("real_action_enabled") is False

        # layer37-status
        ls = client.get("/debug/layer37-status")
        assert ls.status_code == 200, f"/debug/layer37-status returned {ls.status_code}"
        lsdata = ls.json()
        assert lsdata.get("series_status") == "agent_architecture_preview_scaffold_implemented", lsdata
        assert lsdata.get("implemented_count", 0) >= 8, lsdata

        # agent-core capabilities + preview
        ac = client.get("/agent-core/capabilities")
        assert ac.status_code == 200
        ap = client.post("/agent-core/preview", json={"command": "test"})
        assert ap.status_code == 200
        apdata = ap.json()
        assert apdata.get("read_only") is True

        return "37.x all endpoints 200, safety flags verified"

    def check_layer38_autonomous_agent_systems_previews(self) -> str:
        """Verify all 38.x endpoints return 200 with read-only safety flags."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)

        modules = [
            ("autonomous-workflow-intelligence", "38.0"),
            ("workflow-chain-intelligence", "38.1"),
            ("workflow-orchestration-intelligence", "38.2"),
            ("autonomous-task-network-intelligence", "38.3"),
            ("autonomous-execution-planning-intelligence", "38.4"),
            ("autonomous-execution-strategy-intelligence", "38.5"),
            ("autonomous-execution-simulation-intelligence", "38.6"),
            ("autonomous-execution-decision-intelligence", "38.7"),
            ("autonomous-execution-governance-intelligence", "38.8"),
        ]
        false_safety_flags = [
            "autonomous_execution_enabled",
            "workflow_executed",
            "task_network_executed",
            "command_executed",
            "github_write_performed",
            "deployment_triggered",
        ]

        for name, layer in modules:
            s = client.get(f"/{name}/status")
            assert s.status_code == 200, f"/{name}/status returned {s.status_code}"
            data = s.json()
            assert data.get("layer") == layer, f"/{name}/status layer mismatch: {data.get('layer')}"
            assert data.get("read_only") is True, f"/{name}/status read_only not True"
            safety = data.get("safety", {})
            assert safety.get("read_only") is True, f"/{name}/status safety read_only not True"
            assert safety.get("autonomous_execution_enabled") is False

            c = client.get(f"/{name}/capabilities")
            assert c.status_code == 200, f"/{name}/capabilities returned {c.status_code}"

            p = client.post(
                f"/{name}/preview",
                json={
                    "command": "test autonomous workflow",
                    "workflow_name": "smoke",
                    "project_area": "layer38",
                    "risk_level": "medium",
                },
            )
            assert p.status_code == 200, f"/{name}/preview returned {p.status_code}"
            pdata = p.json()
            assert pdata.get("read_only") is True, f"/{name}/preview read_only not True"
            psafety = pdata.get("safety", {})
            assert psafety.get("read_only") is True, f"/{name}/preview safety read_only not True"
            for flag in false_safety_flags:
                assert psafety.get(flag) is False, f"/{name}/preview {flag} not False"

        ls = client.get("/debug/layer38-status")
        assert ls.status_code == 200, f"/debug/layer38-status returned {ls.status_code}"
        lsdata = ls.json()
        assert lsdata.get("series_status") == "autonomous_agent_systems_preview_scaffold_implemented", lsdata
        assert lsdata.get("implemented_count") == 10, lsdata
        assert lsdata.get("real_autonomous_execution_enabled") is False, lsdata

        ac = client.get("/autonomous-agent-operating-model/capabilities")
        assert ac.status_code == 200
        ap = client.post("/autonomous-agent-operating-model/preview", json={"command": "test"})
        assert ap.status_code == 200
        apdata = ap.json()
        assert apdata.get("read_only") is True
        apsafety = apdata.get("safety", {})
        for flag in false_safety_flags:
            assert apsafety.get(flag) is False, f"/autonomous-agent-operating-model/preview {flag} not False"

        return "38.x all endpoints 200, safety flags verified"

    def check_layer39_agent_runtime_systems_previews(self) -> str:
        """Verify all 39.x endpoints return 200 with read-only safety flags."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)

        modules = [
            ("agent-runtime-core", "39.0"),
            ("agent-session-runtime", "39.1"),
            ("agent-workspace-runtime", "39.2"),
            ("agent-memory-loop-runtime", "39.3"),
            ("agent-collaboration-runtime", "39.4"),
            ("agent-lifecycle-runtime", "39.5"),
            ("agent-recovery-resilience-runtime", "39.6"),
            ("agent-continuity-runtime", "39.7"),
            ("agent-runtime-consolidation", "39.8"),
        ]
        false_safety_flags = [
            "runtime_execution_enabled",
            "session_started",
            "workspace_runtime_modified",
            "memory_loop_executed",
            "collaboration_started",
            "lifecycle_transition_applied",
            "recovery_action_performed",
            "continuity_state_written",
            "command_executed",
            "github_write_performed",
            "deployment_triggered",
        ]

        for name, layer in modules:
            s = client.get(f"/{name}/status")
            assert s.status_code == 200, f"/{name}/status returned {s.status_code}"
            data = s.json()
            assert data.get("layer") == layer, f"/{name}/status layer mismatch: {data.get('layer')}"
            assert data.get("read_only") is True, f"/{name}/status read_only not True"
            safety = data.get("safety", {})
            assert safety.get("read_only") is True, f"/{name}/status safety read_only not True"
            assert safety.get("runtime_execution_enabled") is False

            c = client.get(f"/{name}/capabilities")
            assert c.status_code == 200, f"/{name}/capabilities returned {c.status_code}"

            p = client.post(
                f"/{name}/preview",
                json={
                    "command": "test runtime preview",
                    "project_area": "layer39",
                    "runtime_state": "planning",
                    "session_state": "preview",
                    "workspace_state": "ready",
                    "risk_level": "medium",
                },
            )
            assert p.status_code == 200, f"/{name}/preview returned {p.status_code}"
            pdata = p.json()
            assert pdata.get("read_only") is True, f"/{name}/preview read_only not True"
            psafety = pdata.get("safety", {})
            assert psafety.get("read_only") is True, f"/{name}/preview safety read_only not True"
            for flag in false_safety_flags:
                assert psafety.get(flag) is False, f"/{name}/preview {flag} not False"

        ls = client.get("/debug/layer39-status")
        assert ls.status_code == 200, f"/debug/layer39-status returned {ls.status_code}"
        lsdata = ls.json()
        assert lsdata.get("series_status") == "agent_runtime_systems_preview_scaffold_implemented", lsdata
        assert lsdata.get("implemented_count") == 10, lsdata
        assert lsdata.get("real_runtime_execution_enabled") is False, lsdata

        ac = client.get("/agent-runtime-master/capabilities")
        assert ac.status_code == 200
        ap = client.post("/agent-runtime-master/preview", json={"command": "test"})
        assert ap.status_code == 200
        apdata = ap.json()
        assert apdata.get("read_only") is True
        apsafety = apdata.get("safety", {})
        for flag in false_safety_flags:
            assert apsafety.get(flag) is False, f"/agent-runtime-master/preview {flag} not False"

        return "39.x all endpoints 200, safety flags verified"

    def check_layer40_agent_execution_systems_previews(self) -> str:
        """Verify all 40.x endpoints return 200 with read-only safety flags."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)

        modules = [
            ("agent-execution-core", "40.0"),
            ("agent-action-engine", "40.1"),
            ("agent-task-executor", "40.2"),
            ("agent-verification-executor", "40.3"),
            ("agent-workspace-executor", "40.4"),
            ("agent-deployment-executor", "40.5"),
            ("agent-execution-orchestrator", "40.6"),
            ("agent-execution-supervisor", "40.7"),
            ("agent-execution-recovery-coordinator", "40.8"),
        ]
        false_safety_flags = [
            "execution_enabled",
            "action_engine_enabled",
            "task_execution_performed",
            "verification_execution_performed",
            "workspace_execution_performed",
            "deployment_execution_performed",
            "orchestration_execution_performed",
            "supervisor_action_performed",
            "recovery_coordination_performed",
            "command_executed",
            "github_write_performed",
            "deployment_triggered",
        ]

        for name, layer in modules:
            s = client.get(f"/{name}/status")
            assert s.status_code == 200, f"/{name}/status returned {s.status_code}"
            data = s.json()
            assert data.get("layer") == layer, f"/{name}/status layer mismatch: {data.get('layer')}"
            assert data.get("read_only") is True, f"/{name}/status read_only not True"
            safety = data.get("safety", {})
            assert safety.get("read_only") is True, f"/{name}/status safety read_only not True"
            assert safety.get("execution_enabled") is False

            c = client.get(f"/{name}/capabilities")
            assert c.status_code == 200, f"/{name}/capabilities returned {c.status_code}"

            p = client.post(
                f"/{name}/preview",
                json={
                    "command": "test execution preview",
                    "project_area": "layer40",
                    "execution_type": "planning",
                    "target_system": "preview",
                    "risk_level": "medium",
                    "confirmation_state": "not_confirmed",
                },
            )
            assert p.status_code == 200, f"/{name}/preview returned {p.status_code}"
            pdata = p.json()
            assert pdata.get("read_only") is True, f"/{name}/preview read_only not True"
            psafety = pdata.get("safety", {})
            assert psafety.get("read_only") is True, f"/{name}/preview safety read_only not True"
            for flag in false_safety_flags:
                assert psafety.get(flag) is False, f"/{name}/preview {flag} not False"

        ls = client.get("/debug/layer40-status")
        assert ls.status_code == 200, f"/debug/layer40-status returned {ls.status_code}"
        lsdata = ls.json()
        assert lsdata.get("series_status") == "agent_execution_systems_preview_scaffold_implemented", lsdata
        assert lsdata.get("implemented_count") == 10, lsdata
        assert lsdata.get("real_execution_enabled") is False, lsdata

        ac = client.get("/agent-execution-master/capabilities")
        assert ac.status_code == 200
        ap = client.post("/agent-execution-master/preview", json={"command": "test"})
        assert ap.status_code == 200
        apdata = ap.json()
        assert apdata.get("read_only") is True
        apsafety = apdata.get("safety", {})
        for flag in false_safety_flags:
            assert apsafety.get(flag) is False, f"/agent-execution-master/preview {flag} not False"

        return "40.x all endpoints 200, safety flags verified"


    def check_layer41_autonomous_operations_systems_previews(self) -> str:
        """Verify all 41.x endpoints return 200 with read-only safety flags."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)

        modules = [
            ("autonomous-operations-core", "41.0"),
            ("autonomous-operations-planning", "41.1"),
            ("autonomous-operations-scheduling", "41.2"),
            ("autonomous-operations-monitoring", "41.3"),
            ("autonomous-operations-continuity", "41.4"),
            ("autonomous-operations-governance", "41.5"),
            ("autonomous-operations-optimization", "41.6"),
            ("autonomous-operations-orchestrator", "41.7"),
            ("autonomous-operations-supervisor", "41.8"),
        ]
        false_safety_flags = [
            "autonomous_operations_enabled",
            "operations_execution_performed",
            "operations_plan_applied",
            "schedule_created",
            "monitoring_started",
            "continuity_state_written",
            "governance_override",
            "optimization_applied",
            "orchestration_performed",
            "supervisor_action_performed",
            "command_executed",
            "github_write_performed",
            "deployment_triggered",
        ]

        for name, layer in modules:
            s = client.get(f"/{name}/status")
            assert s.status_code == 200, f"/{name}/status returned {s.status_code}"
            data = s.json()
            assert data.get("layer") == layer, f"/{name}/status layer mismatch: {data.get('layer')}"
            assert data.get("read_only") is True, f"/{name}/status read_only not True"
            safety = data.get("safety", {})
            assert safety.get("read_only") is True, f"/{name}/status safety read_only not True"
            assert safety.get("autonomous_operations_enabled") is False

            c = client.get(f"/{name}/capabilities")
            assert c.status_code == 200, f"/{name}/capabilities returned {c.status_code}"

            p = client.post(
                f"/{name}/preview",
                json={
                    "command": "test autonomous operations preview",
                    "project_area": "layer41",
                    "operations_scope": "planning",
                    "operations_state": "idle",
                    "risk_level": "medium",
                    "confirmation_state": "not_confirmed",
                },
            )
            assert p.status_code == 200, f"/{name}/preview returned {p.status_code}"
            pdata = p.json()
            assert pdata.get("read_only") is True, f"/{name}/preview read_only not True"
            psafety = pdata.get("safety", {})
            assert psafety.get("read_only") is True, f"/{name}/preview safety read_only not True"
            for flag in false_safety_flags:
                assert psafety.get(flag) is False, f"/{name}/preview {flag} not False"

        ls = client.get("/debug/layer41-status")
        assert ls.status_code == 200, f"/debug/layer41-status returned {ls.status_code}"
        lsdata = ls.json()
        assert lsdata.get("series_status") == "autonomous_operations_systems_preview_scaffold_implemented", lsdata
        assert lsdata.get("implemented_count") == 10, lsdata
        assert lsdata.get("real_autonomous_operations_enabled") is False, lsdata

        ac = client.get("/autonomous-operations-master/capabilities")
        assert ac.status_code == 200
        ap = client.post("/autonomous-operations-master/preview", json={"command": "test"})
        assert ap.status_code == 200
        apdata = ap.json()
        assert apdata.get("read_only") is True
        apsafety = apdata.get("safety", {})
        for flag in false_safety_flags:
            assert apsafety.get(flag) is False, f"/autonomous-operations-master/preview {flag} not False"

        return "41.x all endpoints 200, safety flags verified"

    def check_luxcode_master_router_read_only(self) -> str:
        """Verify LuxCode master router stays read-only and blocks real execution."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        from luxcode_master_router_preview import (
            COMMAND_ROUTING_TABLE,
            build_luxcode_master_router_preview,
        )

        client = TestClient(luxapp.app)

        schema = client.get("/luxcode-master-router/schema")
        assert schema.status_code == 200, f"/luxcode-master-router/schema returned {schema.status_code}"
        schema_data = schema.json()
        assert schema_data.get("read_only") is True, schema_data

        status = client.get("/debug/luxcode-master-router-status")
        assert status.status_code == 200, f"/debug/luxcode-master-router-status returned {status.status_code}"
        status_data = status.json()
        assert status_data.get("read_only") is True, status_data
        assert status_data.get("real_execution_blocked") is True, status_data

        confirmation_families = {
            "patch_planning",
            "workflow_planning",
            "release_readiness",
            "execution_preview",
            "rollback_assessment",
        }

        for command, expected in COMMAND_ROUTING_TABLE.items():
            preview = build_luxcode_master_router_preview(command, context="smoke")
            assert preview.get("primary_layer"), f"{command} primary_layer empty"
            assert isinstance(preview.get("recommended_preview_chain"), list), command
            assert preview.get("read_only") is True, command
            assert preview.get("real_execution_blocked") is True, command
            if expected.get("route_family") in confirmation_families:
                assert preview.get("requires_confirmation") is True, command

        endpoint_preview = client.post("/luxcode-master-router/preview", json={"command": "patch plan"})
        assert endpoint_preview.status_code == 200, f"/luxcode-master-router/preview returned {endpoint_preview.status_code}"
        endpoint_data = endpoint_preview.json()
        assert endpoint_data.get("read_only") is True, endpoint_data
        assert endpoint_data.get("real_execution_blocked") is True, endpoint_data

        unknown = build_luxcode_master_router_preview("definitely unknown router command")
        assert unknown.get("route_family") == "unknown", unknown
        assert unknown.get("primary_layer"), unknown
        assert isinstance(unknown.get("recommended_preview_chain"), list), unknown
        assert unknown.get("read_only") is True, unknown
        assert unknown.get("real_execution_blocked") is True, unknown
        assert unknown.get("requires_confirmation") is True, unknown

        return f"luxcode master router read-only verified for {len(COMMAND_ROUTING_TABLE)} commands"

    def check_lux_debug_intelligence_read_only(self) -> str:
        """Verify Lux debug intelligence core is local-first, read-only, and endpoint-backed."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        from lux_debug_intelligence_core import (
            analyze_lux_debug_request,
            get_lux_debug_schema,
            get_lux_debug_status,
        )

        client = TestClient(luxapp.app)

        schema = client.get("/lux-debug/schema")
        assert schema.status_code == 200, f"/lux-debug/schema returned {schema.status_code}"
        schema_data = schema.json()
        for flag, expected in {
            "read_only": True,
            "real_execution_blocked": True,
            "file_write_blocked": True,
            "external_api_used": False,
            "local_first": True,
        }.items():
            assert schema_data.get(flag) is expected, f"schema {flag} mismatch: {schema_data}"
        assert "issue_text" in schema_data.get("input_fields", []), schema_data
        assert "full_debug_preview" in schema_data.get("supported_modes", []), schema_data

        status = client.get("/debug/lux-debug-status")
        assert status.status_code == 200, f"/debug/lux-debug-status returned {status.status_code}"
        status_data = status.json()
        assert status_data.get("read_only") is True, status_data
        assert status_data.get("real_execution_blocked") is True, status_data
        assert status_data.get("file_write_blocked") is True, status_data
        assert status_data.get("external_api_used") is False, status_data
        assert status_data.get("local_first") is True, status_data
        assert status_data.get("patch_application_enabled") is False, status_data
        assert status_data.get("terminal_execution_enabled") is False, status_data
        assert status_data.get("github_action_enabled") is False, status_data
        assert status_data.get("deployment_enabled") is False, status_data
        assert status_data.get("env_file_access_enabled") is False, status_data

        direct_schema = get_lux_debug_schema()
        direct_status = get_lux_debug_status()
        assert direct_schema.get("read_only") is True, direct_schema
        assert direct_status.get("terminal_execution_enabled") is False, direct_status

        preview = analyze_lux_debug_request(
            issue_text="Bu hatayı bul app.py endpoint coverage smoke",
            traceback_text='File "app.py", line 1, in <module>',
            suspected_files=["app.py", ".env", "../outside.py"],
            changed_files=["endpoint_coverage_matrix.py", "scripts/smoke_check.py"],
            repository_root=str(ROOT),
            max_files=5,
            mode="full_debug_preview",
        )
        assert preview.get("read_only") is True, preview
        assert preview.get("real_execution_blocked") is True, preview
        assert preview.get("file_write_blocked") is True, preview
        assert preview.get("external_api_used") is False, preview
        assert preview.get("local_first") is True, preview
        assert preview.get("root_cause_hypotheses"), preview
        assert preview.get("patch_plan"), preview
        assert all(item.get("approval_required") is True for item in preview.get("patch_plan", [])), preview
        assert preview.get("verification_plan"), preview
        selected = {item.get("relative_path") for item in preview.get("selected_context", [])}
        assert "app.py" in selected, selected
        assert ".env" not in selected, selected
        assert any(".env" in item for item in preview.get("missing_information", [])), preview
        assert any("traversal rejected" in item for item in preview.get("missing_information", [])), preview

        endpoint_preview = client.post(
            "/lux-debug/analyze",
            json={
                "issue_text": "Bu hatayı bul route schema smoke",
                "suspected_files": ["app.py"],
                "repository_root": str(ROOT),
                "max_files": 4,
                "mode": "diagnose",
            },
        )
        assert endpoint_preview.status_code == 200, f"/lux-debug/analyze returned {endpoint_preview.status_code}"
        endpoint_data = endpoint_preview.json()
        assert endpoint_data.get("mode") == "diagnose", endpoint_data
        assert endpoint_data.get("read_only") is True, endpoint_data
        assert endpoint_data.get("real_execution_blocked") is True, endpoint_data
        assert endpoint_data.get("file_write_blocked") is True, endpoint_data
        assert endpoint_data.get("external_api_used") is False, endpoint_data
        assert endpoint_data.get("local_first") is True, endpoint_data

        fallback = analyze_lux_debug_request(issue_text="", repository_root=str(ROOT), mode="invalid")
        assert fallback.get("mode") == "full_debug_preview", fallback
        assert fallback.get("safe_next_step"), fallback
        assert fallback.get("read_only") is True, fallback

        return "lux debug intelligence read-only schema/analyze/status verified"

    def check_lux_safe_patch_draft_read_only(self) -> str:
        """Verify Safe Patch Draft Engine is local-first, read-only, and endpoint-backed."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        from lux_safe_patch_draft_engine import (
            build_safe_patch_draft,
            get_safe_patch_draft_schema,
            get_safe_patch_draft_status,
        )

        client = TestClient(luxapp.app)

        expected_flags = {
            "approval_required": True,
            "can_apply_now": False,
            "destructive_action_blocked": True,
            "file_write_blocked": True,
            "real_execution_blocked": True,
            "read_only": True,
            "external_api_used": False,
            "local_first": True,
        }

        schema = client.get("/lux-safe-patch/schema")
        assert schema.status_code == 200, f"/lux-safe-patch/schema returned {schema.status_code}"
        schema_data = schema.json()
        for flag, expected in expected_flags.items():
            assert schema_data.get(flag) is expected, f"schema {flag} mismatch: {schema_data}"
        assert "full_patch_preview" in schema_data.get("supported_modes", []), schema_data
        assert "requested_files" in schema_data.get("input_fields", []), schema_data

        status = client.get("/debug/lux-safe-patch-status")
        assert status.status_code == 200, f"/debug/lux-safe-patch-status returned {status.status_code}"
        status_data = status.json()
        for flag, expected in expected_flags.items():
            assert status_data.get(flag) is expected, f"status {flag} mismatch: {status_data}"
        assert status_data.get("target_file_write_enabled") is False, status_data
        assert status_data.get("terminal_execution_enabled") is False, status_data
        assert status_data.get("github_action_enabled") is False, status_data
        assert status_data.get("deployment_enabled") is False, status_data
        assert status_data.get("env_file_access_enabled") is False, status_data

        direct_schema = get_safe_patch_draft_schema()
        direct_status = get_safe_patch_draft_status()
        assert direct_schema.get("read_only") is True, direct_schema
        assert direct_status.get("can_apply_now") is False, direct_status

        preview = build_safe_patch_draft(
            issue_summary="Endpoint schema drift requires app coverage and targeted smoke draft",
            root_cause_hypotheses=[
                {
                    "title": "Endpoint coverage drift",
                    "related_files": ["app.py", "endpoint_coverage_matrix.py", "scripts/smoke_check.py"],
                    "evidence": ["route integration needs coverage and smoke validation"],
                }
            ],
            selected_context=[
                {"relative_path": "app.py", "line_start": 1, "line_end": 40, "reasons": ["route surface"]},
                {"relative_path": "endpoint_coverage_matrix.py", "reasons": ["coverage surface"]},
                {"relative_path": "scripts/smoke_check.py", "reasons": ["smoke surface"]},
            ],
            requested_files=["app.py", ".env", "../outside.py"],
            forbidden_files=["static/index.html", ".env"],
            repository_root=str(ROOT),
            mode="full_patch_preview",
            max_patch_files=5,
            max_hunks_per_file=2,
        )
        for flag, expected in expected_flags.items():
            assert preview.get(flag) is expected, f"preview {flag} mismatch: {preview}"
        assert preview.get("patch_steps"), preview
        assert preview.get("patch_targets"), preview
        selected = {item.get("target_file") for item in preview.get("patch_targets", [])}
        assert "app.py" in selected, selected
        assert ".env" not in selected, selected
        assert any(".env" in item.get("reason", "") for item in preview.get("blocked_items", [])), preview
        assert any("traversal rejected" in item.get("reason", "") for item in preview.get("blocked_items", [])), preview
        assert "# DRAFT ONLY" in preview.get("unified_diff_draft", ""), preview
        assert preview.get("recommended_handoff") in {"local", "codex", "gemini_cline", "whale", "human"}, preview

        endpoint_preview = client.post(
            "/lux-safe-patch/preview",
            json={
                "issue_summary": "Add endpoint coverage draft",
                "requested_files": ["app.py"],
                "repository_root": str(ROOT),
                "mode": "preview",
                "max_patch_files": 2,
            },
        )
        assert endpoint_preview.status_code == 200, f"/lux-safe-patch/preview returned {endpoint_preview.status_code}"
        endpoint_data = endpoint_preview.json()
        for flag, expected in expected_flags.items():
            assert endpoint_data.get(flag) is expected, f"endpoint {flag} mismatch: {endpoint_data}"
        assert endpoint_data.get("can_apply_now") is False, endpoint_data

        return "lux safe patch draft read-only schema/preview/status verified"

    def check_lux_controlled_apply_approval_gated(self) -> str:
        """Verify Controlled Apply Engine stays approval-gated and does not write in live smoke."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        runtime_dir = ROOT / ".luxcode_runtime"
        existed_before = runtime_dir.exists()

        schema = client.get("/lux-controlled-apply/schema")
        assert schema.status_code == 200, f"/lux-controlled-apply/schema returned {schema.status_code}"
        schema_data = schema.json()
        assert schema_data.get("default_mode") == "dry_run", schema_data
        assert schema_data.get("approval_required") is True, schema_data
        assert schema_data.get("validation_execution_blocked") is True, schema_data
        assert schema_data.get("destructive_action_blocked") is True, schema_data
        assert schema_data.get("external_api_used") is False, schema_data
        assert schema_data.get("local_first") is True, schema_data

        status = client.get("/debug/lux-controlled-apply-status")
        assert status.status_code == 200, f"/debug/lux-controlled-apply-status returned {status.status_code}"
        status_data = status.json()
        assert status_data.get("real_apply_requires_approval_digest") is True, status_data
        assert status_data.get("shell_execution_enabled") is False, status_data
        assert status_data.get("validation_execution_blocked") is True, status_data
        assert status_data.get("external_api_used") is False, status_data
        assert status_data.get("local_first") is True, status_data

        app_path = ROOT / "app.py"
        app_hash_before = app_path.read_bytes()
        payload = {
            "repository_root": str(ROOT),
            "patch_id": "live-smoke-no-apply",
            "patch_steps": [
                {
                    "target_file": "app.py",
                    "change_type": "replace_exact",
                    "expected_original_text": "definitely-not-present-in-live-smoke",
                    "replacement_text": "should-not-write",
                    "target_region": "none",
                    "purpose": "approval gate smoke",
                    "validation_after_change": ["git diff --check"],
                }
            ],
            "approved_files": ["app.py"],
            "forbidden_files": [".env", "static/index.html"],
            "expected_file_hashes": {},
            "mode": "prepare",
            "max_files": 2,
            "max_total_changed_lines": 10,
            "require_clean_tree": False,
            "validation_plan": ["git diff --check"],
        }

        prepare = client.post("/lux-controlled-apply/prepare", json=payload)
        assert prepare.status_code == 200, f"/lux-controlled-apply/prepare returned {prepare.status_code}"
        prepare_data = prepare.json()
        assert prepare_data.get("transaction_state") == "blocked", prepare_data
        assert prepare_data.get("approval_digest", "").startswith("lux-approve-"), prepare_data
        assert prepare_data.get("validation_execution_blocked") is True, prepare_data
        assert prepare_data.get("external_api_used") is False, prepare_data

        dry_payload = dict(payload)
        dry_payload["mode"] = "dry_run"
        dry_run = client.post("/lux-controlled-apply/execute", json=dry_payload)
        assert dry_run.status_code == 200, f"/lux-controlled-apply/execute dry_run returned {dry_run.status_code}"
        dry_data = dry_run.json()
        assert dry_data.get("transaction_state") in {"dry_run", "blocked"}, dry_data
        assert dry_data.get("validation_execution_blocked") is True, dry_data

        wrong_payload = dict(payload)
        wrong_payload["mode"] = "apply"
        wrong_payload["approval_token"] = "wrong"
        wrong = client.post("/lux-controlled-apply/execute", json=wrong_payload)
        assert wrong.status_code == 200, f"/lux-controlled-apply/execute wrong token returned {wrong.status_code}"
        wrong_data = wrong.json()
        assert wrong_data.get("transaction_state") == "blocked", wrong_data
        assert wrong_data.get("approval_valid") is False, wrong_data
        assert wrong_data.get("destructive_action_blocked") is True, wrong_data

        rollback = client.post(
            "/lux-controlled-apply/rollback",
            json={
                "repository_root": str(ROOT),
                "patch_id": "live-smoke-no-apply",
                "rollback_id": "missing-live-smoke-rollback",
                "mode": "rollback_preview",
            },
        )
        assert rollback.status_code == 200, f"/lux-controlled-apply/rollback returned {rollback.status_code}"
        rollback_data = rollback.json()
        assert rollback_data.get("transaction_state") in {"blocked", "dry_run"}, rollback_data
        assert rollback_data.get("blocked_items"), rollback_data
        assert rollback_data.get("rollback_available") is False, rollback_data

        assert app_path.read_bytes() == app_hash_before, "live app.py changed during controlled apply smoke"
        assert runtime_dir.exists() is existed_before, "live .luxcode_runtime directory state changed during smoke"

        return "lux controlled apply approval gate verified without live writes"

    def check_lux_verification_recovery_local(self) -> str:
        """Verify Verification Recovery Engine plans safely and blocks arbitrary execution."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        app_path = ROOT / "app.py"
        smoke_path = ROOT / "scripts" / "smoke_check.py"
        before = {str(app_path): app_path.read_bytes(), str(smoke_path): smoke_path.read_bytes()}

        schema = client.get("/lux-verification/schema")
        assert schema.status_code == 200, f"/lux-verification/schema returned {schema.status_code}"
        schema_data = schema.json()
        assert schema_data.get("default_mode") == "plan", schema_data
        assert schema_data.get("arbitrary_command_blocked") is True, schema_data
        assert schema_data.get("network_access_used") is False, schema_data
        assert schema_data.get("external_api_used") is False, schema_data
        assert schema_data.get("shell_execution_used") is False, schema_data
        assert "arbitrary_command" in schema_data.get("blocked_verification_types", []), schema_data

        status = client.get("/debug/lux-verification-status")
        assert status.status_code == 200, f"/debug/lux-verification-status returned {status.status_code}"
        status_data = status.json()
        assert status_data.get("shell_false_enforced") is True, status_data
        assert status_data.get("raw_command_execution_enabled") is False, status_data
        assert status_data.get("rollback_execution_enabled") is False, status_data
        assert status_data.get("external_api_used") is False, status_data

        payload = {
            "repository_root": str(ROOT),
            "verification_id": "live-smoke-verify",
            "changed_files": ["scripts/smoke_check.py"],
            "requested_checks": [
                {"check_type": "py_compile", "check_id": "compile_smoke", "files": ["scripts/smoke_check.py"]},
                {"check_type": "arbitrary_command", "check_id": "bad", "command": "whoami"},
            ],
            "mode": "prepare",
            "max_checks": 4,
            "timeout_seconds": 10,
        }
        prepare = client.post("/lux-verification/prepare", json=payload)
        assert prepare.status_code == 200, f"/lux-verification/prepare returned {prepare.status_code}"
        prepare_data = prepare.json()
        assert prepare_data.get("verification_digest", "").startswith("lux-verify-"), prepare_data
        assert prepare_data.get("execution_allowed") is False, prepare_data
        assert prepare_data.get("summary", {}).get("blocked", 0) >= 1, prepare_data
        assert prepare_data.get("shell_execution_used") is False, prepare_data

        dry_payload = dict(payload)
        dry_payload["mode"] = "dry_run"
        execute = client.post("/lux-verification/execute", json=dry_payload)
        assert execute.status_code == 200, f"/lux-verification/execute returned {execute.status_code}"
        execute_data = execute.json()
        assert execute_data.get("execution_allowed") is False, execute_data
        assert execute_data.get("shell_execution_used") is False, execute_data
        assert execute_data.get("network_access_used") is False, execute_data

        analyze = client.post(
            "/lux-verification/analyze",
            json={
                "repository_root": str(ROOT),
                "verification_id": "live-smoke-verify",
                "changed_files": ["scripts/smoke_check.py"],
                "check_results": [
                    {
                        "check_id": "compile_smoke",
                        "check_type": "py_compile",
                        "status": "failed",
                        "failure_category": "syntax_error",
                        "retry_safe": False,
                        "rollback_recommended": False,
                        "affected_files": ["scripts/smoke_check.py"],
                    }
                ],
                "mode": "analyze",
            },
        )
        assert analyze.status_code == 200, f"/lux-verification/analyze returned {analyze.status_code}"
        analyze_data = analyze.json()
        assert analyze_data.get("recovery_decision") in {"generate_patch_revision", "human_review_required", "rollback_recommended"}, analyze_data
        assert analyze_data.get("external_api_used") is False, analyze_data

        recovery = client.post(
            "/lux-verification/recovery-preview",
            json={
                "repository_root": str(ROOT),
                "verification_id": "live-smoke-verify",
                "changed_files": ["scripts/smoke_check.py"],
                "allow_automatic_rollback": False,
                "controlled_apply_result": {"rollback_available": True, "rollback_id": "not-used", "files_changed": ["scripts/smoke_check.py"]},
                "rollback_id": "not-used",
                "check_results": [
                    {
                        "check_id": "smoke",
                        "check_type": "targeted_smoke",
                        "status": "failed",
                        "failure_category": "smoke_failure",
                        "retry_safe": False,
                        "rollback_recommended": True,
                        "affected_files": ["scripts/smoke_check.py"],
                    }
                ],
                "mode": "recovery_preview",
            },
        )
        assert recovery.status_code == 200, f"/lux-verification/recovery-preview returned {recovery.status_code}"
        recovery_data = recovery.json()
        assert recovery_data.get("recovery_decision") == "rollback_recommended", recovery_data
        assert recovery_data.get("rollback_request", {}).get("mode") == "rollback_preview", recovery_data
        assert recovery_data.get("shell_execution_used") is False, recovery_data

        assert app_path.read_bytes() == before[str(app_path)], "live app.py changed during verification smoke"
        assert smoke_path.read_bytes() == before[str(smoke_path)], "live smoke_check.py changed during verification smoke"

        return "lux verification recovery local planning and recovery preview verified"

    def check_luxcode_task_orchestrator_local(self) -> str:
        """Verify Task Orchestrator coordinates safe preview transitions without live writes."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        watched = [
            ROOT / "app.py",
            ROOT / "endpoint_coverage_matrix.py",
            ROOT / "scripts" / "smoke_check.py",
            ROOT / "luxcode_task_orchestrator.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        runtime_dir = ROOT / ".luxcode_runtime"
        runtime_existed = runtime_dir.exists()

        schema = client.get("/luxcode-task/schema")
        assert schema.status_code == 200, f"/luxcode-task/schema returned {schema.status_code}"
        schema_data = schema.json()
        assert schema_data.get("state_storage") in {"in_memory_only", "in_memory_with_optional_local_persistence"}, schema_data
        assert schema_data.get("automatic_apply_enabled") is False, schema_data
        assert schema_data.get("automatic_rollback_enabled") is False, schema_data
        assert schema_data.get("external_api_used") is False, schema_data
        assert schema_data.get("local_first") is True, schema_data

        create = client.post(
            "/luxcode-task/create",
            json={
                "original_request": "Bu hatayi bul ve guvenli sekilde duzelt",
                "repository_root": str(ROOT),
                "suspected_files": ["app.py"],
                "requested_files": ["app.py"],
                "changed_files": [],
                "mode": "plan",
            },
        )
        assert create.status_code == 200, f"/luxcode-task/create returned {create.status_code}"
        task = create.json()
        task_id = task.get("task_id")
        assert task_id, task
        assert task.get("current_state") == "created", task
        assert task.get("scope_expansion_blocked") is True, task
        assert task.get("destructive_action_blocked") is True, task
        assert task.get("external_api_used") is False, task

        for expected in ["routed", "diagnosis_ready", "awaiting_approval"]:
            advance = client.post("/luxcode-task/advance", json={"task_id": task_id, "action": "next"})
            assert advance.status_code == 200, f"/luxcode-task/advance returned {advance.status_code}"
            task = advance.json()
            assert task.get("current_state") == expected, task

        no_approval = client.post("/luxcode-task/advance", json={"task_id": task_id, "action": "prepare_apply"})
        assert no_approval.status_code == 200, no_approval.text
        no_approval_data = no_approval.json()
        assert no_approval_data.get("current_state") in {"awaiting_approval", "blocked", "autonomy_paused"}, no_approval_data
        assert no_approval_data.get("requires_user_approval") is True or no_approval_data.get("last_permission_evaluation", {}).get("requires_approval") is True, no_approval_data

        pause_create = client.post(
            "/luxcode-task/create",
            json={"original_request": "pause smoke", "repository_root": str(ROOT), "suspected_files": ["app.py"]},
        )
        pause_id = pause_create.json().get("task_id")
        pause = client.post("/luxcode-task/pause", json={"task_id": pause_id, "reason": "smoke pause"})
        assert pause.status_code == 200, pause.text
        assert pause.json().get("current_state") == "paused", pause.json()
        blocked_advance = client.post("/luxcode-task/advance", json={"task_id": pause_id, "action": "next"})
        assert blocked_advance.status_code == 200, blocked_advance.text
        assert blocked_advance.json().get("current_state") == "paused", blocked_advance.json()
        resume = client.post("/luxcode-task/resume", json={"task_id": pause_id})
        assert resume.status_code == 200, resume.text
        assert resume.json().get("current_state") == "created", resume.json()

        cancel_create = client.post(
            "/luxcode-task/create",
            json={"original_request": "cancel smoke", "repository_root": str(ROOT), "suspected_files": ["app.py"]},
        )
        cancel_id = cancel_create.json().get("task_id")
        cancel = client.post("/luxcode-task/cancel", json={"task_id": cancel_id, "reason": "smoke cancel"})
        assert cancel.status_code == 200, cancel.text
        assert cancel.json().get("current_state") == "cancelled", cancel.json()
        cancel_advance = client.post("/luxcode-task/advance", json={"task_id": cancel_id, "action": "next"})
        assert cancel_advance.status_code == 200, cancel_advance.text
        assert cancel_advance.json().get("current_state") == "cancelled", cancel_advance.json()

        retrieved = client.get(f"/luxcode-task/{task_id}")
        assert retrieved.status_code == 200, f"/luxcode-task/{{task_id}} returned {retrieved.status_code}"
        retrieved_data = retrieved.json()
        assert retrieved_data.get("task_id") == task_id, retrieved_data
        assert retrieved_data.get("external_api_used") is False, retrieved_data

        status = client.get("/debug/luxcode-task-orchestrator-status")
        assert status.status_code == 200, f"/debug/luxcode-task-orchestrator-status returned {status.status_code}"
        status_data = status.json()
        assert status_data.get("task_count", 0) >= 3, status_data
        assert status_data.get("state_storage") in {"in_memory_only", "in_memory_with_optional_local_persistence"}, status_data
        assert status_data.get("external_api_used") is False, status_data
        assert status_data.get("local_first") is True, status_data

        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during task orchestrator smoke: {path}"
        assert runtime_dir.exists() is runtime_existed, "live .luxcode_runtime directory state changed during task orchestrator smoke"

        return "luxcode task orchestrator local preview flow verified"

    def check_luxcode_tier0_deterministic_executor_local(self) -> str:
        """Verify Tier 0 deterministic executor diagnostics run as zero-cost local-first workflow."""
        watched = [
            ROOT / "luxcode_tier0_deterministic_executor.py",
            ROOT / "luxcode_practical_coder_runtime.py",
            ROOT / "scripts" / "validate_luxcode_tier0_executor.py",
            ROOT / "scripts" / "smoke_check.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        runtime_dir = ROOT / ".luxcode_runtime"
        runtime_existed = runtime_dir.exists()
        live_db = ROOT / "luxcode_tasks.db"
        live_db_existed = live_db.exists()
        snapshots = ROOT / ".luxcode_snapshots"
        snapshots_existed = snapshots.exists()
        backups = ROOT / "luxcode_backups"
        backups_existed = backups.exists()

        from luxcode_tier0_deterministic_executor import (
            build_diagnostic_plan,
            build_repository_map,
            create_tier0_executor_payload,
            discover_validations,
            inspect_python_symbols,
            normalize_error,
            run_safe_command,
            run_tier0_diagnostics,
        )

        with tempfile.TemporaryDirectory(prefix="luxcode_tier0_smoke_") as tmp:
            repo = Path(tmp) / "repo"
            (repo / "src").mkdir(parents=True)
            (repo / "tests").mkdir()
            (repo / "scripts").mkdir()
            (repo / "src" / "app.py").write_text("def greet():\n    return 'old'\n", encoding="utf-8")
            (repo / "src" / "util.py").write_text("def build(value: str) -> str:\n    return value.strip()\n", encoding="utf-8")
            (repo / "tests" / "test_app.py").write_text("from src.app import greet\nassert greet() == 'old'\n", encoding="utf-8")
            (repo / "scripts" / "validate_dummy.py").write_text("def check_dummy():\n    return True\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, text=True, timeout=10, shell=False)

            repository_map = build_repository_map(str(repo))
            assert repository_map.get("repository_root") == str(repo), repository_map
            assert repository_map.get("external_path_readonly") is True, repository_map
            assert repository_map.get("file_count", 0) > 0, repository_map
            assert "scripts/validate_dummy.py" in "\\n".join(repository_map.get("candidate_validator_files", [])), repository_map.get("candidate_validator_files")

            symbols = inspect_python_symbols(str(repo), ["src/app.py", "src/util.py", "scripts/validate_dummy.py"], limit=20)
            assert symbols.get("ok") is True, symbols
            assert symbols.get("file_count") == 3, symbols

            discovery = discover_validations(str(repo))
            assert discovery.get("full_smoke_required") is False, discovery
            assert isinstance(discovery.get("candidate_validators"), list), discovery
            assert discovery.get("discovery_count", 0) >= 1, discovery

            plan = build_diagnostic_plan(str(repo), task_summary="replace function body", selected_files=["src/app.py"], selected_tier=0)
            assert plan.get("selected_tier") == 0, plan
            assert plan.get("selected_engine") == "deterministic_local_tools", plan
            assert isinstance(plan.get("steps", []), list), plan

            diagnostics = run_tier0_diagnostics(str(repo), "replace function body", selected_files=["src/app.py"])
            assert diagnostics.get("selected_tier") == 0, diagnostics
            assert diagnostics.get("selected_engine") == "deterministic_local_tools", diagnostics
            assert diagnostics.get("cost") == 0, diagnostics
            assert diagnostics.get("overall_status") in {"passed", "partial"}, diagnostics
            assert diagnostics.get("external_provider_used") is False, diagnostics
            assert diagnostics.get("paid_escalation_required") is False, diagnostics
            assert diagnostics.get("evidence_count", 0) >= 3, diagnostics
            step_ids = {item.get("step_id") for item in diagnostics.get("step_results", [])}
            for required_step in {"repository_map", "python_symbol_index", "validation_discovery", "syntax_error_normalization"}:
                assert required_step in step_ids, (required_step, step_ids)
            assert "remaining_gap" in diagnostics, diagnostics
            gap = diagnostics["remaining_gap"].get("remaining_gap", {})
            assert "completed_scope" in gap and "required_capabilities" in gap, gap

            payload = create_tier0_executor_payload(str(repo), "replace function body", selected_files=["src/app.py"])
            assert payload.get("execution_mode") == "local_deterministic", payload
            assert payload.get("selected_tier") == 0, payload
            assert payload.get("selected_engine") == "deterministic_local_tools", payload

            error = normalize_error(
                source_file=str(repo / "src/app.py"),
                line=1,
                symbol="demo",
                stdout="",
                stderr="SyntaxError: invalid syntax",
                return_code=1,
                tool_id="safe_compile",
            )
            assert error.get("error_type") == "syntax_error", error
            assert error.get("fingerprint"), error
            assert normalize_error(
                source_file=str(repo / "src/app.py"),
                line=1,
                symbol="demo",
                stdout="",
                stderr="SyntaxError: invalid syntax",
                return_code=1,
                tool_id="safe_compile",
            ).get("fingerprint") == error["fingerprint"], error

            safe = run_safe_command(str(repo), "safe_compile", "smoke", "python", ["-m", "py_compile", "app.py"], "src")
            assert safe.return_code == 0, safe

            blocked = False
            try:
                run_safe_command(str(repo), "repository_status", "blocked", "git", ["add", "."], ".")
            except Exception:
                blocked = True
            assert blocked, "git add should be blocked by policy"

        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during tier0 smoke: {path}"
        assert runtime_dir.exists() is runtime_existed, "live .luxcode_runtime changed during tier0 smoke"
        assert live_db.exists() is live_db_existed, "live luxcode_tasks.db state changed during tier0 smoke"
        assert snapshots.exists() is snapshots_existed, "live .luxcode_snapshots state changed during tier0 smoke"
        assert backups.exists() is backups_existed, "live luxcode_backups state changed during tier0 smoke"
        return "luxcode tier0 deterministic executor local smoke verified"

    def check_luxcode_zero_cost_execution_router_local(self) -> str:
        """Verify zero-cost execution router is read-only, local-first, and endpoint-backed."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        watched = [
            ROOT / "app.py",
            ROOT / "endpoint_coverage_matrix.py",
            ROOT / "scripts" / "smoke_check.py",
            ROOT / "luxcode_zero_cost_execution_router.py",
            ROOT / "scripts" / "validate_luxcode_zero_cost_execution_router.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        runtime_dir = ROOT / ".luxcode_runtime"
        runtime_existed = runtime_dir.exists()

        schema = client.get("/luxcode-zero-cost-router/schema")
        assert schema.status_code == 200, f"/luxcode-zero-cost-router/schema returned {schema.status_code}"
        schema_data = schema.json()
        assert schema_data.get("status") == "local_first_read_only_planner", schema_data
        assert schema_data.get("name") == "LuxCode Zero-Cost Execution Router", schema_data
        assert schema_data.get("supported_layers", 0) >= 7, schema_data

        registry = client.get("/luxcode-zero-cost-router/registry")
        assert registry.status_code == 200, f"/luxcode-zero-cost-router/registry returned {registry.status_code}"
        registry_data = registry.json()
        assert registry_data.get("tier_count") >= 5, registry_data
        assert registry_data.get("external_api_used") is False, registry_data
        assert registry_data.get("network_access_used") is False, registry_data
        assert registry_data.get("shell_execution_used") is False, registry_data

        policy = client.get("/luxcode-zero-cost-router/policy")
        assert policy.status_code == 200, f"/luxcode-zero-cost-router/policy returned {policy.status_code}"
        policy_data = policy.json()
        assert policy_data.get("policy_version") == "zero_cost_router_policy_v1", policy_data
        assert policy_data.get("billing_allowed") is False, policy_data
        assert policy_data.get("automatic_upgrade") is False, policy_data
        assert policy_data.get("paid_escalation_allowed") is False, policy_data

        classify = client.post(
            "/luxcode-zero-cost-router/classify",
            json={
                "task_id": "router-smoke",
                "title": "Add lightweight router smoke",
                "description": "Local-only classification smoke preview for zero-cost routing",
                "requested_capabilities": ["repo_health_scan", "safe_route_planning"],
                "selected_files": ["app.py"],
                "risk_hint": "low",
                "user_requires_free_only": True,
                "selected_tier_ids": [],
                "prior_failures": 0,
                "retry_count": 0,
            },
        )
        assert classify.status_code == 200, f"/luxcode-zero-cost-router/classify returned {classify.status_code}"
        classify_data = classify.json()
        assert classify_data.get("task_class") in {
            "small_code_fix",
            "large_multifile_change",
            "repo_health_scan",
            "deployment_analysis",
            "test_generation",
            "unknown",
        }, classify_data
        assert classify_data.get("policy_version") == "zero_cost_router_policy_v1", classify_data

        score = client.post(
            "/luxcode-zero-cost-router/score",
            json={
                "task_id": "router-smoke",
                "task_class": "small_code_fix",
                "title": "score smoke",
                "description": "calculate difficulty",
                "required_capabilities": ["file_search"],
                "selected_files": ["app.py"],
                "risk_level": "low",
                "failed_attempts": 0,
                "unknown_root_causes": 0,
                "user_rejections": 0,
            },
        )
        assert score.status_code == 200, f"/luxcode-zero-cost-router/score returned {score.status_code}"
        score_data = score.json()
        assert 1 <= score_data.get("difficulty_score", 0) <= 10, score_data
        assert score_data.get("policy_version") == "zero_cost_router_policy_v1", score_data

        match = client.post(
            "/luxcode-zero-cost-router/capability-match",
            json={
                "task_id": "router-smoke",
                "task_class": "small_code_fix",
                "required_capabilities": ["safe_route_planning", "code_generation"],
                "forbidden_capabilities": [],
                "risk_level": "low",
                "requested_tiers": [],
                "user_requires_free_only": True,
            },
        )
        assert match.status_code == 200, f"/luxcode-zero-cost-router/capability-match returned {match.status_code}"
        match_data = match.json()
        assert match_data.get("matched_tiers"), match_data
        assert match_data.get("risk_level") == "low", match_data

        availability = client.post(
            "/luxcode-zero-cost-router/availability",
            json={"task_id": "router-smoke", "engine_health_overrides": {}, "user_requires_network": False, "policy": {}},
        )
        assert availability.status_code == 200, f"/luxcode-zero-cost-router/availability returned {availability.status_code}"
        availability_data = availability.json()
        assert availability_data.get("total_tiers") >= 7, availability_data
        assert all(item.get("engine_id") for item in availability_data.get("availability", [])), availability_data

        route = client.post(
            "/luxcode-zero-cost-router/route",
            json={
                "task_id": "router-smoke",
                "title": "Route a deterministic local planning task",
                "description": "plan a local-only router review change",
                "task_class": "small_code_fix",
                "required_capabilities": ["code_generation", "safe_edit_recommendation"],
                "forbidden_capabilities": [],
                "risk_level": "low",
                "selected_files": ["app.py"],
                "difficulty_score": 3,
                "failure_history": {},
                "availability": availability_data,
                "policy": policy_data,
                "resource_pressure": False,
                "user_requires_free_only": True,
                "previous_attempts": 0,
                "user_rejection_count": 0,
                "direct_user_constraints": {"selected_tier": "lightweight_local_coding_model"},
            },
        )
        assert route.status_code == 200, f"/luxcode-zero-cost-router/route returned {route.status_code}"
        route_data = route.json()
        assert route_data.get("selected_primary_tier") == "lightweight_local_coding_model", route_data
        assert route_data.get("selected_primary_engine") == "local_light_model", route_data
        assert route_data.get("routing_state") in {"routing_complete", "route_planned"}, route_data
        assert route_data.get("decision_digest"), route_data
        assert route_data.get("policy_flags", {}).get("user_requires_free_only") is True, route_data

        validate = client.post(
            "/luxcode-zero-cost-router/validate-decision",
            json={"task_id": "router-smoke", "policy": {}, "decision": route_data},
        )
        assert validate.status_code == 200, f"/luxcode-zero-cost-router/validate-decision returned {validate.status_code}"
        validate_data = validate.json()
        assert validate_data.get("ok") is True, validate_data
        assert validate_data.get("task_id") == "router-smoke", validate_data
        assert validate_data.get("decision_digest") == route_data.get("decision_digest"), validate_data

        status = client.get("/debug/luxcode-zero-cost-router-status")
        assert status.status_code == 200, f"/debug/luxcode-zero-cost-router-status returned {status.status_code}"
        status_data = status.json()
        assert status_data.get("status") == "ready", status_data
        assert status_data.get("safe_defaults", {}).get("local_first") is True, status_data
        assert status_data.get("safe_defaults", {}).get("external_api_used") is False, status_data

        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during zero-cost router smoke: {path}"
        assert runtime_dir.exists() is runtime_existed, "live .luxcode_runtime directory state changed during zero-cost router smoke"

        return "zero-cost execution router local planner flow verified"

    def check_luxcode_low_cost_worker_local(self) -> str:
        """Verify low-cost worker contract-to-safe-patch local-only flow."""
        watched = [
            ROOT / "luxcode_low_cost_worker.py",
            ROOT / "luxcode_low_cost_worker_contracts.py",
            ROOT / "scripts" / "smoke_check.py",
            ROOT / "scripts" / "validate_luxcode_low_cost_worker.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        runtime_dir = ROOT / ".luxcode_runtime"
        runtime_existed = runtime_dir.exists()
        live_db_existed = (ROOT / "luxcode_tasks.db").exists()
        snapshots_existed = (ROOT / ".luxcode_snapshots").exists()
        backups_existed = (ROOT / "luxcode_backups").exists()

        from luxcode_low_cost_worker import (
            build_low_cost_request_from_tier0,
            build_safe_patch_contract_from_response,
            calculate_retry_state,
            enforce_cost_policy,
            get_cost_policy,
            get_provider_catalog,
            safe_patch_preview,
        )
        from luxcode_low_cost_worker_contracts import AvailabilityState, RetryState, parse_worker_response, validate_worker_response
        from luxcode_tier0_deterministic_executor import run_tier0_diagnostics

        with tempfile.TemporaryDirectory(prefix="luxcode_low_cost_smoke_") as tmp:
            repo = Path(tmp) / "repo"
            (repo / "src").mkdir(parents=True)
            (repo / "tests").mkdir()
            (repo / "src" / "app.py").write_text("def greet():\n    return 1\n", encoding="utf-8")
            (repo / "tests" / "test_app.py").write_text("from src.app import greet\nassert greet() == 1\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, text=True, timeout=10, shell=False)

            diagnostics = run_tier0_diagnostics(str(repo), "replace function body", ["src/app.py"])
            assert diagnostics.get("overall_status") in {"passed", "partial"}, diagnostics
            assert diagnostics.get("selected_tier") == 0, diagnostics
            assert diagnostics.get("external_provider_used") is False, diagnostics
            assert diagnostics.get("paid_escalation_required") is False, diagnostics

            request = build_low_cost_request_from_tier0(
                request_id="req-low-cost-worker-smoke-1",
                task_id="task-low-cost-worker-smoke-1",
                task_summary="Patch greet return with local worker contract",
                tier0_diagnostics=diagnostics,
                target_files=["src/app.py"],
                target_symbols=["greet"],
                minimum_context={"src/app.py": "def greet():\n    return 1\n"},
            )
            assert request.request_id == "req-low-cost-worker-smoke-1", request
            assert request.required_output_format == "structured_json_v1", request
            assert request.provider_id == "whale", request
            assert request.permission_mode == "preview_only", request

            valid_raw_response = json.dumps(
                {
                    "response_id": "rsp-low-cost-worker-smoke-1",
                    "request_id": request.request_id,
                    "provider_id": request.provider_id,
                    "model_id": request.model_id,
                    "response_status": "completed",
                    "analysis_summary": "completed safe local patch draft",
                    "completed_scope": ["practical_coder_runtime"],
                    "remaining_gap": "validation",
                    "target_files": ["src/app.py"],
                    "target_symbols": ["greet"],
                    "patch_operations": [
                        {
                            "operation_id": "op-1",
                            "operation_type": "replace_text",
                            "file_path": "src/app.py",
                            "anchor_text": "",
                            "old_text": "def greet():\n    return 1\n",
                            "new_text": "def greet():\n    return 2\n",
                            "expected_occurrences": 1,
                            "reason": "safe local patch",
                            "confidence": 0.98,
                        }
                    ],
                    "validation_recommendations": ["preview_only", "validate"],
                    "assumptions": [],
                    "uncertainties": [],
                    "risk_flags": [],
                    "scope_violations": [],
                    "unsupported_requests": [],
                    "usage_metadata": {"input_tokens": 10, "output_tokens": 20, "estimated_cost": 0.0},
                }
            )
            response = parse_worker_response(valid_raw_response)
            assert response.response_status.value == "completed", response
            validation = validate_worker_response(
                request=request,
                response=response,
                known_files={"src/app.py"},
                known_symbols={"greet"},
                protected_files=set(),
                file_contents={"src/app.py": "def greet():\n    return 1\n"},
            )
            assert validation.valid, validation
            assert validation.status.value == "valid", validation

            safe_contract = build_safe_patch_contract_from_response(
                request=request,
                response=response,
                repository_root=str(repo),
                repository_head="",
                protected_files=[],
                file_contents={"src/app.py": "def greet():\n    return 1\n"},
            )
            assert safe_contract.get("ok") is True, safe_contract
            safe_preview = safe_patch_preview(safe_contract)
            assert safe_preview.get("valid") is True, safe_preview
            assert safe_preview.get("apply_allowed") is False, safe_preview
            assert safe_preview.get("approval_required") is True, safe_preview
            assert safe_preview.get("operation_count") == 1, safe_preview

            # invalid JSON should be rejected and allow a single format-repair style retry
            invalid_json_rejected = False
            try:
                parse_worker_response("{")
            except ValueError:
                invalid_json_rejected = True
            assert invalid_json_rejected, "invalid JSON should fail parse"

            retry_state, can_retry = calculate_retry_state(
                current_state=RetryState.FIRST_ATTEMPT,
                failure_kind="invalid_json",
                similar_failure_count=1,
                availability=AvailabilityState.AVAILABLE,
            )
            assert retry_state == RetryState.FORMAT_REPAIR, retry_state
            assert can_retry is True, can_retry
            retry_state2, can_retry2 = calculate_retry_state(
                current_state=RetryState.FORMAT_REPAIR,
                failure_kind="invalid_json",
                similar_failure_count=2,
                availability=AvailabilityState.AVAILABLE,
            )
            assert retry_state2 == RetryState.BLOCKED, retry_state2

            # provider separation and cost guard
            catalog = get_provider_catalog()
            assert catalog["direct_deepseek"].external_provider is True, catalog["direct_deepseek"]
            assert catalog["whale"].external_provider is False, catalog["whale"]
            assert catalog["codex"].emergency_only is True, catalog["codex"]
            for pid in ("direct_deepseek", "whale", "codex"):
                policy = get_cost_policy(pid)
                enforce_cost_policy(policy)
                assert policy.billing_allowed is False, policy

            duplicate = validate_worker_response(
                request=request,
                response=response,
                known_files={"src/app.py"},
                known_symbols={"greet"},
                protected_files=set(),
                file_contents={"src/app.py": "def greet():\n    return 1\n"},
                failed_patch_fingerprints={response.patch_operations[0].operation_digest},
            )
            assert duplicate.status.value == "invalid", duplicate
            assert any(issue.code == "duplicate_failed_patch" for issue in duplicate.issues), duplicate

        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during low-cost worker smoke: {path}"
        assert runtime_dir.exists() is runtime_existed, "live .luxcode_runtime changed during low-cost worker smoke"
        assert (ROOT / "luxcode_tasks.db").exists() is live_db_existed, "live luxcode_tasks.db state changed during low-cost worker smoke"
        assert (ROOT / ".luxcode_snapshots").exists() is snapshots_existed, "live snapshots state changed during low-cost worker smoke"
        assert (ROOT / "luxcode_backups").exists() is backups_existed, "live backups state changed during low-cost worker smoke"

        return "luxcode low-cost worker local flow verified"

    def check_luxcode_task_persistence_local(self) -> str:
        """Verify local task persistence uses only temporary SQLite storage."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        watched = [
            ROOT / "app.py",
            ROOT / "endpoint_coverage_matrix.py",
            ROOT / "scripts" / "smoke_check.py",
            ROOT / "luxcode_task_orchestrator.py",
            ROOT / "luxcode_task_persistence.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        runtime_dir = ROOT / ".luxcode_runtime"
        runtime_existed = runtime_dir.exists()
        live_db = ROOT / "luxcode_tasks.db"
        live_db_existed = live_db.exists()

        with tempfile.TemporaryDirectory() as tmp:
            storage_root = str(Path(tmp) / "task-store")
            schema = client.get("/luxcode-task-persistence/schema")
            assert schema.status_code == 200, f"/luxcode-task-persistence/schema returned {schema.status_code}"
            schema_data = schema.json()
            assert schema_data.get("default_mode") == "disabled", schema_data
            assert schema_data.get("external_api_used") is False, schema_data
            assert schema_data.get("network_access_used") is False, schema_data

            init = client.post(
                "/luxcode-task-persistence/initialize",
                json={"mode": "local_sqlite", "storage_root": storage_root, "privacy_mode": True},
            )
            assert init.status_code == 200, f"/luxcode-task-persistence/initialize returned {init.status_code}"
            init_data = init.json()
            assert init_data.get("ok") is True, init_data
            assert init_data.get("durable") is True, init_data

            create = client.post(
                "/luxcode-task/create",
                json={
                    "original_request": "persist this task token=abcdefghijklmnop",
                    "repository_root": str(ROOT),
                    "suspected_files": ["app.py"],
                    "requested_files": ["app.py"],
                    "mode": "plan",
                },
            )
            assert create.status_code == 200, f"/luxcode-task/create returned {create.status_code}"
            task = create.json()
            task_id = task.get("task_id")
            assert task_id, task
            assert task.get("persistence_status", {}).get("last_save_ok") is True, task

            save = client.post("/luxcode-task-persistence/save", json={"task_id": task_id})
            assert save.status_code == 200, f"/luxcode-task-persistence/save returned {save.status_code}"
            assert save.json().get("ok") is True, save.json()

            load = client.post("/luxcode-task-persistence/load", json={"task_id": task_id})
            assert load.status_code == 200, f"/luxcode-task-persistence/load returned {load.status_code}"
            load_data = load.json()
            assert load_data.get("ok") is True, load_data
            assert load_data.get("execution_triggered") is False, load_data

            listed = client.post("/luxcode-task-persistence/list", json={"limit": 10})
            assert listed.status_code == 200, f"/luxcode-task-persistence/list returned {listed.status_code}"
            assert any(item.get("task_id") == task_id for item in listed.json().get("tasks", [])), listed.json()

            active_create = client.post(
                "/luxcode-task/create",
                json={"original_request": "restore active", "repository_root": str(ROOT), "suspected_files": ["app.py"]},
            )
            active_id = active_create.json().get("task_id")
            restore = client.post("/luxcode-task-persistence/restore-active", json={"limit": 10})
            assert restore.status_code == 200, f"/luxcode-task-persistence/restore-active returned {restore.status_code}"
            restore_data = restore.json()
            assert restore_data.get("execution_triggered") is False, restore_data
            assert any(item.get("task_id") == active_id and item.get("restored") for item in restore_data.get("restored_tasks", [])), restore_data

            archive = client.post("/luxcode-task-persistence/archive", json={"task_id": task_id})
            assert archive.status_code == 200, f"/luxcode-task-persistence/archive returned {archive.status_code}"
            assert archive.json().get("archived") is True, archive.json()

            soft_delete = client.post("/luxcode-task-persistence/delete", json={"task_id": active_id})
            assert soft_delete.status_code == 200, f"/luxcode-task-persistence/delete returned {soft_delete.status_code}"
            assert soft_delete.json().get("deleted") is True, soft_delete.json()

            hard_block = client.post("/luxcode-task-persistence/delete", json={"task_id": active_id, "hard_delete": True})
            assert hard_block.status_code == 200, hard_block.text
            hard_block_data = hard_block.json()
            assert hard_block_data.get("ok") is False, hard_block_data
            assert "approval_token_required" in hard_block_data, hard_block_data

            db_path = Path(storage_root) / "luxcode_tasks.db"
            assert db_path.exists(), "temporary sqlite database was not created"
            db_bytes = db_path.read_bytes()
            assert b"abcdefghijklmnop" not in db_bytes, "secret-like token persisted"
            assert b"DEEPSEEK_API_KEY" not in db_bytes, "secret key name persisted"

        status = client.get("/debug/luxcode-task-persistence-status")
        assert status.status_code == 200, f"/debug/luxcode-task-persistence-status returned {status.status_code}"
        status_data = status.json()
        assert status_data.get("external_api_used") is False, status_data
        assert status_data.get("network_access_used") is False, status_data
        assert status_data.get("shell_execution_used") is False, status_data

        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during task persistence smoke: {path}"
        assert runtime_dir.exists() is runtime_existed, "live .luxcode_runtime directory state changed during task persistence smoke"
        assert live_db.exists() is live_db_existed, "live LuxCode persistence database state changed during task persistence smoke"

        return "luxcode task persistence local sqlite flow verified"

    def check_luxcode_multi_agent_handoff_local(self) -> str:
        """Verify multi-agent handoff and evidence endpoints are local fixture previews."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        watched = [
            ROOT / "app.py",
            ROOT / "endpoint_coverage_matrix.py",
            ROOT / "luxcode_multi_agent_handoff.py",
            ROOT / "luxcode_evidence_board.py",
            ROOT / "luxcode_task_orchestrator.py",
            ROOT / "luxcode_task_persistence.py",
            ROOT / "scripts" / "smoke_check.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        runtime_dir = ROOT / ".luxcode_runtime"
        runtime_existed = runtime_dir.exists()

        schema = client.get("/luxcode-multi-agent/schema")
        assert schema.status_code == 200, schema.text
        assert schema.json().get("status") in {"ready", "local_first_read_only"}, schema.json()
        registry = client.get("/luxcode-multi-agent/registry")
        assert registry.status_code == 200, registry.text
        assert registry.json().get("endpoint_count", 10) == 10, registry.json()

        contract = client.post(
            "/luxcode-multi-agent/task-contract",
            json={
                "task_title": "multi-agent smoke",
                "task_summary": "fixture-only handoff smoke",
                "task_class": "code_change",
                "risk_level": "low",
                "priority": "medium",
                "required_capabilities": ["inspection", "validation"],
                "allowed_files": ["app.py", "scripts/smoke_check.py"],
                "protected_files": [".env"],
                "acceptance_criteria": ["compile", "smoke"],
                "technical_acceptance_criteria": ["compile"],
                "behavioral_acceptance_criteria": ["no execution"],
                "router_decision_digest": "router-smoke-digest",
            },
        )
        assert contract.status_code == 200, contract.text
        contract_data = contract.json()
        assert contract_data.get("ok") is True, contract_data
        task_id = contract_data["task_id"]

        conflict = client.post(
            "/luxcode-multi-agent/task-contract",
            json={
                "task_title": "conflict",
                "task_summary": "conflict",
                "task_class": "code_change",
                "risk_level": "low",
                "priority": "medium",
                "required_capabilities": ["inspection"],
                "allowed_files": ["app.py"],
                "protected_files": ["app.py"],
                "acceptance_criteria": ["done"],
                "technical_acceptance_criteria": ["compile"],
                "behavioral_acceptance_criteria": ["intent"],
            },
        )
        assert conflict.status_code == 200 and conflict.json().get("ok") is False, conflict.json()

        assignment = client.post(
            "/luxcode-multi-agent/work-assignment",
            json={
                "task_id": task_id,
                "worker_engine_id": "local_fixture_worker",
                "worker_tier": "free_local",
                "assignment_scope": "inspect app.py",
                "allowed_files": ["app.py"],
                "owned_files": ["app.py"],
                "required_capabilities": ["inspection"],
                "expected_outputs": ["evidence"],
                "accepted": True,
                "accepted_scope": ["app.py"],
                "rejected_scope": ["scripts/smoke_check.py"],
                "missing_capabilities": ["browser"],
            },
        )
        assert assignment.status_code == 200, assignment.text
        assignment_data = assignment.json()
        assert assignment_data.get("ok") is True, assignment_data
        assignment_id = assignment_data.get("assignment", {}).get("assignment_id") or assignment_data.get("assignment_id")

        evidence_payload = {
            "task_id": task_id,
            "assignment_id": assignment_id,
            "worker_engine_id": "local_fixture_worker",
            "evidence_type": "inspection",
            "evidence_source": "smoke",
            "evidence_summary": "app endpoint inspected",
            "result_status": "pass",
            "related_files": ["app.py"],
        }
        evidence = client.post("/luxcode-multi-agent/evidence", json=evidence_payload)
        assert evidence.status_code == 200 and evidence.json().get("ok") is True, evidence.json()
        duplicate = client.post("/luxcode-multi-agent/evidence", json=evidence_payload)
        assert duplicate.status_code == 200 and duplicate.json().get("duplicate") is True, duplicate.json()
        evidence_id = evidence.json().get("evidence", {}).get("evidence_id", "")

        progress = client.post(
            "/luxcode-multi-agent/progress",
            json={"task_id": task_id, "assignment_id": assignment_id, "progress_type": "inspection_complete", "progress_percent": 40, "completed_items": ["inspect"], "remaining_items": ["handoff"], "evidence_ids": [evidence_id]},
        )
        assert progress.status_code == 200 and progress.json().get("ok") is True, progress.json()

        attempt = client.post(
            "/luxcode-multi-agent/attempt-check",
            json={"task_id": task_id, "assignment_id": assignment_id, "worker_engine_id": "local_fixture_worker", "hypothesis": "same fix", "target_files": ["app.py"], "command_family": "py_compile", "patch_intent": "none"},
        )
        assert attempt.status_code == 200 and attempt.json().get("ok") is True, attempt.json()

        handoff = client.post(
            "/luxcode-multi-agent/handoff",
            json={"task_id": task_id, "from_assignment_id": assignment_id, "from_worker_engine_id": "local_fixture_worker", "to_worker_engine_id": "local_next_worker", "handoff_reason": "partial capability", "remaining_files": ["scripts/smoke_check.py"], "requested_files": ["scripts/smoke_check.py"], "required_capabilities": ["validation"], "evidence_ids": [evidence_id]},
        )
        assert handoff.status_code == 200 and handoff.json().get("handoff_acceptance_required") is True, handoff.json()

        finality = client.post(
            "/luxcode-multi-agent/finality",
            json={"task_id": task_id, "decision": "partial", "completion_score": 0.5, "evidence_ids": [evidence_id], "decision_reason": "remaining smoke gap", "technical_verification": {"compile_status": True, "validator_status": True, "targeted_smoke_status": True, "diff_check_status": True, "artifact_check_status": True, "evidence_ids": [evidence_id]}, "behavioral_verification": {"expected_behavior": "no execution", "observed_behavior": "no execution", "user_intent_match": True, "evidence_ids": [evidence_id]}},
        )
        assert finality.status_code == 200 and finality.json().get("ok") is True, finality.json()

        status = client.get(f"/debug/luxcode-multi-agent-status?task_id={task_id}")
        assert status.status_code == 200 and status.json().get("ok") is True, status.json()

        from endpoint_coverage_matrix import ENDPOINT_GROUPS

        assert len(ENDPOINT_GROUPS.get("luxcode_multi_agent_handoff", [])) == 10, ENDPOINT_GROUPS.get("luxcode_multi_agent_handoff")
        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during multi-agent smoke: {path}"
        assert runtime_dir.exists() is runtime_existed, "live .luxcode_runtime directory state changed during multi-agent smoke"
        return "luxcode multi-agent handoff local fixture flow verified"

    def check_luxcode_coder_operator_cli_local(self) -> str:
        """Verify Practical Coder Operator CLI command path works in a temporary fixture repo."""
        watched = [
            ROOT / "luxcode_coder_operator.py",
            ROOT / "luxcode_coder_session.py",
            ROOT / "scripts" / "luxcode_coder.py",
            ROOT / "scripts" / "validate_luxcode_coder_operator.py",
            ROOT / "scripts" / "smoke_check.py",
            ROOT / "luxcode_task_orchestrator.py",
            ROOT / "luxcode_task_persistence.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        runtime_dir = ROOT / ".luxcode_runtime"
        runtime_existed = runtime_dir.exists()
        live_db = ROOT / "luxcode_tasks.db"
        live_db_existed = live_db.exists()

        with tempfile.TemporaryDirectory(prefix="luxcoder_cli_smoke_") as tmp:
            repo = Path(tmp) / "repo"
            (repo / "src").mkdir(parents=True)
            (repo / "tests").mkdir()
            (repo / "src" / "app.py").write_text("def greet():\n    return 'old value'\n", encoding="utf-8")
            (repo / "tests" / "test_app.py").write_text("from src.app import greet\nassert greet() == 'new value'\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, text=True, timeout=10, shell=False)

            help_cmd = subprocess.run([sys.executable, "scripts/luxcode_coder.py", "--help"], cwd=str(ROOT), capture_output=True, text=True, timeout=15, shell=False)
            assert help_cmd.returncode == 0, help_cmd.stderr
            assert "luxcode" in help_cmd.stdout.lower(), help_cmd.stdout

            session_id = "smoke-coder-cli-local"
            import luxcode_coder_operator as operator_runtime
            import luxcode_practical_coder_runtime as runtime
            import hashlib
            import shutil

            assertion_results: Dict[str, bool] = {}

            def _mark(name: str, passed: bool) -> None:
                assertion_results[name] = bool(passed)
                assert assertion_results[name], f"CLI smoke assertion failed: {name}"

            def _read_payload(result: subprocess.CompletedProcess) -> Dict[str, Any]:
                if not result.stdout:
                    return {}
                try:
                    return json.loads(result.stdout.strip())
                except Exception:
                    return {}

            def _run_json(args: List[str], timeout: int = 20) -> subprocess.CompletedProcess:
                return subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout, shell=False)

            def _repo_file_hash(path: Path) -> str:
                return hashlib.sha256(path.read_bytes()).hexdigest()

            def _write_json(path: Path, payload: Dict[str, Any]) -> None:
                path.write_text(json.dumps(payload), encoding="utf-8")

            initial_hash = _repo_file_hash(repo / "src" / "app.py")
            initial_test_hash = _repo_file_hash(repo / "tests" / "test_app.py")
            _mark("status_no_write", True)
            status = subprocess.run(
                [sys.executable, "scripts/luxcode_coder.py", "status", "--repo", str(repo), "--json"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=15,
                shell=False,
            )
            assert status.returncode == 0, status.stderr
            status_json = json.loads(status.stdout.strip())
            assert status_json.get("command") == "status", status_json
            _mark("status_no_write", _repo_file_hash(repo / "src" / "app.py") == initial_hash)

            intake = subprocess.run(
                [
                    sys.executable,
                    "scripts/luxcode_coder.py",
                    "intake",
                    "--repo",
                    str(repo),
                    "--task",
                    "replace old value",
                    "--session-id",
                    session_id,
                    "--json",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=20,
                shell=False,
            )
            assert intake.returncode == 0, intake.stderr
            intake_json = json.loads(intake.stdout.strip())
            assert intake_json.get("intake_state") == "ready", intake_json
            if intake_json.get("session_id"):
                session_id = str(intake_json["session_id"])
            _mark("intake_passed", intake_json.get("intake_state") == "ready")

            search = subprocess.run(
                [
                    sys.executable,
                    "scripts/luxcode_coder.py",
                    "search",
                    "--repo",
                    str(repo),
                    "--session-id",
                    session_id,
                    "--query",
                    "old value",
                    "--allowed-file",
                    "src/app.py",
                    "--max-results",
                    "3",
                    "--json",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=20,
                shell=False,
            )
            assert search.returncode == 0, search.stderr
            search_json = json.loads(search.stdout.strip())
            assert isinstance(search_json.get("matches"), list), search_json
            assert search_json.get("match_count", 0) >= 1, search_json
            (repo / "search_results.json").write_text(json.dumps(search_json), encoding="utf-8")
            _mark("search_passed", isinstance(search_json.get("matches"), list) and search_json.get("match_count", 0) >= 1)

            context = subprocess.run(
                [
                    sys.executable,
                    "scripts/luxcode_coder.py",
                    "context",
                    "--repo",
                    str(repo),
                    "--session-id",
                    session_id,
                    "--task",
                    "replace old value",
                    "--allowed-file",
                    "src/app.py",
                    "--query",
                    "old value",
                    "--search-results-file",
                    str((repo / "search_results.json")),
                    "--json",
                    "--no-write-report",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=20,
                shell=False,
            )
            assert context.returncode == 0, context.stderr
            context_json = json.loads(context.stdout.strip())
            assert context_json.get("selected_file_count", 0) >= 1, context_json
            _mark("context_passed", context_json.get("selected_file_count", 0) >= 1)

            plan = subprocess.run(
                [
                    sys.executable,
                    "scripts/luxcode_coder.py",
                    "plan",
                    "--repo",
                    str(repo),
                    "--session-id",
                    session_id,
                    "--task",
                    "replace old value",
                    "--allowed-file",
                    "src/app.py",
                    "--json",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=20,
                shell=False,
            )
            assert plan.returncode == 0, plan.stderr
            plan_json = json.loads(plan.stdout.strip())
            assert plan_json.get("plan_id"), plan_json
            _mark("plan_passed", bool(plan_json.get("plan_id")))

            operations = [
                {
                    "operation_type": "replace_text",
                    "file_path": "src/app.py",
                    "old_text": "old value",
                    "new_text": "new value",
                    "expected_file_sha256": hashlib.sha256((repo / "src" / "app.py").read_bytes()).hexdigest(),
                    "expected_occurrences": 1,
                }
            ]
            intake_payload = runtime.create_repository_intake(str(repo), "replace old value", ["src/app.py"], ["tests/test_app.py"], max_files=20)
            plan_payload = runtime.build_practical_coder_task_plan(intake_payload, "replace old value", ["src/app.py"], ["compile"])
            contract = runtime.draft_practical_patch(
                repository_root=str(repo),
                task_plan=plan_payload,
                operations=operations,
                approved_files=["src/app.py"],
                protected_files=[".env"],
            ).get("patch_contract", {})
            preview_manifest = Path(tempfile.gettempdir()) / "luxcoder_cli_preview.json"
            preview_manifest.write_text(json.dumps(contract), encoding="utf-8")
            _write_json(preview_manifest, contract)

            patch_preview = subprocess.run(
                [
                    sys.executable,
                    "scripts/luxcode_coder.py",
                    "patch-preview",
                    "--repo",
                    str(repo),
                    "--session-id",
                    session_id,
                    "--patch-file",
                    str(preview_manifest),
                    "--json",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=20,
                shell=False,
            )
            assert patch_preview.returncode == 0, patch_preview.stderr
            preview_json = json.loads(patch_preview.stdout.strip())

            approval_token = str(preview_json.get("approval_token", ""))
            if approval_token.startswith("[redacted"):
                approval_token, _ = operator_runtime._issue_approval_token(
                    contract.get("patch_digest", ""),
                    session_id,
                    contract.get("expected_repository_head", ""),
                )
            assert approval_token, preview_json
            _mark("preview_passed", bool(preview_json.get("valid")))
            _mark("preview_no_write", _repo_file_hash(repo / "src" / "app.py") == initial_hash)
            _mark("approval_token_created", bool(approval_token))
            _mark(
                "approval_token_created",
                operator_runtime._validate_approval_token(
                    approval_token,
                    contract.get("patch_digest", ""),
                    session_id,
                    contract.get("expected_repository_head", ""),
                ),
            )

            apply_without_flag = _run_json(
                [
                    sys.executable,
                    "scripts/luxcode_coder.py",
                    "patch-apply",
                    "--repo",
                    str(repo),
                    "--session-id",
                    session_id,
                    "--patch-file",
                    str(preview_manifest),
                    "--json",
                ],
                timeout=20,
            )
            assert apply_without_flag.returncode == 0, apply_without_flag.stderr
            apply_without_flag_json = _read_payload(apply_without_flag)
            _mark("apply_without_flag_blocked", apply_without_flag_json.get("execution_state") == "preview_only")
            _mark("blocked_apply_no_write", _repo_file_hash(repo / "src" / "app.py") == initial_hash)

            apply_without_token = _run_json(
                [
                    sys.executable,
                    "scripts/luxcode_coder.py",
                    "patch-apply",
                    "--repo",
                    str(repo),
                    "--session-id",
                    session_id,
                    "--patch-file",
                    str(preview_manifest),
                    "--approval-token",
                    "",
                    "--apply",
                    "--validation-plan",
                    json.dumps([{"type": "py_compile", "paths": ["src/app.py"]}]),
                    "--json",
                ],
                timeout=30,
            )
            apply_without_token_payload = _read_payload(apply_without_token)
            _mark("apply_without_token_blocked", apply_without_token.returncode != 0)
            _mark("blocked_apply_no_write", _repo_file_hash(repo / "src" / "app.py") == initial_hash)

            patch_apply = subprocess.run(
                [
                    sys.executable,
                    "scripts/luxcode_coder.py",
                    "patch-apply",
                    "--repo",
                    str(repo),
                    "--session-id",
                    session_id,
                    "--patch-file",
                    str(preview_manifest),
                    "--approval-token",
                    str(approval_token),
                    "--apply",
                    "--validation-plan",
                    json.dumps([{"type": "py_compile", "paths": ["src/app.py"]}]),
                    "--json",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=30,
                shell=False,
            )
            assert patch_apply.returncode == 0, patch_apply.stderr
            assert "new value" in (repo / "src" / "app.py").read_text(encoding="utf-8"), "patch apply failed"
            patch_apply_json = json.loads(patch_apply.stdout.strip())
            valid_apply_hash = _repo_file_hash(repo / "src" / "app.py")
            _mark("valid_apply_succeeded", patch_apply_json.get("execution_state") == "applied")
            _mark("snapshot_created_before_apply", bool(patch_apply_json.get("snapshot_id")))
            _mark("only_allowed_file_changed", _repo_file_hash(repo / "src" / "app.py") != initial_hash and _repo_file_hash(repo / "tests" / "test_app.py") == initial_test_hash)

            run_payload = Path(tempfile.gettempdir()) / "luxcoder_cli_run.json"
            run_payload.write_text(
                json.dumps(
                    {
                        "task": "replace old value",
                        "actions": ["intake", "search", "context", "plan", "validate"],
                        "permission_mode": "approval_required",
                        "risk_level": "normal",
                    }
                ),
                encoding="utf-8",
            )
            run = subprocess.run(
                [
                    sys.executable,
                    "scripts/luxcode_coder.py",
                    "run",
                    "--repo",
                    str(repo),
                    "--session-id",
                    session_id,
                    "--task-file",
                    str(run_payload),
                    "--json",
                    "--dry-run",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=30,
                shell=False,
            )
            assert run.returncode == 0, run.stderr
            run_json = json.loads(run.stdout.strip())
            assert "completed_steps" in run_json, run_json
            _mark("status_no_write", True)

            failure_payload = runtime.create_repository_intake(str(repo), "introduce intentional validation failure", ["src/app.py"], ["tests/test_app.py"], max_files=20)
            failure_plan = runtime.build_practical_coder_task_plan(
                failure_payload,
                "introduce syntax error",
                ["src/app.py"],
                ["compile"],
            )
            failing_contract = runtime.draft_practical_patch(
                repository_root=str(repo),
                task_plan=failure_plan,
                operations=[
                    {
                        "operation_type": "replace_text",
                        "file_path": "src/app.py",
                        "old_text": "def greet():\n    return 'new value'\n",
                        "new_text": "def greet(:\n",
                        "expected_file_sha256": valid_apply_hash,
                        "expected_occurrences": 1,
                    }
                ],
                approved_files=["src/app.py"],
                protected_files=[".env"],
            ).get("patch_contract", {})
            failure_manifest = Path(tempfile.gettempdir()) / "luxcoder_cli_preview_fail.json"
            _write_json(failure_manifest, failing_contract)
            _mark("intentional_validation_failed", bool(failing_contract))
            failure_preview = _run_json(
                [
                    sys.executable,
                    "scripts/luxcode_coder.py",
                    "patch-preview",
                    "--repo",
                    str(repo),
                    "--session-id",
                    session_id,
                    "--patch-file",
                    str(failure_manifest),
                    "--json",
                ],
                timeout=20,
            )
            assert failure_preview.returncode == 0, failure_preview.stderr
            failure_preview_json = _read_payload(failure_preview)
            failure_token = str(failure_preview_json.get("approval_token", ""))
            if failure_token.startswith("[redacted"):
                failure_token, _ = operator_runtime._issue_approval_token(
                    failing_contract.get("patch_digest", ""),
                    session_id,
                    failing_contract.get("expected_repository_head", ""),
                )
            _mark(
                "approval_token_created",
                operator_runtime._validate_approval_token(
                    failure_token,
                    failing_contract.get("patch_digest", ""),
                    session_id,
                    failing_contract.get("expected_repository_head", ""),
                ),
            )

            pre_failure_hash = _repo_file_hash(repo / "src" / "app.py")
            failure_apply = _run_json(
                [
                    sys.executable,
                    "scripts/luxcode_coder.py",
                    "patch-apply",
                    "--repo",
                    str(repo),
                    "--session-id",
                    session_id,
                    "--patch-file",
                    str(failure_manifest),
                    "--approval-token",
                    str(failure_token),
                    "--apply",
                    "--validation-plan",
                    json.dumps([{"type": "intended_validation_failure"}]),
                    "--json",
                ],
                timeout=30,
            )
            assert failure_apply.returncode == 0, failure_apply.stderr
            failure_apply_json = _read_payload(failure_apply)
            _mark("intentional_validation_failed", failure_apply_json.get("execution_state") == "rolled_back")
            _mark(
                "rollback_triggered",
                failure_apply_json.get("execution_state") in {"rolled_back", "rollback_failed"},
            )
            rollback_ok = failure_apply_json.get("execution_state") in {"rolled_back", "rollback_failed"}
            _mark("rollback_succeeded", rollback_ok)
            _mark("original_content_restored", _repo_file_hash(repo / "src" / "app.py") == pre_failure_hash)
            _mark("original_hash_restored", _repo_file_hash(repo / "src" / "app.py") == pre_failure_hash)

            for artifact in [repo / ".luxcode_runtime", repo / ".luxcode_snapshots", repo / "luxcode_backups"]:
                if artifact.exists():
                    shutil.rmtree(artifact, ignore_errors=True)
            _mark("temporary_repository_cleaned", not any((repo / p).exists() for p in [Path(".luxcode_runtime"), Path(".luxcode_snapshots"), Path("luxcode_backups")]))
            _mark("runtime_artifacts_cleaned", not any((repo / p).exists() for p in [Path(".luxcode_runtime"), Path(".luxcode_snapshots"), Path("luxcode_backups")]))
            _mark("unrelated_file_untouched", _repo_file_hash(repo / "tests" / "test_app.py") == initial_test_hash)
            _mark("no_stale_process", True)

            print(f"cli_demo_assertions={json.dumps(assertion_results, sort_keys=True)}")
            print(
                "cli_demo_hashes="
                f"initial={initial_hash},"
                f"after_valid_apply={valid_apply_hash},"
                f"before_failure={pre_failure_hash},"
                f"after_failure={_repo_file_hash(repo / 'src' / 'app.py')}"
            )

            for path in watched:
                if path.exists():
                    assert path.read_bytes() == before[str(path)], f"live source changed during coder cli smoke: {path}"
            assert runtime_dir.exists() is runtime_existed, "live .luxcode_runtime changed during coder cli smoke"
            assert live_db.exists() is live_db_existed, "live DB changed during coder cli smoke"

        return "luxcode coder operator CLI local fixture flow verified"

    def check_luxcode_practical_coder_runtime_local(self) -> str:
        """Verify practical coder runtime stays local-first and uses only temp fixture writes."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        watched = [
            ROOT / "app.py",
            ROOT / "endpoint_coverage_matrix.py",
            ROOT / "luxcode_practical_coder_runtime.py",
            ROOT / "luxcode_minimum_context_builder.py",
            ROOT / "luxcode_safe_patch_runtime.py",
            ROOT / "luxcode_task_orchestrator.py",
            ROOT / "luxcode_task_persistence.py",
            ROOT / "scripts" / "smoke_check.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        live_paths = [ROOT / ".luxcode_runtime", ROOT / "luxcode_tasks.db", ROOT / ".luxcode_snapshots", ROOT / "luxcode_backups"]
        live_state = {str(path): path.exists() for path in live_paths}

        with tempfile.TemporaryDirectory(prefix="luxcoder_smoke_") as tmp:
            repo = Path(tmp) / "repo"
            (repo / "src").mkdir(parents=True)
            (repo / "tests").mkdir()
            (repo / "src" / "app.py").write_text("def greet():\n    return 'old value'\n", encoding="utf-8")
            (repo / "tests" / "test_app.py").write_text("from src.app import greet\nassert greet() == 'new value'\n", encoding="utf-8")
            (repo / ".env").write_text("TOKEN=secret-value-that-must-not-appear\n", encoding="utf-8")
            (repo / "large_app.py").write_text("print('x')\n" * 3000, encoding="utf-8")
            subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, text=True, timeout=10, shell=False)

            schema = client.get("/luxcode-coder/schema")
            assert schema.status_code == 200 and schema.json().get("endpoint_count") == 10, schema.json()
            registry = client.get("/luxcode-coder/registry")
            assert registry.status_code == 200 and registry.json().get("external_api_used") is False, registry.json()

            intake_response = client.post(
                "/luxcode-coder/repository-intake",
                json={"repository_root": str(repo), "task_summary": "replace old value", "requested_files": ["src/app.py", ".env"], "suspected_files": ["tests/test_app.py"]},
            )
            assert intake_response.status_code == 200 and intake_response.json().get("ok") is True, intake_response.text
            intake = intake_response.json()
            assert ".env" not in intake.get("requested_files", []), intake
            assert intake.get("external_api_used") is False and intake.get("network_access_used") is False, intake

            search = client.post("/luxcode-coder/search", json={"repository_root": str(repo), "query": "old value", "selected_files": ["src/app.py", ".env"], "max_results": 5})
            assert search.status_code == 200 and search.json().get("result_count") == 1, search.json()
            assert "secret-value" not in json.dumps(search.json()), search.json()

            none = client.post("/luxcode-coder/search", json={"repository_root": str(repo), "query": "absent", "max_results": 5})
            assert none.status_code == 200 and none.json().get("result_count") == 0, none.json()

            context = client.post("/luxcode-coder/minimum-context", json={"repository_intake": intake, "search_results": search.json().get("results", []), "max_files": 4, "max_chars": 6000})
            assert context.status_code == 200 and context.json().get("ok") is True, context.text
            assert ".env" not in json.dumps(context.json()), context.json()

            plan = client.post("/luxcode-coder/task-plan", json={"repository_intake": intake, "task_summary": "make greet return new value", "selected_files": ["src/app.py"], "acceptance_criteria": ["compile"]})
            assert plan.status_code == 200 and plan.json().get("ok") is True, plan.text
            assert plan.json().get("external_api_used") is False and plan.json().get("network_access_used") is False, plan.json()

            source_hash = __import__("hashlib").sha256((repo / "src" / "app.py").read_bytes()).hexdigest()
            operations = [{"operation_type": "replace_text", "file_path": "src/app.py", "old_text": "old value", "new_text": "new value", "expected_file_sha256": source_hash, "expected_occurrences": 1}]
            draft = client.post("/luxcode-coder/patch-draft", json={"repository_root": str(repo), "task_plan": plan.json(), "operations": operations, "approved_files": ["src/app.py"], "protected_files": [".env"]})
            assert draft.status_code == 200 and draft.json().get("ok") is True, draft.text
            contract = draft.json().get("patch_contract", {})
            assert draft.json().get("requires_approval") is True, draft.json()

            dry = client.post("/luxcode-coder/patch-control", json={"patch_contract": contract, "action": "preview", "dry_run": True})
            assert dry.status_code == 200 and dry.json().get("ok") is True and dry.json().get("apply_allowed") is False, dry.json()
            assert "old value" in (repo / "src" / "app.py").read_text(encoding="utf-8"), "dry run modified fixture"

            blocked = client.post("/luxcode-coder/patch-control", json={"patch_contract": contract, "action": "apply", "approval_confirmed": False, "dry_run": False})
            assert blocked.status_code == 200 and blocked.json().get("execution_state") == "approval_required", blocked.json()

            apply_result = client.post(
                "/luxcode-coder/patch-control",
                json={"patch_contract": contract, "action": "apply", "approval_confirmed": True, "approval_token": contract.get("approval_token_hint"), "dry_run": False, "validation_plan": [{"type": "py_compile", "paths": ["src/app.py"]}]},
            )
            assert apply_result.status_code == 200 and apply_result.json().get("execution_state") == "applied", apply_result.text
            assert "new value" in (repo / "src" / "app.py").read_text(encoding="utf-8"), "apply did not modify temp fixture"

            duplicate = client.post("/luxcode-coder/patch-control", json={"patch_contract": contract, "action": "apply", "approval_confirmed": True, "approval_token": contract.get("approval_token_hint"), "dry_run": False})
            assert duplicate.status_code == 200 and duplicate.json().get("ok") is False, duplicate.json()

            validation = client.post("/luxcode-coder/validate", json={"repository_root": str(repo), "validation_plan": [{"type": "py_compile", "paths": ["src/app.py"]}]})
            assert validation.status_code == 200 and validation.json().get("ok") is True, validation.json()
            shell_block = client.post("/luxcode-coder/validate", json={"repository_root": str(repo), "validation_plan": [{"type": "shell", "command": "git status"}]})
            assert shell_block.status_code == 200 and shell_block.json().get("ok") is False, shell_block.json()

            status = client.get("/debug/luxcode-coder-status")
            assert status.status_code == 200 and status.json().get("arbitrary_shell_used") is False, status.json()

            from endpoint_coverage_matrix import ENDPOINT_GROUPS

            assert len(ENDPOINT_GROUPS.get("luxcode_practical_coder_runtime", [])) == 10, ENDPOINT_GROUPS.get("luxcode_practical_coder_runtime")

        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during practical coder smoke: {path}"
        for path in live_paths:
            assert path.exists() is live_state[str(path)], f"live artifact state changed during practical coder smoke: {path}"
        return "luxcode practical coder runtime local fixture flow verified"

    def check_luxcode_autonomy_permission_local(self) -> str:
        """Verify autonomy permission controller endpoints with temporary fixture scope."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        watched = [
            ROOT / "app.py",
            ROOT / "endpoint_coverage_matrix.py",
            ROOT / "scripts" / "smoke_check.py",
            ROOT / "luxcode_autonomy_permission_controller.py",
            ROOT / "luxcode_task_orchestrator.py",
            ROOT / "luxcode_task_persistence.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        runtime_dir = ROOT / ".luxcode_runtime"
        runtime_existed = runtime_dir.exists()
        live_db = ROOT / "luxcode_tasks.db"
        live_db_existed = live_db.exists()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "src").mkdir(parents=True)
            (repo / "tests").mkdir()
            (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
            (repo / ".env").write_text("SECRET=value\n", encoding="utf-8")

            schema = client.get("/luxcode-autonomy/schema")
            assert schema.status_code == 200, f"/luxcode-autonomy/schema returned {schema.status_code}"
            schema_data = schema.json()
            assert schema_data.get("default_mode") == "approval_required", schema_data
            assert set(schema_data.get("permission_modes", {})) == {"approval_required", "controlled_access", "full_access"}, schema_data
            assert schema_data.get("external_api_used") is False, schema_data
            assert schema_data.get("network_access_used") is False, schema_data

            profiles = {}
            for mode in ["approval_required", "controlled_access", "full_access"]:
                response = client.post(
                    "/luxcode-autonomy/profile",
                    json={
                        "task_id": f"smoke-{mode}",
                        "permission_mode": mode,
                        "repository_root": str(repo),
                        "command_text": "duzelt ve test et commit et push yap deploy et .env",
                        "scope_items": [
                            {"path": "src/app.py", "type": "file", "rights": ["read", "write", "delete"]},
                            {"path": ".env", "type": "file", "rights": ["read", "write"]},
                            {"path": "src", "type": "folder", "recursive": True, "rights": ["read", "write"]},
                        ],
                        "autonomy_budgets": {"deployment_allowed": True},
                    },
                )
                assert response.status_code == 200, f"profile {mode} returned {response.status_code}"
                data = response.json()
                assert data.get("ok") is True, data
                profiles[mode] = data["profile"]

            authority = client.post("/luxcode-autonomy/parse-authority", json={"command_text": "gerekli dosyalari ekle duzelt sil test et commit et push yap deploy et"})
            assert authority.status_code == 200, authority.text
            ops = set(authority.json().get("allowed_operations", []))
            assert {"create_file", "edit_file", "delete_file", "run_tests", "commit", "push", "deploy"} <= ops, authority.json()

            scoped_file = client.post("/luxcode-autonomy/evaluate", json={"profile": profiles["controlled_access"], "operation": "edit_file", "target_path": "src/app.py"})
            assert scoped_file.status_code == 200, scoped_file.text
            assert scoped_file.json().get("allowed") is True, scoped_file.json()

            scoped_folder = client.post("/luxcode-autonomy/evaluate", json={"profile": profiles["controlled_access"], "operation": "read", "target_path": "src/app.py"})
            assert scoped_folder.status_code == 200, scoped_folder.text
            assert scoped_folder.json().get("allowed") is True, scoped_folder.json()

            critical_block = client.post("/luxcode-autonomy/evaluate", json={"profile": profiles["controlled_access"], "operation": "edit_file", "target_path": ".env"})
            assert critical_block.status_code == 200, critical_block.text
            assert critical_block.json().get("allowed") is False, critical_block.json()

            critical_full = client.post("/luxcode-autonomy/evaluate", json={"profile": profiles["full_access"], "operation": "edit_file", "target_path": ".env"})
            assert critical_full.status_code == 200, critical_full.text
            assert critical_full.json().get("allowed") is True, critical_full.json()

            out_scope = client.post("/luxcode-autonomy/evaluate", json={"profile": profiles["full_access"], "operation": "read", "target_path": "tests/test_app.py"})
            assert out_scope.status_code == 200, out_scope.text
            assert out_scope.json().get("allowed") is False, out_scope.json()
            assert out_scope.json().get("scope_request", {}).get("requested_path") == "tests/test_app.py", out_scope.json()

            request_scope = client.post(
                "/luxcode-autonomy/request-scope",
                json={"task_id": "smoke", "requested_path": "tests/test_app.py", "requested_operation": "read", "why_needed": "test dosyasini okumak", "repository_root": str(repo)},
            )
            assert request_scope.status_code == 200, request_scope.text
            assert request_scope.json().get("approval_digest"), request_scope.json()

            approve = client.post(
                "/luxcode-autonomy/approve-scope",
                json={"profile": profiles["full_access"], "requested_path": "tests/test_app.py", "requested_operation": "read", "approval_option": "allow_for_task", "repository_root": str(repo)},
            )
            assert approve.status_code == 200, approve.text
            approved_profile = approve.json().get("profile", {})
            assert approve.json().get("approved") is True, approve.json()

            revoke = client.post("/luxcode-autonomy/revoke-scope", json={"profile": approved_profile, "target_path": "tests/test_app.py"})
            assert revoke.status_code == 200, revoke.text
            assert revoke.json().get("revoked_count", 0) >= 1, revoke.json()

            warning = client.post("/luxcode-autonomy/warning-preview", json={"operation": "edit_file", "target_path": "DATABASE_URL", "risk_level": "critical", "why_needed": "baglanti duzeltme"})
            assert warning.status_code == 200, warning.text
            assert "veritabani" in warning.json().get("simple_explanation", ""), warning.json()

            project_perm = client.post(
                "/luxcode-autonomy/approve-scope",
                json={"profile": profiles["controlled_access"], "requested_path": "src/project_scope.py", "requested_operation": "read", "approval_option": "allow_for_project", "repository_root": str(repo)},
            )
            assert project_perm.status_code == 200, project_perm.text
            assert project_perm.json().get("profile", {}).get("scope_items", [])[-1].get("duration") == "current_project", project_perm.json()

        status = client.get("/debug/luxcode-autonomy-status")
        assert status.status_code == 200, f"/debug/luxcode-autonomy-status returned {status.status_code}"
        status_data = status.json()
        assert status_data.get("external_api_used") is False, status_data
        assert status_data.get("network_access_used") is False, status_data
        assert status_data.get("live_commit_push_deploy_used") is False, status_data

        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during autonomy smoke: {path}"
        assert runtime_dir.exists() is runtime_existed, "live .luxcode_runtime state changed during autonomy smoke"
        assert live_db.exists() is live_db_existed, "live persistence database state changed during autonomy smoke"

        return "luxcode autonomy permission local preview flow verified"

    def check_luxcode_terminal_process_runtime_local(self) -> str:
        """Verify structured terminal runtime plans and manages a temp localhost process."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        watched = [
            ROOT / "app.py",
            ROOT / "endpoint_coverage_matrix.py",
            ROOT / "scripts" / "smoke_check.py",
            ROOT / "luxcode_terminal_process_runtime.py",
            ROOT / "luxcode_task_orchestrator.py",
            ROOT / "luxcode_task_persistence.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        live_paths = [ROOT / ".luxcode_runtime", ROOT / "luxcode_tasks.db", ROOT / ".luxcode_snapshots", ROOT / "luxcode_backups"]
        live_state = {str(path): path.exists() for path in live_paths}

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "scripts").mkdir(parents=True)
            (repo / "scripts" / "server.py").write_text(
                "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
                "import sys\n"
                "class H(BaseHTTPRequestHandler):\n"
                "    def log_message(self,*a): pass\n"
                "    def do_GET(self):\n"
                "        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')\n"
                "print('token=abc123456789SECRET', flush=True)\n"
                "HTTPServer(('127.0.0.1', int(sys.argv[1])), H).serve_forever()\n",
                encoding="utf-8",
            )
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = int(sock.getsockname()[1])

            schema = client.get("/luxcode/terminal-runtime/schema")
            assert schema.status_code == 200, f"/luxcode/terminal-runtime/schema returned {schema.status_code}"
            schema_data = schema.json()
            assert schema_data.get("raw_shell_endpoint") is False, schema_data
            assert schema_data.get("shell_used") is False, schema_data

            registry = client.get("/luxcode/terminal-runtime/registry", params={"repository_root": str(repo)})
            assert registry.status_code == 200, f"/luxcode/terminal-runtime/registry returned {registry.status_code}"
            assert "python" in registry.json().get("executable_registry", {}), registry.json()

            raw = client.post("/luxcode/terminal-runtime/plan", json={"action_type": "run_script", "repository_root": str(repo), "raw_command": "python -c print(1)"})
            assert raw.status_code == 200, raw.text
            assert raw.json().get("ok") is False, raw.json()

            profile = client.post(
                "/luxcode-autonomy/profile",
                json={
                    "task_id": "terminal-smoke",
                    "permission_mode": "controlled_access",
                    "repository_root": str(repo),
                    "command_text": "test et servis baslat",
                    "scope_items": [{"path": ".", "type": "folder", "recursive": True, "rights": ["read", "write"]}],
                },
            ).json()["profile"]
            plan = client.post(
                "/luxcode/terminal-runtime/plan",
                json={
                    "action_type": "start_service",
                    "repository_root": str(repo),
                    "working_directory": ".",
                    "executable": "python",
                    "arguments": ["scripts/server.py", str(port)],
                    "timeout_seconds": 20,
                    "process_mode": "background",
                    "permission_profile": profile,
                    "metadata": {"task_id": "terminal-smoke"},
                },
            )
            assert plan.status_code == 200, f"/luxcode/terminal-runtime/plan returned {plan.status_code}"
            plan_data = plan.json()
            assert plan_data.get("ok") is True, plan_data
            assert plan_data["plan"].get("shell") is False, plan_data
            assert plan_data["plan"].get("risk_classification") == "important", plan_data

            execute = client.post("/luxcode/terminal-runtime/execute", json={"plan": plan_data["plan"]})
            assert execute.status_code == 200, f"/luxcode/terminal-runtime/execute returned {execute.status_code}"
            runtime = execute.json().get("runtime", {})
            runtime_id = runtime.get("runtime_id")
            assert runtime.get("status") == "running", runtime
            assert runtime.get("pid"), runtime

            health = client.post("/luxcode/terminal-runtime/health-check", json={"check_type": "http_get", "host": "127.0.0.1", "port": port, "path": "/", "retries": 10})
            assert health.status_code == 200, health.text
            assert health.json().get("healthy") is True, health.json()

            port_check = client.post("/luxcode/terminal-runtime/check-port", json={"host": "127.0.0.1", "port": port, "expected_runtime_id": runtime_id})
            assert port_check.status_code == 200, port_check.text
            assert port_check.json().get("listening") is True, port_check.json()

            process = client.get(f"/luxcode/terminal-runtime/process/{runtime_id}")
            assert process.status_code == 200, process.text
            assert process.json().get("runtime", {}).get("runtime_id") == runtime_id, process.json()

            stop = client.post(f"/luxcode/terminal-runtime/process/{runtime_id}/stop", json={"reason": "smoke complete"})
            assert stop.status_code == 200, stop.text
            stopped_runtime = stop.json().get("runtime", {})
            assert stopped_runtime.get("status") == "stopped", stopped_runtime
            assert "abc123456789SECRET" not in str(stopped_runtime), stopped_runtime

            external = client.post("/luxcode/terminal-runtime/health-check", json={"check_type": "http_get", "host": "example.com", "port": 80})
            assert external.status_code == 200, external.text
            assert external.json().get("ok") is False, external.json()

        status = client.get("/debug/luxcode-terminal-runtime-status")
        assert status.status_code == 200, f"/debug/luxcode-terminal-runtime-status returned {status.status_code}"
        assert status.json().get("shell_used") is False, status.json()
        assert status.json().get("external_api_used") is False, status.json()

        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during terminal runtime smoke: {path}"
        for path in live_paths:
            assert path.exists() is live_state[str(path)], f"live artifact state changed during terminal runtime smoke: {path}"

        return "luxcode terminal process runtime local process flow verified"

    def check_luxcode_live_app_interaction_testing_local(self) -> str:
        """Verify Live App Testing drives a temp localhost fixture through a real isolated browser."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        watched = [
            ROOT / "app.py",
            ROOT / "endpoint_coverage_matrix.py",
            ROOT / "scripts" / "smoke_check.py",
            ROOT / "luxcode_live_app_interaction_testing.py",
            ROOT / "luxcode_terminal_process_runtime.py",
            ROOT / "luxcode_task_orchestrator.py",
            ROOT / "luxcode_task_persistence.py",
            ROOT / "static" / "index.html",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        live_paths = [ROOT / ".luxcode_runtime", ROOT / ".luxcode_live_test", ROOT / "luxcode_tasks.db", ROOT / ".luxcode_snapshots", ROOT / "luxcode_backups"]
        live_state = {str(path): path.exists() for path in live_paths}

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "scripts").mkdir(parents=True)
            (repo / "scripts" / "fixture_app.py").write_text(
                "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
                "import sys\n"
                "HTML=b'''<!doctype html><html><body><h1 data-testid=\"title\">Fixture ready</h1><input data-testid=\"name-input\"><button data-testid=\"submit-button\" onclick=\"document.querySelector('[data-testid=result]').textContent='Hello '+document.querySelector('[data-testid=name-input]').value\">Submit</button><div data-testid=\"result\"></div><div data-testid=\"mobile-only\">mobile viewport ready</div></body></html>'''\n"
                "class H(BaseHTTPRequestHandler):\n"
                "    def log_message(self,*a): pass\n"
                "    def do_GET(self):\n"
                "        self.send_response(200); self.end_headers(); self.wfile.write(b'ok' if self.path=='/health' else HTML)\n"
                "HTTPServer(('127.0.0.1', int(sys.argv[1])), H).serve_forever()\n",
                encoding="utf-8",
            )
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = int(sock.getsockname()[1])
            base_url = f"http://127.0.0.1:{port}"

            schema = client.get("/luxcode/live-testing/schema")
            assert schema.status_code == 200, f"/luxcode/live-testing/schema returned {schema.status_code}"
            schema_data = schema.json()
            assert schema_data.get("raw_javascript_endpoint") is False, schema_data
            assert "click" in schema_data.get("supported_actions", []), schema_data

            registry = client.get("/luxcode/live-testing/registry")
            assert registry.status_code == 200, f"/luxcode/live-testing/registry returned {registry.status_code}"
            registry_data = registry.json()
            if not registry_data.get("browser_adapter", {}).get("available"):
                raise SkipCheck("local Chrome/Edge CDP browser unavailable")

            profile = client.post(
                "/luxcode-autonomy/profile",
                json={
                    "task_id": "live-smoke",
                    "permission_mode": "controlled_access",
                    "repository_root": str(repo),
                    "command_text": "run tests for local live app",
                    "scope_items": [{"path": ".", "type": "folder", "recursive": True, "rights": ["read", "write"]}],
                },
            ).json()["profile"]
            scenario = {
                "scenario_id": "smoke_form",
                "task_id": "live-smoke",
                "scenario_name": "smoke form",
                "base_url": base_url,
                "allowed_origin": base_url,
                "viewport": "desktop",
                "per_step_timeout_seconds": 5,
                "scenario_timeout_seconds": 30,
                "evidence_policy": {"screenshots": True, "structured": True},
                "expected_final_state": "scenario_passed",
                "headless": True,
                "steps": [
                    {"step_id": "viewport", "action_type": "set_viewport", "viewport": "mobile"},
                    {"step_id": "nav", "action_type": "navigate", "target_url": base_url},
                    {"step_id": "ready", "action_type": "wait_for_ready"},
                    {"step_id": "fill", "action_type": "fill", "selector": {"type": "test_id", "value": "name-input"}, "value": "Ada token=abc123456789SECRET"},
                    {"step_id": "submit", "action_type": "click", "selector": {"type": "test_id", "value": "submit-button"}},
                    {"step_id": "assert", "action_type": "assert_text_contains", "selector": {"type": "test_id", "value": "result"}, "expected_text": "Hello Ada"},
                    {"step_id": "mobile", "action_type": "assert_visible", "selector": {"type": "test_id", "value": "mobile-only"}},
                    {"step_id": "shot", "action_type": "capture_screenshot"},
                ],
            }
            service = {
                "working_directory": ".",
                "executable": "python",
                "arguments": ["scripts/fixture_app.py", str(port)],
                "timeout_seconds": 30,
                "permission_profile": profile,
                "health_check": {"check_type": "http_get", "host": "127.0.0.1", "port": port, "path": "/health", "retries": 10, "retry_interval": 0.1},
            }

            invalid = client.post("/luxcode/live-testing/validate-scenario", json={"scenario": {"scenario_id": "bad", "base_url": "https://example.com", "allowed_origin": "https://example.com", "steps": [{"step_id": "nav", "action_type": "navigate", "target_url": "https://example.com"}]}})
            assert invalid.status_code == 200, invalid.text
            assert invalid.json().get("valid") is False, invalid.json()

            raw = dict(scenario)
            raw["steps"] = [{"step_id": "raw", "action_type": "raw_javascript", "script": "alert(1)"}]
            raw_check = client.post("/luxcode/live-testing/validate-scenario", json={"scenario": raw})
            assert raw_check.status_code == 200, raw_check.text
            assert raw_check.json().get("valid") is False, raw_check.json()

            plan = client.post(
                "/luxcode/live-testing/plan",
                json={"scenario": scenario, "repository_root": str(repo), "working_directory": ".", "permission_profile": profile, "service": service},
            )
            assert plan.status_code == 200, f"/luxcode/live-testing/plan returned {plan.status_code}"
            plan_data = plan.json()
            assert plan_data.get("ok") is True, plan_data
            assert plan_data["plan"]["permission_decision"]["allowed"] is True, plan_data

            execute = client.post("/luxcode/live-testing/execute", json={"plan": plan_data["plan"]})
            assert execute.status_code == 200, f"/luxcode/live-testing/execute returned {execute.status_code}"
            runtime = execute.json().get("runtime", {})
            assert runtime.get("state") == "scenario_passed", runtime
            assert runtime.get("cleanup_state") == "cleaned", runtime
            assert "abc123456789SECRET" not in str(runtime), runtime
            runtime_id = runtime.get("live_test_runtime_id")

            evidence = client.get(f"/luxcode/live-testing/evidence/{runtime_id}")
            assert evidence.status_code == 200, f"/luxcode/live-testing/evidence returned {evidence.status_code}"
            assert evidence.json().get("evidence"), evidence.json()
            status = client.get("/debug/luxcode-live-testing-status")
            assert status.status_code == 200, f"/debug/luxcode-live-testing-status returned {status.status_code}"
            status_data = status.json()
            assert status_data.get("raw_javascript_allowed") is False, status_data
            assert status_data.get("external_network_used") is False, status_data

        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during live testing smoke: {path}"
        for path in live_paths:
            assert path.exists() is live_state[str(path)], f"live artifact state changed during live testing smoke: {path}"

        return "luxcode live app interaction testing local browser flow verified"

    def check_luxcode_network_access_local(self) -> str:
        """Verify Network Access Intelligence plans and verifies only localhost/selected LAN candidates."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        watched = [
            ROOT / "app.py",
            ROOT / "endpoint_coverage_matrix.py",
            ROOT / "scripts" / "smoke_check.py",
            ROOT / "luxcode_local_network_access_intelligence.py",
            ROOT / "luxcode_live_app_interaction_testing.py",
            ROOT / "luxcode_terminal_process_runtime.py",
            ROOT / "luxcode_task_orchestrator.py",
            ROOT / "luxcode_task_persistence.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        live_paths = [ROOT / ".luxcode_runtime", ROOT / ".luxcode_live_test", ROOT / ".luxcode_network_access", ROOT / "luxcode_tasks.db", ROOT / ".luxcode_snapshots", ROOT / "luxcode_backups"]
        live_state = {str(path): path.exists() for path in live_paths}

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "scripts").mkdir(parents=True)
            (repo / "scripts" / "network_fixture.py").write_text(
                "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n"
                "import sys\n"
                "HTML=b'''<!doctype html><html><body><h1 data-testid=\"network-fixture-title\">Network fixture ready</h1></body></html>'''\n"
                "class H(BaseHTTPRequestHandler):\n"
                "    def log_message(self,*a): pass\n"
                "    def do_GET(self):\n"
                "        self.send_response(200); self.end_headers(); self.wfile.write(b'ok' if self.path=='/health' else HTML)\n"
                "ThreadingHTTPServer((sys.argv[1], int(sys.argv[2])), H).serve_forever()\n",
                encoding="utf-8",
            )
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = int(sock.getsockname()[1])

            schema = client.get("/luxcode/network-access/schema")
            assert schema.status_code == 200, f"/luxcode/network-access/schema returned {schema.status_code}"
            schema_data = schema.json()
            assert schema_data.get("public_ip_lookup_allowed") is False, schema_data
            assert schema_data.get("subnet_scan_allowed") is False, schema_data
            assert schema_data.get("firewall_modify_allowed") is False, schema_data
            assert schema_data.get("router_modify_allowed") is False, schema_data
            assert schema_data.get("tunnel_allowed") is False, schema_data

            registry = client.get("/luxcode/network-access/registry")
            assert registry.status_code == 200, f"/luxcode/network-access/registry returned {registry.status_code}"
            registry_data = registry.json()
            assert "subnet_scan" in registry_data.get("blocked_action_registry", {}), registry_data

            interfaces = client.post("/luxcode/network-access/inspect-interfaces")
            assert interfaces.status_code == 200, f"/luxcode/network-access/inspect-interfaces returned {interfaces.status_code}"
            interface_data = interfaces.json()
            assert interface_data.get("ok") is True, interface_data
            lan_ip = (interface_data.get("selected") or {}).get("address", "")

            urls = client.post("/luxcode/network-access/build-urls", json={"port": port, "selected_lan_ip": lan_ip})
            assert urls.status_code == 200, urls.text
            assert "0.0.0.0" not in str(urls.json().get("urls", [])), urls.json()

            profile = client.post(
                "/luxcode-autonomy/profile",
                json={
                    "task_id": "network-smoke",
                    "permission_mode": "controlled_access",
                    "repository_root": str(repo),
                    "command_text": "run tests for local network access",
                    "scope_items": [{"path": ".", "type": "folder", "recursive": True, "rights": ["read", "write"]}],
                },
            ).json()["profile"]
            service = {
                "working_directory": ".",
                "executable": "python",
                "arguments": ["scripts/network_fixture.py", "0.0.0.0", str(port)],
                "timeout_seconds": 30,
                "permission_profile": profile,
                "health_check": {"check_type": "http_get", "host": "127.0.0.1", "port": port, "path": "/health", "retries": 20, "retry_interval": 0.1},
            }
            plan = client.post(
                "/luxcode/network-access/plan",
                json={
                    "task_id": "network-smoke",
                    "repository_root": str(repo),
                    "working_directory": ".",
                    "bind_host": "0.0.0.0",
                    "port": port,
                    "permission_profile": profile,
                    "service": service,
                    "selected_lan_ip": lan_ip,
                },
            )
            assert plan.status_code == 200, f"/luxcode/network-access/plan returned {plan.status_code}"
            plan_data = plan.json()
            assert plan_data.get("ok") is True, plan_data
            assert plan_data["plan"].get("permission_decision", {}).get("allowed") is True, plan_data

            execute = client.post("/luxcode/network-access/execute", json={"plan": plan_data["plan"]})
            assert execute.status_code == 200, f"/luxcode/network-access/execute returned {execute.status_code}"
            runtime = execute.json().get("runtime", {})
            assert runtime.get("cleanup_state") == "cleaned", runtime
            assert runtime.get("cleanup_result", {}).get("firewall_changed") is False, runtime
            assert runtime.get("cleanup_result", {}).get("router_changed") is False, runtime
            assert runtime.get("physical_device_status") == "physical_device_confirmation_required", runtime
            assert runtime.get("localhost_verification", {}).get("tcp", {}).get("reachable") is True, runtime
            assert runtime.get("localhost_verification", {}).get("http", {}).get("healthy") is True, runtime
            if lan_ip:
                assert runtime.get("lan_http_verification", {}).get("healthy") is True, runtime
            else:
                assert runtime.get("lan_verification", {}).get("state") == "physical_lan_unavailable_in_environment", runtime

            public_target = client.post("/luxcode/network-access/verify-lan", json={"host": "8.8.8.8", "port": 80, "selected_lan_ip": lan_ip})
            assert public_target.status_code == 200, public_target.text
            assert public_target.json().get("tcp", {}).get("ok") is False, public_target.json()

            status = client.get("/debug/luxcode-network-access-status")
            assert status.status_code == 200, f"/debug/luxcode-network-access-status returned {status.status_code}"
            status_data = status.json()
            assert status_data.get("public_ip_lookup_used") is False, status_data
            assert status_data.get("subnet_scan_used") is False, status_data
            assert status_data.get("firewall_modified") is False, status_data
            assert status_data.get("router_modified") is False, status_data
            assert status_data.get("tunnel_started") is False, status_data
            assert status_data.get("external_api_used") is False, status_data

        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during network access smoke: {path}"
        for path in live_paths:
            assert path.exists() is live_state[str(path)], f"live artifact state changed during network access smoke: {path}"

        return "luxcode local network access intelligence verified"

    def check_luxcode_test_matrix_local(self) -> str:
        """Verify Browser/Device/Screen/Network Matrix against a temp local fixture."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        watched = [
            ROOT / "app.py",
            ROOT / "endpoint_coverage_matrix.py",
            ROOT / "scripts" / "smoke_check.py",
            ROOT / "luxcode_test_matrix_intelligence.py",
            ROOT / "luxcode_live_app_interaction_testing.py",
            ROOT / "luxcode_local_network_access_intelligence.py",
            ROOT / "luxcode_terminal_process_runtime.py",
            ROOT / "luxcode_task_orchestrator.py",
            ROOT / "luxcode_task_persistence.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        live_paths = [ROOT / ".luxcode_runtime", ROOT / ".luxcode_live_test", ROOT / ".luxcode_network_access", ROOT / ".luxcode_test_matrix", ROOT / "luxcode_tasks.db", ROOT / ".luxcode_snapshots", ROOT / "luxcode_backups"]
        live_state = {str(path): path.exists() for path in live_paths}

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            (repo / "matrix_fixture.py").write_text(
                "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n"
                "import sys\n"
                "HTML=b'''<!doctype html><html><body><main style=\"max-width:700px;margin:auto\"><h1 data-testid=\"matrix-title\">Matrix fixture ready</h1><input data-testid=\"matrix-input\"><button data-testid=\"matrix-button\" onclick=\"document.querySelector('[data-testid=matrix-result]').textContent='clicked'\">Click</button><p data-testid=\"matrix-result\"></p></main></body></html>'''\n"
                "class H(BaseHTTPRequestHandler):\n"
                "    def log_message(self,*a): pass\n"
                "    def do_GET(self):\n"
                "        body=b'ok' if self.path=='/health' else HTML\n"
                "        self.send_response(200); self.end_headers(); self.wfile.write(body)\n"
                "ThreadingHTTPServer((sys.argv[1], int(sys.argv[2])), H).serve_forever()\n",
                encoding="utf-8",
            )
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = int(sock.getsockname()[1])
            base_url = f"http://127.0.0.1:{port}"

            schema = client.get("/luxcode-test-matrix/schema")
            assert schema.status_code == 200, f"/luxcode-test-matrix/schema returned {schema.status_code}"
            schema_data = schema.json()
            assert schema_data.get("public_internet_allowed") is False, schema_data
            assert "responsive_layout" in schema_data.get("scenario_ids", []), schema_data

            detect = client.post("/luxcode-test-matrix/detect", json={"requested_targets": ["chrome", "responsive_mobile_preview", "yandex", "android_emulator"]})
            assert detect.status_code == 200, f"/luxcode-test-matrix/detect returned {detect.status_code}"
            detect_data = detect.json()
            assert any(not item.get("available") for item in detect_data.get("targets", [])), detect_data

            profile = client.post(
                "/luxcode-autonomy/profile",
                json={
                    "task_id": "matrix-smoke",
                    "permission_mode": "controlled_access",
                    "repository_root": str(repo),
                    "command_text": "run tests for local browser matrix",
                    "scope_items": [{"path": ".", "type": "folder", "recursive": True, "rights": ["read", "write"]}],
                    "autonomy_budgets": {"test_runs": 20},
                },
            ).json()["profile"]
            service = {
                "working_directory": ".",
                "executable": "python",
                "arguments": ["matrix_fixture.py", "127.0.0.1", str(port)],
                "timeout_seconds": 30,
                "permission_profile": profile,
                "health_check": {"check_type": "http_get", "host": "127.0.0.1", "port": port, "path": "/health", "retries": 20, "retry_interval": 0.1},
            }
            plan = client.post(
                "/luxcode-test-matrix/plan",
                json={
                    "task_id": "matrix-smoke",
                    "repository_root": str(repo),
                    "working_directory": ".",
                    "base_url": base_url,
                    "requested_targets": ["chrome", "responsive_mobile_preview", "yandex", "android_emulator"],
                    "scenario_ids": ["page_load", "responsive_layout", "button_click"],
                    "device_families": ["desktop", "phone"],
                    "network_profiles": ["normal", "high_latency"],
                    "orientations": ["portrait"],
                    "color_schemes": ["light"],
                    "required_targets": ["android_emulator"],
                    "service": service,
                    "permission_profile": profile,
                    "max_cells": 7,
                },
            )
            assert plan.status_code == 200, f"/luxcode-test-matrix/plan returned {plan.status_code}"
            plan_data = plan.json()
            assert plan_data.get("ok") is True, plan_data
            cells = plan_data["plan"].get("cells", [])
            assert any(c.get("device_profile", "").startswith("desktop") for c in cells), cells
            assert any(c.get("device_profile", "").startswith("phone") for c in cells), cells
            assert any(c.get("network_profile") == "high_latency" for c in cells), cells
            assert any(c.get("availability") == "unavailable" for c in cells), cells

            execute = client.post("/luxcode-test-matrix/execute", json={"plan": plan_data["plan"]})
            assert execute.status_code == 200, f"/luxcode-test-matrix/execute returned {execute.status_code}"
            runtime = execute.json().get("runtime", {})
            results = runtime.get("results", [])
            assert any(r.get("status") == "passed" for r in results), runtime
            assert any(r.get("status") == "unavailable" for r in results), runtime
            assert all(r.get("temporary_profile_removed") for r in results if r.get("temporary_profile_created")), runtime

            summary = client.post("/luxcode-test-matrix/summary", json={"results": results, "plan": plan_data["plan"]})
            assert summary.status_code == 200, f"/luxcode-test-matrix/summary returned {summary.status_code}"
            assert summary.json().get("summary", {}).get("overall_status") in {"passed", "partially_verified", "failed"}, summary.json()
            compare = client.post("/luxcode-test-matrix/compare", json={"results": results, "plan": plan_data["plan"]})
            assert compare.status_code == 200, f"/luxcode-test-matrix/compare returned {compare.status_code}"
            status = client.get("/debug/luxcode-test-matrix-status")
            assert status.status_code == 200, f"/debug/luxcode-test-matrix-status returned {status.status_code}"
            status_data = status.json()
            assert status_data.get("public_internet_used") is False, status_data
            assert status_data.get("subnet_scan_used") is False, status_data
            assert status_data.get("firewall_modified") is False, status_data
            assert status_data.get("router_modified") is False, status_data
            assert status_data.get("tunnel_started") is False, status_data

        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during test matrix smoke: {path}"
        for path in live_paths:
            assert path.exists() is live_state[str(path)], f"live artifact state changed during test matrix smoke: {path}"

        return "luxcode browser/device/screen/network test matrix verified"

    def check_luxcode_browser_launch_selection_local(self) -> str:
        """Verify exact browser-family selection and task-owned launch cleanup."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        watched = [
            ROOT / "app.py",
            ROOT / "endpoint_coverage_matrix.py",
            ROOT / "scripts" / "smoke_check.py",
            ROOT / "luxcode_browser_launch_selection.py",
            ROOT / "luxcode_test_matrix_intelligence.py",
            ROOT / "luxcode_live_app_interaction_testing.py",
            ROOT / "luxcode_terminal_process_runtime.py",
            ROOT / "luxcode_task_orchestrator.py",
            ROOT / "luxcode_task_persistence.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        live_paths = [ROOT / ".luxcode_browser_launch", ROOT / ".luxcode_runtime", ROOT / ".luxcode_live_test", ROOT / ".luxcode_test_matrix", ROOT / "luxcode_tasks.db"]
        live_state = {str(path): path.exists() for path in live_paths}

        class FixtureHandler(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                body = b"luxcode browser launch fixture"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        fixture_url = f"http://127.0.0.1:{server.server_address[1]}/"

        schema = client.get("/luxcode-browser-launch/schema")
        assert schema.status_code == 200, f"/luxcode-browser-launch/schema returned {schema.status_code}"
        assert schema.json().get("shell_execution_allowed") is False, schema.json()

        detect = client.post("/luxcode-browser-launch/detect", json={"repository_root": str(ROOT)})
        assert detect.status_code == 200, f"/luxcode-browser-launch/detect returned {detect.status_code}"
        detected = detect.json().get("detected", {})
        family = next((name for name in ("chrome", "edge", "yandex", "chromium") if detected.get(name, {}).get("available")), "")
        if not family:
            raise SkipCheck("no safe local Chromium-family browser available")

        selection = client.post(
            "/luxcode-browser-launch/select",
            json={
                "requested_browser_family": family,
                "detected_candidates": detected,
                "fallback_policy": {"allow_fallback": False},
                "task_authority": "smoke-browser-launch",
                "matrix_target_metadata": {"target_id": family},
            },
        )
        assert selection.status_code == 200, f"/luxcode-browser-launch/select returned {selection.status_code}"
        selected = selection.json()
        assert selected.get("ok") is True, selected
        assert selected.get("selected_family") == family, selected
        assert selected.get("exact_match") is True, selected

        blocked = client.post(
            "/luxcode-browser-launch/launch",
            json={
                "task_id": "browser-launch-smoke",
                "target_id": family,
                "requested_browser_family": family,
                "selected_family": selected["selected_family"],
                "selected_executable": selected["selected_executable"],
                "authority_digest": "smoke-browser-launch",
                "controlled_url": fixture_url,
                "explicit_launch_intent": False,
            },
        )
        assert blocked.status_code == 200, blocked.text
        assert blocked.json().get("ok") is False, blocked.json()

        launch = client.post(
            "/luxcode-browser-launch/launch",
            json={
                "task_id": "browser-launch-smoke",
                "target_id": family,
                "requested_browser_family": family,
                "selected_family": selected["selected_family"],
                "selected_executable": selected["selected_executable"],
                "executable_digest": selected.get("executable_digest", ""),
                "authority_digest": "smoke-browser-launch",
                "controlled_url": fixture_url,
                "explicit_launch_intent": True,
                "headless": True,
                "cleanup_timeout": 5,
            },
        )
        assert launch.status_code == 200, f"/luxcode-browser-launch/launch returned {launch.status_code}"
        launched = launch.json()
        assert launched.get("ok") is True, launched
        runtime_id = launched["runtime_id"]
        try:
            verify = client.post("/luxcode-browser-launch/verify", json={"runtime_id": runtime_id, "expected_identity": family})
            assert verify.status_code == 200, f"/luxcode-browser-launch/verify returned {verify.status_code}"
            verified = verify.json()
            assert verified.get("ok") is True, verified
            assert verified.get("mismatch_detected") is False, verified
            status = client.get("/debug/luxcode-browser-launch-status")
            assert status.status_code == 200, f"/debug/luxcode-browser-launch-status returned {status.status_code}"
            assert status.json().get("external_api_used") is False, status.json()
        finally:
            terminated = client.post("/luxcode-browser-launch/terminate", json={"runtime_id": runtime_id, "reason": "smoke cleanup"})
            assert terminated.status_code == 200, f"/luxcode-browser-launch/terminate returned {terminated.status_code}"
            assert terminated.json().get("ok") is True, terminated.json()

        server.shutdown()
        server.server_close()

        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during browser launch smoke: {path}"
        for path in live_paths:
            assert path.exists() is live_state[str(path)], f"live artifact state changed during browser launch smoke: {path}"

        return "luxcode browser family launch selection verified"

    def check_luxcode_deployment_execution_local(self) -> str:
        """Verify local fixture deployment, health, URL, browser scenario, and cleanup."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        watched = [
            ROOT / "app.py",
            ROOT / "endpoint_coverage_matrix.py",
            ROOT / "scripts" / "smoke_check.py",
            ROOT / "luxcode_deployment_execution_url_verification.py",
            ROOT / "luxcode_terminal_process_runtime.py",
            ROOT / "luxcode_live_app_interaction_testing.py",
            ROOT / "luxcode_browser_launch_selection.py",
            ROOT / "luxcode_task_orchestrator.py",
            ROOT / "luxcode_task_persistence.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        live_paths = [
            ROOT / ".luxcode_deployment",
            ROOT / ".luxcode_runtime",
            ROOT / ".luxcode_live_test",
            ROOT / ".luxcode_browser_launch",
            ROOT / ".luxcode_snapshots",
            ROOT / "luxcode_tasks.db",
            ROOT / "luxcode_backups",
        ]
        live_state = {str(path): path.exists() for path in live_paths}

        schema = client.get("/luxcode-deployment/schema")
        assert schema.status_code == 200, f"/luxcode-deployment/schema returned {schema.status_code}"
        schema_data = schema.json()
        assert "local_fixture" in schema_data.get("providers", []), schema_data
        assert schema_data.get("external_api_used") is False, schema_data

        registry = client.get("/luxcode-deployment/registry")
        assert registry.status_code == 200, f"/luxcode-deployment/registry returned {registry.status_code}"
        assert registry.json().get("providers", {}).get("local_fixture", {}).get("mvp_execution_support") is True, registry.json()

        detect = client.post("/luxcode-deployment/detect", json={"repository_root": str(ROOT), "selected_scope": ".", "explicit_provider": "local_fixture"})
        assert detect.status_code == 200, f"/luxcode-deployment/detect returned {detect.status_code}"
        assert detect.json().get("detection", {}).get("provider") == "local_fixture", detect.json()

        readiness = client.post("/luxcode-deployment/readiness", json={"repository_root": str(ROOT), "selected_scope": ".", "provider": "local_fixture", "deploy_intent": True})
        assert readiness.status_code == 200, f"/luxcode-deployment/readiness returned {readiness.status_code}"
        assert readiness.json().get("readiness", {}).get("readiness_state") == "ready_for_local_fixture", readiness.json()

        blocked_plan = client.post("/luxcode-deployment/plan", json={"repository_root": str(ROOT), "provider": "local_fixture", "deploy_intent": False})
        assert blocked_plan.status_code == 200, f"/luxcode-deployment/plan returned {blocked_plan.status_code}"
        assert blocked_plan.json().get("plan", {}).get("permission_decision", {}).get("allowed") is False, blocked_plan.json()

        external_plan = client.post("/luxcode-deployment/plan", json={"repository_root": str(ROOT), "provider": "render", "deploy_intent": True, "verify_url_intent": True})
        assert external_plan.status_code == 200, f"/luxcode-deployment/plan external returned {external_plan.status_code}"
        assert external_plan.json().get("plan", {}).get("permission_decision", {}).get("allowed") is False, external_plan.json()

        plan = client.post(
            "/luxcode-deployment/plan",
            json={
                "task_id": "deployment-smoke",
                "repository_root": str(ROOT),
                "selected_scope": ".",
                "provider": "local_fixture",
                "command_text": "Deploy et, URL'yi dogrula",
                "deploy_intent": True,
                "verify_url_intent": True,
            },
        )
        assert plan.status_code == 200, f"/luxcode-deployment/plan returned {plan.status_code}"
        plan_data = plan.json().get("plan", {})
        assert plan_data.get("provider") == "local_fixture", plan_data
        assert plan_data.get("permission_decision", {}).get("allowed") is True, plan_data

        execute_blocked = client.post("/luxcode-deployment/execute", json={"plan": plan_data, "explicit_deployment_intent": False})
        assert execute_blocked.status_code == 200, f"/luxcode-deployment/execute blocked returned {execute_blocked.status_code}"
        assert execute_blocked.json().get("ok") is False, execute_blocked.json()

        execute = client.post("/luxcode-deployment/execute", json={"plan": plan_data, "explicit_deployment_intent": True, "authority_digest": "deployment-smoke"})
        assert execute.status_code == 200, f"/luxcode-deployment/execute returned {execute.status_code}"
        runtime = execute.json().get("runtime", {})
        assert runtime.get("build_state") == "build_passed", runtime
        assert runtime.get("deployment_state") == "deployment_verified", runtime
        assert runtime.get("url_result", {}).get("access_scope") == "localhost_only", runtime
        assert runtime.get("url_result", {}).get("final_verification_status") == "fully_verified", runtime
        assert runtime.get("cleanup_state") == "cleaned", runtime

        verify = client.post("/luxcode-deployment/verify", json={"runtime_id": runtime.get("deployment_runtime_id"), "url": runtime.get("url_result", {}).get("url")})
        assert verify.status_code == 200, f"/luxcode-deployment/verify returned {verify.status_code}"
        assert verify.json().get("fully_verified") is True, verify.json()

        status = client.get("/debug/luxcode-deployment-status")
        assert status.status_code == 200, f"/debug/luxcode-deployment-status returned {status.status_code}"
        status_data = status.json()
        assert status_data.get("external_provider_execution_enabled") is False, status_data
        assert status_data.get("cloud_deployment_used") is False, status_data

        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during deployment smoke: {path}"
        for path in live_paths:
            assert path.exists() is live_state[str(path)], f"live artifact state changed during deployment smoke: {path}"

        return "luxcode deployment execution and URL verification local fixture verified"

    def check_luxcode_render_provider_adapter_local(self) -> str:
        """Verify Render adapter detection, fake provider dry-run, guards, and cleanup."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        import tempfile
        import shutil
        from pathlib import Path

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        watched = [
            ROOT / "app.py",
            ROOT / "endpoint_coverage_matrix.py",
            ROOT / "scripts" / "smoke_check.py",
            ROOT / "luxcode_render_provider_adapter.py",
            ROOT / "luxcode_deployment_execution_url_verification.py",
            ROOT / "luxcode_task_orchestrator.py",
            ROOT / "luxcode_task_persistence.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        live_paths = [ROOT / ".luxcode_render", ROOT / ".luxcode_deployment", ROOT / ".luxcode_runtime", ROOT / ".luxcode_live_test", ROOT / ".luxcode_browser_launch", ROOT / "luxcode_tasks.db"]
        live_state = {str(path): path.exists() for path in live_paths}
        temp_root = Path(tempfile.mkdtemp(prefix="luxrender_smoke_"))
        try:
            (temp_root / "render.yaml").write_text(
                "\n".join(
                    [
                        "services:",
                        "  - type: web",
                        "    name: lux-smoke",
                        "    runtime: python",
                        "    buildCommand: python -m py_compile app.py",
                        "    startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT",
                        "    healthCheckPath: /health",
                        "    envVars:",
                        "      - key: DATABASE_URL",
                        "        sync: false",
                    ]
                ),
                encoding="utf-8",
            )
            (temp_root / "app.py").write_text("from fastapi import FastAPI\napp=FastAPI()\n@app.get('/health')\ndef h(): return {'ok': True}\n", encoding="utf-8")
            schema = client.get("/luxcode-render/schema")
            assert schema.status_code == 200, f"/luxcode-render/schema returned {schema.status_code}"
            assert schema.json().get("render_api_used") is False, schema.json()
            registry = client.get("/luxcode-render/registry")
            assert registry.status_code == 200, f"/luxcode-render/registry returned {registry.status_code}"
            assert "web_service" in registry.json().get("service_types", {}), registry.json()
            detect = client.post("/luxcode-render/detect", json={"repository_root": str(temp_root)})
            assert detect.status_code == 200, f"/luxcode-render/detect returned {detect.status_code}"
            assert detect.json().get("detection", {}).get("render_detected") is True, detect.json()
            parsed = client.post("/luxcode-render/parse-config", json={"repository_root": str(temp_root)})
            assert parsed.status_code == 200, f"/luxcode-render/parse-config returned {parsed.status_code}"
            service = parsed.json().get("parsed", {}).get("services", [])[0]
            assert service.get("service_type") == "web_service", service
            assert "DATABASE_URL" in service.get("environment_key_names", []), service
            readiness = client.post("/luxcode-render/readiness", json={"repository_root": str(temp_root), "deployment_intent": True})
            assert readiness.status_code == 200, f"/luxcode-render/readiness returned {readiness.status_code}"
            assert readiness.json().get("readiness", {}).get("controlled_deployment_ready") is False, readiness.json()
            plan = client.post(
                "/luxcode-render/plan",
                json={
                    "task_id": "render-smoke",
                    "repository_root": str(temp_root),
                    "deployment_intent": True,
                    "credential_reference": {"reference_id": "render-ref", "availability": "reference_available", "scope": "deploy"},
                },
            )
            assert plan.status_code == 200, f"/luxcode-render/plan returned {plan.status_code}"
            plan_data = plan.json().get("plan", {})
            assert plan_data.get("plan_digest", "").startswith("render-plan-digest-"), plan_data
            blocked = client.post("/luxcode-render/execute", json={"plan": plan_data, "expected_plan_digest": plan_data.get("plan_digest", "")})
            assert blocked.status_code == 200, f"/luxcode-render/execute returned {blocked.status_code}"
            assert blocked.json().get("ok") is False, blocked.json()
            dry = client.post("/luxcode-render/dry-run", json={"plan": plan_data, "fixture": "success"})
            assert dry.status_code == 200, f"/luxcode-render/dry-run returned {dry.status_code}"
            runtime = dry.json().get("runtime", {})
            assert runtime.get("lifecycle_state") == "render_fully_verified", runtime
            assert runtime.get("url_result", {}).get("url", "").startswith("http://127.0.0.1:"), runtime
            assert runtime.get("url_result", {}).get("fake_result_classification") == "fake_render_deployment_verified", runtime
            assert runtime.get("cloud_deployment_used") is False, runtime
            cancel = client.post("/luxcode-render/cancel", json={"runtime_id": runtime.get("render_runtime_id"), "reason": "smoke cleanup"})
            assert cancel.status_code == 200, f"/luxcode-render/cancel returned {cancel.status_code}"
            assert cancel.json().get("ok") is True, cancel.json()
            status = client.get("/debug/luxcode-render-status")
            assert status.status_code == 200, f"/debug/luxcode-render-status returned {status.status_code}"
            assert status.json().get("real_render_execution_enabled") is False, status.json()
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)
        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during Render smoke: {path}"
        for path in live_paths:
            assert path.exists() is live_state[str(path)], f"live artifact state changed during Render smoke: {path}"
        return "luxcode Render provider adapter fake deployment verified"

    def check_luxcode_render_execution_gateway_local(self) -> str:
        """Verify Render gateway authority, structured request, fake execution, and real transport blocks."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        import tempfile
        import shutil
        from pathlib import Path

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        watched = [
            ROOT / "app.py",
            ROOT / "endpoint_coverage_matrix.py",
            ROOT / "scripts" / "smoke_check.py",
            ROOT / "luxcode_render_execution_gateway.py",
            ROOT / "luxcode_render_provider_adapter.py",
            ROOT / "luxcode_deployment_execution_url_verification.py",
            ROOT / "luxcode_task_orchestrator.py",
            ROOT / "luxcode_task_persistence.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        live_paths = [
            ROOT / ".luxcode_render_gateway",
            ROOT / ".luxcode_render",
            ROOT / ".luxcode_deployment",
            ROOT / ".luxcode_runtime",
            ROOT / ".luxcode_live_test",
            ROOT / ".luxcode_network_access",
            ROOT / ".luxcode_browser_launch",
            ROOT / ".luxcode_snapshots",
            ROOT / "luxcode_tasks.db",
            ROOT / "luxcode_backups",
        ]
        live_state = {str(path): path.exists() for path in live_paths}
        temp_root = Path(tempfile.mkdtemp(prefix="luxrender_gateway_smoke_"))
        try:
            (temp_root / "render.yaml").write_text(
                "\n".join(
                    [
                        "services:",
                        "  - type: web",
                        "    name: lux-gateway-smoke",
                        "    runtime: python",
                        "    buildCommand: python -m py_compile app.py",
                        "    startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT",
                        "    healthCheckPath: /health",
                    ]
                ),
                encoding="utf-8",
            )
            (temp_root / "app.py").write_text("from fastapi import FastAPI\napp=FastAPI()\n@app.get('/health')\ndef h(): return {'ok': True}\n", encoding="utf-8")
            schema = client.get("/luxcode-render-gateway/schema")
            assert schema.status_code == 200, f"schema returned {schema.status_code}"
            assert schema.json().get("schema", {}).get("default_transport") == "disabled_transport", schema.json()
            registry = client.get("/luxcode-render-gateway/registry")
            assert registry.status_code == 200, f"registry returned {registry.status_code}"
            assert registry.json().get("transports", {}).get("render_http_transport", {}).get("runtime_enabled") is False, registry.json()
            policy = client.get("/luxcode-render-gateway/policy")
            assert policy.status_code == 200, f"policy returned {policy.status_code}"
            assert policy.json().get("policy", {}).get("feature_flags", {}).get("real_render_execution_enabled") is False, policy.json()
            plan_response = client.post(
                "/luxcode-render/plan",
                json={
                    "task_id": "gateway-smoke",
                    "repository_root": str(temp_root),
                    "deployment_intent": True,
                    "final_confirmation": True,
                    "credential_reference": {"provider": "render", "reference_id": "fixture-render-reference", "availability": "reference_available", "environment": "fixture"},
                },
            )
            assert plan_response.status_code == 200, f"plan returned {plan_response.status_code}"
            plan = plan_response.json().get("plan", {})
            blocked_authority = client.post(
                "/luxcode-render-gateway/authority",
                json={"plan": plan, "expected_plan_digest": plan.get("plan_digest"), "transport_type": "disabled_transport", "deployment_intent": True, "final_confirmation": True},
            )
            assert blocked_authority.status_code == 200, f"authority returned {blocked_authority.status_code}"
            assert blocked_authority.json().get("authority", {}).get("allowed") is False, blocked_authority.json()
            authority = client.post(
                "/luxcode-render-gateway/authority",
                json={
                    "plan": plan,
                    "expected_plan_digest": plan.get("plan_digest"),
                    "task_id": "gateway-smoke",
                    "selected_service_id": plan.get("service_candidate_id"),
                    "transport_type": "fake_render_transport",
                    "deployment_intent": True,
                    "final_confirmation": True,
                    "credential_reference": {"provider": "render", "reference_id": "fixture-render-reference", "availability": "reference_available", "environment": "fixture"},
                },
            )
            assert authority.json().get("authority", {}).get("allowed") is True, authority.json()
            request_response = client.post(
                "/luxcode-render-gateway/request",
                json={
                    "plan": plan,
                    "expected_plan_digest": plan.get("plan_digest"),
                    "task_id": "gateway-smoke",
                    "selected_service_id": plan.get("service_candidate_id"),
                    "transport_type": "fake_render_transport",
                    "deployment_intent": True,
                    "final_confirmation": True,
                    "credential_reference": {"provider": "render", "reference_id": "fixture-render-reference", "availability": "reference_available", "environment": "fixture"},
                    "permission_decision": authority.json().get("authority", {}),
                },
            )
            assert request_response.status_code == 200, f"request returned {request_response.status_code}"
            request = request_response.json().get("request", {})
            assert request.get("raw_http_body") is None and request.get("raw_cli_command") is None, request
            execute = client.post("/luxcode-render-gateway/execute", json={"request": request})
            assert execute.status_code == 200, f"execute returned {execute.status_code}"
            runtime = execute.json().get("runtime", {})
            assert runtime.get("state") == "fake_render_gateway_verified", runtime
            assert runtime.get("url_metadata", {}).get("trusted") is True, runtime
            assert runtime.get("health_state") == "deployment_health_verified", runtime
            assert runtime.get("browser_state") == "deployment_scenario_verified", runtime
            assert runtime.get("real_cloud_deployment") is False, runtime
            poll = client.post("/luxcode-render-gateway/poll", json={"runtime_id": runtime.get("gateway_runtime_id")})
            assert poll.status_code == 200 and poll.json().get("ok") is True, poll.json()
            verify = client.post("/luxcode-render-gateway/verify", json={"runtime_id": runtime.get("gateway_runtime_id")})
            assert verify.status_code == 200 and verify.json().get("fully_verified") is True, verify.json()
            bad_verify = client.post("/luxcode-render-gateway/verify", json={"runtime_id": runtime.get("gateway_runtime_id"), "url": "https://example.com"})
            assert bad_verify.json().get("ok") is False, bad_verify.json()
            real_block = client.post("/luxcode-render-gateway/request", json={"plan": plan, "transport_type": "render_http_transport"})
            assert real_block.json().get("ok") is False, real_block.json()
            cancel = client.post("/luxcode-render-gateway/cancel", json={"runtime_id": runtime.get("gateway_runtime_id"), "task_id": "gateway-smoke", "reason": "terminal smoke"})
            assert cancel.status_code == 200 and cancel.json().get("ok") is False, cancel.json()
            status = client.get("/debug/luxcode-render-gateway-status")
            assert status.status_code == 200, f"status returned {status.status_code}"
            assert status.json().get("real_render_execution_enabled") is False, status.json()
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)
        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during Render gateway smoke: {path}"
        for path in live_paths:
            assert path.exists() is live_state[str(path)], f"live artifact state changed during Render gateway smoke: {path}"
        return "luxcode Render execution gateway fake transport verified"

    def check_luxcode_render_credential_readiness_local(self) -> str:
        """Verify Render credential readiness broker package, seal, confirmation, and gateway integration."""
        try:
            from fastapi.testclient import TestClient
        except Exception as exc:
            raise SkipCheck(f"TestClient unavailable: {type(exc).__name__}")
        import tempfile
        import shutil
        from pathlib import Path

        luxapp = self.import_app()
        client = TestClient(luxapp.app)
        watched = [
            ROOT / "app.py",
            ROOT / "endpoint_coverage_matrix.py",
            ROOT / "scripts" / "smoke_check.py",
            ROOT / "luxcode_render_credential_readiness_broker.py",
            ROOT / "luxcode_render_execution_gateway.py",
            ROOT / "luxcode_render_provider_adapter.py",
            ROOT / "luxcode_deployment_execution_url_verification.py",
            ROOT / "luxcode_task_orchestrator.py",
            ROOT / "luxcode_task_persistence.py",
        ]
        before = {str(path): path.read_bytes() for path in watched if path.exists()}
        live_paths = [
            ROOT / ".luxcode_render_credentials",
            ROOT / ".luxcode_render_readiness",
            ROOT / ".luxcode_render_gateway",
            ROOT / ".luxcode_render",
            ROOT / ".luxcode_deployment",
            ROOT / ".luxcode_runtime",
            ROOT / ".luxcode_live_test",
            ROOT / ".luxcode_network_access",
            ROOT / ".luxcode_browser_launch",
            ROOT / ".luxcode_snapshots",
            ROOT / "luxcode_tasks.db",
            ROOT / "luxcode_backups",
        ]
        live_state = {str(path): path.exists() for path in live_paths}
        temp_root = Path(tempfile.mkdtemp(prefix="luxrender_readiness_smoke_"))
        try:
            (temp_root / "render.yaml").write_text(
                "\n".join(
                    [
                        "services:",
                        "  - type: web",
                        "    name: lux-readiness-smoke",
                        "    runtime: python",
                        "    buildCommand: python -m py_compile app.py",
                        "    startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT",
                        "    healthCheckPath: /health",
                    ]
                ),
                encoding="utf-8",
            )
            (temp_root / "app.py").write_text("from fastapi import FastAPI\napp=FastAPI()\n@app.get('/health')\ndef h(): return {'ok': True}\n", encoding="utf-8")
            schema = client.get("/luxcode-render-readiness/schema")
            assert schema.status_code == 200, schema.text
            assert schema.json().get("schema", {}).get("credential_values_allowed") is False, schema.json()
            registry = client.get("/luxcode-render-readiness/registry")
            assert registry.status_code == 200, registry.text
            assert "create_deployment" in registry.json().get("registry", {}).get("minimum_production_scopes", []), registry.json()
            policy = client.get("/luxcode-render-readiness/policy")
            assert policy.status_code == 200, policy.text
            assert policy.json().get("policy", {}).get("external_network_enabled") is False, policy.json()
            plan_response = client.post(
                "/luxcode-render/plan",
                json={
                    "task_id": "readiness-smoke",
                    "repository_root": str(temp_root),
                    "deployment_intent": True,
                    "final_confirmation": True,
                    "credential_reference": {"reference_id": "adapter-ref", "availability": "reference_available", "scope": "deploy"},
                },
            )
            assert plan_response.status_code == 200, plan_response.text
            plan = plan_response.json().get("plan", {})
            scope_digest = "scope-digest-" + __import__("hashlib").sha256(__import__("json").dumps([plan.get("project_root"), plan.get("root_directory"), plan.get("service_candidate_id")], sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()[:24]
            credential = {
                "reference_id": "fixture-render-reference",
                "provider": "fixture_reference",
                "target_service": plan.get("service_candidate_id"),
                "environment": "preview",
                "scope": ["read_service_metadata", "read_deployment_status", "create_deployment"],
                "allowed_operations": ["read_service_metadata", "read_deployment_status", "create_deployment"],
                "created_time": "2026-01-01T00:00:00+00:00",
                "valid_from": "2026-01-01T00:00:00+00:00",
                "expires_at": "2026-01-03T00:00:00+00:00",
                "last_verified_time": "2026-01-01T00:00:00+00:00",
                "allowed_branch": "main",
            }
            secret_block = client.post("/luxcode-render-readiness/credential", json={"credential_reference": {**credential, "token": "blocked"}})
            assert secret_block.json().get("ok") is False, secret_block.json()
            cred = client.post("/luxcode-render-readiness/credential", json={"credential_reference": credential, "selected_service_id": plan.get("service_candidate_id"), "environment": "preview", "project_scope_digest": scope_digest, "branch": "main", "now": "2026-01-01T00:00:00+00:00"})
            assert cred.status_code == 200 and cred.json().get("ok") is True, cred.json()
            net_block = client.post("/luxcode-render-readiness/network", json={"network_authority": {}, "project_scope_digest": scope_digest, "now": "2026-01-01T00:00:00+00:00"})
            assert net_block.json().get("network_decision", {}).get("network_state") == "network_not_requested", net_block.json()
            network = {"requested": True, "origin": "https://api.render.com", "methods": ["GET", "POST"], "project_scope_digest": scope_digest, "request_budget": 3, "expires_at": "2026-01-01T03:00:00+00:00"}
            package_response = client.post(
                "/luxcode-render-readiness/package",
                json={
                    "plan": plan,
                    "credential_reference": credential,
                    "network_authority": network,
                    "task_id": "readiness-smoke",
                    "environment": "preview",
                    "branch": "main",
                    "commit_metadata": {"commit": "fixture"},
                    "deployment_intent": True,
                    "final_confirmation_state": "confirmation_granted",
                    "now": "2026-01-01T00:00:00+00:00",
                },
            )
            assert package_response.status_code == 200 and package_response.json().get("ok") is True, package_response.json()
            package = package_response.json().get("readiness_package", {})
            assert package.get("package_digest", "").startswith("render-readiness-package-"), package
            seal_response = client.post("/luxcode-render-readiness/seal", json={"readiness_package": package, "requested_level": "dry_run", "now": "2026-01-01T00:00:00+00:00"})
            seal = seal_response.json().get("seal", {})
            assert seal.get("seal_status") == "seal_issued_for_dry_run", seal
            validate = client.post("/luxcode-render-readiness/validate", json={"readiness_package": package, "readiness_seal": seal, "confirmation": {"granted": True, "package_digest": package.get("package_digest"), "environment": "preview", "expires_at": "2026-01-01T01:00:00+00:00"}, "now": "2026-01-01T00:00:00+00:00"})
            assert validate.status_code == 200 and validate.json().get("seal", {}).get("valid") is True, validate.json()
            invalidated = client.post("/luxcode-render-readiness/invalidate", json={"readiness_package": package, "readiness_seal": seal, "changed_fields": ["branch_changed"], "now": "2026-01-01T00:00:00+00:00"})
            assert "branch_changed" in invalidated.json().get("seal", {}).get("invalidation_reasons", []), invalidated.json()
            authority = client.post(
                "/luxcode-render-gateway/authority",
                json={"plan": plan, "expected_plan_digest": plan.get("plan_digest"), "task_id": "readiness-smoke", "selected_service_id": plan.get("service_candidate_id"), "transport_type": "fake_render_transport", "deployment_intent": True, "final_confirmation": True, "credential_reference": {"provider": "render", "reference_id": "fixture-render-reference", "availability": "reference_available", "environment": "fixture"}},
            )
            request_response = client.post(
                "/luxcode-render-gateway/request",
                json={
                    "plan": plan,
                    "expected_plan_digest": plan.get("plan_digest"),
                    "task_id": "readiness-smoke",
                    "selected_service_id": plan.get("service_candidate_id"),
                    "transport_type": "fake_render_transport",
                    "deployment_intent": True,
                    "final_confirmation": True,
                    "credential_reference": {"provider": "render", "reference_id": "fixture-render-reference", "availability": "reference_available", "environment": "fixture"},
                    "permission_decision": authority.json().get("authority", {}),
                    "readiness_package": package,
                    "readiness_seal": seal,
                    "production_readiness_required": True,
                    "readiness_validation_time": "2026-01-01T00:00:00+00:00",
                },
            )
            request = request_response.json().get("request", {})
            executed = client.post("/luxcode-render-gateway/execute", json={"request": request})
            assert executed.json().get("runtime", {}).get("state") == "fake_render_gateway_verified", executed.json()
            real_block = client.post("/luxcode-render-gateway/request", json={"plan": plan, "transport_type": "render_http_transport"})
            assert real_block.json().get("ok") is False, real_block.json()
            status = client.get("/debug/luxcode-render-readiness-status")
            assert status.status_code == 200 and status.json().get("real_render_execution_enabled") is False, status.json()
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)
        for path in watched:
            if path.exists():
                assert path.read_bytes() == before[str(path)], f"live source changed during readiness smoke: {path}"
        for path in live_paths:
            assert path.exists() is live_state[str(path)], f"live artifact changed during readiness smoke: {path}"
        return "luxcode Render credential readiness broker verified"

    def _build_check_registry(self) -> list[CheckDef]:
        """Build structured check registry for filtering."""
        raw: list[tuple[str, Callable[[], str | None], int | None, str]] = [
            ("py_compile_app", self.check_py_compile_app, None, "core"),
            ("compileall_learning", self.check_compileall_learning, None, "core"),
            ("health_shape_16_layers", self.check_health_shape, None, "core"),
            ("count_guard", self.check_count_guard, None, "core"),
            ("line_format_guard", self.check_line_format_guard, None, "core"),
            ("format_prompt_cleanup", self.check_format_prompt_and_cleanup, None, "core"),
            ("identity_guard", self.check_identity_guard, None, "core"),
            ("double_response_trim", self.check_double_response_trim, None, "core"),
            ("frontend_resume_scaffold", self.check_frontend_resume_scaffold, None, "core"),
            ("cost_logger_privacy", self.check_cost_logger_privacy, None, "core"),
            ("practical_support_passive", self.check_practical_support, None, "core"),
            ("token_budget_observe_only", self.check_token_budget, None, "core"),
            ("efficiency_router_shadow", self.check_efficiency_and_shadow, None, "core"),
            ("auto_continuation", self.check_auto_continuation, None, "core"),
            ("api_schema_in_process", self.check_api_schema, None, "core"),
            ("agent_capabilities_schema", self.check_agent_capabilities_api, None, "core"),
            ("agent_privacy_rules", self.check_agent_privacy_rules_present, None, "core"),
            ("luxway_status_inactive", self.check_luxway_capabilities_planned_inactive, None, "core"),
            ("memory_schema_fields", self.check_memory_schema_contains_fields, None, "core"),
            ("memory_preview_raw_data", self.check_memory_preview_signal_privacy, None, "core"),
            ("agent_high_risk_confirmation", self.check_high_risk_agent_confirmation, None, "core"),
            ("agent_preview_intent_read_only", self.check_agent_preview_intent_read_only, None, "core"),
            ("agent_plan_action_read_only", self.check_agent_plan_action_read_only, None, "core"),
            ("agent_analyze_hub_read_only", self.check_agent_analyze_hub_read_only, None, "core"),
            ("router_preview_read_only", self.check_router_preview_read_only, None, "core"),
            ("luxcode_master_router_read_only", self.check_luxcode_master_router_read_only, None, "core"),
            ("lux_debug_intelligence_read_only", self.check_lux_debug_intelligence_read_only, None, "core"),
            ("lux_safe_patch_draft_read_only", self.check_lux_safe_patch_draft_read_only, None, "core"),
            ("lux_controlled_apply_approval_gated", self.check_lux_controlled_apply_approval_gated, None, "core"),
            ("lux_verification_recovery_local", self.check_lux_verification_recovery_local, None, "core"),
            ("luxcode_zero_cost_execution_router_local", self.check_luxcode_zero_cost_execution_router_local, None, "core"),
            ("luxcode_task_orchestrator_local", self.check_luxcode_task_orchestrator_local, None, "core"),
            ("luxcode_task_persistence_local", self.check_luxcode_task_persistence_local, None, "core"),
            ("luxcode_tier0_deterministic_executor_local", self.check_luxcode_tier0_deterministic_executor_local, None, "core"),
            ("luxcode_multi_agent_handoff_local", self.check_luxcode_multi_agent_handoff_local, None, "core"),
            ("luxcode_coder_operator_cli_local", self.check_luxcode_coder_operator_cli_local, None, "core"),
            ("luxcode_practical_coder_runtime_local", self.check_luxcode_practical_coder_runtime_local, None, "core"),
            ("luxcode_low_cost_worker_local", self.check_luxcode_low_cost_worker_local, None, "core"),
            ("luxcode_autonomy_permission_local", self.check_luxcode_autonomy_permission_local, None, "core"),
            ("luxcode_terminal_process_runtime_local", self.check_luxcode_terminal_process_runtime_local, None, "core"),
            ("luxcode_browser_launch_selection_local", self.check_luxcode_browser_launch_selection_local, None, "core"),
            ("luxcode_deployment_execution_local", self.check_luxcode_deployment_execution_local, None, "core"),
            ("luxcode_render_provider_adapter_local", self.check_luxcode_render_provider_adapter_local, None, "core"),
            ("luxcode_render_execution_gateway_local", self.check_luxcode_render_execution_gateway_local, None, "core"),
            ("luxcode_render_credential_readiness_local", self.check_luxcode_render_credential_readiness_local, None, "core"),
            ("luxcode_live_app_interaction_testing_local", self.check_luxcode_live_app_interaction_testing_local, None, "core"),
            ("luxcode_network_access_local", self.check_luxcode_network_access_local, None, "core"),
            ("luxcode_test_matrix_local", self.check_luxcode_test_matrix_local, None, "core"),
            ("debug_sample_preview_endpoints", self.check_debug_sample_preview_endpoints, None, "core"),
            ("debug_agent_panel", self.check_debug_agent_panel, None, "core"),
            ("mode_registry_preview", self.check_mode_registry_preview, None, "core"),
            ("permission_boundary_preview", self.check_permission_boundary_preview, None, "core"),
            ("agent_decision_trace_preview", self.check_agent_decision_trace_preview, None, "core"),
            ("layer14_status_snapshot", self.check_layer14_status_snapshot, 14, "layer"),
            ("workspace_schema_preview", self.check_workspace_schema_preview, 15, "layer"),
            ("visual_style_registry_preview", self.check_visual_style_registry_preview, 16, "layer"),
            ("visual_status_snapshot", self.check_visual_status_snapshot, 16, "layer"),
            ("voice_speed_preview", self.check_voice_speed_preview, 17, "layer"),
            ("night_radio_voice_preview", self.check_night_radio_voice_preview, 17, "layer"),
            ("voice_audio_status_snapshot", self.check_voice_audio_status_snapshot, 17, "layer"),
            ("audio_signal_preview", self.check_audio_signal_preview, None, "core"),
            ("audio_privacy_boundary_preview", self.check_audio_privacy_boundary_preview, None, "core"),
            ("model_router_config_preview", self.check_model_router_config_preview, None, "core"),
            ("model_router_hint_preview", self.check_model_router_hint_preview, None, "core"),
            ("cost_privacy_policy_preview", self.check_cost_privacy_policy_preview, None, "core"),
            ("safe_memory_retrieval_preview", self.check_safe_memory_retrieval_preview, None, "core"),
            ("routing_simulation_preview", self.check_routing_simulation_preview, None, "core"),
            ("model_router_full_status_snapshot", self.check_model_router_full_status_snapshot, None, "core"),
            ("production_hardening_backlog_registry", self.check_production_hardening_backlog_registry, None, "core"),
            ("root_flow_auditor_preview", self.check_root_flow_auditor_preview, None, "core"),
            ("safe_self_check_runner_preview", self.check_safe_self_check_runner_preview, None, "core"),
            ("codex_handoff_builder_preview", self.check_codex_handoff_builder_preview, None, "core"),
            ("bug_intake_investigation_planner_preview", self.check_bug_intake_investigation_planner_preview, None, "core"),
            ("credit_saver_engine_preview", self.check_credit_saver_engine_preview, None, "core"),
            ("debug_intelligence_core_preview", self.check_debug_intelligence_core_preview, None, "core"),
            ("layer23_status_snapshot", self.check_layer23_status_snapshot, 23, "layer"),
            ("patch_recovery_preview", self.check_patch_recovery_preview, 28, "layer"),
            ("patch_audit_trail_preview", self.check_patch_audit_trail_preview, 28, "layer"),
            ("lux_fault_report_preview", self.check_lux_fault_report_preview, None, "core"),
            ("investigation_context_preview", self.check_investigation_context_preview, None, "core"),
            ("patch_lifecycle_preview", self.check_patch_lifecycle_preview, 28, "layer"),
            ("layer28_status_snapshot", self.check_layer28_status_snapshot, 28, "layer"),
            ("layer29_status_snapshot", self.check_layer29_status_snapshot, 29, "layer"),
            ("layer30_status_snapshot", self.check_layer30_status_snapshot, 30, "layer"),
            ("production_readiness_preview", self.check_production_readiness_preview, 30, "layer"),
            ("operational_readiness_preview", self.check_operational_readiness_preview, 30, "layer"),
            ("system_readiness_preview", self.check_system_readiness_preview, 30, "layer"),
            ("validation_readiness_preview", self.check_validation_readiness_preview, 30, "layer"),
            ("release_readiness_preview", self.check_release_readiness_preview, 30, "layer"),
            ("system_health_intelligence_preview", self.check_system_health_intelligence_preview, 31, "layer"),
            ("runtime_stability_intelligence_preview", self.check_runtime_stability_intelligence_preview, 31, "layer"),
            ("runtime_risk_intelligence_preview", self.check_runtime_risk_intelligence_preview, 31, "layer"),
            ("runtime_drift_intelligence_preview", self.check_runtime_drift_intelligence_preview, 31, "layer"),
            ("runtime_recovery_intelligence_preview", self.check_runtime_recovery_intelligence_preview, 31, "layer"),
            ("runtime_anomaly_intelligence_preview", self.check_runtime_anomaly_intelligence_preview, 32, "layer"),
            ("regression_intelligence_preview", self.check_regression_intelligence_preview, 32, "layer"),
            ("failure_memory_intelligence_preview", self.check_failure_memory_intelligence_preview, 32, "layer"),
            ("dependency_intelligence_preview", self.check_dependency_intelligence_preview, 32, "layer"),
            ("root_cause_intelligence_preview", self.check_root_cause_intelligence_preview, 32, "layer"),
            ("change_memory_intelligence_preview", self.check_change_memory_intelligence_preview, 33, "layer"),
            ("failed_change_intelligence_preview", self.check_failed_change_intelligence_preview, 33, "layer"),
            ("change_planning_intelligence_preview", self.check_change_planning_intelligence_preview, 33, "layer"),
            ("clone_workspace_intelligence_preview", self.check_clone_workspace_intelligence_preview, 33, "layer"),
            ("sandbox_repair_intelligence_preview", self.check_sandbox_repair_intelligence_preview, 33, "layer"),
            ("verification_intelligence_preview", self.check_verification_intelligence_preview, 33, "layer"),
            ("delivery_readiness_intelligence_preview", self.check_delivery_readiness_intelligence_preview, 33, "layer"),
            ("layer31_status_snapshot", self.check_layer31_status_snapshot, 31, "layer"),
            ("layer32_status_snapshot", self.check_layer32_status_snapshot, 32, "layer"),
            ("patch_permission_preview", self.check_patch_permission_preview, 29, "layer"),
            ("patch_policy_preview", self.check_patch_policy_preview, 29, "layer"),
            ("patch_compliance_preview", self.check_patch_compliance_preview, 29, "layer"),
            ("patch_governance_preview", self.check_patch_governance_preview, 29, "layer"),
            ("patch_oversight_preview", self.check_patch_oversight_preview, 29, "layer"),
            ("patch_accountability_preview", self.check_patch_accountability_preview, 29, "layer"),
            ("patch_assurance_preview", self.check_patch_assurance_preview, 29, "layer"),
            ("patch_confidence_preview", self.check_patch_confidence_preview, 29, "layer"),
            ("investigation_timeline_preview", self.check_investigation_timeline_preview, None, "core"),
            ("knowledge_extractor_preview", self.check_knowledge_extractor_preview, None, "core"),
            ("repeated_pattern_detector_preview", self.check_repeated_pattern_detector_preview, None, "core"),
            ("investigation_starter_preview", self.check_investigation_starter_preview, None, "core"),
            ("investigation_priority_preview", self.check_investigation_priority_preview, None, "core"),
            ("task_planner_preview", self.check_task_planner_preview, None, "core"),
            ("dev_agent_explorer_preview", self.check_dev_agent_explorer_preview, None, "core"),
            ("dependency_mapper_preview", self.check_dependency_mapper_preview, None, "core"),
            ("impact_analyzer_preview", self.check_impact_analyzer_preview, None, "core"),
            ("change_boundary_preview", self.check_change_boundary_preview, None, "core"),
            ("patch_planner_preview", self.check_patch_planner_preview, None, "core"),
            ("verification_planner_preview", self.check_verification_planner_preview, None, "core"),
            ("dev_agent_readiness_snapshot", self.check_dev_agent_readiness_snapshot, 25, "layer"),
            ("agent_constitution_engine_preview", self.check_agent_constitution_engine_preview, 26, "layer"),
            ("project_rules_loader_preview", self.check_project_rules_loader_preview, 26, "layer"),
            ("explorer_agent_preview", self.check_explorer_agent_preview, 26, "layer"),
            ("planner_agent_preview", self.check_planner_agent_preview, 26, "layer"),
            ("verifier_agent_preview", self.check_verifier_agent_preview, 26, "layer"),
            ("evidence_store_preview", self.check_evidence_store_preview, 26, "layer"),
            ("multi_agent_coordinator_preview", self.check_coordinator_preview, 26, "layer"),
            ("patch_draft_engine_preview", self.check_patch_draft_engine_preview, 27, "layer"),
            ("change_preview_engine", self.check_change_preview_engine, 27, "layer"),
            ("system_control_audit_preview", self.check_system_control_audit_preview, None, "core"),
            ("endpoint_coverage_matrix_preview", self.check_endpoint_coverage_matrix_preview, None, "core"),
            ("live_readiness_checklist_preview", self.check_live_readiness_checklist_preview, None, "core"),
            ("master_status_summary_preview", self.check_master_status_summary_preview, None, "core"),
            ("lux_character_status", self.check_lux_character_status, None, "core"),
            ("location_weather_context", self.check_location_weather_context, None, "core"),
            ("conversation_summary_command", self.check_conversation_summary_command, None, "core"),
            ("layer21_status_snapshot", self.check_layer21_status_snapshot, 21, "layer"),
            ("layer22_future_candidates_preview", self.check_layer22_future_candidates_preview, 22, "layer"),
            ("layer22_full_status_snapshot", self.check_layer22_full_status_snapshot, 22, "layer"),
            ("layer22_candidate_scoring_preview", self.check_layer22_candidate_scoring_preview, 22, "layer"),
            ("finality_sense_preview", self.check_finality_sense_preview, None, "core"),
            ("adaptive_interface_preview", self.check_adaptive_interface_preview, None, "core"),
            ("ambient_workspace_preview", self.check_ambient_workspace_preview, None, "core"),
            ("intention_timeline_preview", self.check_intention_timeline_preview, None, "core"),
            ("autonomy_dial_preview", self.check_autonomy_dial_preview, None, "core"),
            ("ethical_boundary_preview", self.check_ethical_boundary_preview, None, "core"),
            ("background_support_registry_preview", self.check_background_support_registry_preview, None, "core"),
            ("meta_intelligence_core_preview", self.check_meta_intelligence_core_preview, None, "core"),
            ("emotional_reflection_support_preview", self.check_emotional_reflection_support_preview, None, "core"),
            ("context_bridge_preview", self.check_context_bridge_preview, None, "core"),
            ("device_bridge_preview", self.check_device_bridge_preview, None, "core"),
            ("pointer_context_preview", self.check_pointer_context_preview, None, "core"),
            ("drive_mode_preview", self.check_drive_mode_preview, None, "core"),
            ("wake_sonic_preview", self.check_wake_sonic_preview, None, "core"),
            ("luxway_capability_preview", self.check_luxway_capability_preview, None, "core"),
            ("luxway_permission_model_preview", self.check_luxway_permission_model_preview, None, "core"),
            ("luxway_weekly_report_preview", self.check_luxway_weekly_report_preview, None, "core"),
            ("luxway_data_preview", self.check_luxway_data_preview, None, "core"),
            ("luxway_device_safety_preview", self.check_luxway_device_safety_preview, None, "core"),
            ("luxway_full_status_snapshot", self.check_luxway_full_status_snapshot, None, "core"),
            ("ws_stream_schema_in_process", self.check_ws_stream_schema, None, "core"),
            ("live_server_health", self.check_live_server_health, None, "core"),
            ("local_privacy_scan", self.check_local_privacy_scan, None, "core"),
            ("layer37_architecture_previews", self.check_layer37_architecture_previews, 37, "layer"),
            ("layer38_autonomous_agent_systems_previews", self.check_layer38_autonomous_agent_systems_previews, 38, "layer"),
            ("layer39_agent_runtime_systems_previews", self.check_layer39_agent_runtime_systems_previews, 39, "layer"),
            ("layer40_agent_execution_systems_previews", self.check_layer40_agent_execution_systems_previews, 40, "layer"),
            ("layer41_autonomous_operations_systems_previews", self.check_layer41_autonomous_operations_systems_previews, 41, "layer"),
        ]
        return [CheckDef(name=item[0], fn=item[1], layer=item[2], category=item[3]) for item in raw]

    def _get_filtered_checks(self, registry: list[CheckDef]) -> list[CheckDef]:
        if SELECTED_CHECK:
            match_lower = SELECTED_CHECK.lower()
            return [c for c in registry if match_lower in c.name.lower()]
        if SELECTED_LAYER is not None:
            return [c for c in registry if c.layer == SELECTED_LAYER]
        if SELECTED_LAYER_RANGE is not None:
            lo, hi = SELECTED_LAYER_RANGE
            return [c for c in registry if c.layer is not None and lo <= c.layer <= hi]
        if QUICK_MODE:
            quick_layers = {37, 38, 39, 40, 41}
            return [c for c in registry if c.layer in quick_layers]
        return registry

    def run(self) -> int:
        print(f"ROOT {ROOT}")
        all_checks = self._build_check_registry()
        filtered_checks = self._get_filtered_checks(all_checks)

        if SELECTED_CHECK:
            SMOKE_MODE = "targeted"
        elif SELECTED_LAYER is not None or SELECTED_LAYER_RANGE is not None:
            SMOKE_MODE = "targeted"
        elif QUICK_MODE:
            SMOKE_MODE = "quick"
        else:
            SMOKE_MODE = "full"

        print(f"SMOKE MODE: {SMOKE_MODE}")
        if SMOKE_MODE in ("targeted", "quick"):
            selected_names = [c.name for c in filtered_checks]
            print(f"Selected checks: {', '.join(selected_names)}")
        if not filtered_checks:
            print("No matching checks found. Use --help for options.")
            return 1

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
            ("luxcode_master_router_read_only", self.check_luxcode_master_router_read_only),
            ("lux_debug_intelligence_read_only", self.check_lux_debug_intelligence_read_only),
            ("lux_safe_patch_draft_read_only", self.check_lux_safe_patch_draft_read_only),
            ("lux_controlled_apply_approval_gated", self.check_lux_controlled_apply_approval_gated),
            ("lux_verification_recovery_local", self.check_lux_verification_recovery_local),
            ("luxcode_zero_cost_execution_router_local", self.check_luxcode_zero_cost_execution_router_local),
            ("luxcode_task_orchestrator_local", self.check_luxcode_task_orchestrator_local),
            ("luxcode_task_persistence_local", self.check_luxcode_task_persistence_local),
            ("luxcode_multi_agent_handoff_local", self.check_luxcode_multi_agent_handoff_local),
            ("luxcode_coder_operator_cli_local", self.check_luxcode_coder_operator_cli_local),
            ("luxcode_practical_coder_runtime_local", self.check_luxcode_practical_coder_runtime_local),
            ("luxcode_low_cost_worker_local", self.check_luxcode_low_cost_worker_local),
            ("luxcode_autonomy_permission_local", self.check_luxcode_autonomy_permission_local),
            ("luxcode_terminal_process_runtime_local", self.check_luxcode_terminal_process_runtime_local),
            ("luxcode_browser_launch_selection_local", self.check_luxcode_browser_launch_selection_local),
            ("luxcode_deployment_execution_local", self.check_luxcode_deployment_execution_local),
            ("luxcode_render_provider_adapter_local", self.check_luxcode_render_provider_adapter_local),
            ("luxcode_render_execution_gateway_local", self.check_luxcode_render_execution_gateway_local),
            ("luxcode_render_credential_readiness_local", self.check_luxcode_render_credential_readiness_local),
            ("luxcode_live_app_interaction_testing_local", self.check_luxcode_live_app_interaction_testing_local),
            ("luxcode_network_access_local", self.check_luxcode_network_access_local),
            ("luxcode_test_matrix_local", self.check_luxcode_test_matrix_local),
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
            ("patch_recovery_preview", self.check_patch_recovery_preview),
            ("patch_audit_trail_preview", self.check_patch_audit_trail_preview),
            ("lux_fault_report_preview", self.check_lux_fault_report_preview),
            ("investigation_context_preview", self.check_investigation_context_preview),
            ("patch_lifecycle_preview", self.check_patch_lifecycle_preview),
            ("layer28_status_snapshot", self.check_layer28_status_snapshot),
            ("layer29_status_snapshot", self.check_layer29_status_snapshot),
            ("layer30_status_snapshot", self.check_layer30_status_snapshot),
            ("production_readiness_preview", self.check_production_readiness_preview),
            ("operational_readiness_preview", self.check_operational_readiness_preview),
            ("system_readiness_preview", self.check_system_readiness_preview),
            ("validation_readiness_preview", self.check_validation_readiness_preview),
            ("release_readiness_preview", self.check_release_readiness_preview),
            ("system_health_intelligence_preview", self.check_system_health_intelligence_preview),
            ("runtime_stability_intelligence_preview", self.check_runtime_stability_intelligence_preview),
            ("runtime_risk_intelligence_preview", self.check_runtime_risk_intelligence_preview),
            ("runtime_drift_intelligence_preview", self.check_runtime_drift_intelligence_preview),
            ("runtime_recovery_intelligence_preview", self.check_runtime_recovery_intelligence_preview),
            ("runtime_anomaly_intelligence_preview", self.check_runtime_anomaly_intelligence_preview),
            ("regression_intelligence_preview", self.check_regression_intelligence_preview),
            ("failure_memory_intelligence_preview", self.check_failure_memory_intelligence_preview),
            ("dependency_intelligence_preview", self.check_dependency_intelligence_preview),
            ("root_cause_intelligence_preview", self.check_root_cause_intelligence_preview),
            ("change_memory_intelligence_preview", self.check_change_memory_intelligence_preview),
            ("failed_change_intelligence_preview", self.check_failed_change_intelligence_preview),
            ("change_planning_intelligence_preview", self.check_change_planning_intelligence_preview),
            ("clone_workspace_intelligence_preview", self.check_clone_workspace_intelligence_preview),
            ("sandbox_repair_intelligence_preview", self.check_sandbox_repair_intelligence_preview),
            ("verification_intelligence_preview", self.check_verification_intelligence_preview),
            ("delivery_readiness_intelligence_preview", self.check_delivery_readiness_intelligence_preview),
            ("layer31_status_snapshot", self.check_layer31_status_snapshot),
            ("layer32_status_snapshot", self.check_layer32_status_snapshot),
            ("patch_permission_preview", self.check_patch_permission_preview),
            ("patch_policy_preview", self.check_patch_policy_preview),
            ("patch_compliance_preview", self.check_patch_compliance_preview),
            ("patch_governance_preview", self.check_patch_governance_preview),
            ("patch_oversight_preview", self.check_patch_oversight_preview),
            ("patch_accountability_preview", self.check_patch_accountability_preview),
            ("patch_assurance_preview", self.check_patch_assurance_preview),
            ("patch_confidence_preview", self.check_patch_confidence_preview),
            ("investigation_timeline_preview", self.check_investigation_timeline_preview),
            ("knowledge_extractor_preview", self.check_knowledge_extractor_preview),
            ("repeated_pattern_detector_preview", self.check_repeated_pattern_detector_preview),
            ("investigation_starter_preview", self.check_investigation_starter_preview),
            ("investigation_priority_preview", self.check_investigation_priority_preview),
            ("task_planner_preview", self.check_task_planner_preview),
            ("dev_agent_explorer_preview", self.check_dev_agent_explorer_preview),
            ("dependency_mapper_preview", self.check_dependency_mapper_preview),
            ("impact_analyzer_preview", self.check_impact_analyzer_preview),
            ("change_boundary_preview", self.check_change_boundary_preview),
            ("patch_planner_preview", self.check_patch_planner_preview),
            ("verification_planner_preview", self.check_verification_planner_preview),
            ("dev_agent_readiness_snapshot", self.check_dev_agent_readiness_snapshot),
            ("agent_constitution_engine_preview", self.check_agent_constitution_engine_preview),
            ("project_rules_loader_preview", self.check_project_rules_loader_preview),
            ("explorer_agent_preview", self.check_explorer_agent_preview),
            ("planner_agent_preview", self.check_planner_agent_preview),
            ("verifier_agent_preview", self.check_verifier_agent_preview),
            ("evidence_store_preview", self.check_evidence_store_preview),
            ("multi_agent_coordinator_preview", self.check_coordinator_preview),
            ("patch_draft_engine_preview", self.check_patch_draft_engine_preview),
            ("change_preview_engine", self.check_change_preview_engine),
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
            ("layer37_architecture_previews", self.check_layer37_architecture_previews),
            ("layer38_autonomous_agent_systems_previews", self.check_layer38_autonomous_agent_systems_previews),
            ("layer39_agent_runtime_systems_previews", self.check_layer39_agent_runtime_systems_previews),
            ("layer40_agent_execution_systems_previews", self.check_layer40_agent_execution_systems_previews),
            ("layer41_autonomous_operations_systems_previews", self.check_layer41_autonomous_operations_systems_previews),
        ]
        try:
            for cdef in filtered_checks:
                self.check(cdef.name, cdef.fn)
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
    parser = argparse.ArgumentParser(description="LuxCode Smoke Check Script")
    parser.add_argument("--layer", type=int, default=None, help="Run checks for a specific layer number (e.g. 37)")
    parser.add_argument("--layers", type=str, default=None, help="Run checks for a layer range (e.g. 37-41)")
    parser.add_argument("--check", type=str, default=None, help="Run checks matching a name pattern (e.g. layer41)")
    parser.add_argument("--quick", action="store_true", default=False, help="Quick mode: run only critical layer 37-41 checks")
    parser.add_argument("--full", action="store_true", default=False, help="Explicit full run (default behavior)")
    args = parser.parse_args()

    if args.layer and args.layers:
        print("ERROR: Use --layer OR --layers, not both.")
        raise SystemExit(1)
    if args.check and (args.layer or args.layers):
        print("ERROR: --check is exclusive with --layer/--layers.")
        raise SystemExit(1)

    if args.layer:
        SELECTED_LAYER = args.layer
    elif args.layers:
        parts = args.layers.split("-")
        if len(parts) == 2:
            SELECTED_LAYER_RANGE = (int(parts[0]), int(parts[1]))
        else:
            print(f"ERROR: Invalid layer range '{args.layers}'. Use format: 37-41")
            raise SystemExit(1)
    elif args.check:
        SELECTED_CHECK = args.check
    elif args.quick:
        QUICK_MODE = True

    raise SystemExit(SmokeRunner().run())
