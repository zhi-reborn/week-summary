from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class QualityLevel(StrEnum):
    FAILED = "failed"
    RISK = "risk"
    CONFIRM = "confirm"
    PASS = "pass"


class QualityFinding(BaseModel):
    code: str
    message: str
    token: str | None = None


class CoverageCell(BaseModel):
    person_id: str
    section_id: str
    state: Literal["referenced", "no_source_content", "unreferenced"]
    fact_ids: list[str] = Field(default_factory=list)
