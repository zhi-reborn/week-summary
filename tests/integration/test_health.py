from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import Settings
from app.main import create_app
from tests.conftest import migrate_database


def test_health_only_reports_process_liveness() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "alive", "version": "0.1.0"}


def test_readiness_checks_database_directory_and_migration(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    migrate_database(settings.database_url)
    client = TestClient(create_app(settings))

    response = client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "database": "ok",
            "data_directory": "ok",
            "migration": "0006",
        },
    }


def test_readiness_rejects_outdated_database(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    migrate_database(settings.database_url)
    application = create_app(settings)
    with application.state.session_factory() as session:
        session.execute(text("UPDATE alembic_version SET version_num = '0005'"))
        session.commit()

    response = TestClient(application).get("/api/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["migration"] == "outdated"
