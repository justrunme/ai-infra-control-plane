# Workload identity and tenant quotas

Prototype design for multi-tenant attribution and quota enforcement across the runtime gateway and control plane.

## Architecture

```text
Client
  -> x-ai-team / x-ai-owner / x-ai-tenant headers
  -> runtime gateway (tenant counters + metrics)
  -> control plane /governance/evaluate
      -> tenant quota stage
      -> model risk registry
      -> cost / risk / approval
  -> allow | block | approval_required
  -> model backend
```

## Workload identity headers

| Header | Purpose |
| --- | --- |
| `x-ai-team` | Tenant or team identifier used for quota and cost attribution |
| `x-ai-owner` | Human owner for approval workflows |
| `x-ai-subject` | Stable user or service principal ID (audit trail) |
| `x-ai-groups` | Comma-separated groups; maps to team when JWT is absent |
| `x-ai-tenant` | Optional alias for team when integrating with SSO claims |
| `x-ai-environment` | Environment label (`development`, `production`) |
| `x-ai-namespace` | Kubernetes namespace or logical isolation boundary |

The runtime gateway forwards these headers into the governance evaluate payload. The control plane quota stage reads `team`, `requests_last_minute`, and `tokens_today`.

## Tenant quota policy

Configured in `governance/quota/policies.yaml`:

```yaml
tenants:
  platform:
    requests_per_minute: 120
    tokens_per_day: 2000000
    max_monthly_budget_usd: 2000
    sensitive_data_allowed: true
```

Quota checks run **before** cost, registry, risk, and approval stages.

## Runtime prototype counters

When `TENANT_ATTRIBUTION_ENABLED=true`, the gateway:

- increments `gateway_tenant_requests_total{team}`
- tracks rolling per-team RPM and daily token estimates in memory
- passes `requests_last_minute` and `tokens_today` to the control plane

This is an in-memory prototype suitable for demos; production would use Redis or a billing service.

## Model risk registry

Model metadata lives in `governance/registry/models.yaml` and feeds registry, risk, and approval stages:

```yaml
models:
  qwen2.5-7b:
    risk_tier: low
    allowed_namespaces: [ai-dev, ai-prod]
    max_monthly_budget_usd: 500
    pii_allowed: false
    external_provider: false
```

## Request attribution flow

1. Client sends OpenAI chat request with `x-ai-team: finance`.
2. Runtime records tenant usage and builds governance payload.
3. Control plane quota stage validates RPM, token budget, and sensitive-data policy.
4. Registry stage validates model namespace and PII rules.
5. Runtime enforces final verdict before upstream inference.

## Next steps for production

- Persist tenant counters in Redis with TTL aligned to quota windows.
- Federate `gateway_tenant_*` metrics into the SLO catalog (`observability/slo/`).
- Issue workload identity from OIDC (`sub`, `groups`) instead of static headers.
- Connect quota blocks to chargeback and FinOps dashboards.
