from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.domain.quality import QualityFinding
from app.infrastructure.db.repositories import (
    AnalysisJobRepository,
    JobStepRepository,
    QualityFindingRepository,
    TaskRepository,
)


class AnalysisProgress(BaseModel):
    task_id: str
    task_status: str
    job_status: str | None
    total_steps: int
    succeeded_steps: int
    current_step: str | None
    failed_error_code: str | None
    retryable: bool
    quality_findings: list[QualityFinding]


ResultT = TypeVar("ResultT")


def run_persisted_step(
    session: Session,
    task_id: str,
    step_type: str,
    entity_id: str,
    operation: Callable[[], ResultT],
) -> ResultT | None:
    steps = JobStepRepository(session)
    step = steps.get_or_create(task_id, step_type, entity_id)
    if step.status == "succeeded":
        return None
    steps.mark_running(step.id)
    session.commit()
    try:
        result = operation()
        JobStepRepository(session).mark_succeeded(step.id)
        session.commit()
        return result
    except Exception as exc:
        session.rollback()
        current = JobStepRepository(session).get(task_id, step_type, entity_id)
        if current is not None:
            JobStepRepository(session).mark_failed(
                current.id, getattr(exc, "code", "ANALYSIS_STEP_FAILED")
            )
            session.commit()
        raise


def read_progress(session: Session, task_id: str) -> AnalysisProgress:
    task = TaskRepository(session).get(task_id)
    if task is None:
        raise LookupError("任务不存在")
    job = AnalysisJobRepository(session).get(task_id)
    steps = JobStepRepository(session).list_for_task(task_id)
    active = next(
        (step for status in ("running", "failed", "pending") for step in steps if step.status == status),
        None,
    )
    error_code = active.error_code if active is not None else None
    if error_code is None and job is not None:
        error_code = job.error_code
    return AnalysisProgress(
        task_id=task.id,
        task_status=task.status.value,
        job_status=job.status if job is not None else None,
        total_steps=len(steps),
        succeeded_steps=sum(step.status == "succeeded" for step in steps),
        current_step=(f"{active.step_type}:{active.entity_id}" if active is not None else None),
        failed_error_code=error_code,
        retryable=task.status.value == "failed" and job is not None and job.status == "failed",
        quality_findings=QualityFindingRepository(session).list_for_task(task_id),
    )
