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
        assert "resumeUnavailableFallback" in html
        assert "Yalnızca bu son bölümün doğal devamını yaz" in html
        assert "interruptedState && isContinueCommand(text)" in html
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
        assert "if (interruptedState && !isContinueCommand(messageInput.value))" in html
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
        bullets = "\n".join(f"- Madde {i}" for i in range(1, 21))
        count_plan = {
            "kind": "model",
            "skip_save": False,
            "mode": "luxviai",
            "message": "20 madde yaz",
            "count_constraints": [{"kind": "bullet", "target": 20, "limit": "exact"}],
        }
        assert luxapp.should_auto_continue_response("length", bullets, count_plan) is False
        return "length simulation/count stop"

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
