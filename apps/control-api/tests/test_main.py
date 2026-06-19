import httpx
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "checked_at" in response.json()


def test_models() -> None:
    response = client.get("/models")

    assert response.status_code == 200
    assert response.json()[0]["healthy"] is True


def test_capacity() -> None:
    response = client.get("/capacity")

    assert response.status_code == 200
    assert response.json() == {
        "models": 1,
        "healthy_models": 1,
        "total_capacity_tokens_per_second": 320,
    }


def test_cost() -> None:
    response = client.get("/cost")

    assert response.status_code == 200
    assert response.json() == {
        "currency": "USD",
        "estimated_hourly_cost": 0.18,
        "estimated_daily_cost": 4.32,
        "estimated_monthly_cost": 129.6,
    }


def test_metrics() -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "ai_control_plane_models_total 1" in response.text
    assert "ai_control_plane_models_healthy 1" in response.text
    assert "ai_control_plane_capacity_tokens_per_second 320" in response.text


def test_summary() -> None:
    response = client.get("/summary")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["healthy_models"] == 1


def test_ollama_health(monkeypatch) -> None:
    def fake_get(url: str, timeout: float) -> httpx.Response:
        assert url == "http://ollama.local:11434/api/tags"
        assert timeout == 2.0
        return httpx.Response(
            200,
            json={"models": []},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.local:11434")
    monkeypatch.setattr("app.main.httpx.get", fake_get)

    response = client.get("/backends/ollama/health")

    assert response.status_code == 200
    assert response.json()["backend"] == "ollama"
    assert response.json()["base_url"] == "http://ollama.local:11434"
    assert response.json()["healthy"] is True
    assert response.json()["status"] == "up"


def test_ollama_models(monkeypatch) -> None:
    def fake_get(url: str, timeout: float) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "llama3.1:8b"},
                    {"name": "mistral:7b"},
                    {"digest": "missing-name"},
                ]
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr("app.main.httpx.get", fake_get)

    response = client.get("/backends/ollama/models")

    assert response.status_code == 200
    assert response.json()["healthy"] is True
    assert response.json()["models"] == [
        {"name": "llama3.1:8b"},
        {"name": "mistral:7b"},
    ]


def test_ollama_latency(monkeypatch) -> None:
    def fake_get(url: str, timeout: float) -> httpx.Response:
        return httpx.Response(
            200,
            json={"models": []},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr("app.main.httpx.get", fake_get)

    response = client.get("/backends/ollama/latency")

    assert response.status_code == 200
    assert response.json()["healthy"] is True
    assert response.json()["measured_endpoint"] == "/api/tags"
    assert isinstance(response.json()["latency_ms"], int)


def test_ollama_health_reports_down_on_error(monkeypatch) -> None:
    def fake_get(url: str, timeout: float) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("app.main.httpx.get", fake_get)

    response = client.get("/backends/ollama/health")

    assert response.status_code == 200
    assert response.json()["healthy"] is False
    assert response.json()["status"] == "down"
    assert "connection refused" in response.json()["error"]
