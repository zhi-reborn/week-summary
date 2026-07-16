from enum import StrEnum


class TaskStatus(StrEnum):
    DRAFT = "draft"
    PEOPLE_CONFIRMATION = "people_confirmation"
    TEMPLATE_CONFIRMATION = "template_confirmation"
    READY_FOR_ANALYSIS = "ready_for_analysis"
    ANALYZING = "analyzing"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"

