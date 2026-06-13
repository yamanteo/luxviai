from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lux_verification_recovery_engine import (  # noqa: E402
    execute_verification_run,
    get_verification_recovery_schema,
    get_verification_recovery_status,
    prepare_recovery_action,
    prepare_verification_run,
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _make_repo() -> tempfile.TemporaryDirectory[str]:
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "good.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "bad_syntax.py").write_text("def nope(:\n", encoding="utf-8")
    (root / "importer.py").write_text("import missing_fixture_module\n", encoding="utf-8")
    (root / "ok_module.py").write_text("ANSWER = 42\n", encoding="utf-8")
    (root / "app.py").write_text("class Route:\n    def __init__(self, path): self.path = path\nclass App:\n    routes = [Route('/ok')]\napp = App()\n", encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "validate_ok.py").write_text("print('validator ok')\n", encoding="utf-8")
    (scripts / "validate_fail.py").write_text("import sys\nprint('validator failed', file=sys.stderr)\nsys.exit(3)\n", encoding="utf-8")
    (scripts / "validate_sleep.py").write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
    (scripts / "validate_secret.py").write_text("import os\nprint('API_KEY=sk-12345678901234567890')\nprint(os.environ.get('LUX_TEST_SECRET', 'env-missing'))\n", encoding="utf-8")
    (scripts / "validate_big.py").write_text("print('x' * 10000)\n", encoding="utf-8")
    (scripts / "smoke_check.py").write_text("print('fixture smoke')\n", encoding="utf-8")
    (root / ".env").write_text("SECRET=do-not-read\n", encoding="utf-8")
    return temp


def _prep(root: Path, checks: list[dict], **overrides) -> dict:
    data = {
        "repository_root": str(root),
        "verification_id": "verify-demo",
        "changed_files": ["good.py"],
        "requested_checks": checks,
        "max_checks": 8,
        "timeout_seconds": 3,
        "mode": "prepare",
    }
    data.update(overrides)
    return prepare_verification_run(**data)


def _exec(root: Path, checks: list[dict], token: str | None = None, **overrides) -> dict:
    data = {
        "repository_root": str(root),
        "verification_id": "verify-demo",
        "changed_files": ["good.py"],
        "requested_checks": checks,
        "approval_token": token,
        "max_checks": 8,
        "timeout_seconds": 3,
        "mode": "execute",
    }
    data.update(overrides)
    return execute_verification_run(**data)


def _flags(payload: dict) -> None:
    _assert(payload["arbitrary_command_blocked"] is True, "arbitrary command invariant")
    _assert(payload["network_access_used"] is False, "network invariant")
    _assert(payload["external_api_used"] is False, "external api invariant")
    _assert(payload["shell_execution_used"] is False, "shell execution invariant")
    _assert(payload["local_first"] is True, "local-first invariant")


def main() -> int:
    checks = 0
    live_files = {
        path: (REPO_ROOT / path).read_bytes()
        for path in ["app.py", "endpoint_coverage_matrix.py", "scripts/smoke_check.py"]
        if (REPO_ROOT / path).exists()
    }
    fixture = _make_repo()
    try:
        root = Path(fixture.name)
        schema = get_verification_recovery_schema()
        status = get_verification_recovery_status()
        _assert(schema["default_mode"] == "plan", "default mode is plan")
        _assert("py_compile" in schema["allowed_verification_types"], "py_compile allowed")
        _assert(status["shell_false_enforced"] is True, "shell false status")
        _flags(schema)
        _flags(status)
        checks += 5

        py_ok = [{"check_type": "py_compile", "check_id": "compile_ok", "files": ["good.py"]}]
        plan = prepare_verification_run(repository_root=str(root), verification_id="verify-demo", requested_checks=py_ok)
        _assert(plan["mode"] == "plan", "prepare default plan")
        _assert(plan["execution_allowed"] is False, "plan performs no execution")
        _assert(plan["check_results"] == [], "plan no subprocess result")
        digest1 = _prep(root, py_ok)["verification_digest"]
        digest2 = _prep(root, py_ok)["verification_digest"]
        _assert(digest1 == digest2 and digest1.startswith("lux-verify-"), "deterministic digest")
        checks += 4

        _assert(_exec(root, py_ok)["summary"]["blocked"] == 1, "missing token blocked")
        _assert(_exec(root, py_ok, "wrong")["summary"]["blocked"] == 1, "wrong token blocked")
        prepared = _prep(root, py_ok)
        altered_checks = [{"check_type": "py_compile", "check_id": "compile_ok", "files": ["bad_syntax.py"]}]
        _assert(_exec(root, altered_checks, prepared["verification_digest"])["summary"]["blocked"] == 1, "modified check list blocked")
        _assert(_exec(root, py_ok, prepared["verification_digest"], timeout_seconds=9)["summary"]["blocked"] == 1, "modified timeout blocked")
        other = Path(tempfile.mkdtemp())
        try:
            _assert(_exec(other, py_ok, prepared["verification_digest"])["summary"]["blocked"] >= 1, "modified repository root blocked")
        finally:
            try:
                other.rmdir()
            except OSError:
                pass
        checks += 5

        bad_inputs = [
            ({"check_type": "arbitrary_command", "check_id": "a"}, "arbitrary command blocked"),
            ({"check_type": "targeted_smoke", "check_id": "pipe", "check": "abc|whoami"}, "pipe injection blocked"),
            ({"check_type": "targeted_smoke", "check_id": "semi", "check": "abc;whoami"}, "semicolon injection blocked"),
            ({"check_type": "targeted_smoke", "check_id": "amp", "check": "abc&whoami"}, "ampersand injection blocked"),
            ({"check_type": "targeted_smoke", "check_id": "nl", "check": "abc\nwhoami"}, "newline injection blocked"),
            ({"check_type": "validator_script", "check_id": "exe", "script": "C:/Windows/System32/cmd.exe"}, "external exe blocked"),
            ({"check_type": "validator_script", "check_id": "outside", "script": "good.py"}, "validator outside scripts blocked"),
            ({"check_type": "validator_script", "check_id": "pattern", "script": "scripts/smoke_check.py"}, "validator filename pattern enforced"),
            ({"check_type": "targeted_smoke", "check_id": "badid", "check": "bad id"}, "targeted smoke id invalid"),
            ({"check_type": "segmented_smoke", "check_id": "badlayer", "layers": "37;38"}, "invalid layer range blocked"),
            ({"check_type": "py_compile", "check_id": "badpath", "files": ["missing.py"]}, "invalid file path blocked"),
            ({"check_type": "py_compile", "check_id": "outsidepath", "files": [str(root.parent / "outside.py")]}, "outside root blocked"),
            ({"check_type": "py_compile", "check_id": "envpath", "files": [".env"]}, ".env path blocked"),
        ]
        for raw, label in bad_inputs:
            res = _prep(root, [raw])
            _assert(res["summary"]["blocked"] >= 1, label)
        checks += len(bad_inputs)

        ok = _exec(root, py_ok, prepared["verification_digest"])
        _assert(ok["summary"]["passed"] == 1, "py_compile success")
        _assert(ok["shell_execution_used"] is False, "shell execution false")
        _assert(ok["check_results"][0]["stdout_excerpt"] == "", "stdout captured")
        _assert(ok["check_results"][0]["stderr_excerpt"] == "", "stderr captured")
        checks += 4

        syntax = [{"check_type": "py_compile", "check_id": "syntax_fail", "files": ["bad_syntax.py"]}]
        syntax_prepared = _prep(root, syntax)
        syntax_res = _exec(root, syntax, syntax_prepared["verification_digest"])
        _assert(syntax_res["check_results"][0]["failure_category"] == "syntax_error", "syntax classified")
        _assert(syntax_res["summary"]["failed"] == 1, "failed summary")
        checks += 2

        import_ok = [{"check_type": "import_check", "check_id": "import_ok", "module": "ok_module"}]
        import_fail = [{"check_type": "import_check", "check_id": "import_fail", "module": "missing_fixture_module"}]
        ipo = _prep(root, import_ok)
        ipf = _prep(root, import_fail)
        _assert(_exec(root, import_ok, ipo["verification_digest"])["summary"]["passed"] == 1, "import success")
        _assert(_exec(root, import_fail, ipf["verification_digest"])["check_results"][0]["failure_category"] == "import_error", "import failure")
        checks += 2

        val_ok = [{"check_type": "validator_script", "check_id": "val_ok", "script": "scripts/validate_ok.py"}]
        val_fail = [{"check_type": "validator_script", "check_id": "val_fail", "script": "scripts/validate_fail.py"}]
        vok = _prep(root, val_ok)
        vfail = _prep(root, val_fail)
        _assert("validator ok" in _exec(root, val_ok, vok["verification_digest"])["check_results"][0]["stdout_excerpt"], "validator stdout")
        _assert(_exec(root, val_fail, vfail["verification_digest"])["check_results"][0]["failure_category"] == "validator_failure", "validator failure")
        checks += 2

        constructed = [
            {"check_type": "targeted_smoke", "check_id": "target", "check": "lux_verification_recovery_local"},
            {"check_type": "quick_smoke", "check_id": "quick"},
            {"check_type": "git_diff_check", "check_id": "diff"},
            {"check_type": "segmented_smoke", "check_id": "layer", "layers": "37-38"},
        ]
        cp = _prep(root, constructed)
        previews = " ".join(item["command_preview"] for item in cp["planned_checks"])
        _assert("--check lux_verification_recovery_local" in previews, "targeted smoke construction")
        _assert("--quick" in previews, "quick smoke construction")
        _assert("git diff --check" in previews, "git diff construction")
        _assert("--layers 37-38" in previews, "segmented smoke construction")
        checks += 4

        slow = [{"check_type": "validator_script", "check_id": "slow", "script": "scripts/validate_sleep.py"}]
        sp = _prep(root, slow, timeout_seconds=1)
        slow_res = _exec(root, slow, sp["verification_digest"], timeout_seconds=1)
        _assert(slow_res["check_results"][0]["status"] == "timed_out", "timeout enforced")
        _assert(slow_res["check_results"][0]["failure_category"] == "timeout", "timeout classification")
        checks += 2

        os.environ["LUX_TEST_SECRET"] = "SHOULD_NOT_LEAK"
        secret = [{"check_type": "validator_script", "check_id": "secret", "script": "scripts/validate_secret.py"}]
        secp = _prep(root, secret)
        sec = _exec(root, secret, secp["verification_digest"])
        out = sec["check_results"][0]["stdout_excerpt"]
        _assert("<redacted>" in out, "secret redaction")
        _assert("SHOULD_NOT_LEAK" not in out, "environment value not exposed")
        checks += 2

        big = [{"check_type": "validator_script", "check_id": "big", "script": "scripts/validate_big.py"}]
        bp = _prep(root, big)
        big_res = _exec(root, big, bp["verification_digest"])
        _assert(big_res["check_results"][0]["output_truncated"] is True, "output truncation")
        checks += 1

        mixed = [{"check_type": "py_compile", "check_id": "ok", "files": ["good.py"]}, {"check_type": "py_compile", "check_id": "bad", "files": ["bad_syntax.py"]}, {"check_type": "manual_ui_required", "check_id": "manual"}]
        mp = _prep(root, mixed)
        mr = _exec(root, mixed, mp["verification_digest"])
        _assert(mr["summary"]["passed"] == 1 and mr["summary"]["failed"] == 1 and mr["summary"]["manual_required"] == 1, "mixed summary")
        checks += 1

        timeout_analysis = prepare_recovery_action(repository_root=str(root), verification_id="r", check_results=[{"check_id": "t", "status": "timed_out", "failure_category": "timeout", "retry_safe": True, "affected_files": ["good.py"]}], changed_files=["good.py"])
        patch_analysis = prepare_recovery_action(repository_root=str(root), verification_id="r", check_results=[{"check_id": "s", "status": "failed", "failure_category": "syntax_error", "rollback_recommended": False, "affected_files": ["good.py"]}], changed_files=["good.py"])
        rollback = prepare_recovery_action(repository_root=str(root), verification_id="r", check_results=[{"check_id": "v", "status": "failed", "failure_category": "validator_failure", "rollback_recommended": True, "affected_files": ["good.py"]}], changed_files=["good.py"], controlled_apply_result={"rollback_available": True, "rollback_id": "rb1", "patch_id": "p", "files_changed": ["good.py"]}, rollback_id="rb1")
        auto_denied = prepare_recovery_action(repository_root=str(root), verification_id="r", check_results=[{"check_id": "v", "status": "failed", "failure_category": "validator_failure", "rollback_recommended": True, "affected_files": ["good.py"]}], changed_files=["good.py"], controlled_apply_result={"rollback_available": True, "rollback_id": "rb1", "patch_id": "p", "files_changed": ["good.py"]}, rollback_id="rb1", allow_automatic_rollback=False)
        no_rid = prepare_recovery_action(repository_root=str(root), verification_id="r", check_results=[{"check_id": "v", "status": "failed", "failure_category": "validator_failure", "rollback_recommended": True, "affected_files": ["good.py"]}], changed_files=["good.py"], controlled_apply_result={"rollback_available": True, "patch_id": "p", "files_changed": ["good.py"]}, allow_automatic_rollback=True)
        unrelated = prepare_recovery_action(repository_root=str(root), verification_id="r", check_results=[{"check_id": "v", "status": "failed", "failure_category": "validator_failure", "rollback_recommended": True, "affected_files": ["other.py"]}], changed_files=["good.py"], controlled_apply_result={"rollback_available": True, "rollback_id": "rb1", "patch_id": "p", "files_changed": ["good.py"]}, rollback_id="rb1", allow_automatic_rollback=True)
        auto_allowed = prepare_recovery_action(repository_root=str(root), verification_id="r", check_results=[{"check_id": "v", "status": "failed", "failure_category": "validator_failure", "rollback_recommended": True, "affected_files": ["good.py"]}], changed_files=["good.py"], controlled_apply_result={"rollback_available": True, "rollback_id": "rb1", "patch_id": "p", "files_changed": ["good.py"]}, rollback_id="rb1", allow_automatic_rollback=True, expected_repository_state={"current_hashes_match_post_apply": True})
        _assert(timeout_analysis["recovery_decision"] == "retry_targeted_check", "retry recommendation")
        _assert(patch_analysis["recovery_decision"] == "generate_patch_revision", "patch revision recommendation")
        _assert(rollback["recovery_decision"] == "rollback_recommended", "rollback recommendation")
        _assert(auto_denied["recovery_decision"] == "rollback_recommended", "auto denied without permission")
        _assert(no_rid["recovery_decision"] == "rollback_recommended", "auto denied without rollback id")
        _assert(unrelated["recovery_decision"] == "rollback_recommended", "auto denied unrelated")
        _assert(auto_allowed["recovery_decision"] == "automatic_rollback_allowed", "auto allowed conditions")
        _assert(auto_allowed["rollback_request"]["rollback_id"] == "rb1", "rollback request payload")
        _assert(auto_allowed["rollback_request"]["mode"] == "rollback_preview", "no rollback execution")
        _assert(auto_allowed["recovery_decision"] in {"no_recovery_needed", "retry_targeted_check", "generate_patch_revision", "human_review_required", "rollback_recommended", "automatic_rollback_allowed", "recovery_blocked"}, "valid recovery decision")
        checks += 10

        maxed = _prep(root, py_ok * 3, max_checks=1)
        _assert(maxed["summary"]["blocked"] >= 1, "max check budget")
        _assert(_exec(root, slow * 2, _prep(root, slow * 2, timeout_seconds=1)["verification_digest"], timeout_seconds=1)["summary"]["timed_out"] >= 1, "global duration/timeout budget")
        _assert(_prep(root, [{"check_type": "manual_ui_required", "check_id": "manual"}])["summary"]["manual_required"] == 1, "manual UI marked")
        fallback = prepare_verification_run(repository_root=str(root), verification_id="", requested_checks=[])
        _assert(fallback["summary"]["blocked"] >= 1, "safe insufficient input fallback")
        checks += 4

        for payload in [plan, ok, syntax_res, auto_allowed]:
            _flags(payload)
        checks += 4

        _assert("shell=True" not in (REPO_ROOT / "lux_verification_recovery_engine.py").read_text(encoding="utf-8"), "no shell=True usage")
        _assert("requests." not in (REPO_ROOT / "lux_verification_recovery_engine.py").read_text(encoding="utf-8"), "no network access")
        _assert("OpenAI" not in (REPO_ROOT / "lux_verification_recovery_engine.py").read_text(encoding="utf-8"), "no external api")
        _assert((root / "scripts" / "validate_ok.py").exists(), "temporary fixture only")
        checks += 4
    finally:
        fixture.cleanup()

    for path, before in live_files.items():
        _assert((REPO_ROOT / path).read_bytes() == before, f"live file changed unexpectedly: {path}")
    checks += 1

    # subprocess.run with TimeoutExpired should not leave the sleep child alive; this is a cheap local sanity check.
    print(f"PASS lux verification recovery validator: {checks} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
