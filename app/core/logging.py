import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.redaction import safe_log_event

LOGGER_NAME = "weekly_report_assistant"


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "safe_event", {})
        return json.dumps(safe_log_event(event), ensure_ascii=False, separators=(",", ":"))


def configure_logging(log_dir: Path) -> logging.Logger:
    close_logging()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app.jsonl"
    handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(JsonLineFormatter())
    log_path.chmod(0o600)

    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def log_event(event: dict[str, Any], *, level: int = logging.INFO) -> None:
    event = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    logging.getLogger(LOGGER_NAME).log(
        level,
        "structured_event",
        extra={"safe_event": safe_log_event(event)},
    )


def close_logging() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()
