from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse


def _no_cache_file_response(path: Path, now_iso: Callable[[], str]) -> FileResponse:
    response = FileResponse(str(path))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, proxy-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Content-Version"] = now_iso()
    return response


def build_page_router(base_dir: Path, static_dir: Path, now_iso: Callable[[], str]) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def index():
        return _no_cache_file_response(static_dir / "index.html", now_iso)

    @router.get("/luxcode")
    async def luxcode_index():
        return _no_cache_file_response(static_dir / "luxcode" / "index.html", now_iso)

    def luxviai_dev_version_payload() -> Dict[str, Any]:
        watched = [base_dir / "app.py", static_dir / "index.html", static_dir / "luxcode" / "index.html"]
        parts = []
        for path in watched:
            try:
                stat = path.stat()
                parts.append(f"{path.name}:{int(stat.st_mtime_ns)}:{stat.st_size}")
            except OSError:
                parts.append(f"{path.name}:missing")
        return {
            "version": "|".join(parts),
            "watched": [path.name for path in watched],
            "generated_at": now_iso(),
        }

    @router.get("/luxviai-dev/version")
    async def luxviai_dev_version():
        response = JSONResponse(luxviai_dev_version_payload())
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, proxy-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    return router
