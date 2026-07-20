from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient


def _compressed_docx(payload: bytes) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", payload)
    return output.getvalue()


def test_rejects_docx_zip_bomb(client: TestClient) -> None:
    task = client.post("/api/tasks", json={"name": "压缩炸弹"}).json()

    response = client.post(
        f"/api/tasks/{task['id']}/inputs",
        files={
            "reports": ("reports.txt", b"Alice weekly", "text/plain"),
            "template": (
                "template.docx",
                _compressed_docx(b"0" * 1_000_000),
                "application/octet-stream",
            ),
        },
    )

    assert response.status_code == 413
    assert response.json()["code"] == "DOCX_EXPANSION_LIMIT"
