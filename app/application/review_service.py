from dataclasses import dataclass

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from app.domain.enums import TaskStatus
from app.domain.review import SectionReview, SectionVersion
from app.domain.template import TemplateSection
from app.application.section_generation_service import SectionGenerationService, SectionGenerator
from app.infrastructure.db.repositories import (
    FactRepository,
    PeopleRepository,
    SectionReviewRepository,
    SectionVersionRepository,
    TaskRepository,
)
from app.infrastructure.files.task_storage import TaskStorage


class ReviewNotReady(ValueError):
    pass


@dataclass(frozen=True)
class ReviewSectionData:
    section: TemplateSection
    review: SectionReview
    generated: SectionVersion


@dataclass(frozen=True)
class ReviewSource:
    source_id: str
    fact_id: str
    person_id: str
    person: str
    line_start: int
    line_end: int
    excerpt: str


class ReviewService:
    def __init__(self, session: Session, storage: TaskStorage) -> None:
        self._session = session
        self._storage = storage

    def list_sections(self, task_id: str) -> list[ReviewSectionData]:
        return [self._get_data(task_id, section) for section in self._sections(task_id)]

    def get_section(self, task_id: str, section_key: str) -> ReviewSectionData:
        return self._get_data(task_id, self._section(task_id, section_key))

    def update_section(
        self, task_id: str, section_key: str, content: str, editor: str
    ) -> ReviewSectionData:
        self._require_editable(task_id)
        current = self.get_section(task_id, section_key)
        if not content.strip():
            raise ValueError("板块内容不能为空")
        saved = SectionReviewRepository(self._session).save(
            task_id, current.review.revise(content, editor)
        )
        return ReviewSectionData(current.section, saved, current.generated)

    def confirm_section(
        self, task_id: str, section_key: str, editor: str
    ) -> ReviewSectionData:
        self._require_editable(task_id)
        current = self.get_section(task_id, section_key)
        saved = SectionReviewRepository(self._session).save(
            task_id, current.review.confirm(editor)
        )
        return ReviewSectionData(current.section, saved, current.generated)

    def restore_section(
        self, task_id: str, section_key: str, revision: int, editor: str
    ) -> ReviewSectionData:
        self._require_editable(task_id)
        current = self.get_section(task_id, section_key)
        historical = SectionReviewRepository(self._session).get_revision(
            task_id, section_key, revision
        )
        if historical is None:
            raise LookupError("校审版本不存在")
        saved = SectionReviewRepository(self._session).save(
            task_id, current.review.revise(historical.content, editor)
        )
        return ReviewSectionData(current.section, saved, current.generated)

    def list_versions(self, task_id: str, section_key: str) -> list[ReviewSectionData]:
        current = self.get_section(task_id, section_key)
        versions = SectionReviewRepository(self._session).list_versions(task_id, section_key)
        return [ReviewSectionData(current.section, item, current.generated) for item in versions]

    def list_sources(self, task_id: str, section_key: str) -> list[ReviewSource]:
        current = self.get_section(task_id, section_key)
        facts = {fact.id: fact for fact in FactRepository(self._session).list_by_task(task_id)}
        people = {
            person.id: person.name
            for person in PeopleRepository(self._session).list_confirmed(task_id)
        }
        results: list[ReviewSource] = []
        for source_id in current.generated.generated.source_ids:
            fact_id, separator, source_number = source_id.rpartition(":S")
            fact = facts.get(fact_id)
            if not separator or fact is None or not source_number.isdigit():
                continue
            index = int(source_number) - 1
            if not 0 <= index < len(fact.sources):
                continue
            source = fact.sources[index]
            results.append(
                ReviewSource(
                    source_id=source_id,
                    fact_id=fact_id,
                    person_id=source.person_id,
                    person=people.get(source.person_id, source.person_id),
                    line_start=source.line_start,
                    line_end=source.line_end,
                    excerpt=source.quote,
                )
            )
        return results

    def regenerate_section(
        self,
        task_id: str,
        section_key: str,
        instruction: str,
        generator: SectionGenerator,
        editor: str,
    ) -> ReviewSectionData:
        self._require_editable(task_id)
        current = self.get_section(task_id, section_key)
        generated = SectionGenerationService(
            self._session, self._storage, generator
        ).regenerate(task_id, current.section, instruction)
        saved = SectionReviewRepository(self._session).save(
            task_id, current.review.revise(generated.generated.body, editor)
        )
        return ReviewSectionData(current.section, saved, generated)

    def _get_data(self, task_id: str, section: TemplateSection) -> ReviewSectionData:
        generated = SectionVersionRepository(self._session).latest(task_id, section.id)
        if generated is None:
            raise LookupError("板块尚未生成")
        reviews = SectionReviewRepository(self._session)
        review = reviews.latest(task_id, section.id)
        if review is None:
            review = reviews.save(
                task_id,
                SectionReview(
                    section_key=section.id,
                    revision=1,
                    content=generated.generated.body,
                ),
            )
        return ReviewSectionData(section, review, generated)

    def _section(self, task_id: str, section_key: str) -> TemplateSection:
        for section in self._sections(task_id):
            if section.id == section_key:
                return section
        raise LookupError("模板板块不存在")

    def _sections(self, task_id: str) -> list[TemplateSection]:
        self._require_task(task_id)
        try:
            data = self._storage.read_result(task_id, "template_sections.json")
        except FileNotFoundError as exc:
            raise LookupError("模板板块不存在") from exc
        return _SECTIONS_ADAPTER.validate_json(data)

    def _require_task(self, task_id: str) -> None:
        if TaskRepository(self._session).get(task_id) is None:
            raise LookupError("任务不存在")

    def _require_editable(self, task_id: str) -> None:
        task = TaskRepository(self._session).get(task_id)
        if task is None:
            raise LookupError("任务不存在")
        if task.status != TaskStatus.REVIEW:
            raise ReviewNotReady("分析尚未完成，当前不能编辑")


_SECTIONS_ADAPTER = TypeAdapter(list[TemplateSection])
