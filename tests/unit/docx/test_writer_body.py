from pathlib import Path

from docx import Document
from docx.shared import RGBColor

from app.infrastructure.docx.writer import write_sections


def test_replaces_split_placeholder_with_multiple_paragraphs(tmp_path: Path) -> None:
    output = tmp_path / "out.docx"

    result = write_sections(
        Path("tests/fixtures/docx/split_runs_placeholder.docx"),
        output,
        {"本周重点": "完成项目 A\n完成项目 B"},
    )

    document = Document(output)
    assert result.replaced_keys == ["本周重点"]
    assert [paragraph.text for paragraph in document.paragraphs] == [
        "完成项目 A",
        "完成项目 B",
    ]
    assert "{{本周重点}}" not in "\n".join(paragraph.text for paragraph in document.paragraphs)


def test_new_paragraph_inherits_placeholder_run_style(tmp_path: Path) -> None:
    source = tmp_path / "styled.docx"
    output = tmp_path / "out.docx"
    document = Document()
    paragraph = document.add_paragraph()
    run = paragraph.add_run("{{本周重点}}")
    run.bold = True
    run.font.color.rgb = RGBColor(0x24, 0x57, 0xA6)
    document.save(source)

    write_sections(source, output, {"本周重点": "第一项\n第二项"})

    written = Document(output)
    assert written.paragraphs[0].runs[0].bold is True
    assert written.paragraphs[1].runs[0].bold is True
    assert written.paragraphs[1].runs[0].font.color.rgb == RGBColor(0x24, 0x57, 0xA6)
