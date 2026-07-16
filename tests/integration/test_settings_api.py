import os
import stat
from pathlib import Path

from fastapi.testclient import TestClient


def test_model_settings_never_return_api_key(client: TestClient, tmp_path: Path) -> None:
    response = client.put(
        "/api/settings/model",
        json={
            "base_url": "http://127.0.0.1:8000/v1",
            "model": "private-model",
            "api_key": "secret-value",
            "timeout_seconds": 60,
            "max_retries": 1,
            "temperature": 0.1,
            "context_tokens": 8192,
        },
    )

    assert response.status_code == 200
    assert response.json()["has_api_key"] is True
    assert "api_key" not in response.json()
    assert "secret-value" not in response.text
    assert "api_key" not in client.get("/api/settings/model").json()
    key_path = tmp_path / "model_api_key"
    if os.name != "nt":
        assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
