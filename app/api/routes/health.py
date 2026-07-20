import os
from tempfile import NamedTemporaryFile
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.api.dependencies import get_session

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "alive", "version": "0.1.0"}


@router.get("/api/health/ready")
def readiness(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> JSONResponse:
    checks: dict[str, str] = {}
    expected_migration = "0007"
    try:
        bind = session.get_bind()
        if isinstance(bind, Engine):
            with bind.connect() as connection:
                _check_database_write(connection)
        else:
            _check_database_write(bind)
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "failed"

    temporary_path = None
    try:
        request.app.state.settings.data_dir.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            dir=request.app.state.settings.data_dir,
            delete=False,
        ) as temporary:
            temporary_path = temporary.name
            temporary.write(b"ready")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.unlink(temporary_path)
        checks["data_directory"] = "ok"
    except OSError:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
        checks["data_directory"] = "failed"

    try:
        current = session.scalar(text("SELECT version_num FROM alembic_version"))
        checks["migration"] = str(current) if current == expected_migration else "outdated"
    except Exception:
        session.rollback()
        checks["migration"] = "unavailable"

    ready = checks == {
        "database": "ok",
        "data_directory": "ok",
        "migration": expected_migration,
    }
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )


def _check_database_write(connection: Connection) -> None:
    connection.exec_driver_sql("BEGIN IMMEDIATE")
    connection.execute(text("SELECT 1"))
    connection.rollback()
