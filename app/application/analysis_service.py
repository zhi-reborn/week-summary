from typing import Protocol

from sqlalchemy.orm import Session

from app.domain.facts import PersonExtraction
from app.domain.people import PersonSegment
from app.infrastructure.db.repositories import FactRepository, JobStepRepository, PeopleRepository


class PersonExtractor(Protocol):
    def extract_person(self, person: PersonSegment) -> PersonExtraction: ...


class AnalysisService:
    def __init__(self, session: Session, llm: PersonExtractor) -> None:
        self._session = session
        self._llm = llm

    def extract_people(self, task_id: str) -> None:
        people = PeopleRepository(self._session).list_confirmed(task_id)
        if not people:
            raise LookupError("没有已确认人员")
        for person in people:
            steps = JobStepRepository(self._session)
            step = steps.get_or_create(task_id, "extract_person", person.id)
            if step.status == "succeeded":
                continue
            steps.mark_running(step.id)
            self._session.commit()
            try:
                extraction = self._bind_person(person, self._llm.extract_person(person))
                self._validate_person(person, extraction)
                FactRepository(self._session).replace_person_facts(task_id, extraction)
                JobStepRepository(self._session).mark_succeeded(step.id)
                self._session.commit()
            except Exception as exc:
                self._session.rollback()
                current = JobStepRepository(self._session).get(
                    task_id, "extract_person", person.id
                )
                if current is None:
                    raise
                JobStepRepository(self._session).mark_failed(
                    current.id, getattr(exc, "code", "PERSON_EXTRACTION_FAILED")
                )
                self._session.commit()
                raise

    @staticmethod
    def _bind_person(
        person: PersonSegment, extraction: PersonExtraction
    ) -> PersonExtraction:
        facts = [
            fact.model_copy(
                update={
                    "id": f"{person.id}-F{index:02d}",
                    "sources": [
                        source.model_copy(update={"person_id": person.id})
                        for source in fact.sources
                    ],
                }
            )
            for index, fact in enumerate(extraction.facts, start=1)
        ]
        return PersonExtraction(
            person_id=person.id,
            person_name=person.name,
            facts=facts,
        )

    @staticmethod
    def _validate_person(person: PersonSegment, extraction: PersonExtraction) -> None:
        if extraction.person_id != person.id or extraction.person_name != person.name:
            raise ValueError("模型返回的人员身份与请求不一致")
        if any(source.person_id != person.id for fact in extraction.facts for source in fact.sources):
            raise ValueError("事实来源人员与当前人员不一致")
