import os
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from app.core.secrets import validate_secret_name


class WindowsDPAPISecretStore:
    def __init__(
        self,
        directory: Path,
        *,
        protect: Callable[[bytes], bytes] | None = None,
        unprotect: Callable[[bytes], bytes] | None = None,
    ) -> None:
        self._directory = directory
        self._protect = protect or _protect_machine_scope
        self._unprotect = unprotect or _unprotect

    def save(self, name: str, value: str) -> None:
        destination = self._path(name)
        self._directory.mkdir(parents=True, exist_ok=True)
        encrypted = self._protect(value.encode("utf-8"))
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(dir=self._directory, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(encrypted)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, destination)
        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

    def load(self, name: str) -> str | None:
        path = self._path(name)
        if not path.is_file():
            return None
        return self._unprotect(path.read_bytes()).decode("utf-8")

    def delete(self, name: str) -> None:
        self._path(name).unlink(missing_ok=True)

    def _path(self, name: str) -> Path:
        return self._directory / validate_secret_name(name)


def _protect_machine_scope(value: bytes) -> bytes:
    win32crypt = _win32crypt()

    return bytes(
        win32crypt.CryptProtectData(
            value,
            "WeeklyReportAssistant",
            None,
            None,
            None,
            win32crypt.CRYPTPROTECT_LOCAL_MACHINE,
        )
    )


def _unprotect(value: bytes) -> bytes:
    win32crypt = _win32crypt()

    _description, plaintext = win32crypt.CryptUnprotectData(
        value, None, None, None, 0
    )
    return bytes(plaintext)


def _win32crypt() -> Any:
    import win32crypt  # type: ignore[import-untyped]

    return win32crypt
