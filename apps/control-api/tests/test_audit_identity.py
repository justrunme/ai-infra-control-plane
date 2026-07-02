"""Tests for workload identity resolution and governance audit trail."""

from __future__ import annotations

import base64
import json

from fastapi.testclient import TestClient

from app import main as app_main
from app.audit_service import AUDIT_STORE
from app.governance_service import GovernanceEvaluateRequest
from app.identity_service import resolve_workload_identity

client = TestClient(app_main.app)


def _make_jwt(claims: dict) -> str:
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode())
        .decode()
        .rstrip("=")
    )
    payload = (
        base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    )
    return f"{header}.{payload}.signature"


def test_resolve_identity_from_jwt_groups() -> None:
    token = _make_jwt(
        {
            "sub": "user-42",
            "preferred_username": "alice",
            "groups": ["finance", "employees"],
            "environment": "production",
        }
    )
    identity = resolve_workload_identity(
        {"authorization": f"Bearer {token}"},
        GovernanceEvaluateRequest(),
    )

    assert identity.subject == "user-42"
    assert identity.team == "finance"
    assert identity.owner == "alice"
    assert identity.environment == "production"
    assert identity.source == "jwt"


def test_resolve_identity_prefers_headers_without_jwt() -> None:
    identity = resolve_workload_identity(
        {
            "x-ai-subject": "svc-bot",
            "x-ai-team": "search",
            "x-ai-owner": "platform-oncall",
            "x-ai-groups": "search,employees",
        },
        GovernanceEvaluateRequest(team="platform"),
    )

    assert identity.subject == "svc-bot"
    assert identity.team == "search"
    assert identity.groups == ["search", "employees"]
    assert identity.source == "headers"


def test_governance_evaluate_records_audit_event() -> None:
    before = len(AUDIT_STORE.list_events(limit=500))

    response = client.post(
        "/governance/evaluate",
        headers={
            "x-ai-subject": "audit-user",
            "x-ai-team": "finance",
            "x-request-id": "req-123",
        },
        json={
            "team": "finance",
            "owner": "bob",
            "environment": "development",
            "namespace": "ai-dev",
            "model": "llama3.1:8b",
            "provider": "ollama",
            "requests_last_minute": 30,
            "sensitive_data": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["final_verdict"] == "block"

    events = AUDIT_STORE.list_events(limit=10, team="finance")
    assert len(events) >= before + 1
    latest = events[0]
    assert latest.subject == "audit-user"
    assert latest.final_verdict == "block"
    assert latest.blocking_stage == "quota"
    assert latest.request_id == "req-123"


def test_audit_events_endpoint_filters_by_verdict() -> None:
    client.post(
        "/governance/evaluate",
        json={
            "team": "platform",
            "owner": "alice",
            "model": "llama3.1:8b",
            "provider": "ollama",
        },
    )

    response = client.get("/audit/events", params={"verdict": "allow", "limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert all(event["final_verdict"] == "allow" for event in payload)


def test_audit_status_endpoint_reports_sinks() -> None:
    response = client.get("/audit/status")

    assert response.status_code == 200
    payload = response.json()
    assert "sinks" in payload
    assert "jsonl_enabled" in payload
    assert "loki_enabled" in payload


def test_metrics_include_governance_decisions() -> None:
    client.post(
        "/governance/evaluate",
        json={
            "team": "platform",
            "owner": "alice",
            "environment": "development",
            "model": "llama3.1:8b",
            "provider": "ollama",
        },
    )

    metrics = client.get("/metrics").text
    assert "ai_control_governance_decisions_total" in metrics
