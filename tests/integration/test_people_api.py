from fastapi.testclient import TestClient


def test_detects_and_confirms_people(client: TestClient, valid_docx_bytes: bytes) -> None:
    task = client.post("/api/tasks", json={"name": "第29周"}).json()
    client.post(
        f"/api/tasks/{task['id']}/inputs",
        files={
            "reports": (
                "reports.txt",
                "姓名：张三\n完成A\n\n李四周报\n完成B".encode(),
                "text/plain",
            ),
            "template": ("template.docx", valid_docx_bytes, "application/octet-stream"),
        },
    )

    detect_response = client.post(f"/api/tasks/{task['id']}/people/detect")
    assert detect_response.status_code == 200
    assert [item["name"] for item in detect_response.json()["people"]] == ["张三", "李四"]
    assert detect_response.json()["unassigned"] == []

    confirm_response = client.post(f"/api/tasks/{task['id']}/people/confirm")
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "template_confirmation"


def test_rejects_overlapping_people_ranges(client: TestClient, valid_docx_bytes: bytes) -> None:
    task = client.post("/api/tasks", json={"name": "第29周"}).json()
    client.post(
        f"/api/tasks/{task['id']}/inputs",
        files={
            "reports": ("reports.txt", "姓名：张三\n完成A\n李四周报\n完成B".encode(), "text/plain"),
            "template": ("template.docx", valid_docx_bytes, "application/octet-stream"),
        },
    )

    response = client.put(
        f"/api/tasks/{task['id']}/people",
        json={
            "people": [
                {"id": "P01", "name": "张三", "line_start": 1, "line_end": 3, "content": "完成A"},
                {"id": "P02", "name": "李四", "line_start": 3, "line_end": 4, "content": "完成B"},
            ],
            "unassigned": [],
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_PEOPLE_SEGMENTS"
