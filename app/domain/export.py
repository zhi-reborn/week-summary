from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExportRecord:
    task_id: str
    stored_name: str
    download_name: str
    created_at: datetime
