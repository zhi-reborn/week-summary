from pathlib import Path

from app.infrastructure.docx.template_parser import parse_template


def test_finds_placeholders_in_body_header_and_footer() -> None:
    path = Path("tests/fixtures/docx/header_footer_placeholder.docx")

    sections = parse_template(path)

    assert {(item.name, item.locator.part) for item in sections} == {
        ("本周重点", "document"),
        ("风险问题", "header1"),
        ("下周计划", "footer1"),
    }


def test_finds_placeholder_inside_table() -> None:
    sections = parse_template(Path("tests/fixtures/docx/table_placeholder.docx"))

    assert [item.name for item in sections] == ["本周重点"]
    assert sections[0].method.value == "placeholder"


def test_heading_does_not_reuse_a_placeholder_target() -> None:
    sections = parse_template(Path("tests/fixtures/docx/plain_placeholder.docx"))

    assert [item.name for item in sections] == ["本周重点"]
