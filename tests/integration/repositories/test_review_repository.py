import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.review import SectionReview
from app.infrastructure.db.repositories import SectionReviewRepository, TaskRepository


def test_reads_latest_review_and_immutable_history(db_session: Session) -> None:
    task = TaskRepository(db_session).create("第29周")
    repository = SectionReviewRepository(db_session)
    first = SectionReview(section_key="progress", revision=1, content="旧内容")
    second = first.revise("新内容", editor="local-user")

    repository.save(task.id, first)
    repository.save(task.id, second)
    db_session.commit()

    assert repository.latest(task.id, "progress").content == "新内容"
    assert [item.revision for item in repository.list_versions(task.id, "progress")] == [2, 1]
    assert repository.get_revision(task.id, "progress", 1).content == "旧内容"


def test_rejects_duplicate_review_revision(db_session: Session) -> None:
    task = TaskRepository(db_session).create("第29周")
    repository = SectionReviewRepository(db_session)
    review = SectionReview(section_key="risk", revision=1, content="风险 A")
    repository.save(task.id, review)
    db_session.commit()

    with pytest.raises(IntegrityError):
        repository.save(task.id, review)
