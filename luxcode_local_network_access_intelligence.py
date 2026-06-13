from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import os
import socket
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from luxcode_autonomy_permission_controller import evaluate_requested_action
from luxcode_live_app_interaction_testing import execute_live_test, plan_live_test, restore_live_test_record
from luxcode_terminal_process_runtime import execute_terminal_action, health_check, plan_terminal_action, stop_terminal_process


SUPPORTED_ACTIONS = {
    "inspect_interfaces",
    "select_lan_address",
    "inspect_bind_address",
    "check_localhost_access",
    "check_lan_port",
    "check_lan_http",
    "build_access_urls",
    "validate_same_device_url",
    "validate_same_wifi_url",
    "validate_mobile_viewport_url",
    "diagnose_bind_issue",
    "diagnose_port_conflict",
    "create_network_access_plan",
}
BLOCKED_ACTIONS = {
    "subnet_scan",
    "public_ip_lookup",
    "firewall_modify",
    "router_modify",
    "port_forward",
    "tunnel",
    "raw_network_command",
}
LIFECYCLE_STATES = [
    "planned",
    "approval_required",
    "inspecting_interfaces",
    "interface_selected",
    "waiting_for_service",
    "service_ready",
    "bind_inspected",
    "localhost_verified",
    "lan_port_verified",
    "lan_http_verified",
    "mobile_viewport_testing",
    "mobile_viewport_verified",
    "physical_device_confirmation_required",
    "completed",
    "blocked",
    "failed",
    "timed_out",
    "cancelled",
    "cleanup_required",
    "cleaned",
    "manual_review_required",
]
AUDIT_EVENTS = [
    "network_plan_created",
    "network_permission_evaluated",
    "network_scope_checked",
    "network_interfaces_inspected",
    "network_interface_selected",
    "network_service_requested",
    "network_service_ready",
    "network_bind_inspected",
    "network_localhost_verified",
    "network_lan_port_verified",
    "network_lan_http_verified",
    "network_mobile_viewport_verified",
    "network_physical_device_confirmation_required",
    "network_access_blocked",
    "network_access_failed",
    "network_access_cancelled",
    "network_cleanup_started",
    "network_cleanup_completed",
    "network_restore_requires_user_action",
]

_RUNTIMES: Dict[str, Dict[str, Any]] = {}
_STATUS = {
    "external_api_used": False,
    "public_ip_lookup_used": False,
    "subnet_scan_used": False,
    "firewall_modified": False,
    "router_modified": False,
    "tunnel_started": False,
    "layer42_started": False,
}


def _now() -> float:
    return round(time.time(), 6)


def _digest(parts: List[Any]) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode("utf-8", "replace")).hexdigest()[:20]


def _safe_success(**extra: Any) -> Dict[str, Any]:
    data = {"ok": True, "external_api_used": False, "public_network_used": False}
    data.update(extra)
    return data


def _safe_failure(reason: str, **extra: Any) -> Dict[str, Any]:
    data = {"ok": False, "blocked": True, "reason": reason, "external_api_used": False, "public_network_used": False}
    data.update(extra)
    return data


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): ("[redacted]" if any(s in str(k).lower() for s in ("secret", "token", "password", "cookie", "ssid", "mac")) else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value[:80]]
    if isinstance(value, str):
        if len(value) > 1200:
            return value[:1200] + "...[truncated]"
        return value
    return value


def _audit(target: Dict[str, Any], event: str, details: Optional[Dict[str, Any]] = None) -> None:
    target.setdefault("audit_events", []).append({"event": event, "at": _now(), "details": _redact(details or {})})


def _safe_path(root: str, relative: str = ".") -> Tuple[Optional[Path], str]:
    try:
        base = Path(root or os.getcwd()).resolve()
        target = (base / (relative or ".")).resolve()
    except Exception as exc:
        return None, f"path resolution failed: {type(exc).__name__}"
    if any(part == ".." for part in Path(relative or ".").parts):
        return None, "path traversal blocked"
    if base != target and base not in target.parents:
        return None, "scope outside repository root blocked"
    return target, ""


def _classify_ip(address: str) -> Dict[str, Any]:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return {"valid": False, "selectable": False, "reason": "invalid_ip"}
    is_ipv4 = ip.version == 4
    virtual_hint = False
    selectable = bool(is_ipv4 and ip.is_private and not ip.is_loopback and not ip.is_link_local and not ip.is_multicast and not ip.is_unspecified)
    reasons = []
    if ip.is_loopback:
        reasons.append("loopback")
    if ip.is_link_local:
        reasons.append("link_local")
    if ip.is_private:
        reasons.append("private")
    if ip.is_global:
        reasons.append("public_global")
    if ip.is_unspecified:
        reasons.append("unspecified")
    return {
        "valid": True,
        "address_family": f"IPv{ip.version}",
        "is_private": bool(ip.is_private),
        "is_public": bool(ip.is_global),
        "is_loopback": bool(ip.is_loopback),
        "is_link_local": bool(ip.is_link_local),
        "is_multicast": bool(ip.is_multicast),
        "is_unspecified": bool(ip.is_unspecified),
        "likely_virtual_or_vpn": virtual_hint,
        "selectable": selectable,
        "classification_reasons": reasons,
    }


def _host_addresses() -> List[str]:
    addresses = {"127.0.0.1"}
    try:
        hostname = socket.gethostname()
        for item in socket.getaddrinfo(hostname, None):
            addresses.add(str(item[4][0]))
    except Exception:
        pass
    return sorted(addresses)


def inspect_network_interfaces() -> Dict[str, Any]:
    interfaces: List[Dict[str, Any]] = []
    for address in _host_addresses():
        cls = _classify_ip(address)
        if not cls.get("valid"):
            continue
        name = "loopback" if cls.get("is_loopback") else f"host-{address}"
        interfaces.append({
            "interface_name": name,
            "address": address,
            "address_family": cls["address_family"],
            "prefix_or_netmask": "",
            "is_loopback": cls["is_loopback"],
            "is_link_local": cls["is_link_local"],
            "is_private": cls["is_private"],
            "is_public": cls["is_public"],
            "is_active": True,
            "default_route_related": not cls["is_loopback"] and cls["selectable"],
            "likely_virtual_or_vpn": False,
            "selectable": cls["selectable"],
            "selection_reason": "private IPv4 candidate" if cls["selectable"] else ",".join(cls["classification_reasons"]),
        })
    selected = select_lan_address(interfaces=interfaces)
    return _safe_success(interfaces=interfaces, selected=selected.get("selected_interface"), environment_has_private_lan=bool(selected.get("selected_interface")))


def select_lan_address(interfaces: Optional[List[Dict[str, Any]]] = None, preferred_address: str = "") -> Dict[str, Any]:
    interfaces = interfaces if interfaces is not None else inspect_network_interfaces().get("interfaces", [])
    if preferred_address:
        cls = _classify_ip(preferred_address)
        if not cls.get("selectable"):
            return _safe_failure("preferred address is not a safe LAN candidate", address=preferred_address, classification=cls)
        match = next((item for item in interfaces if item.get("address") == preferred_address), {"interface_name": "explicit", "address": preferred_address})
        selected = {**match, "confidence": 0.85, "selection_reason": "explicit safe private IPv4 selected"}
        return _safe_success(selected_interface=selected, manual_selection_required=False)
    candidates = [item for item in interfaces if item.get("selectable")]
    candidates.sort(key=lambda item: (not item.get("default_route_related", False), item.get("likely_virtual_or_vpn", False), item.get("address", "")))
    if not candidates:
        return _safe_success(selected_interface=None, manual_selection_required=True, confidence=0.0, reason="no safe private LAN IPv4 interface discovered")
    selected = dict(candidates[0])
    selected["confidence"] = 0.78 if selected.get("default_route_related") else 0.65
    selected["selection_reason"] = "active private IPv4 candidate selected; physical device still unverified"
    return _safe_success(selected_interface=selected, manual_selection_required=False)


def _origin_url(host: str, port: int, protocol: str = "http") -> str:
    return f"{protocol}://{host}:{int(port)}"


def _validate_target_host(host: str, selected_lan_ip: str = "", allow_loopback: bool = True) -> Tuple[bool, str]:
    if host in {"localhost", "127.0.0.1", "::1"}:
        return (True, "") if allow_loopback else (False, "loopback is not a LAN target")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False, "host must be localhost or selected private IP"
    if ip.is_global:
        return False, "public IP targets are blocked"
    if ip.is_link_local:
        return False, "link-local targets are blocked"
    if ip.is_loopback:
        return (True, "") if allow_loopback else (False, "loopback is not a LAN target")
    if selected_lan_ip and host != selected_lan_ip:
        return False, "arbitrary private IP target is blocked"
    if not selected_lan_ip:
        return False, "selected LAN IP is required for private target"
    return True, ""


def tcp_connect(host: str, port: int, timeout_seconds: float = 1.0, selected_lan_ip: str = "", allow_loopback: bool = True) -> Dict[str, Any]:
    ok, reason = _validate_target_host(host, selected_lan_ip, allow_loopback)
    if not ok:
        return _safe_failure(reason)
    try:
        with socket.create_connection((host, int(port)), timeout=float(timeout_seconds)):
            return _safe_success(reachable=True, host=host, port=int(port))
    except Exception as exc:
        return _safe_success(reachable=False, host=host, port=int(port), error=type(exc).__name__)


def http_check(host: str, port: int, path: str = "/health", timeout_seconds: float = 1.0, selected_lan_ip: str = "", allow_loopback: bool = True) -> Dict[str, Any]:
    ok, reason = _validate_target_host(host, selected_lan_ip, allow_loopback)
    if not ok:
        return _safe_failure(reason)
    try:
        conn = http.client.HTTPConnection(host, int(port), timeout=float(timeout_seconds))
        conn.request("GET", path or "/")
        resp = conn.getresponse()
        body = resp.read(300)
        conn.close()
        return _safe_success(healthy=200 <= int(resp.status) < 400, status=resp.status, body_preview=body.decode("utf-8", "replace")[:120], host=host, port=int(port), path=path)
    except Exception as exc:
        return _safe_success(healthy=False, host=host, port=int(port), path=path, error=type(exc).__name__)


def inspect_bind_address(expected_bind_host: str, port: int, selected_lan_ip: str = "") -> Dict[str, Any]:
    if expected_bind_host in {"0.0.0.0", "::"}:
        bind_scope = "all_interfaces"
    elif expected_bind_host in {"127.0.0.1", "localhost", "::1"}:
        bind_scope = "localhost_only"
    elif selected_lan_ip and expected_bind_host == selected_lan_ip:
        bind_scope = "selected_lan_ip"
    else:
        bind_scope = "unknown_or_mismatch"
    localhost = tcp_connect("127.0.0.1", port)
    lan = tcp_connect(selected_lan_ip, port, selected_lan_ip=selected_lan_ip, allow_loopback=False) if selected_lan_ip else _safe_success(reachable=False, reason="no selected LAN IP")
    return _safe_success(
        bind_host=expected_bind_host,
        bind_scope=bind_scope,
        port=int(port),
        localhost_reachable=localhost.get("reachable"),
        lan_reachable=lan.get("reachable"),
        lan_access_possible=bind_scope in {"all_interfaces", "selected_lan_ip"} and bool(lan.get("reachable")),
        diagnosis="bind_change_required_for_same_wifi" if bind_scope == "localhost_only" else "lan_candidate_requires_verification",
    )


def build_access_urls(port: int, selected_lan_ip: str = "", protocol: str = "http", localhost_host: str = "127.0.0.1") -> Dict[str, Any]:
    localhost_url = _origin_url(localhost_host, port, protocol)
    urls = [{
        "url": localhost_url,
        "access_scope": "same_device_loopback",
        "verification_status": "candidate",
        "tested_from": "not_tested",
        "known_limitation": "same computer only",
    }]
    if selected_lan_ip:
        ok, reason = _validate_target_host(selected_lan_ip, selected_lan_ip, allow_loopback=False)
        if ok:
            urls.append({
                "url": _origin_url(selected_lan_ip, port, protocol),
                "access_scope": "same_network_candidate",
                "verification_status": "candidate",
                "tested_from": "not_tested",
                "known_limitation": "physical mobile device not verified",
                "next_required_confirmation": "open this URL on a device on the same Wi-Fi and report result",
            })
        else:
            urls.append({"url": "", "access_scope": "same_network_candidate", "verification_status": "invalid", "reason": reason})
    return _safe_success(urls=urls, localhost_url=localhost_url, lan_url=_origin_url(selected_lan_ip, port, protocol) if selected_lan_ip else "")


def get_network_access_schema() -> Dict[str, Any]:
    return _safe_success(
        layer="luxcode_local_network_access_intelligence",
        supported_actions=sorted(SUPPORTED_ACTIONS),
        blocked_actions=sorted(BLOCKED_ACTIONS),
        raw_network_command_allowed=False,
        subnet_scan_allowed=False,
        public_ip_lookup_allowed=False,
        firewall_modify_allowed=False,
        router_modify_allowed=False,
        tunnel_allowed=False,
        lifecycle_states=LIFECYCLE_STATES,
        audit_events=AUDIT_EVENTS,
        physical_device_claim_policy="never claim physical device verification without explicit device confirmation",
    )


def get_network_access_registry() -> Dict[str, Any]:
    return _safe_success(
        action_registry={name: {"supported": True, "raw_shell": False} for name in sorted(SUPPORTED_ACTIONS)},
        blocked_action_registry={name: {"supported": False, "reason": "outside local-first network boundary"} for name in sorted(BLOCKED_ACTIONS)},
        interface_selection_priority=["active physical private IPv4", "default-route private IPv4", "explicit safe selected interface", "manual review"],
        url_statuses=["candidate", "listening", "reachable_from_host", "browser_verified", "physical_device_unverified", "blocked", "invalid"],
    )


def validate_network_action(action_type: str, target_host: str = "", selected_lan_ip: str = "", raw_command: str = "") -> Dict[str, Any]:
    if raw_command:
        return _safe_failure("raw network commands are blocked")
    if action_type in BLOCKED_ACTIONS:
        return _safe_failure("blocked network action", action_type=action_type)
    if action_type not in SUPPORTED_ACTIONS:
        return _safe_failure("unsupported network action", action_type=action_type)
    if target_host:
        ok, reason = _validate_target_host(target_host, selected_lan_ip, allow_loopback=True)
        if not ok:
            return _safe_failure(reason)
    return _safe_success(valid=True, action_type=action_type)


def create_network_access_plan(
    task_id: str = "",
    repository_root: str = "",
    working_directory: str = ".",
    bind_host: str = "127.0.0.1",
    port: int = 0,
    protocol: str = "http",
    permission_profile: Optional[Dict[str, Any]] = None,
    service: Optional[Dict[str, Any]] = None,
    selected_lan_ip: str = "",
    approval_digest: str = "",
) -> Dict[str, Any]:
    root, root_error = _safe_path(repository_root or os.getcwd(), ".")
    if root_error:
        return _safe_failure(root_error)
    cwd, cwd_error = _safe_path(str(root), working_directory)
    if cwd_error:
        return _safe_failure(cwd_error)
    if int(port) < 0 or int(port) > 65535:
        return _safe_failure("invalid port")
    interfaces = inspect_network_interfaces()
    selected = select_lan_address(interfaces.get("interfaces", []), selected_lan_ip)
    selected_interface = selected.get("selected_interface")
    lan_ip = selected_interface.get("address") if selected_interface else ""
    permission = evaluate_requested_action(
        profile=permission_profile,
        task_id=task_id,
        operation="run_tests",
        target_path=str(cwd.relative_to(root)) if cwd != root else ".",
        metadata={"why_needed": "local network access verification for task-owned service", "risk_hint": "important" if bind_host == "0.0.0.0" else "normal"},
        approval_digest=approval_digest,
        recovery_plan_available=True,
    ) if permission_profile else _safe_success(allowed=False, requires_approval=True, reason="permission profile is required")
    runtime_id = "luxnet-" + _digest([task_id, repository_root, bind_host, port, time.time()])
    urls = build_access_urls(int(port), lan_ip, protocol)
    plan = {
        "network_access_runtime_id": runtime_id,
        "task_id": task_id,
        "state": "planned" if permission.get("allowed") else "approval_required",
        "repository_root": str(root),
        "working_directory": str(cwd),
        "service": deepcopy(service or {}),
        "permission_profile": deepcopy(permission_profile or {}),
        "service_runtime_id": "",
        "protocol": protocol,
        "bind_host": bind_host,
        "bind_port": int(port),
        "localhost_url": urls.get("localhost_url"),
        "selected_lan_ip": lan_ip,
        "lan_url": urls.get("lan_url"),
        "network_interface": selected_interface,
        "interface_type": "private_ipv4" if selected_interface else "manual_review_required",
        "permission_decision": permission,
        "risk_level": permission.get("risk_level", "important" if bind_host == "0.0.0.0" else "normal"),
        "verification_steps": ["inspect_interfaces", "verify_localhost", "verify_lan", "mobile_viewport_over_lan"],
        "expected_result": "same_device_lan_verified_when_private_interface_available",
        "timeout_seconds": 45,
        "retry_policy": {"retries": 3, "interval_seconds": 0.1},
        "evidence_policy": {"structured": True, "screenshots": "temporary_via_live_testing"},
        "cleanup_policy": {"owned_service_only": True, "owned_browser_only": True, "no_firewall_or_router_changes": True},
        "generated_urls": urls.get("urls", []),
        "physical_device_status": "physical_device_not_verified",
        "audit_events": [],
    }
    _audit(plan, "network_plan_created", {"runtime_id": runtime_id, "task_id": task_id})
    _audit(plan, "network_permission_evaluated", permission)
    _audit(plan, "network_scope_checked", {"working_directory": plan["working_directory"]})
    _audit(plan, "network_interfaces_inspected", {"count": len(interfaces.get("interfaces", []))})
    if selected_interface:
        _audit(plan, "network_interface_selected", selected_interface)
    return _safe_success(plan=plan, interfaces=interfaces)


def _cleanup_network_runtime(runtime: Dict[str, Any], service_runtime_id: str) -> None:
    if runtime.get("cleanup_state") == "cleaned":
        return
    runtime["cleanup_state"] = "cleaning"
    _audit(runtime, "network_cleanup_started", {})
    if service_runtime_id:
        stop_terminal_process(service_runtime_id, reason="network access cleanup")
    runtime["cleanup_state"] = "cleaned"
    runtime["cleanup_result"] = {"service_stopped": bool(service_runtime_id), "firewall_changed": False, "router_changed": False}
    runtime["ended_at"] = _now()
    _audit(runtime, "network_cleanup_completed", runtime["cleanup_result"])
    _RUNTIMES[runtime["network_access_runtime_id"]] = runtime


def _finish_network_response(runtime: Dict[str, Any], service_runtime_id: str) -> Dict[str, Any]:
    _cleanup_network_runtime(runtime, service_runtime_id)
    return _safe_success(runtime=_public_runtime(runtime))


def execute_network_access_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    if not plan or "network_access_runtime_id" not in plan:
        return _safe_failure("valid network access plan is required")
    runtime = deepcopy(plan)
    runtime["started_at"] = _now()
    _RUNTIMES[runtime["network_access_runtime_id"]] = runtime
    service_runtime_id = ""
    try:
        if not runtime.get("permission_decision", {}).get("allowed"):
            runtime["state"] = "approval_required"
            return _finish_network_response(runtime, service_runtime_id)
        service = runtime.get("service") or {}
        if service:
            runtime["state"] = "waiting_for_service"
            _audit(runtime, "network_service_requested", {"bind_host": runtime.get("bind_host"), "port": runtime.get("bind_port")})
            service_plan = plan_terminal_action(
                action_type="start_service",
                repository_root=runtime["repository_root"],
                working_directory=service.get("working_directory", "."),
                executable=service.get("executable", "python"),
                arguments=service.get("arguments", []),
                timeout_seconds=int(service.get("timeout_seconds", 30)),
                process_mode="background",
                permission_profile=service.get("permission_profile") or runtime.get("permission_profile"),
                metadata={"task_id": runtime.get("task_id", ""), "network_access_runtime_id": runtime["network_access_runtime_id"]},
            )
            if not service_plan.get("ok"):
                runtime["state"] = "blocked"
                runtime["diagnosis"] = service_plan
                _audit(runtime, "network_access_blocked", service_plan)
                return _finish_network_response(runtime, service_runtime_id)
            service_exec = execute_terminal_action(service_plan["plan"])
            if not service_exec.get("ok"):
                runtime["state"] = "failed"
                runtime["diagnosis"] = service_exec
                _audit(runtime, "network_access_failed", service_exec)
                return _finish_network_response(runtime, service_runtime_id)
            service_runtime_id = service_exec.get("runtime", {}).get("runtime_id", "")
            runtime["service_runtime_id"] = service_runtime_id
            runtime["service_runtime"] = service_exec.get("runtime", {})
            health = service.get("health_check")
            if health:
                ready = health_check(**health)
                if not ready.get("healthy"):
                    runtime["state"] = "failed"
                    runtime["localhost_health"] = ready
                    return _finish_network_response(runtime, service_runtime_id)
            runtime["state"] = "service_ready"
            _audit(runtime, "network_service_ready", {"service_runtime_id": service_runtime_id})
        bind = inspect_bind_address(runtime.get("bind_host", "127.0.0.1"), int(runtime.get("bind_port", 0)), runtime.get("selected_lan_ip", ""))
        runtime["bind_inspection"] = bind
        runtime["state"] = "bind_inspected"
        _audit(runtime, "network_bind_inspected", bind)
        localhost_tcp = tcp_connect("127.0.0.1", int(runtime["bind_port"]))
        localhost_http = http_check("127.0.0.1", int(runtime["bind_port"]), "/health")
        runtime["localhost_verification"] = {"tcp": localhost_tcp, "http": localhost_http}
        if localhost_tcp.get("reachable") and localhost_http.get("healthy"):
            runtime["state"] = "localhost_verified"
            _audit(runtime, "network_localhost_verified", runtime["localhost_verification"])
        lan_ip = runtime.get("selected_lan_ip", "")
        if not lan_ip:
            runtime["lan_verification"] = {"state": "physical_lan_unavailable_in_environment", "same_device_lan_verified": False}
            runtime["state"] = "physical_device_confirmation_required"
            _audit(runtime, "network_physical_device_confirmation_required", runtime["lan_verification"])
            return _finish_network_response(runtime, service_runtime_id)
        lan_tcp = tcp_connect(lan_ip, int(runtime["bind_port"]), selected_lan_ip=lan_ip, allow_loopback=False)
        runtime["lan_port_verification"] = lan_tcp
        if lan_tcp.get("reachable"):
            runtime["state"] = "lan_port_verified"
            _audit(runtime, "network_lan_port_verified", lan_tcp)
        lan_http = http_check(lan_ip, int(runtime["bind_port"]), "/health", selected_lan_ip=lan_ip, allow_loopback=False)
        runtime["lan_http_verification"] = lan_http
        if lan_http.get("healthy"):
            runtime["state"] = "lan_http_verified"
            _audit(runtime, "network_lan_http_verified", lan_http)
        for url in runtime.get("generated_urls", []):
            if url.get("access_scope") == "same_network_candidate":
                url["verification_status"] = "reachable_from_host" if lan_http.get("healthy") else "blocked"
                url["tested_from"] = "same_device_selected_lan_ip"
                url["verification_time"] = _now()
                url["viewport"] = ""
                url["next_required_confirmation"] = "physical device confirmation required"
        if lan_http.get("healthy"):
            live_scenario = {
                "scenario_id": "network_mobile_viewport_lan",
                "task_id": runtime.get("task_id", ""),
                "scenario_name": "LAN URL mobile viewport verification",
                "base_url": runtime["lan_url"],
                "allowed_origin": runtime["lan_url"],
                "network_access_policy": {"allow_selected_private_origin": True, "selected_private_origin": runtime["lan_url"]},
                "viewport": "mobile",
                "headless": True,
                "per_step_timeout_seconds": 5,
                "scenario_timeout_seconds": 30,
                "steps": [
                    {"step_id": "mobile", "action_type": "set_viewport", "viewport": "mobile"},
                    {"step_id": "navigate", "action_type": "navigate", "target_url": runtime["lan_url"]},
                    {"step_id": "ready", "action_type": "wait_for_ready"},
                    {"step_id": "title", "action_type": "assert_visible", "selector": {"type": "test_id", "value": "network-fixture-title"}},
                    {"step_id": "shot", "action_type": "capture_screenshot"},
                ],
            }
            live_plan = plan_live_test(live_scenario, repository_root=runtime["repository_root"], working_directory=".", permission_profile=runtime.get("permission_profile"))
            if live_plan.get("ok"):
                runtime["state"] = "mobile_viewport_testing"
                live_result = execute_live_test(live_plan["plan"])
                runtime["mobile_viewport_result"] = live_result.get("runtime", live_result)
                if live_result.get("runtime", {}).get("state") == "scenario_passed":
                    runtime["state"] = "mobile_viewport_verified"
                    _audit(runtime, "network_mobile_viewport_verified", {"lan_url": runtime["lan_url"]})
        runtime["physical_device_status"] = "physical_device_confirmation_required"
        _audit(runtime, "network_physical_device_confirmation_required", {"physical_device_verified": False})
        runtime["state"] = "completed" if runtime.get("state") in {"mobile_viewport_verified", "lan_http_verified"} else runtime.get("state")
        return _finish_network_response(runtime, service_runtime_id)
    finally:
        _cleanup_network_runtime(runtime, service_runtime_id)


def _public_runtime(runtime: Dict[str, Any]) -> Dict[str, Any]:
    return _redact(deepcopy(runtime))


def get_network_access_runtime(runtime_id: str) -> Dict[str, Any]:
    runtime = _RUNTIMES.get(runtime_id)
    if not runtime:
        return _safe_failure("runtime not found")
    return _safe_success(runtime=_public_runtime(runtime))


def cancel_network_access_runtime(runtime_id: str, reason: str = "user_requested") -> Dict[str, Any]:
    runtime = _RUNTIMES.get(runtime_id)
    if not runtime:
        return _safe_failure("runtime not found")
    runtime["state"] = "cancelled"
    _audit(runtime, "network_access_cancelled", {"reason": reason})
    service_id = str(runtime.get("service_runtime_id", ""))
    if service_id:
        stop_terminal_process(service_id, reason="network access cancel")
    runtime["cleanup_state"] = "cleaned"
    runtime["cleanup_result"] = {"cancelled": True, "service_stopped": bool(service_id)}
    return _safe_success(runtime=_public_runtime(runtime))


def restore_network_access_record(record: Dict[str, Any]) -> Dict[str, Any]:
    restored = _redact(deepcopy(record))
    restored["state"] = "manual_review_required"
    restored["service_restarted"] = False
    restored["browser_restarted"] = False
    restored["lan_test_resumed"] = False
    restored["restore_policy"] = "resume_requires_user_action"
    restored.setdefault("audit_events", []).append({"event": "network_restore_requires_user_action", "at": _now(), "details": {}})
    return _safe_success(runtime=restored)


def diagnose_bind_issue(bind_host: str, wants_same_wifi: bool = True) -> Dict[str, Any]:
    if bind_host in {"127.0.0.1", "localhost", "::1"} and wants_same_wifi:
        return _safe_success(
            issue="localhost_only_bind",
            result="bind_change_required",
            suggested_bind_host="0.0.0.0",
            permission_required=True,
            automatic_patch_applied=False,
        )
    return _safe_success(issue="no_bind_change_required_for_declared_goal", automatic_patch_applied=False)


def diagnose_port_conflict(port: int, selected_lan_ip: str = "") -> Dict[str, Any]:
    localhost = tcp_connect("127.0.0.1", int(port))
    return _safe_success(
        port=int(port),
        listening=bool(localhost.get("reachable")),
        ownership_known=False,
        action_taken="none",
        recommendation="choose alternate port or inspect owning process manually" if localhost.get("reachable") else "port appears free on loopback",
    )


def get_network_access_status() -> Dict[str, Any]:
    return _safe_success(
        runtime_count=len(_RUNTIMES),
        active_runtime_count=sum(1 for item in _RUNTIMES.values() if item.get("state") not in {"completed", "cleaned", "failed", "blocked", "cancelled"}),
        local_first=True,
        public_ip_lookup_used=False,
        public_network_used=False,
        subnet_scan_used=False,
        firewall_modified=False,
        router_modified=False,
        tunnel_started=False,
        external_api_used=False,
        physical_device_auto_claim=False,
        layer42_started=False,
    )


def get_safe_network_access_metadata(runtime: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "network_access_runtime_id": runtime.get("network_access_runtime_id"),
        "task_id": runtime.get("task_id"),
        "state": runtime.get("state"),
        "selected_interface": _redact(runtime.get("network_interface")),
        "selected_lan_ip": runtime.get("selected_lan_ip"),
        "bind_host": runtime.get("bind_host"),
        "bind_port": runtime.get("bind_port"),
        "generated_urls": _redact(runtime.get("generated_urls", [])),
        "physical_device_status": runtime.get("physical_device_status"),
        "cleanup_state": runtime.get("cleanup_state"),
        "audit_event_count": len(runtime.get("audit_events", [])),
    }
