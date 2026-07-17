from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.infrastructure.docx.validator import validate_docx
from app.infrastructure.docx.writer import write_sections


def test_rejects_corrupt_package(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.docx"
    corrupt.write_bytes(b"not-a-docx")

    result = validate_docx(corrupt, expected_sections={"本周重点"})

    assert result.valid is False
    assert "INVALID_ZIP" in result.errors


def test_rejects_unresolved_placeholder() -> None:
    result = validate_docx(
        Path("tests/fixtures/docx/plain_placeholder.docx"),
        expected_sections={"本周重点"},
    )

    assert result.valid is False
    assert "UNRESOLVED_PLACEHOLDER" in result.errors


def test_accepts_written_docx_that_can_be_reopened(tmp_path: Path) -> None:
    output = tmp_path / "out.docx"
    write_sections(
        Path("tests/fixtures/docx/plain_placeholder.docx"),
        output,
        {"本周重点": "完成统一认证联调"},
    )

    result = validate_docx(output, expected_sections={"本周重点"})

    assert result.valid is True
    assert result.errors == []


def test_rejects_missing_internal_relationship_target(tmp_path: Path) -> None:
    source = Path("tests/fixtures/docx/plain_placeholder.docx")
    broken = tmp_path / "broken.docx"
    with ZipFile(source) as archive, ZipFile(broken, "w", ZIP_DEFLATED) as output:
        for info in archive.infolist():
            if info.filename != "word/styles.xml":
                output.writestr(info, archive.read(info.filename))

    result = validate_docx(broken, expected_sections=set())

    assert result.valid is False
    assert "MISSING_RELATIONSHIP_TARGET" in result.errors
