from dataclasses import dataclass
from io import BytesIO
from zipfile import BadZipFile, ZipFile


class UnsafeDocx(ValueError):
    pass


@dataclass(frozen=True)
class DocxPackageInfo:
    entries: tuple[str, ...]
    uncompressed_bytes: int


def inspect_docx_package(
    data: bytes,
    *,
    max_entries: int,
    max_uncompressed: int,
) -> DocxPackageInfo:
    try:
        with ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > max_entries:
                raise UnsafeDocx("DOCX 内文件数量超过限制")
            total = sum(item.file_size for item in infos)
            if total > max_uncompressed:
                raise UnsafeDocx("DOCX 解压后大小超过限制")
            names = tuple(item.filename for item in infos)
            required = {"[Content_Types].xml", "word/document.xml"}
            if not required.issubset(names):
                raise UnsafeDocx("文件不是有效 DOCX")
            return DocxPackageInfo(entries=names, uncompressed_bytes=total)
    except BadZipFile as exc:
        raise UnsafeDocx("文件不是有效 ZIP/DOCX") from exc
