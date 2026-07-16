from dataclasses import dataclass


@dataclass(frozen=True)
class JobStep:
    id: str
    task_id: str
    step_type: str
    entity_id: str
    status: str
    error_code: str | None
