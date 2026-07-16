from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile


def snapshot_docx_parts(path: Path) -> dict[str, str]:
    with ZipFile(path) as archive:
        return {
            name: sha256(archive.read(name)).hexdigest()
            for name in archive.namelist()
            if name != "docProps/core.xml"
        }


def changed_parts(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}

