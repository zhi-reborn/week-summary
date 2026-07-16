import re
import unicodedata
from collections import Counter, defaultdict
from typing import Protocol

from app.domain.aggregation import AggregationResult, Conflict, FactGroup
from app.domain.facts import Fact, FactKind


class InvalidAggregationResponse(ValueError):
    pass


class FactClusterer(Protocol):
    def cluster(self, facts: list[Fact]) -> dict[str, list[str]]: ...


def normalize_topic(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.split()).casefold()


def validate_grouping(groups: dict[str, list[str]], expected_ids: set[str]) -> list[list[str]]:
    fact_ids = [fact_id for group in groups.values() for fact_id in group]
    counts = Counter(fact_ids)
    if not groups or any(not group for group in groups.values()):
        raise InvalidAggregationResponse("aggregation groups cannot be empty")
    if set(fact_ids) != expected_ids or any(count != 1 for count in counts.values()):
        raise InvalidAggregationResponse("every known fact id must appear exactly once")
    return list(groups.values())


class AggregationService:
    def __init__(self, clusterer: FactClusterer | None = None) -> None:
        self._clusterer = clusterer

    def aggregate(self, facts: list[Fact]) -> AggregationResult:
        groups = self._group(facts)
        return AggregationResult(groups=groups, conflicts=self._find_conflicts(facts))

    def _group(self, facts: list[Fact]) -> list[FactGroup]:
        grouped_ids: list[tuple[FactKind, str, list[str]]] = []
        if self._clusterer is None:
            exact: dict[tuple[FactKind, str], list[str]] = defaultdict(list)
            topics: dict[tuple[FactKind, str], str] = {}
            for fact in facts:
                key = (fact.kind, normalize_topic(fact.topic))
                exact[key].append(fact.id)
                topics.setdefault(key, fact.topic)
            grouped_ids = [(key[0], topics[key], ids) for key, ids in exact.items()]
        else:
            by_kind: dict[FactKind, list[Fact]] = defaultdict(list)
            for fact in facts:
                by_kind[fact.kind].append(fact)
            for kind, bucket in by_kind.items():
                fact_by_id = {fact.id: fact for fact in bucket}
                model_groups = validate_grouping(
                    self._clusterer.cluster(bucket), set(fact_by_id)
                )
                merged_groups = [set(ids) for ids in model_groups]
                exact_ids: dict[str, set[str]] = defaultdict(set)
                for fact in bucket:
                    exact_ids[normalize_topic(fact.topic)].add(fact.id)
                for matching_ids in exact_ids.values():
                    indexes = [
                        index
                        for index, group in enumerate(merged_groups)
                        if group & matching_ids
                    ]
                    if len(indexes) <= 1:
                        continue
                    combined = set().union(*(merged_groups[index] for index in indexes))
                    merged_groups = [
                        group for index, group in enumerate(merged_groups) if index not in indexes
                    ]
                    merged_groups.append(combined)
                order = {fact.id: index for index, fact in enumerate(bucket)}
                sorted_groups = [sorted(group, key=order.__getitem__) for group in merged_groups]
                sorted_groups.sort(key=lambda ids: order[ids[0]])
                for ids in sorted_groups:
                    grouped_ids.append((kind, fact_by_id[ids[0]].topic, ids))

        return [
            FactGroup(id=f"G{index:03d}", kind=kind, topic=topic, fact_ids=ids)
            for index, (kind, topic, ids) in enumerate(grouped_ids, start=1)
        ]

    def _find_conflicts(self, facts: list[Fact]) -> list[Conflict]:
        conflicts = self._metric_conflicts(facts)
        by_topic: dict[str, list[Fact]] = defaultdict(list)
        for fact in facts:
            by_topic[normalize_topic(fact.topic)].append(fact)
        for topic_facts in by_topic.values():
            kinds = {fact.kind for fact in topic_facts}
            if {FactKind.COMPLETED, FactKind.IN_PROGRESS} <= kinds:
                conflicts.append(
                    Conflict(
                        kind="status",
                        topic=topic_facts[0].topic,
                        label="工作状态",
                        values=sorted(kind.value for kind in kinds),
                        fact_ids=[fact.id for fact in topic_facts],
                    )
                )
            conflicts.extend(self._token_conflicts(topic_facts, "date", _DATE_PATTERN))
            conflicts.extend(self._token_conflicts(topic_facts, "version", _VERSION_PATTERN))
        return conflicts

    @staticmethod
    def _metric_conflicts(facts: list[Fact]) -> list[Conflict]:
        entries: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
        for fact in facts:
            for metric in fact.metrics:
                key = (normalize_topic(fact.topic), normalize_topic(metric.label))
                entries[key].append((metric.value, fact.id, fact.topic))
        conflicts: list[Conflict] = []
        for (_topic, label), values in entries.items():
            distinct = sorted({value for value, _fact_id, _name in values})
            if len(distinct) > 1:
                conflicts.append(
                    Conflict(
                        kind="metric",
                        topic=values[0][2],
                        label=label,
                        values=distinct,
                        fact_ids=[fact_id for _value, fact_id, _name in values],
                    )
                )
        return conflicts

    @staticmethod
    def _token_conflicts(
        facts: list[Fact], kind: str, pattern: re.Pattern[str]
    ) -> list[Conflict]:
        values_by_fact = [(fact, pattern.findall(fact.text)) for fact in facts]
        distinct = sorted({value for _fact, values in values_by_fact for value in values})
        if len(distinct) <= 1:
            return []
        return [
            Conflict(
                kind=kind,  # type: ignore[arg-type]
                topic=facts[0].topic,
                label="日期" if kind == "date" else "版本",
                values=distinct,
                fact_ids=[fact.id for fact, values in values_by_fact if values],
            )
        ]


_DATE_PATTERN = re.compile(r"\b20\d{2}(?:[-/.年]\d{1,2}){1,2}日?\b")
_VERSION_PATTERN = re.compile(r"\bv\d+(?:\.\d+)+\b", re.IGNORECASE)
