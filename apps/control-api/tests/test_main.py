from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_models() -> None:
    response = client.get("/models")

    assert response.status_code == 200
    assert response.json()[0]["healthy"] is True


def test_summary() -> None:
    response = client.get("/summary")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["healthy_models"] == 1

