import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, cast
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree  # type: ignore[import-untyped]

from app.infrastructure.docx.locator import package_part_name
from app.infrastructure.docx.style_inheritance import (
    append_inherited_run,
    copy_paragraph_properties,
)
from app.infrastructure.docx.template_parser import parse_template

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_XML = "http://www.w3.org/XML/1998/namespace"
_NS = {"w": _W}


@dataclass(frozen=True)
class WriteResult:
    replaced_keys: list[str]


class DocxWriteError(ValueError):
    def __init__(self, code: str, message: str, keys: list[str] | None = None) -> None:
        self.code = code
        self.keys = keys or []
        super().__init__(message)


def write_sections(
    template_path: Path, output_path: Path, values: dict[str, str]
) -> WriteResult:
    sections = {section.name: section for section in parse_template(template_path)}
    missing = sorted(values.keys() - sections.keys())
    if missing:
        raise DocxWriteError(
            "UNKNOWN_SECTION", f"模板中不存在板块：{', '.join(missing)}", missing
        )

    replacements: dict[str, list[tuple[int, str | None, str]]] = {}
    for name, value in values.items():
        locator = sections[name].locator
        part_name = package_part_name(locator.part)
        replacements.setdefault(part_name, []).append(
            (locator.paragraph_index, locator.token, value)
        )

    with ZipFile(template_path) as source:
        source_parts = {info.filename: source.read(info.filename) for info in source.infolist()}
        _validate_unique_tokens(source_parts, sections, list(values))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = _temporary_output(output_path)
        try:
            with ZipFile(temporary_path, "w", ZIP_DEFLATED) as target:
                for info in source.infolist():
                    data = source_parts[info.filename]
                    if info.filename in replacements:
                        data = _replace_in_part(data, replacements[info.filename])
                    target.writestr(info, data)
            os.replace(temporary_path, output_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
    return WriteResult(replaced_keys=list(values))


def _temporary_output(output_path: Path) -> Path:
    with NamedTemporaryFile(
        dir=output_path.parent, prefix=f".{output_path.name}.", suffix=".tmp", delete=False
    ) as temporary:
        return Path(temporary.name)


def _validate_unique_tokens(
    source_parts: dict[str, bytes], sections: dict[str, Any], keys: list[str]
) -> None:
    content_parts = [
        data
        for name, data in source_parts.items()
        if name == "word/document.xml"
        or name.startswith("word/header")
        or name.startswith("word/footer")
    ]
    for key in keys:
        token = sections[key].locator.token
        if token is None:
            continue
        count = sum(_count_token(data, token) for data in content_parts)
        if count == 0:
            raise DocxWriteError("PLACEHOLDER_MISSING", f"模板占位符已失效：{key}", [key])
        if count > 1:
            raise DocxWriteError(
                "DUPLICATE_PLACEHOLDER", f"模板占位符重复：{key}", [key]
            )


def _count_token(data: bytes, token: str) -> int:
    root = etree.fromstring(data)
    paragraphs: list[Any] = root.xpath(".//w:p", namespaces=_NS)
    return sum(
        "".join(node.text or "" for node in paragraph.xpath(".//w:t", namespaces=_NS)).count(
            token
        )
        for paragraph in paragraphs
    )


def _replace_in_part(data: bytes, replacements: list[tuple[int, str | None, str]]) -> bytes:
    root = etree.fromstring(data)
    paragraphs: list[Any] = root.xpath(".//w:p", namespaces=_NS)
    for paragraph_index, token, value in replacements:
        if paragraph_index >= len(paragraphs):
            raise DocxWriteError("STALE_LOCATOR", "模板定位已失效")
        _replace_paragraph(paragraphs[paragraph_index], token, value)
    return cast(
        bytes,
        etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True),
    )


def _replace_paragraph(paragraph: Any, token: str | None, value: str) -> None:
    nodes: list[Any] = paragraph.xpath(".//w:t", namespaces=_NS)
    if not nodes:
        run = etree.SubElement(paragraph, f"{{{_W}}}r")
        nodes = [etree.SubElement(run, f"{{{_W}}}t")]
    combined = "".join(node.text or "" for node in nodes)
    start = 0 if token is None else combined.find(token)
    if start < 0:
        raise DocxWriteError("PLACEHOLDER_MISSING", "模板占位符已失效")
    end = len(combined) if token is None else start + len(token)
    first_index, first_offset = _node_at(nodes, start, prefer_next=True)
    last_index, last_offset = _node_at(nodes, end, prefer_next=False)
    lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    first_node = nodes[first_index]
    last_node = nodes[last_index]
    first_text = first_node.text or ""
    last_text = last_node.text or ""
    prefix = first_text[:first_offset]
    suffix = last_text[last_offset:]

    _set_text(first_node, prefix + lines[0] + (suffix if first_index == last_index else ""))
    for index in range(first_index + 1, last_index):
        _set_text(nodes[index], "")
    if last_index > first_index:
        _set_text(last_node, suffix)

    source_run = first_node.getparent()
    previous = paragraph
    for line in lines[1:]:
        new_paragraph = etree.Element(f"{{{_W}}}p")
        copy_paragraph_properties(paragraph, new_paragraph)
        append_inherited_run(new_paragraph, source_run, line)
        parent = previous.getparent()
        parent.insert(parent.index(previous) + 1, new_paragraph)
        previous = new_paragraph


def _node_at(nodes: list[Any], position: int, *, prefer_next: bool) -> tuple[int, int]:
    offset = 0
    for index, node in enumerate(nodes):
        length = len(node.text or "")
        boundary_matches = position == offset + length
        if position < offset + length or (boundary_matches and not prefer_next):
            return index, position - offset
        if boundary_matches and prefer_next and index + 1 < len(nodes):
            return index + 1, 0
        offset += length
    return len(nodes) - 1, len(nodes[-1].text or "")


def _set_text(node: Any, value: str) -> None:
    node.text = value
    preserve = f"{{{_XML}}}space"
    if value[:1].isspace() or value[-1:].isspace():
        node.set(preserve, "preserve")
    else:
        node.attrib.pop(preserve, None)
