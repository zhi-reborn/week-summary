from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import TaskStatus
from app.domain.task import Task
from app.infrastructure.db.models import TaskRow


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, name: str) -> Task:
        row = TaskRow(id=str(uuid4()), name=name, status=TaskStatus.DRAFT.value)
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def get(self, task_id: str) -> Task | None:
        row = self._session.scalar(select(TaskRow).where(TaskRow.id == task_id))
        return self._to_domain(row) if row is not None else None

    def set_status(self, task_id: str, status: TaskStatus) -> Task:
        row = self._session.get(TaskRow, task_id)
        if row is None:
            raise LookupError("任务不存在")
        row.status = status.value
        self._session.flush()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: TaskRow) -> Task:
        return Task(
            id=row.id,
            name=row.name,
            status=TaskStatus(row.status),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
