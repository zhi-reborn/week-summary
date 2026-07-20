from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from pydantic import TypeAdapter
from sqlalchemy.orm import Session, sessionmaker

from app.application.analysis_pipeline import AnalysisPipeline
from app.domain.enums import GenerationMode, TaskStatus
from app.domain.facts import Fact, FactKind, PersonExtraction, SourceRef
from app.domain.people import PersonSegment
from app.domain.review import GeneratedSection
from app.domain.template import RecognitionMethod, TemplateLocator, TemplateSection
from app.infrastructure.db.repositories import (
    ExportRepository,
    JobStepRepository,
    PeopleRepository,
    SectionVersionRepository,
    TaskRepository,
)
from app.infrastructure.files.task_storage import TaskStorage


@dataclass
class PipelineLLMStub:
    people_calls: list[str] = field(default_factory=list)
    section_calls: list[str] = field(default_factory=list)

    def extract_person(self, person: PersonSegment) -> PersonExtraction:
        self.people_calls.append(person.id)
        fact = Fact(
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
        return PersonExtraction(person_id=person.id, person_name=person.name, facts=[fact])

    def generate_section(
        self, section: TemplateSection, facts: list[Fact], instruction: str
    ) -> GeneratedSection:
        del instruction
        self.section_calls.append(section.id)
        return GeneratedSection(
            section_id=section.id,
            body="；".join(fact.text for fact in facts),
            fact_ids=[fact.id for fact in facts],
            source_ids=[f"{fact.id}:S1" for fact in facts],
        )


def test_pipeline_persists_all_resumable_stages(db_session: Session, tmp_path: Path) -> None:
    task = TaskRepository(db_session).create("第29周")
    PeopleRepository(db_session).replace_confirmed(
        task.id,
        [PersonSegment(id="P01", name="张三", line_start=1, line_end=2, content="完成A")],
    )
    section = TemplateSection(
        id="progress",
        name="本周进展",
        method=RecognitionMethod.PLACEHOLDER,
        confidence=1,
        locator=TemplateLocator(
            part="word/document.xml", paragraph_index=0, token="{{本周进展}}"
        ),
    )
    storage = TaskStorage(tmp_path)
    storage.write_result(
        task.id,
        "template_sections.json",
        TypeAdapter(list[TemplateSection]).dump_json([section]),
    )
    db_session.commit()
    llm = PipelineLLMStub()
    factory = sessionmaker(db_session.get_bind(), expire_on_commit=False)

    AnalysisPipeline(factory, storage, lambda: llm).run(task.id)

    with factory() as verification:
        steps = JobStepRepository(verification).list_for_task(task.id)
        assert {(step.step_type, step.entity_id, step.status) for step in steps} == {
            ("extract_person", "P01", "succeeded"),
            ("aggregate", "task", "succeeded"),
            ("generate_section", "progress", "succeeded"),
            ("quality_coverage", "task", "succeeded"),
        }
        assert SectionVersionRepository(verification).latest(task.id, "progress") is not None
    assert storage.read_result(task.id, "aggregation.json")
    assert storage.read_result(task.id, "coverage.json")


def test_direct_pipeline_exports_after_analysis(
    db_session: Session, tmp_path: Path, valid_docx_bytes: bytes
) -> None:
    task = TaskRepository(db_session).create("第29周", mode=GenerationMode.DIRECT)
    TaskRepository(db_session).set_status(task.id, TaskStatus.ANALYZING)
    PeopleRepository(db_session).replace_confirmed(
        task.id,
        [PersonSegment(id="P01", name="张三", line_start=1, line_end=2, content="完成A")],
    )
    section = TemplateSection(
        id="progress",
        name="本周重点",
        method=RecognitionMethod.PLACEHOLDER,
        confidence=1,
        locator=TemplateLocator(
            part="document", paragraph_index=0, token="{{本周重点}}"
        ),
    )
    storage = TaskStorage(tmp_path)
    storage.write_stream(
        task.id,
        "template.docx",
        BytesIO(valid_docx_bytes),
        len(valid_docx_bytes),
    )
    storage.write_result(
        task.id,
        "template_sections.json",
        TypeAdapter(list[TemplateSection]).dump_json([section]),
    )
    db_session.commit()
    factory = sessionmaker(db_session.get_bind(), expire_on_commit=False)

    AnalysisPipeline(factory, storage, PipelineLLMStub).run(task.id)

    with factory() as verification:
        assert TaskRepository(verification).get(task.id).status == TaskStatus.COMPLETED
        assert ExportRepository(verification).get(task.id) is not None
    assert storage.output_path(task.id, "weekly-report.docx").is_file()
