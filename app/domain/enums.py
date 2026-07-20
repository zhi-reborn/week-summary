from enum import StrEnum


class GenerationMode(StrEnum):
    REVIEW = "review"
    DIRECT = "direct"


class TaskStatus(StrEnum):
    DRAFT = "draft"
    PEOPLE_CONFIRMATION = "people_confirmation"
    TEMPLATE_CONFIRMATION = "template_confirmation"
    READY_FOR_ANALYSIS = "ready_for_analysis"
    ANALYZING = "analyzing"
    REVIEW = "review"
    EXPORTING = "exporting"
    EXPORT_FAILED = "export_failed"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETING = "deleting"
