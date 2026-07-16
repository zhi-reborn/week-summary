from typing import Literal

from pydantic import BaseModel

from app.domain.facts import FactKind


class FactGroup(BaseModel):
    id: str
    kind: FactKind
    topic: str
    fact_ids: list[str]


class Conflict(BaseModel):
    kind: Literal["metric", "status", "date", "version"]
    topic: str
    label: str
    values: list[str]
    fact_ids: list[str]
    resolved_value: str | None = None


class AggregationResult(BaseModel):
    groups: list[FactGroup]
    conflicts: list[Conflict]
