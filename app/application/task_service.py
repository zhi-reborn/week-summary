from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.domain.enums import TaskStatus
from app.domain.task import Task
from app.infrastructure.db.repositories import TaskRepository
from app.infrastructure.files.task_storage import TaskStorage


class TaskService:
    def __init__(self, session: Session, storage: TaskStorage, max_upload_bytes: int) -> None:
        self._repository = TaskRepository(session)
        self._storage = storage
        self._max_upload_bytes = max_upload_bytes

    def create(self, name: str) -> Task:
        return self._repository.create(name)

    def get(self, task_id: str) -> Task | None:
        return self._repository.get(task_id)

    def store_inputs(
        self,
        task_id: str,
        reports: BinaryIO,
        template: BinaryIO,
    ) -> tuple[Path, Path, Task]:
        if self._repository.get(task_id) is None:
            raise LookupError("任务不存在")
        reports_path = self._storage.write_stream(
            task_id, "reports.txt", reports, self._max_upload_bytes
        )
        template_path = self._storage.write_stream(
            task_id, "template.docx", template, self._max_upload_bytes
        )
        task = self._repository.set_status(task_id, TaskStatus.PEOPLE_CONFIRMATION)
        return reports_path, template_path, task

