from pathlib import PurePath


def safe_filename(name: str) -> str:
    if not name or PurePath(name).name != name or "/" in name or "\\" in name:
        raise ValueError("文件名不能包含路径")
    if name in {".", ".."}:
        raise ValueError("文件名无效")
    return name

