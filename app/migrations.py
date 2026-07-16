import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import Settings


def run_migrations(settings: Settings) -> None:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    config = Config()
    config.set_main_option("script_location", str(bundle_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
