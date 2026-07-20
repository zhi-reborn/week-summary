import os
import shutil
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import BinaryIO


class FileTooLarge(ValueError):
    pass


class TaskStorage:
    def __init__(self, data_dir: Path) -> None:
        self._tasks_dir = (data_dir / "tasks").resolve()

    def write_stream(
        self,
        task_id: str,
        stored_name: str,
        stream: BinaryIO,
        max_bytes: int,
    ) -> Path:
        input_dir = self._task_dir(task_id) / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        destination = self._safe_child(input_dir, stored_name)
        return self._write_stream(destination, stream, max_bytes)

    def read_input(self, task_id: str, stored_name: str) -> bytes:
        return self._safe_child(self._task_dir(task_id) / "input", stored_name).read_bytes()

    def input_path(self, task_id: str, stored_name: str) -> Path:
        return self._safe_child(self._task_dir(task_id) / "input", stored_name)

    def write_result(self, task_id: str, stored_name: str, data: bytes) -> Path:
        result_dir = self._task_dir(task_id) / "result"
        result_dir.mkdir(parents=True, exist_ok=True)
        return self._write_stream(
            self._safe_child(result_dir, stored_name), BytesIO(data), len(data)
        )

    def read_result(self, task_id: str, stored_name: str) -> bytes:
        return self._safe_child(self._task_dir(task_id) / "result", stored_name).read_bytes()

    def output_path(self, task_id: str, stored_name: str, *, create: bool = False) -> Path:
        output_dir = self._task_dir(task_id) / "output"
        if create:
            output_dir.mkdir(parents=True, exist_ok=True)
        return self._safe_child(output_dir, stored_name)

    def delete_inputs(self, task_id: str) -> None:
        shutil.rmtree(self._task_dir(task_id) / "input", ignore_errors=True)

    def delete_task(self, task_id: str) -> None:
        task_dir = self._task_dir(task_id)
        if task_dir.exists():
            shutil.rmtree(task_dir)

    def task_size(self, task_id: str) -> int:
        task_dir = self._task_dir(task_id)
        if not task_dir.exists():
            return 0
        return sum(path.stat().st_size for path in task_dir.rglob("*") if path.is_file())

    def tasks_size(self) -> int:
        if not self._tasks_dir.exists():
            return 0
        return sum(
            path.stat().st_size for path in self._tasks_dir.rglob("*") if path.is_file()
        )

    def _task_dir(self, task_id: str) -> Path:
        return self._safe_child(self._tasks_dir, task_id)

    @staticmethod
    def _safe_child(parent: Path, name: str) -> Path:
        if not name or name in {".", ".."} or "/" in name or "\\" in name:
            raise ValueError("存储路径无效")
        parent = parent.resolve()
        candidate = (parent / name).resolve()
        if candidate.parent != parent:
            raise ValueError("存储路径超出数据目录")
        return candidate

    @staticmethod
    def _write_stream(destination: Path, stream: BinaryIO, max_bytes: int) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        temporary_path: Path | None = None

        try:
            with NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                while chunk := stream.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise FileTooLarge("上传文件超过大小限制")
                    temporary.write(chunk)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, destination)
            return destination
        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise
