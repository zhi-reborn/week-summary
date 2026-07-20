from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.application.diagnostics_service import DiagnosticsService

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("")
def download_diagnostics(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    content = DiagnosticsService(
        session,
        request.app.state.settings,
        getattr(request.app.state, "model_connectivity", None),
    ).create_package()
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="diagnostics.zip"'},
    )
