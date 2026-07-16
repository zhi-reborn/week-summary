import os
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
        total = 0
        temporary_path: Path | None = None

        try:
            with NamedTemporaryFile(dir=input_dir, delete=False) as temporary:
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
