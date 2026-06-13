from __future__ import annotations

import socket
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from luxcode_autonomy_permission_controller import create_permission_profile
from luxcode_local_network_access_intelligence import (
    build_access_urls,
    create_network_access_plan,
    diagnose_bind_issue,
    diagnose_port_conflict,
    execute_network_access_plan,
    get_network_access_registry,
    get_network_access_schema,
    get_network_access_status,
    inspect_network_interfaces,
    restore_network_access_record,
    select_lan_address,
    validate_network_action,
)


CHECKS = 0


def check(condition: bool, label: str, detail: object = "") -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(f"{label}: {detail}")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def write_fixture(tmp: Path) -> Path:
    fixture = tmp / "network_fixture.py"
    fixture.write_text(
        "\n".join(
            [
                "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer",
                "import sys",
                "host = sys.argv[1]",
                "port = int(sys.argv[2])",
                "class Handler(BaseHTTPRequestHandler):",
                "    def do_GET(self):",
                "        body = b'<html><body><h1 data-testid=\"network-fixture-title\">Network fixture ready</h1></body></html>'",
                "        if self.path == '/health': body = b'ok'",
                "        self.send_response(200)",
                "        self.send_header('Content-Type', 'text/html')",
                "        self.send_header('Content-Length', str(len(body)))",
                "        self.end_headers()",
                "        self.wfile.write(body)",
                "    def log_message(self, fmt, *args):",
                "        return",
                "ThreadingHTTPServer((host, port), Handler).serve_forever()",
            ]
        ),
        encoding="utf-8",
    )
    return fixture


def permission_profile(repo: Path) -> dict:
    result = create_permission_profile(
        task_id="network-access-validator",
        permission_mode="controlled_access",
        repository_root=str(repo),
        command_text="validate test smoke local network access",
        selected_folders=["."],
        autonomy_budgets={"test_runs": 10, "scope_expansions": 0},
    )
    check(result.get("ok"), "permission profile created", result)
    return result["profile"]


def main() -> None:
    repo = ROOT
    before_artifacts = {name: (repo / name).exists() for name in [".luxcode_runtime", ".luxcode_network_access", "luxcode_tasks.db"]}

    schema = get_network_access_schema()
    check(schema.get("ok"), "schema ok", schema)
    check(schema.get("public_ip_lookup_allowed") is False, "public ip lookup blocked in schema")
    check(schema.get("subnet_scan_allowed") is False, "subnet scan blocked in schema")
    check(schema.get("firewall_modify_allowed") is False, "firewall modify blocked in schema")
    check(schema.get("router_modify_allowed") is False, "router modify blocked in schema")
    check(schema.get("tunnel_allowed") is False, "tunnel blocked in schema")

    registry = get_network_access_registry()
    check(registry.get("ok"), "registry ok", registry)
    check("subnet_scan" in registry.get("blocked_action_registry", {}), "subnet scan registered as blocked")

    interfaces = inspect_network_interfaces()
    check(interfaces.get("ok"), "interfaces ok", interfaces)
    check(any(item.get("is_loopback") for item in interfaces.get("interfaces", [])), "loopback interface discovered")
    selected = interfaces.get("selected", {})
    lan_ip = (selected or {}).get("address", "")
    if lan_ip:
        check(selected.get("selectable") is True, "selected LAN candidate is selectable", selected)
    else:
        check(interfaces.get("environment_has_private_lan") is False, "no fake LAN selected", interfaces)

    check(not select_lan_address(preferred_address="127.0.0.1").get("ok"), "loopback cannot be selected as LAN")
    check(not validate_network_action("public_ip_lookup").get("ok"), "public IP lookup blocked")
    check(not validate_network_action("subnet_scan").get("ok"), "subnet scan blocked")
    check(not validate_network_action("raw_network_command", raw_command="ipconfig").get("ok"), "raw network command blocked")
    check(not validate_network_action("check_lan_http", target_host="8.8.8.8", selected_lan_ip=lan_ip).get("ok"), "public target blocked")
    check(not validate_network_action("check_lan_http", target_host="169.254.1.1", selected_lan_ip=lan_ip).get("ok"), "link-local target blocked")
    if lan_ip:
        check(not validate_network_action("check_lan_http", target_host="10.255.255.1", selected_lan_ip=lan_ip).get("ok"), "arbitrary private target blocked")

    urls = build_access_urls(8080, lan_ip)
    check(urls.get("ok"), "url build ok", urls)
    check("0.0.0.0" not in " ".join(item.get("url", "") for item in urls.get("urls", [])), "wildcard bind not exposed as URL")

    bind = diagnose_bind_issue("127.0.0.1")
    check(bind.get("result") == "bind_change_required", "localhost bind diagnosis", bind)
    check(bind.get("automatic_patch_applied") is False, "bind diagnosis does not patch")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as held:
        held.bind(("127.0.0.1", 0))
        held.listen(1)
        conflict = diagnose_port_conflict(int(held.getsockname()[1]), selected_lan_ip=lan_ip)
        check(conflict.get("action_taken") == "none", "port conflict does not kill process", conflict)

    with tempfile.TemporaryDirectory(prefix="luxnet-validator-") as tmp_name:
        tmp = Path(tmp_name)
        fixture_repo = tmp / "repo"
        fixture_repo.mkdir()
        fixture = write_fixture(fixture_repo)
        port = free_port()
        profile = permission_profile(fixture_repo)
        service = {
            "working_directory": ".",
            "executable": sys.executable,
            "arguments": [fixture.name, "0.0.0.0", str(port)],
            "timeout_seconds": 30,
            "health_check": {"check_type": "http_get", "host": "127.0.0.1", "port": port, "path": "/health", "timeout_seconds": 1.0, "retries": 20},
            "permission_profile": profile,
        }
        plan_result = create_network_access_plan(
            task_id="network-access-validator",
            repository_root=str(fixture_repo),
            working_directory=".",
            bind_host="0.0.0.0",
            port=port,
            permission_profile=profile,
            service=service,
            selected_lan_ip=lan_ip,
        )
        check(plan_result.get("ok"), "network plan created", plan_result)
        plan = plan_result["plan"]
        check(plan.get("permission_decision", {}).get("allowed") is True, "network plan permission allowed", plan.get("permission_decision"))
        check(plan.get("selected_lan_ip", "") == lan_ip, "selected LAN is stable", plan)
        execute_result = execute_network_access_plan(plan)
        check(execute_result.get("ok"), "network plan executed", execute_result)
        runtime = execute_result["runtime"]
        check(runtime.get("cleanup_state") == "cleaned", "owned service cleaned", runtime.get("cleanup_result"))
        check(runtime.get("cleanup_result", {}).get("firewall_changed") is False, "firewall unchanged")
        check(runtime.get("cleanup_result", {}).get("router_changed") is False, "router unchanged")
        check(runtime.get("physical_device_status") == "physical_device_confirmation_required", "physical device remains unverified", runtime)
        check(runtime.get("localhost_verification", {}).get("tcp", {}).get("reachable") is True, "localhost tcp verified", runtime.get("localhost_verification"))
        check(runtime.get("localhost_verification", {}).get("http", {}).get("healthy") is True, "localhost http verified", runtime.get("localhost_verification"))
        if lan_ip:
            check(runtime.get("lan_http_verification", {}).get("healthy") is True, "selected LAN http verified from host", runtime.get("lan_http_verification"))
        else:
            check(runtime.get("lan_verification", {}).get("state") == "physical_lan_unavailable_in_environment", "LAN unavailable handled", runtime.get("lan_verification"))

    blocked_plan = create_network_access_plan(
        task_id="network-access-validator",
        repository_root=str(repo),
        working_directory="..",
        bind_host="127.0.0.1",
        port=free_port(),
        permission_profile=permission_profile(repo),
    )
    check(not blocked_plan.get("ok"), "path traversal blocked", blocked_plan)

    restored = restore_network_access_record({"network_access_runtime_id": "restored", "state": "completed"})
    check(restored.get("runtime", {}).get("service_restarted") is False, "restore does not restart service")
    check(restored.get("runtime", {}).get("browser_restarted") is False, "restore does not restart browser")
    check(restored.get("runtime", {}).get("lan_test_resumed") is False, "restore does not resume LAN test")

    status = get_network_access_status()
    check(status.get("external_api_used") is False, "no external API")
    check(status.get("public_ip_lookup_used") is False, "no public IP lookup")
    check(status.get("subnet_scan_used") is False, "no subnet scan")
    check(status.get("firewall_modified") is False, "firewall unchanged in status")
    check(status.get("router_modified") is False, "router unchanged in status")
    check(status.get("tunnel_started") is False, "no tunnel")
    check(status.get("layer42_started") is False, "no Layer 42.x")

    after_artifacts = {name: (repo / name).exists() for name in before_artifacts}
    check(after_artifacts == before_artifacts, "no live runtime artifacts created", after_artifacts)

    print(f"PASS: {CHECKS} checks")


if __name__ == "__main__":
    main()
