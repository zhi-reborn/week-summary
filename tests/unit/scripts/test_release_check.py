from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.release_check import (
    ReleaseCheckError,
    expected_artifact_names,
    read_declared_versions,
    validate_release,
    write_checksums,
)


ROOT = Path(__file__).resolve().parents[3]


def test_repository_version_declarations_are_consistent() -> None:
    versions = read_declared_versions(ROOT)

    assert versions == {
        "VERSION": "0.1.0",
        "backend": "0.1.0",
        "frontend": "0.1.0",
        "windows_installer": "0.1.0",
    }


def test_native_build_scripts_read_the_root_version_file() -> None:
    linux_build = (ROOT / "scripts" / "build_linux.sh").read_text(encoding="utf-8")
    windows_build = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8-sig")

    assert '"$ROOT/VERSION"' in linux_build
    assert 'Join-Path $Root "VERSION"' in windows_build
    assert "WeeklyReportAssistant-$Version-windows-x64.exe" in windows_build


def test_release_validation_accepts_exact_artifacts_and_checksums(tmp_path: Path) -> None:
    version = "0.1.0"
    for index, name in enumerate(expected_artifact_names(version), start=1):
        (tmp_path / name).write_bytes(f"artifact-{index}".encode())

    write_checksums(tmp_path, version)

    result = validate_release(ROOT, tmp_path)

    assert result.version == version
    assert result.artifact_count == 3
    assert result.checksum_count == 3


def test_release_validation_rejects_modified_artifact(tmp_path: Path) -> None:
    version = "0.1.0"
    for name in expected_artifact_names(version):
        (tmp_path / name).write_bytes(name.encode())
    write_checksums(tmp_path, version)
    artifact = tmp_path / expected_artifact_names(version)[0]
    artifact.write_bytes(b"modified")

    with pytest.raises(ReleaseCheckError, match="SHA-256"):
        validate_release(ROOT, tmp_path)


def test_release_validation_rejects_missing_or_unexpected_packages(tmp_path: Path) -> None:
    version = "0.1.0"
    names = expected_artifact_names(version)
    for name in names[:-1]:
        (tmp_path / name).write_bytes(hashlib.sha256(name.encode()).digest())
    (tmp_path / "old-release.deb").write_bytes(b"old")

    with pytest.raises(ReleaseCheckError, match="安装包集合"):
        write_checksums(tmp_path, version)


def test_release_validation_rejects_inconsistent_source_versions(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "weekly-report-assistant"\nversion = "0.1.1"\n',
        encoding="utf-8",
    )
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text('{"version":"0.1.0"}', encoding="utf-8")
    windows = tmp_path / "packaging" / "windows"
    windows.mkdir(parents=True)
    (windows / "weekly-report-assistant.iss").write_text(
        '#define MyAppVersion "0.1.0"\n', encoding="utf-8"
    )

    with pytest.raises(ReleaseCheckError, match="版本声明不一致"):
        validate_release(tmp_path, tmp_path / "installers")
