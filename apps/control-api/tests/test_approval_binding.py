"""Security tests: approvals are request-bound and one-time use."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main
from app.approval_binding import compute_request_digest
from app.governance_service import GovernanceEvaluateRequest

client = TestClient(app_main.app)


def _approval_required_payload(**overrides) -> dict:
    payload = {
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
    payload.update(overrides)
    return payload


def _approve(payload: dict) -> str:
    evaluate = client.post("/governance/evaluate", json=payload)
    assert evaluate.status_code == 200
    body = evaluate.json()
    assert body["final_verdict"] == "approval_required"
    approval_id = body["approval_id"]
    approved = client.post(
        f"/approvals/{approval_id}/approve",
        json={"reviewer": "secops", "comment": "ok"},
    )
    assert approved.status_code == 200
    return approval_id


def test_request_digest_ignores_live_telemetry_only() -> None:
    left = GovernanceEvaluateRequest(**_approval_required_payload())
    right = GovernanceEvaluateRequest(
        **_approval_required_payload(requests_last_minute=99, tokens_today=12345)
    )
    assert compute_request_digest(left) == compute_request_digest(right)


def test_request_digest_includes_cost_fields() -> None:
    left = GovernanceEvaluateRequest(**_approval_required_payload(cost_per_hour_usd=0.18))
    right = GovernanceEvaluateRequest(
        **_approval_required_payload(cost_per_hour_usd=100.0)
    )
    assert compute_request_digest(left) != compute_request_digest(right)


def test_cost_mismatch_cannot_reuse_approval() -> None:
    payload = _approval_required_payload(cost_per_hour_usd=0.18)
    approval_id = _approve(payload)

    mismatched = dict(payload)
    mismatched["cost_per_hour_usd"] = 100.0
    reused = client.post(
        "/governance/evaluate",
        headers={"x-ai-approval-id": approval_id},
        json=mismatched,
    )
    assert reused.status_code == 200
    assert "durable approval grants allow" not in reused.json().get("reasons", [])


def test_mismatched_model_cannot_reuse_approval() -> None:
    payload = _approval_required_payload()
    approval_id = _approve(payload)

    mismatched = dict(payload)
    mismatched["model"] = "qwen2.5:14b"
    reused = client.post(
        "/governance/evaluate",
        headers={"x-ai-approval-id": approval_id},
        json=mismatched,
    )
    assert reused.status_code == 200
    # Must not short-circuit to allow via stolen approval id.
    assert reused.json()["final_verdict"] != "allow" or "durable approval" not in (
        " ".join(reused.json().get("reasons") or [])
    )
    assert "durable approval grants allow" not in reused.json().get("reasons", [])


def test_matching_approval_is_one_time_use() -> None:
    payload = _approval_required_payload()
    approval_id = _approve(payload)

    first = client.post(
        "/governance/evaluate",
        headers={"x-ai-approval-id": approval_id},
        json=payload,
    )
    assert first.status_code == 200
    assert first.json()["final_verdict"] == "allow"
    assert "durable approval grants allow" in first.json()["reasons"]

    second = client.post(
        "/governance/evaluate",
        headers={"x-ai-approval-id": approval_id},
        json=payload,
    )
    assert second.status_code == 200
    assert "durable approval grants allow" not in second.json().get("reasons", [])

    status = client.get(f"/approvals/{approval_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "consumed"
    assert status.json()["used_at"]


def test_environment_mismatch_rejected() -> None:
    payload = _approval_required_payload()
    approval_id = _approve(payload)
    bad = dict(payload)
    bad["environment"] = "staging"
    reused = client.post(
        "/governance/evaluate",
        headers={"x-ai-approval-id": approval_id},
        json=bad,
    )
    assert reused.status_code == 200
    assert "durable approval grants allow" not in reused.json().get("reasons", [])
