"""Unified error envelope shape."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main
from app.decision_store import StoreUnavailableError

client = TestClient(app_main.app)


def test_http_error_includes_unified_envelope(monkeypatch) -> None:
    def _boom(**_kwargs):
        raise StoreUnavailableError("authoritative store unavailable")

    monkeypatch.setattr("app.routers.governance.persist_evaluation", _boom)
    response = client.post(
        "/governance/evaluate",
        json={
            "team": "platform",
            "environment": "development",
            "model": "llama3.1:8b",
            "estimated_cost_usd": 0.01,
        },
        headers={"x-request-id": "req-envelope-1"},
    )
    assert response.status_code == 503
    payload = response.json()
    assert payload["error"]["code"]
    assert payload["error"]["message"]
    assert payload["error"]["request_id"] == "req-envelope-1"
    assert payload["error"]["retryable"] is True
    assert payload["detail"]["error"] == "authoritative store unavailable"


def test_metrics_include_db_gauges() -> None:
    body = client.get("/metrics").text
    assert "ai_control_db_pool_size" in body
    assert "ai_control_db_operations_total" in body
