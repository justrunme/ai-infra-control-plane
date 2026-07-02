"""API tests for sovereign AI and response evaluations."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main

client = TestClient(app_main.app)


def test_sovereign_blocks_external_model_in_eu() -> None:
    response = client.post(
        "/governance/evaluate",
        headers={"x-ai-region": "eu-central"},
        json={
            "team": "platform",
            "namespace": "ai-prod",
            "environment": "development",
            "policy_pack": "development",
            "model": "gpt-4.1-mini",
            "provider": "openai",
            "region": "eu-central",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["final_verdict"] == "block"
    assert payload["stages"]["sovereign"]["decision"] == "block"


def test_evaluate_response_records_evaluation() -> None:
    response = client.post(
        "/governance/evaluate-response",
        json={
            "team": "platform",
            "model": "llama3.1:8b",
            "request_id": "eval-test-1",
            "prompt_text": "Hello",
            "response_text": "Hello! How can I help?",
            "latency_ms": 250,
            "cost_usd": 0.001,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "pass"
    assert payload["scores"]["latency_ok"] is True


def test_evaluations_recent_lists_records() -> None:
    client.post(
        "/governance/evaluate-response",
        json={
            "team": "platform",
            "model": "llama3.1:8b",
            "response_text": "Test response for listing.",
            "latency_ms": 100,
        },
    )
    response = client.get("/evaluations/recent", params={"team": "platform", "limit": 5})
    assert response.status_code == 200
    payload = response.json()
    assert payload["evaluation_count"] >= 1
