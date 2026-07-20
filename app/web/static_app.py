from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def mount_static_app(application: FastAPI, static_dir: Path) -> None:
    index_path = static_dir / "index.html"
    if not index_path.is_file():
        return
    static_root = static_dir.resolve()

    @application.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str) -> FileResponse:
        if _is_backend_path(full_path):
            raise HTTPException(status_code=404)
        candidate = (static_root / full_path).resolve()
        if candidate.is_relative_to(static_root) and candidate.is_file():
            return FileResponse(candidate)
        if full_path == "assets" or full_path.startswith("assets/"):
            raise HTTPException(status_code=404)
        return FileResponse(index_path)


def _is_backend_path(path: str) -> bool:
    return path in {"api", "health"} or path.startswith(("api/", "health/"))
