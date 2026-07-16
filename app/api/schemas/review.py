from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.application.review_service import ReviewSectionData, ReviewSource


class UpdateSectionRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10000)

    @field_validator("content")
    @classmethod
    def reject_blank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("板块内容不能为空")
        return value


class ReviewSectionResponse(BaseModel):
    section_key: str
    name: str
    revision: int
    content: str
    confirmed: bool
    editor: str
    created_at: datetime | None
    quality_status: str

    @classmethod
    def from_data(cls, data: ReviewSectionData) -> "ReviewSectionResponse":
        return cls(
            section_key=data.section.id,
            name=data.section.name,
            revision=data.review.revision,
            content=data.review.content,
            confirmed=data.review.confirmed,
            editor=data.review.editor,
            created_at=data.review.created_at,
            quality_status=data.generated.status,
        )


class ReviewSourceResponse(BaseModel):
    source_id: str
    fact_id: str
    person_id: str
    person: str
    line_start: int
    line_end: int
    excerpt: str

    @classmethod
    def from_source(cls, source: ReviewSource) -> "ReviewSourceResponse":
        return cls(**source.__dict__)
