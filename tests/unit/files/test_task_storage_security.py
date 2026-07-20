from io import BytesIO

import pytest

from app.infrastructure.files.task_storage import TaskStorage


@pytest.mark.parametrize("task_id", ["../other", "..\\other", "/tmp/other"])
def test_task_storage_rejects_task_path_traversal(tmp_path, task_id: str) -> None:
    with pytest.raises(ValueError, match="路径"):
        TaskStorage(tmp_path).write_stream(task_id, "reports.txt", BytesIO(b"data"), 10)


@pytest.mark.parametrize("stored_name", ["../report.txt", "..\\report.txt", "/tmp/report.txt"])
def test_task_storage_rejects_stored_name_path_traversal(tmp_path, stored_name: str) -> None:
    with pytest.raises(ValueError, match="路径"):
        TaskStorage(tmp_path).write_stream("task-1", stored_name, BytesIO(b"data"), 10)
