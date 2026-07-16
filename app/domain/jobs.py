from dataclasses import dataclass


@dataclass(frozen=True)
class JobStep:
    id: str
    task_id: str
    step_type: str
    entity_id: str
    status: str
    error_code: str | None


@dataclass(frozen=True)
class AnalysisJob:
    task_id: str
    status: str
    owner_id: str | None
    error_code: str | None
