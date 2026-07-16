from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.api.errors import ApiError
from app.infrastructure.jobs.runner import AnalysisRunner
from app.infrastructure.jobs.state_machine import InvalidTransition
from app.infrastructure.jobs.steps import AnalysisProgress, read_progress

router = APIRouter(prefix="/api/tasks/{task_id}/analysis", tags=["analysis"])


def _runner(request: Request) -> AnalysisRunner:
    runner = getattr(request.app.state, "runner", None)
    if runner is None:
        raise ApiError(503, "ANALYSIS_RUNNER_UNAVAILABLE", "分析运行器尚未启动")
    return cast(AnalysisRunner, runner)


def _progress(session: Session, task_id: str) -> AnalysisProgress:
    try:
        session.expire_all()
        return read_progress(session, task_id)
    except LookupError as exc:
        raise ApiError(404, "TASK_NOT_FOUND", str(exc)) from exc


@router.post("/start", response_model=AnalysisProgress, status_code=status.HTTP_202_ACCEPTED)
def start_analysis(
    task_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> AnalysisProgress:
    try:
        _runner(request).enqueue(task_id)
    except LookupError as exc:
        raise ApiError(404, "TASK_NOT_FOUND", str(exc)) from exc
    except InvalidTransition as exc:
        raise ApiError(409, "ANALYSIS_NOT_READY", "请先确认人员和模板板块") from exc
    return _progress(session, task_id)


@router.get("/status", response_model=AnalysisProgress)
def get_analysis_status(
    task_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> AnalysisProgress:
    return _progress(session, task_id)


@router.post("/retry", response_model=AnalysisProgress, status_code=status.HTTP_202_ACCEPTED)
def retry_analysis(
    task_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> AnalysisProgress:
    try:
        _runner(request).retry(task_id)
    except LookupError as exc:
        raise ApiError(404, "TASK_NOT_FOUND", str(exc)) from exc
    except InvalidTransition as exc:
        raise ApiError(409, "ANALYSIS_NOT_RETRYABLE", "当前分析任务不可重试") from exc
    return _progress(session, task_id)
