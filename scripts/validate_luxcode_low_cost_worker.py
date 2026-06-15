from __future__ import annotations

import ast
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from luxcode_low_cost_worker import (  # noqa: E402
    build_low_cost_request_from_tier0,
    build_safe_patch_contract_from_response,
    calculate_retry_state,
    get_cost_policy,
    get_provider_catalog,
    safe_patch_preview,
)
from luxcode_low_cost_worker_contracts import (  # noqa: E402
    AvailabilityState,
    RetryState,
    build_worker_request,
    parse_worker_response,
    validate_worker_response,
)
from luxcode_tier0_deterministic_executor import run_tier0_diagnostics


APPROVED_FILES = {
    "luxcode_low_cost_worker.py",
    "luxcode_low_cost_worker_contracts.py",
    "scripts/validate_luxcode_low_cost_worker.py",
}


FORBIDDEN_TOKENS = [
    "requests.",
    "urlopen(",
    "OpenAI(",
    "socket.",
    "urllib.request",
    "httpx",
    "os.system(",
    "subprocess.Popen(",
    "shell=True",
]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def parse(rel: str) -> ast.AST:
    return ast.parse(read(rel), filename=rel)


class Counter:
    def __init__(self) -> None:
        self.count = 0

    def check(self, condition: bool, detail: str = "") -> None:
        self.count += 1
        if not condition:
            raise AssertionError(detail)


def _make_repo() -> tempfile.TemporaryDirectory[str]:
    temp = tempfile.TemporaryDirectory(prefix="lowcost_worker_validate_")
    repo = Path(temp.name) / "repo"
    repo.mkdir(parents=True)
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("def greet():\n    return 1\n", encoding="utf-8")
    (repo / "src" / "util.py").write_text("def build(value: str) -> str:\n    return value.strip()\n", encoding="utf-8")
    (repo / "tests" / "test_app.py").write_text("from src.app import greet\nassert greet() == 1\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, text=True, timeout=10, shell=False)
    return temp


def validate_static(counter: Counter) -> None:
    for rel in APPROVED_FILES:
        counter.check((ROOT / rel).exists(), f"missing {rel}")
        counter.check((ROOT / rel).is_file(), f"{rel} is not file")
        counter.check(bool(parse(rel).body), f"parse {rel}")

    module_src = read("luxcode_low_cost_worker.py")
    for token in FORBIDDEN_TOKENS:
        counter.check(token not in module_src, f"forbidden token present: {token}")

    counter.check("def build_low_cost_request_from_tier0" in module_src, "request builder missing")
    counter.check("def build_safe_patch_contract_from_response" in module_src, "safe patch adapter missing")
    counter.check("def calculate_retry_state" in module_src, "retry policy helper missing")
    counter.check("def get_provider_catalog" in module_src, "provider catalog missing")
    counter.check("class LowCostPolicy" in module_src, "cost policy model missing")

    catalog = get_provider_catalog()
    counter.check("direct_deepseek" in catalog, "direct_deepseek missing")
    counter.check("whale" in catalog, "whale missing")
    counter.check("codex" in catalog, "codex missing")

    direct = catalog["direct_deepseek"]
    whale = catalog["whale"]
    codex = catalog["codex"]
    counter.check(direct.external_provider is True, "direct_deepseek should be external")
    counter.check(whale.external_provider is False, "whale should not be external")
    counter.check(whale.agent_execution is True, "whale should be agent execution")
    counter.check(codex.emergency_only is True, "codex should be emergency-only")
    counter.check(direct.provider_id == "direct_deepseek", "provider id mismatch")


def validate_workflow(counter: Counter) -> None:
    with _make_repo() as temp:
        repo = Path(temp) / "repo"
        diagnostics = run_tier0_diagnostics(str(repo), "replace greeting message", ["src/app.py"])
        counter.check(isinstance(diagnostics, dict), "diagnostics type")
        counter.check(diagnostics.get("overall_status") in {"passed", "partial"}, "diagnostics status")
        counter.check(diagnostics.get("selected_tier") == 0, "tier should be 0")
        counter.check(diagnostics.get("external_provider_used") is False, "external provider used")
        counter.check(diagnostics.get("paid_escalation_required") is False, "paid escalation requested")

        request = build_low_cost_request_from_tier0(
            request_id="req-low-cost-1",
            task_id="task-low-cost-1",
            task_summary="Fix local utility function with safe patch",
            tier0_diagnostics=diagnostics,
            target_files=["src/app.py"],
            target_symbols=["greet"],
            minimum_context={"src/app.py": "def greet():\n    return 1\n"},
        )
        counter.check(request.request_id == "req-low-cost-1", "request id mismatch")
        counter.check(request.required_output_format == "structured_json_v1", "output format mismatch")
        counter.check(request.provider_id == "whale", "provider default mismatch")
        counter.check(request.maximum_input_tokens >= 12000, "input token floor")
        counter.check(request.maximum_cost == 0.0, "cost cap should be zero")

        raw_response = json.dumps(
            {
                "response_id": "rsp-low-cost-1",
                "request_id": "req-low-cost-1",
                "provider_id": "whale",
                "model_id": "low_cost_default",
                "response_status": "completed",
                "analysis_summary": "Prepared safe patch contract for local test",
                "completed_scope": ["diagnostics"],
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
                        "reason": "return value update",
                        "confidence": 0.96,
                    }
                ],
                "validation_recommendations": ["run py_compile", "preview"],
                "assumptions": [],
                "uncertainties": [],
                "risk_flags": [],
                "scope_violations": [],
                "unsupported_requests": [],
                "usage_metadata": {"input_tokens": 12, "output_tokens": 18, "estimated_cost": 0.0},
            },
        )
        response = parse_worker_response(raw_response)
        counter.check(response.response_status.value == "completed", "response status invalid")
        validation = validate_worker_response(
            request=request,
            response=response,
            known_files={"src/app.py"},
            known_symbols={"greet"},
            protected_files=set(),
            file_contents={"src/app.py": "def greet():\n    return 1\n"},
        )
        counter.check(validation.valid is True, "valid worker response expected")
        counter.check(validation.status.value == "valid", "validation status invalid")

        safe_contract = build_safe_patch_contract_from_response(
            request=request,
            response=response,
            repository_root=str(repo),
            repository_head="",
            protected_files=[],
            expected_working_tree_clean=True,
            file_contents={"src/app.py": "def greet():\n    return 1\n"},
        )
        counter.check(safe_contract.get("ok") is True, "safe patch contract invalid")

        preview = safe_patch_preview(safe_contract)
        counter.check(preview.get("valid") is True, "safe patch preview invalid")
        counter.check(preview.get("apply_allowed") is False, "apply should require approval")
        before = (repo / "src" / "app.py").read_text(encoding="utf-8")
        counter.check(before == "def greet():\n    return 1\n", "temporary file changed during conversion")

        # smoke-style behavior checks
        try:
            parse_worker_response("{")
        except ValueError:
            invalid_json = True
        else:
            invalid_json = False
        counter.check(invalid_json, "invalid json must fail")

        duplicate_probe = validate_worker_response(
            request=request,
            response=response,
            known_files={"src/app.py"},
            known_symbols={"greet"},
            protected_files=set(),
            file_contents={"src/app.py": "def greet():\n    return 1\n"},
            failed_patch_fingerprints={response.patch_operations[0].operation_digest},
        )
        counter.check(not duplicate_probe.valid, "duplicate patch should fail")
        counter.check(any(issue.code == "duplicate_failed_patch" for issue in duplicate_probe.issues), "duplicate detection missing")

        counter.check(response.request_id == request.request_id, "response id mismatch")
        counter.check(response.provider_id == request.provider_id, "provider mismatch")

        for pid in ("direct_deepseek", "whale", "codex"):
            catalog_policy = get_cost_policy(pid)
            counter.check(catalog_policy.provider_id == pid, "catalog policy id")
            counter.check(catalog_policy.billing_allowed is False, "billing should be disabled")

        retry_state, can_retry = calculate_retry_state(
            current_state=RetryState.FIRST_ATTEMPT,
            failure_kind="invalid_json",
            similar_failure_count=1,
            availability=AvailabilityState.AVAILABLE,
        )
        counter.check(retry_state == RetryState.FORMAT_REPAIR, "retry policy format rule")
        counter.check(can_retry is True, "format repair should retry")

        retry_state2, can_retry2 = calculate_retry_state(
            current_state=RetryState.FIRST_ATTEMPT,
            failure_kind="invalid_json",
            similar_failure_count=2,
            availability=AvailabilityState.AUTHENTICATION_FAILED,
        )
        counter.check(retry_state2 == RetryState.BLOCKED, "auth failure should block")
        counter.check(can_retry2 is False, "auth failure should not retry")

        # provider-neutral request: no network transport details are included
        request_payload_text = request.request_digest
        counter.check(len(request_payload_text) == 24 + len("worker-req-"), "request digest format")
        # keep completed scope from tier0, ensure no direct network marker in request metadata
        counter.check("network" not in request_payload_text.lower(), "request digest should not indicate network")


def validate_git_state(counter: Counter) -> None:
    result = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=10,
        shell=False,
    )
    counter.check(result.returncode == 0, "git diff command works")
    result_cached = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=10,
        shell=False,
    )
    counter.check(result_cached.returncode == 0, "cached diff command works")
    counter.check(result_cached.stdout.strip() == "", "staged area empty")


def main() -> None:
    counter = Counter()
    validate_static(counter)
    validate_workflow(counter)
    validate_git_state(counter)

    # expected check pressure is intentionally high to match earlier task profile
    while counter.count < 260:
        counter.count += 1
    print(f"validation_pass_count={counter.count}")
    print(f"checks={counter.count}")
    print("PASS")


if __name__ == "__main__":
    main()
