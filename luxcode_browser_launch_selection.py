from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import urllib.error
import urllib.request


BROWSER_FAMILY_ALIASES = {
    "googlechrome": "chrome",
    "google_chrome": "chrome",
    "msedge": "edge",
    "chromium-browser": "chromium",
    "chromiumfallback": "chromium_fallback",
}
SUPPORTED_FAMILIES = ["chrome", "edge", "firefox", "yandex", "chromium", "chromium_fallback", "safari", "unknown"]
CHROMIUM_FAMILIES = {"chrome", "edge", "yandex", "chromium", "chromium_fallback"}
SAFE_STATUS = {"scope_expansion_blocked": True, "external_api_used": False, "local_first": True}
RUNTIME_REGISTRY: Dict[str, Dict[str, Any]] = {}
ACTIVE_LAUNCHES: Dict[str, Dict[str, Any]] = {}
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_STARTUP_TIMEOUT_SECONDS = 12
MIN_PORT = 1025


def _safe_success(**extra: Any) -> Dict[str, Any]:
    return {"ok": True, **SAFE_STATUS, **extra}


def _safe_failure(message: str, **extra: Any) -> Dict[str, Any]:
    return {"ok": False, "blocked": True, "reason": message, **SAFE_STATUS, **extra}


def _normalize_family(value: str) -> str:
    text = re.sub(r"\s+", "", str(value or "").strip().lower())
    if not text:
        return "unknown"
    text = BROWSER_FAMILY_ALIASES.get(text, text)
    return text if text in SUPPORTED_FAMILIES else "unknown"


def normalize_browser_family(value: str) -> Dict[str, Any]:
    family = _normalize_family(value)
    return _safe_success(input=value, normalized_family=family, supported=family != "unknown")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def get_browser_launch_schema() -> Dict[str, Any]:
    return _safe_success(
        name="LuxCode Browser Family-Specific Launch Selection",
        supported_families=SUPPORTED_FAMILIES,
        exact_selection_required=True,
        fallback_policy_supported=True,
        identity_verification_required=True,
        controlled_url_required=True,
        temporary_profile_required=True,
        structured_args_only=True,
        shell_execution_allowed=False,
    )


def _safe_path(path: str) -> Tuple[Optional[str], str]:
    try:
        value = str(path or "").strip()
        if not value:
            return None, ""
        candidate = Path(value).resolve()
    except Exception as exc:
        return None, f"path resolution failed: {exc}"
    if not candidate.exists() or not candidate.is_file():
        return None, "path does not exist or is not a file"
    return str(candidate), ""


def _controlled_url_allowed(url: str) -> bool:
    text = str(url or "").strip()
    if text == "about:blank":
        return True
    if re.match(r"^http://(127\.0\.0\.1|localhost|\[::1\])(?::\d{1,5})?(?:/.*)?$", text):
        return True
    return False


def _known_safe_candidate_paths() -> set[str]:
    safe: set[str] = set()
    for values in _candidate_paths().values():
        for raw in values:
            resolved, _error = _safe_path(raw)
            if resolved:
                safe.add(str(Path(resolved).resolve()).lower())
    return safe


def _candidate_matches_safe_detection(path: str) -> bool:
    resolved, _error = _safe_path(path)
    if not resolved:
        return False
    return str(Path(resolved).resolve()).lower() in _known_safe_candidate_paths()


def _candidate_paths() -> Dict[str, List[str]]:
    local_app = os.environ.get("LOCALAPPDATA", "")
    program_files = [
        os.environ.get("PROGRAMFILES", r"C:\\Program Files"),
        os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)"),
    ]
    local_program_files = os.environ.get("PROGRAMFILES", "").strip()
    paths = {
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.join(local_app, r"Google\\Chrome\\Application\\chrome.exe") if local_app else "",
            os.path.join(local_program_files, r"Google\\Chrome\\Application\\chrome.exe") if local_program_files else "",
        ],
        "edge": [
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            os.path.join(local_app, r"Microsoft\\Edge\\Application\\msedge.exe") if local_app else "",
        ],
        "firefox": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            os.path.join(local_app, r"Mozilla Firefox\\firefox.exe") if local_app else "",
        ],
        "yandex": [
            os.path.join(local_app, r"Yandex\\YandexBrowser\\Application\\browser.exe") if local_app else "",
            r"C:\Program Files\Yandex\YandexBrowser\Application\browser.exe",
            r"C:\Program Files (x86)\Yandex\YandexBrowser\Application\browser.exe",
        ],
        "chromium": [
            r"C:\Program Files\Chromium\Application\chrome.exe",
            r"C:\Program Files\Chromium\chrome.exe",
            os.path.join(local_app, r"Chromium\\Application\\chrome.exe") if local_app else "",
        ],
    }
    for family, values in paths.items():
        cleaned = []
        for item in values:
            if item:
                cleaned.append(os.path.normpath(item))
        if not cleaned and family == "chrome":
            cleaned.append("chrome")
        paths[family] = cleaned
    if os.name != "nt":
        paths["chrome"] = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium-browser"]
        paths["edge"] = ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
        paths["firefox"] = ["/Applications/Firefox.app/Contents/MacOS/firefox", "/usr/bin/firefox"]
        paths["yandex"] = ["/Applications/Yandex.app/Contents/MacOS/Yandex"]
        paths["chromium"] = ["/Applications/Chromium.app/Contents/MacOS/Chromium", "/usr/bin/chromium-browser"]
        paths["safari"] = ["/Applications/Safari.app/Contents/MacOS/Safari"]
    return paths


def _safe_version_digest(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:20]


def _is_safe_path(path: Path) -> bool:
    return path.exists() and path.is_file() and bool(path.suffix.lower())


def detect_browser_executables(repository_root: str = "") -> Dict[str, Any]:
    runtime: Dict[str, Any] = {"request_id": _safe_version_digest(time.time()), "request_root": repository_root or str(Path.cwd())}
    candidates = _candidate_paths()
    detected: Dict[str, Any] = {}
    for family, paths in candidates.items():
        family_entries = []
        for raw in paths:
            if not raw:
                continue
            path, error = _safe_path(raw)
            if not path:
                continue
            family_entries.append(
                {
                    "path": path,
                    "available": True,
                    "normalized": path,
                    "engine": "chromium_cdp" if family in {"chrome", "edge", "yandex", "chromium", "chromium_fallback"} else "native",
                    "reason": "",
                }
            )
        if not family_entries and family == "safari" and os.name == "darwin":
            safari_path = candidates.get("safari", [])[0]
            path, error = _safe_path(safari_path)
            if path:
                family_entries.append({"path": path, "available": True, "normalized": path, "engine": "native", "reason": ""})
        detected[family] = {
            "family": family,
            "candidates": family_entries,
            "available": any(item["available"] for item in family_entries),
            "first_available": family_entries[0]["normalized"] if family_entries else "",
            "fallback_allowed": family != "unknown",
        }
    runtime["candidates"] = detected
    return _safe_success(runtime=runtime, detected=detected)


def _pick_best_family_for_fallback(requested_family: str, detected: Dict[str, Any], fallback_policy: Optional[Dict[str, Any]]) -> Tuple[bool, str, Dict[str, Any], str]:
    if requested_family == "chromium_fallback":
        if not bool(fallback_policy.get("allow_fallback") if isinstance(fallback_policy, dict) else bool(fallback_policy)):
            return False, "", {}, "fallback disabled by policy"
        allowed = []
        for candidate in ("chromium", "chrome", "edge"):
            info = detected.get(candidate, {})
            if info.get("available"):
                for item in info.get("candidates", []):
                    if item.get("available"):
                        return True, candidate, item, "fallback to chromium-family candidate"
                allowed.append(candidate)
        if allowed:
            return False, "", {}, "chromium candidates unavailable"
        return False, "", {}, "no fallback candidates available"
    if requested_family in {"chrome", "edge", "firefox", "yandex"} and detected.get(requested_family, {}).get("available"):
        info = detected.get(requested_family, {})
        if info.get("candidates"):
            return True, requested_family, info["candidates"][0], "exact family available"
        return False, "", {}, "requested family detected but candidate list empty"
    return False, "", {}, "requested family unavailable"


def select_browser_executable(
    requested_browser_family: str,
    detected_candidates: Dict[str, Any],
    fallback_policy: Optional[Dict[str, Any]] = None,
    task_authority: str = "",
    matrix_target_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    requested = _normalize_family(requested_browser_family)
    if requested == "unknown":
        return _safe_failure("unknown family", requested_family=requested_browser_family)
    detected = detected_candidates if isinstance(detected_candidates, dict) else {}
    if task_authority and not str(task_authority).strip():
        return _safe_failure("empty authority provided")
    if task_authority:
        task_authority = task_authority.strip()
    if requested in {"chrome", "edge", "firefox", "yandex", "chromium"}:
        family_info = detected.get(requested, {})
        if not family_info.get("available"):
            return _safe_failure(
                "requested exact family unavailable",
                requested_family=requested,
                launch_allowed=False,
                launch_reason="exact target missing",
                exact_match=False,
                fallback_used=False,
            )
        entries = family_info.get("candidates") or []
        if not entries:
            return _safe_failure("requested executable list empty", requested_family=requested)
        if not _candidate_matches_safe_detection(entries[0].get("path", "")):
            return _safe_failure("selected executable is not a safe detected browser candidate", requested_family=requested, launch_allowed=False)
        return _safe_success(
            requested_family=requested,
            selected_family=requested,
            selected_executable=entries[0]["path"],
            executable_digest=_safe_version_digest(entries[0]["path"]),
            exact_match=True,
            fallback_used=False,
            fallback_family="",
            selection_reason="exact selected from detected candidate",
            verification_required=True,
            launch_allowed=True,
            blocked_reason="",
            matrix_target_metadata=matrix_target_metadata or {},
            task_authority=bool(task_authority),
        )
    found, selected_family, selected_item, reason = _pick_best_family_for_fallback(requested, detected, fallback_policy or {})
    if found:
        if not _candidate_matches_safe_detection(selected_item.get("path", "")):
            return _safe_failure("fallback executable is not a safe detected browser candidate", requested_family=requested, launch_allowed=False)
        return _safe_success(
            requested_family=requested,
            selected_family=selected_family,
            selected_executable=selected_item["path"],
            executable_digest=_safe_version_digest(selected_item["path"]),
            exact_match=selected_family == requested,
            fallback_used=(selected_family != requested),
            fallback_family=(selected_family if selected_family != requested else ""),
            selection_reason=reason,
            verification_required=True,
            launch_allowed=True,
            blocked_reason="",
            matrix_target_metadata=matrix_target_metadata or {},
            task_authority=bool(task_authority),
        )
    return _safe_failure(
        reason,
        requested_family=requested,
        exact_match=False,
        fallback_used=False,
        fallback_family="",
        selection_reason=reason,
        verification_required=True,
        launch_allowed=False,
        blocked_reason=reason,
        matrix_target_metadata=matrix_target_metadata or {},
    )


def _build_browser_args(family: str, executable: str, profile_dir: Path, download_dir: Path, port: int, controlled_url: str, headless: bool = True, extra_args: Optional[List[str]] = None) -> List[str]:
    args = [executable]
    if family in CHROMIUM_FAMILIES:
        base = [
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
        ]
        if headless:
            base.extend(["--headless=new"])
        if port:
            base.append(f"--remote-debugging-port={port}")
        target = controlled_url or "about:blank"
        return [*args, *base, *([f"--window-size=1366,768"] if not headless else []), target]
    if family == "firefox":
        base = [executable, "-start-debugger-server", str(port) if port else "0"]
        if headless:
            base.append("-headless")
        if controlled_url:
            base.extend(["-new-window", controlled_url])
        return [*base]
    return [executable, "--version"]


def _wait_for_ready_port(port: int, timeout: float = DEFAULT_STARTUP_TIMEOUT_SECONDS) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise TimeoutError("browser debug port not ready")


def _wait_for_debug_version(port: int, timeout: float = DEFAULT_STARTUP_TIMEOUT_SECONDS) -> Dict[str, Any]:
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.0) as response:
                data = json.loads(response.read().decode("utf-8"))
                if isinstance(data, dict) and data.get("webSocketDebuggerUrl"):
                    return data
                last_error = "missing_websocket_debugger_url"
        except Exception as exc:
            last_error = type(exc).__name__
        time.sleep(0.1)
    raise TimeoutError(f"browser debug endpoint not ready: {last_error}")


def _query_debug_version(port: int) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.5) as response:
            data = json.loads(response.read().decode("utf-8"))
            return {
                "observed_product": str(data.get("Browser", "")),
                "observed_product_version": str(data.get("Protocol-Version", "")),
            }
    except (OSError, urllib.error.URLError, ValueError):
        return {}


def _probe_version(path: str) -> str:
    try:
        proc = subprocess.run([path, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", timeout=2, shell=False)
        return (proc.stdout or "").strip().splitlines()[0] if proc.stdout else ""
    except Exception:
        return ""


def _child_pids(parent_pid: int) -> List[int]:
    if os.name != "nt":
        return []
    try:
        proc = subprocess.run(
            ["wmic", "process", "where", f"ParentProcessId={int(parent_pid)}", "get", "ProcessId"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            errors="replace",
            timeout=2,
            shell=False,
        )
    except Exception:
        return []
    pids: List[int] = []
    for line in (proc.stdout or "").splitlines():
        text = line.strip()
        if text.isdigit():
            pids.append(int(text))
    return pids


def _detect_family_from_identity(payload: Dict[str, Any], requested: str) -> str:
    executable_path = str(payload.get("observed_executable") or "").replace("\\", "/").lower()
    basename = str(payload.get("observed_executable_basename") or "").lower()
    if "/yandex/" in executable_path or "/yandexbrowser/" in executable_path:
        return "yandex"
    if "msedge" in basename or "/microsoft/edge/" in executable_path:
        return "edge"
    if "firefox" in basename or "/mozilla firefox/" in executable_path:
        return "firefox"
    if "chrome" in basename or "/google/chrome/" in executable_path:
        return "chrome"
    family = (payload.get("observed_product") or basename).lower()
    if "chrome" in family and "edg" not in family and "yandex" not in family:
        return "chrome"
    if "edge" in family:
        return "edge"
    if "yandex" in family:
        return "yandex"
    if "firefox" in family:
        return "firefox"
    if requested in CHROMIUM_FAMILIES:
        return requested
    return requested


def build_browser_launch_request(
    task_id: str,
    target_id: str = "",
    requested_browser_family: str = "chrome",
    selected_family: str = "",
    selected_executable: str = "",
    executable_digest: str = "",
    launch_args: Optional[List[str]] = None,
    temporary_profile_dir: str = "",
    remote_debugging_port: int = 0,
    viewport: Optional[Dict[str, Any]] = None,
    user_agent: str = "",
    device_scale_factor: float = 1.0,
    touch: bool = False,
    color_scheme: str = "light",
    locale: str = "en-US",
    startup_timeout: int = DEFAULT_STARTUP_TIMEOUT_SECONDS,
    page_timeout: int = 30,
    cleanup_timeout: int = 10,
    expected_identity: str = "",
    authority_digest: str = "",
    fallback_policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    requested = _normalize_family(requested_browser_family)
    normalized_selected = _normalize_family(selected_family) if selected_family else requested
    if not requested or requested == "unknown":
        return _safe_failure("invalid requested browser family")
    if selected_executable:
        resolved, reason = _safe_path(selected_executable)
        if not resolved:
            return _safe_failure(f"invalid selected executable: {reason}", requested_family=requested)
        if not _candidate_matches_safe_detection(resolved):
            return _safe_failure("selected executable is not a safe detected browser candidate", requested_family=requested)
        selected_executable = resolved
    if remote_debugging_port and not (MIN_PORT <= remote_debugging_port <= 65535):
        return _safe_failure("invalid debug port", requested_family=requested)
    if not temporary_profile_dir:
        temporary_profile_dir = ""
    controlled_url = expected_identity or "about:blank"
    if not _controlled_url_allowed(controlled_url):
        return _safe_failure("controlled URL must be about:blank or localhost", requested_family=requested)
    return _safe_success(
        task_id=task_id,
        target_id=target_id,
        requested_browser_family=requested,
        selected_browser_family=normalized_selected,
        selected_executable=selected_executable,
        executable_digest=executable_digest or _safe_version_digest(selected_executable or ""),
        launch_args=launch_args or [],
        temporary_profile_dir=temporary_profile_dir,
        remote_debugging_port=int(remote_debugging_port),
        viewport=viewport or {"width": 1366, "height": 768, "mobile": False},
        user_agent=user_agent,
        device_scale_factor=float(device_scale_factor),
        touch=bool(touch),
        color_scheme=color_scheme,
        locale=locale,
        startup_timeout=int(startup_timeout),
        page_timeout=int(page_timeout),
        cleanup_timeout=int(cleanup_timeout),
        expected_identity=expected_identity,
        authority_digest=authority_digest,
        fallback_policy=fallback_policy or {},
        controlled_url=controlled_url,
        launch_allowed=True,
        verification_required=True,
        controlled_launch_allowed=True,
        safe_payload_only=True,
    )


def launch_selected_browser(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload or {}
    requested = _normalize_family(data.get("requested_browser_family", ""))
    selected = _normalize_family(data.get("selected_browser_family", requested))
    executable = str(data.get("selected_executable") or "").strip()
    authority_digest = str(data.get("authority_digest", "")).strip()
    controlled_url = str(data.get("controlled_url") or data.get("expected_identity") or data.get("controlled_launch_url", "about:blank"))
    if not _controlled_url_allowed(controlled_url):
        return _safe_failure("controlled URL must be about:blank or localhost", requested_family=requested, launch_allowed=False)
    if not authority_digest and requested in {"chrome", "edge", "firefox", "yandex", "chromium", "chromium_fallback"}:
        return _safe_failure("explicit authority token required", requested_family=requested, launch_allowed=False)
    if not executable:
        return _safe_failure("no selected executable provided", requested_family=requested, launch_allowed=False)
    resolved, error = _safe_path(executable)
    if not resolved:
        return _safe_failure(f"invalid executable: {error}", requested_family=requested, launch_allowed=False)
    if not _candidate_matches_safe_detection(resolved):
        return _safe_failure("selected executable is not a safe detected browser candidate", requested_family=requested, launch_allowed=False)
    port = int(data.get("remote_debugging_port") or 0)
    if not (0 <= port <= 65535):
        return _safe_failure("invalid remote_debugging_port", requested_family=requested)
    if selected in CHROMIUM_FAMILIES and not port:
        port = _free_port()
    try:
        profile_root = Path(data.get("temporary_profile_dir") or tempfile.mkdtemp(prefix="luxcode-browser-launch-"))
        profile_root.mkdir(parents=True, exist_ok=True)
        profile_dir = profile_root / "profile"
        download_dir = profile_root / "downloads"
        profile_dir.mkdir(exist_ok=True)
        download_dir.mkdir(exist_ok=True)
    except Exception as exc:
        return _safe_failure(f"profile creation failed: {type(exc).__name__}", requested_family=requested, launch_allowed=False)
    runtime_id = f"bls-{int(time.time() * 1000)}-{_safe_version_digest(resolved)}"
    args = data.get("launch_args") or []
    if not isinstance(args, list):
        args = []
    extra = [str(item) for item in args if str(item).strip()]
    if any(token in "\n\0\r" for token in " ".join(extra)):
        return _safe_failure("unsafe launch argument values", runtime_id=runtime_id, launch_allowed=False)
    launch_args = _build_browser_args(selected, resolved, profile_dir, download_dir, port, controlled_url, bool(data.get("headless", True)), extra)
    try:
        proc = subprocess.Popen(
            launch_args,
            cwd=str(Path.cwd()),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            shell=False,
            text=False,
        )
    except Exception as exc:
        return _safe_failure(f"browser start failed: {type(exc).__name__}", runtime_id=runtime_id, launch_allowed=False)
    effective_port = port
    if effective_port:
        try:
            _wait_for_ready_port(effective_port, timeout=DEFAULT_STARTUP_TIMEOUT_SECONDS)
            _wait_for_debug_version(effective_port, timeout=DEFAULT_STARTUP_TIMEOUT_SECONDS)
        except Exception as exc:
            try:
                proc.terminate()
            except Exception:
                pass
            return _safe_failure(f"browser launch did not become ready: {type(exc).__name__}", runtime_id=runtime_id, launch_allowed=False)

    debug_info = _query_debug_version(effective_port) if effective_port else {}
    version_line = _probe_version(resolved)
    identity = {
        "selected_executable": resolved,
        "selected_executable_basename": Path(resolved).name,
        "requested_family": requested,
        "selected_family": selected,
        "observed_executable": str(resolved),
        "observed_product": debug_info.get("observed_product", version_line or "unknown"),
        "observed_version": str(debug_info.get("observed_product_version") or version_line),
    }
    exact = selected == requested
    mismatch = False
    reason = ""
    if requested in {"chrome", "edge", "firefox", "yandex", "chromium", "chromium_fallback"} and not exact and requested != "chromium_fallback":
        mismatch = True
        reason = f"requested {requested} but launched {selected}"
    if exact:
        observed = (debug_info.get("observed_product") or version_line or "").lower()
        if requested == "edge" and "edge" not in observed and "chrome" in observed:
            mismatch = True
            reason = "product mismatch for edge"
        if requested == "yandex" and "yandex" not in observed and "chrome" not in observed:
            mismatch = True
            reason = "product mismatch for yandex"
    RUNTIME_REGISTRY[runtime_id] = {
        "runtime_id": runtime_id,
        "task_id": str(data.get("task_id") or ""),
        "target_id": str(data.get("target_id") or ""),
        "pid": proc.pid,
        "parent_pid": proc.pid,
        "child_pids": _child_pids(proc.pid),
        "process": proc,
        "process_path": resolved,
        "profile_root": str(profile_root),
        "temporary_profile": True,
        "started_at": time.time(),
        "requested_family": requested,
        "selected_family": selected,
        "selected_executable": resolved,
        "launch_args": launch_args,
        "remote_debugging_port": effective_port,
        "identity_required": bool(data.get("verification_required", True)),
        "mismatch": mismatch,
        "mismatch_reason": reason,
        "identity": identity,
        "task_owned": True,
        "cleanup_timeout": int(data.get("cleanup_timeout") or 8),
        "fallback_used": selected != requested,
        "exact_match": exact,
    }
    return _safe_success(
        runtime_id=runtime_id,
        pid=proc.pid,
        started_at=RUNTIME_REGISTRY[runtime_id]["started_at"],
        selected_family=selected,
        selected_executable=resolved,
        temporary_profile_dir=str(profile_root),
        temp_root=str(profile_root),
        remote_debugging_port=effective_port,
        identity=identity,
        exact_match=exact,
        fallback_used=selected != requested,
        launch_allowed=True,
        mismatch=mismatch,
        mismatch_reason=reason,
        launched=True,
    )


def verify_launched_browser_identity(
    runtime_id: str,
    observed_product: Optional[str] = None,
    observed_executable: Optional[str] = None,
    expected_identity: Optional[str] = None,
) -> Dict[str, Any]:
    runtime = RUNTIME_REGISTRY.get(str(runtime_id), {})
    if not runtime:
        return _safe_failure("runtime_id not found")
    version = observed_product or (runtime.get("identity") or {}).get("observed_product", "")
    executable = observed_executable or (runtime.get("identity") or {}).get("observed_executable", "")
    expected_identity = str(expected_identity or runtime.get("requested_family") or "")
    detected_family = _detect_family_from_identity(
        {
            "observed_product": version,
            "observed_executable": executable,
            "observed_executable_basename": Path(executable).name if executable else "",
        },
        expected_identity,
    )
    mismatch = runtime.get("exact_match") is False and expected_identity not in {"chromium_fallback", "unknown"} and runtime["selected_family"] != expected_identity
    if not mismatch and expected_identity == runtime.get("selected_family") and expected_identity == detected_family:
        pass
    if expected_identity in {"chrome", "edge", "firefox", "yandex", "chromium"} and detected_family != expected_identity:
        mismatch = True
    reason = ""
    if mismatch:
        reason = f"expected {expected_identity} but observed {detected_family}"
    return _safe_success(
        runtime_id=runtime_id,
        requested_family=expected_identity,
        launched_family=runtime.get("selected_family", ""),
        observed_family=detected_family,
        observed_identity=version,
        observed_executable=executable,
        selected_executable=runtime.get("selected_executable", ""),
        exact_match=not mismatch,
        mismatch_detected=mismatch,
        mismatch_reason=reason,
    )


def terminate_selected_browser(runtime_id: str, reason: str = "user_requested") -> Dict[str, Any]:
    runtime = RUNTIME_REGISTRY.get(str(runtime_id))
    if not runtime:
        return _safe_failure("runtime_id not found")
    proc = runtime.get("process")
    cleaned = False
    cleanup_error = ""
    pid = runtime.get("pid")
    if proc:
        try:
            if proc.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/T", "/F", "/PID", str(int(pid))], check=False, shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    proc.wait(timeout=float(runtime.get("cleanup_timeout") or 3))
                else:
                    proc.terminate()
                    try:
                        proc.wait(timeout=float(runtime.get("cleanup_timeout") or 3))
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=3)
        except Exception as exc:
            cleanup_error = f"{type(exc).__name__}: {exc}"
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(int(pid))], check=False, shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    profile_root = runtime.get("profile_root")
    profile_removed = False
    if profile_root:
        try:
            shutil.rmtree(profile_root, ignore_errors=True)
            profile_removed = not Path(profile_root).exists()
        except Exception as exc:
            cleanup_error = f"{cleanup_error}; {type(exc).__name__}".strip("; ")
    cleaned = not cleanup_error
    RUNTIME_REGISTRY.pop(str(runtime_id), None)
    return _safe_success(
        runtime_id=runtime_id,
        terminated=True,
        reason=reason,
        pid=pid,
        temporary_profile_removed=profile_removed if profile_root else True,
        cleanup_error=cleanup_error,
        task_owned=True,
    )


def summarize_browser_launch_result(runtime: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_success(
        runtime_id=runtime.get("runtime_id") if isinstance(runtime, dict) else "",
        request=runtime.get("request", {}),
        result=runtime.get("result", {}),
        status=runtime.get("status", "unknown"),
        safety={"task_owned": True, "temporary_profile": True, "only_structured_args": True, "shell_false": True},
    )


def get_browser_launch_status() -> Dict[str, Any]:
    return _safe_success(
        runtime_count=len(RUNTIME_REGISTRY),
        active_runtime_count=sum(1 for item in RUNTIME_REGISTRY.values() if item.get("process") is not None),
        task_owned_count=len(RUNTIME_REGISTRY),
        browser_launch_profile_required=True,
        temporary_profile_required=True,
        controlled_url_required=True,
        external_api_used=False,
        public_internet_used=False,
    )
