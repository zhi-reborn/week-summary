from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.api.errors import ApiError
from app.application.cleanup_service import CleanupService
from app.infrastructure.files.task_storage import TaskStorage

router = APIRouter(prefix="/api/data", tags=["data"])


def _service(request: Request, session: Session) -> CleanupService:
    settings = request.app.state.settings
    return CleanupService(
        session,
        TaskStorage(settings.data_dir),
        settings.data_dir,
        settings.retention_days,
    )


@router.get("/usage")
def get_usage(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int]:
    usage = _service(request, session).usage()
    return {
        "task_count": usage.task_count,
        "task_bytes": usage.task_bytes,
        "database_bytes": usage.database_bytes,
        "total_bytes": usage.total_bytes,
    }


@router.post("/cleanup")
def cleanup_data(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int]:
    try:
        result = _service(request, session).cleanup()
    except ValueError as exc:
        raise ApiError(409, "RETENTION_DISABLED", str(exc)) from exc
    except OSError as exc:
        raise ApiError(503, "TASK_DELETE_FAILED", "任务文件删除失败，可稍后重试") from exc
    return {
        "deleted_tasks": result.deleted_tasks,
        "freed_bytes": result.freed_bytes,
    }
