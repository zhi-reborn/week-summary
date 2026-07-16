import json
from pathlib import Path

from app.application.quality_service import QualityService
from app.domain.facts import Fact, FactKind, Metric, SourceRef
from app.domain.quality import QualityFinding, QualityLevel


def _source(text: str) -> SourceRef:
    return SourceRef(person_id="P01", line_start=1, line_end=1, quote=text)


def _fact(fact_id: str, person_id: str, kind: FactKind) -> Fact:
    return Fact(
        id=fact_id,
        kind=kind,
        topic="主题",
        text="内容",
        sources=[SourceRef(person_id=person_id, line_start=1, line_end=1, quote="内容")],
        confidence=0.9,
    )


def test_rejects_unknown_person_name() -> None:
    findings = QualityService().check_text("王五完成上线", {"张三", "李四"}, [])

    assert findings[0].code == "UNKNOWN_PERSON"


def test_flags_number_not_present_in_sources() -> None:
    findings = QualityService().check_text(
        "覆盖率达到 95%", {"张三"}, [_source("覆盖率达到 90%")]
    )

    assert findings[0].code == "UNSOURCED_NUMBER"
    assert findings[0].token == "95%"


def test_accepts_number_from_structured_metric() -> None:
    findings = QualityService().check_text(
        "覆盖率达到 90%",
        {"张三"},
        [],
        [Metric(label="覆盖率", value="90", unit="%")],
    )

    assert findings == []


def test_builds_referenced_unreferenced_and_empty_coverage_cells() -> None:
    facts = [
        _fact("F1", "P01", FactKind.COMPLETED),
        _fact("F2", "P02", FactKind.COMPLETED),
    ]

    cells = QualityService().build_coverage(
        person_ids=["P01", "P02", "P03"],
        section_ids=["progress"],
        facts=facts,
        section_fact_ids={"progress": {"F1"}},
        section_kinds={"progress": {FactKind.COMPLETED}},
    )

    assert [cell.state for cell in cells] == [
        "referenced",
        "unreferenced",
        "no_source_content",
    ]


def test_quality_level_is_determined_by_rule_table() -> None:
    service = QualityService()

    assert service.level([], required_section_empty=True) == QualityLevel.FAILED
    assert service.level([QualityFinding(code="UNSOURCED_NUMBER", message="x")]) == QualityLevel.RISK
    assert service.level([QualityFinding(code="LOW_CONFIDENCE", message="x")]) == QualityLevel.CONFIRM
    assert service.level([]) == QualityLevel.PASS


def test_quality_fixture_matrix() -> None:
    cases = json.loads(
        Path("tests/fixtures/reports/quality_cases.json").read_text(encoding="utf-8")
    )
    service = QualityService()
    for case in cases:
        findings = service.check_text(
            case["text"],
            set(case["known_people"]),
            [_source(text) for text in case["sources"]],
        )
        assert [finding.code for finding in findings] == case["expected_codes"], case["name"]
