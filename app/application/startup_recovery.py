from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.logging import log_event
from app.domain.enums import GenerationMode, TaskStatus
from app.infrastructure.db.repositories import AnalysisJobRepository, TaskRepository
from app.infrastructure.files.task_storage import TaskStorage


@dataclass(frozen=True)
class RecoveryResult:
    requeued_analysis: int
    exhausted_analysis: int
    recovered_review_exports: int
    retriggered_direct_exports: int
    cleaned_temporary_files: int


class StartupRecovery:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        storage: TaskStorage,
        export_task: Callable[[str], object],
        max_recovery_attempts: int,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._export_task = export_task
        self._max_recovery_attempts = max_recovery_attempts

    def run(self) -> RecoveryResult:
        cleaned = self._storage.cleanup_temporary_outputs()
        with self._session_factory() as session:
            tasks = TaskRepository(session)
            jobs = AnalysisJobRepository(session)
            requeued, exhausted = jobs.recover_interrupted(self._max_recovery_attempts)
            for task_id in exhausted:
                task = tasks.get(task_id)
                if task is not None and task.status == TaskStatus.ANALYZING:
                    tasks.set_status(task_id, TaskStatus.FAILED)
            for task in tasks.list_by_status(TaskStatus.ANALYZING):
                if task.id in exhausted:
                    continue
                job = jobs.get(task.id)
                if job is None or job.status in {"failed", "succeeded"}:
                    jobs.enqueue(task.id)
                    requeued.append(task.id)

            review_exports = tasks.list_by_status(TaskStatus.EXPORTING)
            direct_exports: list[str] = []
            recovered_reviews = 0
            for task in review_exports:
                if task.mode == GenerationMode.REVIEW:
                    tasks.set_status(task.id, TaskStatus.REVIEW)
                    recovered_reviews += 1
                else:
                    tasks.set_status(task.id, TaskStatus.EXPORT_FAILED)
                    direct_exports.append(task.id)
            session.commit()

        retriggered = 0
        for task_id in direct_exports:
            retriggered += 1
            try:
                self._export_task(task_id)
            except Exception as exc:
                log_event(
                    {
                        "task_id": task_id,
                        "stage": "startup_recovery",
                        "error_code": getattr(exc, "code", "EXPORT_RECOVERY_FAILED"),
                    }
                )

        return RecoveryResult(
            requeued_analysis=len(set(requeued)),
            exhausted_analysis=len(exhausted),
            recovered_review_exports=recovered_reviews,
            retriggered_direct_exports=retriggered,
            cleaned_temporary_files=cleaned,
        )
