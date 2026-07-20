from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.application.export_service import ExportError, ExportService
from app.domain.enums import GenerationMode, TaskStatus
from app.infrastructure.db.repositories import ExportRepository, TaskRepository
from app.infrastructure.files.task_storage import TaskStorage
from tests.helpers.export_task import create_exportable_task


def test_direct_mode_exports_without_review_confirmation(
    db_session: Session, tmp_path: Path
) -> None:
    factory = sessionmaker(db_session.get_bind(), expire_on_commit=False)
    task_id = create_exportable_task(
        factory,
        tmp_path,
        mode=GenerationMode.DIRECT,
        confirmed=False,
    )

    ExportService(factory, TaskStorage(tmp_path)).export(task_id)

    with factory() as verification:
        assert TaskRepository(verification).get(task_id).status == TaskStatus.COMPLETED
        assert ExportRepository(verification).get(task_id) is not None


def test_failed_export_is_not_delivered(
    db_session: Session, tmp_path: Path
) -> None:
    factory = sessionmaker(db_session.get_bind(), expire_on_commit=False)
    task_id = create_exportable_task(
        factory,
        tmp_path,
        mode=GenerationMode.DIRECT,
        confirmed=False,
    )
    document = Document()
    document.add_paragraph("{{其他板块}}")
    replacement = BytesIO()
    document.save(replacement)
    TaskStorage(tmp_path).write_stream(
        task_id,
        "template.docx",
        BytesIO(replacement.getvalue()),
        len(replacement.getvalue()),
    )

    with pytest.raises(ExportError) as raised:
        ExportService(factory, TaskStorage(tmp_path)).export(task_id)

    assert raised.value.code == "UNKNOWN_SECTION"
    assert not TaskStorage(tmp_path).output_path(task_id, "weekly-report.docx").exists()
    with factory() as verification:
        assert TaskRepository(verification).get(task_id).status == TaskStatus.EXPORT_FAILED
        assert ExportRepository(verification).get(task_id) is None
