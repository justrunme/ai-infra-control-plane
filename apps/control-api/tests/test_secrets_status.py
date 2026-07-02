"""API tests for secrets status reporting."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main

client = TestClient(app_main.app)


def test_secrets_status_lists_catalog(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GATEWAY_API_KEYS", raising=False)

    response = client.get("/secrets/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured_count"] >= 0
    assert len(payload["items"]) >= 4
    names = {item["name"] for item in payload["items"]}
    assert "gateway_api_keys" in names
    assert "openai_api_key" in names


def test_secrets_status_redacts_configured_value(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-demo-12345678")

    response = client.get("/secrets/status")
    payload = response.json()
    openai = next(item for item in payload["items"] if item["name"] == "openai_api_key")

    assert openai["status"] == "configured"
    assert openai["fingerprint"] == "********5678"
    assert "sk-demo" not in response.text


def test_metrics_include_secret_gauges(monkeypatch) -> None:
    monkeypatch.setenv("GATEWAY_API_KEYS", "demo-key")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "ai_control_secret_configured" in response.text
