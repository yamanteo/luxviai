from __future__ import annotations

import ast
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from endpoint_coverage_matrix import ENDPOINT_GROUPS  # noqa: E402
from luxcode_render_provider_adapter import (  # noqa: E402
    ACTION_TYPES,
    AUDIT_EVENTS,
    CREDENTIAL_STATES,
    FAILURE_CATEGORIES,
    LIFECYCLE_STATES,
    READINESS_STATES,
    SERVICE_TYPES,
    analyze_render_readiness,
    build_render_deployment_plan,
    build_render_rollback_plan,
    build_render_service_candidates,
    collect_render_url,
    detect_render_configuration,
    evaluate_render_permission,
    execute_render_deployment,
    execute_render_dry_run,
    get_render_adapter_registry,
    get_render_adapter_schema,
    get_render_adapter_status,
    parse_render_configuration,
    restore_render_record,
    select_render_service,
    validate_render_deployment_plan,
    verify_render_result,
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


def project(render_name: str = "render.yaml", service_type: str = "web") -> Path:
    root = Path(tempfile.mkdtemp(prefix="luxrender_validator_"))
    config = "\n".join(
        [
            "services:",
            f"  - type: {service_type}",
            "    name: lux-validator",
            "    runtime: python",
            "    region: frankfurt",
            "    branch: main",
            "    rootDir: .",
            "    buildCommand: python -m py_compile app.py",
            "    startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT",
            "    staticPublishPath: dist",
            "    healthCheckPath: /health",
            "    autoDeploy: false",
            "    envVars:",
            "      - key: DATABASE_URL",
            "        sync: false",
            "      - key: RENDER_API_KEY",
            "        sync: false",
        ]
    )
    (root / render_name).write_text(config, encoding="utf-8")
    (root / "app.py").write_text("from fastapi import FastAPI\napp=FastAPI()\n@app.get('/health')\ndef h(): return {'ok': True}\n", encoding="utf-8")
    (root / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
    return root


def validate_schema(checks: Checks) -> None:
    schema = get_render_adapter_schema()
    registry = get_render_adapter_registry()
    checks.check(schema["provider"] == "render", "provider must be render")
    checks.check({"web_service", "static_site", "postgres", "redis", "unknown"} <= set(schema["service_types"]), "service types incomplete")
    checks.check("render_fully_verified" in LIFECYCLE_STATES, "lifecycle states incomplete")
    checks.check("render_ready_for_dry_run" in READINESS_STATES, "readiness states incomplete")
    checks.check("blocked_by_final_confirmation" in FAILURE_CATEGORIES, "failure categories incomplete")
    checks.check("reference_available" in CREDENTIAL_STATES, "credential states incomplete")
    checks.check("render_plan_created" in AUDIT_EVENTS, "audit events incomplete")
    checks.check("execute_render_deployment" in ACTION_TYPES, "action model incomplete")
    checks.check(registry["action_registry"]["execute_render_deployment"]["raw_provider_command_allowed"] is False, "raw provider command must be blocked")
    checks.check(schema["render_api_used"] is False and schema["render_cli_used"] is False, "Render execution must be off")


def validate_detection_parsing_mapping(checks: Checks) -> Path:
    roots = []
    root = project()
    roots.append(root)
    try:
        detect = detect_render_configuration(str(root))
        checks.check(detect["detection"]["render_detected"] is True, "render.yaml detection failed")
        checks.check("render.yaml" in detect["detection"]["evidence_files"], "render evidence missing")
        parsed = parse_render_configuration(str(root))
        service = parsed["parsed"]["services"][0]
        checks.check(service["service_name"] == "lux-validator", "service name parse failed")
        checks.check(service["service_type"] == "web_service", "service type parse failed")
        checks.check(service["runtime"] == "python", "runtime parse failed")
        checks.check(service["build_command"], "build command parse failed")
        checks.check(service["start_command"], "start command parse failed")
        checks.check(service["publish_directory"] == "dist", "publish path parse failed")
        checks.check(service["health_path"] == "/health", "health path parse failed")
        checks.check("DATABASE_URL" in service["environment_key_names"], "env key names parse failed")
        checks.check(parsed["parsed"]["unsafe_loader_used"] is False, "unsafe YAML loader must not be used")
        static_root = project("render.yml", "static")
        roots.append(static_root)
        checks.check(detect_render_configuration(str(static_root))["detection"]["render_detected"] is True, "render.yml detection failed")
        checks.check(parse_render_configuration(str(static_root))["parsed"]["services"][0]["service_type"] == "static_site", "static site parse failed")
        docker_root = project()
        roots.append(docker_root)
        (docker_root / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
        checks.check("Dockerfile" in detect_render_configuration(str(docker_root))["detection"]["evidence_files"], "Docker signal missing")
        ambiguous = project()
        roots.append(ambiguous)
        with (ambiguous / "render.yaml").open("a", encoding="utf-8") as handle:
            handle.write("\n  - type: web\n    name: lux-validator\n    buildCommand: echo hi\n    startCommand: echo hi\n")
        checks.check(parse_render_configuration(str(ambiguous))["parsed"]["duplicate_service_names"], "duplicate service handling missing")
        unsafe = project()
        roots.append(unsafe)
        (unsafe / "render.yaml").write_text("!!python/object/apply:os.system ['x']", encoding="utf-8")
        checks.check(parse_render_configuration(str(unsafe))["parsed"]["valid"] is False, "unsafe YAML must be invalid")
        outside = detect_render_configuration(str(root), "../")
        checks.check(outside["ok"] is False, "outside-root config must be blocked")
        unknown = Path(tempfile.mkdtemp(prefix="luxrender_unknown_"))
        roots.append(unknown)
        checks.check(detect_render_configuration(str(unknown))["detection"]["render_detected"] is False, "unknown config should not detect")
        (root / ".env").write_text("RENDER_API_KEY=secret-value", encoding="utf-8")
        checks.check("secret-value" not in str(detect_render_configuration(str(root))), ".env value leaked")
        candidates = build_render_service_candidates(str(root))
        checks.check(candidates["candidate_count"] >= 1, "service candidates missing")
        selected = select_render_service(str(root))
        checks.check(selected["selected_service"]["service_name"] == "lux-validator", "service selection failed")
        mapping = candidates["project_mapping"]
        checks.check(mapping["detected_framework"] == "fastapi", "FastAPI mapping failed")
        node = Path(tempfile.mkdtemp(prefix="luxrender_node_"))
        roots.append(node)
        (node / "package.json").write_text('{"scripts":{"build":"vite build"},"dependencies":{"react":"latest","vite":"latest"}}', encoding="utf-8")
        checks.check(build_render_service_candidates(str(node))["project_mapping"]["recommended_service_type"] == "static_site", "static mapping failed")
        flask = Path(tempfile.mkdtemp(prefix="luxrender_flask_"))
        roots.append(flask)
        (flask / "requirements.txt").write_text("flask\n", encoding="utf-8")
        checks.check(build_render_service_candidates(str(flask))["project_mapping"]["detected_framework"] == "flask", "Flask mapping failed")
        django = Path(tempfile.mkdtemp(prefix="luxrender_django_"))
        roots.append(django)
        (django / "requirements.txt").write_text("django\n", encoding="utf-8")
        checks.check(build_render_service_candidates(str(django))["project_mapping"]["detected_framework"] == "django", "Django mapping failed")
        return root
    finally:
        for item in roots[1:]:
            shutil.rmtree(item, ignore_errors=True)


def validate_readiness_permission_plan(checks: Checks, root: Path) -> dict:
    ready = analyze_render_readiness(str(root), deployment_intent=True)
    checks.check(ready["readiness"]["readiness_state"] in {"render_credentials_required", "render_external_network_permission_required", "render_final_confirmation_required", "render_ready_for_dry_run"}, "readiness blocker failed")
    checks.check(ready["readiness"]["credential_reference"]["secret_value_present"] in {False, "unknown"}, "credential value must not be present")
    checks.check(ready["readiness"]["controlled_deployment_ready"] is False, "controlled deployment must not be ready without credential/network/confirmation")
    credential = {"reference_id": "render-ref", "availability": "reference_available", "scope": "deploy"}
    dry = analyze_render_readiness(str(root), credential_reference=credential, deployment_intent=True)
    checks.check(dry["readiness"]["dry_run_ready"] is True, "dry-run readiness missing")
    plan = build_render_deployment_plan(str(root), repository_root=str(root), credential_reference=credential, deployment_intent=True)
    checks.check(plan["ok"] is True, "plan build failed")
    plan_data = plan["plan"]
    checks.check(plan_data["plan_digest"].startswith("render-plan-digest-"), "plan digest missing")
    checks.check(validate_render_deployment_plan(plan_data)["ok"] is True, "plan validation failed")
    mutated = dict(plan_data)
    mutated["service_name"] = "changed"
    checks.check(validate_render_deployment_plan(mutated)["ok"] is False, "plan digest mismatch must block")
    no_intent = evaluate_render_permission({**plan_data, "deployment_intent": False})
    checks.check(no_intent["allowed"] is False, "no deploy intent must block")
    final = evaluate_render_permission(plan_data, credential_reference=credential, external_network_allowed=True, final_confirmation=False)
    checks.check(final["failure_category"] == "blocked_by_final_confirmation", "final confirmation guard failed")
    real = execute_render_deployment(plan_data, expected_plan_digest=plan_data["plan_digest"], credential_reference=credential, external_network_allowed=True, final_confirmation=True)
    checks.check(real["ok"] is False and real["failure_category"] == "adapter_execution_not_enabled", "real Render execution must be blocked")
    return plan_data


def validate_fake_provider(checks: Checks, plan: dict) -> None:
    result = execute_render_dry_run(plan)
    runtime = result["runtime"]
    checks.check(runtime["lifecycle_state"] == "render_fully_verified", "fake Render lifecycle did not verify")
    checks.check(runtime["deployment_id"].startswith("fake-render-deploy-"), "fake deployment id missing")
    checks.check(runtime["url_result"]["url"].startswith("http://127.0.0.1:"), "localhost URL missing")
    checks.check(runtime["url_result"]["final_verification_status"] == "fully_verified", "URL not fully verified")
    checks.check(runtime["url_result"]["fake_result_classification"] == "fake_render_deployment_verified", "fake classification missing")
    checks.check(runtime["cloud_deployment_used"] is False, "fake provider must not be cloud deploy")
    checks.check(runtime["cleanup_state"] == "render_cleanup_completed", "cleanup missing")
    checks.check(collect_render_url(runtime["render_runtime_id"])["ok"] is True, "collect verified URL failed")
    checks.check(verify_render_result(runtime["render_runtime_id"])["ok"] is True, "verify fake URL failed")
    for fixture, category in [
        ("build_failure", "fake_build_failed"),
        ("deployment_failure", "fake_deployment_failed"),
        ("timeout", "fake_deployment_timeout"),
        ("url_missing", "fake_url_missing"),
        ("health_failure", "fake_health_failed"),
        ("scenario_failure", "fake_scenario_failed"),
        ("cancel", "render_cancelled"),
    ]:
        failed = execute_render_dry_run(plan, fixture=fixture)["runtime"]
        checks.check(failed["failure_category"] == category, f"{fixture} failure category missing")
    rb = build_render_rollback_plan("web_service")
    checks.check(rb["rollback_plan"]["production_rollback_executed"] is False, "production rollback must not execute")
    restored = restore_render_record(runtime)
    checks.check(restored["runtime"]["execution_triggered"] is False, "restore must not auto-deploy")
    checks.check(restored["runtime"]["status_poll_triggered"] is False, "restore must not poll")
    checks.check(restored["runtime"]["url_probe_triggered"] is False, "restore must not probe")
    checks.check(restored["runtime"]["rollback_triggered"] is False, "restore must not rollback")


def validate_integration_security(checks: Checks) -> None:
    core = source("luxcode_deployment_execution_url_verification.py")
    checks.check("luxcode_render_provider_adapter" in core, "deployment core delegation missing")
    persistence = __import__("luxcode_task_persistence")
    checks.check("safe_render_metadata" in persistence.get_task_persistence_schema(), "persistence render metadata missing")
    status = persistence.get_task_persistence_status()
    checks.check(status["safe_render_metadata_supported"] is True, "persistence render status missing")
    checks.check(status["render_restore_auto_deploys"] is False, "restore auto deploy must be false")
    orchestrator = source("luxcode_task_orchestrator.py")
    checks.check("render_intent" in orchestrator and "plan_luxcode_task_render_deployment" in orchestrator, "orchestrator render state missing")
    app_source = source("app.py")
    for path in ["/luxcode-render/schema", "/luxcode-render/registry", "/luxcode-render/detect", "/luxcode-render/parse-config", "/luxcode-render/readiness", "/luxcode-render/plan", "/luxcode-render/dry-run", "/luxcode-render/execute", "/luxcode-render/cancel", "/debug/luxcode-render-status"]:
        checks.check(path in app_source, f"endpoint missing {path}")
    matrix = ENDPOINT_GROUPS.get("luxcode_render_provider_adapter", [])
    checks.check(len(matrix) == 10, "coverage must have ten Render records")
    checks.check(len({item["path"] for item in matrix}) == 10, "duplicate Render coverage record")
    smoke = source("scripts/smoke_check.py")
    checks.check("luxcode_render_provider_adapter_local" in smoke, "targeted smoke missing")
    adapter = source("luxcode_render_provider_adapter.py")
    tree = ast.parse(adapter)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    checks.check("requests" not in imports and "subprocess" not in imports, "Render adapter must not call API/CLI")
    checks.check("shell=True" not in adapter, "shell=True must not appear")
    checks.check("render_api_used" in adapter and "render_cli_used" in adapter, "Render execution guards missing")
    checks.check("static/index.html" not in adapter, "protected UI must not be touched")
    checks.check(get_render_adapter_status()["active_runtime_count"] == 0, "active Render runtime cleanup incomplete")


def validate_no_artifacts(checks: Checks) -> None:
    for rel in [".luxcode_render", ".luxcode_deployment", ".luxcode_runtime", ".luxcode_live_test", ".luxcode_network_access", ".luxcode_browser_launch", ".luxcode_snapshots", "luxcode_tasks.db", "luxcode_backups"]:
        checks.check(not (ROOT / rel).exists(), f"artifact exists: {rel}")


def main() -> None:
    checks = Checks()
    validate_schema(checks)
    root = validate_detection_parsing_mapping(checks)
    try:
        plan = validate_readiness_permission_plan(checks, root)
        validate_fake_provider(checks, plan)
        validate_integration_security(checks)
        validate_no_artifacts(checks)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print(f"PASS validate_luxcode_render_provider_adapter checks={checks.count}")


if __name__ == "__main__":
    main()
