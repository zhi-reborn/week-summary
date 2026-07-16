from io import BytesIO

import pytest

from app.infrastructure.files.task_storage import FileTooLarge, TaskStorage


def test_write_stream_rejects_oversized_file_and_removes_temporary_file(tmp_path) -> None:
    storage = TaskStorage(tmp_path)

    with pytest.raises(FileTooLarge, match="大小限制"):
        storage.write_stream("task-1", "reports.txt", BytesIO(b"1234"), max_bytes=3)

    input_dir = tmp_path / "tasks" / "task-1" / "input"
    assert list(input_dir.iterdir()) == []
