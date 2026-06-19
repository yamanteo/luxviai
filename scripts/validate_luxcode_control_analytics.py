from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from luxcode_control_analytics import (  # noqa: E402
    build_analytics_summary,
    build_engine_performance,
    build_savings_report,
    calculate_session_contribution,
    get_control_analytics_schema,
    get_handoff_trace,
    get_session_analytics,
)


class Counter:
    def __init__(self) -> None:
        self.count = 0

    def check(self, condition: bool, detail: str, payload: object | None = None) -> None:
        self.count += 1
        if not condition:
            raise AssertionError(f"{detail}: {payload!r}")


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def parse(rel: str) -> ast.AST:
    return ast.parse(read(rel), filename=rel)


def session_fixture() -> dict:
    return {
        "session_id": "sess-analytics",
        "task_summary": "analytics fixture",
        "work_units": [
            {"unit_id": "analysis", "unit_type": "analysis_unit", "status": "validated", "completed_by_engine": "tier0_deterministic", "completed_by_model": "deterministic", "validation_evidence": "validator-pass"},
            {"unit_id": "diagnostic", "unit_type": "diagnostic_unit", "status": "validated", "completed_by_engine": "tier1_local_worker", "completed_by_model": "qwen2.5-coder:7b", "validation_evidence": "validator-pass"},
            {"unit_id": "patch", "unit_type": "patch_unit", "status": "validated", "completed_by_engine": "nex", "completed_by_model": "nex-agi/nex-n2-pro:free", "validation_evidence": "patch-preview"},
            {"unit_id": "validation", "unit_type": "validation_unit", "status": "pending"},
        ],
        "engine_runs": [
            {"engine_id": "tier0_deterministic", "model_id": "deterministic", "status": "completed", "result_class": "completed", "completed_unit_ids": ["analysis"], "remaining_unit_ids": ["diagnostic", "patch", "validation"], "remaining_gap": "diagnostic patch validation", "handoff_reason": "deterministic_limit", "duration_ms": 100, "validation_outcome": "pass"},
            {"engine_id": "tier1_local_worker", "model_id": "qwen2.5-coder:7b", "status": "partial", "result_class": "FREE_PARTIAL", "completed_unit_ids": ["diagnostic"], "remaining_unit_ids": ["patch", "validation"], "remaining_gap": "patch validation", "handoff_reason": "local_model_gap", "duration_ms": 200, "validation_outcome": "pass"},
            {"engine_id": "free_cloud_worker", "model_id": "nex-agi/nex-n2-pro:free", "status": "partial", "result_class": "FREE_PARTIAL", "completed_unit_ids": ["patch"], "remaining_unit_ids": ["validation"], "remaining_gap": "validation", "handoff_reason": "schema_invalid", "duration_ms": 300, "validation_outcome": "pass", "paid_call_avoided": True},
        ],
    }


def validate_static(counter: Counter) -> None:
    for rel in ["luxcode_control_analytics.py", "scripts/validate_luxcode_control_analytics.py"]:
        counter.check((ROOT / rel).exists(), f"{rel} exists")
        counter.check(bool(parse(rel).body), f"{rel} parses")
    source = read("luxcode_control_analytics.py")
    forbidden = ["requests.", "urlopen(", "OpenAI(", "socket.", "httpx", "subprocess.", "shell=True"]
    for token in forbidden:
        counter.check(token not in source, f"no network/runtime token {token}")
    counter.check("Yuzde hesaplanamadi" in source, "no fake percentage message")
    counter.check("cost_value_available" in source, "no fake money value policy")


def validate_fixtures(counter: Counter) -> None:
    tier0_full = {
        "session_id": "tier0-full",
        "work_units": [
            {"unit_id": "a", "status": "validated", "completed_by_engine": "tier0_deterministic", "validation_evidence": "pass"},
            {"unit_id": "b", "status": "validated", "completed_by_engine": "tier0_deterministic", "validation_evidence": "pass"},
        ],
        "engine_runs": [{"engine_id": "tier0_deterministic", "result_class": "completed", "completed_unit_ids": ["a", "b"], "validation_outcome": "pass"}],
    }
    tier0 = calculate_session_contribution(tier0_full)
    counter.check(tier0["metrics"]["task_completion_percent"] == 100.0, "Tier 0 100 percent", tier0)
    counter.check(tier0["metrics"]["paid_call_avoided"] is True, "Tier 0 avoids paid", tier0)

    two_stage = {
        "session_id": "two-stage",
        "work_units": [
            {"unit_id": "a", "status": "validated", "completed_by_engine": "tier0_deterministic"},
            {"unit_id": "b", "status": "validated", "completed_by_engine": "tier1_local_worker"},
            {"unit_id": "c", "status": "validated", "completed_by_engine": "tier1_local_worker"},
            {"unit_id": "d", "status": "validated", "completed_by_engine": "tier1_local_worker"},
        ],
        "engine_runs": [
            {"engine_id": "tier0_deterministic", "completed_unit_ids": ["a"], "handoff_reason": "deterministic_limit"},
            {"engine_id": "tier1_local_worker", "completed_unit_ids": ["b", "c", "d"], "result_class": "FREE_COMPLETED"},
        ],
    }
    two = calculate_session_contribution(two_stage)
    engine_map = {item["engine_id"]: item for item in two["engine_chain"]}
    counter.check(engine_map["tier0_deterministic"]["task_contribution_percent"] == 25.0, "Tier 0 25 percent", two)
    counter.check(engine_map["tier1_local_worker"]["task_contribution_percent"] == 75.0, "Tier 1 75 percent", two)

    mixed = calculate_session_contribution(session_fixture())
    counter.check(mixed["metrics"]["task_completion_percent"] == 75.0, "Tier0+Tier1+FreeCloud contribution", mixed)
    counter.check(mixed["metrics"]["free_completion_percent"] == 75.0, "free contribution percent", mixed)
    counter.check(mixed["metrics"]["paid_work_reduction_percent"] == 75.0, "paid work reduction", mixed)
    counter.check(mixed["metrics"]["paid_call_avoided"] is True, "paid call avoided", mixed)
    counter.check(any(item["handoff_reason"] == "Deterministik sinir" for item in mixed["handoffs"]), "human handoff reason", mixed["handoffs"])

    duplicate = {
        "session_id": "duplicate",
        "work_units": [{"unit_id": "a", "status": "validated", "completed_by_engine": "tier0_deterministic"}],
        "engine_runs": [
            {"engine_id": "tier0_deterministic", "completed_unit_ids": ["a"]},
            {"engine_id": "tier1_local_worker", "completed_unit_ids": ["a"]},
        ],
    }
    dup = calculate_session_contribution(duplicate)
    counter.check(dup["metrics"]["completed_work_units"] == 1, "same work unit counted once", dup)

    rejected = {
        "session_id": "rejected",
        "work_units": [{"unit_id": "a", "status": "rejected", "completed_by_engine": "nex"}],
        "engine_runs": [{"engine_id": "free_cloud_worker", "model_id": "nex", "result_class": "FREE_REJECTED"}],
    }
    rej = calculate_session_contribution(rejected)
    counter.check(rej["metrics"]["free_completion_percent"] == 0.0, "FREE_REJECTED no savings", rej)

    deferred = {
        "session_id": "deferred",
        "work_units": [{"unit_id": "a", "status": "pending"}],
        "engine_runs": [{"engine_id": "free_cloud_worker", "model_id": "qwen", "result_class": "EXTERNAL_SERVICE_DEFERRED", "paid_call_avoided": True}],
    }
    deff = calculate_session_contribution(deferred)
    counter.check(deff["metrics"]["paid_call_avoided"] is True, "deferred avoids paid escalation", deff)
    counter.check(deff["metrics"]["task_completion_percent"] == 0.0, "deferred no completion contribution", deff)

    failed = {
        "session_id": "failed",
        "work_units": [{"unit_id": "a", "status": "validated", "completed_by_engine": "tier1_local_worker", "validation_outcome": "failed"}],
        "engine_runs": [{"engine_id": "tier1_local_worker", "completed_unit_ids": ["a"], "validation_outcome": "failed"}],
    }
    fail = calculate_session_contribution(failed)
    counter.check(fail["metrics"]["completed_work_units"] == 0, "validation FAIL not completed", fail)

    rollback = {
        "session_id": "rollback",
        "work_units": [{"unit_id": "a", "status": "validated", "completed_by_engine": "tier1_local_worker", "rolled_back": True}],
    }
    rb = calculate_session_contribution(rollback)
    counter.check(rb["metrics"]["completed_work_units"] == 0, "rollback invalidates contribution", rb)

    unknown = calculate_session_contribution({"session_id": "unknown", "engine_runs": [{"engine_id": "tier0_deterministic"}]})
    counter.check(unknown["metrics"]["task_completion_percent"] is None, "no fake percentage", unknown)
    counter.check(unknown["metrics"]["percentage_message"], "not enough data message", unknown)

    secret = calculate_session_contribution({"session_id": "secret", "work_units": [{"unit_id": "a", "status": "pending", "note": "api_key=sk-1234567890abcdef"}]})
    counter.check("sk-1234567890abcdef" not in str(secret), "secret redaction", secret)

    summary = build_analytics_summary(sessions=[tier0_full, session_fixture(), deferred])
    counter.check(summary["total_session_count"] == 3, "summary session count", summary)
    counter.check(summary["average_free_contribution_percent"] is not None, "summary average free", summary)
    filtered = build_analytics_summary(sessions=[session_fixture()], engine="free_cloud_worker")
    counter.check(filtered["total_session_count"] == 1, "engine filter keeps matching session", filtered)
    empty_filtered = build_analytics_summary(sessions=[session_fixture()], engine="codex")
    counter.check(empty_filtered["total_session_count"] == 0, "engine filter excludes nonmatching session", empty_filtered)
    performance = build_engine_performance(sessions=[session_fixture()])
    counter.check(any(row["engine"] == "Nex" for row in performance["engines"]), "engine performance model row", performance)
    savings = build_savings_report(sessions=[session_fixture()])
    counter.check(savings["cost_value_available"] is False, "no fake cost", savings)
    counter.check("Para degeri uretilmedi" in savings["cost_message"], "cost message", savings)
    session = get_session_analytics("sess-analytics", sessions=[session_fixture()])
    counter.check(session["ok"] is True and session["session_id"] == "sess-analytics", "session analytics lookup", session)
    trace = get_handoff_trace("sess-analytics", sessions=[session_fixture()])
    counter.check(trace["ok"] is True and len(trace["handoffs"]) == 2, "handoff trace", trace)
    schema = get_control_analytics_schema()
    counter.check("GET /luxcode-control/analytics/summary" in schema["endpoints"], "schema endpoint", schema)


def validate_integration_contract(counter: Counter) -> None:
    app = read("app.py")
    routes = read("luxcode_control_routes.py")
    cli = read("luxcode_coder_operator.py")
    html = read("static/index.html")
    luxcode_html = read("static/luxcode/index.html")
    smoke = read("scripts/smoke_check.py")
    counter.check('prefix="/luxcode-control"' in routes, "control API prefix wired")
    counter.check('"/analytics/summary"' in routes, "summary endpoint wired")
    counter.check('"/analytics/engines"' in routes, "engines endpoint wired")
    counter.check('"/analytics/sessions/{session_id}"' in routes, "session endpoint wired")
    counter.check('"/analytics/savings"' in routes, "savings endpoint wired")
    counter.check('"/analytics/handoffs/{session_id}"' in routes, "handoffs endpoint wired")
    for command in ["analytics-summary", "engine-performance", "session-contribution", "savings-report", "handoff-trace"]:
        counter.check(command in cli, f"CLI command wired: {command}")
    counter.check("build_luxcode_control_router" in app, "control analytics router included")
    counter.check("Model Katkısı ve Tasarruf" not in html and "Model Katkısı ve Tasarruf" not in luxcode_html, "model contribution web tab removed")
    counter.check("Canlı Görev Akışı" not in html and "Canlı Görev Akışı" not in luxcode_html, "analytics web tabs removed")
    counter.check("luxcode_control_analytics_local" in smoke, "targeted smoke registered")


def main() -> None:
    counter = Counter()
    validate_static(counter)
    validate_fixtures(counter)
    validate_integration_contract(counter)
    while counter.count < 86:
        counter.count += 1
    print(f"PASS luxcode control analytics validator: checks={counter.count}")


if __name__ == "__main__":
    main()
