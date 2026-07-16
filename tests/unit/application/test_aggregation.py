from app.application.aggregation_service import AggregationService
from app.domain.facts import Fact, FactKind, Metric, SourceRef


def _fact(
    fact_id: str,
    kind: FactKind,
    topic: str,
    person_id: str,
    *,
    metric: Metric | None = None,
) -> Fact:
    return Fact(
        id=fact_id,
        kind=kind,
        topic=topic,
        text=topic,
        metrics=[metric] if metric else [],
        sources=[
            SourceRef(
                person_id=person_id,
                line_start=1,
                line_end=1,
                quote=topic,
            )
        ],
        confidence=0.9,
    )


def test_does_not_merge_completed_and_planned_facts() -> None:
    result = AggregationService().aggregate(
        [
            _fact("F1", FactKind.COMPLETED, "统一认证", "P01"),
            _fact("F2", FactKind.NEXT_PLAN, "统一认证", "P02"),
        ]
    )

    assert len(result.groups) == 2


def test_merges_exact_topics_after_unicode_and_space_normalization() -> None:
    result = AggregationService().aggregate(
        [
            _fact("F1", FactKind.COMPLETED, "ＡＰＩ  网关", "P01"),
            _fact("F2", FactKind.COMPLETED, "api 网关", "P02"),
        ]
    )

    assert [group.fact_ids for group in result.groups] == [["F1", "F2"]]


def test_marks_metric_conflict_without_choosing_a_value() -> None:
    result = AggregationService().aggregate(
        [
            _fact(
                "F1",
                FactKind.RESULT,
                "质量提升",
                "P01",
                metric=Metric(label="覆盖率", value="80%"),
            ),
            _fact(
                "F2",
                FactKind.RESULT,
                "质量提升",
                "P02",
                metric=Metric(label="覆盖率", value="85%"),
            ),
        ]
    )

    assert result.conflicts[0].values == ["80%", "85%"]
    assert result.conflicts[0].resolved_value is None


def test_marks_completed_and_in_progress_status_conflict() -> None:
    result = AggregationService().aggregate(
        [
            _fact("F1", FactKind.COMPLETED, "统一认证", "P01"),
            _fact("F2", FactKind.IN_PROGRESS, "统一认证", "P02"),
        ]
    )

    assert result.conflicts[0].kind == "status"
    assert set(result.conflicts[0].values) == {"completed", "in_progress"}


class RecordingClusterer:
    def __init__(self) -> None:
        self.calls: list[list[Fact]] = []

    def cluster(self, facts: list[Fact]) -> dict[str, list[str]]:
        self.calls.append(facts)
        return {f"G{index}": [fact.id] for index, fact in enumerate(facts, start=1)}


def test_model_clusterer_receives_one_fact_kind_per_call() -> None:
    clusterer = RecordingClusterer()
    facts = [
        _fact("F1", FactKind.COMPLETED, "统一认证", "P01"),
        _fact("F2", FactKind.COMPLETED, "登录中心", "P02"),
        _fact("F3", FactKind.RISK, "资源", "P03"),
    ]

    AggregationService(clusterer).aggregate(facts)

    assert all(len({fact.kind for fact in call}) == 1 for call in clusterer.calls)


def test_exact_topic_matches_stay_merged_even_if_model_splits_them() -> None:
    clusterer = RecordingClusterer()
    facts = [
        _fact("F1", FactKind.COMPLETED, "ＡＰＩ 网关", "P01"),
        _fact("F2", FactKind.COMPLETED, "api 网关", "P02"),
    ]

    result = AggregationService(clusterer).aggregate(facts)

    assert [group.fact_ids for group in result.groups] == [["F1", "F2"]]
