from __future__ import annotations

import json
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _reason(decision, engine_id):
    for item in decision.get("rejected_candidates", []):
        if item.get("engine_id") == engine_id:
            return str(item.get("reason", ""))
    return ""


def main() -> int:
    from luxcode_first_usable_registry import (
        ALL_ENGINE_IDS,
        ENGINE_ORDER,
        build_safe_config,
        engine_failure_fingerprint,
        get_unified_engine_registry,
        select_engine_preview,
    )
    from luxcode_first_usable_session_flow import (
        build_decision_event,
        build_first_usable_restore_policy,
        build_guard_fingerprints,
        build_handoff_preview,
        build_fixture_safe_patch_preview,
        build_request_envelope,
        build_result_envelope,
        build_runtime_health_snapshot,
        build_session_state,
        execute_fixture_safe_workflow,
    )

    checks = []
    registry = get_unified_engine_registry()
    config = build_safe_config()

    checks.extend(
        [
            list(registry.keys()) == ALL_ENGINE_IDS,
            ENGINE_ORDER == ["tier0_deterministic", "tier1_local_worker", "free_gemini", "free_32b", "direct_deepseek", "whale", "codex"],
            registry["tier0_deterministic"]["enabled"] is True,
            registry["tier0_deterministic"]["verified"] is True,
            registry["tier0_deterministic"]["cost_class"] == "zero",
            registry["tier1_local_worker"]["enabled"] is True,
            registry["tier1_local_worker"]["cost_class"] == "zero",
            registry["tier1_local_worker"]["local_only"] is True,
            registry["free_gemini"]["enabled"] is False,
            registry["free_gemini"]["verified"] is False,
            registry["free_32b"]["enabled"] is False,
            registry["free_32b"]["verified"] is False,
            registry["direct_deepseek"]["enabled"] is False,
            registry["direct_deepseek"]["cost_class"] == "paid",
            registry["direct_deepseek"]["requires_api_key"] is True,
            registry["direct_deepseek"]["requires_user_approval"] is True,
            registry["whale"]["manual_only"] is True,
            registry["whale"]["agent_execution"] is True,
            registry["codex"]["manual_only"] is True,
            registry["codex"]["emergency_only"] is True,
            config["network_allowed"] is False,
            config["billing_allowed"] is False,
            config["paid_escalation_allowed"] is False,
            config["approval_required"] is True,
            config["auto_apply_allowed"] is False,
            config["runtime_start_allowed"] is False,
            config["model_download_allowed"] is False,
            isinstance(config["config_digest"], str) and config["config_digest"].startswith("first-usable-config-"),
        ]
    )

    completed = select_engine_preview(completed=True, completed_scope=["tier0_deterministic"], remaining_gap={"remaining_gap": "none"})
    checks.extend([completed["selected_engine"] is None, completed["reason"] == "completed_no_engine_selected"])

    tier0 = select_engine_preview(completed=False, remaining_gap={"remaining_gap": "start local"})
    checks.extend([tier0["selected_engine"] == "tier0_deterministic", tier0["selected_tier"] == 0])

    tier1 = select_engine_preview(
        completed=False,
        completed_scope=["tier0_deterministic"],
        remaining_gap={"remaining_gap": "tier0_partial"},
        runtime_health={"tier1_local_worker": "healthy"},
    )
    checks.extend([tier1["selected_engine"] == "tier1_local_worker", tier1["reason"] == "tier1_runtime_healthy"])

    no_auto_paid = select_engine_preview(
        completed=False,
        completed_scope=["tier0_deterministic"],
        remaining_gap={"remaining_gap": "tier1 unavailable"},
        runtime_health={"tier1_local_worker": "unavailable"},
        registry_overrides={"direct_deepseek": {"enabled": True, "availability": "available"}},
        free_tier_exhaustion_confirmed=False,
    )
    checks.extend([no_auto_paid["selected_engine"] is None, "free_tiers_not_exhausted" in _reason(no_auto_paid, "direct_deepseek")])

    gemini_unverified = select_engine_preview(
        completed=False,
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        remaining_gap={"remaining_gap": "try free placeholder"},
        registry_overrides={"free_gemini": {"enabled": True, "verified": False, "availability": "available"}},
    )
    checks.extend([gemini_unverified["selected_engine"] is None, "engine_unverified" in _reason(gemini_unverified, "free_gemini")])

    free32 = select_engine_preview(
        completed=False,
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        remaining_gap={"remaining_gap": "free 32b candidate"},
        registry_overrides={
            "free_gemini": {"enabled": True, "verified": False, "availability": "available"},
            "free_32b": {"enabled": True, "verified": True, "availability": "available"},
            "direct_deepseek": {"enabled": True, "availability": "available"},
        },
        config_overrides={"network_allowed": True, "billing_allowed": True, "paid_escalation_allowed": True, "maximum_cost_per_request": 0.001},
        free_tier_exhaustion_confirmed=True,
        paid_escalation_approved=True,
        cost_budget=0.001,
    )
    checks.extend([free32["selected_engine"] == "free_32b", free32["selected_tier"] == 3])

    deepseek_base = {
        "completed": False,
        "completed_scope": ["tier0_deterministic", "tier1_local_worker"],
        "remaining_gap": {"remaining_gap": "paid candidate"},
        "registry_overrides": {
            "free_gemini": {"enabled": False},
            "free_32b": {"enabled": False},
            "direct_deepseek": {"enabled": True, "availability": "available"},
        },
        "config_overrides": {"network_allowed": True, "billing_allowed": True, "paid_escalation_allowed": True, "maximum_cost_per_request": 0.001},
        "paid_escalation_approved": True,
        "free_tier_exhaustion_confirmed": True,
        "cost_budget": 0.001,
    }
    deepseek_allowed = select_engine_preview(**deepseek_base)
    checks.extend([deepseek_allowed["selected_engine"] == "direct_deepseek", deepseek_allowed["required_approval"] is True])

    free_not_exhausted = select_engine_preview(**{**deepseek_base, "free_tier_exhaustion_confirmed": False})
    paid_false = select_engine_preview(**{**deepseek_base, "paid_escalation_approved": False})
    billing_false = select_engine_preview(**{**deepseek_base, "config_overrides": {"network_allowed": True, "billing_allowed": False, "paid_escalation_allowed": True, "maximum_cost_per_request": 0.001}})
    checks.extend(
        [
            free_not_exhausted["selected_engine"] is None and "free_tiers_not_exhausted" in _reason(free_not_exhausted, "direct_deepseek"),
            paid_false["selected_engine"] is None and "paid_escalation_not_approved" in _reason(paid_false, "direct_deepseek"),
            billing_false["selected_engine"] is None and "paid_network_or_billing_gate_closed" in _reason(billing_false, "direct_deepseek"),
        ]
    )

    whale = select_engine_preview(completed=False, completed_scope=list(ENGINE_ORDER[:-2]), remaining_gap={"remaining_gap": "manual needed"})
    codex = select_engine_preview(completed=False, completed_scope=list(ENGINE_ORDER[:-1]), remaining_gap={"remaining_gap": "emergency needed"}, manual_request=True)
    checks.extend(["manual_request_required" in _reason(whale, "whale"), "emergency_manual_request_required" in _reason(codex, "codex")])

    fp = engine_failure_fingerprint("tier0_deterministic", {"remaining_gap": "loop guard"})
    loop_guard = select_engine_preview(completed=False, remaining_gap={"remaining_gap": "loop guard"}, failed_engine_fingerprints=[fp], runtime_health={"tier1_local_worker": "healthy"})
    checks.extend([loop_guard["selected_engine"] == "tier1_local_worker", "repeated_failure_fingerprint" in _reason(loop_guard, "tier0_deterministic")])

    fail_closed = select_engine_preview(completed=False, remaining_gap={"remaining_gap": "bad config"}, config_overrides={"engine_order": ["unknown-new-engine"], "network_allowed": "yes"})
    checks.extend([fail_closed["selected_engine"] is None, fail_closed["fallback_chain"] == []])

    digest_a = select_engine_preview(completed=False, remaining_gap={"remaining_gap": "stable digest"})
    digest_b = select_engine_preview(completed=False, remaining_gap={"remaining_gap": "stable digest"})
    checks.append(digest_a["decision_digest"] == digest_b["decision_digest"])
    checks.extend(["completed_scope" not in digest_a["decision_context"], "tier0_deterministic" not in json.dumps(digest_a["decision_context"])])

    session = {"session_id": "session-first-usable-validator", "task_id": "task-first-usable-validator", "task_summary": "Fix greet only"}
    healthy_tier1 = build_runtime_health_snapshot("tier1_local_worker", health_status="healthy")
    stopped = build_handoff_preview(
        session=session,
        completed=True,
        completed_scope=["tier0_deterministic"],
        remaining_gap={"remaining_gap": "none"},
        minimum_context={"src/app.py": "def greet():\n    return 1\n"},
    )
    checks.extend([stopped["request"] is None, stopped["stop_reason"] == "completed_by_lower_tier", stopped["session_state"]["current_stage"] == "completed"])

    tier0_preview = build_handoff_preview(session=session, remaining_gap={"remaining_gap": "start"}, minimum_context={"src/app.py": "def greet():\n    return 1\n"}, target_files=["src/app.py"])
    checks.extend([tier0_preview["selected_engine"] == "tier0_deterministic", tier0_preview["request"] is not None, tier0_preview["execution_allowed"] is False])

    tier1_preview = build_handoff_preview(
        session=session,
        completed_scope=["tier0_deterministic"],
        remaining_gap={"remaining_gap": "tier0 partial"},
        minimum_context={"src/app.py": "def greet():\n    return 1\n", ".env": "DEEPSEEK_API_KEY=sk-secret-value"},
        target_files=["src/app.py"],
        target_symbols=["greet"],
        runtime_health_snapshots={"tier1_local_worker": healthy_tier1},
    )
    checks.extend(
        [
            tier1_preview["selected_engine"] == "tier1_local_worker",
            tier1_preview["request"]["remaining_gap"] == {"remaining_gap": "tier0 partial"},
            "completed_scope" not in tier1_preview["request"],
            "completed_scope_digest" in tier1_preview["request"],
            ".env" not in tier1_preview["request"]["minimum_context"],
            "sk-secret-value" not in json.dumps(tier1_preview),
        ]
    )

    cooldown = build_runtime_health_snapshot("tier1_local_worker", health_status="healthy", cooldown_until="2099-01-01T00:00:00Z")
    tier1_cooldown = build_handoff_preview(
        session=session,
        completed_scope=["tier0_deterministic"],
        remaining_gap={"remaining_gap": "tier1 cooldown"},
        runtime_health_snapshots={"tier1_local_worker": cooldown},
        registry_overrides={"direct_deepseek": {"enabled": True, "availability": "available"}},
        free_tier_exhaustion_confirmed=False,
    )
    checks.extend([tier1_cooldown["selected_engine"] is None, any("health_cooldown" == item.get("reason") for item in tier1_cooldown["decision"]["rejected_candidates"])])

    not_running = build_runtime_health_snapshot("tier1_local_worker", health_status="not_running")
    tier1_not_running = build_handoff_preview(
        session=session,
        completed_scope=["tier0_deterministic"],
        remaining_gap={"remaining_gap": "tier1 not running"},
        runtime_health_snapshots={"tier1_local_worker": not_running},
    )
    checks.extend([tier1_not_running["selected_engine"] is None, any("health_not_running" == item.get("reason") for item in tier1_not_running["decision"]["rejected_candidates"])])

    failed_fp = engine_failure_fingerprint("tier0_deterministic", {"remaining_gap": "loop guard 2"})
    loop_preview = build_handoff_preview(
        session=session,
        remaining_gap={"remaining_gap": "loop guard 2"},
        runtime_health_snapshots={"tier1_local_worker": healthy_tier1},
        failed_attempt_fingerprints=[failed_fp],
    )
    checks.extend([loop_preview["selected_engine"] == "tier1_local_worker", any(item.get("reason") == "repeated_failure_fingerprint" for item in loop_preview["decision"]["rejected_candidates"])])

    free32_preview = build_handoff_preview(
        session=session,
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        remaining_gap={"remaining_gap": "free 32b before paid"},
        registry_overrides={"free_32b": {"enabled": True, "verified": True, "availability": "available"}, "direct_deepseek": {"enabled": True, "availability": "available"}},
        config_overrides={"network_allowed": True, "billing_allowed": True, "paid_escalation_allowed": True, "maximum_cost_per_request": 0.001},
        free_tier_exhaustion_confirmed=True,
        paid_escalation_approved=True,
        cost_budget=0.001,
    )
    checks.append(free32_preview["selected_engine"] == "free_32b")

    deepseek_blocked = build_handoff_preview(
        session=session,
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        remaining_gap={"remaining_gap": "deepseek blocked"},
        registry_overrides={"direct_deepseek": {"enabled": True, "availability": "available"}},
        free_tier_exhaustion_confirmed=False,
        paid_escalation_approved=False,
    )
    checks.extend([deepseek_blocked["selected_engine"] is None, any("free_tiers_not_exhausted" in item.get("reason", "") for item in deepseek_blocked["decision"]["rejected_candidates"])])

    deepseek_preview = build_handoff_preview(
        session=session,
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        remaining_gap={"remaining_gap": "deepseek preview only"},
        registry_overrides={"free_gemini": {"enabled": False}, "free_32b": {"enabled": False}, "direct_deepseek": {"enabled": True, "availability": "available"}},
        config_overrides={"network_allowed": True, "billing_allowed": True, "paid_escalation_allowed": True, "maximum_cost_per_request": 0.001},
        free_tier_exhaustion_confirmed=True,
        paid_escalation_approved=True,
        cost_budget=0.001,
    )
    checks.extend([deepseek_preview["selected_engine"] == "direct_deepseek", deepseek_preview["required_approval"] is True, deepseek_preview["execution_allowed"] is False])

    whale_preview = build_handoff_preview(
        session=session,
        completed_scope=list(ENGINE_ORDER[:-2]),
        remaining_gap={"remaining_gap": "manual whale"},
        registry_overrides={"whale": {"enabled": True, "verified": True, "availability": "available"}},
        manual_request=True,
    )
    codex_preview = build_handoff_preview(
        session=session,
        completed_scope=list(ENGINE_ORDER[:-1]),
        remaining_gap={"remaining_gap": "emergency codex"},
        registry_overrides={"codex": {"enabled": True, "verified": True, "availability": "available"}},
        manual_request=True,
        emergency_request=True,
    )
    checks.extend([whale_preview["selected_engine"] == "whale", whale_preview["stop_reason"] == "handoff_required", codex_preview["selected_engine"] == "codex", codex_preview["stop_reason"] == "handoff_required"])

    empty_request = build_request_envelope(
        task_id="task-empty",
        session_id="session-empty",
        engine_id="tier1_local_worker",
        tier=1,
        task_summary="No remaining gap",
        remaining_gap="",
        completed_scope=[],
        target_files=[],
        target_symbols=[],
        minimum_context={},
    )
    checks.append(empty_request is None)

    seen_requests: set[str] = set()
    first_request = build_request_envelope(
        task_id="task-dup",
        session_id="session-dup",
        engine_id="tier1_local_worker",
        tier=1,
        task_summary="Duplicate request",
        remaining_gap={"remaining_gap": "same"},
        completed_scope=["tier0_deterministic"],
        target_files=["src/app.py"],
        target_symbols=[],
        minimum_context={"src/app.py": "content"},
        seen_request_digests=seen_requests,
    )
    duplicate_request = build_request_envelope(
        task_id="task-dup",
        session_id="session-dup",
        engine_id="tier1_local_worker",
        tier=1,
        task_summary="Duplicate request",
        remaining_gap={"remaining_gap": "same"},
        completed_scope=["tier0_deterministic"],
        target_files=["src/app.py"],
        target_symbols=[],
        minimum_context={"src/app.py": "content"},
        seen_request_digests=seen_requests,
    )
    checks.extend([first_request is not None, duplicate_request is None])

    result = build_result_envelope(
        request=first_request,
        status="completed",
        analysis_summary="verified summary only",
        completed_scope=["tier1_local_worker"],
        remaining_gap="",
        patch_operations=[{"operation_type": "replace_text", "old_text": "x", "new_text": "y"}],
        validation_recommendations=["preview"],
        usage_metadata={"input_tokens": None, "output_tokens": None},
    )
    invalid_result = build_result_envelope(request=first_request, status="not-a-status", analysis_summary="bad")
    checks.extend([result["status"] == "completed", result["result_digest"].startswith("result-"), invalid_result["status"] == "invalid"])

    session_state = build_session_state(
        session_id="session-state",
        task_id="task-state",
        current_stage="handoff_required",
        selected_engine="whale",
        selected_tier=5,
        completed_scope=["tier0_deterministic"],
        remaining_gap={"remaining_gap": "manual"},
        stop_reason="manual_only",
    )
    checks.extend([session_state["current_stage"] == "handoff_required", session_state["session_digest"].startswith("session-")])

    fingerprints = build_guard_fingerprints(task="task", context={"file": "x"}, request=first_request, response=result, engine_id="tier1_local_worker", validation_error="none")
    checks.extend([set(fingerprints) == {"task_fingerprint", "context_fingerprint", "request_fingerprint", "response_fingerprint", "engine_failure_fingerprint", "validation_failure_fingerprint"}])

    event = build_decision_event(
        session_id="session-event",
        task_id="task-event",
        engine=registry["tier1_local_worker"],
        event_type="selection",
        decision_reason="tier1_runtime_healthy",
        selected=True,
        rejected_reason=None,
        health_status="healthy",
        retry_state=None,
        estimated_cost=None,
        completed=False,
        remaining_gap={"remaining_gap": "event"},
        timestamp="2026-06-16T00:00:00Z",
    )
    event2 = build_decision_event(
        session_id="session-event",
        task_id="task-event",
        engine=registry["tier1_local_worker"],
        event_type="selection",
        decision_reason="tier1_runtime_healthy",
        selected=True,
        rejected_reason=None,
        health_status="healthy",
        retry_state=None,
        estimated_cost=None,
        completed=False,
        remaining_gap={"remaining_gap": "event"},
        timestamp="2026-06-16T00:00:00Z",
    )
    checks.extend([event["event_digest"] == event2["event_digest"], event["estimated_cost"] is None, event["event_id"].startswith("evt-")])

    seen_stage: set[str] = set()
    first_stage = build_handoff_preview(session=session, remaining_gap={"remaining_gap": "stage"}, minimum_context={"src/app.py": "x"}, seen_stage_input_digests=seen_stage)
    duplicate_stage = build_handoff_preview(session=session, remaining_gap={"remaining_gap": "stage"}, minimum_context={"src/app.py": "x"}, seen_stage_input_digests=seen_stage)
    checks.extend([first_stage["stop_reason"] == "worker_request_ready", duplicate_stage["stop_reason"] == "blocked", "duplicate_stage_input" in duplicate_stage["blockers"]])

    checks.extend(
        [
            build_runtime_health_snapshot("x", health_status="invalid")["health_status"] == "unknown",
            tier1_preview["request"]["request_digest"] == build_request_envelope(
                task_id=session["task_id"],
                session_id=session["session_id"],
                engine_id="tier1_local_worker",
                tier=1,
                task_summary=session["task_summary"],
                remaining_gap={"remaining_gap": "tier0 partial"},
                completed_scope=["tier0_deterministic"],
                target_files=["src/app.py"],
                target_symbols=["greet"],
                minimum_context={"src/app.py": "def greet():\n    return 1\n", ".env": "DEEPSEEK_API_KEY=sk-secret-value"},
            )["request_digest"],
            result["result_digest"] == build_result_envelope(
                request=first_request,
                status="completed",
                analysis_summary="verified summary only",
                completed_scope=["tier1_local_worker"],
                remaining_gap="",
                patch_operations=[{"operation_type": "replace_text", "old_text": "x", "new_text": "y"}],
                validation_recommendations=["preview"],
                usage_metadata={"input_tokens": None, "output_tokens": None},
            )["result_digest"],
        ]
    )

    with tempfile.TemporaryDirectory(prefix="first_usable_validator_") as tmp:
        repo = Path(tmp) / "repo"
        (repo / "src").mkdir(parents=True)
        app = repo / "src" / "app.py"
        original_text = "def greet():\n    return 1\n"
        app.write_text(original_text, encoding="utf-8")
        e2e_request = build_request_envelope(
            task_id="task-first-usable-e2e",
            session_id="session-first-usable-e2e",
            engine_id="tier1_local_worker",
            tier=1,
            task_summary="Fixture patch sk-secret-value",
            remaining_gap={"remaining_gap": "replace greet return"},
            completed_scope=["tier0_deterministic"],
            target_files=["src/app.py"],
            target_symbols=["greet"],
            minimum_context={"src/app.py": original_text, ".env": "API_KEY=sk-secret-value"},
        )
        patch_result = build_result_envelope(
            request=e2e_request,
            status="completed",
            analysis_summary="fixture patch result token=sk-secret-value",
            completed_scope=["tier1_local_worker"],
            remaining_gap="",
            patch_operations=[
                {
                    "operation_type": "replace_text",
                    "file_path": "src/app.py",
                    "old_text": original_text,
                    "new_text": "def greet():\n    return 2\n",
                    "reason": "fixture safe patch",
                }
            ],
            validation_recommendations=[{"type": "py_compile", "path": "src/app.py"}],
            evidence_records=[{"summary": "authorization bearer sk-secret-value"}],
        )
        preview = build_fixture_safe_patch_preview(str(repo), patch_result)
        checks.extend(
            [
                preview["operation_count"] == 1,
                preview["files_to_modify"] == ["src/app.py"],
                preview["approval_required"] is True,
                preview["approval_digest"].startswith("lux-approve-"),
                preview["precondition_hashes"].get("src/app.py"),
            ]
        )

        awaiting = execute_fixture_safe_workflow(
            repository_root=str(repo),
            request=e2e_request,
            result=patch_result,
            temporary_fixture_repo=True,
            approval_token=None,
            validation_plan=[{"type": "py_compile", "path": "src/app.py"}],
        )
        wrong = execute_fixture_safe_workflow(
            repository_root=str(repo),
            request=e2e_request,
            result=patch_result,
            temporary_fixture_repo=True,
            approval_token="wrong-approval",
            validation_plan=[{"type": "py_compile", "path": "src/app.py"}],
        )
        protected = execute_fixture_safe_workflow(
            repository_root=str(repo),
            request=e2e_request,
            result=patch_result,
            temporary_fixture_repo=False,
            approval_token=preview["approval_digest"],
            validation_plan=[{"type": "py_compile", "path": "src/app.py"}],
        )
        checks.extend(
            [
                awaiting["final_status"] == "awaiting_approval",
                app.read_text(encoding="utf-8") == original_text,
                wrong["stop_reason"] == "apply_blocked",
                protected["stop_reason"] == "protected_repository_apply_blocked",
            ]
        )

        seen_apply: set[str] = set()
        applied = execute_fixture_safe_workflow(
            repository_root=str(repo),
            request=e2e_request,
            result=patch_result,
            temporary_fixture_repo=True,
            approval_token=preview["approval_digest"],
            validation_plan=[{"type": "py_compile", "path": "src/app.py"}],
            seen_apply_digests=seen_apply,
            persist=True,
        )
        duplicate_apply = execute_fixture_safe_workflow(
            repository_root=str(repo),
            request=e2e_request,
            result=patch_result,
            temporary_fixture_repo=True,
            approval_token=preview["approval_digest"],
            validation_plan=[{"type": "py_compile", "path": "src/app.py"}],
            seen_apply_digests=seen_apply,
        )
        checks.extend(
            [
                applied["final_status"] == "completed",
                applied["validation"]["passed"] is True,
                "return 2" in app.read_text(encoding="utf-8"),
                applied["persistence"].get("ok") is True,
                duplicate_apply["stop_reason"] == "duplicate_apply_attempt",
                "sk-secret-value" not in json.dumps(applied),
            ]
        )

        from luxcode_task_persistence import load_task_state

        loaded = load_task_state("task-first-usable-e2e", mode="memory_only")
        restore_policy = build_first_usable_restore_policy(loaded.get("task", {}))
        checks.extend(
            [
                loaded.get("found") is True,
                restore_policy["engine_auto_execute"] is False,
                restore_policy["apply_auto_repeat"] is False,
                restore_policy["approval_revalidation_required"] is True,
                "sk-secret-value" not in json.dumps(loaded),
            ]
        )

    with tempfile.TemporaryDirectory(prefix="first_usable_rollback_") as tmp:
        repo = Path(tmp) / "repo"
        (repo / "src").mkdir(parents=True)
        app = repo / "src" / "app.py"
        original_text = "def greet():\n    return 1\n"
        app.write_text(original_text, encoding="utf-8")
        request = build_request_envelope(
            task_id="task-first-usable-rollback",
            session_id="session-first-usable-rollback",
            engine_id="tier1_local_worker",
            tier=1,
            task_summary="Fixture rollback",
            remaining_gap={"remaining_gap": "bad syntax patch"},
            completed_scope=["tier0_deterministic"],
            target_files=["src/app.py"],
            target_symbols=["greet"],
            minimum_context={"src/app.py": original_text},
        )
        bad_result = build_result_envelope(
            request=request,
            status="completed",
            analysis_summary="fixture bad syntax",
            completed_scope=["tier1_local_worker"],
            patch_operations=[
                {
                    "operation_type": "replace_text",
                    "file_path": "src/app.py",
                    "old_text": original_text,
                    "new_text": "def greet(:\n    return 2\n",
                }
            ],
            validation_recommendations=[{"type": "py_compile", "path": "src/app.py"}],
        )
        bad_preview = build_fixture_safe_patch_preview(str(repo), bad_result)
        rolled_back = execute_fixture_safe_workflow(
            repository_root=str(repo),
            request=request,
            result=bad_result,
            temporary_fixture_repo=True,
            approval_token=bad_preview["approval_digest"],
            validation_plan=[{"type": "py_compile", "path": "src/app.py"}],
        )
        checks.extend(
            [
                rolled_back["final_status"] == "rolled_back",
                rolled_back["validation"]["passed"] is False,
                rolled_back["rollback"]["transaction_state"] == "rolled_back",
                app.read_text(encoding="utf-8") == original_text,
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
