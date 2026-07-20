from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import migrate_database


@pytest.fixture
def limited_client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        data_dir=tmp_path,
        max_txt_bytes=8,
        max_docx_bytes=20 * 1024 * 1024,
    )
    migrate_database(settings.database_url)
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("../report.txt", "report.txt"),
        ("..\\report.txt", "report.txt"),
        ("/tmp/report.txt", "report.txt"),
    ],
)
def test_upload_ignores_client_path(
    client: TestClient,
    valid_docx_bytes: bytes,
    filename: str,
    expected: str,
) -> None:
    task = client.post("/api/tasks", json={"name": "安全测试"}).json()

    response = client.post(
        f"/api/tasks/{task['id']}/inputs",
        files={
            "reports": (filename, b"Alice weekly", "text/plain"),
            "template": ("template.docx", valid_docx_bytes, "application/octet-stream"),
        },
    )

    assert response.status_code == 200
    assert response.json()["reports_name"] == expected
    assert ".." not in response.json()["reports_name"]


def test_rejects_file_disguised_as_docx(client: TestClient, tmp_path: Path) -> None:
    task = client.post("/api/tasks", json={"name": "伪装文件"}).json()

    response = client.post(
        f"/api/tasks/{task['id']}/inputs",
        files={
            "reports": ("reports.txt", b"Alice weekly", "text/plain"),
            "template": ("template.docx", b"not a zip package", "application/octet-stream"),
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_DOCX"
    assert not (tmp_path / "tasks" / task["id"] / "input").exists()


def test_txt_and_docx_have_separate_size_limits(
    limited_client: TestClient,
    valid_docx_bytes: bytes,
) -> None:
    task = limited_client.post("/api/tasks", json={"name": "文件大小"}).json()

    response = limited_client.post(
        f"/api/tasks/{task['id']}/inputs",
        files={
            "reports": ("reports.txt", b"123456789", "text/plain"),
            "template": ("template.docx", valid_docx_bytes, "application/octet-stream"),
        },
    )

    assert response.status_code == 413
    assert response.json()["code"] == "FILE_TOO_LARGE"


def test_docx_uses_its_own_upload_limit(tmp_path: Path, valid_docx_bytes: bytes) -> None:
    settings = Settings(
        data_dir=tmp_path,
        max_txt_bytes=1024,
        max_docx_bytes=len(valid_docx_bytes) - 1,
    )
    migrate_database(settings.database_url)
    with TestClient(create_app(settings)) as client:
        task = client.post("/api/tasks", json={"name": "DOCX 大小"}).json()
        response = client.post(
            f"/api/tasks/{task['id']}/inputs",
            files={
                "reports": ("reports.txt", b"weekly", "text/plain"),
                "template": (
                    "template.docx",
                    valid_docx_bytes,
                    "application/octet-stream",
                ),
            },
        )

    assert response.status_code == 413
    assert response.json()["code"] == "FILE_TOO_LARGE"
