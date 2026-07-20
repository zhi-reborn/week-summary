from fastapi.testclient import TestClient

from app.domain.enums import GenerationMode
from app.infrastructure.docx.validator import validate_docx
from tests.helpers.export_task import create_exportable_task


def test_export_requires_confirmed_sections_in_review_mode(client: TestClient) -> None:
    task_id = create_exportable_task(
        client.app.state.session_factory,
        client.app.state.settings.data_dir,
        mode=GenerationMode.REVIEW,
        confirmed=False,
    )

    response = client.post(f"/api/tasks/{task_id}/export")

    assert response.status_code == 409
    assert response.json()["code"] == "UNCONFIRMED_SECTIONS"


def test_exports_and_downloads_with_server_generated_filename(client: TestClient) -> None:
    task_id = create_exportable_task(
        client.app.state.session_factory,
        client.app.state.settings.data_dir,
        mode=GenerationMode.REVIEW,
        confirmed=True,
    )

    exported = client.post(f"/api/tasks/{task_id}/export")
    response = client.get(f"/api/tasks/{task_id}/download")

    assert exported.status_code == 201
    assert exported.json()["status"] == "completed"
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert "attachment" in response.headers["content-disposition"]
    assert ".docx" in response.headers["content-disposition"]
    saved = client.app.state.settings.data_dir / "downloaded.docx"
    saved.write_bytes(response.content)
    assert validate_docx(saved, expected_sections={"本周重点"}).valid is True


def test_download_requires_recorded_export(client: TestClient) -> None:
    task_id = create_exportable_task(
        client.app.state.session_factory,
        client.app.state.settings.data_dir,
        mode=GenerationMode.REVIEW,
        confirmed=True,
    )

    response = client.get(f"/api/tasks/{task_id}/download")

    assert response.status_code == 404
    assert response.json()["code"] == "EXPORT_NOT_FOUND"
