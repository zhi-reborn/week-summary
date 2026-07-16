from pathlib import Path

from app.config import Settings


def test_settings_use_localhost_and_given_data_dir(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)

    assert settings.host == "127.0.0.1"
    assert settings.port == 8765
    assert settings.database_url == f"sqlite:///{tmp_path / 'app.db'}"

