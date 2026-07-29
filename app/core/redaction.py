import re
from collections.abc import Mapping
from typing import Any

_REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = {
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
}
_LOG_FIELDS = {
    "request_id",
    "task_id",
    "stage",
    "entity_id",
    "duration_ms",
    "error_code",
    "model_http_status",
    "http_method",
    "http_status",
    "timestamp",
}
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_POSIX_PATH_PATTERN = re.compile(r"(?<![:\w])/(?:[^/\s]+/)*[^/\s]*")
_WINDOWS_PATH_PATTERN = re.compile(r"(?i)\b[A-Z]:\\(?:[^\\\s]+\\)*[^\\\s]*")


def redact_event(value: Any, *, key: str | None = None) -> Any:
    if key is not None and _is_sensitive_key(key):
        return _REDACTED
    if isinstance(value, Mapping):
        return {str(item_key): redact_event(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_event(item) for item in value]
    if isinstance(value, str):
        redacted = _BEARER_PATTERN.sub(_REDACTED, value)
        redacted = _WINDOWS_PATH_PATTERN.sub(_REDACTED, redacted)
        return _POSIX_PATH_PATTERN.sub(_REDACTED, redacted)
    return value


def safe_log_event(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: redact_event(value, key=key)
        for key, value in event.items()
        if key in _LOG_FIELDS and value is not None
    }


def _normalized_key(key: str) -> str:
    return "".join(character for character in key.casefold() if character.isalnum())


def _is_sensitive_key(key: str) -> bool:
    normalized = _normalized_key(key)
    return normalized in _SENSITIVE_KEYS or normalized.endswith(
        ("apikey", "accesstoken", "refreshtoken", "clientsecret", "password")
    )
