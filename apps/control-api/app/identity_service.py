"""Resolve workload identity from OIDC JWT claims and attribution headers."""

from __future__ import annotations

import json
import os
from typing import Any

import jwt
from pydantic import BaseModel, Field

from app.governance_service import GovernanceEvaluateRequest
from app.jwt_verify import (
    decode_unsigned_payload,
    is_jwt_verify_enabled,
    verify_bearer_token,
)

KNOWN_TEAMS = frozenset({"platform", "finance", "search"})
DEFAULT_APPROVER_GROUPS = ("ai-approvers", "secops")


class WorkloadIdentity(BaseModel):
    subject: str = "anonymous"
    team: str = "platform"
    tenant_id: str = "platform"
    owner: str = "unknown"
    groups: list[str] = Field(default_factory=list)
    policy_pack: str = ""
    environment: str = "development"
    namespace: str = "ai-dev"
    source: str = "default"


class AuthenticationError(Exception):
    """Missing or invalid credentials."""


class AuthorizationError(Exception):
    """Authenticated principal lacks required role."""


def extract_bearer_claims(headers: dict[str, str]) -> dict[str, Any]:
    authorization = headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return {}
    token = authorization[7:].strip()
    if not token:
        return {}
    try:
        if is_jwt_verify_enabled():
            return verify_bearer_token(token)
        return decode_unsigned_payload(token)
    except (ValueError, json.JSONDecodeError, jwt.PyJWTError):
        return {}


def require_bearer_claims(headers: dict[str, str]) -> dict[str, Any]:
    """Fail closed: require a valid Bearer JWT when OIDC verify is enabled."""
    authorization = headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        raise AuthenticationError("missing bearer token")
    token = authorization[7:].strip()
    if not token:
        raise AuthenticationError("missing bearer token")
    try:
        return verify_bearer_token(token)
    except (ValueError, json.JSONDecodeError, jwt.PyJWTError) as exc:
        raise AuthenticationError("invalid bearer token") from exc


def get_approver_groups() -> frozenset[str]:
    raw = os.getenv("OIDC_APPROVER_GROUPS", "").strip()
    if not raw:
        return frozenset(DEFAULT_APPROVER_GROUPS)
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def claim_roles(claims: dict[str, Any]) -> list[str]:
    """Collect group/role claims used for authorization decisions."""
    roles = normalize_groups(claims.get("groups"))
    roles.extend(normalize_groups(claims.get("roles")))
    realm_access = claims.get("realm_access")
    if isinstance(realm_access, dict):
        roles.extend(normalize_groups(realm_access.get("roles")))
    return roles


def resolve_approver_identity(
    headers: dict[str, str],
    *,
    body_reviewer: str = "",
) -> str:
    """Return the reviewer identity for approve/reject endpoints.

    When ``OIDC_JWT_VERIFY`` is enabled the reviewer is taken from the JWT and
    must belong to an approver group. In demo mode the JSON body reviewer is
    accepted.
    """
    if is_jwt_verify_enabled():
        claims = require_bearer_claims(headers)
        reviewer = (
            str(claims.get("preferred_username") or claims.get("sub") or "").strip()
        )
        if not reviewer:
            raise AuthenticationError("token missing subject")
        roles = claim_roles(claims)
        allowed = get_approver_groups()
        if not any(role in allowed for role in roles):
            raise AuthorizationError("approver role required")
        return reviewer

    reviewer = body_reviewer.strip()
    if not reviewer:
        raise AuthenticationError("reviewer required")
    return reviewer


def parse_groups_header(headers: dict[str, str]) -> list[str]:
    raw = headers.get("x-ai-groups", "").strip()
    if not raw:
        return []
    return [group.strip() for group in raw.split(",") if group.strip()]


def normalize_groups(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def team_from_groups(groups: list[str], fallback: str | None) -> str | None:
    for group in groups:
        if group in KNOWN_TEAMS:
            return group
    return fallback


def resolve_workload_identity(
    headers: dict[str, str],
    body: GovernanceEvaluateRequest,
) -> WorkloadIdentity:
    claims = extract_bearer_claims(headers)
    header_groups = parse_groups_header(headers)
    claim_groups = normalize_groups(claims.get("groups"))

    subject = (
        str(claims.get("sub") or claims.get("email") or "").strip()
        or headers.get("x-ai-subject", "").strip()
        or body.subject
        or "anonymous"
    )
    groups = claim_groups or header_groups or list(body.groups)
    team = (
        str(claims.get("team") or "").strip()
        or headers.get("x-ai-team", "").strip()
        or team_from_groups(groups, None)
        or body.team
    )
    body_tenant = str(getattr(body, "tenant_id", "") or "").strip()
    tenant_id = (
        str(claims.get("tenant") or claims.get("tenant_id") or "").strip()
        or headers.get("x-ai-tenant", "").strip()
        or body_tenant
        or team
    )
    owner = (
        str(claims.get("preferred_username") or claims.get("name") or "").strip()
        or headers.get("x-ai-owner", "").strip()
        or body.owner
    )
    environment = (
        str(claims.get("environment") or "").strip()
        or headers.get("x-ai-environment", "").strip()
        or body.environment
    )
    namespace = (
        str(claims.get("namespace") or "").strip()
        or headers.get("x-ai-namespace", "").strip()
        or body.namespace
    )
    policy_pack = (
        str(claims.get("policy_pack") or "").strip()
        or headers.get("x-ai-policy-pack", "").strip()
        or body.policy_pack
    )

    if claims:
        source = "jwt"
    elif any(
        headers.get(name)
        for name in (
            "x-ai-subject",
            "x-ai-team",
            "x-ai-tenant",
            "x-ai-owner",
            "x-ai-groups",
        )
    ):
        source = "headers"
    elif body.subject or body.groups:
        source = "body"
    else:
        source = "default"

    return WorkloadIdentity(
        subject=subject,
        team=team,
        tenant_id=tenant_id,
        owner=owner,
        groups=groups,
        policy_pack=policy_pack,
        environment=environment,
        namespace=namespace,
        source=source,
    )


def apply_identity(
    body: GovernanceEvaluateRequest,
    identity: WorkloadIdentity,
) -> GovernanceEvaluateRequest:
    update = {
        "subject": identity.subject,
        "team": identity.team,
        "owner": identity.owner,
        "groups": identity.groups,
        "policy_pack": identity.policy_pack,
        "environment": identity.environment,
        "namespace": identity.namespace,
    }
    if hasattr(body, "tenant_id"):
        update["tenant_id"] = identity.tenant_id
    return body.model_copy(update=update)


def resolve_request_tenant(headers: dict[str, str]) -> str:
    """Resolve tenant for read/list isolation (headers / JWT claims)."""
    claims = extract_bearer_claims(headers)
    return (
        str(claims.get("tenant") or claims.get("tenant_id") or "").strip()
        or headers.get("x-ai-tenant", "").strip()
        or str(claims.get("team") or "").strip()
        or headers.get("x-ai-team", "").strip()
        or ""
    )
