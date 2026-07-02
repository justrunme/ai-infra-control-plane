"""Resolve workload identity from OIDC JWT claims and attribution headers."""

from __future__ import annotations

import base64
import json
from typing import Any

from pydantic import BaseModel, Field

from app.governance_service import GovernanceEvaluateRequest

KNOWN_TEAMS = frozenset({"platform", "finance", "search"})


class WorkloadIdentity(BaseModel):
    subject: str = "anonymous"
    team: str = "platform"
    owner: str = "unknown"
    groups: list[str] = Field(default_factory=list)
    policy_pack: str = ""
    environment: str = "development"
    namespace: str = "ai-dev"
    source: str = "default"


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("JWT must have three segments")
    padding = "=" * (-len(parts[1]) % 4)
    payload = base64.urlsafe_b64decode(parts[1] + padding)
    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        raise ValueError("JWT payload must be a JSON object")
    return decoded


def extract_bearer_claims(headers: dict[str, str]) -> dict[str, Any]:
    authorization = headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return {}
    token = authorization[7:].strip()
    if not token:
        return {}
    try:
        return _decode_jwt_payload(token)
    except (ValueError, json.JSONDecodeError):
        return {}


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
        str(claims.get("team") or claims.get("tenant") or "").strip()
        or headers.get("x-ai-team", "").strip()
        or headers.get("x-ai-tenant", "").strip()
        or team_from_groups(groups, None)
        or body.team
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
    return body.model_copy(
        update={
            "subject": identity.subject,
            "team": identity.team,
            "owner": identity.owner,
            "groups": identity.groups,
            "policy_pack": identity.policy_pack,
            "environment": identity.environment,
            "namespace": identity.namespace,
        }
    )
