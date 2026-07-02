"""API tests for intent engine orchestration."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main

client = TestClient(app_main.app)


def test_intent_resolve_finance_report() -> None:
    response = client.post(
        "/intent/resolve",
        headers={"x-ai-team": "finance"},
        json={
            "message": "Generate quarterly revenue report",
            "team": "finance",
            "environment": "production",
            "namespace": "ai-prod",
            "run_governance": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "finance_report"
    assert payload["plan"]["agent"] == "finance-copilot"
    assert payload["plan"]["model"] == "llama3.1:8b"
    assert "jira-read" in payload["plan"]["tools"]
    assert payload["plan"]["region"] == "eu-central"
    assert payload["cluster"]["name"] == "eu-prod"


def test_intent_resolve_runs_governance_for_platform() -> None:
    response = client.post(
        "/intent/resolve",
        json={
            "message": "Hello, help me summarize this document",
            "team": "platform",
            "environment": "development",
            "namespace": "ai-dev",
            "run_governance": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["governance"] is not None
    assert payload["governance"]["final_verdict"] in {"allow", "approval_required"}


def test_intent_resolve_support_ticket() -> None:
    response = client.post(
        "/intent/resolve",
        headers={"x-ai-team": "support"},
        json={
            "message": "Open a customer support ticket in Jira",
            "team": "support",
            "environment": "development",
            "namespace": "ai-dev",
            "run_governance": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "support_ticket"
    assert payload["plan"]["agent"] == "support-agent"
