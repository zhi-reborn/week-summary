from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import app.main as main_module
from app.config import Settings


def test_spa_fallback_does_not_swallow_unknown_api_routes(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<h1>应用首页</h1>", encoding="utf-8")
    monkeypatch.setattr(main_module, "_static_dir", lambda: static_dir)

    with TestClient(main_module.create_app(Settings(data_dir=tmp_path / "data"))) as client:
        assert client.get("/tasks/demo/people").text == "<h1>应用首页</h1>"
        response = client.get("/api/not-found")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
