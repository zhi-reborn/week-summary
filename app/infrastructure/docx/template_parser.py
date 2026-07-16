import re
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from lxml import etree  # type: ignore[import-untyped]

from app.domain.template import RecognitionMethod, TemplateLocator, TemplateSection
from app.infrastructure.docx.locator import logical_part_name

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NS = {"w": _W}
_PLACEHOLDER = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_KNOWN_HEADINGS = {"本周重点", "本周进展", "风险问题", "下周计划", "需要协助"}


def parse_template(path: Path) -> list[TemplateSection]:
    candidates: list[tuple[str, int, str, RecognitionMethod, float, str | None]] = []
    with ZipFile(path) as archive:
        for package_name in _ordered_content_parts(archive.namelist()):
            root = etree.fromstring(archive.read(package_name))
            paragraphs: list[Any] = root.xpath(".//w:p", namespaces=_NS)
            part = logical_part_name(package_name)
            for index, paragraph in enumerate(paragraphs):
                text = _paragraph_text(paragraph)
                for match in _PLACEHOLDER.finditer(text):
                    name = match.group(1).strip()
                    if name:
                        candidates.append(
                            (part, index, name, RecognitionMethod.PLACEHOLDER, 1.0, match.group(0))
                        )

            if part == "document":
                candidates.extend(_heading_candidates(paragraphs, candidates))

    return [
        TemplateSection(
            id=f"S{index:02d}",
            name=name,
            method=method,
            confidence=confidence,
            locator=TemplateLocator(part=part, paragraph_index=paragraph_index, token=token),
        )
        for index, (part, paragraph_index, name, method, confidence, token) in enumerate(
            _deduplicate(candidates), start=1
        )
    ]


def _ordered_content_parts(names: list[str]) -> list[str]:
    parts = [
        name
        for name in names
        if name == "word/document.xml"
        or re.fullmatch(r"word/(?:header|footer)\d+\.xml", name)
    ]
    return sorted(parts, key=lambda name: (name != "word/document.xml", name))


def _paragraph_text(paragraph: Any) -> str:
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=_NS))


def _heading_candidates(
    paragraphs: list[Any],
    existing: list[tuple[str, int, str, RecognitionMethod, float, str | None]],
) -> list[tuple[str, int, str, RecognitionMethod, float, str | None]]:
    existing_names = {item[2] for item in existing}
    results: list[tuple[str, int, str, RecognitionMethod, float, str | None]] = []
    for index, paragraph in enumerate(paragraphs[:-1]):
        text = _paragraph_text(paragraph).strip()
        if not text or text in existing_names or _PLACEHOLDER.search(text):
            continue
        styles = paragraph.xpath("./w:pPr/w:pStyle/@w:val", namespaces=_NS)
        if styles and str(styles[0]).lower().startswith("heading"):
            results.append(("document", index + 1, text, RecognitionMethod.HEADING_STYLE, 0.9, None))
        elif text in _KNOWN_HEADINGS:
            results.append(("document", index + 1, text, RecognitionMethod.HEADING_TEXT, 0.8, None))
    return results


def _deduplicate(
    candidates: list[tuple[str, int, str, RecognitionMethod, float, str | None]],
) -> list[tuple[str, int, str, RecognitionMethod, float, str | None]]:
    selected: dict[str, tuple[str, int, str, RecognitionMethod, float, str | None]] = {}
    for candidate in candidates:
        selected.setdefault(candidate[2], candidate)
    return list(selected.values())
