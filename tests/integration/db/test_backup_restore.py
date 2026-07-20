import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.config import Settings
from app.infrastructure.db.backup import create_sqlite_backup, restore_sqlite_backup
from app.migrations import run_migrations
from tests.conftest import migrate_database


def test_backup_can_be_opened_and_contains_current_schema(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    migrate_database(settings.database_url)
    engine = create_engine(settings.database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO tasks (id, name, mode, status, created_at, updated_at) "
                "VALUES ('task-1', '第29周', 'review', 'draft', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )

    backup_path = create_sqlite_backup(tmp_path / "app.db", tmp_path / "backups")

    with sqlite3.connect(backup_path) as restored:
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert restored.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0007"
        assert restored.execute("SELECT name FROM tasks WHERE id = 'task-1'").fetchone()[0] == "第29周"


def test_restore_replaces_damaged_database_with_verified_backup(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    migrate_database(settings.database_url)
    database_path = tmp_path / "app.db"
    backup_path = create_sqlite_backup(database_path, tmp_path / "backups")
    database_path.write_bytes(b"damaged")

    restore_sqlite_backup(backup_path, database_path)

    with sqlite3.connect(database_path) as restored:
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert restored.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0007"


def test_run_migrations_backs_up_outdated_database(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    migrate_database(settings.database_url)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.downgrade(config, "0006")

    backup_path = run_migrations(settings)

    assert backup_path is not None
    assert backup_path.parent == tmp_path / "backups"
    with sqlite3.connect(settings.data_dir / "app.db") as database:
        assert database.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0007"
    with sqlite3.connect(backup_path) as backup:
        assert backup.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0006"


def test_failed_migration_restores_original_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(data_dir=tmp_path)
    migrate_database(settings.database_url)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.downgrade(config, "0006")

    def fail_after_change(_config: Config, _revision: str) -> None:
        with sqlite3.connect(tmp_path / "app.db") as database:
            database.execute("UPDATE alembic_version SET version_num = 'broken'")
            database.commit()
        raise RuntimeError("migration failed")

    monkeypatch.setattr("app.migrations.command.upgrade", fail_after_change)

    with pytest.raises(RuntimeError, match="migration failed"):
        run_migrations(settings)

    with sqlite3.connect(tmp_path / "app.db") as database:
        assert database.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert database.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0006"
