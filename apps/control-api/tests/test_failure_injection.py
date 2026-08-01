"""Failure-injection matrix for non-authoritative vs authoritative deps."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main
from app.decision_store import StoreUnavailableError
from app.prometheus_service import PrometheusSignals

client = TestClient(app_main.app)

_EVALUATE_BODY = {
    "team": "platform",
    "environment": "development",
    "model": "llama3.1:8b",
    "estimated_cost_usd": 0.01,
}


def test_redis_unavailable_evaluate_still_ok(monkeypatch) -> None:
    monkeypatch.setenv("QUOTA_REDIS_URL", "redis://127.0.0.1:1/0")
    response = client.post("/governance/evaluate", json=_EVALUATE_BODY)
    assert response.status_code == 200


def test_prometheus_unavailable_evaluate_still_ok(monkeypatch) -> None:
    monkeypatch.setenv("PROMETHEUS_GOVERNANCE_ENABLED", "true")
    monkeypatch.setenv("PROMETHEUS_URL", "http://127.0.0.1:1")
    monkeypatch.setattr(
        "app.governance_inputs.fetch_prometheus_signals",
        lambda **_: PrometheusSignals(
            enabled=True,
            errors=["prometheus: connection refused"],
        ),
    )
    response = client.post("/governance/evaluate", json=_EVALUATE_BODY)
    assert response.status_code == 200


def test_backend_probe_failure_keeps_api_up(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routers.backends.fetch_ollama_tags",
        lambda: ({}, 0.0, "connection refused"),
    )
    health = client.get("/health")
    assert health.status_code == 200
    backend = client.get("/backends/ollama/health")
    assert backend.status_code == 200
    assert backend.json()["healthy"] is False


def test_decision_store_unavailable_evaluate_503(monkeypatch) -> None:
    def _boom(**_kwargs):
        raise StoreUnavailableError("authoritative store unavailable")

    monkeypatch.setattr("app.routers.governance.persist_evaluation", _boom)
    response = client.post("/governance/evaluate", json=_EVALUATE_BODY)
    assert response.status_code == 503
