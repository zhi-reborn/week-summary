from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.domain.enums import TaskStatus
from app.infrastructure.db.repositories import TaskRepository
from app.infrastructure.files.task_storage import TaskStorage


@dataclass(frozen=True)
class DataUsage:
    task_count: int
    task_bytes: int
    database_bytes: int

    @property
    def total_bytes(self) -> int:
        return self.task_bytes + self.database_bytes


@dataclass(frozen=True)
class CleanupResult:
    deleted_tasks: int
    freed_bytes: int


class CleanupService:
    def __init__(
        self,
        session: Session,
        storage: TaskStorage,
        data_dir: Path,
        retention_days: int | None,
    ) -> None:
        self._session = session
        self._repository = TaskRepository(session)
        self._storage = storage
        self._database_path = data_dir / "app.db"
        self._retention_days = retention_days

    def delete_task(self, task_id: str) -> int:
        if self._repository.get(task_id) is None:
            raise LookupError("任务不存在")

        freed_bytes = self._storage.task_size(task_id)
        self._repository.set_status(task_id, TaskStatus.DELETING)
        self._session.commit()
        self._storage.delete_task(task_id)
        self._repository.delete_with_dependents(task_id)
        self._session.commit()
        return freed_bytes

    def cleanup(self, *, now: datetime | None = None) -> CleanupResult:
        if self._retention_days is None:
            raise ValueError("未启用数据保留策略")
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=self._retention_days)
        deleted_tasks = 0
        freed_bytes = 0
        for task_id in self._repository.list_terminal_before(cutoff):
            freed_bytes += self.delete_task(task_id)
            deleted_tasks += 1
        return CleanupResult(deleted_tasks=deleted_tasks, freed_bytes=freed_bytes)

    def usage(self) -> DataUsage:
        database_bytes = self._database_path.stat().st_size if self._database_path.exists() else 0
        return DataUsage(
            task_count=self._repository.count(),
            task_bytes=self._storage.tasks_size(),
            database_bytes=database_bytes,
        )
