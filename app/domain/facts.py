from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class FactKind(StrEnum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    RESULT = "result"
    RISK = "risk"
    HELP_NEEDED = "help_needed"
    NEXT_PLAN = "next_plan"
    MILESTONE = "milestone"


class SourceRef(BaseModel):
    person_id: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> "SourceRef":
        if self.line_end < self.line_start:
            raise ValueError("source line_end must be greater than or equal to line_start")
        return self


class Metric(BaseModel):
    label: str
    value: str
    unit: str | None = None


class Fact(BaseModel):
    id: str
    kind: FactKind
    topic: str
    text: str
    metrics: list[Metric] = Field(default_factory=list)
    sources: list[SourceRef]
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def require_source(self) -> "Fact":
        if not self.sources:
            raise ValueError("fact must have at least one source")
        return self


class PersonExtraction(BaseModel):
    person_id: str
    person_name: str
    facts: list[Fact]
