import pytest

from app.infrastructure.docx.package_guard import UnsafeDocx, inspect_docx_package


def test_rejects_too_many_zip_entries(zip_with_many_entries: bytes) -> None:
    with pytest.raises(UnsafeDocx, match="文件数量"):
        inspect_docx_package(zip_with_many_entries, max_entries=10, max_uncompressed=1_000_000)


def test_accepts_minimal_valid_docx(valid_docx_bytes: bytes) -> None:
    result = inspect_docx_package(valid_docx_bytes, max_entries=100, max_uncompressed=1_000_000)

    assert "word/document.xml" in result.entries

