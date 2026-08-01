"""Governance evaluate latency histogram exposition."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main
from app.metrics_util import reset_governance_latency_metrics

client = TestClient(app_main.app)


def test_evaluate_emits_latency_histogram() -> None:
    reset_governance_latency_metrics()
    response = client.post(
        "/governance/evaluate",
        json={
            "team": "platform",
            "environment": "development",
            "model": "llama3.1:8b",
            "estimated_cost_usd": 0.01,
        },
    )
    assert response.status_code == 200

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    body = metrics.text
    assert "ai_control_governance_evaluate_latency_ms_bucket" in body
    assert 'le="+Inf"' in body
    assert "ai_control_governance_evaluate_latency_ms_count" in body
    assert "ai_control_governance_evaluate_latency_ms_sum" in body
