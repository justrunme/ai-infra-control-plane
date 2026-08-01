"""Approve/reject endpoints require authenticated approvers when OIDC is on."""

from __future__ import annotations

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import main as app_main
from app.jwt_verify import get_jwks_client

client = TestClient(app_main.app)


def _rsa_keypair() -> tuple[bytes, bytes]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def _enable_oidc(monkeypatch: pytest.MonkeyPatch, public_pem: bytes) -> None:
    get_jwks_client.cache_clear()

    class FakeSigningKey:
        def __init__(self, key: bytes) -> None:
            self.key = key

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, _: str) -> FakeSigningKey:
            return FakeSigningKey(public_pem)

    monkeypatch.setenv("OIDC_JWT_VERIFY", "true")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://idp.example.com/jwks")
    monkeypatch.setenv("OIDC_APPROVER_GROUPS", "ai-approvers,secops")
    monkeypatch.setattr(
        "app.jwt_verify.get_jwks_client",
        lambda _url: FakeJwksClient(),
    )


def _pending_approval_id() -> str:
    response = client.post(
        "/governance/evaluate",
        json={
            "team": "platform",
            "owner": "alice",
            "environment": "production",
            "namespace": "ai-prod",
            "action": "invoke_model",
            "model": "llama3.1:8b",
            "provider": "ollama",
            "tool_access": True,
            "write_permission": True,
            "forecast_monthly_cost_usd": 300.0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["final_verdict"] == "approval_required"
    return body["approval_id"]


def test_approve_requires_token_when_oidc_enabled(monkeypatch) -> None:
    private_pem, public_pem = _rsa_keypair()
    _enable_oidc(monkeypatch, public_pem)
    approval_id = _pending_approval_id()

    response = client.post(
        f"/approvals/{approval_id}/approve",
        json={"reviewer": "secops", "comment": "spoof"},
    )
    assert response.status_code == 401


def test_approve_rejects_invalid_token(monkeypatch) -> None:
    private_pem, public_pem = _rsa_keypair()
    _enable_oidc(monkeypatch, public_pem)
    approval_id = _pending_approval_id()

    response = client.post(
        f"/approvals/{approval_id}/approve",
        headers={"Authorization": "Bearer not-a-jwt"},
        json={"reviewer": "secops"},
    )
    assert response.status_code == 401


def test_approve_rejects_valid_token_without_approver_role(monkeypatch) -> None:
    private_pem, public_pem = _rsa_keypair()
    _enable_oidc(monkeypatch, public_pem)
    approval_id = _pending_approval_id()
    token = jwt.encode(
        {
            "sub": "user-1",
            "preferred_username": "alice",
            "groups": ["employees"],
        },
        private_pem,
        algorithm="RS256",
    )

    response = client.post(
        f"/approvals/{approval_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
        json={"reviewer": "secops"},
    )
    assert response.status_code == 403


def test_approve_uses_jwt_subject_not_body_reviewer(monkeypatch) -> None:
    private_pem, public_pem = _rsa_keypair()
    _enable_oidc(monkeypatch, public_pem)
    approval_id = _pending_approval_id()
    token = jwt.encode(
        {
            "sub": "approver-42",
            "preferred_username": "secops-bot",
            "groups": ["ai-approvers"],
        },
        private_pem,
        algorithm="RS256",
    )

    response = client.post(
        f"/approvals/{approval_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
        json={"reviewer": "spoofed-secops", "comment": "ok"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["reviewer"] == "secops-bot"


def test_demo_mode_still_accepts_body_reviewer(monkeypatch) -> None:
    monkeypatch.delenv("OIDC_JWT_VERIFY", raising=False)
    approval_id = _pending_approval_id()
    response = client.post(
        f"/approvals/{approval_id}/approve",
        json={"reviewer": "secops", "comment": "demo"},
    )
    assert response.status_code == 200
    assert response.json()["reviewer"] == "secops"
