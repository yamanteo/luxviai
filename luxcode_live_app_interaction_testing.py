from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import ipaddress
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from luxcode_autonomy_permission_controller import evaluate_requested_action
from luxcode_terminal_process_runtime import (
    execute_terminal_action,
    health_check,
    plan_terminal_action,
    stop_terminal_process,
)


SUPPORTED_ACTIONS = {
    "navigate",
    "wait_for_ready",
    "wait_for_selector",
    "click",
    "fill",
    "press_key",
    "select_option",
    "assert_visible",
    "assert_hidden",
    "assert_text",
    "assert_text_contains",
    "assert_value",
    "assert_url",
    "assert_element_count",
    "set_viewport",
    "capture_screenshot",
    "collect_console_errors",
    "collect_page_errors",
    "collect_layout_observations",
    "stop_scenario",
}
EXECUTED_ACTIONS = {
    "navigate",
    "wait_for_ready",
    "wait_for_selector",
    "click",
    "fill",
    "press_key",
    "assert_visible",
    "assert_hidden",
    "assert_text",
    "assert_text_contains",
    "assert_value",
    "assert_url",
    "assert_element_count",
    "set_viewport",
    "capture_screenshot",
    "collect_console_errors",
    "collect_page_errors",
    "collect_layout_observations",
    "stop_scenario",
}
DEFERRED_ACTIONS = {"select_option"}
VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900, "mobile_emulation": False, "label": "desktop viewport"},
    "mobile": {"width": 390, "height": 844, "mobile_emulation": True, "label": "mobile viewport emulation"},
}
LIFECYCLE_STATES = [
    "planned",
    "approval_required",
    "waiting_for_service",
    "service_ready",
    "browser_starting",
    "browser_ready",
    "scenario_running",
    "step_running",
    "step_passed",
    "step_failed",
    "scenario_passed",
    "scenario_failed",
    "timed_out",
    "cancelled",
    "cleanup_required",
    "cleaning",
    "cleaned",
    "blocked",
    "manual_review_required",
]
AUDIT_EVENTS = [
    "live_test_plan_created",
    "live_test_permission_evaluated",
    "live_test_scope_checked",
    "live_test_service_requested",
    "live_test_service_ready",
    "browser_session_started",
    "browser_context_created",
    "scenario_started",
    "step_started",
    "step_passed",
    "step_failed",
    "evidence_captured",
    "layout_observed",
    "console_error_observed",
    "page_error_observed",
    "scenario_passed",
    "scenario_failed",
    "scenario_timed_out",
    "scenario_cancelled",
    "cleanup_started",
    "cleanup_completed",
    "cleanup_failed",
    "restore_requires_user_action",
]

_RUNTIMES: Dict[str, Dict[str, Any]] = {}
_BROWSER_PROCESSES: Dict[str, subprocess.Popen] = {}
_STATUS = {
    "external_api_used": False,
    "external_network_used": False,
    "raw_javascript_allowed": False,
    "desktop_automation_used": False,
    "browser_binary_downloaded": False,
    "persistent_browser_profile_used": False,
    "layer42_started": False,
}


def _now() -> float:
    return round(time.time(), 6)


def _digest(parts: List[Any]) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str).encode("utf-8", "replace")
    return hashlib.sha256(raw).hexdigest()[:20]


def _safe_success(**extra: Any) -> Dict[str, Any]:
    data = {"ok": True, "external_api_used": False, "external_network_used": False}
    data.update(extra)
    return data


def _safe_failure(reason: str, **extra: Any) -> Dict[str, Any]:
    data = {"ok": False, "blocked": True, "reason": reason, "external_api_used": False, "external_network_used": False}
    data.update(extra)
    return data


def _redact_text(value: Any, limit: int = 1200) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{6,}", r"\1=[redacted]", text)
    text = re.sub(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{8,}", "Bearer [redacted]", text)
    text = re.sub(r"sk-[A-Za-z0-9]{10,}", "sk-[redacted]", text)
    if len(text) > limit:
        return text[:limit] + "...[truncated]"
    return text


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): ("[redacted]" if re.search(r"(?i)(token|secret|password|cookie|authorization)", str(k)) else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value[:80]]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _audit(target: Dict[str, Any], event: str, details: Optional[Dict[str, Any]] = None) -> None:
    target.setdefault("audit_events", []).append({"event": event, "at": _now(), "details": _redact(details or {})})


def _is_localhost_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"} and bool(parsed.port)


def _origin(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.hostname or not parsed.port:
        return ""
    host = parsed.hostname
    if host == "::1":
        host = "[::1]"
    return f"{parsed.scheme}://{host}:{parsed.port}"


def _is_selected_private_origin(url: str, policy: Optional[Dict[str, Any]] = None) -> bool:
    policy = policy or {}
    if not policy.get("allow_selected_private_origin"):
        return False
    selected = str(policy.get("selected_private_origin", ""))
    if not selected or _origin(url) != selected:
        return False
    parsed = urllib.parse.urlparse(url)
    try:
        ip = ipaddress.ip_address(parsed.hostname or "")
    except ValueError:
        return False
    return parsed.scheme == "http" and ip.is_private and not ip.is_loopback and not ip.is_link_local and bool(parsed.port)


def _validate_base_url(base_url: str, network_access_policy: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    if not base_url:
        return False, "base_url is required"
    if not _is_localhost_url(base_url) and not _is_selected_private_origin(base_url, network_access_policy):
        return False, "only localhost or selected private network origins are allowed"
    return True, ""


def _safe_path(root: str, relative: str = ".") -> Tuple[Optional[Path], str]:
    try:
        base = Path(root).resolve()
        target = (base / (relative or ".")).resolve()
    except Exception as exc:
        return None, f"path resolution failed: {type(exc).__name__}"
    if base != target and base not in target.parents:
        return None, "scope outside repository root blocked"
    if any(part == ".." for part in Path(relative or ".").parts):
        return None, "path traversal blocked"
    return target, ""


def _selector_to_css(selector: Any) -> Tuple[str, str]:
    if isinstance(selector, str):
        kind, value = "css", selector
    elif isinstance(selector, dict):
        kind, value = str(selector.get("type", "css")), str(selector.get("value", ""))
    else:
        return "", "selector must be a string or object"
    if not value or len(value) > 240:
        return "", "selector is empty or too long"
    if re.search(r"(?i)(<script|javascript:|eval\s*\(|function\s*\(|=>|document\.|window\.)", value):
        return "", "selector contains script-like content"
    if kind == "test_id":
        if not re.match(r"^[A-Za-z0-9_.:-]{1,120}$", value):
            return "", "test id selector contains unsafe characters"
        return f'[data-testid="{value}"]', ""
    if kind in {"id", "stable_id"}:
        if not re.match(r"^[A-Za-z0-9_.:-]{1,120}$", value):
            return "", "id selector contains unsafe characters"
        return f"#{value}", ""
    if kind == "css":
        if re.search(r"[{};`]", value):
            return "", "css selector contains blocked characters"
        return value, ""
    return "", "selector type is not executable in this version"


def _find_browser() -> Dict[str, Any]:
    candidates = [
        os.environ.get("LUXCODE_BROWSER_PATH", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        shutil.which("chrome") or "",
        shutil.which("msedge") or "",
        shutil.which("chromium") or "",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return {"available": True, "engine": "chromium_cdp", "path": str(Path(candidate))}
    return {"available": False, "engine": "chromium_cdp", "path": "", "reason": "local Chrome/Edge binary not found"}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _CDPClient:
    def __init__(self, websocket_url: str):
        parsed = urllib.parse.urlparse(websocket_url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = int(parsed.port or 80)
        self.path = parsed.path
        if parsed.query:
            self.path += "?" + parsed.query
        self.sock = socket.create_connection((self.host, self.port), timeout=5)
        self.next_id = 1
        self.console_errors: List[str] = []
        self.page_errors: List[str] = []
        self._handshake()

    def _handshake(self) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        self.sock.sendall(request)
        response = self.sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError("CDP websocket handshake failed")

    def close(self) -> None:
        try:
            self.sock.close()
        except Exception:
            pass

    def _send_frame(self, payload: bytes, opcode: int = 1) -> None:
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(payload[i] ^ mask[i % 4] for i in range(length))
        self.sock.sendall(bytes(header) + masked)

    def _recv_exact(self, length: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < length:
            part = self.sock.recv(length - len(chunks))
            if not part:
                raise RuntimeError("CDP websocket closed")
            chunks.extend(part)
        return bytes(chunks)

    def _recv_frame(self) -> Dict[str, Any]:
        first = self._recv_exact(2)
        opcode = first[0] & 0x0F
        length = first[1] & 0x7F
        masked = bool(first[1] & 0x80)
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length) if length else b""
        if masked:
            payload = bytes(payload[i] ^ mask[i % 4] for i in range(length))
        if opcode == 8:
            raise RuntimeError("CDP websocket close frame received")
        if opcode == 9:
            self._send_frame(payload, opcode=10)
            return {}
        if opcode != 1:
            return {}
        return json.loads(payload.decode("utf-8", "replace"))

    def _record_event(self, message: Dict[str, Any]) -> None:
        method = message.get("method")
        params = message.get("params", {})
        if method == "Runtime.consoleAPICalled" and params.get("type") == "error":
            args = " ".join(_redact_text(arg.get("value", arg.get("description", "")), 400) for arg in params.get("args", []))
            self.console_errors.append(args or "console error")
        elif method == "Runtime.exceptionThrown":
            detail = params.get("exceptionDetails", {})
            self.page_errors.append(_redact_text(detail.get("text") or detail.get("exception", {}).get("description", "page error"), 400))
        elif method == "Log.entryAdded" and params.get("entry", {}).get("level") == "error":
            self.console_errors.append(_redact_text(params.get("entry", {}).get("text", "log error"), 400))

    def command(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 5) -> Dict[str, Any]:
        message_id = self.next_id
        self.next_id += 1
        self._send_frame(json.dumps({"id": message_id, "method": method, "params": params or {}}).encode("utf-8"))
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.sock.settimeout(max(0.1, deadline - time.time()))
            message = self._recv_frame()
            if not message:
                continue
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(_redact_text(message["error"]))
                return message.get("result", {})
            self._record_event(message)
        raise TimeoutError(f"CDP command timed out: {method}")

    def evaluate(self, expression: str, timeout: float = 5) -> Any:
        result = self.command("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True}, timeout=timeout)
        if "exceptionDetails" in result:
            raise RuntimeError(_redact_text(result["exceptionDetails"]))
        return result.get("result", {}).get("value")


def get_live_testing_schema() -> Dict[str, Any]:
    return _safe_success(
        layer="luxcode_live_app_interaction_testing",
        local_first=True,
        supported_actions=sorted(SUPPORTED_ACTIONS),
        executable_actions=sorted(EXECUTED_ACTIONS),
        deferred_actions=sorted(DEFERRED_ACTIONS),
        raw_javascript_endpoint=False,
        arbitrary_url_endpoint=False,
        arbitrary_coordinate_click=False,
        desktop_automation=False,
        allowed_origins=["http://127.0.0.1:<port>", "http://localhost:<port>", "network-plan-selected-private-origin"],
        blocked_origins=["public_internet", "lan_ip", "file_url", "custom_protocol", "production_url"],
        lifecycle_states=LIFECYCLE_STATES,
        audit_events=AUDIT_EVENTS,
        evidence_policy={"structured": True, "screenshots": "temporary_and_cleaned", "secret_redaction": True},
        restore_policy="manual_review_required_no_auto_browser_or_service_start",
    )


def get_live_testing_registry() -> Dict[str, Any]:
    browser = _find_browser()
    return _safe_success(
        browser_adapter={"engine": "chromium_cdp", "available": browser.get("available"), "path_present": bool(browser.get("path")), "downloads_required": False},
        action_registry={name: {"supported": True, "executable": name in EXECUTED_ACTIONS, "raw_script": False} for name in sorted(SUPPORTED_ACTIONS)},
        selector_registry=["data-testid", "stable_id", "limited_css", "role_label_text_schema_only"],
        viewport_registry=deepcopy(VIEWPORTS),
        browser_context_policy={
            "temporary_profile": True,
            "user_profile_reuse": False,
            "cookies_cleared": True,
            "downloads_limited_to_temp": True,
            "camera_microphone_geolocation_notifications_clipboard": "blocked",
        },
    )


def validate_live_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    base_url = str(scenario.get("base_url", ""))
    network_access_policy = scenario.get("network_access_policy") if isinstance(scenario.get("network_access_policy"), dict) else {}
    ok, reason = _validate_base_url(base_url, network_access_policy)
    if not ok:
        issues.append(reason)
    allowed_origin = scenario.get("allowed_origin") or _origin(base_url)
    if allowed_origin != _origin(base_url):
        issues.append("allowed_origin must match base_url origin")
    if scenario.get("raw_javascript") or scenario.get("script"):
        issues.append("raw javascript is blocked")
    viewport = scenario.get("viewport", "desktop")
    if isinstance(viewport, dict):
        width, height = int(viewport.get("width", 0)), int(viewport.get("height", 0))
        if width < 240 or width > 3840 or height < 240 or height > 2160:
            issues.append("viewport dimensions out of bounds")
    elif viewport not in VIEWPORTS:
        issues.append("unknown viewport profile")
    steps = scenario.get("steps", [])
    if not isinstance(steps, list) or not steps:
        issues.append("scenario must include ordered steps")
    for index, step in enumerate(steps):
        action = str(step.get("action_type", ""))
        if action not in SUPPORTED_ACTIONS:
            issues.append(f"unsupported action at step {index + 1}: {action}")
        if action in {"raw_javascript", "evaluate", "execute_script"}:
            issues.append("raw script action is blocked")
        if action in {"click", "fill", "wait_for_selector", "assert_visible", "assert_hidden", "assert_text", "assert_text_contains", "assert_value", "assert_element_count"}:
            _, selector_error = _selector_to_css(step.get("selector"))
            if selector_error:
                issues.append(f"invalid selector at step {index + 1}: {selector_error}")
        target_url = str(step.get("target_url", ""))
        if target_url and not target_url.startswith(allowed_origin):
            issues.append(f"external target url blocked at step {index + 1}")
    return _safe_success(valid=not issues, issues=issues, blocked=bool(issues), allowed_origin=allowed_origin)


def plan_live_test(
    scenario: Dict[str, Any],
    repository_root: str = "",
    working_directory: str = ".",
    permission_profile: Optional[Dict[str, Any]] = None,
    service: Optional[Dict[str, Any]] = None,
    approval_digest: str = "",
) -> Dict[str, Any]:
    root_path, path_error = _safe_path(repository_root or os.getcwd(), ".")
    if path_error:
        return _safe_failure(path_error)
    cwd_path, cwd_error = _safe_path(str(root_path), working_directory or ".")
    if cwd_error:
        return _safe_failure(cwd_error)
    validation = validate_live_scenario(scenario)
    if not validation.get("valid"):
        return _safe_failure("scenario validation failed", validation=validation)
    risk = str(scenario.get("risk_classification") or ("important" if service else "normal"))
    permission = evaluate_requested_action(
        profile=permission_profile,
        task_id=str(scenario.get("task_id", "")),
        operation="run_tests",
        target_path=str(cwd_path.relative_to(root_path)) if cwd_path != root_path else ".",
        metadata={"why_needed": "execute local live app interaction test", "risk_hint": risk},
        approval_digest=approval_digest,
        recovery_plan_available=True,
    ) if permission_profile else _safe_success(allowed=False, requires_approval=True, reason="permission profile is required", risk_level=risk)
    runtime_id = "luxlive-" + _digest([scenario.get("scenario_id"), scenario.get("task_id"), scenario.get("base_url"), time.time()])
    plan = {
        "live_test_runtime_id": runtime_id,
        "state": "planned" if permission.get("allowed") else "approval_required",
        "scenario": _redact(scenario),
        "repository_root": str(root_path),
        "working_directory": str(cwd_path),
        "service": deepcopy(service or {}),
        "permission_profile": deepcopy(permission_profile or {}),
        "allowed_origin": validation.get("allowed_origin"),
        "risk_classification": permission.get("risk_level", risk),
        "permission_decision": permission,
        "cleanup_policy": {"owned_browser_only": True, "owned_service_only": True, "temporary_evidence_cleanup": True},
        "browser_policy": get_live_testing_registry()["browser_context_policy"],
        "audit_events": [],
    }
    _audit(plan, "live_test_plan_created", {"scenario_id": scenario.get("scenario_id"), "runtime_id": runtime_id})
    _audit(plan, "live_test_permission_evaluated", permission)
    _audit(plan, "live_test_scope_checked", {"working_directory": plan["working_directory"]})
    return _safe_success(plan=plan)


def _json_http(url: str, method: str = "GET", timeout: float = 5) -> Dict[str, Any]:
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_cdp(port: int, timeout: float = 8) -> Dict[str, Any]:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            return _json_http(f"http://127.0.0.1:{port}/json/version", timeout=1)
        except Exception as exc:
            last = type(exc).__name__
            time.sleep(0.1)
    raise TimeoutError(f"browser cdp not ready: {last}")


def _new_page(port: int) -> str:
    try:
        data = _json_http(f"http://127.0.0.1:{port}/json/new?{urllib.parse.quote('about:blank')}", method="PUT", timeout=3)
    except urllib.error.HTTPError:
        pages = _json_http(f"http://127.0.0.1:{port}/json", timeout=3)
        data = pages[0]
    return str(data["webSocketDebuggerUrl"])


def _launch_browser(runtime: Dict[str, Any], headless: bool = True) -> Tuple[_CDPClient, Path, int]:
    browser = _find_browser()
    if not browser.get("available"):
        raise RuntimeError(browser.get("reason", "browser unavailable"))
    temp_root = Path(tempfile.mkdtemp(prefix="luxlive-browser-"))
    profile_dir = temp_root / "profile"
    download_dir = temp_root / "downloads"
    profile_dir.mkdir()
    download_dir.mkdir()
    port = _free_port()
    args = [
        browser["path"],
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-features=Translate,MediaRouter,OptimizationHints",
        "--deny-permission-prompts",
        "--disable-notifications",
        f"--download-default-directory={download_dir}",
        "about:blank",
    ]
    if headless:
        args.insert(1, "--headless=new")
    proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    _BROWSER_PROCESSES[runtime["live_test_runtime_id"]] = proc
    runtime["browser"] = {"engine": browser["engine"], "pid": proc.pid, "owned_by_runtime": True, "temporary_profile": True, "headless": headless}
    _audit(runtime, "browser_session_started", {"pid": proc.pid, "headless": headless})
    _wait_cdp(port)
    client = _CDPClient(_new_page(port))
    client.command("Runtime.enable")
    client.command("Page.enable")
    client.command("Log.enable")
    _audit(runtime, "browser_context_created", {"temporary_profile": True, "profile_dir": "[temporary]"})
    return client, temp_root, port


def _js_string(value: Any) -> str:
    return json.dumps(str(value or ""))


def _element_js(css: str, expression: str) -> str:
    return f"(() => {{ const el = document.querySelector({_js_string(css)}); if (!el) return {{ok:false, reason:'selector_not_found'}}; {expression} }})()"


def _wait_until(client: _CDPClient, expression: str, timeout: float, interval: float = 0.1) -> Any:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = client.evaluate(expression, timeout=min(2, timeout))
        if last:
            return last
        time.sleep(interval)
    return last


def _execute_step(client: _CDPClient, runtime: Dict[str, Any], step: Dict[str, Any], evidence_dir: Path) -> Dict[str, Any]:
    action = str(step.get("action_type", ""))
    timeout = max(1, min(int(step.get("timeout_seconds", runtime.get("per_step_timeout", 5))), 30))
    if action not in EXECUTED_ACTIONS:
        return _safe_failure("unsupported action is schema-only in this version", action_type=action)
    if action == "navigate":
        target = str(step.get("target_url") or runtime["scenario"].get("base_url"))
        if not target.startswith(runtime["allowed_origin"]):
            return _safe_failure("blocked_external_origin", state="scope_expansion_required", target_url=target)
        client.command("Page.navigate", {"url": target}, timeout=timeout)
        loaded = _wait_until(client, "document.readyState === 'complete'", timeout)
        current_url = client.evaluate("location.href")
        if not str(current_url).startswith(runtime["allowed_origin"]):
            return _safe_failure("blocked_external_origin_after_redirect", observed_url=current_url)
        return _safe_success(observed_url=current_url, loaded=bool(loaded))
    if action == "wait_for_ready":
        return _safe_success(ready=bool(_wait_until(client, "document.readyState === 'complete'", timeout)))
    if action == "set_viewport":
        viewport = step.get("viewport") or runtime["scenario"].get("viewport", "desktop")
        profile = viewport if isinstance(viewport, dict) else VIEWPORTS.get(viewport, VIEWPORTS["desktop"])
        width, height = int(profile["width"]), int(profile["height"])
        client.command("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": bool(profile.get("mobile_emulation"))})
        return _safe_success(viewport={"width": width, "height": height, "mobile_viewport": bool(profile.get("mobile_emulation"))})
    if action in {"wait_for_selector", "click", "fill", "press_key", "assert_visible", "assert_hidden", "assert_text", "assert_text_contains", "assert_value", "assert_element_count"}:
        css, selector_error = _selector_to_css(step.get("selector"))
        if selector_error:
            return _safe_failure(selector_error)
        if action == "wait_for_selector":
            found = _wait_until(client, f"!!document.querySelector({_js_string(css)})", timeout)
            return _safe_success(found=bool(found), selector=css) if found else _safe_failure("selector_not_found", selector=css)
        if action == "click":
            result = client.evaluate(_element_js(css, "el.click(); return {ok:true, clicked:true};"), timeout=timeout)
            return _safe_success(**result) if result.get("ok") else _safe_failure(result.get("reason", "click failed"), selector=css)
        if action == "fill":
            value = str(step.get("value", ""))
            result = client.evaluate(_element_js(css, f"el.value = {_js_string(value)}; el.dispatchEvent(new Event('input', {{bubbles:true}})); return {{ok:true, value_length:{len(value)}}};"), timeout=timeout)
            return _safe_success(**result)
        if action == "press_key":
            key = str(step.get("key", "Enter"))
            result = client.evaluate(_element_js(css, f"el.dispatchEvent(new KeyboardEvent('keydown', {{key:{_js_string(key)}, bubbles:true}})); return {{ok:true, key:{_js_string(key)}}};"), timeout=timeout)
            return _safe_success(**result)
        if action == "assert_visible":
            value = client.evaluate(_element_js(css, "const s=getComputedStyle(el); return {ok:true, visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length) && s.visibility !== 'hidden' && s.display !== 'none'};"), timeout=timeout)
            return _safe_success(**value) if value.get("visible") else _safe_failure("element_not_visible", selector=css)
        if action == "assert_hidden":
            value = client.evaluate(f"(() => {{ const el=document.querySelector({_js_string(css)}); if(!el) return {{ok:true, hidden:true}}; const s=getComputedStyle(el); return {{ok:true, hidden: !(el.offsetWidth || el.offsetHeight || el.getClientRects().length) || s.visibility === 'hidden' || s.display === 'none'}}; }})()", timeout=timeout)
            return _safe_success(**value) if value.get("hidden") else _safe_failure("element_not_hidden", selector=css)
        if action == "assert_text":
            expected = str(step.get("expected_text", ""))
            value = client.evaluate(_element_js(css, "return {ok:true, text:(el.textContent || '').trim()};"), timeout=timeout)
            return _safe_success(**value) if value.get("text") == expected else _safe_failure("text_mismatch", expected=expected, observed=value.get("text"))
        if action == "assert_text_contains":
            expected = str(step.get("expected_text", ""))
            value = client.evaluate(_element_js(css, "return {ok:true, text:(el.textContent || '').trim()};"), timeout=timeout)
            return _safe_success(**value) if expected in str(value.get("text", "")) else _safe_failure("text_missing", expected=expected, observed=value.get("text"))
        if action == "assert_value":
            expected = str(step.get("expected_value", ""))
            value = client.evaluate(_element_js(css, "return {ok:true, value:el.value || ''};"), timeout=timeout)
            return _safe_success(**value) if value.get("value") == expected else _safe_failure("value_mismatch", expected=expected, observed=value.get("value"))
        if action == "assert_element_count":
            expected_count = int(step.get("expected_count", 0))
            count = client.evaluate(f"document.querySelectorAll({_js_string(css)}).length", timeout=timeout)
            return _safe_success(count=count) if int(count) == expected_count else _safe_failure("element_count_mismatch", expected=expected_count, observed=count)
    if action == "assert_url":
        expected = str(step.get("expected_url", ""))
        current = str(client.evaluate("location.href", timeout=timeout))
        if expected and current != expected:
            return _safe_failure("url_mismatch", expected=expected, observed=current)
        if not current.startswith(runtime["allowed_origin"]):
            return _safe_failure("blocked_external_origin_after_redirect", observed_url=current)
        return _safe_success(observed_url=current)
    if action == "capture_screenshot":
        if step.get("sensitive", False):
            return _safe_failure("screenshot blocked for sensitive step")
        index = len(runtime.get("evidence", [])) + 1
        result = client.command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False}, timeout=timeout)
        screenshot_path = evidence_dir / f"evidence-{index}.png"
        screenshot_path.write_bytes(base64.b64decode(result.get("data", "")))
        evidence = {"type": "screenshot", "filename": screenshot_path.name, "temporary": True, "path": str(screenshot_path), "cleaned": False}
        runtime.setdefault("evidence", []).append(evidence)
        _audit(runtime, "evidence_captured", {"type": "screenshot", "filename": screenshot_path.name})
        return _safe_success(evidence=evidence)
    if action == "collect_console_errors":
        return _safe_success(console_errors=[_redact_text(item) for item in client.console_errors[:20]])
    if action == "collect_page_errors":
        return _safe_success(page_errors=[_redact_text(item) for item in client.page_errors[:20]])
    if action == "collect_layout_observations":
        script = """
(() => {
  const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
  const vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
  const doc = document.documentElement;
  const body = document.body || doc;
  const visible = Array.from(document.querySelectorAll('body *')).filter((el) => {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  }).slice(0, 400);
  const controls = visible.filter((el) => /^(A|BUTTON|INPUT|SELECT|TEXTAREA)$/.test(el.tagName) || el.getAttribute('role') === 'button');
  const rectOf = (el) => {
    const r = el.getBoundingClientRect();
    return {tag: el.tagName.toLowerCase(), id: el.id || '', testid: el.getAttribute('data-testid') || '', text: (el.textContent || '').trim().slice(0, 80), x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height)};
  };
  const offscreen = controls.map(rectOf).filter((r) => r.x < -1 || r.y < -1 || r.x + r.width > vw + 1 || r.y + r.height > vh + 1).slice(0, 20);
  const smallTouchTargets = controls.map(rectOf).filter((r) => r.width < 44 || r.height < 44).slice(0, 20);
  const clippedText = visible.filter((el) => el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1).map(rectOf).slice(0, 20);
  const overlaps = [];
  for (let i = 0; i < Math.min(visible.length, 80); i++) {
    const a = visible[i].getBoundingClientRect();
    for (let j = i + 1; j < Math.min(visible.length, 80); j++) {
      const b = visible[j].getBoundingClientRect();
      const area = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
      if (area > 1600 && !visible[i].contains(visible[j]) && !visible[j].contains(visible[i])) {
        overlaps.push({a: rectOf(visible[i]), b: rectOf(visible[j]), overlap_area: Math.round(area)});
        break;
      }
    }
    if (overlaps.length >= 10) break;
  }
  const sticky = visible.filter((el) => ['fixed', 'sticky'].includes(getComputedStyle(el).position)).map(rectOf).slice(0, 20);
  const excessiveWhitespace = (doc.scrollHeight || body.scrollHeight || 0) > vh * 3 && visible.length < 6;
  return {
    viewport: {width: vw, height: vh, devicePixelRatio: window.devicePixelRatio || 1, direction: getComputedStyle(doc).direction},
    horizontal_overflow: (doc.scrollWidth || body.scrollWidth || 0) > vw + 1,
    clipped_text: clippedText,
    offscreen_controls: offscreen,
    overlapping_elements: overlaps,
    missing_controls: controls.length === 0,
    hidden_navigation: !!document.querySelector('nav') && !visible.includes(document.querySelector('nav')),
    broken_modal_position: Array.from(document.querySelectorAll('[role="dialog"], dialog, .modal')).map(rectOf).filter((r) => r.x < 0 || r.y < 0 || r.x + r.width > vw || r.y + r.height > vh),
    sticky_collisions: sticky,
    excessive_whitespace: excessiveWhitespace,
    touch_targets_too_small: smallTouchTargets,
    long_text_overflow: clippedText.filter((r) => r.text.length > 40),
    rtl_alignment_warning: getComputedStyle(doc).direction === 'rtl' && visible.some((el) => getComputedStyle(el).textAlign === 'left')
  };
})()
"""
        observations = client.evaluate(script, timeout=timeout) or {}
        runtime.setdefault("layout_observations", []).append(observations)
        _audit(runtime, "layout_observed", {"horizontal_overflow": observations.get("horizontal_overflow"), "overlap_count": len(observations.get("overlapping_elements", []))})
        return _safe_success(layout_observations=observations)
    if action == "stop_scenario":
        return _safe_success(stopped=True)
    return _safe_failure("unsupported action")


def execute_live_test(plan: Dict[str, Any], approval_digest: str = "") -> Dict[str, Any]:
    if not plan or "live_test_runtime_id" not in plan:
        return _safe_failure("valid live test plan is required")
    runtime = deepcopy(plan)
    runtime["state"] = "waiting_for_service"
    runtime["started_at"] = _now()
    runtime["completed_steps"] = []
    runtime["failed_step"] = None
    runtime["evidence"] = []
    _RUNTIMES[runtime["live_test_runtime_id"]] = runtime
    if runtime.get("permission_decision", {}).get("requires_approval") and not runtime.get("permission_decision", {}).get("allowed"):
        runtime["state"] = "approval_required"
        return _finish_runtime_response(runtime, None, None, "")
    client: Optional[_CDPClient] = None
    temp_root: Optional[Path] = None
    service_runtime_id = ""
    try:
        service = runtime.get("service") or {}
        if service:
            _audit(runtime, "live_test_service_requested", {"action_type": service.get("action_type", "start_service")})
            service_plan = plan_terminal_action(
                action_type="start_service",
                repository_root=runtime["repository_root"],
                working_directory=service.get("working_directory", "."),
                executable=service.get("executable", "python"),
                arguments=service.get("arguments", []),
                timeout_seconds=int(service.get("timeout_seconds", 30)),
                process_mode="background",
                permission_profile=service.get("permission_profile") or runtime.get("permission_profile"),
                metadata={"task_id": runtime["scenario"].get("task_id", ""), "live_test_runtime_id": runtime["live_test_runtime_id"]},
            )
            if not service_plan.get("ok"):
                runtime["state"] = "blocked"
                runtime["failed_step"] = {"reason": "service plan failed", "details": service_plan}
                return _finish_runtime_response(runtime, client, temp_root, service_runtime_id)
            service_exec = execute_terminal_action(service_plan["plan"])
            if not service_exec.get("ok"):
                runtime["state"] = "scenario_failed"
                runtime["failed_step"] = {"reason": "service start failed", "details": service_exec}
                return _finish_runtime_response(runtime, client, temp_root, service_runtime_id)
            service_runtime_id = service_exec.get("runtime", {}).get("runtime_id", "")
            runtime["service_runtime"] = service_exec.get("runtime", {})
            health = service.get("health_check", {})
            if health:
                ready = health_check(**health)
                if not ready.get("healthy"):
                    runtime["state"] = "scenario_failed"
                    runtime["failed_step"] = {"reason": "service health failed", "details": ready}
                    return _finish_runtime_response(runtime, client, temp_root, service_runtime_id)
            runtime["state"] = "service_ready"
            _audit(runtime, "live_test_service_ready", {"service_runtime_id": service_runtime_id})
        runtime["state"] = "browser_starting"
        client, temp_root, _ = _launch_browser(runtime, headless=bool(runtime["scenario"].get("headless", True)))
        runtime["state"] = "browser_ready"
        evidence_dir = temp_root / "evidence"
        evidence_dir.mkdir(exist_ok=True)
        scenario_timeout = max(3, min(int(runtime["scenario"].get("scenario_timeout_seconds", 30)), 180))
        runtime["per_step_timeout"] = max(1, min(int(runtime["scenario"].get("per_step_timeout_seconds", 5)), 30))
        deadline = time.time() + scenario_timeout
        runtime["state"] = "scenario_running"
        _audit(runtime, "scenario_started", {"scenario_id": runtime["scenario"].get("scenario_id")})
        for step in runtime["scenario"].get("steps", []):
            if time.time() > deadline:
                runtime["state"] = "timed_out"
                _audit(runtime, "scenario_timed_out", {"step_id": step.get("step_id")})
                break
            runtime["current_step"] = step.get("step_id")
            runtime["state"] = "step_running"
            _audit(runtime, "step_started", {"step_id": step.get("step_id"), "action_type": step.get("action_type")})
            result = _execute_step(client, runtime, step, evidence_dir)
            step_result = {"step_id": step.get("step_id"), "action_type": step.get("action_type"), "result": _redact(result)}
            if result.get("ok"):
                runtime["completed_steps"].append(step_result)
                runtime["state"] = "step_passed"
                _audit(runtime, "step_passed", {"step_id": step.get("step_id")})
                if step.get("action_type") == "stop_scenario":
                    runtime["state"] = "cancelled"
                    _audit(runtime, "scenario_cancelled", {"reason": "stop_scenario step"})
                    break
            else:
                runtime["failed_step"] = step_result
                runtime["state"] = "scenario_failed"
                _audit(runtime, "step_failed", step_result)
                break
        if runtime["state"] in {"step_passed", "scenario_running"}:
            runtime["state"] = "scenario_passed"
            _audit(runtime, "scenario_passed", {"completed_steps": len(runtime["completed_steps"])})
        runtime["console_error_summary"] = [_redact_text(item) for item in client.console_errors[:20]]
        runtime["page_error_summary"] = [_redact_text(item) for item in client.page_errors[:20]]
        if runtime["console_error_summary"]:
            _audit(runtime, "console_error_observed", {"count": len(runtime["console_error_summary"])})
        if runtime["page_error_summary"]:
            _audit(runtime, "page_error_observed", {"count": len(runtime["page_error_summary"])})
        return _finish_runtime_response(runtime, client, temp_root, service_runtime_id)
    except TimeoutError as exc:
        runtime["state"] = "timed_out"
        runtime["failed_step"] = {"reason": _redact_text(exc)}
        _audit(runtime, "scenario_timed_out", {"error": type(exc).__name__})
        return _finish_runtime_response(runtime, client, temp_root, service_runtime_id)
    except Exception as exc:
        runtime["state"] = "scenario_failed"
        runtime["failed_step"] = {"reason": _redact_text(f"{type(exc).__name__}: {exc}")}
        _audit(runtime, "scenario_failed", {"error": type(exc).__name__})
        return _finish_runtime_response(runtime, client, temp_root, service_runtime_id)
    finally:
        _cleanup_runtime(runtime, client, temp_root, service_runtime_id)


def _finish_runtime_response(runtime: Dict[str, Any], client: Optional[_CDPClient], temp_root: Optional[Path], service_runtime_id: str = "") -> Dict[str, Any]:
    _cleanup_runtime(runtime, client, temp_root, service_runtime_id)
    return _safe_success(runtime=_public_runtime(runtime))


def _cleanup_runtime(runtime: Dict[str, Any], client: Optional[_CDPClient], temp_root: Optional[Path], service_runtime_id: str = "") -> None:
    if runtime.get("cleanup_state") == "cleaned":
        _RUNTIMES[runtime["live_test_runtime_id"]] = runtime
        return
    runtime["cleanup_state"] = "cleaning"
    _audit(runtime, "cleanup_started", {})
    try:
        if client:
            client.close()
        proc = _BROWSER_PROCESSES.pop(runtime["live_test_runtime_id"], None)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        if service_runtime_id:
            stop_terminal_process(service_runtime_id, reason="live test cleanup")
        if temp_root and temp_root.exists():
            for evidence in runtime.get("evidence", []):
                evidence["cleaned"] = True
            shutil.rmtree(temp_root, ignore_errors=True)
        runtime["cleanup_state"] = "cleaned"
        runtime["cleanup_result"] = {"browser_closed": True, "service_stopped": bool(service_runtime_id), "temporary_artifacts_removed": True}
        _audit(runtime, "cleanup_completed", runtime["cleanup_result"])
    except Exception as exc:
        runtime["cleanup_state"] = "cleanup_failed"
        runtime["cleanup_result"] = {"error": _redact_text(f"{type(exc).__name__}: {exc}")}
        _audit(runtime, "cleanup_failed", runtime["cleanup_result"])
    runtime["ended_at"] = _now()
    _RUNTIMES[runtime["live_test_runtime_id"]] = runtime


def _public_runtime(runtime: Dict[str, Any]) -> Dict[str, Any]:
    public = deepcopy(runtime)
    for evidence in public.get("evidence", []):
        if "path" in evidence:
            evidence["path"] = "[temporary-cleaned]" if evidence.get("cleaned") else "[temporary]"
    public["scenario"] = _redact(public.get("scenario", {}))
    return _redact(public)


def get_live_test_runtime(runtime_id: str) -> Dict[str, Any]:
    runtime = _RUNTIMES.get(runtime_id)
    if not runtime:
        return _safe_failure("runtime not found")
    return _safe_success(runtime=_public_runtime(runtime))


def cancel_live_test_runtime(runtime_id: str, reason: str = "user_requested") -> Dict[str, Any]:
    runtime = _RUNTIMES.get(runtime_id)
    if not runtime:
        return _safe_failure("runtime not found")
    runtime["state"] = "cancelled"
    _audit(runtime, "scenario_cancelled", {"reason": reason})
    _cleanup_runtime(runtime, None, None, str(runtime.get("service_runtime", {}).get("runtime_id", "")))
    return _safe_success(runtime=_public_runtime(runtime))


def get_live_test_evidence(runtime_id: str) -> Dict[str, Any]:
    runtime = _RUNTIMES.get(runtime_id)
    if not runtime:
        return _safe_failure("runtime not found")
    return _safe_success(evidence=deepcopy(_public_runtime(runtime).get("evidence", [])), console_errors=runtime.get("console_error_summary", []), page_errors=runtime.get("page_error_summary", []))


def restore_live_test_record(record: Dict[str, Any]) -> Dict[str, Any]:
    restored = _redact(deepcopy(record))
    restored["state"] = "manual_review_required"
    restored["browser_restarted"] = False
    restored["service_restarted"] = False
    restored["execution_resumed"] = False
    restored["restore_policy"] = "requires explicit user action before any browser or service execution"
    restored.setdefault("audit_events", []).append({"event": "restore_requires_user_action", "at": _now(), "details": {}})
    return _safe_success(runtime=restored)


def get_live_testing_status() -> Dict[str, Any]:
    browser = _find_browser()
    return _safe_success(
        browser_engine="chromium_cdp",
        browser_available=browser.get("available"),
        browser_binary_downloaded=False,
        runtime_count=len(_RUNTIMES),
        active_runtime_count=sum(1 for r in _RUNTIMES.values() if r.get("state") in {"scenario_running", "step_running", "browser_ready"}),
        raw_javascript_allowed=False,
        arbitrary_desktop_control=False,
        local_only=True,
        external_api_used=False,
        external_network_used=False,
        persistent_browser_profile_used=False,
        layer42_started=False,
    )


def get_safe_live_test_metadata(runtime: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "live_test_runtime_id": runtime.get("live_test_runtime_id"),
        "scenario_id": runtime.get("scenario", {}).get("scenario_id"),
        "task_id": runtime.get("scenario", {}).get("task_id"),
        "state": runtime.get("state"),
        "allowed_origin": runtime.get("allowed_origin"),
        "viewport": runtime.get("scenario", {}).get("viewport"),
        "completed_step_count": len(runtime.get("completed_steps", [])),
        "failed_step": _redact(runtime.get("failed_step")),
        "evidence_count": len(runtime.get("evidence", [])),
        "cleanup_state": runtime.get("cleanup_state"),
        "audit_event_count": len(runtime.get("audit_events", [])),
    }
