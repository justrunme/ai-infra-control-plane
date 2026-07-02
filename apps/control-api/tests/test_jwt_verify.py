"""Tests for OIDC JWT signature verification."""

from __future__ import annotations

import base64
import json

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.governance_service import GovernanceEvaluateRequest
from app.identity_service import resolve_workload_identity
from app.jwt_verify import decode_unsigned_payload, verify_bearer_token


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


def _unsigned_jwt(claims: dict) -> str:
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode())
        .decode()
        .rstrip("=")
    )
    payload = (
        base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    )
    return f"{header}.{payload}.signature"


def test_decode_unsigned_payload_reads_claims() -> None:
    token = _unsigned_jwt({"sub": "user-1", "groups": ["finance"]})
    claims = decode_unsigned_payload(token)
    assert claims["sub"] == "user-1"
    assert claims["groups"] == ["finance"]


def test_verify_bearer_token_with_jwks(monkeypatch) -> None:
    private_pem, public_pem = _rsa_keypair()
    token = jwt.encode(
        {"sub": "user-99", "groups": ["platform"], "preferred_username": "carol"},
        private_pem,
        algorithm="RS256",
    )

    class FakeSigningKey:
        def __init__(self, key: bytes) -> None:
            self.key = key

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, _: str) -> FakeSigningKey:
            return FakeSigningKey(public_pem)

    monkeypatch.setenv("OIDC_JWT_VERIFY", "true")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://idp.example.com/jwks")
    monkeypatch.setattr(
        "app.jwt_verify.get_jwks_client",
        lambda _url: FakeJwksClient(),
    )

    claims = verify_bearer_token(token)
    assert claims["sub"] == "user-99"
    assert claims["groups"] == ["platform"]


def test_verify_bearer_token_rejects_tampered_token(monkeypatch) -> None:
    private_pem, public_pem = _rsa_keypair()
    token = jwt.encode({"sub": "user-99"}, private_pem, algorithm="RS256")
    tampered = f"{token}tampered"

    class FakeSigningKey:
        def __init__(self, key: bytes) -> None:
            self.key = key

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, _: str) -> FakeSigningKey:
            return FakeSigningKey(public_pem)

    monkeypatch.setenv("OIDC_JWT_VERIFY", "true")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://idp.example.com/jwks")
    monkeypatch.setattr(
        "app.jwt_verify.get_jwks_client",
        lambda _url: FakeJwksClient(),
    )

    with pytest.raises(jwt.PyJWTError):
        verify_bearer_token(tampered)


def test_identity_rejects_invalid_jwt_when_verify_enabled(monkeypatch) -> None:
    monkeypatch.setenv("OIDC_JWT_VERIFY", "true")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://idp.example.com/jwks")

    identity = resolve_workload_identity(
        {"authorization": "Bearer not-a-valid-jwt"},
        GovernanceEvaluateRequest(team="platform"),
    )

    assert identity.source == "default"
    assert identity.team == "platform"
