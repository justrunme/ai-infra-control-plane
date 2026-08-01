# ADR 0005: JWT-only tenant and quota fail-closed on unavailable

## Status

Accepted (v1.7)

## Context

Tenant isolation accepted header spoofing (`x-ai-tenant`) which is unsafe when
OIDC is enforced. Redis quota failures previously failed open, allowing traffic
without live counters in production.

## Decision

1. Add `TENANT_JWT_ONLY` so tenant/team attribution comes only from verified JWT
   claims when isolation is enforced in production.
2. Add control-plane RBAC roles mapped from IdP groups; enforce `platform-admin`
   on policy activate/rollback and keep `approver` for resolve paths.
3. Add `QUOTA_ON_UNAVAILABLE` with production default `approval_required`.

## Consequences

- Production Helm profile sets `tenantJwtOnly: true` and
  `quota.onUnavailable: approval_required`.
- Demo/dev keep header-based identity and quota fail-open (`allow`).
