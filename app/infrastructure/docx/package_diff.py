from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import cast
from zipfile import ZipFile

from lxml import etree  # type: ignore[import-untyped]


@dataclass(frozen=True)
class PackageDiffResult:
    changed_parts: set[str]
    unexpected_changed_parts: set[str]


def compare_packages(
    before_path: Path,
    after_path: Path,
    *,
    allowed_changed_parts: set[str],
) -> PackageDiffResult:
    before = _snapshot(before_path)
    after = _snapshot(after_path)
    changed = {
        name
        for name in before.keys() | after.keys()
        if before.get(name) != after.get(name)
    }
    return PackageDiffResult(
        changed_parts=changed,
        unexpected_changed_parts=changed - allowed_changed_parts,
    )


def _snapshot(path: Path) -> dict[str, str]:
    with ZipFile(path) as archive:
        return {
            name: sha256(_canonical_content(name, archive.read(name))).hexdigest()
            for name in archive.namelist()
        }


def _canonical_content(name: str, data: bytes) -> bytes:
    if not (name.endswith(".xml") or name.endswith(".rels")):
        return data
    try:
        root = etree.fromstring(data)
    except etree.XMLSyntaxError:
        return data
    return cast(bytes, etree.tostring(root, method="c14n", with_comments=True))
