import pytest

from app.infrastructure.files.safe_upload import safe_filename


@pytest.mark.parametrize("name", ["../a.txt", "..\\a.txt", "/tmp/a.txt", "C:\\a.txt"])
def test_safe_filename_rejects_paths(name: str) -> None:
    with pytest.raises(ValueError, match="文件名"):
        safe_filename(name)

