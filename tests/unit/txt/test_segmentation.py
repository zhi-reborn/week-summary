from pathlib import Path

from app.infrastructure.txt.segmentation import segment_people


def test_segments_name_headers_and_tracks_lines() -> None:
    text = "姓名：张三\n完成A\n计划B\n\n李四周报\n完成C"

    result = segment_people(text)

    assert [(item.name, item.line_start, item.line_end) for item in result.people] == [
        ("张三", 1, 3),
        ("李四", 5, 6),
    ]
    assert result.unassigned == []


def test_does_not_treat_owner_in_body_as_person_header() -> None:
    text = "姓名：张三\n负责人：李四\n完成A"

    result = segment_people(text)

    assert [item.name for item in result.people] == ["张三"]
    assert "负责人：李四" in result.people[0].content


def test_returns_unassigned_block_when_no_header_exists() -> None:
    result = segment_people("完成A\n计划B")

    assert result.people == []
    assert [(item.line_start, item.line_end) for item in result.unassigned] == [(1, 2)]


def test_segments_twenty_people_fixture() -> None:
    text = Path("tests/fixtures/reports/20_people.txt").read_text(encoding="utf-8")

    result = segment_people(text)

    assert len(result.people) == 20
    assert result.unassigned == []

