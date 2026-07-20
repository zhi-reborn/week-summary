import pytest

from app.infrastructure.files.safe_upload import safe_filename


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("../a.txt", "a.txt"),
        ("..\\a.txt", "a.txt"),
        ("/tmp/a.txt", "a.txt"),
        ("C:\\temp\\a.txt", "a.txt"),
    ],
)
def test_safe_filename_ignores_client_paths(name: str, expected: str) -> None:
    assert safe_filename(name) == expected


@pytest.mark.parametrize("name", ["", ".", "..", "bad\x00name.txt"])
def test_safe_filename_rejects_empty_or_unsafe_basename(name: str) -> None:
    with pytest.raises(ValueError, match="文件名"):
        safe_filename(name)
