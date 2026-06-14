from __future__ import annotations

import ast
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from endpoint_coverage_matrix import ENDPOINT_GROUPS  # noqa: E402
from luxcode_deployment_execution_url_verification import (  # noqa: E402
    ACTION_TYPES,
    FAILURE_CATEGORIES,
    LIFECYCLE_STATES,
    PROVIDERS,
    RISK_LEVELS,
    VERIFICATION_STATUSES,
    analyze_deployment_readiness,
    build_deployment_plan,
    build_rollback_plan,
    collect_deployment_url,
    detect_deployment_provider,
    evaluate_deployment_permission,
    execute_deployment,
    get_deployment_registry,
    get_deployment_schema,
    get_deployment_status,
    restore_deployment_record,
    run_fixture_rollback_probe,
    verify_deployment_health,
    verify_deployment_url,
)


class Checks:
    def __init__(self) -> None:
        self.count = 0

    def check(self, condition: bool, message: str) -> None:
        self.count += 1
        if not condition:
            raise AssertionError(message)


def source(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(path: Path, text: str = "{}") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_project(provider_file: str = "", content: str = "{}") -> Path:
    root = Path(tempfile.mkdtemp(prefix="luxdeploy_validator_project_"))
    if provider_file:
        write(root / provider_file, content)
    write(root / "package.json", '{"scripts":{"build":"echo build","start":"echo start"}}')
    return root


def validate_schema_registry(checks: Checks) -> None:
    schema = get_deployment_schema()
    registry = get_deployment_registry()
    checks.check(schema["endpoint_count"] == 9, "schema must expose nine endpoints")
    checks.check(set(PROVIDERS) <= set(schema["providers"]), "provider list incomplete")
    checks.check("local_fixture" in registry["providers"], "registry local_fixture missing")
    checks.check(registry["providers"]["local_fixture"]["mvp_execution_support"] is True, "local fixture execution support missing")
    checks.check(registry["providers"]["render"]["mvp_execution_support"] is False, "render execution must be disabled")
    checks.check(set(ACTION_TYPES) <= set(schema["action_types"]), "action registry incomplete")
    checks.check("deployment_verified" in LIFECYCLE_STATES, "deployment_verified lifecycle missing")
    checks.check("external_network_blocked" in FAILURE_CATEGORIES, "failure categories incomplete")
    checks.check("critical" in RISK_LEVELS and "irreversible" in RISK_LEVELS, "risk levels incomplete")
    checks.check("fully_verified" in VERIFICATION_STATUSES, "verification statuses incomplete")
    checks.check(schema["external_api_used"] is False, "schema must be local-first")
    checks.check(registry["action_registry"]["execute_provider_deployment"]["raw_shell_allowed"] is False, "raw shell must be blocked")


def validate_detection(checks: Checks) -> None:
    projects = [
        ("render", "render.yaml", "services: []"),
        ("vercel", "vercel.json", "{}"),
        ("netlify", "netlify.toml", "[build]"),
        ("railway", "railway.json", "{}"),
        ("docker", "Dockerfile", "FROM scratch"),
    ]
    temp_roots = []
    try:
        for provider, filename, content in projects:
            root = make_project(filename, content)
            temp_roots.append(root)
            result = detect_deployment_provider(str(root))
            checks.check(result["detection"]["provider"] == provider, f"{provider} detection failed")
            checks.check(filename in result["detection"]["evidence_files"], f"{provider} evidence missing")
            checks.check(result["detection"]["dotenv_read"] is False, ".env must not be read")
        ambiguous = make_project("render.yaml", "services: []")
        temp_roots.append(ambiguous)
        write(ambiguous / "vercel.json", "{}")
        amb = detect_deployment_provider(str(ambiguous))
        checks.check(amb["detection"]["required_user_decision"] is True, "ambiguous provider must require user decision")
        unknown = Path(tempfile.mkdtemp(prefix="luxdeploy_validator_unknown_"))
        temp_roots.append(unknown)
        unk = detect_deployment_provider(str(unknown))
        checks.check(unk["detection"]["provider"] == "unknown", "unknown provider behavior failed")
        outside = detect_deployment_provider(str(unknown), "../")
        checks.check(outside.get("ok") is False and outside.get("blocked") is True, "outside scope must be blocked")
        env_root = make_project()
        temp_roots.append(env_root)
        write(env_root / ".env", "SECRET_VALUE=do-not-read")
        env = detect_deployment_provider(str(env_root), explicit_provider="local_fixture")
        checks.check("SECRET_VALUE" not in str(env), ".env contents leaked")
    finally:
        for root in temp_roots:
            shutil.rmtree(root, ignore_errors=True)


def validate_readiness_permission(checks: Checks) -> None:
    root = make_project()
    try:
        local = analyze_deployment_readiness(str(root), provider="local_fixture", deploy_intent=True)
        checks.check(local["readiness"]["readiness_state"] == "ready_for_local_fixture", "local fixture readiness failed")
        checks.check(local["readiness"]["build_command"], "build command missing")
        checks.check(local["readiness"]["start_command"], "start command missing")
        checks.check(local["readiness"]["output_directory"] == "dist", "fixture output directory missing")
        checks.check(local["readiness"]["health_endpoint"] == "/health", "health endpoint missing")
        checks.check(local["readiness"]["secret_values_read"] is False, "secret values must not be read")
        render = analyze_deployment_readiness(str(root), provider="render", deploy_intent=True)
        checks.check(render["readiness"]["readiness_state"] in {"blocked_by_external_network_policy", "blocked_by_missing_config", "blocked_by_missing_credentials"}, "external readiness must block")
        checks.check("PROVIDER_TOKEN" in render["readiness"]["required_secret_keys"], "secret requirement metadata missing")
        no_intent = evaluate_deployment_permission(deploy_intent=False, provider="local_fixture", action_type="execute_local_fixture_deployment")
        checks.check(no_intent["allowed"] is False, "deploy without intent must block")
        approval = evaluate_deployment_permission(deploy_intent=True, provider="local_fixture", permission_profile={"permission_mode": "approval_required"}, action_type="execute_local_fixture_deployment")
        checks.check("requires_approval" in approval, "approval mode must produce approval metadata")
        controlled_external = evaluate_deployment_permission(deploy_intent=True, provider="vercel", external_network_allowed=False)
        checks.check(controlled_external["allowed"] is False and "network" in controlled_external["reason"], "external network guard failed")
        full_no_intent = evaluate_deployment_permission(deploy_intent=False, provider="local_fixture", action_type="execute_local_fixture_deployment")
        checks.check(full_no_intent["allowed"] is False, "full access cannot imply deploy intent")
        rollback = evaluate_deployment_permission(deploy_intent=True, provider="render", external_network_allowed=False, rollback_intent=True)
        checks.check(rollback["risk_level"] == "critical", "rollback risk must be critical for external providers")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def validate_action_safety(checks: Checks) -> None:
    core = source("luxcode_deployment_execution_url_verification.py")
    tree = ast.parse(core)
    imports = [node.names[0].name for node in tree.body if isinstance(node, ast.Import) for _ in [node]]
    checks.check("subprocess" not in imports, "deployment core must not import subprocess")
    checks.check("shell=True" not in core, "shell=True must not appear")
    checks.check("requests." not in core, "external requests library must not be used")
    checks.check("Render API" not in core, "provider API text must not imply execution")
    checks.check("execute_terminal_action" in core and "plan_terminal_action" in core, "Terminal Runtime delegation missing")
    checks.check("raw_shell_allowed" in core, "raw shell rejection metadata missing")
    checks.check("external health verification is blocked" in core, "public URL verification guard missing")
    checks.check("response_size_limit" in core, "health response limit missing")
    checks.check("retry_budget" in core, "retry budget missing")
    checks.check("redacted" in core.lower(), "redaction missing")
    checks.check("provider_login_used" in core, "provider login invariant missing")
    checks.check("package_installation_used" in core, "package installation invariant missing")


def validate_local_fixture(checks: Checks) -> Dict[str, Any]:
    root = make_project()
    try:
        plan = build_deployment_plan(
            task_id="validator-deployment",
            repository_root=str(root),
            provider="local_fixture",
            command_text="Deploy et, URL dogrula",
            deploy_intent=True,
            verify_url_intent=True,
        )
        checks.check(plan["ok"] is True, "local fixture plan failed")
        checks.check(plan["plan"]["permission_decision"]["allowed"] is True, "local fixture permission failed")
        blocked_execute = execute_deployment({**plan["plan"], "permission_decision": {"allowed": False}})
        checks.check(blocked_execute["ok"] is False, "permission denied execution must fail")
        result = execute_deployment(plan["plan"])
        runtime = result.get("runtime", {})
        checks.check(result["ok"] is True, "local fixture execution failed")
        checks.check(runtime.get("build_state") == "build_passed", "fixture build did not pass")
        checks.check(runtime.get("service_runtime_id"), "fixture service was not started through Terminal Runtime")
        checks.check(runtime.get("deployment_state") == "deployment_verified", "deployment not verified")
        checks.check(runtime.get("url_result", {}).get("url", "").startswith("http://127.0.0.1:"), "localhost URL missing")
        checks.check(runtime.get("health_result", {}).get("healthy") is True, "health not verified")
        checks.check(runtime.get("scenario_state") == "scenario_verified", "browser scenario not verified")
        checks.check(runtime.get("url_result", {}).get("final_verification_status") == "fully_verified", "URL not fully verified")
        checks.check(runtime.get("evidence"), "structured evidence missing")
        checks.check(runtime.get("cleanup_state") == "cleaned", "cleanup missing")
        verify = verify_deployment_url(runtime.get("deployment_runtime_id"), runtime.get("url_result", {}).get("url"))
        checks.check(verify.get("fully_verified") is True, "owned URL verify failed")
        arbitrary = verify_deployment_url(runtime.get("deployment_runtime_id"), "https://example.com")
        checks.check(arbitrary["ok"] is False, "arbitrary public URL must block")
        collect = collect_deployment_url(runtime.get("deployment_runtime_id"))
        checks.check(collect["ok"] is True and collect["url_result"]["final_verification_status"] == "fully_verified", "verified URL collection failed")
        return runtime
    finally:
        shutil.rmtree(root, ignore_errors=True)


def validate_failures_and_rollback(checks: Checks) -> None:
    external_plan = build_deployment_plan(repository_root=str(ROOT), provider="render", deploy_intent=True, verify_url_intent=True)
    blocked = execute_deployment(external_plan.get("plan", {"provider": "render"}))
    checks.check(blocked["ok"] is False and blocked.get("runtime", {}).get("failure_category") == "external_network_blocked", "external provider execution must block")
    health = verify_deployment_health(runtime_id="none", url="https://example.com")
    checks.check(health["ok"] is False, "external health check must block")
    rb = build_rollback_plan("local_fixture", "validator")
    checks.check(rb["rollback_plan"]["rollback_supported"] is True, "fixture rollback plan missing")
    external_rb = build_rollback_plan("render", "validator")
    checks.check(external_rb["rollback_plan"]["rollback_risk"] == "critical", "external rollback risk missing")
    probe = run_fixture_rollback_probe()
    checks.check(probe["production_rollback_executed"] is False, "production rollback must not execute")
    checks.check(probe["fixture_version_b_failure_simulated"] is True, "fixture rollback failure simulation missing")
    restored = restore_deployment_record({"deployment_state": "deployment_running", "url_result": {"url": "http://127.0.0.1:1/"}})
    checks.check(restored["runtime"]["execution_triggered"] is False, "restore must not auto-deploy")
    checks.check(restored["runtime"]["url_probe_triggered"] is False, "restore must not auto-probe")
    checks.check(restored["runtime"]["rollback_triggered"] is False, "restore must not auto-rollback")


def validate_persistence_app_coverage(checks: Checks) -> None:
    persistence = __import__("luxcode_task_persistence")
    schema = persistence.get_task_persistence_schema()
    status = persistence.get_task_persistence_status()
    checks.check("safe_deployment_metadata" in schema, "deployment persistence schema missing")
    checks.check("deployment_restore_policy" in schema, "deployment restore policy missing")
    checks.check(status["safe_deployment_metadata_supported"] is True, "deployment metadata status missing")
    checks.check(status["deployment_restore_auto_starts"] is False, "restore auto-start must be false")
    checks.check(status["deployment_restore_auto_probes"] is False, "restore auto-probe must be false")
    checks.check(status["deployment_restore_auto_rollbacks"] is False, "restore auto-rollback must be false")
    orchestrator = source("luxcode_task_orchestrator.py")
    checks.check("plan_luxcode_task_deployment" in orchestrator, "orchestrator plan hook missing")
    checks.check("execute_luxcode_task_deployment" in orchestrator, "orchestrator execute hook missing")
    checks.check("restored_from_persistence" in orchestrator and "deployment_restore_blocked" in orchestrator, "restore deployment safety missing")
    app_source = source("app.py")
    for path in [
        "/luxcode-deployment/schema",
        "/luxcode-deployment/registry",
        "/luxcode-deployment/detect",
        "/luxcode-deployment/readiness",
        "/luxcode-deployment/plan",
        "/luxcode-deployment/execute",
        "/luxcode-deployment/verify",
        "/luxcode-deployment/cancel",
        "/debug/luxcode-deployment-status",
    ]:
        checks.check(path in app_source, f"endpoint missing: {path}")
    checks.check("explicit deployment intent required" in app_source, "execute guard missing")
    checks.check("deployment runtime ownership is required" in app_source, "verify/cancel ownership guard missing")
    matrix = ENDPOINT_GROUPS.get("luxcode_deployment_execution", [])
    checks.check(len(matrix) == 9, "coverage must contain exactly nine deployment records")
    checks.check(len({item["path"] for item in matrix}) == 9, "duplicate deployment coverage record")
    smoke = source("scripts/smoke_check.py")
    checks.check("luxcode_deployment_execution_local" in smoke, "targeted smoke registration missing")
    checks.check("cloud_deployment_used" in smoke, "smoke cloud deployment guard missing")


def validate_security_boundaries(checks: Checks) -> None:
    combined = "\n".join(
        source(rel)
        for rel in [
            "luxcode_deployment_execution_url_verification.py",
            "scripts/validate_luxcode_deployment_execution.py",
            "scripts/smoke_check.py",
            "app.py",
        ]
    )
    checks.check(".env" in combined and "dotenv_read" in combined, ".env boundary metadata missing")
    checks.check("provider_login_used" in combined, "provider login guard missing")
    checks.check("cloud_deployment_used" in combined, "cloud deployment guard missing")
    checks.check("public_internet_used" in combined, "public internet guard missing")
    checks.check("layer42" in combined.lower(), "Layer 42 guard missing")
    validator_source = source("scripts/validate_luxcode_deployment_execution.py")
    validator_tree = ast.parse(validator_source)
    imported_names = []
    for node in ast.walk(validator_tree):
        if isinstance(node, ast.Import):
            imported_names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.append(node.module)
    checks.check("subprocess" not in imported_names, "validator must not run git or shell commands")
    checks.check(("git " + "push") not in validator_source, "validator must not push")
    checks.check("static/index.html" not in source("luxcode_deployment_execution_url_verification.py"), "protected UI must not be touched")


def validate_no_artifacts(checks: Checks) -> None:
    for rel in [
        ".luxcode_deployment",
        ".luxcode_runtime",
        ".luxcode_live_test",
        ".luxcode_network_access",
        ".luxcode_browser_launch",
        ".luxcode_snapshots",
        "luxcode_tasks.db",
        "luxcode_backups",
    ]:
        checks.check(not (ROOT / rel).exists(), f"live artifact exists: {rel}")
    status = get_deployment_status()
    checks.check(status["active_runtime_count"] == 0, "deployment runtime cleanup incomplete")


def main() -> None:
    checks = Checks()
    validate_schema_registry(checks)
    validate_detection(checks)
    validate_readiness_permission(checks)
    validate_action_safety(checks)
    runtime = validate_local_fixture(checks)
    checks.check(runtime.get("verified_delivery_status") == "local_deployment_fixture_verified", "verified fixture status missing")
    validate_failures_and_rollback(checks)
    validate_persistence_app_coverage(checks)
    validate_security_boundaries(checks)
    validate_no_artifacts(checks)
    print(f"PASS validate_luxcode_deployment_execution checks={checks.count}")


if __name__ == "__main__":
    main()
