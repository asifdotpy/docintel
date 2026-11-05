from fastapi.testclient import TestClient

from docintel.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    api_response = client.get("/api/health")
    assert api_response.status_code == 200
    assert api_response.json() == {"status": "ok"}
