from codecs import BOM_UTF8
from dataclasses import dataclass


class UnsupportedTextEncoding(ValueError):
    pass


@dataclass(frozen=True)
class DecodedReport:
    text: str
    encoding: str


def decode_report(data: bytes) -> DecodedReport:
    candidates = ["utf-8-sig"] if data.startswith(BOM_UTF8) else ["utf-8", "gb18030"]
    for encoding in candidates:
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if _looks_like_text(text):
            return DecodedReport(text=text, encoding=encoding)
    raise UnsupportedTextEncoding("TXT 编码不受支持")


def _looks_like_text(text: str) -> bool:
    if not text or "\x00" in text:
        return False
    readable = sum(character.isprintable() or character in "\n\r\t" for character in text)
    return readable / len(text) >= 0.9

