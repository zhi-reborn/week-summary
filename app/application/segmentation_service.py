from app.domain.enums import TaskStatus
from app.domain.people import SegmentationResult
from app.domain.task import Task
from app.infrastructure.db.repositories import PeopleRepository, TaskRepository
from app.infrastructure.files.task_storage import TaskStorage
from app.infrastructure.txt.decoding import decode_report
from app.infrastructure.txt.segmentation import segment_people
from sqlalchemy.orm import Session


class SegmentationService:
    def __init__(self, session: Session, storage: TaskStorage) -> None:
        self._repository = TaskRepository(session)
        self._people = PeopleRepository(session)
        self._storage = storage

    def detect(self, task_id: str) -> SegmentationResult:
        self._require_task(task_id)
        report = decode_report(self._storage.read_input(task_id, "reports.txt"))
        result = segment_people(report.text)
        self._storage.write_result(
            task_id,
            "people.json",
            result.model_dump_json(indent=2).encode("utf-8"),
        )
        return result

    def get(self, task_id: str) -> SegmentationResult:
        self._require_task(task_id)
        try:
            data = self._storage.read_result(task_id, "people.json")
        except FileNotFoundError as exc:
            raise LookupError("尚未执行人员拆分") from exc
        return SegmentationResult.model_validate_json(data)

    def replace(self, task_id: str, result: SegmentationResult) -> SegmentationResult:
        self._require_task(task_id)
        report = decode_report(self._storage.read_input(task_id, "reports.txt"))
        self._validate(result, report.text.splitlines())
        self._storage.write_result(
            task_id,
            "people.json",
            result.model_dump_json(indent=2).encode("utf-8"),
        )
        return result

    def confirm(self, task_id: str) -> Task:
        result = self.get(task_id)
        if not result.people or result.unassigned:
            raise ValueError("人员拆分仍有未分配内容")
        self._people.replace_confirmed(task_id, result.people)
        return self._repository.set_status(task_id, TaskStatus.TEMPLATE_CONFIRMATION)

    def _require_task(self, task_id: str) -> None:
        if self._repository.get(task_id) is None:
            raise LookupError("任务不存在")

    @staticmethod
    def _validate(result: SegmentationResult, lines: list[str]) -> None:
        names = [person.name for person in result.people]
        if len(names) != len(set(names)):
            raise ValueError("人员姓名不能重复")
        if not 1 <= len(result.people) <= 20:
            raise ValueError("人员数量必须为 1 至 20")

        coverage = [0] * len(lines)
        ranges = [(item.line_start, item.line_end) for item in result.people]
        ranges += [(item.line_start, item.line_end) for item in result.unassigned]
        for line_start, line_end in ranges:
            if line_start > line_end or line_end > len(lines):
                raise ValueError("行号范围无效")
            for index in range(line_start - 1, line_end):
                coverage[index] += 1
                if coverage[index] > 1:
                    raise ValueError("人员内容行范围不能重叠")

        if any(line.strip() and coverage[index] == 0 for index, line in enumerate(lines)):
            raise ValueError("存在未覆盖的原文内容")
