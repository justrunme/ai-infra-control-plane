"""API tests for durable decisions and approval lifecycle."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main

client = TestClient(app_main.app)


def _approval_required_payload() -> dict:
    return {
        "team": "platform",
        "owner": "alice",
        "environment": "production",
        "namespace": "ai-prod",
        "action": "invoke_model",
        "model": "llama3.1:8b",
        "provider": "ollama",
        "input_tokens": 1000,
        "output_tokens": 500,
        "cost_per_hour_usd": 0.18,
        "month_to_date_cost_usd": 100.0,
        "forecast_monthly_cost_usd": 300.0,
        "sensitive_data": False,
        "tool_access": True,
        "write_permission": True,
    }


def test_evaluate_persists_decision_and_policy_bundle_ids() -> None:
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
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["final_verdict"] == "allow"
    assert payload["decision_id"]
    assert payload["policy_bundle_id"]
    assert payload["policy_digest"]

    decision = client.get(f"/governance/decisions/{payload['decision_id']}")
    assert decision.status_code == 200
    assert decision.json()["final_verdict"] == "allow"
    assert decision.json()["request_digest"]


def test_approval_lifecycle_approve_and_consume() -> None:
    evaluate = client.post("/governance/evaluate", json=_approval_required_payload())
    assert evaluate.status_code == 200
    payload = evaluate.json()
    assert payload["final_verdict"] == "approval_required"
    assert payload["approval_id"]

    approval_id = payload["approval_id"]
    listed = client.get("/approvals", params={"status": "pending"})
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1

    approved = client.post(
        f"/approvals/{approval_id}/approve",
        json={"reviewer": "secops", "comment": "ok for batch job"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    reused = client.post(
        "/governance/evaluate",
        headers={"x-ai-approval-id": approval_id},
        json=_approval_required_payload(),
    )
    assert reused.status_code == 200
    assert reused.json()["final_verdict"] == "allow"
    assert reused.json()["approval_id"] == approval_id
    assert "durable approval grants allow" in reused.json()["reasons"]

    consumed = client.get(f"/approvals/{approval_id}")
    assert consumed.status_code == 200
    assert consumed.json()["status"] == "consumed"


def test_policy_bundle_status_endpoint() -> None:
    response = client.get("/governance/policy-bundle")
    assert response.status_code == 200
    payload = response.json()
    assert payload["validation_status"] == "ok"
    assert payload["bundle_id"]
    assert payload["content_digest"]
