from pathlib import Path
from types import SimpleNamespace

import app.config as config_module
from app.config import Settings
from app.core.paths import resolve_runtime_paths


def test_windows_data_directory_is_outside_install_directory() -> None:
    paths = resolve_runtime_paths(
        platform="windows",
        app_dir=Path(r"C:\Program Files\WeeklyReportAssistant"),
        environ={"PROGRAMDATA": r"C:\ProgramData"},
    )

    assert paths.data_dir == Path(r"C:\ProgramData") / "WeeklyReportAssistant"
    assert not str(paths.data_dir).startswith(str(paths.install_dir))
    assert paths.config_file.parent == paths.data_dir


def test_linux_uses_service_data_config_and_log_directories() -> None:
    paths = resolve_runtime_paths(platform="linux", app_dir=Path("/opt/weekly-report"))

    assert paths.data_dir == Path("/var/lib/weekly-report-assistant")
    assert paths.config_file == Path("/etc/weekly-report-assistant/config.toml")
    assert paths.log_dir == Path("/var/log/weekly-report-assistant")


def test_settings_uses_platform_runtime_data_directory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("WRA_DATA_DIR", raising=False)
    monkeypatch.setattr(
        config_module,
        "resolve_runtime_paths",
        lambda: SimpleNamespace(
            data_dir=tmp_path / "platform-data",
            log_dir=tmp_path / "platform-logs",
        ),
    )

    settings = Settings()
    assert settings.data_dir == tmp_path / "platform-data"
    assert settings.log_dir == tmp_path / "platform-logs"
