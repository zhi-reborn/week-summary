import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.errors import ApiError, api_error_handler
from app.api.routes.analysis import router as analysis_router
from app.api.routes.downloads import router as downloads_router
from app.api.routes.data_management import router as data_management_router
from app.api.routes.diagnostics import router as diagnostics_router
from app.api.routes.health import router as health_router
from app.api.routes.people import router as people_router
from app.api.routes.review import router as review_router
from app.api.routes.settings import router as settings_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.templates import router as templates_router
from app.config import Settings
from app.core.logging import log_event


def _static_dir() -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return bundle_root / "app" / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    application = FastAPI(title="智能周报汇总系统", version="0.1.0")
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
    application.state.settings = settings
    application.state.session_factory = sessionmaker(engine, expire_on_commit=False)
    application.add_exception_handler(ApiError, api_error_handler)

    @application.middleware("http")
    async def structured_request_log(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        path_parts = request.url.path.split("/")
        request.state.task_id = (
            path_parts[3]
            if path_parts[:3] == ["", "api", "tasks"] and len(path_parts) > 3
            else None
        )
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            log_event(
                {
                    "request_id": request_id,
                    "task_id": request.state.task_id,
                    "stage": "http_request",
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    "error_code": "UNHANDLED_ERROR",
                    "http_method": request.method,
                    "http_status": 500,
                }
            )
            raise
        log_event(
            {
                "request_id": request_id,
                "task_id": request.state.task_id,
                "stage": "http_request",
                "duration_ms": round((time.monotonic() - started) * 1000),
                "http_method": request.method,
                "http_status": response.status_code,
            }
        )
        response.headers["X-Request-ID"] = request_id
        return response

    application.include_router(health_router)
    application.include_router(tasks_router)
    application.include_router(people_router)
    application.include_router(templates_router)
    application.include_router(settings_router)
    application.include_router(analysis_router)
    application.include_router(review_router)
    application.include_router(downloads_router)
    application.include_router(data_management_router)
    application.include_router(diagnostics_router)
    static_dir = _static_dir()
    if (static_dir / "index.html").is_file():

        @application.get("/{full_path:path}", include_in_schema=False)
        def serve_frontend(full_path: str) -> FileResponse:
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404)
            candidate = (static_dir / full_path).resolve()
            if candidate.is_relative_to(static_dir.resolve()) and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")

    return application


app = create_app()
