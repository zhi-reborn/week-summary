from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.errors import ApiError, api_error_handler
from app.api.routes.health import router as health_router
from app.api.routes.people import router as people_router
from app.api.routes.tasks import router as tasks_router
from app.config import Settings


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
    return application


app = create_app()
