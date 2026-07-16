from dataclasses import dataclass, field

from sqlalchemy.orm import Session, sessionmaker

from app.application.analysis_service import AnalysisService
from app.domain.enums import TaskStatus
from app.domain.facts import PersonExtraction
from app.domain.people import PersonSegment
from app.infrastructure.db.repositories import (
    AnalysisJobRepository,
    JobStepRepository,
    PeopleRepository,
    TaskRepository,
)
from app.infrastructure.jobs.runner import AnalysisRunner


@dataclass
class RecordingLLM:
    calls: list[str] = field(default_factory=list)

    def extract_person(self, person: PersonSegment) -> PersonExtraction:
        self.calls.append(person.id)
        return PersonExtraction(person_id=person.id, person_name=person.name, facts=[])


class ExtractionProcessor:
    def __init__(self, factory: sessionmaker[Session], llm: RecordingLLM) -> None:
        self._factory = factory
        self._llm = llm

    def run(self, task_id: str) -> None:
        with self._factory() as session:
            AnalysisService(session, self._llm).extract_people(task_id)


def test_restart_resumes_first_failed_person_step(db_session: Session) -> None:
    task = TaskRepository(db_session).create("第29周")
    PeopleRepository(db_session).replace_confirmed(
        task.id,
        [
            PersonSegment(id="P01", name="张三", line_start=1, line_end=2, content="完成A"),
            PersonSegment(id="P02", name="李四", line_start=4, line_end=5, content="完成B"),
        ],
    )
    steps = JobStepRepository(db_session)
    p01 = steps.get_or_create(task.id, "extract_person", "P01")
    steps.mark_succeeded(p01.id)
    p02 = steps.get_or_create(task.id, "extract_person", "P02")
    steps.mark_failed(p02.id, "MODEL_TIMEOUT")
    TaskRepository(db_session).set_status(task.id, TaskStatus.FAILED)
    AnalysisJobRepository(db_session).create_failed(task.id, "MODEL_TIMEOUT")
    db_session.commit()

    factory = sessionmaker(db_session.get_bind(), expire_on_commit=False)
    llm = RecordingLLM()
    runner = AnalysisRunner(factory, ExtractionProcessor(factory, llm))
    runner.retry(task.id)
    runner.run_once()

    assert llm.calls == ["P02"]
    with factory() as verification:
        assert TaskRepository(verification).get(task.id).status == TaskStatus.REVIEW


def test_interrupted_running_job_is_requeued_on_recovery(db_session: Session) -> None:
    task = TaskRepository(db_session).create("第29周")
    TaskRepository(db_session).set_status(task.id, TaskStatus.ANALYZING)
    jobs = AnalysisJobRepository(db_session)
    jobs.enqueue(task.id)
    jobs.claim_next("old-process")
    db_session.commit()
    factory = sessionmaker(db_session.get_bind(), expire_on_commit=False)

    AnalysisRunner(factory, ExtractionProcessor(factory, RecordingLLM())).recover()

    with factory() as verification:
        assert AnalysisJobRepository(verification).get(task.id).status == "queued"
