from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.api.errors import ApiError
from app.application.template_service import TemplateService
from app.domain.template import TemplateSection
from app.infrastructure.files.task_storage import TaskStorage

router = APIRouter(prefix="/api/tasks/{task_id}/template", tags=["template"])


def _service(request: Request, session: Session) -> TemplateService:
    return TemplateService(session, TaskStorage(request.app.state.settings.data_dir))


@router.post("/detect", response_model=list[TemplateSection])
def detect_template(
    task_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> list[TemplateSection]:
    try:
        return _service(request, session).detect(task_id)
    except (LookupError, FileNotFoundError) as exc:
        raise ApiError(404, "TEMPLATE_NOT_FOUND", str(exc)) from exc
    except ValueError as exc:
        raise ApiError(422, "INVALID_DOCX", str(exc)) from exc


@router.get("/sections", response_model=list[TemplateSection])
def get_template_sections(
    task_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> list[TemplateSection]:
    try:
        return _service(request, session).get(task_id)
    except LookupError as exc:
        raise ApiError(404, "TEMPLATE_SECTIONS_NOT_FOUND", str(exc)) from exc


@router.put("/sections", response_model=list[TemplateSection])
def replace_template_sections(
    task_id: str,
    sections: list[TemplateSection],
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> list[TemplateSection]:
    try:
        return _service(request, session).replace(task_id, sections)
    except LookupError as exc:
        raise ApiError(404, "TEMPLATE_SECTIONS_NOT_FOUND", str(exc)) from exc
    except ValueError as exc:
        raise ApiError(422, "INVALID_TEMPLATE_SECTIONS", str(exc)) from exc


@router.post("/confirm")
def confirm_template(
    task_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, str]:
    try:
        task = _service(request, session).confirm(task_id)
    except LookupError as exc:
        raise ApiError(404, "TEMPLATE_SECTIONS_NOT_FOUND", str(exc)) from exc
    except ValueError as exc:
        raise ApiError(409, "TEMPLATE_NOT_READY", str(exc)) from exc
    return {"id": task.id, "status": task.status.value}
