from pathlib import Path

from app.application.settings_service import SettingsService
from app.domain.model_settings import ModelSettingsUpdate


class MemorySecretStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def save(self, name: str, value: str) -> None:
        self.values[name] = value

    def load(self, name: str) -> str | None:
        return self.values.get(name)

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


def test_settings_service_uses_secret_store_for_api_key(tmp_path: Path) -> None:
    secrets = MemorySecretStore()
    service = SettingsService(tmp_path, secrets)

    view = service.save(
        ModelSettingsUpdate(
            base_url="http://127.0.0.1:8000/v1",
            model="private-model",
            api_key="secret-value",
        )
    )

    assert view.has_api_key is True
    assert secrets.values == {"model_api_key": "secret-value"}
    assert not (tmp_path / "model_api_key").exists()
    _settings, api_key = service.load_client_values()
    assert api_key == "secret-value"


def test_platform_secret_store_uses_secrets_subdirectory(tmp_path: Path) -> None:
    # Regression: _platform_secret_store must scope secrets under data_dir/secrets,
    # not data_dir directly. Otherwise a key file placed at the conventional
    # data/secrets/model_api_key path is never read and the service silently
    # authenticates without an API key.
    service = SettingsService(tmp_path)

    service.save(
        ModelSettingsUpdate(
            base_url="http://127.0.0.1:8000/v1",
            model="private-model",
            api_key="secret-value",
        )
    )

    assert (tmp_path / "secrets" / "model_api_key").is_file()
    assert not (tmp_path / "model_api_key").exists()

    _settings, api_key = SettingsService(tmp_path).load_client_values()
    assert api_key == "secret-value"
