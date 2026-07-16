from pathlib import Path
from typing import Any, cast
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree  # type: ignore[import-untyped]

from app.infrastructure.docx.locator import package_part_name
from app.infrastructure.docx.template_parser import parse_template

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_XML = "http://www.w3.org/XML/1998/namespace"
_NS = {"w": _W}


def write_sections(template_path: Path, output_path: Path, values: dict[str, str]) -> None:
    sections = {section.name: section for section in parse_template(template_path)}
    missing = sorted(values.keys() - sections.keys())
    if missing:
        raise ValueError(f"模板中不存在板块：{', '.join(missing)}")

    replacements: dict[str, list[tuple[int, str | None, str]]] = {}
    for name, value in values.items():
        locator = sections[name].locator
        part_name = package_part_name(locator.part)
        replacements.setdefault(part_name, []).append(
            (locator.paragraph_index, locator.token, value)
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(template_path) as source, ZipFile(output_path, "w", ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename in replacements:
                data = _replace_in_part(data, replacements[info.filename])
            target.writestr(info, data)


def _replace_in_part(data: bytes, replacements: list[tuple[int, str | None, str]]) -> bytes:
    root = etree.fromstring(data)
    paragraphs: list[Any] = root.xpath(".//w:p", namespaces=_NS)
    for paragraph_index, token, value in replacements:
        if paragraph_index >= len(paragraphs):
            raise ValueError("模板定位已失效")
        _replace_paragraph(paragraphs[paragraph_index], token, value)
    return cast(
        bytes,
        etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True),
    )


def _replace_paragraph(paragraph: Any, token: str | None, value: str) -> None:
    nodes: list[Any] = paragraph.xpath(".//w:t", namespaces=_NS)
    combined = "".join(node.text or "" for node in nodes)
    replacement = value if token is None else combined.replace(token, value, 1)
    if token is not None and replacement == combined:
        raise ValueError("模板占位符已失效")
    if not nodes:
        run = etree.SubElement(paragraph, f"{{{_W}}}r")
        nodes = [etree.SubElement(run, f"{{{_W}}}t")]
    nodes[0].text = replacement
    if replacement[:1].isspace() or replacement[-1:].isspace():
        nodes[0].set(f"{{{_XML}}}space", "preserve")
    for node in nodes[1:]:
        node.text = ""
