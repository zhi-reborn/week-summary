from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.application.analysis_service import AnalysisService
from app.domain.facts import Fact, FactKind, PersonExtraction, SourceRef
from app.domain.people import PersonSegment
from app.infrastructure.db.repositories import (
    JobStepRepository,
    PeopleRepository,
    TaskRepository,
)


@dataclass
class LLMStub:
    calls: list[str] = field(default_factory=list)

    def extract_person(self, person: PersonSegment) -> PersonExtraction:
        self.calls.append(person.id)
        return PersonExtraction(
            person_id=person.id,
            person_name=person.name,
            facts=[
                Fact(
                    id=f"{person.id}-F01",
                    kind=FactKind.COMPLETED,
                    topic="交付",
                    text=person.content,
                    sources=[
                        SourceRef(
                            person_id=person.id,
                            line_start=person.line_start,
                            line_end=person.line_end,
                            quote=person.content,
                        )
                    ],
                    confidence=0.9,
                )
            ],
        )


def _task_with_two_people(session: Session) -> str:
    task = TaskRepository(session).create("第29周")
    PeopleRepository(session).replace_confirmed(
        task.id,
        [
            PersonSegment(id="P01", name="张三", line_start=1, line_end=2, content="完成A"),
            PersonSegment(id="P02", name="李四", line_start=4, line_end=5, content="完成B"),
        ],
    )
    session.commit()
    return task.id


def test_extracts_each_person_separately(db_session: Session) -> None:
    task_id = _task_with_two_people(db_session)
    llm = LLMStub()

    AnalysisService(db_session, llm).extract_people(task_id)

    assert llm.calls == ["P01", "P02"]


def test_skips_already_completed_person_step(db_session: Session) -> None:
    task_id = _task_with_two_people(db_session)
    steps = JobStepRepository(db_session)
    step = steps.get_or_create(task_id, "extract_person", "P01")
    steps.mark_succeeded(step.id)
    db_session.commit()
    llm = LLMStub()

    AnalysisService(db_session, llm).extract_people(task_id)

    assert llm.calls == ["P02"]
