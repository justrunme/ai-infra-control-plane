# Policy packs

Named governance profiles (`production`, `development`, `research`) that tighten or relax controls before quota, registry, cost, risk, and approval stages.

## Resolution order

1. Explicit `policy_pack` in evaluate payload or `x-ai-policy-pack` header
2. `environment_map` in `governance/policy-packs/packs.yaml`
3. `default_pack` (`development`)

## Pack behavior

| Pack | Quota multiplier | Unknown models | External providers | Environment gate |
| --- | --- | --- | --- | --- |
| `production` | 1.0 | block | block | requires `production` |
| `development` | 2.0 | allow | allow | none |
| `research` | 5.0 | allow | allow | none |

Production also sets `min_risk_for_approval: medium` (evaluated after the risk stage).

## Example

```bash
# Block unregistered model under production pack
curl -sS -X POST http://127.0.0.1:8091/governance/evaluate \
  -H 'x-ai-policy-pack: production' \
  -H 'content-type: application/json' \
  -d '{
    "team": "platform",
    "environment": "production",
    "namespace": "ai-prod",
    "model": "experimental-model",
    "provider": "ollama"
  }'
```

## Related

- [Identity and audit trail](identity-audit.md)
- [Workload identity and quotas](workload-identity-quotas.md)
