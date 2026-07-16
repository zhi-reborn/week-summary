from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.api.errors import ApiError
from app.application.segmentation_service import SegmentationService
from app.domain.people import SegmentationResult
from app.infrastructure.files.task_storage import TaskStorage

router = APIRouter(prefix="/api/tasks/{task_id}/people", tags=["people"])


def _service(request: Request, session: Session) -> SegmentationService:
    return SegmentationService(session, TaskStorage(request.app.state.settings.data_dir))


@router.post("/detect", response_model=SegmentationResult)
def detect_people(
    task_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> SegmentationResult:
    try:
        return _service(request, session).detect(task_id)
    except LookupError as exc:
        raise ApiError(404, "TASK_NOT_FOUND", "任务或输入文件不存在") from exc
    except ValueError as exc:
        raise ApiError(422, "UNSUPPORTED_TEXT_ENCODING", str(exc)) from exc


@router.get("", response_model=SegmentationResult)
def get_people(
    task_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> SegmentationResult:
    try:
        return _service(request, session).get(task_id)
    except LookupError as exc:
        raise ApiError(404, "PEOPLE_NOT_FOUND", str(exc)) from exc


@router.put("", response_model=SegmentationResult)
def replace_people(
    task_id: str,
    result: SegmentationResult,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> SegmentationResult:
    try:
        return _service(request, session).replace(task_id, result)
    except LookupError as exc:
        raise ApiError(404, "TASK_NOT_FOUND", str(exc)) from exc
    except ValueError as exc:
        raise ApiError(422, "INVALID_PEOPLE_SEGMENTS", str(exc)) from exc


@router.post("/confirm")
def confirm_people(
    task_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, str]:
    try:
        task = _service(request, session).confirm(task_id)
    except LookupError as exc:
        raise ApiError(404, "PEOPLE_NOT_FOUND", str(exc)) from exc
    except ValueError as exc:
        raise ApiError(409, "PEOPLE_NOT_READY", str(exc)) from exc
    return {"id": task.id, "status": task.status.value}
