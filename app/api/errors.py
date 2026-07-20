from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.logging import log_event


@dataclass
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    details: Any = None


async def api_error_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, ApiError):
        raise error
    log_event(
        {
            "request_id": getattr(request.state, "request_id", None),
            "task_id": getattr(request.state, "task_id", None),
            "stage": "api_error",
            "error_code": error.code,
            "http_status": error.status_code,
        }
    )
    return JSONResponse(
        status_code=error.status_code,
        content={"code": error.code, "message": error.message, "details": error.details},
    )
