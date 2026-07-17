from pathlib import Path

import pytest
from docx import Document

from app.infrastructure.docx.writer import DocxWriteError, write_sections


def test_writes_body_header_and_footer_targets(tmp_path: Path) -> None:
    output = tmp_path / "out.docx"

    result = write_sections(
        Path("tests/fixtures/docx/header_footer_placeholder.docx"),
        output,
        {
            "本周重点": "完成统一认证联调",
            "风险问题": "测试资源不足",
            "下周计划": "完成灰度发布",
        },
    )

    document = Document(output)
    assert result.replaced_keys == ["本周重点", "风险问题", "下周计划"]
    assert document.paragraphs[0].text == "完成统一认证联调"
    assert document.sections[0].header.paragraphs[0].text == "测试资源不足"
    assert document.sections[0].footer.paragraphs[0].text == "完成灰度发布"


def test_rejects_duplicate_target_placeholder(tmp_path: Path) -> None:
    source = tmp_path / "duplicate.docx"
    document = Document()
    document.add_paragraph("{{本周重点}}")
    document.add_paragraph("{{本周重点}}")
    document.save(source)

    with pytest.raises(DocxWriteError) as caught:
        write_sections(source, tmp_path / "out.docx", {"本周重点": "完成 A"})

    assert caught.value.code == "DUPLICATE_PLACEHOLDER"
    assert not (tmp_path / "out.docx").exists()
