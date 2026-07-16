import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.domain.enums import TaskStatus
from app.domain.facts import Fact, PersonExtraction
from app.domain.jobs import AnalysisJob, JobStep
from app.domain.people import PersonSegment
from app.domain.quality import QualityFinding
from app.domain.review import GeneratedSection, SectionVersion
from app.domain.task import Task
from app.infrastructure.db.models import (
    AnalysisJobRow,
    FactRow,
    FactSourceRow,
    JobStepRow,
    PersonRow,
    QualityFindingRow,
    SectionVersionRow,
    TaskRow,
)


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, name: str) -> Task:
        row = TaskRow(id=str(uuid4()), name=name, status=TaskStatus.DRAFT.value)
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def get(self, task_id: str) -> Task | None:
        row = self._session.scalar(select(TaskRow).where(TaskRow.id == task_id))
        return self._to_domain(row) if row is not None else None

    def set_status(self, task_id: str, status: TaskStatus) -> Task:
        row = self._session.get(TaskRow, task_id)
        if row is None:
            raise LookupError("任务不存在")
        row.status = status.value
        self._session.flush()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: TaskRow) -> Task:
        return Task(
            id=row.id,
            name=row.name,
            status=TaskStatus(row.status),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class PeopleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_confirmed(self, task_id: str, people: list[PersonSegment]) -> None:
        self._session.execute(delete(PersonRow).where(PersonRow.task_id == task_id))
        self._session.add_all(
            [
                PersonRow(
                    task_id=task_id,
                    id=person.id,
                    name=person.name,
                    line_start=person.line_start,
                    line_end=person.line_end,
                    content=person.content,
                )
                for person in people
            ]
        )
        self._session.flush()

    def list_confirmed(self, task_id: str) -> list[PersonSegment]:
        rows = self._session.scalars(
            select(PersonRow).where(PersonRow.task_id == task_id).order_by(PersonRow.line_start)
        )
        return [
            PersonSegment(
                id=row.id,
                name=row.name,
                line_start=row.line_start,
                line_end=row.line_end,
                content=row.content,
            )
            for row in rows
        ]


class FactRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_person_facts(self, task_id: str, extraction: PersonExtraction) -> None:
        existing_ids = list(
            self._session.scalars(
                select(FactRow.id).where(
                    FactRow.task_id == task_id,
                    FactRow.person_id == extraction.person_id,
                )
            )
        )
        if existing_ids:
            self._session.execute(
                delete(FactSourceRow).where(
                    FactSourceRow.task_id == task_id,
                    FactSourceRow.fact_id.in_(existing_ids),
                )
            )
        self._session.execute(
            delete(FactRow).where(
                FactRow.task_id == task_id,
                FactRow.person_id == extraction.person_id,
            )
        )
        for fact in extraction.facts:
            self._session.add(
                FactRow(
                    task_id=task_id,
                    id=fact.id,
                    person_id=extraction.person_id,
                    kind=fact.kind.value,
                    topic=fact.topic,
                    text=fact.text,
                    metrics_json=json.dumps([item.model_dump() for item in fact.metrics]),
                    payload_json=fact.model_dump_json(),
                    confidence=fact.confidence,
                )
            )
            self._session.add_all(
                [
                    FactSourceRow(
                        task_id=task_id,
                        fact_id=fact.id,
                        person_id=source.person_id,
                        line_start=source.line_start,
                        line_end=source.line_end,
                        quote=source.quote,
                    )
                    for source in fact.sources
                ]
            )
        self._session.flush()

    def list_by_person(self, task_id: str, person_id: str) -> list[Fact]:
        rows = self._session.scalars(
            select(FactRow)
            .where(FactRow.task_id == task_id, FactRow.person_id == person_id)
            .order_by(FactRow.id)
        )
        return [Fact.model_validate_json(row.payload_json) for row in rows]

    def list_by_task(self, task_id: str) -> list[Fact]:
        rows = self._session.scalars(
            select(FactRow).where(FactRow.task_id == task_id).order_by(FactRow.id)
        )
        return [Fact.model_validate_json(row.payload_json) for row in rows]


class JobStepRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, task_id: str, step_type: str, entity_id: str) -> JobStep | None:
        row = self._session.scalar(
            select(JobStepRow).where(
                JobStepRow.task_id == task_id,
                JobStepRow.step_type == step_type,
                JobStepRow.entity_id == entity_id,
            )
        )
        return self._to_domain(row) if row is not None else None

    def get_or_create(self, task_id: str, step_type: str, entity_id: str) -> JobStep:
        existing = self.get(task_id, step_type, entity_id)
        if existing is not None:
            return existing
        row = JobStepRow(
            id=str(uuid4()),
            task_id=task_id,
            step_type=step_type,
            entity_id=entity_id,
            status="pending",
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def list_for_task(self, task_id: str) -> list[JobStep]:
        rows = self._session.scalars(
            select(JobStepRow)
            .where(JobStepRow.task_id == task_id)
            .order_by(JobStepRow.updated_at, JobStepRow.id)
        )
        return [self._to_domain(row) for row in rows]

    def mark_running(self, step_id: str) -> JobStep:
        return self._set_status(step_id, "running", None)

    def mark_succeeded(self, step_id: str) -> JobStep:
        return self._set_status(step_id, "succeeded", None)

    def mark_failed(self, step_id: str, error_code: str) -> JobStep:
        return self._set_status(step_id, "failed", error_code)

    def _set_status(self, step_id: str, status: str, error_code: str | None) -> JobStep:
        row = self._session.get(JobStepRow, step_id)
        if row is None:
            raise LookupError("任务步骤不存在")
        row.status = status
        row.error_code = error_code
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: JobStepRow) -> JobStep:
        return JobStep(
            id=row.id,
            task_id=row.task_id,
            step_type=row.step_type,
            entity_id=row.entity_id,
            status=row.status,
            error_code=row.error_code,
        )


class SectionVersionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        task_id: str,
        generated: GeneratedSection,
        status: str,
        instruction: str,
    ) -> SectionVersion:
        latest_version = self._session.scalar(
            select(func.max(SectionVersionRow.version)).where(
                SectionVersionRow.task_id == task_id,
                SectionVersionRow.section_id == generated.section_id,
            )
        )
        row = SectionVersionRow(
            id=str(uuid4()),
            task_id=task_id,
            section_id=generated.section_id,
            version=(latest_version or 0) + 1,
            payload_json=generated.model_dump_json(),
            status=status,
            instruction=instruction,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def latest(self, task_id: str, section_id: str) -> SectionVersion | None:
        row = self._session.scalar(
            select(SectionVersionRow)
            .where(
                SectionVersionRow.task_id == task_id,
                SectionVersionRow.section_id == section_id,
            )
            .order_by(SectionVersionRow.version.desc())
            .limit(1)
        )
        return self._to_domain(row) if row is not None else None

    @staticmethod
    def _to_domain(row: SectionVersionRow) -> SectionVersion:
        return SectionVersion(
            id=row.id,
            task_id=row.task_id,
            section_id=row.section_id,
            version=row.version,
            generated=GeneratedSection.model_validate_json(row.payload_json),
            status=row.status,
            instruction=row.instruction,
            created_at=row.created_at,
        )


class QualityFindingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_for_version(
        self, task_id: str, version_id: str, findings: list[QualityFinding]
    ) -> None:
        self._session.add_all(
            [
                QualityFindingRow(
                    id=str(uuid4()),
                    task_id=task_id,
                    section_version_id=version_id,
                    code=finding.code,
                    message=finding.message,
                    token=finding.token,
                )
                for finding in findings
            ]
        )
        self._session.flush()


class AnalysisJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(self, task_id: str) -> AnalysisJob:
        row = self._session.get(AnalysisJobRow, task_id)
        if row is None:
            row = AnalysisJobRow(task_id=task_id, status="queued")
            self._session.add(row)
        else:
            row.status = "queued"
            row.owner_id = None
            row.error_code = None
            row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return self._to_domain(row)

    def create_failed(self, task_id: str, error_code: str) -> AnalysisJob:
        job = self.enqueue(task_id)
        return self.mark_failed(job.task_id, error_code)

    def get(self, task_id: str) -> AnalysisJob | None:
        row = self._session.get(AnalysisJobRow, task_id)
        return self._to_domain(row) if row is not None else None

    def claim_next(self, owner_id: str) -> AnalysisJob | None:
        task_id = self._session.scalar(
            select(AnalysisJobRow.task_id)
            .where(AnalysisJobRow.status == "queued")
            .order_by(AnalysisJobRow.updated_at)
            .limit(1)
        )
        if task_id is None:
            return None
        result = self._session.execute(
            update(AnalysisJobRow)
            .where(
                AnalysisJobRow.task_id == task_id,
                AnalysisJobRow.status == "queued",
            )
            .values(
                status="running",
                owner_id=owner_id,
                error_code=None,
                updated_at=datetime.now(timezone.utc),
            )
        )
        if getattr(result, "rowcount", 0) != 1:
            return None
        self._session.flush()
        row = self._session.get(AnalysisJobRow, task_id)
        if row is None:
            return None
        return self._to_domain(row)

    def mark_succeeded(self, task_id: str) -> AnalysisJob:
        return self._set_status(task_id, "succeeded", None)

    def mark_failed(self, task_id: str, error_code: str) -> AnalysisJob:
        return self._set_status(task_id, "failed", error_code)

    def requeue_interrupted(self) -> int:
        result = self._session.execute(
            update(AnalysisJobRow)
            .where(AnalysisJobRow.status == "running")
            .values(
                status="queued",
                owner_id=None,
                error_code=None,
                updated_at=datetime.now(timezone.utc),
            )
        )
        return int(getattr(result, "rowcount", 0))

    def _set_status(self, task_id: str, status: str, error_code: str | None) -> AnalysisJob:
        row = self._session.get(AnalysisJobRow, task_id)
        if row is None:
            raise LookupError("分析任务不存在")
        row.status = status
        row.error_code = error_code
        row.owner_id = None
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: AnalysisJobRow) -> AnalysisJob:
        return AnalysisJob(
            task_id=row.task_id,
            status=row.status,
            owner_id=row.owner_id,
            error_code=row.error_code,
        )
