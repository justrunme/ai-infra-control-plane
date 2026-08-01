"""HTTP authorization helpers for control-plane routers."""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.identity_service import (
    AuthenticationError,
    AuthorizationError,
    require_bearer_claims,
    resolve_request_tenant,
)
from app.jwt_verify import is_jwt_verify_enabled
from app.rbac import require_any_role, roles_from_claims
from app.settings import get_settings


def require_roles(request: Request, *roles: str) -> str:
    """Return subject or raise 401/403 HTTPException."""
    try:
        return require_any_role(dict(request.headers), *roles)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=401, detail={"error": str(exc)}
        ) from exc
    except AuthorizationError as exc:
        raise HTTPException(
            status_code=403, detail={"error": str(exc)}
        ) from exc


def tenant_for_request(
    request: Request,
    *,
    query_tenant: str | None = None,
    body_tenant: str = "",
    allow_cross_tenant_roles: tuple[str, ...] = ("platform-admin", "auditor"),
) -> str | None:
    """Resolve tenant scope for list/get APIs.

    When JWT verify is off, returns query/body tenant (demo mode).
    When on, tenant-admin/viewer are locked to their JWT tenant; platform-admin
    and auditor may select another tenant via query.
    """
    if not is_jwt_verify_enabled():
        return (query_tenant or body_tenant or "").strip() or None

    headers = dict(request.headers)
    try:
        claims = require_bearer_claims(headers)
        jwt_tenant = resolve_request_tenant(headers)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=401, detail={"error": str(exc)}
        ) from exc

    roles = roles_from_claims(claims)
    requested = (query_tenant or body_tenant or "").strip() or None

    if roles.intersection(allow_cross_tenant_roles):
        return requested or jwt_tenant or None

    if not jwt_tenant:
        if get_settings().tenant_isolation:
            raise HTTPException(
                status_code=400,
                detail={"error": "tenant required in JWT claims"},
            )
        return requested

    if requested and requested != jwt_tenant:
        raise HTTPException(
            status_code=403,
            detail={"error": "cross-tenant access denied"},
        )
    return jwt_tenant
