"""Fail-closed 503 when the authoritative decision store is unavailable."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main
from app.decision_store import StoreUnavailableError
from app.metrics_util import reset_governance_latency_metrics

client = TestClient(app_main.app)


def test_evaluate_returns_503_when_store_unavailable(monkeypatch) -> None:
    reset_governance_latency_metrics()

    def _boom(*_args, **_kwargs):
        raise StoreUnavailableError("authoritative store unavailable")

    monkeypatch.setattr(
        "app.routers.governance.persist_evaluation",
        _boom,
    )

    response = client.post(
        "/governance/evaluate",
        json={
            "team": "platform",
            "environment": "development",
            "model": "llama3.1:8b",
            "estimated_cost_usd": 0.01,
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "authoritative store unavailable"

    metrics = client.get("/metrics").text
    assert "ai_control_governance_evaluate_errors_total" in metrics
    assert 'reason="store_unavailable"' in metrics


def test_list_approvals_returns_503_when_store_unavailable(monkeypatch) -> None:
    def _boom():
        raise StoreUnavailableError("authoritative store unavailable")

    monkeypatch.setattr(
        "app.routers.approvals.get_decision_store",
        _boom,
    )
    response = client.get("/approvals")
    assert response.status_code == 503
