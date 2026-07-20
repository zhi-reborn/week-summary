import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4


def create_sqlite_backup(database_path: Path, backup_dir: Path) -> Path:
    if not database_path.is_file():
        raise FileNotFoundError(database_path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.chmod(0o700)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = backup_dir / f"app-{timestamp}-{uuid4().hex[:8]}.db"
    temporary_path = _temporary_path(backup_dir)
    try:
        _sqlite_copy(database_path, temporary_path)
        _verify(temporary_path)
        os.replace(temporary_path, destination)
        destination.chmod(0o600)
        return destination
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def restore_sqlite_backup(backup_path: Path, database_path: Path) -> None:
    _verify(backup_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = _temporary_path(database_path.parent)
    try:
        _sqlite_copy(backup_path, temporary_path)
        _verify(temporary_path)
        for suffix in ("-wal", "-shm", "-journal"):
            Path(f"{database_path}{suffix}").unlink(missing_ok=True)
        os.replace(temporary_path, database_path)
        database_path.chmod(0o600)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _sqlite_copy(source_path: Path, destination_path: Path) -> None:
    source_uri = f"file:{source_path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source:
        with sqlite3.connect(destination_path) as destination:
            source.backup(destination)
            destination.commit()
    with destination_path.open("rb") as copied:
        os.fsync(copied.fileno())


def _verify(path: Path) -> None:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as database:
        result = database.execute("PRAGMA integrity_check").fetchone()
    if result is None or result[0] != "ok":
        raise RuntimeError("SQLite 备份完整性校验失败")


def _temporary_path(directory: Path) -> Path:
    with NamedTemporaryFile(dir=directory, prefix=".backup-", suffix=".tmp", delete=False) as file:
        return Path(file.name)
