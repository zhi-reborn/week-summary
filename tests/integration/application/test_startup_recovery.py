from pathlib import Path

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.application.startup_recovery import StartupRecovery
from app.domain.enums import GenerationMode, TaskStatus
from app.infrastructure.db.models import AnalysisJobRow
from app.infrastructure.db.repositories import (
    AnalysisJobRepository,
    JobStepRepository,
    TaskRepository,
)
from app.infrastructure.files.task_storage import TaskStorage


def _factory(session: Session) -> sessionmaker[Session]:
    return sessionmaker(session.get_bind(), expire_on_commit=False)


def test_recovery_requeues_interrupted_analysis_and_keeps_succeeded_steps(
    db_session: Session,
    tmp_path: Path,
) -> None:
    task = TaskRepository(db_session).create("中断分析")
    TaskRepository(db_session).set_status(task.id, TaskStatus.ANALYZING)
    step = JobStepRepository(db_session).get_or_create(task.id, "extract_person", "P01")
    JobStepRepository(db_session).mark_succeeded(step.id)
    jobs = AnalysisJobRepository(db_session)
    jobs.enqueue(task.id)
    jobs.claim_next("old-process")
    db_session.commit()

    result = StartupRecovery(
        _factory(db_session),
        TaskStorage(tmp_path),
        export_task=lambda _task_id: None,
        max_recovery_attempts=3,
    ).run()

    assert result.requeued_analysis == 1
    with _factory(db_session)() as verification:
        recovered = AnalysisJobRepository(verification).get(task.id)
        assert recovered is not None
        assert recovered.status == "queued"
        assert recovered.recovery_attempts == 1
        assert JobStepRepository(verification).get(
            task.id, "extract_person", "P01"
        ).status == "succeeded"


def test_recovery_marks_analysis_failed_after_retry_limit(
    db_session: Session,
    tmp_path: Path,
) -> None:
    task = TaskRepository(db_session).create("反复中断")
    TaskRepository(db_session).set_status(task.id, TaskStatus.ANALYZING)
    jobs = AnalysisJobRepository(db_session)
    jobs.enqueue(task.id)
    jobs.claim_next("old-process")
    db_session.execute(
        update(AnalysisJobRow)
        .where(AnalysisJobRow.task_id == task.id)
        .values(recovery_attempts=2)
    )
    db_session.commit()

    result = StartupRecovery(
        _factory(db_session),
        TaskStorage(tmp_path),
        export_task=lambda _task_id: None,
        max_recovery_attempts=3,
    ).run()

    assert result.exhausted_analysis == 1
    with _factory(db_session)() as verification:
        assert TaskRepository(verification).get(task.id).status == TaskStatus.FAILED
        recovered = AnalysisJobRepository(verification).get(task.id)
        assert recovered is not None
        assert recovered.status == "failed"
        assert recovered.error_code == "RECOVERY_RETRY_EXHAUSTED"


def test_recovery_restores_review_export_and_retriggers_direct_export(
    db_session: Session,
    tmp_path: Path,
) -> None:
    tasks = TaskRepository(db_session)
    review_task = tasks.create("校审导出", GenerationMode.REVIEW)
    direct_task = tasks.create("直接导出", GenerationMode.DIRECT)
    tasks.set_status(review_task.id, TaskStatus.EXPORTING)
    tasks.set_status(direct_task.id, TaskStatus.EXPORTING)
    db_session.commit()
    storage = TaskStorage(tmp_path)
    temporary = storage.output_path(
        review_task.id,
        ".weekly-report.docx.interrupted.tmp",
        create=True,
    )
    temporary.write_bytes(b"partial")
    exported: list[str] = []

    result = StartupRecovery(
        _factory(db_session),
        storage,
        export_task=exported.append,
        max_recovery_attempts=3,
    ).run()

    assert result.cleaned_temporary_files == 1
    assert result.recovered_review_exports == 1
    assert exported == [direct_task.id]
    assert not temporary.exists()
    with _factory(db_session)() as verification:
        assert TaskRepository(verification).get(review_task.id).status == TaskStatus.REVIEW
        assert (
            TaskRepository(verification).get(direct_task.id).status
            == TaskStatus.EXPORT_FAILED
        )
