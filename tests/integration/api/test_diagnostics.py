import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.application.settings_service import SettingsService
from app.config import Settings
from app.domain.model_settings import ModelSettingsUpdate
from app.main import create_app
from tests.conftest import migrate_database


def test_diagnostic_package_contains_only_redacted_whitelisted_data(tmp_path: Path) -> None:
    secret = "diagnostic-secret-123"
    settings = Settings(data_dir=tmp_path, log_dir=tmp_path / "logs")
    migrate_database(settings.database_url)
    SettingsService(tmp_path).save(
        ModelSettingsUpdate(
            base_url="http://127.0.0.1:9000/v1",
            model="private-model",
            api_key=secret,
        )
    )
    settings.log_dir.mkdir()
    (settings.log_dir / "app.jsonl").write_text(
        json.dumps(
            {
                "stage": "model_request",
                "error_code": "MODEL_TIMEOUT",
                "api_key": secret,
                "path": str(tmp_path / "tasks" / "private.txt"),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/diagnostics")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(response.content)) as archive:
        assert archive.namelist() == ["diagnostics.json"]
        payload_bytes = archive.read("diagnostics.json")
        payload = json.loads(payload_bytes)

    serialized = payload_bytes.decode("utf-8")
    assert secret not in serialized
    assert str(tmp_path) not in serialized
    assert "api_key" not in serialized
    assert payload["version"] == "0.1.0"
    assert payload["database"]["migration_version"] == "0007"
    assert payload["configuration"]["model_configured"] is True
    assert payload["configuration"]["model"] == "private-model"
    assert payload["model_connectivity"]["status"] == "not_checked"
    assert payload["recent_errors"][0]["error_code"] == "MODEL_TIMEOUT"
