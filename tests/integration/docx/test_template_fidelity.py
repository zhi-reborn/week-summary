from pathlib import Path

from app.infrastructure.docx.package_diff import compare_packages
from app.infrastructure.docx.writer import write_sections


def test_only_target_document_part_changes(tmp_path: Path) -> None:
    source = Path("tests/fixtures/docx/image_numbering_template.docx")
    output = tmp_path / "out.docx"
    write_sections(source, output, {"本周重点": "完成项目 A\n完成项目 B"})

    result = compare_packages(source, output, allowed_changed_parts={"word/document.xml"})

    assert result.changed_parts == {"word/document.xml"}
    assert result.unexpected_changed_parts == set()


def test_header_footer_changes_are_explicitly_scoped(tmp_path: Path) -> None:
    source = Path("tests/fixtures/docx/header_footer_placeholder.docx")
    output = tmp_path / "out.docx"
    write_sections(
        source,
        output,
        {"风险问题": "资源不足", "下周计划": "完成灰度发布"},
    )

    result = compare_packages(
        source,
        output,
        allowed_changed_parts={"word/header1.xml", "word/footer1.xml"},
    )

    assert result.unexpected_changed_parts == set()
