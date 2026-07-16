from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from alembic import command
from alembic.config import Config
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.main import create_app


def migrate_database(database_url: str) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    database_path = tmp_path / "test.db"
    database_url = f"sqlite:///{database_path}"
    migrate_database(database_url)

    engine = create_engine(database_url)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(data_dir=tmp_path)
    migrate_database(settings.database_url)
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def valid_docx_bytes() -> bytes:
    document = Document()
    document.add_paragraph("{{本周重点}}")
    output = BytesIO()
    document.save(output)
    return output.getvalue()


@pytest.fixture
def zip_with_many_entries() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
        for index in range(20):
            archive.writestr(f"word/item-{index}.xml", "<item/>")
    return output.getvalue()
