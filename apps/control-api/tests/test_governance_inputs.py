"""Tests for live governance input enrichment."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main
from app.governance_service import GovernanceEvaluateRequest

client = TestClient(app_main.app)


def test_governance_inputs_status_endpoint() -> None:
    response = client.get("/governance/inputs/status")
    assert response.status_code == 200
    payload = response.json()
    assert "quota" in payload
    assert "prometheus" in payload


def test_enrich_governance_request_uses_redis_quota(monkeypatch) -> None:
    from app import governance_inputs as inputs_module
    from app.quota_state_service import QuotaStateSnapshot

    monkeypatch.setattr(
        inputs_module,
        "read_quota_state",
        lambda team: QuotaStateSnapshot(
            team=team,
            requests_last_minute=42,
            tokens_today=9000,
            source="redis",
        ),
    )
    from app.prometheus_service import PrometheusSignals

    monkeypatch.setattr(
        inputs_module,
        "fetch_prometheus_signals",
        lambda **_: PrometheusSignals(enabled=False),
    )

    payload = GovernanceEvaluateRequest(team="finance")
    enriched, snapshot, _signals = inputs_module.enrich_governance_request(payload)
    assert snapshot is not None
    assert enriched.requests_last_minute == 42
    assert enriched.tokens_today == 9000
