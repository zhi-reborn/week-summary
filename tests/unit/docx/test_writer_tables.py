from pathlib import Path

from docx import Document

from app.infrastructure.docx.writer import write_sections


def test_writes_multiple_paragraphs_inside_target_table_cell(tmp_path: Path) -> None:
    output = tmp_path / "out.docx"

    write_sections(
        Path("tests/fixtures/docx/table_placeholder.docx"),
        output,
        {"本周重点": "完成项目 A\n完成项目 B"},
    )

    document = Document(output)
    assert len(document.tables[0].rows) == 1
    assert [paragraph.text for paragraph in document.tables[0].cell(0, 1).paragraphs] == [
        "完成项目 A",
        "完成项目 B",
    ]
