import os
import platform as platform_module
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    install_dir: Path
    data_dir: Path
    config_file: Path
    log_dir: Path


def resolve_runtime_paths(
    *,
    platform: str | None = None,
    app_dir: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> RuntimePaths:
    system = (platform or platform_module.system()).casefold()
    install_dir = app_dir or _install_dir()
    environment = environ or os.environ

    if system in {"windows", "win32"}:
        data_dir = Path(environment.get("PROGRAMDATA", r"C:\ProgramData")) / (
            "WeeklyReportAssistant"
        )
        return RuntimePaths(
            install_dir=install_dir,
            data_dir=data_dir,
            config_file=data_dir / "config.toml",
            log_dir=data_dir / "logs",
        )
    if system == "linux":
        return RuntimePaths(
            install_dir=install_dir,
            data_dir=Path("/var/lib/weekly-report-assistant"),
            config_file=Path("/etc/weekly-report-assistant/config.toml"),
            log_dir=Path("/var/log/weekly-report-assistant"),
        )
    if system in {"darwin", "macos"}:
        data_dir = Path.home() / "Library/Application Support/WeeklyReportAssistant"
        return RuntimePaths(
            install_dir=install_dir,
            data_dir=data_dir,
            config_file=data_dir / "config.toml",
            log_dir=data_dir / "logs",
        )
    data_dir = install_dir / "data"
    return RuntimePaths(
        install_dir=install_dir,
        data_dir=data_dir,
        config_file=data_dir / "config.toml",
        log_dir=data_dir / "logs",
    )


def _install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]
