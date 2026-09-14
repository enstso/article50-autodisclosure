from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "article50-autodisclosure-api",
        "model_mode": "LIVE",
        "model_provider": "Amazon Bedrock",
    }


def test_health_reports_mock_mode_from_configuration() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(use_mock_model=True)
    try:
        response = client.get("/api/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["model_mode"] == "DEMO"
    assert response.json()["model_provider"] == "Mock model"
