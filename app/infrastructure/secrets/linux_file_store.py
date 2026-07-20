import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.core.secrets import validate_secret_name


class LinuxFileSecretStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, name: str, value: str) -> None:
        destination = self._path(name)
        self._directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._directory.chmod(0o700)
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(dir=self._directory, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(value.encode("utf-8"))
                temporary.flush()
                os.fsync(temporary.fileno())
            temporary_path.chmod(0o600)
            os.replace(temporary_path, destination)
            destination.chmod(0o600)
        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

    def load(self, name: str) -> str | None:
        path = self._path(name)
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def delete(self, name: str) -> None:
        self._path(name).unlink(missing_ok=True)

    def _path(self, name: str) -> Path:
        return self._directory / validate_secret_name(name)
