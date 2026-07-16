from pathlib import PurePosixPath


def logical_part_name(package_name: str) -> str:
    path = PurePosixPath(package_name)
    if path.name == "document.xml":
        return "document"
    return path.stem


def package_part_name(logical_name: str) -> str:
    if logical_name == "document":
        return "word/document.xml"
    return f"word/{logical_name}.xml"

