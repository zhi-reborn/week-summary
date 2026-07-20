from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import resolve_runtime_paths


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WRA_", extra="ignore")

    data_dir: Path = Field(default_factory=lambda: resolve_runtime_paths().data_dir)
    host: str = "127.0.0.1"
    port: int = 8765
    max_upload_bytes: int = 25 * 1024 * 1024
    max_docx_entries: int = 5000
    max_docx_uncompressed_bytes: int = 100 * 1024 * 1024

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'app.db'}"
