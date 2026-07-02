"""Secret reference catalog and safe status reporting for the control plane."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class SecretRefSpec(BaseModel):
    name: str
    env_var: str
    component: Literal["control-plane", "execution-plane", "shared"]
    description: str
    optional: bool = False
    rotation_days: int = 90


class SecretRefStatus(BaseModel):
    name: str
    env_var: str
    component: str
    description: str
    optional: bool
    rotation_days: int
    status: Literal["configured", "missing"]
    fingerprint: str | None = None
    source: str = "environment"


class SecretsStatusResponse(BaseModel):
    checked_at: str
    backend: Literal["environment", "kubernetes", "external-secrets"]
    configured_count: int
    missing_required_count: int
    items: list[SecretRefStatus] = Field(default_factory=list)


SECRET_CATALOG: tuple[SecretRefSpec, ...] = (
    SecretRefSpec(
        name="gateway_api_keys",
        env_var="GATEWAY_API_KEYS",
        component="execution-plane",
        description="Comma-separated API keys accepted by the runtime gateway.",
    ),
    SecretRefSpec(
        name="openai_api_key",
        env_var="OPENAI_API_KEY",
        component="execution-plane",
        description="OpenAI-compatible provider credential for external models.",
    ),
    SecretRefSpec(
        name="anthropic_api_key",
        env_var="ANTHROPIC_API_KEY",
        component="execution-plane",
        description="Anthropic provider credential for external models.",
        optional=True,
    ),
    SecretRefSpec(
        name="oidc_client_secret",
        env_var="OIDC_CLIENT_SECRET",
        component="shared",
        description="OAuth2/OIDC client secret for workload identity federation.",
        optional=True,
    ),
    SecretRefSpec(
        name="audit_signing_key",
        env_var="AUDIT_SIGNING_KEY",
        component="control-plane",
        description="HMAC key for signed governance audit events.",
        optional=True,
    ),
    SecretRefSpec(
        name="vault_token",
        env_var="VAULT_TOKEN",
        component="shared",
        description="Short-lived Vault token when not using Kubernetes auth.",
        optional=True,
    ),
)


def fingerprint_secret(value: str) -> str:
    normalized = value.strip()
    if len(normalized) <= 4:
        return "****"
    return f"{'*' * 8}{normalized[-4:]}"


def resolve_secrets_backend() -> Literal["environment", "kubernetes", "external-secrets"]:
    if os.getenv("EXTERNAL_SECRETS_ENABLED", "").strip().lower() in {"1", "true", "yes"}:
        return "external-secrets"
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        return "kubernetes"
    return "environment"


def inspect_secret(spec: SecretRefSpec) -> SecretRefStatus:
    raw = os.getenv(spec.env_var, "").strip()
    configured = bool(raw)
    source = (
        "external-secrets"
        if os.getenv("EXTERNAL_SECRETS_ENABLED")
        else "environment"
    )
    return SecretRefStatus(
        name=spec.name,
        env_var=spec.env_var,
        component=spec.component,
        description=spec.description,
        optional=spec.optional,
        rotation_days=spec.rotation_days,
        status="configured" if configured else "missing",
        fingerprint=fingerprint_secret(raw) if configured else None,
        source=source,
    )


def build_secrets_status() -> SecretsStatusResponse:
    items = [inspect_secret(spec) for spec in SECRET_CATALOG]
    configured_count = sum(1 for item in items if item.status == "configured")
    missing_required_count = sum(
        1 for item in items if item.status == "missing" and not item.optional
    )
    return SecretsStatusResponse(
        checked_at=datetime.now(UTC).isoformat(),
        backend=resolve_secrets_backend(),
        configured_count=configured_count,
        missing_required_count=missing_required_count,
        items=items,
    )
