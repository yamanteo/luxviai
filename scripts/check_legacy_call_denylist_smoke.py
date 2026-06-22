from __future__ import annotations

import argparse
import http.client
import json
import socket
import subprocess
import random
import string
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Result:
    name: str
    ok: bool
    detail: str


def now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def parse_base_url(raw: str) -> tuple[str, int, bool]:
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("base-url must start with http or https")
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return host, port, parsed.scheme == "https"


def request(host: str, port: int, method: str, path: str, use_https: bool = False, timeout: float = 5.0) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPSConnection(host, port, timeout=timeout) if use_https else http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request(method, path, headers={"Connection": "close"})
        resp = conn.getresponse()
        headers = {k.lower(): v for k, v in resp.getheaders()}
        body = resp.read()
        return resp.status, headers, body
    except (ConnectionRefusedError, socket.gaierror) as exc:
        raise RuntimeError(f"cannot connect to {host}:{port} ({exc})") from exc
    except OSError as exc:
        raise RuntimeError(f"request failed for {method} {path}: {exc}") from exc
    finally:
        conn.close()


def random_session_id() -> str:
    rand = "".join(random.choice(string.hexdigits.lower()) for _ in range(24))
    return f"smoke-{int(time.time())}-{rand}"


def is_local_http(host: str, use_https: bool) -> bool:
    return not use_https and host in {"127.0.0.1", "localhost", "::1"}


def can_connect(host: str, port: int, use_https: bool) -> bool:
    try:
        request(host, port, "GET", "/", use_https=use_https, timeout=1.5)
        return True
    except RuntimeError:
        return False


def start_local_server(host: str, port: int) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for_server(host: str, port: int, use_https: bool, timeout_seconds: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    last_notice = 0.0
    while time.monotonic() < deadline:
        if can_connect(host, port, use_https):
            return True
        now = time.monotonic()
        if now - last_notice >= 5.0:
            remaining = max(0, int(deadline - now))
            print(f"INFO: waiting for temporary server... {remaining}s left")
            last_notice = now
        time.sleep(0.35)
    return False


def stop_started_server(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=8)


def expect_redirect(results: list[Result], name: str, host: str, port: int, path: str, target: str, use_https: bool) -> None:
    status, headers, body = request(host, port, "GET", path, use_https=use_https)
    detail = f"status={status}, body={body[:40]!r}"
    if status != 307:
        results.append(Result(name, False, f"{detail} expected HTTP 307"))
        return
    location = headers.get("location") or ""
    if location != target and not location.endswith(target):
        results.append(Result(name, False, f"location={location!r}, expected {target!r}"))
        return
    results.append(Result(name, True, f"status={status}, location={location!r}"))


def expect_ui(results: list[Result], name: str, host: str, port: int, cache_bust: str, use_https: bool) -> None:
    path = f"/luxcode-v1/?v={cache_bust}"
    status, _, body = request(host, port, "GET", path, use_https=use_https)
    if status != 200:
        results.append(Result(name, False, f"status={status}, expected 200"))
        return
    text = body.decode("utf-8", errors="replace")
    snippet = text[:400].lower()
    if "<!doctype html>" not in snippet and "<html" not in snippet:
        results.append(Result(name, False, "response did not look like HTML"))
        return
    if "/luxcode-conversation/" in text:
        results.append(Result(name, False, "legacy conversation path still appears in UI payload"))
        return
    results.append(Result(name, True, f"status={status}, size={len(body)}"))


def expect_legacy_event_denylist(results: list[Result], name: str, host: str, port: int, use_https: bool) -> None:
    session_id = random_session_id()
    status, _, body = request(host, port, "GET", f"/luxcode-conversation/{session_id}/events", use_https=use_https)
    if status != 410:
        results.append(Result(name, False, f"status={status}, expected 410"))
        return
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        results.append(Result(name, False, f"response is not JSON: {exc}"))
        return
    if payload.get("error") != "legacy_endpoint_removed":
        results.append(
            Result(
                name,
                False,
                f"unexpected payload: {payload.get('error')!r}",
            )
        )
        return
    results.append(Result(name, True, f"status={status}, legacy marker={payload.get('error')!r}"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Legacy /luxcode-conversation denylist mini smoke")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="LUXCODE base URL (default: http://127.0.0.1:5000)")
    parser.add_argument("--no-auto-start", action="store_true", help="Do not start a temporary local uvicorn server when port is closed")
    args = parser.parse_args(argv)

    host, port, use_https = parse_base_url(args.base_url)
    print(f"START legacy-call denylist smoke -> {host}:{port} @ {now_text()}")
    results: list[Result] = []
    started_proc: subprocess.Popen[bytes] | None = None

    try:
        if not can_connect(host, port, use_https):
            if args.no_auto_start or not is_local_http(host, use_https):
                raise RuntimeError(f"cannot connect to {host}:{port}")
            print("INFO: server was not running; starting temporary uvicorn for this smoke")
            started_proc = start_local_server(host, port)
            if not wait_for_server(host, port, use_https):
                code = started_proc.poll()
                raise RuntimeError(f"temporary server did not become ready, exit={code}")
            print(f"INFO: temporary server ready, pid={started_proc.pid}")

        expect_redirect(results, "GET / -> /luxcode-v1/", host, port, "/", "/luxcode-v1/", use_https)
        expect_redirect(results, "GET /luxcode -> /luxcode-v1/", host, port, "/luxcode", "/luxcode-v1/", use_https)
        expect_ui(results, "GET /luxcode-v1/ load", host, port, "mini-denylist-smoke", use_https)
        expect_legacy_event_denylist(results, "GET /luxcode-conversation/*/events returns 410", host, port, use_https)
    except RuntimeError as exc:
        results.append(Result("request chain", False, str(exc)))
    finally:
        if started_proc is not None:
            stop_started_server(started_proc)
            print("INFO: temporary server stopped")

    failures = [r for r in results if not r.ok]
    for item in results:
        status = "PASS" if item.ok else "FAIL"
        print(f"{status}: {item.name} - {item.detail}")

    if failures:
        print(f"SUMMARY: {len(failures)} FAILED, {len(results) - len(failures)} PASSED")
        return 1

    print(f"SUMMARY: ALL PASS ({len(results)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
