from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from app.application.section_generation_service import (
    SectionGenerationService,
    section_allowed_kinds,
)
from app.domain.facts import Fact, FactKind, PersonExtraction, SourceRef
from app.domain.people import PersonSegment
from app.domain.review import GeneratedSection
from app.domain.template import RecognitionMethod, TemplateLocator, TemplateSection
from app.infrastructure.db.repositories import (
    FactRepository,
    PeopleRepository,
    SectionVersionRepository,
    TaskRepository,
)
from app.infrastructure.files.task_storage import TaskStorage


@dataclass
class SectionLLMStub:
    requests: list[tuple[TemplateSection, list[Fact], str]] = field(default_factory=list)

    def generate_section(
        self, section: TemplateSection, facts: list[Fact], instruction: str
    ) -> GeneratedSection:
        self.requests.append((section, facts, instruction))
        fact_ids = [fact.id for fact in facts]
        source_ids = [f"{fact.id}:S1" for fact in facts]
        return GeneratedSection(
            section_id=section.id,
            body="；".join(fact.text for fact in facts),
            fact_ids=fact_ids,
            source_ids=source_ids,
            unused_important_fact_ids=[],
            review_questions=[],
        )


def _section(section_id: str, name: str) -> TemplateSection:
    return TemplateSection(
        id=section_id,
        name=name,
        method=RecognitionMethod.PLACEHOLDER,
        confidence=1,
        locator=TemplateLocator(part="word/document.xml", paragraph_index=0, token="{{x}}"),
        instruction="",
        max_chars=1200,
    )


def _setup_task(session: Session, tmp_path: Path) -> str:
    task = TaskRepository(session).create("第29周")
    person = PersonSegment(id="P01", name="张三", line_start=1, line_end=2, content="完成A")
    PeopleRepository(session).replace_confirmed(task.id, [person])
    extraction = PersonExtraction(
        person_id="P01",
        person_name="张三",
        facts=[
            Fact(
                id="F-RISK",
                kind=FactKind.RISK,
                topic="资源不足",
                text="资源不足",
                sources=[SourceRef(person_id="P01", line_start=2, line_end=2, quote="资源不足")],
                confidence=0.9,
            ),
            Fact(
                id="F-DONE",
                kind=FactKind.COMPLETED,
                topic="交付",
                text="完成A",
                sources=[SourceRef(person_id="P01", line_start=2, line_end=2, quote="完成A")],
                confidence=0.9,
            ),
        ],
    )
    FactRepository(session).replace_person_facts(task.id, extraction)
    session.commit()
    TaskStorage(tmp_path).write_result(
        task.id,
        "template_sections.json",
        b"[]",
    )
    return task.id


def test_section_generation_receives_only_relevant_facts(
    db_session: Session, tmp_path: Path
) -> None:
    task_id = _setup_task(db_session, tmp_path)
    section = _section("risk", "风险与问题")
    llm = SectionLLMStub()

    service = SectionGenerationService(db_session, TaskStorage(tmp_path), llm)
    service.generate(task_id, section)

    assert {fact.kind for fact in llm.requests[0][1]} <= {
        FactKind.RISK,
        FactKind.HELP_NEEDED,
    }


def test_loads_section_by_id_from_confirmed_template(
    db_session: Session, tmp_path: Path
) -> None:
    task_id = _setup_task(db_session, tmp_path)
    section = _section("risk", "风险与问题")
    TaskStorage(tmp_path).write_result(
        task_id,
        "template_sections.json",
        TypeAdapter(list[TemplateSection]).dump_json([section]),
    )
    llm = SectionLLMStub()

    SectionGenerationService(db_session, TaskStorage(tmp_path), llm).generate(task_id, "risk")

    assert llm.requests[0][0].id == "risk"


def test_retrying_one_section_keeps_other_versions(
    db_session: Session, tmp_path: Path
) -> None:
    task_id = _setup_task(db_session, tmp_path)
    llm = SectionLLMStub()
    service = SectionGenerationService(db_session, TaskStorage(tmp_path), llm)
    service.generate(task_id, _section("progress", "本周进展"))
    service.generate(task_id, _section("risk", "风险与问题"))
    before = SectionVersionRepository(db_session).latest(task_id, "progress")

    service.regenerate(task_id, _section("risk", "风险与问题"), "更精炼")

    assert SectionVersionRepository(db_session).latest(task_id, "progress") == before
    assert SectionVersionRepository(db_session).latest(task_id, "risk").version == 2


class CrossFactSourceStub(SectionLLMStub):
    def generate_section(
        self, section: TemplateSection, facts: list[Fact], instruction: str
    ) -> GeneratedSection:
        del instruction
        return GeneratedSection(
            section_id=section.id,
            body="资源不足",
            fact_ids=["F-RISK"],
            source_ids=["F-DONE:S1"],
            unused_important_fact_ids=[],
            review_questions=[],
        )


def test_rejects_source_from_fact_not_used_by_section(
    db_session: Session, tmp_path: Path
) -> None:
    task_id = _setup_task(db_session, tmp_path)
    service = SectionGenerationService(
        db_session, TaskStorage(tmp_path), CrossFactSourceStub()
    )

    with pytest.raises(ValueError, match="来源"):
        service.generate(task_id, _section("all", "综合情况"))


def _overview_section() -> TemplateSection:
    return TemplateSection(
        id="S01",
        name="本周工作概述 / 业务连续性",
        method=RecognitionMethod.PLACEHOLDER,
        confidence=1,
        locator=TemplateLocator(part="word/document.xml", paragraph_index=0, token="{{x}}"),
        instruction="概述本周扩容、迁移、升级、演练等工作成果及风险收敛情况。",
        max_chars=1200,
    )


def test_overview_section_aggregates_all_fact_kinds() -> None:
    # S01 is an overview section; its instruction mentions "风险" but it should
    # aggregate every fact kind, not be misclassified as risk-only.
    assert section_allowed_kinds(_overview_section()) == set(FactKind)
