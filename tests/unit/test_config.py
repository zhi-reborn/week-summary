from pathlib import Path

from app.config import Settings


def test_settings_use_localhost_and_given_data_dir(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)

    assert settings.host == "127.0.0.1"
    assert settings.port == 8765
    assert settings.max_txt_bytes == 10 * 1024 * 1024
    assert settings.max_docx_bytes == 20 * 1024 * 1024
    assert settings.max_docx_entries == 2000
    assert settings.max_docx_uncompressed_bytes == 100 * 1024 * 1024
    assert settings.max_docx_compression_ratio == 100
    assert settings.retention_days is None
    assert settings.max_recovery_attempts == 3
    assert settings.database_url == f"sqlite:///{tmp_path / 'app.db'}"
