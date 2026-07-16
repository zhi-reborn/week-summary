import re
from dataclasses import dataclass

from app.domain.people import PersonSegment, SegmentationResult, SourceSpan

_NAME_HEADER = re.compile(r"^\s*姓名\s*[:：]\s*(?P<name>[^\s:：]{1,80})\s*$")
_WEEKLY_HEADER = re.compile(r"^\s*(?P<name>[\u3400-\u9fffA-Za-z0-9·]{1,80})\s*周报\s*$")


@dataclass(frozen=True)
class _Header:
    line_index: int
    name: str


def segment_people(text: str) -> SegmentationResult:
    lines = text.splitlines()
    headers = [
        _Header(index, name)
        for index, line in enumerate(lines)
        if (name := _header_name(line)) is not None
    ]
    if not headers:
        return SegmentationResult(people=[], unassigned=_nonempty_span(lines, 0, len(lines)))

    people: list[PersonSegment] = []
    for position, header in enumerate(headers):
        next_index = headers[position + 1].line_index if position + 1 < len(headers) else len(lines)
        end_index = _trim_trailing_blank_lines(lines, header.line_index + 1, next_index)
        content = "\n".join(lines[header.line_index + 1 : end_index]).strip()
        people.append(
            PersonSegment(
                id=f"P{position + 1:02d}",
                name=header.name,
                line_start=header.line_index + 1,
                line_end=max(header.line_index + 1, end_index),
                content=content,
            )
        )

    unassigned = _nonempty_span(lines, 0, headers[0].line_index)
    return SegmentationResult(people=people, unassigned=unassigned)


def _header_name(line: str) -> str | None:
    for pattern in (_NAME_HEADER, _WEEKLY_HEADER):
        if match := pattern.fullmatch(line):
            return match.group("name").strip()
    return None


def _trim_trailing_blank_lines(lines: list[str], start: int, end: int) -> int:
    while end > start and not lines[end - 1].strip():
        end -= 1
    return end


def _nonempty_span(lines: list[str], start: int, end: int) -> list[SourceSpan]:
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    if start == end:
        return []
    return [SourceSpan(line_start=start + 1, line_end=end, text="\n".join(lines[start:end]))]
