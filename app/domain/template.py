from enum import StrEnum

from pydantic import BaseModel, Field


class RecognitionMethod(StrEnum):
    PLACEHOLDER = "placeholder"
    HEADING_STYLE = "heading_style"
    HEADING_TEXT = "heading_text"
    TABLE_LABEL = "table_label"


class TemplateLocator(BaseModel):
    part: str
    paragraph_index: int
    token: str | None = None


class TemplateSection(BaseModel):
    id: str
    name: str
    method: RecognitionMethod
    confidence: float = Field(ge=0, le=1)
    required: bool = True
    locator: TemplateLocator
    instruction: str = ""
    max_chars: int = Field(default=1200, ge=50, le=10000)

