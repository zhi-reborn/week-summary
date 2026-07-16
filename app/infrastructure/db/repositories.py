from uuid import uuid4

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

    @staticmethod
    def _to_domain(row: TaskRow) -> Task:
        return Task(
            id=row.id,
            name=row.name,
            status=TaskStatus(row.status),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

