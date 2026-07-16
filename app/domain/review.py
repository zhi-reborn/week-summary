from dataclasses import dataclass, replace
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class GeneratedSection(BaseModel):
    section_id: str
    body: str
    fact_ids: list[str]
    source_ids: list[str]
    unused_important_fact_ids: list[str] = Field(default_factory=list)
    review_questions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_unique_references(self) -> "GeneratedSection":
        if len(self.fact_ids) != len(set(self.fact_ids)):
            raise ValueError("fact_ids must be unique")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("source_ids must be unique")
        return self


@dataclass(frozen=True)
class SectionVersion:
    id: str
    task_id: str
    section_id: str
    version: int
    generated: GeneratedSection
    status: str
    instruction: str
    created_at: datetime


@dataclass(frozen=True)
class SectionReview:
    section_key: str
    revision: int
    content: str
    confirmed: bool = False
    editor: str = "local-user"
    created_at: datetime | None = None

    def revise(self, content: str, editor: str) -> "SectionReview":
        return replace(
            self,
            revision=self.revision + 1,
            content=content,
            confirmed=False,
            editor=editor,
            created_at=None,
        )

    def confirm(self, editor: str) -> "SectionReview":
        return replace(
            self,
            revision=self.revision + 1,
            confirmed=True,
            editor=editor,
            created_at=None,
        )
