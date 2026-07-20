from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_session
from app.api.errors import ApiError
from app.application.task_service import TaskService
from app.application.cleanup_service import CleanupService
from app.infrastructure.files.safe_upload import safe_filename
from app.infrastructure.files.task_storage import FileTooLarge, TaskStorage
from app.infrastructure.docx.package_guard import UnsafeDocx
from app.domain.task import Task
from app.domain.enums import GenerationMode
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task_service(request: Request, session: Session) -> TaskService:
    settings = request.app.state.settings
    return TaskService(
        session,
        TaskStorage(settings.data_dir),
        max_txt_bytes=settings.max_txt_bytes,
        max_docx_bytes=settings.max_docx_bytes,
        max_docx_entries=settings.max_docx_entries,
        max_docx_uncompressed_bytes=settings.max_docx_uncompressed_bytes,
        max_docx_compression_ratio=settings.max_docx_compression_ratio,
    )


class CreateTaskRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    mode: GenerationMode = GenerationMode.REVIEW


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(
    payload: CreateTaskRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, str]:
    task = _task_service(request, session).create(payload.name, payload.mode)
    return _serialize_task(task)


@router.get("/{task_id}")
def get_task(
    task_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, str]:
    task = _task_service(request, session).get(task_id)
    if task is None:
        raise ApiError(404, "TASK_NOT_FOUND", "任务不存在")
    return _serialize_task(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    settings = request.app.state.settings
    service = CleanupService(
        session,
        TaskStorage(settings.data_dir),
        settings.data_dir,
        settings.retention_days,
    )
    try:
        service.delete_task(task_id)
    except LookupError as exc:
        raise ApiError(404, "TASK_NOT_FOUND", "任务不存在") from exc
    except OSError as exc:
        raise ApiError(503, "TASK_DELETE_FAILED", "任务文件删除失败，可稍后重试") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{task_id}/inputs")
def upload_inputs(
    task_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    reports: Annotated[UploadFile, File()],
    template: Annotated[UploadFile, File()],
) -> dict[str, str]:
    reports_name = _validate_filename(reports, ".txt")
    template_name = _validate_filename(template, ".docx")
    service = _task_service(request, session)
    try:
        _, _, task = service.store_inputs(task_id, reports.file, template.file)
    except LookupError as exc:
        raise ApiError(404, "TASK_NOT_FOUND", "任务不存在") from exc
    except FileTooLarge as exc:
        raise ApiError(413, "FILE_TOO_LARGE", "上传文件超过大小限制") from exc
    except UnsafeDocx as exc:
        raise ApiError(exc.status_code, exc.code, str(exc)) from exc
    return {
        "reports_name": reports_name,
        "template_name": template_name,
        "status": task.status.value,
    }


def _validate_filename(upload: UploadFile, suffix: str) -> str:
    try:
        name = safe_filename(upload.filename or "")
    except ValueError as exc:
        raise ApiError(400, "INVALID_FILENAME", "文件名无效") from exc
    if not name.lower().endswith(suffix):
        raise ApiError(415, "UNSUPPORTED_FILE_TYPE", "只支持 TXT 周报和 DOCX 模板")
    return name


def _serialize_task(task: Task) -> dict[str, str]:
    return {
        "id": task.id,
        "name": task.name,
        "mode": task.mode.value,
        "status": task.status.value,
    }
