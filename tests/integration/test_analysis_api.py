from fastapi.testclient import TestClient

from app.domain.enums import TaskStatus
from app.infrastructure.db.repositories import (
    AnalysisJobRepository,
    JobStepRepository,
    TaskRepository,
)
from app.infrastructure.jobs.runner import AnalysisRunner


class NoopProcessor:
    def run(self, task_id: str) -> None:
        del task_id


def _install_runner(client: TestClient) -> AnalysisRunner:
    runner = AnalysisRunner(client.app.state.session_factory, NoopProcessor())
    client.app.state.runner = runner
    return runner


def _create_task_with_steps(client: TestClient, status: TaskStatus) -> str:
    with client.app.state.session_factory() as session:
        task = TaskRepository(session).create("第29周")
        TaskRepository(session).set_status(task.id, status)
        steps = JobStepRepository(session)
        first = steps.get_or_create(task.id, "extract_person", "P01")
        steps.mark_succeeded(first.id)
        steps.get_or_create(task.id, "extract_person", "P02")
        session.commit()
        return task.id


def test_starts_analysis_and_returns_step_progress(client: TestClient) -> None:
    _install_runner(client)
    task_id = _create_task_with_steps(client, TaskStatus.READY_FOR_ANALYSIS)

    started = client.post(f"/api/tasks/{task_id}/analysis/start")
    status = client.get(f"/api/tasks/{task_id}/analysis/status")

    assert started.status_code == 202
    assert started.json()["task_status"] == "analyzing"
    assert status.status_code == 200
    assert status.json() == {
        "task_id": task_id,
        "task_status": "analyzing",
        "job_status": "queued",
        "total_steps": 2,
        "succeeded_steps": 1,
        "current_step": "extract_person:P02",
        "failed_error_code": None,
        "retryable": False,
    }


def test_retries_failed_analysis_and_clears_job_error(client: TestClient) -> None:
    _install_runner(client)
    task_id = _create_task_with_steps(client, TaskStatus.FAILED)
    with client.app.state.session_factory() as session:
        step = JobStepRepository(session).get(task_id, "extract_person", "P02")
        assert step is not None
        JobStepRepository(session).mark_failed(step.id, "MODEL_TIMEOUT")
        AnalysisJobRepository(session).create_failed(task_id, "MODEL_TIMEOUT")
        session.commit()

    retried = client.post(f"/api/tasks/{task_id}/analysis/retry")

    assert retried.status_code == 202
    assert retried.json()["task_status"] == "analyzing"
    assert retried.json()["job_status"] == "queued"
    assert retried.json()["failed_error_code"] == "MODEL_TIMEOUT"
    assert retried.json()["retryable"] is False


def test_rejects_analysis_before_confirmations(client: TestClient) -> None:
    _install_runner(client)
    task_id = _create_task_with_steps(client, TaskStatus.DRAFT)

    response = client.post(f"/api/tasks/{task_id}/analysis/start")

    assert response.status_code == 409
    assert response.json()["code"] == "ANALYSIS_NOT_READY"
