import logging
import re
from typing import Protocol

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

_logger = logging.getLogger(__name__)

# Strip fact IDs like (P01-F01) or (P01-F01, P02-F03) that the model may
# erroneously embed in the generated body text.
_FACT_ID_REF_PATTERN = re.compile(
    r"\s*[（(]P\d+-F\d+(?:[，,\s]*P\d+-F\d+)*[）)]\s*"
)

from app.application.quality_service import QualityService
from app.domain.facts import Fact, FactKind, SourceRef
from app.domain.review import GeneratedSection, SectionVersion
from app.domain.template import TemplateSection
from app.infrastructure.db.repositories import (
    FactRepository,
    PeopleRepository,
    QualityFindingRepository,
    SectionVersionRepository,
)
from app.infrastructure.files.task_storage import TaskStorage


class SectionGenerator(Protocol):
    def generate_section(
        self, section: TemplateSection, facts: list[Fact], instruction: str
    ) -> GeneratedSection: ...


class SectionGenerationService:
    def __init__(
        self,
        session: Session,
        storage: TaskStorage,
        llm: SectionGenerator,
        quality: QualityService | None = None,
    ) -> None:
        self._session = session
        self._storage = storage
        self._llm = llm
        self._quality = quality or QualityService()

    def generate(
        self, task_id: str, section: TemplateSection | str, instruction: str = ""
    ) -> SectionVersion:
        if isinstance(section, str):
            section = self._load_section(task_id, section)
        all_facts = FactRepository(self._session).list_by_task(task_id)
        candidates = [fact for fact in all_facts if fact.kind in section_allowed_kinds(section)]
        generated = self._llm.generate_section(section, candidates, instruction)
        generated = _clean_body_fact_refs(generated)
        self._validate_generated(task_id, section, candidates, generated)

        facts_by_id = {fact.id: fact for fact in candidates}
        selected = [facts_by_id[fact_id] for fact_id in generated.fact_ids]
        source_map = _source_map(candidates)
        sources = [source_map[source_id] for source_id in generated.source_ids]
        metrics = [metric for fact in selected for metric in fact.metrics]
        people = PeopleRepository(self._session).list_confirmed(task_id)
        findings = self._quality.check_text(
            generated.body,
            {person.name for person in people},
            sources,
            metrics,
        )
        level = self._quality.level(
            findings,
            required_section_empty=section.required and not generated.body.strip(),
        )
        version = SectionVersionRepository(self._session).save(
            task_id, generated, level.value, instruction
        )
        QualityFindingRepository(self._session).save_for_version(
            task_id, version.id, findings
        )
        self._session.commit()
        return version

    def regenerate(
        self, task_id: str, section: TemplateSection | str, instruction: str
    ) -> SectionVersion:
        return self.generate(task_id, section, instruction)

    def _load_section(self, task_id: str, section_id: str) -> TemplateSection:
        sections = _SECTIONS_ADAPTER.validate_json(
            self._storage.read_result(task_id, "template_sections.json")
        )
        for section in sections:
            if section.id == section_id:
                return section
        raise LookupError("模板板块不存在")

    @staticmethod
    def _validate_generated(
        task_id: str,
        section: TemplateSection,
        candidates: list[Fact],
        generated: GeneratedSection,
    ) -> None:
        if generated.section_id != section.id:
            raise ValueError("模型返回的板块 ID 不一致")
        if len(generated.body) > section.max_chars:
            _logger.warning(
                "section %s body truncated from %d to %d chars",
                section.id, len(generated.body), section.max_chars,
            )
            generated.body = generated.body[: section.max_chars]
        fact_ids = {fact.id for fact in candidates}
        if not set(generated.fact_ids) <= fact_ids:
            raise ValueError("生成结果引用了当前板块候选集以外的事实")
        if not set(generated.unused_important_fact_ids) <= fact_ids:
            raise ValueError("未使用事实列表包含未知事实")
        selected = [fact for fact in candidates if fact.id in generated.fact_ids]
        if not set(generated.source_ids) <= set(_source_map(selected)):
            raise ValueError("生成结果引用了未知来源")


def section_allowed_kinds(section: TemplateSection) -> set[FactKind]:
    if section.allowed_fact_kinds:
        return set(section.allowed_fact_kinds)
    if "概述" in section.name:
        return set(FactKind)
    text = f"{section.name} {section.instruction}".casefold()
    if any(keyword in text for keyword in ("风险", "问题", "求助", "阻塞")):
        return {FactKind.RISK, FactKind.HELP_NEEDED}
    if any(keyword in text for keyword in ("下周", "计划")):
        return {FactKind.NEXT_PLAN, FactKind.MILESTONE}
    if any(keyword in text for keyword in ("进展", "成果", "完成", "重点")):
        return {
            FactKind.COMPLETED,
            FactKind.IN_PROGRESS,
            FactKind.RESULT,
            FactKind.MILESTONE,
        }
    return set(FactKind)


def _clean_body_fact_refs(generated: GeneratedSection) -> GeneratedSection:
    body = _FACT_ID_REF_PATTERN.sub("", generated.body)
    if body != generated.body:
        _logger.warning(
            "section %s body contained embedded fact IDs; stripped %d chars",
            generated.section_id, len(generated.body) - len(body),
        )
    return generated.model_copy(update={"body": body})


def _source_map(facts: list[Fact]) -> dict[str, SourceRef]:
    return {
        f"{fact.id}:S{index}": source
        for fact in facts
        for index, source in enumerate(fact.sources, start=1)
    }


_SECTIONS_ADAPTER = TypeAdapter(list[TemplateSection])
