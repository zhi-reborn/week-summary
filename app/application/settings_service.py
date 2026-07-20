import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.core.secrets import SecretStore
from app.domain.model_settings import ModelSettings, ModelSettingsUpdate, ModelSettingsView
from app.infrastructure.secrets.linux_file_store import LinuxFileSecretStore
from app.infrastructure.secrets.windows_dpapi import WindowsDPAPISecretStore


class SettingsService:
    def __init__(self, data_dir: Path, secret_store: SecretStore | None = None) -> None:
        self._data_dir = data_dir
        self._settings_path = data_dir / "model_settings.json"
        self._secret_store = secret_store or _platform_secret_store(data_dir)

    def get(self) -> ModelSettingsView:
        settings = ModelSettings.model_validate_json(self._settings_path.read_bytes())
        return ModelSettingsView(
            **settings.model_dump(),
            has_api_key=self._secret_store.load("model_api_key") is not None,
        )

    def save(self, update: ModelSettingsUpdate) -> ModelSettingsView:
        settings = ModelSettings.model_validate(update.model_dump(exclude={"api_key"}))
        self._write(self._settings_path, settings.model_dump_json(indent=2).encode("utf-8"), 0o600)
        if update.api_key is not None:
            if update.api_key:
                self._secret_store.save("model_api_key", update.api_key)
            else:
                self._secret_store.delete("model_api_key")
        return ModelSettingsView(
            **settings.model_dump(),
            has_api_key=self._secret_store.load("model_api_key") is not None,
        )

    def load_client_values(self) -> tuple[ModelSettings, str | None]:
        settings = ModelSettings.model_validate_json(self._settings_path.read_bytes())
        api_key = self._secret_store.load("model_api_key")
        return settings, api_key

    def _write(self, destination: Path, content: bytes, mode: int) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(dir=self._data_dir, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            temporary_path.chmod(mode)
            os.replace(temporary_path, destination)
            destination.chmod(mode)
        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise


def _platform_secret_store(data_dir: Path) -> SecretStore:
    if os.name == "nt":
        return WindowsDPAPISecretStore(data_dir)
    return LinuxFileSecretStore(data_dir)
