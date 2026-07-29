import json

from app.core.logging import close_logging, configure_logging, log_event
from app.core.redaction import redact_event, safe_log_event


def test_recursively_redacts_secrets_headers_and_absolute_paths(tmp_path) -> None:
    secret = "secret-123"
    event = {
        "api_key": secret,
        "headers": {
            "Authorization": f"Bearer {secret}",
            "Cookie": f"session={secret}",
            "X-Api-Key": secret,
        },
        "items": [{"token": secret, "message": f"failed at {tmp_path / 'private.txt'}"}],
    }

    redacted = redact_event(event)
    serialized = json.dumps(redacted)

    assert secret not in serialized
    assert str(tmp_path) not in serialized
    assert serialized.count("[REDACTED]") >= 4


def test_structured_log_event_only_keeps_whitelisted_fields() -> None:
    event = safe_log_event(
        {
            "request_id": "request-1",
            "task_id": "task-1",
            "stage": "model_request",
            "entity_id": "P01",
            "duration_ms": 12,
            "error_code": "MODEL_TIMEOUT",
            "model_http_status": 504,
            "report_text": "private weekly report",
            "response_body": "private model response",
        }
    )

    assert event == {
        "request_id": "request-1",
        "task_id": "task-1",
        "stage": "model_request",
        "entity_id": "P01",
        "duration_ms": 12,
        "error_code": "MODEL_TIMEOUT",
        "model_http_status": 504,
    }


def test_json_log_never_writes_unapproved_sensitive_fields(tmp_path) -> None:
    secret = "log-secret-123"
    configure_logging(tmp_path)
    try:
        log_event(
            {
                "stage": "model_request",
                "error_code": "AUTH_FAILED",
                "api_key": secret,
                "authorization": f"Bearer {secret}",
                "report_text": "private weekly report",
            }
        )
    finally:
        close_logging()

    content = (tmp_path / "app.jsonl").read_text(encoding="utf-8")
    assert secret not in content
    assert "private weekly report" not in content
    assert json.loads(content)["error_code"] == "AUTH_FAILED"
