from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.api.errors import ApiError
from app.application.export_service import ExportError, ExportService
from app.infrastructure.db.repositories import ExportRepository
from app.infrastructure.files.task_storage import TaskStorage
from app.infrastructure.jobs.state_machine import InvalidTransition

router = APIRouter(prefix="/api/tasks/{task_id}", tags=["exports"])
_DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


@router.post("/export", status_code=status.HTTP_201_CREATED)
def export_task(task_id: str, request: Request) -> dict[str, str]:
    storage = TaskStorage(request.app.state.settings.data_dir)
    try:
        record = ExportService(request.app.state.session_factory, storage).export(task_id)
    except LookupError as exc:
        raise ApiError(404, "TASK_NOT_FOUND", "任务不存在") from exc
    except FileNotFoundError as exc:
        raise ApiError(409, "EXPORT_INPUT_MISSING", "导出所需文件不存在") from exc
    except InvalidTransition as exc:
        raise ApiError(409, "INVALID_TASK_STATUS", "当前任务状态无法导出") from exc
    except ExportError as exc:
        status_code = 409 if exc.code == "UNCONFIRMED_SECTIONS" else 422
        raise ApiError(status_code, exc.code, str(exc)) from exc
    return {
        "status": "completed",
        "download_name": record.download_name,
    }


@router.get("/download", response_class=FileResponse)
def download_export(
    task_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> FileResponse:
    record = ExportRepository(session).get(task_id)
    if record is None:
        raise ApiError(404, "EXPORT_NOT_FOUND", "尚未生成可下载的汇总文件")
    path = TaskStorage(request.app.state.settings.data_dir).output_path(
        task_id, record.stored_name
    )
    if not path.is_file():
        raise ApiError(404, "EXPORT_NOT_FOUND", "尚未生成可下载的汇总文件")
    return FileResponse(
        path,
        media_type=_DOCX_MEDIA_TYPE,
        filename=record.download_name,
    )
