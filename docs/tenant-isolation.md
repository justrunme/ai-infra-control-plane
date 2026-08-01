# Tenant isolation

## Behavior

| `TENANT_ISOLATION` | Effect |
| --- | --- |
| `false` (default / demos) | `tenant_id` is stored; reads are not filtered |
| `true` (production profile) | List/get decision & approval require tenant context and filter by it |

Tenant resolution order for reads:

1. JWT claim `tenant` / `tenant_id`
2. Header `x-ai-tenant`
3. JWT claim `team` / header `x-ai-team`

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

Helm: `persistence.tenantIsolation` → env `TENANT_ISOLATION`.
