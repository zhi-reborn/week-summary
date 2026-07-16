from pathlib import Path

from docx import Document

from app.infrastructure.docx.writer import write_sections
from tests.helpers.docx_diff import changed_parts, snapshot_docx_parts


def test_replaces_split_run_placeholder_without_touching_other_parts(tmp_path: Path) -> None:
    source = Path("tests/fixtures/docx/split_runs_placeholder.docx")
    before = snapshot_docx_parts(source)
    output = tmp_path / "out.docx"

    write_sections(source, output, {"本周重点": "完成统一认证联调。"})

    after = snapshot_docx_parts(output)
    text = "\n".join(paragraph.text for paragraph in Document(output).paragraphs)
    assert text.count("完成统一认证联调。") == 1
    assert changed_parts(before, after) == {"word/document.xml"}

