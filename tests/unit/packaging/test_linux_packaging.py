from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_systemd_unit_uses_restricted_service_account_and_writable_paths() -> None:
    unit = _read("packaging/linux/weekly-report-assistant.service")

    assert "User=weekly-report" in unit
    assert "NoNewPrivileges=true" in unit
    assert "PrivateTmp=true" in unit
    assert "ProtectSystem=strict" in unit
    assert "ProtectHome=true" in unit
    assert "ReadWritePaths=/var/lib/weekly-report-assistant /var/log/weekly-report-assistant" in unit
    assert "127.0.0.1" in unit


def test_linux_installers_keep_data_by_default_and_support_explicit_purge() -> None:
    install = _read("packaging/linux/install.sh")
    uninstall = _read("packaging/linux/uninstall.sh")

    assert "weekly-report" in install
    assert "/var/lib/weekly-report-assistant" in install
    assert '"$INSTALL_DIR/installer/uninstall.sh"' in install
    assert 'if [[ "${1:-}" == "--purge" ]]' in uninstall
    assert "rm -rf /var/lib/weekly-report-assistant" in uninstall


def test_linux_upgrade_rollback_restores_program_data_and_service() -> None:
    install = _read("packaging/linux/install.sh")
    preinst = _read("packaging/linux/preinst")
    postinst = _read("packaging/linux/postinst")

    assert "restore_previous" in install
    assert "app.db-wal" in install
    assert "package-rollback" in preinst
    assert "is-upgrade" in preinst
    assert "rollback_failed_upgrade" in postinst
    assert "app.db-wal" in postinst
    assert "systemctl disable --now weekly-report-assistant.service" in postinst


def test_linux_build_requires_native_x86_64_and_produces_both_formats() -> None:
    build = _read("scripts/build_linux.sh")
    acceptance = _read("scripts/test_linux_install.sh")

    assert '[[ "$(uname -s)" == "Linux" ]]' in build
    assert '[[ "$(uname -m)" == "x86_64" ]]' in build
    assert "dpkg-deb" in build
    assert "tar -czf" in build
    assert "LINUX_INSTALL_OK" in acceptance
    assert "/api/health/ready" in acceptance
