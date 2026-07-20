import stat
from pathlib import Path

import pytest

from app.infrastructure.secrets.linux_file_store import LinuxFileSecretStore
from app.infrastructure.secrets.windows_dpapi import WindowsDPAPISecretStore


def test_linux_secret_file_has_restricted_permissions(tmp_path: Path) -> None:
    store = LinuxFileSecretStore(tmp_path / "secrets")

    store.save("model_api_key", "secret-value")

    secret_path = tmp_path / "secrets" / "model_api_key"
    assert store.load("model_api_key") == "secret-value"
    assert stat.S_IMODE(secret_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600
    store.delete("model_api_key")
    assert store.load("model_api_key") is None


def test_windows_store_persists_only_protected_bytes(tmp_path: Path) -> None:
    store = WindowsDPAPISecretStore(
        tmp_path,
        protect=lambda value: b"protected:" + value,
        unprotect=lambda value: value.removeprefix(b"protected:"),
    )

    store.save("model_api_key", "secret-value")

    assert (tmp_path / "model_api_key").read_bytes() == b"protected:secret-value"
    assert store.load("model_api_key") == "secret-value"


@pytest.mark.parametrize("name", ["../key", "nested/key", "nested\\key", ""])
def test_secret_names_cannot_escape_store(tmp_path: Path, name: str) -> None:
    store = LinuxFileSecretStore(tmp_path)

    with pytest.raises(ValueError):
        store.save(name, "secret")
