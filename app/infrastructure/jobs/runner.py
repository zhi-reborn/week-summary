import threading
from collections.abc import Callable
from typing import Protocol
from uuid import uuid4

from sqlalchemy.orm import Session

from app.domain.enums import TaskStatus
from app.infrastructure.db.repositories import AnalysisJobRepository, TaskRepository
from app.infrastructure.jobs.state_machine import transition


class AnalysisProcessor(Protocol):
    def run(self, task_id: str) -> None: ...


class AnalysisRunner:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        processor: AnalysisProcessor,
        *,
        poll_seconds: float = 0.5,
    ) -> None:
        self._session_factory = session_factory
        self._processor = processor
        self._poll_seconds = poll_seconds
        self._owner_id = str(uuid4())
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def enqueue(self, task_id: str) -> None:
        with self._session_factory() as session:
            tasks = TaskRepository(session)
            task = tasks.get(task_id)
            if task is None:
                raise LookupError("任务不存在")
            tasks.set_status(task_id, transition(task.status, TaskStatus.ANALYZING))
            AnalysisJobRepository(session).enqueue(task_id)
            session.commit()

    def retry(self, task_id: str) -> None:
        with self._session_factory() as session:
            tasks = TaskRepository(session)
            task = tasks.get(task_id)
            if task is None:
                raise LookupError("任务不存在")
            tasks.set_status(task_id, transition(task.status, TaskStatus.ANALYZING))
            AnalysisJobRepository(session).enqueue(task_id)
            session.commit()

    def recover(self) -> None:
        with self._session_factory() as session:
            AnalysisJobRepository(session).requeue_interrupted()
            session.commit()

    def run_once(self) -> bool:
        with self._session_factory() as session:
            job = AnalysisJobRepository(session).claim_next(self._owner_id)
            session.commit()
        if job is None:
            return False
        try:
            self._processor.run(job.task_id)
        except Exception as exc:
            with self._session_factory() as session:
                AnalysisJobRepository(session).mark_failed(
                    job.task_id, getattr(exc, "code", "ANALYSIS_FAILED")
                )
                task = TaskRepository(session).get(job.task_id)
                if task is not None and task.status == TaskStatus.ANALYZING:
                    TaskRepository(session).set_status(
                        job.task_id, transition(task.status, TaskStatus.FAILED)
                    )
                session.commit()
            return True
        with self._session_factory() as session:
            AnalysisJobRepository(session).mark_succeeded(job.task_id)
            task = TaskRepository(session).get(job.task_id)
            if task is None:
                raise LookupError("任务不存在")
            TaskRepository(session).set_status(
                job.task_id, transition(task.status, TaskStatus.REVIEW)
            )
            session.commit()
        return True

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self.recover()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2, self._poll_seconds * 2))

    def _run_forever(self) -> None:
        while not self._stop.is_set():
            processed = self.run_once()
            if not processed:
                self._stop.wait(self._poll_seconds)
