"""Role-based access control mapped from IdP group/role claims."""

from __future__ import annotations

import os
from collections.abc import Iterable

from app.identity_service import (
    AuthenticationError,
    AuthorizationError,
    claim_roles,
    get_approver_groups,
    require_bearer_claims,
)
from app.jwt_verify import is_jwt_verify_enabled

ControlPlaneRole = str

KNOWN_ROLES: frozenset[str] = frozenset(
    {
        "platform-admin",
        "tenant-admin",
        "approver",
        "auditor",
        "viewer",
        "runtime-service",
    }
)

_DEFAULT_ROLE_GROUPS: dict[str, frozenset[str]] = {
    "platform-admin": frozenset({"platform-admins", "ai-platform-admins"}),
    "tenant-admin": frozenset({"tenant-admins", "ai-tenant-admins"}),
    "approver": frozenset(),  # filled from OIDC_APPROVER_GROUPS at resolve time
    "auditor": frozenset({"ai-auditors", "auditors"}),
    "viewer": frozenset({"ai-viewers", "viewers"}),
    "runtime-service": frozenset({"ai-runtime-services", "runtime-services"}),
}


def _parse_group_csv(raw: str) -> frozenset[str]:
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def role_groups(role: str) -> frozenset[str]:
    """Return IdP groups that grant ``role``."""
    if role not in KNOWN_ROLES:
        return frozenset()
    env_key = f"OIDC_ROLE_{role.upper().replace('-', '_')}_GROUPS"
    raw = os.getenv(env_key, "").strip()
    if raw:
        return _parse_group_csv(raw)
    if role == "approver":
        return get_approver_groups()
    return _DEFAULT_ROLE_GROUPS[role]


def roles_from_claims(claims: dict) -> set[str]:
    """Map JWT group/role claims onto control-plane roles."""
    claimed = set(claim_roles(claims))
    granted: set[str] = set()
    for role in KNOWN_ROLES:
        if claimed.intersection(role_groups(role)):
            granted.add(role)
    # Direct role claim passthrough (e.g. roles=["platform-admin"]).
    granted.update(claimed.intersection(KNOWN_ROLES))
    return granted


def principal_has_any_role(claims: dict, required: Iterable[str]) -> bool:
    granted = roles_from_claims(claims)
    return any(role in granted for role in required)


def require_any_role(headers: dict[str, str], *required: str) -> str:
    """Return principal subject when JWT verify is on and a required role matches.

    When JWT verify is disabled (demo mode), returns ``demo`` without checking
    roles so local/dev flows keep working.
    """
    if not required:
        raise ValueError("at least one role is required")
    if not is_jwt_verify_enabled():
        return "demo"
    claims = require_bearer_claims(headers)
    subject = str(
        claims.get("preferred_username") or claims.get("sub") or ""
    ).strip()
    if not subject:
        raise AuthenticationError("token missing subject")
    if not principal_has_any_role(claims, required):
        raise AuthorizationError(
            "required role: " + " or ".join(required)
        )
    return subject
