from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_windows_service_uses_virtual_account_and_bounded_restart_policy() -> None:
    installer = _read("packaging/windows/install_service.ps1")

    assert r"NT SERVICE\WeeklyReportAssistant" in installer
    assert "sc.exe failure" in installer
    assert "restart/5000/restart/15000" in installer
    assert "icacls.exe" in installer


def test_windows_installer_targets_supported_x64_systems_and_keeps_data_by_default() -> None:
    definition = _read("packaging/windows/weekly-report-assistant.iss")

    assert "ArchitecturesAllowed=x64compatible" in definition
    assert "MinVersion=10.0.17763" in definition
    assert "RemoveDataCheckBox.Checked := False" in definition
    assert "upgrade_backup.ps1" in definition


def test_windows_build_and_acceptance_scripts_have_native_gates() -> None:
    build = _read("scripts/build_windows.ps1")
    acceptance = _read("scripts/test_windows_install.ps1")

    assert "$env:PROCESSOR_ARCHITECTURE -ne \"AMD64\"" in build
    assert "ISCC.exe" in build
    assert "WINDOWS_INSTALL_OK" in acceptance
    assert "/api/health/ready" in acceptance
