import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from docx import Document
from lxml import etree  # type: ignore[import-untyped]

_RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_PLACEHOLDER = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


@dataclass(frozen=True)
class DocxValidationResult:
    valid: bool
    errors: list[str]
    unresolved_placeholders: list[str]


def validate_docx(path: Path, expected_sections: set[str]) -> DocxValidationResult:
    errors: list[str] = []
    unresolved: list[str] = []
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            if archive.testzip() is not None:
                errors.append("CORRUPT_ZIP_ENTRY")
            if not {"[Content_Types].xml", "word/document.xml"} <= names:
                errors.append("MISSING_REQUIRED_PART")
            if _missing_relationship_targets(archive, names):
                errors.append("MISSING_RELATIONSHIP_TARGET")
            unresolved = _unresolved_placeholders(archive)
            expected_unresolved = set(unresolved) & expected_sections
            if unresolved or expected_unresolved:
                errors.append("UNRESOLVED_PLACEHOLDER")
    except (BadZipFile, OSError, etree.XMLSyntaxError):
        return DocxValidationResult(False, ["INVALID_ZIP"], [])

    try:
        Document(str(path))
    except Exception:
        errors.append("WORD_REOPEN_FAILED")
    return DocxValidationResult(not errors, list(dict.fromkeys(errors)), unresolved)


def _missing_relationship_targets(archive: ZipFile, names: set[str]) -> list[str]:
    missing: list[str] = []
    for relationship_part in (name for name in names if name.endswith(".rels")):
        root = etree.fromstring(archive.read(relationship_part))
        relationships: list[Any] = root.findall(f"{{{_RELATIONSHIPS}}}Relationship")
        base = _relationship_base(relationship_part)
        for relationship in relationships:
            if relationship.get("TargetMode") == "External":
                continue
            target = (relationship.get("Target") or "").replace("\\", "/")
            if not target:
                continue
            resolved = (
                target.lstrip("/")
                if target.startswith("/")
                else posixpath.normpath(posixpath.join(base, target.split("#", 1)[0]))
            )
            if resolved not in names:
                missing.append(resolved)
    return missing


def _relationship_base(relationship_part: str) -> str:
    if relationship_part == "_rels/.rels":
        return ""
    parent, _rels, filename = relationship_part.rpartition("/_rels/")
    if not _rels:
        return posixpath.dirname(relationship_part)
    source_part = posixpath.join(parent, filename.removesuffix(".rels"))
    return posixpath.dirname(source_part)


def _unresolved_placeholders(archive: ZipFile) -> list[str]:
    results: list[str] = []
    for name in archive.namelist():
        if not (
            name == "word/document.xml"
            or name.startswith("word/header")
            or name.startswith("word/footer")
        ):
            continue
        root = etree.fromstring(archive.read(name))
        paragraphs: list[Any] = root.xpath(".//w:p", namespaces={"w": _W})
        for paragraph in paragraphs:
            text = "".join(paragraph.xpath(".//w:t/text()", namespaces={"w": _W}))
            results.extend(match.group(1).strip() for match in _PLACEHOLDER.finditer(text))
    return results
