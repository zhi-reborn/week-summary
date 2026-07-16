from dataclasses import dataclass, field

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.analysis_service import AnalysisService
from app.domain.facts import Fact, FactKind, PersonExtraction, SourceRef
from app.domain.people import PersonSegment
from app.infrastructure.db.repositories import (
    FactRepository,
    JobStepRepository,
    PeopleRepository,
    TaskRepository,
)


@dataclass
class FailingSecondLLM:
    calls: list[str] = field(default_factory=list)

    def extract_person(self, person: PersonSegment) -> PersonExtraction:
        self.calls.append(person.id)
        if person.id == "P02":
            raise RuntimeError("model failed")
        return PersonExtraction(
            person_id=person.id,
            person_name=person.name,
            facts=[
                Fact(
                    id="P01-F01",
                    kind=FactKind.COMPLETED,
                    topic="交付",
                    text="完成A",
                    sources=[
                        SourceRef(
                            person_id="P01",
                            line_start=2,
                            line_end=2,
                            quote="完成A",
                        )
                    ],
                    confidence=0.9,
                )
            ],
        )


def test_person_failure_keeps_prior_person_facts(db_session: Session) -> None:
    task = TaskRepository(db_session).create("第29周")
    PeopleRepository(db_session).replace_confirmed(
        task.id,
        [
            PersonSegment(id="P01", name="张三", line_start=1, line_end=2, content="完成A"),
            PersonSegment(id="P02", name="李四", line_start=4, line_end=5, content="完成B"),
        ],
    )
    db_session.commit()

    with pytest.raises(RuntimeError, match="model failed"):
        AnalysisService(db_session, FailingSecondLLM()).extract_people(task.id)

    db_session.expire_all()
    assert [fact.id for fact in FactRepository(db_session).list_by_person(task.id, "P01")] == [
        "P01-F01"
    ]
    assert JobStepRepository(db_session).get(task.id, "extract_person", "P01").status == "succeeded"
    assert JobStepRepository(db_session).get(task.id, "extract_person", "P02").status == "failed"


def test_job_step_status_is_constrained_by_database(db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO job_steps "
                "(id, task_id, step_type, entity_id, status, updated_at) "
                "VALUES ('s1', 't1', 'extract_person', 'P01', 'unknown', CURRENT_TIMESTAMP)"
            )
        )
        db_session.flush()
