from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import GenerationMode, TaskStatus


@dataclass(frozen=True)
class Task:
    id: str
    name: str
    mode: GenerationMode
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
