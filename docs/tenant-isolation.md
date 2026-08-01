# Tenant isolation

## Behavior

| `TENANT_ISOLATION` | Effect |
| --- | --- |
| `false` (default / demos) | `tenant_id` is stored; reads are not filtered |
| `true` (production profile) | List/get decision & approval require tenant context and filter by it |

Tenant resolution order for reads (when `TENANT_JWT_ONLY=false`):

1. JWT claim `tenant` / `tenant_id`
2. Header `x-ai-tenant`
3. JWT claim `team` / header `x-ai-team`

When `TENANT_JWT_ONLY=true` (requires `OIDC_JWT_VERIFY=true`), only verified JWT
`tenant` / `tenant_id` / `team` claims are accepted — headers and body cannot
spoof tenant.

Writes always persist `tenant_id` (from identity; defaults to `team`).

## Examples

```bash
# Evaluate (tenant stored on decision)
curl -sS -X POST "$BASE/governance/evaluate" \
  -H 'content-type: application/json' \
  -H 'x-ai-tenant: finance' \
  -d '{"team":"finance","owner":"bob","environment":"development","namespace":"ai-dev","action":"invoke_model","model":"llama3.1:8b","provider":"ollama"}'

# Read back (must match tenant when isolation is on)
curl -sS "$BASE/governance/decisions/$DECISION_ID" -H 'x-ai-tenant: finance'
```

Cross-tenant reads return **404**.

Helm:

- `persistence.tenantIsolation` → `TENANT_ISOLATION`
- `persistence.tenantJwtOnly` → `TENANT_JWT_ONLY` (on in production values)

See also [RBAC](rbac.md).
