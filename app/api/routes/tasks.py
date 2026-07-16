from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_session
from app.api.errors import ApiError
from app.application.task_service import TaskService
from app.infrastructure.files.safe_upload import safe_filename
from app.infrastructure.files.task_storage import FileTooLarge, TaskStorage
from app.domain.task import Task
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(
    payload: CreateTaskRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, str]:
    settings = request.app.state.settings
    task = TaskService(
        session, TaskStorage(settings.data_dir), settings.max_upload_bytes
    ).create(payload.name)
    return _serialize_task(task)


@router.get("/{task_id}")
def get_task(
    task_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, str]:
    settings = request.app.state.settings
    task = TaskService(
        session, TaskStorage(settings.data_dir), settings.max_upload_bytes
    ).get(task_id)
    if task is None:
        raise ApiError(404, "TASK_NOT_FOUND", "任务不存在")
    return _serialize_task(task)


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
    settings = request.app.state.settings
    service = TaskService(session, TaskStorage(settings.data_dir), settings.max_upload_bytes)
    try:
        _, _, task = service.store_inputs(task_id, reports.file, template.file)
    except LookupError as exc:
        raise ApiError(404, "TASK_NOT_FOUND", "任务不存在") from exc
    except FileTooLarge as exc:
        raise ApiError(413, "FILE_TOO_LARGE", "上传文件超过大小限制") from exc
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
    return {"id": task.id, "name": task.name, "status": task.status.value}
