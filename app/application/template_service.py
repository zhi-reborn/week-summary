from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from app.domain.enums import TaskStatus
from app.domain.task import Task
from app.domain.template import TemplateSection
from app.infrastructure.db.repositories import TaskRepository
from app.infrastructure.docx.package_guard import inspect_docx_package
from app.infrastructure.docx.template_parser import parse_template
from app.infrastructure.files.task_storage import TaskStorage

_SECTIONS_ADAPTER = TypeAdapter(list[TemplateSection])


class TemplateService:
    def __init__(
        self,
        session: Session,
        storage: TaskStorage,
        *,
        max_docx_entries: int = 2000,
        max_docx_uncompressed_bytes: int = 100 * 1024 * 1024,
        max_docx_compression_ratio: int = 100,
    ) -> None:
        self._repository = TaskRepository(session)
        self._storage = storage
        self._max_docx_entries = max_docx_entries
        self._max_docx_uncompressed_bytes = max_docx_uncompressed_bytes
        self._max_docx_compression_ratio = max_docx_compression_ratio

    def detect(self, task_id: str) -> list[TemplateSection]:
        self._require_task(task_id)
        template_bytes = self._storage.read_input(task_id, "template.docx")
        inspect_docx_package(
            template_bytes,
            max_entries=self._max_docx_entries,
            max_uncompressed=self._max_docx_uncompressed_bytes,
            max_compression_ratio=self._max_docx_compression_ratio,
        )
        sections = parse_template(self._storage.input_path(task_id, "template.docx"))
        self._storage.write_result(
            task_id,
            "template_sections.json",
            _SECTIONS_ADAPTER.dump_json(sections, indent=2),
        )
        return sections

    def get(self, task_id: str) -> list[TemplateSection]:
        self._require_task(task_id)
        try:
            data = self._storage.read_result(task_id, "template_sections.json")
        except FileNotFoundError as exc:
            raise LookupError("尚未识别模板板块") from exc
        return _SECTIONS_ADAPTER.validate_json(data)

    def replace(self, task_id: str, sections: list[TemplateSection]) -> list[TemplateSection]:
        current = self.get(task_id)
        current_locators = {item.id: item.locator for item in current}
        if len(sections) != len(current) or len({item.id for item in sections}) != len(sections):
            raise ValueError("模板板块必须完整且 ID 唯一")
        if any(current_locators.get(item.id) != item.locator for item in sections):
            raise ValueError("不能修改模板定位信息")
        self._storage.write_result(
            task_id,
            "template_sections.json",
            _SECTIONS_ADAPTER.dump_json(sections, indent=2),
        )
        return sections

    def confirm(self, task_id: str) -> Task:
        if not self.get(task_id):
            raise ValueError("模板中没有可生成板块")
        return self._repository.set_status(task_id, TaskStatus.READY_FOR_ANALYSIS)

    def _require_task(self, task_id: str) -> None:
        if self._repository.get(task_id) is None:
            raise LookupError("任务不存在")
