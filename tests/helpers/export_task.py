from collections.abc import Callable
from io import BytesIO
from pathlib import Path

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from app.domain.enums import GenerationMode, TaskStatus
from app.domain.review import GeneratedSection, SectionReview
from app.domain.template import RecognitionMethod, TemplateLocator, TemplateSection
from app.infrastructure.db.repositories import (
    SectionReviewRepository,
    SectionVersionRepository,
    TaskRepository,
)
from app.infrastructure.files.task_storage import TaskStorage


def create_exportable_task(
    session_factory: Callable[[], Session],
    data_dir: Path,
    *,
    mode: GenerationMode,
    confirmed: bool,
    required: bool = True,
) -> str:
    with session_factory() as session:
        task = TaskRepository(session).create("第29周", mode=mode)
        TaskRepository(session).set_status(task.id, TaskStatus.REVIEW)
        generated = GeneratedSection(
            section_id="S01",
            body="完成统一认证联调",
            fact_ids=[],
            source_ids=[],
        )
        SectionVersionRepository(session).save(task.id, generated, "pass", "")
        SectionReviewRepository(session).save(
            task.id,
            SectionReview(
                section_key="S01",
                revision=1,
                content=generated.body,
                confirmed=confirmed,
            ),
        )
        session.commit()
    storage = TaskStorage(data_dir)
    template = Path("tests/fixtures/docx/plain_placeholder.docx").read_bytes()
    storage.write_stream(task.id, "template.docx", BytesIO(template), len(template))
    section = TemplateSection(
        id="S01",
        name="本周重点",
        method=RecognitionMethod.PLACEHOLDER,
        confidence=1,
        required=required,
        locator=TemplateLocator(
            part="document", paragraph_index=1, token="{{本周重点}}"
        ),
    )
    storage.write_result(
        task.id,
        "template_sections.json",
        TypeAdapter(list[TemplateSection]).dump_json([section]),
    )
    return task.id
