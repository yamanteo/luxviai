from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fixture_response(request) -> str:
    return json.dumps(
        {
            "response_id": "rsp-tier1-validator-1",
            "request_id": request.request_id,
            "status": "completed",
            "analysis_summary": "fixture local model produced one safe patch operation",
            "completed_scope": ["tier1_patch_draft"],
            "remaining_gap": "safe_patch_preview_ready",
            "target_files": ["src/app.py"],
            "target_symbols": ["greet"],
            "patch_operations": [
                {
                    "operation_id": "op-tier1-1",
                    "operation_type": "replace_text",
                    "file_path": "src/app.py",
                    "anchor_text": "",
                    "old_text": "def greet():\n    return 1\n",
                    "new_text": "def greet():\n    return 2\n",
                    "expected_occurrences": 1,
                    "reason": "fixture local coding model patch",
                    "confidence": 0.97,
                }
            ],
            "validation_recommendations": ["preview", "py_compile"],
            "assumptions": [],
            "uncertainties": [],
            "risk_flags": [],
            "unsupported_requests": [],
            "model_metadata": {"runtime_id": "fixture_local_runtime", "local_only": True, "external_api_used": False},
        },
        sort_keys=True,
    )


def main() -> int:
    checks = []
    from luxcode_tier0_deterministic_executor import run_tier0_diagnostics
    from luxcode_tier1_local_worker import (
        build_safe_patch_contract_from_tier1_response,
        build_tier1_evidence,
        build_tier1_remaining_gap,
        build_tier1_request_from_tier0,
        check_ollama_health,
        check_ollama_model,
        execute_tier0_router_tier1_preview,
        parse_tier1_response,
        preview_tier1_safe_patch,
        validate_tier1_response,
    )

    with tempfile.TemporaryDirectory(prefix="luxcode_tier1_validator_") as tmp:
        repo = Path(tmp) / "repo"
        (repo / "src").mkdir(parents=True)
        (repo / "tests").mkdir()
        (repo / "src" / "app.py").write_text("def greet():\n    return 1\n", encoding="utf-8")
        (repo / "tests" / "test_app.py").write_text("from src.app import greet\nassert greet() == 1\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, text=True, timeout=10, shell=False)

        diagnostics = run_tier0_diagnostics(str(repo), "replace greet return", ["src/app.py"])
        checks.append(diagnostics.get("selected_tier") == 0)
        checks.append(bool(diagnostics.get("remaining_gap")))

        request = build_tier1_request_from_tier0(
            request_id="req-tier1-validator-1",
            task_id="task-tier1-validator-1",
            task_summary="Patch greet return using fixture local worker",
            tier0_diagnostics=diagnostics,
            target_files=["src/app.py"],
            target_symbols=["greet"],
            minimum_context={"src/app.py": "def greet():\n    return 1\n"},
        )
        checks.extend(
            [
                request.provider_id == "tier1_local_worker",
                request.required_output_format == "structured_json_v1",
                request.maximum_cost == 0.0,
                request.permission_mode == "preview_only",
            ]
        )

        response = parse_tier1_response(_fixture_response(request), request=request)
        checks.extend([response.request_id == request.request_id, len(response.patch_operations) == 1])

        validation = validate_tier1_response(
            request=request,
            response=response,
            known_files={"src/app.py"},
            known_symbols={"greet"},
            protected_files=set(),
            file_contents={"src/app.py": "def greet():\n    return 1\n"},
        )
        checks.extend([validation["valid"] is True, validation["status"] == "valid"])

        contract = build_safe_patch_contract_from_tier1_response(
            request=request,
            response=response,
            repository_root=str(repo),
            protected_files=[],
            file_contents={"src/app.py": "def greet():\n    return 1\n"},
        )
        preview = preview_tier1_safe_patch(contract)
        checks.extend(
            [
                contract.get("source") == "tier1_local_worker",
                len(contract.get("operations", [])) == 1,
                preview.get("operation_count") == 1,
                preview.get("files_to_modify") == ["src/app.py"],
                preview.get("approval_required") is True,
                preview.get("apply_allowed") is False,
            ]
        )

        evidence = build_tier1_evidence(request=request, response=response, patch_contract=contract, status="preview_ready")
        gap = build_tier1_remaining_gap(request=request, response=response)
        checks.extend(
            [
                evidence.get("tier") == 1,
                evidence.get("patch_digest") == contract.get("patch_digest"),
                gap.get("remaining_gap") == "safe_patch_preview_ready",
                gap.get("fallback_required") is False,
            ]
        )

        invalid_json_blocked = False
        try:
            parse_tier1_response("{", request=request)
        except ValueError:
            invalid_json_blocked = True
        checks.append(invalid_json_blocked)

        invalid = json.loads(_fixture_response(request))
        invalid["patch_operations"][0]["operation_type"] = "shell_operation"
        invalid_response = parse_tier1_response(json.dumps(invalid), request=request)
        invalid_validation = validate_tier1_response(
            request=request,
            response=invalid_response,
            known_files={"src/app.py"},
            known_symbols={"greet"},
            protected_files=set(),
            file_contents={"src/app.py": "def greet():\n    return 1\n"},
        )
        checks.extend([invalid_validation["valid"] is False, any(item["code"] == "unsupported_operation" for item in invalid_validation["issues"])])

        rejected = check_ollama_health("http://example.com:11434")
        checks.extend([rejected.get("ok") is False, rejected.get("state") == "endpoint_rejected"])
        missing = check_ollama_model("definitely_missing_tier1_fixture_model", endpoint="http://127.0.0.1:11434", timeout_seconds=2)
        checks.append(missing.get("state") in {"model_missing", "connection_failure", "timeout"})

        fallback = execute_tier0_router_tier1_preview(
            task_id="task-tier1-missing-model-validator",
            repository_root=str(repo),
            task_summary="Patch greet return using missing model",
            target_files=["src/app.py"],
            target_symbols=["greet"],
            minimum_context={"src/app.py": "def greet():\n    return 1\n"},
            model_id="definitely_missing_tier1_fixture_model",
            persist=False,
        )
        checks.extend(
            [
                fallback.get("ok") is False,
                fallback.get("state") == "tier1_not_selected",
                fallback.get("route_decision", {}).get("selected_primary_tier") != "lightweight_local_coding_model",
                bool(fallback.get("evidence", {}).get("failure_fingerprint")),
            ]
        )

    passed = sum(1 for item in checks if item)
    if passed != len(checks):
        print(f"validation_failed passed={passed} checks={len(checks)}")
        return 1
    print(f"checks={len(checks)}")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
