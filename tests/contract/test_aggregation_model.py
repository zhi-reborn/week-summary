import pytest

from app.application.aggregation_service import InvalidAggregationResponse, validate_grouping


def test_accepts_grouping_that_uses_every_fact_once() -> None:
    result = validate_grouping({"G1": ["F1", "F2"], "G2": ["F3"]}, {"F1", "F2", "F3"})

    assert result == [["F1", "F2"], ["F3"]]


@pytest.mark.parametrize(
    "groups",
    [
        {"G1": ["F1", "UNKNOWN"], "G2": ["F2"]},
        {"G1": ["F1", "F2"], "G2": ["F2"]},
        {"G1": ["F1"]},
    ],
)
def test_rejects_unknown_duplicate_or_missing_fact_ids(groups: dict[str, list[str]]) -> None:
    with pytest.raises(InvalidAggregationResponse):
        validate_grouping(groups, {"F1", "F2"})
