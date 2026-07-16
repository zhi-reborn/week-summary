from pathlib import Path

from fastapi.testclient import TestClient


def test_detects_and_confirms_template_sections(client: TestClient) -> None:
    task = client.post("/api/tasks", json={"name": "第29周"}).json()
    template = Path("tests/fixtures/docx/header_footer_placeholder.docx").read_bytes()
    client.post(
        f"/api/tasks/{task['id']}/inputs",
        files={
            "reports": ("reports.txt", "姓名：张三\n完成A".encode(), "text/plain"),
            "template": ("template.docx", template, "application/octet-stream"),
        },
    )

    response = client.post(f"/api/tasks/{task['id']}/template/detect")
    assert response.status_code == 200
    assert {item["name"] for item in response.json()} == {"本周重点", "风险问题", "下周计划"}

    sections = response.json()
    sections[0]["instruction"] = "只保留最重要的三项"
    update = client.put(f"/api/tasks/{task['id']}/template/sections", json=sections)
    assert update.status_code == 200
    assert update.json()[0]["instruction"] == "只保留最重要的三项"

    confirm = client.post(f"/api/tasks/{task['id']}/template/confirm")
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "ready_for_analysis"
