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
_INSTRUCTION_PLACEHOLDER = re.compile(
    r"【(?P<instruction>(?:填写|概述|无[；;，, ]*如有[，, ]*请填写)[^【】]*)】"
)
_SECTION_PREFIX = re.compile(r"^[一二三四五六七八九十]+[、，,.．]\s*")
_ITEM_PREFIX = re.compile(r"^\d+[.、．]\s*")
_PLAN_LABEL = re.compile(r"填写下周(?P<label>计划[一二三四五六七八九十\d]+)")
_KNOWN_HEADINGS = {"本周重点", "本周进展", "风险问题", "下周计划", "需要协助"}
_Candidate = tuple[
    str,
    int,
    str,
    RecognitionMethod,
    float,
    str | None,
    str,
]


def parse_template(path: Path) -> list[TemplateSection]:
    candidates: list[_Candidate] = []
    name_counts: dict[str, int] = {}
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
                            (
                                part,
                                index,
                                name,
                                RecognitionMethod.PLACEHOLDER,
                                1.0,
                                match.group(0),
                                "",
                            )
                        )
                        name_counts[name] = name_counts.get(name, 0) + 1

            candidates.extend(_instruction_candidates(part, paragraphs, name_counts))

            if part == "document":
                candidates.extend(_heading_candidates(paragraphs, candidates))

    return [
        TemplateSection(
            id=f"S{index:02d}",
            name=name,
            method=method,
            confidence=confidence,
            locator=TemplateLocator(part=part, paragraph_index=paragraph_index, token=token),
            instruction=instruction,
        )
        for index, (
            part,
            paragraph_index,
            name,
            method,
            confidence,
            token,
            instruction,
        ) in enumerate(
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


def _instruction_candidates(
    part: str,
    paragraphs: list[Any],
    name_counts: dict[str, int],
) -> list[_Candidate]:
    results: list[_Candidate] = []
    section = ""
    group = ""
    for index, paragraph in enumerate(paragraphs):
        text = _paragraph_text(paragraph).strip()
        style = _paragraph_style(paragraph)
        if style == "weeklysection":
            section = _clean_label(text)
            group = ""
        elif style == "weeklygroup":
            group = _clean_label(text)

        previous_end = 0
        for match in _INSTRUCTION_PLACEHOLDER.finditer(text):
            instruction = match.group("instruction").strip()
            field = _clean_label(text[previous_end : match.start()])
            if not field and (plan_match := _PLAN_LABEL.search(instruction)):
                field = plan_match.group("label")
            base_name = _hierarchical_name(section, group, field)
            if not base_name:
                previous_end = match.end()
                continue
            name = _unique_name(base_name, name_counts)
            results.append(
                (
                    part,
                    index,
                    name,
                    RecognitionMethod.INSTRUCTION_PLACEHOLDER,
                    0.95,
                    match.group(0),
                    instruction,
                )
            )
            previous_end = match.end()
    return results


def _paragraph_style(paragraph: Any) -> str:
    styles = paragraph.xpath("./w:pPr/w:pStyle/@w:val", namespaces=_NS)
    if not styles:
        return ""
    return str(styles[0]).replace(" ", "").casefold()


def _clean_label(value: str) -> str:
    cleaned = _SECTION_PREFIX.sub("", value.strip())
    cleaned = _ITEM_PREFIX.sub("", cleaned)
    return cleaned.strip(" \t:：,，;；。")


def _hierarchical_name(section: str, group: str, field: str) -> str:
    parts: list[str] = []
    for value in (section, group, field):
        if value and value not in parts:
            parts.append(value)
    return " / ".join(parts)


def _unique_name(name: str, counts: dict[str, int]) -> str:
    count = counts.get(name, 0) + 1
    counts[name] = count
    return name if count == 1 else f"{name}（{count}）"


def _heading_candidates(
    paragraphs: list[Any],
    existing: list[_Candidate],
) -> list[_Candidate]:
    existing_names = {item[2] for item in existing}
    claimed_targets = {item[1] for item in existing if item[0] == "document"}
    results: list[_Candidate] = []
    for index, paragraph in enumerate(paragraphs[:-1]):
        text = _paragraph_text(paragraph).strip()
        if (
            not text
            or text in existing_names
            or _PLACEHOLDER.search(text)
            or index + 1 in claimed_targets
        ):
            continue
        styles = paragraph.xpath("./w:pPr/w:pStyle/@w:val", namespaces=_NS)
        if styles and str(styles[0]).lower().startswith("heading"):
            results.append(
                ("document", index + 1, text, RecognitionMethod.HEADING_STYLE, 0.9, None, "")
            )
        elif text in _KNOWN_HEADINGS:
            results.append(
                ("document", index + 1, text, RecognitionMethod.HEADING_TEXT, 0.8, None, "")
            )
    return results


def _deduplicate(
    candidates: list[_Candidate],
) -> list[_Candidate]:
    selected: dict[str, _Candidate] = {}
    for candidate in candidates:
        selected.setdefault(candidate[2], candidate)
    return list(selected.values())
