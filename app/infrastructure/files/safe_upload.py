import re


def safe_filename(name: str) -> str:
    basename = re.split(r"[/\\]", name)[-1]
    if (
        not basename
        or basename in {".", ".."}
        or any(ord(character) < 32 or ord(character) == 127 for character in basename)
    ):
        raise ValueError("文件名无效")
    return basename
