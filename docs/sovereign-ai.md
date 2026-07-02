# Sovereign AI

Data residency and regional model routing for regulated workloads.

## Residency rules

`governance/sovereign/residency.yaml` defines per-region constraints:

| Region | Behavior |
| --- | --- |
| `eu-central` | Block external providers; require local/on-prem models |
| `us-east-1` | Allow external providers |
| `local` | Demo/sandbox — relaxed |

## Model regions

Models declare `allowed_regions` in `governance/registry/models.yaml`. Example: `gpt-4.1-mini` is limited to `us-east-1`.

## Policy pack

`eu-sovereign` policy pack requires `x-ai-region: eu-central` and blocks external providers.

```bash
curl -sS -X POST http://127.0.0.1:8091/governance/evaluate \
  -H 'x-ai-policy-pack: eu-sovereign' \
  -H 'x-ai-region: eu-central' \
  -H 'content-type: application/json' \
  -d '{
    "team": "platform",
    "namespace": "ai-prod",
    "environment": "production",
    "model": "gpt-4.1-mini",
    "provider": "openai",
    "region": "eu-central"
  }'
```

## Headers

| Header | Purpose |
| --- | --- |
| `x-ai-region` | Target residency region (`eu-central`, `us-east-1`, `local`) |

## Pipeline stage

```text
... → model_registry → sovereign_ai → cost_decision → ...
```
