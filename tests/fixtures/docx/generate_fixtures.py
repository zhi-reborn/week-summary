from base64 import b64decode
from pathlib import Path

from docx import Document
from docx.shared import Inches

OUTPUT_DIR = Path(__file__).parent


def save_plain() -> None:
    document = Document()
    document.add_heading("周报汇总", level=1)
    document.add_paragraph("{{本周重点}}")
    document.save(OUTPUT_DIR / "plain_placeholder.docx")


def save_table() -> None:
    document = Document()
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "本周重点"
    table.cell(0, 1).text = "{{本周重点}}"
    document.save(OUTPUT_DIR / "table_placeholder.docx")


def save_header_footer() -> None:
    document = Document()
    document.add_paragraph("{{本周重点}}")
    section = document.sections[0]
    section.header.paragraphs[0].text = "{{风险问题}}"
    section.footer.paragraphs[0].text = "{{下周计划}}"
    document.save(OUTPUT_DIR / "header_footer_placeholder.docx")


def save_split_runs() -> None:
    document = Document()
    paragraph = document.add_paragraph()
    paragraph.add_run("{{本")
    paragraph.add_run("周重点}}")
    document.save(OUTPUT_DIR / "split_runs_placeholder.docx")


def save_image_numbering() -> None:
    image_path = OUTPUT_DIR / "fixture.png"
    image_path.write_bytes(
        b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
    )
    document = Document()
    document.add_picture(str(image_path), width=Inches(0.2))
    document.add_paragraph("第一项", style="List Number")
    document.add_paragraph("{{本周重点}}")
    document.save(OUTPUT_DIR / "image_numbering_template.docx")
    image_path.unlink()


if __name__ == "__main__":
    save_plain()
    save_table()
    save_header_footer()
    save_split_runs()
    save_image_numbering()
