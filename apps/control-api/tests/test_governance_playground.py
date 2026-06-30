"""API tests for governance playground and drift endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main

client = TestClient(app_main.app)


def test_governance_evaluate_allow(monkeypatch) -> None:
    response = client.post(
        "/governance/evaluate",
        json={
            "team": "platform",
            "owner": "alice",
            "environment": "development",
            "namespace": "ai-dev",
            "action": "invoke_model",
            "model": "llama3.1:8b",
            "provider": "ollama",
            "input_tokens": 1000,
            "output_tokens": 500,
            "cost_per_hour_usd": 0.18,
            "month_to_date_cost_usd": 100.0,
            "forecast_monthly_cost_usd": 400.0,
            "sensitive_data": False,
            "tool_access": False,
            "write_permission": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["final_verdict"] == "allow"
    assert payload["stages"]["cost"]["decision"] == "allow"
    assert payload["stages"]["risk"]["level"] == "low"


def test_governance_evaluate_block_on_budget(monkeypatch) -> None:
    response = client.post(
        "/governance/evaluate",
        json={
            "team": "platform",
            "owner": "alice",
            "environment": "production",
            "namespace": "ai-prod",
            "action": "enable_external_model",
            "model": "gpt-4.1-mini",
            "provider": "openai",
            "input_tokens": 50000,
            "output_tokens": 20000,
            "cost_per_hour_usd": 1.20,
            "month_to_date_cost_usd": 650.0,
            "forecast_monthly_cost_usd": 2600.0,
            "sensitive_data": True,
            "tool_access": True,
            "write_permission": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["final_verdict"] == "block"


def test_governance_evaluate_blocks_forbidden_model() -> None:
    response = client.post(
        "/governance/evaluate",
        json={
            "team": "platform",
            "owner": "alice",
            "environment": "development",
            "namespace": "ai-dev",
            "action": "invoke_model",
            "model": "unknown-frontier-model",
            "provider": "external",
            "input_tokens": 1000,
            "output_tokens": 500,
            "forecast_monthly_cost_usd": 100.0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["final_verdict"] == "block"
    assert payload["stages"]["registry"]["decision"] == "block"


def test_governance_evaluate_blocks_tenant_quota() -> None:
    response = client.post(
        "/governance/evaluate",
        json={
            "team": "finance",
            "owner": "bob",
            "environment": "development",
            "namespace": "ai-dev",
            "action": "invoke_model",
            "model": "llama3.1:8b",
            "provider": "ollama",
            "input_tokens": 1000,
            "output_tokens": 500,
            "requests_last_minute": 30,
            "sensitive_data": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["final_verdict"] == "block"
    assert payload["stages"]["quota"]["decision"] == "block"


def test_drift_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        app_main,
        "probe_ollama_model_names",
        lambda: (["llama3.1:8b"], True, None),
    )
    monkeypatch.setattr(
        app_main,
        "probe_vllm_model_names",
        lambda: ([], False, "connection refused"),
    )

    response = client.get("/drift")

    assert response.status_code == 200
    payload = response.json()
    assert payload["in_sync"] is False
    assert len(payload["backends"]) == 2


def test_dashboard_includes_playground_copy() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Governance Playground" in response.text
    assert "Inventory Drift" in response.text
