# ADR 0001: Tenant isolation for durable governance records

## Status

Accepted (v1.4)

## Context

Decisions and approvals were globally readable by ID. For enterprise multi-team
deployments this leaks governance state across tenants.

## Decision

1. Persist `decisions.tenant_id` (defaults to `team` when unset).
2. Gate read/list APIs with `TENANT_ISOLATION=true` using `x-ai-tenant` or JWT
   `tenant` / `tenant_id` / `team` claims.
3. Cross-tenant reads return **404** (not 403) to avoid ID oracle leakage.
4. Production Helm profile enables isolation by default; demos keep it off.

## Consequences

- Approvers and operators must send tenant context when isolation is on.
- Existing rows are backfilled (`tenant_id = team`) by migration `006`.
- Approval binding includes `tenant_id` so approvals cannot be reused across tenants.
