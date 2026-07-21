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


def test_linux_installers_back_up_data_and_clean_sqlite_sidecars_on_rollback() -> None:
    install = _read("packaging/linux/install.sh")
    preinst = _read("packaging/linux/preinst")
    postinst = _read("packaging/linux/postinst")

    assert "restore_previous" in install
    assert "app.db-wal" in install
    assert "package-rollback" in preinst
    assert "rollback_failed_upgrade" in postinst
    assert "app.db-wal" in postinst
    assert "systemctl disable --now weekly-report-assistant.service" in postinst


def test_tar_installer_rolls_back_all_failures_after_stopping_the_old_service() -> None:
    install = _read("packaging/linux/install.sh")

    assert install.index("trap restore_previous EXIT") < install.rindex(
        'systemctl stop "$SERVICE_NAME.service"'
    )
    assert "trap abort_install HUP INT TERM" in install
    assert "INSTALL_SUCCESS=1" in install
    assert install.index('for name in app.db model_settings.json') < install.index(
        'mv "$INSTALL_DIR" "$PREVIOUS_DIR"'
    )


def test_deb_failure_restores_data_without_overwriting_dpkg_managed_files() -> None:
    preinst = _read("packaging/linux/preinst")
    postinst = _read("packaging/linux/postinst")

    assert '"$ROLLBACK_DIR/program"' not in preinst
    assert 'cp -a "$ROLLBACK_DIR/program/." "$INSTALL_DIR/"' not in postinst
    assert 'cp -a "$ROLLBACK_DIR/service"' not in postinst


def test_linux_build_requires_native_x86_64_and_produces_both_formats() -> None:
    build = _read("scripts/build_linux.sh")
    acceptance = _read("scripts/test_linux_install.sh")

    assert '[[ "$(uname -s)" == "Linux" ]]' in build
    assert '[[ "$(uname -m)" == "x86_64" ]]' in build
    assert "dpkg-deb" in build
    assert "tar -czf" in build
    assert "LINUX_INSTALL_OK" in acceptance
    assert "/api/health/ready" in acceptance
