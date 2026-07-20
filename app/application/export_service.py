from collections.abc import Callable
from datetime import date

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from app.domain.enums import GenerationMode, TaskStatus
from app.domain.export import ExportRecord
from app.domain.template import TemplateSection
from app.infrastructure.db.repositories import (
    ExportRepository,
    SectionReviewRepository,
    SectionVersionRepository,
    TaskRepository,
)
from app.infrastructure.docx.locator import package_part_name
from app.infrastructure.docx.package_diff import compare_packages
from app.infrastructure.docx.validator import validate_docx
from app.infrastructure.docx.writer import DocxWriteError, write_sections
from app.infrastructure.files.task_storage import TaskStorage
from app.infrastructure.jobs.state_machine import transition

_SECTIONS_ADAPTER = TypeAdapter(list[TemplateSection])
_STORED_NAME = "weekly-report.docx"


class ExportError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class UnconfirmedSections(ExportError):
    def __init__(self) -> None:
        super().__init__("UNCONFIRMED_SECTIONS", "请先确认全部汇总板块")


class ExportService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        storage: TaskStorage,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage

    def export(self, task_id: str) -> ExportRecord:
        sections = _SECTIONS_ADAPTER.validate_json(
            self._storage.read_result(task_id, "template_sections.json")
        )
        values = self._load_values(task_id, sections)
        self._mark_exporting(task_id)

        template_path = self._storage.input_path(task_id, "template.docx")
        output_path = self._storage.output_path(task_id, _STORED_NAME, create=True)
        try:
            write_sections(template_path, output_path, values)
            validation = validate_docx(output_path, expected_sections=set(values))
            if not validation.valid:
                raise ExportError(
                    "DOCX_VALIDATION_FAILED",
                    f"生成文件校验失败：{', '.join(validation.errors)}",
                )
            allowed_parts = {
                package_part_name(section.locator.part) for section in sections
            }
            package_diff = compare_packages(
                template_path,
                output_path,
                allowed_changed_parts=allowed_parts,
            )
            if package_diff.unexpected_changed_parts:
                changed = ", ".join(sorted(package_diff.unexpected_changed_parts))
                raise ExportError(
                    "TEMPLATE_FIDELITY_FAILED",
                    f"模板非目标区域发生变化：{changed}",
                )
            return self._record_success(task_id)
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            self._mark_failed(task_id)
            if isinstance(exc, ExportError):
                raise
            if isinstance(exc, DocxWriteError):
                raise ExportError(exc.code, str(exc)) from exc
            raise ExportError("EXPORT_FAILED", "生成 Word 文件失败") from exc

    def _load_values(
        self, task_id: str, sections: list[TemplateSection]
    ) -> dict[str, str]:
        with self._session_factory() as session:
            task = TaskRepository(session).get(task_id)
            if task is None:
                raise LookupError("任务不存在")
            if task.mode == GenerationMode.REVIEW:
                reviews = SectionReviewRepository(session)
                values: dict[str, str] = {}
                for section in sections:
                    review = reviews.latest(task_id, section.id)
                    if section.required and (review is None or not review.confirmed):
                        raise UnconfirmedSections()
                    if review is not None:
                        values[section.name] = review.content
                        continue
                    version = SectionVersionRepository(session).latest(task_id, section.id)
                    if version is None:
                        raise ExportError(
                            "SECTION_CONTENT_MISSING", "汇总板块内容尚未生成"
                        )
                    values[section.name] = version.generated.body
                return values

            versions = SectionVersionRepository(session)
            direct_values: dict[str, str] = {}
            for section in sections:
                version = versions.latest(task_id, section.id)
                if version is None:
                    raise ExportError("SECTION_CONTENT_MISSING", "汇总板块内容尚未生成")
                direct_values[section.name] = version.generated.body
            return direct_values

    def _mark_exporting(self, task_id: str) -> None:
        with self._session_factory() as session:
            tasks = TaskRepository(session)
            task = tasks.get(task_id)
            if task is None:
                raise LookupError("任务不存在")
            tasks.set_status(task_id, transition(task.status, TaskStatus.EXPORTING))
            session.commit()

    def _record_success(self, task_id: str) -> ExportRecord:
        with self._session_factory() as session:
            record = ExportRepository(session).save(
                task_id,
                _STORED_NAME,
                f"周报汇总_{date.today().isoformat()}.docx",
            )
            tasks = TaskRepository(session)
            task = tasks.get(task_id)
            if task is None:
                raise LookupError("任务不存在")
            tasks.set_status(task_id, transition(task.status, TaskStatus.COMPLETED))
            session.commit()
            return record

    def _mark_failed(self, task_id: str) -> None:
        with self._session_factory() as session:
            tasks = TaskRepository(session)
            task = tasks.get(task_id)
            if task is not None and task.status == TaskStatus.EXPORTING:
                tasks.set_status(
                    task_id, transition(task.status, TaskStatus.EXPORT_FAILED)
                )
                session.commit()
