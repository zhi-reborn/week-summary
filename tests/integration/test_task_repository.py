from sqlalchemy.orm import Session

from app.domain.enums import TaskStatus
from app.infrastructure.db.repositories import TaskRepository


def test_repository_creates_task(db_session: Session) -> None:
    task = TaskRepository(db_session).create("第29周周报")

    assert task.name == "第29周周报"
    assert task.status is TaskStatus.DRAFT

