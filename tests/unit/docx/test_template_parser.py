from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE

from app.infrastructure.docx.template_parser import parse_template


def _instruction_template(path: Path) -> None:
    document = Document()
    document.styles.add_style("Weekly Section", WD_STYLE_TYPE.PARAGRAPH)
    document.styles.add_style("Weekly Group", WD_STYLE_TYPE.PARAGRAPH)
    document.add_paragraph("一、本周工作概述", style="Weekly Section")
    document.add_paragraph(
        "业务连续性：【概述本周成果。】 产品化建设：【概述产品进展。】"
    )
    document.add_paragraph("二、本周重点工作", style="Weekly Section")
    document.add_paragraph("业务连续性", style="Weekly Group")
    document.add_paragraph("系统/项目名称，【填写完成情况。】")
    document.add_paragraph("系统/项目名称，【填写后续安排。】")
    document.add_paragraph("三、问题及风险点", style="Weekly Section")
    document.add_paragraph("【无；如有，请填写风险及计划。】")
    document.add_paragraph("四、下周重点工作", style="Weekly Section")
    document.add_paragraph("1. 【填写下周计划一。】")
    document.save(path)


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


def test_finds_instruction_placeholders_with_hierarchical_unique_names(
    tmp_path: Path,
) -> None:
    path = tmp_path / "instruction-template.docx"
    _instruction_template(path)

    sections = parse_template(path)

    assert [section.name for section in sections] == [
        "本周工作概述 / 业务连续性",
        "本周工作概述 / 产品化建设",
        "本周重点工作 / 业务连续性 / 系统/项目名称",
        "本周重点工作 / 业务连续性 / 系统/项目名称（2）",
        "问题及风险点",
        "下周重点工作 / 计划一",
    ]
    assert all(section.method.value == "instruction_placeholder" for section in sections)
    assert all(section.confidence == 0.95 for section in sections)
    assert sections[0].instruction == "概述本周成果。"
    assert sections[0].locator.token == "【概述本周成果。】"


def test_ignores_non_instruction_square_brackets(tmp_path: Path) -> None:
    path = tmp_path / "ordinary-brackets.docx"
    document = Document()
    document.add_paragraph("变更结果【符合预期】")
    document.save(path)

    assert parse_template(path) == []
