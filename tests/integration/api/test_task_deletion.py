from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.config import Settings
from app.infrastructure.db.models import PersonRow, TaskRow
from app.infrastructure.files.task_storage import TaskStorage
from app.main import create_app
from tests.conftest import migrate_database


def _create_uploaded_task(client: TestClient, docx: bytes, name: str = "待删除") -> dict[str, str]:
    task = client.post("/api/tasks", json={"name": name}).json()
    response = client.post(
        f"/api/tasks/{task['id']}/inputs",
        files={
            "reports": ("reports.txt", b"Alice weekly", "text/plain"),
            "template": ("template.docx", docx, "application/octet-stream"),
        },
    )
    assert response.status_code == 200
    return task


def test_delete_task_removes_files_database_rows_and_only_target_task(
    client: TestClient,
    valid_docx_bytes: bytes,
) -> None:
    target = _create_uploaded_task(client, valid_docx_bytes)
    retained = _create_uploaded_task(client, valid_docx_bytes, "保留")
    with client.app.state.session_factory() as session:
        session.add(
            PersonRow(
                task_id=target["id"],
                id="person-1",
                name="Alice",
                line_start=1,
                line_end=1,
                content="weekly",
            )
        )
        session.commit()

    response = client.delete(f"/api/tasks/{target['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/tasks/{target['id']}").status_code == 404
    assert client.get(f"/api/tasks/{retained['id']}").status_code == 200
    storage = TaskStorage(client.app.state.settings.data_dir)
    assert storage.task_size(target["id"]) == 0
    assert storage.task_size(retained["id"]) > 0
    with client.app.state.session_factory() as session:
        assert session.scalar(
            select(PersonRow).where(PersonRow.task_id == target["id"])
        ) is None


def test_delete_failure_leaves_deleting_state_and_can_be_retried(
    client: TestClient,
    valid_docx_bytes: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _create_uploaded_task(client, valid_docx_bytes)
    original_delete = TaskStorage.delete_task
    attempts = 0

    def fail_once(storage: TaskStorage, task_id: str) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("locked")
        original_delete(storage, task_id)

    monkeypatch.setattr(TaskStorage, "delete_task", fail_once)

    first = client.delete(f"/api/tasks/{task['id']}")
    assert first.status_code == 503
    assert first.json()["code"] == "TASK_DELETE_FAILED"
    assert client.get(f"/api/tasks/{task['id']}").json()["status"] == "deleting"

    assert client.delete(f"/api/tasks/{task['id']}").status_code == 204
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404


def test_usage_reports_task_and_file_totals(
    client: TestClient,
    valid_docx_bytes: bytes,
) -> None:
    _create_uploaded_task(client, valid_docx_bytes)

    response = client.get("/api/data/usage")

    assert response.status_code == 200
    assert response.json()["task_count"] == 1
    assert response.json()["task_bytes"] > 0
    assert response.json()["total_bytes"] >= response.json()["task_bytes"]


def test_cleanup_is_disabled_by_default(client: TestClient) -> None:
    response = client.post("/api/data/cleanup")

    assert response.status_code == 409
    assert response.json()["code"] == "RETENTION_DISABLED"


@pytest.fixture
def retention_client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(data_dir=tmp_path, retention_days=7)
    migrate_database(settings.database_url)
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_cleanup_only_removes_old_terminal_tasks(
    retention_client: TestClient,
    valid_docx_bytes: bytes,
) -> None:
    old_completed = _create_uploaded_task(retention_client, valid_docx_bytes, "旧已完成")
    old_active = _create_uploaded_task(retention_client, valid_docx_bytes, "旧处理中")
    recent_failed = _create_uploaded_task(retention_client, valid_docx_bytes, "新失败")
    old = datetime.now(timezone.utc) - timedelta(days=8)
    with retention_client.app.state.session_factory() as session:
        session.execute(
            update(TaskRow)
            .where(TaskRow.id == old_completed["id"])
            .values(status="completed", updated_at=old)
        )
        session.execute(
            update(TaskRow)
            .where(TaskRow.id == old_active["id"])
            .values(status="analyzing", updated_at=old)
        )
        session.execute(
            update(TaskRow)
            .where(TaskRow.id == recent_failed["id"])
            .values(status="failed", updated_at=datetime.now(timezone.utc))
        )
        session.commit()

    response = retention_client.post("/api/data/cleanup")

    assert response.status_code == 200
    assert response.json()["deleted_tasks"] == 1
    assert response.json()["freed_bytes"] > 0
    assert retention_client.get(f"/api/tasks/{old_completed['id']}").status_code == 404
    assert retention_client.get(f"/api/tasks/{old_active['id']}").status_code == 200
    assert retention_client.get(f"/api/tasks/{recent_failed['id']}").status_code == 200
