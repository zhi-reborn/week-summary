from fastapi import FastAPI

from app.api.routes.health import router as health_router


def create_app() -> FastAPI:
    application = FastAPI(title="智能周报汇总系统", version="0.1.0")
    application.include_router(health_router)
    return application


app = create_app()
