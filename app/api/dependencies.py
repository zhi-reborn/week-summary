from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
