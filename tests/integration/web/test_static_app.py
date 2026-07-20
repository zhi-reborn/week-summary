from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import app.main as main_module
from app.config import Settings


def test_serves_frontend_assets_and_spa_routes(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    static_dir = tmp_path / "web" / "dist"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("<h1>应用首页</h1>", encoding="utf-8")
    (assets_dir / "app.js").write_text("window.ready = true", encoding="utf-8")
    monkeypatch.setattr(main_module, "_static_dir", lambda: static_dir)

    with TestClient(main_module.create_app(Settings(data_dir=tmp_path / "data"))) as client:
        assert client.get("/").text == "<h1>应用首页</h1>"
        spa = client.get("/tasks/example/review")
        asset = client.get("/assets/app.js")

    assert spa.status_code == 200
    assert "text/html" in spa.headers["content-type"]
    assert asset.text == "window.ready = true"


def test_spa_fallback_does_not_swallow_backend_routes(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    static_dir = tmp_path / "web" / "dist"
    static_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("<h1>应用首页</h1>", encoding="utf-8")
    monkeypatch.setattr(main_module, "_static_dir", lambda: static_dir)

    with TestClient(main_module.create_app(Settings(data_dir=tmp_path / "data"))) as client:
        unknown_api = client.get("/api/not-found")
        unknown_health = client.get("/health/not-found")

    assert unknown_api.status_code == 404
    assert unknown_health.status_code == 404
