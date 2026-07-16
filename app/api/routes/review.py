from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.api.errors import ApiError
from app.api.schemas.review import (
    ReviewSectionResponse,
    ReviewSourceResponse,
    UpdateSectionRequest,
)
from app.application.review_service import ReviewNotReady, ReviewService
from app.infrastructure.files.task_storage import TaskStorage

router = APIRouter(prefix="/api/tasks/{task_id}/sections", tags=["review"])


def _service(request: Request, session: Session) -> ReviewService:
    return ReviewService(session, TaskStorage(request.app.state.settings.data_dir))


def _not_found(exc: LookupError) -> ApiError:
    return ApiError(404, "REVIEW_SECTION_NOT_FOUND", str(exc))


@router.get("", response_model=list[ReviewSectionResponse])
def list_sections(
    task_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> list[ReviewSectionResponse]:
    try:
        data = _service(request, session).list_sections(task_id)
    except LookupError as exc:
        raise _not_found(exc) from exc
    return [ReviewSectionResponse.from_data(item) for item in data]


@router.get("/{section_key}", response_model=ReviewSectionResponse)
def get_section(
    task_id: str,
    section_key: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> ReviewSectionResponse:
    try:
        data = _service(request, session).get_section(task_id, section_key)
    except LookupError as exc:
        raise _not_found(exc) from exc
    return ReviewSectionResponse.from_data(data)


@router.put("/{section_key}", response_model=ReviewSectionResponse)
def update_section(
    task_id: str,
    section_key: str,
    payload: UpdateSectionRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> ReviewSectionResponse:
    try:
        data = _service(request, session).update_section(
            task_id, section_key, payload.content, "local-user"
        )
    except ReviewNotReady as exc:
        raise ApiError(409, "REVIEW_NOT_READY", str(exc)) from exc
    except LookupError as exc:
        raise _not_found(exc) from exc
    return ReviewSectionResponse.from_data(data)


@router.post("/{section_key}/confirm", response_model=ReviewSectionResponse)
def confirm_section(
    task_id: str,
    section_key: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> ReviewSectionResponse:
    try:
        data = _service(request, session).confirm_section(task_id, section_key, "local-user")
    except ReviewNotReady as exc:
        raise ApiError(409, "REVIEW_NOT_READY", str(exc)) from exc
    except LookupError as exc:
        raise _not_found(exc) from exc
    return ReviewSectionResponse.from_data(data)


@router.post("/{section_key}/restore/{revision}", response_model=ReviewSectionResponse)
def restore_section(
    task_id: str,
    section_key: str,
    revision: int,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> ReviewSectionResponse:
    try:
        data = _service(request, session).restore_section(
            task_id, section_key, revision, "local-user"
        )
    except ReviewNotReady as exc:
        raise ApiError(409, "REVIEW_NOT_READY", str(exc)) from exc
    except LookupError as exc:
        raise _not_found(exc) from exc
    return ReviewSectionResponse.from_data(data)


@router.get("/{section_key}/versions", response_model=list[ReviewSectionResponse])
def list_versions(
    task_id: str,
    section_key: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> list[ReviewSectionResponse]:
    try:
        data = _service(request, session).list_versions(task_id, section_key)
    except LookupError as exc:
        raise _not_found(exc) from exc
    return [ReviewSectionResponse.from_data(item) for item in data]


@router.get("/{section_key}/sources", response_model=list[ReviewSourceResponse])
def list_sources(
    task_id: str,
    section_key: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> list[ReviewSourceResponse]:
    try:
        sources = _service(request, session).list_sources(task_id, section_key)
    except LookupError as exc:
        raise _not_found(exc) from exc
    return [ReviewSourceResponse.from_source(item) for item in sources]
