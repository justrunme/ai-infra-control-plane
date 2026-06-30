import httpx
from fastapi.testclient import TestClient

from app import main as app_main

app = app_main.app
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


def test_topology() -> None:
    response = client.get("/topology")

    assert response.status_code == 200
    payload = response.json()
    assert payload["graph_version"] == "v1"
    assert "updated_at" in payload

    node_ids = {node["id"] for node in payload["nodes"]}
    assert {
        "control-api",
        "ollama",
        "vllm",
        "openwebui",
        "prometheus",
        "grafana",
        "loki",
        "argocd",
        "k3s",
        "helm-chart",
        "forecasting",
        "opa",
    }.issubset(node_ids)

    edges = {
        (edge["source"], edge["target"], edge["relationship"])
        for edge in payload["edges"]
    }
    assert ("control-api", "ollama", "probes") in edges
    assert ("prometheus", "control-api", "scrapes") in edges
    assert ("grafana", "prometheus", "visualizes") in edges
    assert ("argocd", "helm-chart", "deploys") in edges

    control_api = next(node for node in payload["nodes"] if node["id"] == "control-api")
    signal_names = {signal["name"] for signal in control_api["signals"]}
    assert {"models", "capacity", "estimated_cost"}.issubset(signal_names)


def test_metrics(monkeypatch) -> None:
    def fake_fetch_ollama_tags() -> tuple[dict, int, str | None]:
        return {"models": [{"name": "llama3.1:8b"}]}, 17, None

    monkeypatch.setattr(app_main, "fetch_ollama_tags", fake_fetch_ollama_tags)

    client.get("/health")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert 'ai_control_backend_up{backend="ollama"} 1' in response.text
    assert 'ai_control_backend_latency_ms{backend="ollama"} 17' in response.text
    assert (
        'ai_control_model_available{backend="mock",model="llama-3.1-8b-instruct"} 1'
        in response.text
    )
    assert (
        'ai_control_model_available{backend="ollama",model="llama3.1:8b"} 1'
        in response.text
    )
    assert (
        'ai_control_capacity_available{unit="tokens_per_second"} 320'
        in response.text
    )
    assert 'ai_control_http_requests_total{method="GET",path="/health",status="200"}' in (
        response.text
    )


def test_metrics_reports_backend_down(monkeypatch) -> None:
    def fake_fetch_ollama_tags() -> tuple[dict, int, str | None]:
        return {}, 2000, "connection refused"

    monkeypatch.setattr(app_main, "fetch_ollama_tags", fake_fetch_ollama_tags)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert 'ai_control_backend_up{backend="ollama"} 0' in response.text
    assert 'ai_control_backend_latency_ms{backend="ollama"} 2000' in response.text


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


def test_default_inventory_loads_from_bundled_file() -> None:
    models = app_main.get_model_inventory()

    assert app_main.DEFAULT_MODEL_INVENTORY_PATH.exists()
    assert [model.name for model in models] == ["llama-3.1-8b-instruct"]


def test_inventory_loads_from_custom_path(tmp_path, monkeypatch) -> None:
    inventory_file = tmp_path / "inventory.json"
    inventory_file.write_text(
        '[{"name": "qwen2.5-14b", "backend": "vllm", "healthy": true, '
        '"latency_ms": 55, "capacity_tokens_per_second": 540, '
        '"estimated_hourly_cost_usd": 0.42}]'
    )
    monkeypatch.setenv("MODEL_INVENTORY_PATH", str(inventory_file))

    response = client.get("/models")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "qwen2.5-14b"
    assert payload[0]["backend"] == "vllm"


def test_inventory_falls_back_on_malformed_file(tmp_path, monkeypatch) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{not valid json")
    monkeypatch.setenv("MODEL_INVENTORY_PATH", str(broken))

    models = app_main.get_model_inventory()

    assert [model.name for model in models] == ["llama-3.1-8b-instruct"]


def test_inventory_missing_file_uses_builtin(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MODEL_INVENTORY_PATH", str(tmp_path / "absent.json"))

    models = app_main.get_model_inventory()

    assert models == app_main.BUILTIN_MODEL_INVENTORY
