from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import socket
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from luxcode_autonomy_permission_controller import evaluate_requested_action
from luxcode_live_app_interaction_testing import execute_live_test, get_live_testing_registry, plan_live_test
from luxcode_terminal_process_runtime import stop_terminal_process


DESKTOP_BROWSERS = ["chrome", "edge", "firefox", "yandex", "chromium_fallback"]
MOBILE_TARGETS = ["mobile_chrome", "android_emulator", "android_webview_preview", "tablet_browser", "responsive_mobile_preview"]
PLATFORM_TARGETS = ["safari", "ios_simulator"]
RESULT_STATUSES = {"passed", "failed", "blocked", "skipped", "unavailable", "timed_out", "partially_verified"}
FAILURE_CATEGORIES = {
    "browser_launch_failure",
    "browser_unavailable",
    "emulator_unavailable",
    "page_load_failure",
    "console_error",
    "network_error",
    "element_missing",
    "interaction_failure",
    "layout_overflow",
    "clipped_content",
    "overlap_detected",
    "horizontal_scroll",
    "responsive_break",
    "orientation_failure",
    "reconnect_failure",
    "timeout",
    "screenshot_failure",
    "cleanup_failure",
    "unsupported_target",
    "unknown_failure",
}
SCENARIO_IDS = {
    "page_load",
    "navigation",
    "form_input",
    "button_click",
    "stop_continue",
    "reload_state",
    "offline_reconnect",
    "responsive_layout",
    "mobile_keyboard_safe_area",
    "modal_and_overlay",
    "scroll_and_sticky_elements",
    "error_state",
    "empty_state",
    "loading_state",
    "long_text",
    "multilingual_text",
    "rtl_layout",
}
NETWORK_PROFILES = {
    "normal": {"latency_ms": 0, "offline": False, "local_only": True},
    "fast_wifi": {"latency_ms": 20, "offline": False, "local_only": True},
    "slow_wifi": {"latency_ms": 250, "offline": False, "local_only": True},
    "high_latency": {"latency_ms": 700, "offline": False, "local_only": True},
    "slow_3g_like": {"latency_ms": 1200, "offline": False, "local_only": True},
    "packet_delay": {"latency_ms": 400, "offline": False, "local_only": True},
    "temporary_offline": {"latency_ms": 0, "offline": True, "local_only": True},
    "reconnect_after_offline": {"latency_ms": 300, "offline": "reconnect", "local_only": True},
    "api_slow_response": {"latency_ms": 900, "local_fixture_delay": True, "local_only": True},
    "delayed_service_start": {"latency_ms": 0, "service_start_delay": True, "local_only": True},
}
DEVICE_PROFILES = [
    {"profile_id": "phone_320x568", "family": "phone", "width": 320, "height": 568, "device_scale_factor": 2, "touch_enabled": True, "mobile": True},
    {"profile_id": "phone_360x640", "family": "phone", "width": 360, "height": 640, "device_scale_factor": 2, "touch_enabled": True, "mobile": True},
    {"profile_id": "phone_375x667", "family": "phone", "width": 375, "height": 667, "device_scale_factor": 2, "touch_enabled": True, "mobile": True},
    {"profile_id": "phone_390x844", "family": "phone", "width": 390, "height": 844, "device_scale_factor": 3, "touch_enabled": True, "mobile": True},
    {"profile_id": "phone_412x915", "family": "phone", "width": 412, "height": 915, "device_scale_factor": 3, "touch_enabled": True, "mobile": True},
    {"profile_id": "phone_480x960", "family": "phone", "width": 480, "height": 960, "device_scale_factor": 2, "touch_enabled": True, "mobile": True},
    {"profile_id": "tablet_600x960", "family": "tablet", "width": 600, "height": 960, "device_scale_factor": 2, "touch_enabled": True, "mobile": True},
    {"profile_id": "tablet_768x1024", "family": "tablet", "width": 768, "height": 1024, "device_scale_factor": 2, "touch_enabled": True, "mobile": True},
    {"profile_id": "tablet_820x1180", "family": "tablet", "width": 820, "height": 1180, "device_scale_factor": 2, "touch_enabled": True, "mobile": True},
    {"profile_id": "tablet_1024x1366", "family": "tablet", "width": 1024, "height": 1366, "device_scale_factor": 2, "touch_enabled": True, "mobile": True},
    {"profile_id": "desktop_1024x768", "family": "desktop", "width": 1024, "height": 768, "device_scale_factor": 1, "touch_enabled": False, "mobile": False},
    {"profile_id": "desktop_1280x720", "family": "desktop", "width": 1280, "height": 720, "device_scale_factor": 1, "touch_enabled": False, "mobile": False},
    {"profile_id": "desktop_1366x768", "family": "desktop", "width": 1366, "height": 768, "device_scale_factor": 1, "touch_enabled": False, "mobile": False},
    {"profile_id": "desktop_1440x900", "family": "desktop", "width": 1440, "height": 900, "device_scale_factor": 1, "touch_enabled": False, "mobile": False},
    {"profile_id": "desktop_1920x1080", "family": "desktop", "width": 1920, "height": 1080, "device_scale_factor": 1, "touch_enabled": False, "mobile": False},
    {"profile_id": "desktop_2560x1440", "family": "desktop", "width": 2560, "height": 1440, "device_scale_factor": 1, "touch_enabled": False, "mobile": False},
]
MAX_MATRIX_CELLS = 48
_STATUS = {
    "external_api_used": False,
    "public_internet_used": False,
    "subnet_scan_used": False,
    "firewall_modified": False,
    "router_modified": False,
    "tunnel_started": False,
    "package_install_attempted": False,
    "deployment_or_github_used": False,
    "layer42_started": False,
}
_RUNTIMES: Dict[str, Dict[str, Any]] = {}


def _now() -> float:
    return round(time.time(), 6)


def _digest(value: Any, prefix: str = "luxmatrix-") -> str:
    data = json.dumps(value, sort_keys=True, default=str).encode("utf-8", "replace")
    return prefix + hashlib.sha256(data).hexdigest()[:24]


def _safe_success(**extra: Any) -> Dict[str, Any]:
    data = {"ok": True, "external_api_used": False, "public_internet_used": False, "local_first": True}
    data.update(extra)
    return data


def _safe_failure(reason: str, **extra: Any) -> Dict[str, Any]:
    data = {"ok": False, "blocked": True, "reason": reason, "external_api_used": False, "public_internet_used": False, "local_first": True}
    data.update(extra)
    return data


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): ("[redacted]" if any(token in str(k).lower() for token in ("cookie", "token", "secret", "password", "authorization")) else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value[:100]]
    if isinstance(value, str):
        if len(value) > 1200:
            return value[:1200] + "...[truncated]"
        if any(marker in value.lower() for marker in ("bearer ", "sk-", "password=", "token=")):
            return "[redacted-secret]"
    return value


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


def _known_browser_candidates() -> Dict[str, List[str]]:
    local_app = os.environ.get("LOCALAPPDATA", "")
    program_files = [os.environ.get("PROGRAMFILES", r"C:\Program Files"), os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")]
    candidates = {
        "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe", shutil.which("chrome") or ""],
        "edge": [r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", shutil.which("msedge") or ""],
        "firefox": [r"C:\Program Files\Mozilla Firefox\firefox.exe", r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe", shutil.which("firefox") or ""],
        "yandex": [str(Path(local_app) / "Yandex" / "YandexBrowser" / "Application" / "browser.exe") if local_app else "", *(str(Path(p) / "Yandex" / "YandexBrowser" / "Application" / "browser.exe") for p in program_files if p)],
        "chromium_fallback": [shutil.which("chromium") or "", shutil.which("chromium-browser") or ""],
    }
    if platform.system().lower() == "darwin":
        candidates["safari"] = ["/Applications/Safari.app/Contents/MacOS/Safari"]
    return candidates


def _detect_one_browser(family: str) -> Dict[str, Any]:
    for raw in _known_browser_candidates().get(family, []):
        if not raw:
            continue
        path = Path(raw)
        try:
            if path.exists() and path.is_file():
                return {
                    "target_id": family,
                    "browser_family": family,
                    "available": True,
                    "browser_executable": str(path),
                    "engine": "chromium_cdp" if family in {"chrome", "edge", "chromium_fallback", "yandex"} else "detected_non_cdp",
                    "fallback_evidence": False,
                    "skip_reason": "",
                }
        except OSError:
            continue
    if family == "yandex" and _detect_one_browser("chrome").get("available"):
        return {
            "target_id": "yandex",
            "browser_family": "yandex",
            "available": False,
            "browser_executable": "",
            "engine": "unavailable",
            "fallback_evidence": True,
            "fallback_family": "chrome",
            "skip_reason": "Yandex browser not installed; Chrome can provide Chromium compatibility evidence only",
        }
    return {"target_id": family, "browser_family": family, "available": False, "browser_executable": "", "engine": "unavailable", "fallback_evidence": False, "skip_reason": f"{family} not detected in known safe locations"}


def _android_state() -> Dict[str, Any]:
    adb = shutil.which("adb") or ""
    emulator = shutil.which("emulator") or ""
    return {
        "android_tooling_detected": bool(adb or emulator),
        "adb_path": adb,
        "emulator_path": emulator,
        "running_emulator_detected": False,
        "installed_by_matrix": False,
        "global_emulator_mutation": False,
        "status": "tooling_detected_execution_requires_explicit_allow" if (adb or emulator) else "unavailable",
    }


def detect_available_test_targets(requested_targets: Optional[List[str]] = None, include_mobile_previews: bool = True, include_android: bool = True) -> Dict[str, Any]:
    requested = requested_targets or (DESKTOP_BROWSERS + MOBILE_TARGETS + PLATFORM_TARGETS)
    detected: List[Dict[str, Any]] = []
    desktop = {family: _detect_one_browser(family) for family in DESKTOP_BROWSERS}
    chromium_available = any(desktop.get(f, {}).get("available") and desktop[f].get("engine") == "chromium_cdp" for f in ("chrome", "edge", "chromium_fallback", "yandex"))
    for target in requested:
        if target in desktop:
            detected.append(deepcopy(desktop[target]))
        elif target in {"mobile_chrome", "responsive_mobile_preview", "tablet_browser"}:
            detected.append({
                "target_id": target,
                "browser_family": target,
                "available": bool(include_mobile_previews and chromium_available),
                "browser_executable": next((desktop[f]["browser_executable"] for f in ("chrome", "edge", "chromium_fallback", "yandex") if desktop.get(f, {}).get("available") and desktop[f].get("engine") == "chromium_cdp"), ""),
                "engine": "chromium_cdp_mobile_emulation",
                "fallback_evidence": target != "mobile_chrome",
                "skip_reason": "" if chromium_available else "Chromium-compatible browser unavailable for responsive preview",
            })
        elif target in {"android_emulator", "android_webview_preview"}:
            state = _android_state()
            detected.append({
                "target_id": target,
                "browser_family": target,
                "available": False,
                "browser_executable": "",
                "engine": "android",
                "fallback_evidence": True,
                "skip_reason": "Android emulator execution not enabled in MVP; responsive mobile preview is fallback" if include_android else "Android target not requested",
                "android_state": state,
            })
        elif target == "safari":
            safari = _detect_one_browser("safari")
            safari["available"] = bool(platform.system().lower() == "darwin" and safari.get("available"))
            safari["skip_reason"] = "" if safari.get("available") else "Safari is only available on macOS and was not detected"
            detected.append(safari)
        elif target == "ios_simulator":
            detected.append({"target_id": target, "browser_family": target, "available": False, "browser_executable": "", "engine": "ios", "fallback_evidence": False, "skip_reason": "iOS simulator is only supported when detected on macOS; no simulator mutation performed"})
        else:
            detected.append({"target_id": target, "browser_family": target, "available": False, "browser_executable": "", "engine": "unknown", "fallback_evidence": False, "skip_reason": "unsupported target"})
    return _safe_success(targets=detected, android=_android_state(), live_testing_registry=get_live_testing_registry())


def _orientation_profile(profile: Dict[str, Any], orientation: str) -> Dict[str, Any]:
    item = deepcopy(profile)
    item["orientation"] = orientation
    if orientation == "landscape" and item["height"] > item["width"]:
        item["width"], item["height"] = item["height"], item["width"]
    if orientation == "portrait" and item["width"] > item["height"]:
        item["width"], item["height"] = item["height"], item["width"]
    return item


def _project_breakpoints(repository_root: str) -> List[int]:
    root = Path(repository_root or os.getcwd()).resolve()
    candidates = [root / "static" / "styles.css", root / "static" / "index.css", root / "static" / "index.html"]
    widths = set()
    for path in candidates:
        try:
            if path.exists() and path.is_file() and path.stat().st_size < 500_000:
                text = path.read_text(encoding="utf-8", errors="ignore")
                for match in __import__("re").finditer(r"(?i)(?:min|max)-width\s*:\s*(\d{3,4})px", text):
                    value = int(match.group(1))
                    if 280 <= value <= 3200:
                        widths.add(value)
        except OSError:
            continue
    return sorted(widths)[:12]


def _filtered_device_profiles(families: Optional[List[str]] = None, limit: int = 8, include_project_widths: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    ordered_families = families or ["phone", "tablet", "desktop"]
    allowed = set(ordered_families)
    profiles = []
    for family in ordered_families:
        profiles.extend(deepcopy(item) for item in DEVICE_PROFILES if item["family"] == family and item["family"] in allowed)
    for width in include_project_widths or []:
        profiles.append({"profile_id": f"project_{width}x800", "family": "project", "width": int(width), "height": 800, "device_scale_factor": 1, "touch_enabled": False, "mobile": width < 800, "project_breakpoint": True})
    representative: List[Dict[str, Any]] = []
    for family in ordered_families:
        first = next((item for item in profiles if item.get("family") == family), None)
        if first:
            representative.append(first)
    seen = set()
    unique = []
    for item in representative + profiles:
        key = (item["width"], item["height"], item["family"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[: max(1, min(limit, 32))]


def get_test_matrix_schema() -> Dict[str, Any]:
    return _safe_success(
        name="LuxCode Browser, Device, Screen & Network Test Matrix",
        target_families=DESKTOP_BROWSERS + MOBILE_TARGETS + PLATFORM_TARGETS,
        device_profiles=DEVICE_PROFILES,
        orientations=["portrait", "landscape"],
        color_schemes=["light", "dark"],
        network_profiles=NETWORK_PROFILES,
        scenario_ids=sorted(SCENARIO_IDS),
        result_statuses=sorted(RESULT_STATUSES),
        failure_categories=sorted(FAILURE_CATEGORIES),
        max_matrix_cells=MAX_MATRIX_CELLS,
        public_internet_allowed=False,
        subnet_scan_allowed=False,
        firewall_router_tunnel_mutation_allowed=False,
        package_install_allowed=False,
        persistent_artifacts_allowed=False,
    )


def build_test_matrix_plan(
    task_id: str = "",
    repository_root: str = "",
    working_directory: str = ".",
    base_url: str = "",
    requested_targets: Optional[List[str]] = None,
    scenario_ids: Optional[List[str]] = None,
    device_families: Optional[List[str]] = None,
    network_profiles: Optional[List[str]] = None,
    orientations: Optional[List[str]] = None,
    color_schemes: Optional[List[str]] = None,
    locale: str = "tr-TR",
    direction: str = "ltr",
    required_targets: Optional[List[str]] = None,
    service: Optional[Dict[str, Any]] = None,
    permission_profile: Optional[Dict[str, Any]] = None,
    approval_digest: str = "",
    max_cells: int = 8,
    screenshot_required: bool = True,
    console_capture_required: bool = True,
    network_capture_required: bool = True,
) -> Dict[str, Any]:
    root, root_error = _safe_path(repository_root or os.getcwd(), ".")
    if root_error:
        return _safe_failure(root_error)
    cwd, cwd_error = _safe_path(str(root), working_directory)
    if cwd_error:
        return _safe_failure(cwd_error)
    if not base_url and not service:
        return _safe_failure("base_url or task-owned service is required")
    max_cells = max(1, min(int(max_cells or 8), MAX_MATRIX_CELLS))
    scenarios = [item for item in (scenario_ids or ["page_load", "responsive_layout"]) if item in SCENARIO_IDS]
    if not scenarios:
        return _safe_failure("at least one supported scenario id is required")
    networks = [name for name in (network_profiles or ["normal"]) if name in NETWORK_PROFILES]
    if not networks:
        return _safe_failure("at least one supported network profile is required")
    chosen_orientations = [item for item in (orientations or ["portrait"]) if item in {"portrait", "landscape"}]
    schemes = [item for item in (color_schemes or ["light"]) if item in {"light", "dark"}]
    detected = detect_available_test_targets(requested_targets)
    targets = detected["targets"]
    project_breakpoints = _project_breakpoints(str(root))
    profiles = _filtered_device_profiles(device_families, limit=max_cells, include_project_widths=project_breakpoints)
    required = set(required_targets or [])
    permission = evaluate_requested_action(
        profile=permission_profile,
        task_id=task_id,
        operation="run_tests",
        target_path=str(cwd.relative_to(root)) if cwd != root else ".",
        metadata={"why_needed": "browser/device/network matrix execution", "risk_hint": "important", "validation_runs": 1},
        approval_digest=approval_digest,
        recovery_plan_available=True,
    ) if permission_profile else _safe_success(allowed=False, requires_approval=True, reason="permission profile is required")
    cells = []
    seen = set()
    for profile in profiles:
        for target in targets:
            if target["target_id"] in {"mobile_chrome", "responsive_mobile_preview", "android_webview_preview"} and profile.get("family") != "phone":
                continue
            if target["target_id"] == "tablet_browser" and profile.get("family") != "tablet":
                continue
            if target["target_id"] in DESKTOP_BROWSERS and profile.get("family") not in {"desktop", "project"}:
                continue
            for orientation in chosen_orientations:
                for scheme in schemes:
                    for network in networks:
                        device = _orientation_profile(profile, orientation)
                        key = (target["target_id"], device["width"], device["height"], orientation, scheme, network)
                        if key in seen:
                            continue
                        seen.add(key)
                        available = bool(target.get("available"))
                        skip_reason = target.get("skip_reason", "") if not available else ""
                        cell = {
                            "cell_id": _digest(key, "cell-"),
                            "target_id": target["target_id"],
                            "browser_family": target["browser_family"],
                            "browser_executable": target.get("browser_executable", ""),
                            "device_profile": device["profile_id"],
                            "viewport_width": device["width"],
                            "viewport_height": device["height"],
                            "orientation": orientation,
                            "device_scale_factor": device["device_scale_factor"],
                            "touch_enabled": bool(device["touch_enabled"]),
                            "mobile_user_agent": bool(device.get("mobile")),
                            "desktop_user_agent": not bool(device.get("mobile")),
                            "reduced_motion": True,
                            "color_scheme": scheme,
                            "locale": locale,
                            "direction": direction,
                            "network_profile": network,
                            "network_profile_config": NETWORK_PROFILES[network],
                            "scenario_ids": scenarios,
                            "availability": "available" if available else "unavailable",
                            "skip_reason": skip_reason,
                            "required": target["target_id"] in required,
                            "timeout_seconds": 45,
                            "screenshot_required": bool(screenshot_required),
                            "console_capture_required": bool(console_capture_required),
                            "network_capture_required": bool(network_capture_required),
                            "fallback_evidence": bool(target.get("fallback_evidence")),
                        }
                        cells.append(cell)
                        if len(cells) >= max_cells:
                            break
                    if len(cells) >= max_cells:
                        break
                if len(cells) >= max_cells:
                    break
            if len(cells) >= max_cells:
                break
        if len(cells) >= max_cells:
            break
    plan = {
        "matrix_runtime_id": _digest([task_id, base_url, time.time()]),
        "task_id": task_id,
        "state": "planned" if permission.get("allowed") else "approval_required",
        "repository_root": str(root),
        "working_directory": str(cwd),
        "base_url": base_url,
        "service": deepcopy(service or {}),
        "permission_profile": deepcopy(permission_profile or {}),
        "permission_decision": permission,
        "requested_targets": requested_targets or (DESKTOP_BROWSERS + ["responsive_mobile_preview", "tablet_browser", "android_emulator"]),
        "required_targets": sorted(required),
        "available_targets": [t for t in targets if t.get("available")],
        "skipped_targets": [t for t in targets if not t.get("available")],
        "project_breakpoints": project_breakpoints,
        "cells": cells,
        "cell_count": len(cells),
        "scenario_ids": scenarios,
        "created_at": _now(),
        "result_revision": 1,
        "safety": deepcopy(_STATUS),
    }
    return _safe_success(plan=plan, detected_targets=targets)


def _steps_for_cell(cell: Dict[str, Any], base_url: str) -> List[Dict[str, Any]]:
    viewport = {"width": int(cell["viewport_width"]), "height": int(cell["viewport_height"]), "mobile_emulation": bool(cell.get("mobile_user_agent"))}
    steps: List[Dict[str, Any]] = [
        {"step_id": "viewport", "action_type": "set_viewport", "viewport": viewport},
        {"step_id": "navigate", "action_type": "navigate", "target_url": base_url},
        {"step_id": "ready", "action_type": "wait_for_ready"},
    ]
    scenarios = set(cell.get("scenario_ids", []))
    if "form_input" in scenarios:
        steps.append({"step_id": "form_input", "action_type": "fill", "selector": {"type": "test_id", "value": "matrix-input"}, "value": "Lux matrix"})
    if "button_click" in scenarios:
        steps.append({"step_id": "button_click", "action_type": "click", "selector": {"type": "test_id", "value": "matrix-button"}})
        steps.append({"step_id": "button_result", "action_type": "assert_text_contains", "selector": {"type": "test_id", "value": "matrix-result"}, "expected_text": "clicked"})
    if "page_load" in scenarios:
        steps.append({"step_id": "page_title", "action_type": "assert_visible", "selector": {"type": "test_id", "value": "matrix-title"}})
    if "responsive_layout" in scenarios or "long_text" in scenarios or "rtl_layout" in scenarios:
        steps.append({"step_id": "layout", "action_type": "collect_layout_observations"})
    if cell.get("console_capture_required"):
        steps.append({"step_id": "console", "action_type": "collect_console_errors"})
    if cell.get("screenshot_required"):
        steps.append({"step_id": "screenshot", "action_type": "capture_screenshot"})
    return steps


def _failure_categories(runtime: Dict[str, Any], cell: Dict[str, Any]) -> List[str]:
    categories: List[str] = []
    if runtime.get("state") == "timed_out":
        categories.append("timeout")
    if runtime.get("state") == "scenario_failed":
        failed = str(runtime.get("failed_step", {}).get("reason", ""))
        if "selector" in failed or "element" in failed or "text_missing" in failed:
            categories.append("element_missing")
        elif "blocked_external" in failed:
            categories.append("network_error")
        else:
            categories.append("interaction_failure")
    if runtime.get("console_error_summary"):
        categories.append("console_error")
    for obs in runtime.get("layout_observations", []):
        if obs.get("horizontal_overflow"):
            categories.extend(["layout_overflow", "horizontal_scroll"])
        if obs.get("clipped_text"):
            categories.append("clipped_content")
        if obs.get("overlapping_elements"):
            categories.append("overlap_detected")
        if obs.get("offscreen_controls"):
            categories.append("responsive_break")
        if cell.get("orientation") == "portrait" and obs.get("viewport", {}).get("width", 0) > obs.get("viewport", {}).get("height", 1):
            categories.append("orientation_failure")
        if cell.get("orientation") == "landscape" and obs.get("viewport", {}).get("height", 0) > obs.get("viewport", {}).get("width", 1):
            categories.append("orientation_failure")
    if runtime.get("cleanup_state") != "cleaned":
        categories.append("cleanup_failure")
    return sorted(set(categories)) or ([] if runtime.get("state") == "scenario_passed" else ["unknown_failure"])


def _result_from_live(cell: Dict[str, Any], live_result: Dict[str, Any]) -> Dict[str, Any]:
    runtime = live_result.get("runtime", live_result)
    categories = _failure_categories(runtime, cell)
    status = "passed" if runtime.get("state") == "scenario_passed" and not categories else "failed"
    if runtime.get("state") == "timed_out":
        status = "timed_out"
    return {
        "cell_id": cell["cell_id"],
        "target_id": cell["target_id"],
        "browser_family": cell["browser_family"],
        "device_profile": cell["device_profile"],
        "viewport": {"width": cell["viewport_width"], "height": cell["viewport_height"], "orientation": cell["orientation"], "device_scale_factor": cell["device_scale_factor"]},
        "network_profile": cell["network_profile"],
        "status": status,
        "failure_categories": categories,
        "visible_text_preview": _redact(runtime.get("completed_steps", [])),
        "console_errors": _redact(runtime.get("console_error_summary", [])),
        "failed_network_requests": [],
        "timeout": runtime.get("state") == "timed_out",
        "screenshot_path": "[temporary-cleaned]" if runtime.get("evidence") else "",
        "screenshot_temporary": True,
        "screenshot_cleaned": runtime.get("cleanup_result", {}).get("temporary_artifacts_removed") is True,
        "layout_observations": _redact(runtime.get("layout_observations", [])),
        "interaction_observations": {"completed_steps": runtime.get("completed_steps", []), "failed_step": runtime.get("failed_step")},
        "cleanup_result": runtime.get("cleanup_result", {}),
        "temporary_profile_created": bool(runtime.get("browser", {}).get("temporary_profile")),
        "temporary_profile_removed": runtime.get("cleanup_result", {}).get("temporary_artifacts_removed") is True,
        "live_test_runtime_id": runtime.get("live_test_runtime_id"),
    }


def execute_test_matrix(plan: Dict[str, Any], approval_digest: str = "", retry_cell_ids: Optional[List[str]] = None, resume: bool = True) -> Dict[str, Any]:
    if not plan or "matrix_runtime_id" not in plan:
        return _safe_failure("valid test matrix plan is required")
    runtime = deepcopy(plan)
    runtime["started_at"] = _now()
    runtime.setdefault("results", [])
    runtime["state"] = "running"
    retry_set = set(retry_cell_ids or [])
    completed = {item.get("cell_id") for item in runtime.get("results", []) if item.get("status") == "passed"} if resume else set()
    if not runtime.get("permission_decision", {}).get("allowed"):
        runtime["state"] = "approval_required"
        _RUNTIMES[runtime["matrix_runtime_id"]] = runtime
        return _safe_success(runtime=_redact(runtime))
    base_url = runtime.get("base_url", "")
    service = runtime.get("service") or None
    for cell in runtime.get("cells", []):
        if cell["cell_id"] in completed and cell["cell_id"] not in retry_set:
            continue
        if cell.get("availability") != "available":
            runtime["results"].append({
                "cell_id": cell["cell_id"],
                "target_id": cell["target_id"],
                "browser_family": cell["browser_family"],
                "status": "unavailable",
                "failure_categories": ["browser_unavailable" if "android" not in cell["target_id"] else "emulator_unavailable"],
                "skip_reason": cell.get("skip_reason", "unavailable"),
                "required": bool(cell.get("required")),
            })
            continue
        live_scenario = {
            "scenario_id": f"matrix_{cell['cell_id']}",
            "task_id": runtime.get("task_id", ""),
            "scenario_name": f"Matrix {cell['target_id']} {cell['device_profile']} {cell['network_profile']}",
            "base_url": base_url,
            "allowed_origin": base_url,
            "viewport": {"width": int(cell["viewport_width"]), "height": int(cell["viewport_height"]), "mobile_emulation": bool(cell.get("mobile_user_agent"))},
            "headless": True,
            "per_step_timeout_seconds": 6,
            "scenario_timeout_seconds": int(cell.get("timeout_seconds", 45)),
            "evidence_policy": {"screenshots": bool(cell.get("screenshot_required")), "structured": True},
            "steps": _steps_for_cell(cell, base_url),
        }
        if cell["network_profile"] in {"temporary_offline", "reconnect_after_offline"}:
            live_scenario["network_degradation"] = {"simulated_locally": True, "note": "MVP records offline/reconnect intent without public network dependency"}
        live_plan = plan_live_test(
            scenario=live_scenario,
            repository_root=runtime["repository_root"],
            working_directory=".",
            permission_profile=runtime.get("permission_profile"),
            service=service,
            approval_digest=approval_digest,
        )
        if not live_plan.get("ok"):
            runtime["results"].append({"cell_id": cell["cell_id"], "target_id": cell["target_id"], "status": "blocked", "failure_categories": ["browser_launch_failure"], "diagnosis": live_plan})
            continue
        live_result = execute_live_test(live_plan["plan"], approval_digest=approval_digest)
        runtime["results"].append(_result_from_live(cell, live_result))
    comparison = compare_test_matrix_results(runtime.get("results", []), plan=runtime)
    summary = summarize_test_matrix(runtime.get("results", []), plan=runtime)
    runtime["comparison"] = comparison.get("comparison", comparison)
    runtime["summary"] = summary.get("summary", summary)
    runtime["state"] = runtime["summary"].get("overall_status", "completed")
    runtime["ended_at"] = _now()
    _RUNTIMES[runtime["matrix_runtime_id"]] = runtime
    return _safe_success(runtime=_redact(runtime))


def compare_test_matrix_results(results: List[Dict[str, Any]], plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    by_category: Dict[str, int] = {}
    by_target: Dict[str, Dict[str, int]] = {}
    orientation_failures: Dict[str, int] = {}
    for result in results or []:
        target = str(result.get("target_id", "unknown"))
        status = str(result.get("status", "unknown"))
        by_target.setdefault(target, {}).setdefault(status, 0)
        by_target[target][status] += 1
        for category in result.get("failure_categories", []):
            by_category[category] = by_category.get(category, 0) + 1
        viewport = result.get("viewport", {})
        if "orientation_failure" in result.get("failure_categories", []):
            orientation = str(viewport.get("orientation", "unknown"))
            orientation_failures[orientation] = orientation_failures.get(orientation, 0) + 1
    missing_required = [item for item in results or [] if item.get("required") and item.get("status") in {"unavailable", "skipped", "blocked"}]
    return _safe_success(comparison={"by_target": by_target, "failure_categories": by_category, "orientation_failures": orientation_failures, "missing_required": missing_required, "compatible_targets": [t for t, counts in by_target.items() if counts.get("passed")]})


def summarize_test_matrix(results: List[Dict[str, Any]], plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    counts = {status: 0 for status in sorted(RESULT_STATUSES)}
    skipped_reasons: Dict[str, str] = {}
    failures: List[Dict[str, Any]] = []
    for result in results or []:
        status = str(result.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
        if status in {"failed", "blocked", "timed_out"}:
            failures.append(_redact(result))
        if status in {"skipped", "unavailable"}:
            skipped_reasons[str(result.get("target_id", result.get("cell_id")))] = str(result.get("skip_reason", ""))
    total = len(results or [])
    required_unavailable = [item for item in results or [] if item.get("required") and item.get("status") in {"unavailable", "skipped", "blocked"}]
    if counts.get("failed") or counts.get("timed_out") or counts.get("blocked"):
        overall = "failed"
    elif required_unavailable or counts.get("unavailable") or counts.get("skipped"):
        overall = "partially_verified"
    elif total and counts.get("passed") == total:
        overall = "passed"
    else:
        overall = "partially_verified"
    safe_metadata = {
        "matrix_plan_digest": _digest(plan or {}, "digest-") if plan else "",
        "requested_targets": (plan or {}).get("requested_targets", []),
        "available_targets": [t.get("target_id") for t in (plan or {}).get("available_targets", [])],
        "skipped_targets": [t.get("target_id") for t in (plan or {}).get("skipped_targets", [])],
        "summary_counts": counts,
        "failure_categories": sorted({cat for item in results or [] for cat in item.get("failure_categories", [])}),
        "scenario_ids": (plan or {}).get("scenario_ids", []),
        "viewport_device_metadata": [{"cell_id": r.get("cell_id"), "viewport": r.get("viewport")} for r in results or []],
        "network_profile_names": sorted({str(r.get("network_profile", "")) for r in results or [] if r.get("network_profile")}),
        "task_id": (plan or {}).get("task_id", ""),
        "result_revision": (plan or {}).get("result_revision", 1),
    }
    return _safe_success(summary={"overall_status": overall, "total": total, "counts": counts, "failures": failures[:20], "skipped_target_reasons": skipped_reasons, "safe_persistence_metadata": safe_metadata})


def get_test_matrix_status() -> Dict[str, Any]:
    return _safe_success(
        runtime_count=len(_RUNTIMES),
        active_runtime_count=sum(1 for item in _RUNTIMES.values() if item.get("state") == "running"),
        browser_detection="known_safe_paths_only",
        android=_android_state(),
        temporary_profiles_only=True,
        screenshots_temporary_only=True,
        cookies_persisted=False,
        auth_tokens_persisted=False,
        raw_page_content_persisted=False,
        full_console_logs_persisted=False,
        **_STATUS,
    )


def get_safe_test_matrix_metadata(runtime: Dict[str, Any]) -> Dict[str, Any]:
    summary = runtime.get("summary", {})
    return {
        "matrix_runtime_id": runtime.get("matrix_runtime_id"),
        "task_id": runtime.get("task_id"),
        "state": runtime.get("state"),
        "matrix_plan_digest": _digest(runtime.get("cells", []), "digest-"),
        "requested_targets": runtime.get("requested_targets", []),
        "available_targets": [item.get("target_id") for item in runtime.get("available_targets", [])],
        "skipped_targets": [item.get("target_id") for item in runtime.get("skipped_targets", [])],
        "summary_counts": summary.get("counts", {}),
        "failure_categories": summary.get("safe_persistence_metadata", {}).get("failure_categories", []),
        "scenario_ids": runtime.get("scenario_ids", []),
        "network_profile_names": summary.get("safe_persistence_metadata", {}).get("network_profile_names", []),
        "result_revision": runtime.get("result_revision", 1),
    }
