from collections.abc import Callable
from typing import Protocol

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from app.application.aggregation_service import AggregationService
from app.application.analysis_service import AnalysisService, PersonExtractor
from app.application.quality_service import QualityService
from app.application.section_generation_service import (
    SectionGenerationService,
    SectionGenerator,
    section_allowed_kinds,
)
from app.domain.quality import CoverageCell
from app.domain.template import TemplateSection
from app.infrastructure.db.repositories import (
    FactRepository,
    PeopleRepository,
    SectionVersionRepository,
)
from app.infrastructure.files.task_storage import TaskStorage
from app.infrastructure.jobs.steps import run_persisted_step


class AnalysisLLM(PersonExtractor, SectionGenerator, Protocol):
    pass


class AnalysisPipeline:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        storage: TaskStorage,
        llm_factory: Callable[[], AnalysisLLM],
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._llm_factory = llm_factory

    def run(self, task_id: str) -> None:
        llm = self._llm_factory()
        with self._session_factory() as session:
            AnalysisService(session, llm).extract_people(task_id)
        self._aggregate(task_id)
        sections = self._load_sections(task_id)
        for section in sections:
            self._generate_section(task_id, section, llm)
        self._build_coverage(task_id, sections)

    def _aggregate(self, task_id: str) -> None:
        with self._session_factory() as session:

            def aggregate() -> None:
                facts = FactRepository(session).list_by_task(task_id)
                result = AggregationService().aggregate(facts)
                self._storage.write_result(
                    task_id, "aggregation.json", result.model_dump_json(indent=2).encode()
                )

            run_persisted_step(session, task_id, "aggregate", "task", aggregate)

    def _generate_section(
        self, task_id: str, section: TemplateSection, llm: AnalysisLLM
    ) -> None:
        with self._session_factory() as session:
            service = SectionGenerationService(session, self._storage, llm)
            run_persisted_step(
                session,
                task_id,
                "generate_section",
                section.id,
                lambda: service.generate(task_id, section, section.instruction),
            )

    def _build_coverage(self, task_id: str, sections: list[TemplateSection]) -> None:
        with self._session_factory() as session:

            def build() -> None:
                people = PeopleRepository(session).list_confirmed(task_id)
                facts = FactRepository(session).list_by_task(task_id)
                versions = {
                    section.id: SectionVersionRepository(session).latest(task_id, section.id)
                    for section in sections
                }
                cells = QualityService().build_coverage(
                    person_ids=[person.id for person in people],
                    section_ids=[section.id for section in sections],
                    facts=facts,
                    section_fact_ids={
                        section_id: set(version.generated.fact_ids)
                        for section_id, version in versions.items()
                        if version is not None
                    },
                    section_kinds={
                        section.id: section_allowed_kinds(section) for section in sections
                    },
                )
                self._storage.write_result(
                    task_id, "coverage.json", _COVERAGE_ADAPTER.dump_json(cells)
                )

            run_persisted_step(session, task_id, "quality_coverage", "task", build)

    def _load_sections(self, task_id: str) -> list[TemplateSection]:
        return _SECTIONS_ADAPTER.validate_json(
            self._storage.read_result(task_id, "template_sections.json")
        )


_SECTIONS_ADAPTER = TypeAdapter(list[TemplateSection])
_COVERAGE_ADAPTER = TypeAdapter(list[CoverageCell])
