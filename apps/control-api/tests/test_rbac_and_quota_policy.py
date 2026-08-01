"""RBAC roles, JWT-only tenant, and quota onUnavailable policy."""

from __future__ import annotations

import jwt
import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.governance_service import GovernanceEvaluateRequest
from app.identity_service import (
    AuthenticationError,
    resolve_request_tenant,
    resolve_workload_identity,
)
from app.quota_state_service import QuotaStateSnapshot, read_quota_state
from app.rbac import principal_has_any_role, roles_from_claims
from app.settings import clear_settings_cache

client = TestClient(app_main.app)


def test_roles_from_claims_maps_groups() -> None:
    claims = {"groups": ["ai-approvers", "ai-auditors"], "roles": ["viewer"]}
    roles = roles_from_claims(claims)
    assert "approver" in roles
    assert "auditor" in roles
    assert "viewer" in roles
    assert principal_has_any_role(claims, ("approver",))


def test_tenant_jwt_only_ignores_header(monkeypatch) -> None:
    monkeypatch.setenv("OIDC_JWT_VERIFY", "true")
    monkeypatch.setenv("TENANT_JWT_ONLY", "true")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://example.invalid/jwks")
    clear_settings_cache()

    token = jwt.encode(
        {"sub": "alice", "tenant": "acme", "team": "finance", "groups": []},
        key="secret",
        algorithm="HS256",
    )

    def _verify(raw: str) -> dict:
        return jwt.decode(raw, options={"verify_signature": False})

    monkeypatch.setattr("app.identity_service.verify_bearer_token", _verify)
    monkeypatch.setattr("app.jwt_verify.verify_bearer_token", _verify)

    headers = {
        "authorization": f"Bearer {token}",
        "x-ai-tenant": "evil-tenant",
    }
    assert resolve_request_tenant(headers) == "acme"

    identity = resolve_workload_identity(
        headers,
        GovernanceEvaluateRequest(team="platform", tenant_id="spoof"),
    )
    assert identity.tenant_id == "acme"
    assert identity.team == "finance"

    monkeypatch.delenv("TENANT_JWT_ONLY", raising=False)
    monkeypatch.delenv("OIDC_JWT_VERIFY", raising=False)
    clear_settings_cache()


def test_tenant_jwt_only_requires_verify(monkeypatch) -> None:
    monkeypatch.setenv("TENANT_JWT_ONLY", "true")
    monkeypatch.delenv("OIDC_JWT_VERIFY", raising=False)
    clear_settings_cache()
    with pytest.raises(AuthenticationError):
        resolve_request_tenant({"x-ai-tenant": "acme"})
    monkeypatch.delenv("TENANT_JWT_ONLY", raising=False)
    clear_settings_cache()


def test_quota_unavailable_returns_marker(monkeypatch) -> None:
    monkeypatch.setenv("QUOTA_REDIS_URL", "redis://127.0.0.1:1/0")
    snap = read_quota_state("platform")
    assert snap is not None
    assert snap.unavailable is True
    assert snap.source == "unavailable"
    monkeypatch.delenv("QUOTA_REDIS_URL", raising=False)


def test_quota_on_unavailable_approval_required(monkeypatch) -> None:
    monkeypatch.setenv("QUOTA_REDIS_URL", "redis://127.0.0.1:1/0")
    monkeypatch.setenv("QUOTA_ON_UNAVAILABLE", "approval_required")
    monkeypatch.setattr(
        "app.governance_inputs.read_quota_state",
        lambda team: QuotaStateSnapshot(
            team=team, source="unavailable", unavailable=True
        ),
    )
    response = client.post(
        "/governance/evaluate",
        json={
            "team": "platform",
            "environment": "development",
            "model": "llama3.1:8b",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["final_verdict"] == "approval_required"
    assert any("quota state unavailable" in r for r in body["reasons"])
    monkeypatch.delenv("QUOTA_REDIS_URL", raising=False)
    monkeypatch.delenv("QUOTA_ON_UNAVAILABLE", raising=False)
