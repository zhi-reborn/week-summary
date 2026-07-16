import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.errors import ApiError, api_error_handler
from app.api.routes.health import router as health_router
from app.api.routes.people import router as people_router
from app.api.routes.settings import router as settings_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.templates import router as templates_router
from app.config import Settings


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
    application.include_router(health_router)
    application.include_router(tasks_router)
    application.include_router(people_router)
    application.include_router(templates_router)
    application.include_router(settings_router)
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
