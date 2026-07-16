from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_version_and_ready_status() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "version": "0.1.0"}
