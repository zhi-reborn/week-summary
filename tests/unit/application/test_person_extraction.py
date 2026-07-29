from dataclasses import dataclass, field

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


@dataclass
class DriftingLLM:
    def extract_person(self, person: PersonSegment) -> PersonExtraction:
        return PersonExtraction(
            person_id="P99",
            person_name="错误姓名",
            facts=[
                Fact(
                    id="F1",
                    kind=FactKind.COMPLETED,
                    topic="交付",
                    text=person.content,
                    sources=[
                        SourceRef(
                            person_id="P99",
                            line_start=person.line_start + 1,
                            line_end=person.line_end,
                            quote=person.content,
                        )
                    ],
                    confidence=0.9,
                ),
                Fact(
                    id="F2",
                    kind=FactKind.NEXT_PLAN,
                    topic="计划",
                    text="继续推进",
                    sources=[
                        SourceRef(
                            person_id="P99",
                            line_start=person.line_start + 1,
                            line_end=person.line_end,
                            quote=person.content,
                        )
                    ],
                    confidence=0.8,
                ),
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


def test_binds_model_metadata_to_current_person(db_session: Session) -> None:
    task_id = _task_with_two_people(db_session)

    AnalysisService(db_session, DriftingLLM()).extract_people(task_id)

    for person_id in ("P01", "P02"):
        facts = FactRepository(db_session).list_by_person(task_id, person_id)
        assert [fact.id for fact in facts] == [
            f"{person_id}-F01",
            f"{person_id}-F02",
        ]
        assert {
            source.person_id for fact in facts for source in fact.sources
        } == {person_id}
        step = JobStepRepository(db_session).get(task_id, "extract_person", person_id)
        assert step is not None
        assert step.status == "succeeded"
