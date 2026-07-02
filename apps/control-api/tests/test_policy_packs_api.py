"""API tests for policy pack governance stage."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main

client = TestClient(app_main.app)


def test_governance_evaluate_resolves_development_pack_by_default() -> None:
    response = client.post(
        "/governance/evaluate",
        json={
            "team": "platform",
            "owner": "alice",
            "environment": "development",
            "namespace": "ai-dev",
            "model": "llama3.1:8b",
            "provider": "ollama",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy_pack"] == "development"
    assert payload["stages"]["policy_pack"]["pack"] == "development"


def test_production_pack_blocks_unregistered_model() -> None:
    response = client.post(
        "/governance/evaluate",
        headers={"x-ai-policy-pack": "production"},
        json={
            "team": "platform",
            "owner": "alice",
            "environment": "production",
            "namespace": "ai-prod",
            "model": "experimental-model",
            "provider": "ollama",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy_pack"] == "production"
    assert payload["final_verdict"] == "block"
    assert payload["stages"]["policy_pack"]["decision"] == "block"
