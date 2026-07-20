from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.domain.enums import GenerationMode, TaskStatus
from app.domain.task import Task
from app.infrastructure.db.repositories import TaskRepository
from app.infrastructure.docx.package_guard import inspect_docx_package
from app.infrastructure.files.task_storage import TaskStorage


class TaskService:
    def __init__(
        self,
        session: Session,
        storage: TaskStorage,
        *,
        max_txt_bytes: int,
        max_docx_bytes: int,
        max_docx_entries: int,
        max_docx_uncompressed_bytes: int,
        max_docx_compression_ratio: int,
    ) -> None:
        self._repository = TaskRepository(session)
        self._storage = storage
        self._max_txt_bytes = max_txt_bytes
        self._max_docx_bytes = max_docx_bytes
        self._max_docx_entries = max_docx_entries
        self._max_docx_uncompressed_bytes = max_docx_uncompressed_bytes
        self._max_docx_compression_ratio = max_docx_compression_ratio

    def create(
        self, name: str, mode: GenerationMode = GenerationMode.REVIEW
    ) -> Task:
        return self._repository.create(name, mode)

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
        self._storage.delete_inputs(task_id)
        try:
            reports_path = self._storage.write_stream(
                task_id, "reports.txt", reports, self._max_txt_bytes
            )
            template_path = self._storage.write_stream(
                task_id, "template.docx", template, self._max_docx_bytes
            )
            inspect_docx_package(
                template_path.read_bytes(),
                max_entries=self._max_docx_entries,
                max_uncompressed=self._max_docx_uncompressed_bytes,
                max_compression_ratio=self._max_docx_compression_ratio,
            )
        except Exception:
            self._storage.delete_inputs(task_id)
            raise
        task = self._repository.set_status(task_id, TaskStatus.PEOPLE_CONFIRMATION)
        return reports_path, template_path, task
