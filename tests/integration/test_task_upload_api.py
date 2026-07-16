from pathlib import Path

from fastapi.testclient import TestClient


def test_uploads_one_txt_and_one_docx(
    client: TestClient,
    valid_docx_bytes: bytes,
    tmp_path: Path,
) -> None:
    create_response = client.post("/api/tasks", json={"name": "第29周"})
    assert create_response.status_code == 201
    task = create_response.json()
    assert client.get(f"/api/tasks/{task['id']}").json() == task

    response = client.post(
        f"/api/tasks/{task['id']}/inputs",
        files={
            "reports": ("reports.txt", "姓名：张三\n完成A".encode(), "text/plain"),
            "template": (
                "template.docx",
                valid_docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["reports_name"] == "reports.txt"
    assert response.json()["status"] == "people_confirmation"
    input_dir = tmp_path / "tasks" / task["id"] / "input"
    assert (input_dir / "reports.txt").is_file()
    assert (input_dir / "template.docx").is_file()


def test_rejects_wrong_input_extensions(client: TestClient, valid_docx_bytes: bytes) -> None:
    task = client.post("/api/tasks", json={"name": "第29周"}).json()

    response = client.post(
        f"/api/tasks/{task['id']}/inputs",
        files={
            "reports": ("reports.csv", b"name,work", "text/csv"),
            "template": ("template.docx", valid_docx_bytes, "application/octet-stream"),
        },
    )

    assert response.status_code == 415
    assert response.json() == {
        "code": "UNSUPPORTED_FILE_TYPE",
        "message": "只支持 TXT 周报和 DOCX 模板",
        "details": None,
    }
