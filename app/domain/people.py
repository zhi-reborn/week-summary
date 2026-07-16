from pydantic import BaseModel, Field


class SourceSpan(BaseModel):
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    text: str


class PersonSegment(BaseModel):
    id: str
    name: str = Field(min_length=1, max_length=80)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    content: str


class SegmentationResult(BaseModel):
    people: list[PersonSegment]
    unassigned: list[SourceSpan]

