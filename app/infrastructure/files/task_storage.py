import os
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import BinaryIO


class FileTooLarge(ValueError):
    pass


class TaskStorage:
    def __init__(self, data_dir: Path) -> None:
        self._tasks_dir = data_dir / "tasks"

    def write_stream(
        self,
        task_id: str,
        stored_name: str,
        stream: BinaryIO,
        max_bytes: int,
    ) -> Path:
        input_dir = self._tasks_dir / task_id / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        destination = input_dir / stored_name
        return self._write_stream(destination, stream, max_bytes)

    def read_input(self, task_id: str, stored_name: str) -> bytes:
        return (self._tasks_dir / task_id / "input" / stored_name).read_bytes()

    def input_path(self, task_id: str, stored_name: str) -> Path:
        return self._tasks_dir / task_id / "input" / stored_name

    def write_result(self, task_id: str, stored_name: str, data: bytes) -> Path:
        result_dir = self._tasks_dir / task_id / "result"
        result_dir.mkdir(parents=True, exist_ok=True)
        return self._write_stream(result_dir / stored_name, BytesIO(data), len(data))

    def read_result(self, task_id: str, stored_name: str) -> bytes:
        return (self._tasks_dir / task_id / "result" / stored_name).read_bytes()

    def output_path(self, task_id: str, stored_name: str, *, create: bool = False) -> Path:
        output_dir = self._tasks_dir / task_id / "output"
        if create:
            output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / stored_name

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
