from typing import Protocol


class SecretStore(Protocol):
    def save(self, name: str, value: str) -> None: ...

    def load(self, name: str) -> str | None: ...

    def delete(self, name: str) -> None: ...


def validate_secret_name(name: str) -> str:
    if not name or not all(character.isalnum() or character in "._-" for character in name):
        raise ValueError("密钥名称无效")
    return name
