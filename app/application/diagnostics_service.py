import json
import platform
from dataclasses import asdict
from io import BytesIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application.cleanup_service import CleanupService, DataUsage
from app.application.settings_service import SettingsService
from app.config import Settings
from app.core.redaction import redact_event, safe_log_event
from app.infrastructure.files.task_storage import TaskStorage

_VERSION = "0.1.0"


class DiagnosticsService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        model_connectivity: dict[str, Any] | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._model_connectivity = model_connectivity or {"status": "not_checked"}

    def create_package(self) -> bytes:
        payload = redact_event(
            {
                "version": _VERSION,
                "platform": {
                    "system": platform.system(),
                    "release": platform.release(),
                    "machine": platform.machine(),
                    "python": platform.python_version(),
                },
                "configuration": self._configuration(),
                "database": {"migration_version": self._migration_version()},
                "disk_usage": self._disk_usage(),
                "model_connectivity": self._model_connectivity,
                "recent_errors": self._recent_errors(),
            }
        )
        output = BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            archive.writestr(
                "diagnostics.json",
                json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            )
        return output.getvalue()

    def _configuration(self) -> dict[str, Any]:
        configuration: dict[str, Any] = {
            "host": self._settings.host,
            "port": self._settings.port,
            "max_txt_bytes": self._settings.max_txt_bytes,
            "max_docx_bytes": self._settings.max_docx_bytes,
            "retention_enabled": self._settings.retention_days is not None,
            "model_configured": False,
        }
        try:
            model = SettingsService(self._settings.data_dir).get()
        except FileNotFoundError:
            return configuration
        configuration.update(
            {
                "model_configured": True,
                "model": model.model,
                "model_auth_configured": model.has_api_key,
            }
        )
        return configuration

    def _migration_version(self) -> str | None:
        try:
            value = self._session.scalar(text("SELECT version_num FROM alembic_version"))
            return str(value) if value is not None else None
        except Exception:
            self._session.rollback()
            return None

    def _usage(self) -> DataUsage:
        return CleanupService(
            self._session,
            TaskStorage(self._settings.data_dir),
            self._settings.data_dir,
            self._settings.retention_days,
        ).usage()

    def _disk_usage(self) -> dict[str, int]:
        usage = self._usage()
        return {**asdict(usage), "total_bytes": usage.total_bytes}

    def _recent_errors(self) -> list[dict[str, Any]]:
        log_path = self._settings.log_dir / "app.jsonl"
        if not log_path.is_file():
            return []
        errors: list[dict[str, Any]] = []
        for line in reversed(log_path.read_text(encoding="utf-8", errors="replace").splitlines()):
            try:
                event = json.loads(line)
            except (TypeError, ValueError):
                continue
            if not isinstance(event, dict):
                continue
            safe_event = safe_log_event(event)
            status = safe_event.get("http_status", 0)
            if safe_event.get("error_code") or (
                isinstance(status, int) and status >= 500
            ):
                errors.append(safe_event)
            if len(errors) == 20:
                break
        return errors
