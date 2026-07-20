import sqlite3
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.config import Settings
from app.infrastructure.db.backup import create_sqlite_backup, restore_sqlite_backup


def run_migrations(settings: Settings) -> Path | None:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    config = Config()
    config.set_main_option("script_location", str(bundle_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    database_path = settings.data_dir / "app.db"
    current = _current_revision(database_path)
    head = ScriptDirectory.from_config(config).get_current_head()
    backup_path = None
    if database_path.is_file() and database_path.stat().st_size > 0 and current != head:
        backup_path = create_sqlite_backup(database_path, settings.data_dir / "backups")
    try:
        command.upgrade(config, "head")
    except Exception:
        if backup_path is not None:
            restore_sqlite_backup(backup_path, database_path)
        raise
    return backup_path


def _current_revision(database_path: Path) -> str | None:
    if not database_path.is_file():
        return None
    try:
        with sqlite3.connect(database_path) as database:
            row = database.execute("SELECT version_num FROM alembic_version").fetchone()
    except sqlite3.DatabaseError:
        return None
    return str(row[0]) if row is not None else None
