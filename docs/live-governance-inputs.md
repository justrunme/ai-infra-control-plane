# Live governance inputs

Production-grade governance signals beyond request body fields: shared Redis quota state and Prometheus telemetry.

## Redis quota state

Gateway replicas write tenant counters to Redis when `TENANT_ATTRIBUTION_ENABLED=true` and `REDIS_URL` is set. The control plane reads the same keys when `QUOTA_REDIS_URL` points at the shared Redis:

| Key | Fields |
| --- | --- |
| `ai:tenant:{team}` | `window_start`, `requests_last_minute`, `tokens_today`, `tokens_day` |

During `POST /governance/evaluate`, empty `requests_last_minute` / `tokens_today` in the request are backfilled from Redis before the quota stage runs.

```bash
curl -sS http://127.0.0.1:8091/governance/inputs/status
```

## Prometheus telemetry

Enable live SLO-style inputs from a Prometheus query API:

| Variable | Purpose |
| --- | --- |
| `PROMETHEUS_GOVERNANCE_ENABLED` | `true` to activate |
| `PROMETHEUS_URL` | Base URL, e.g. `http://prometheus:9090` |
| `PROMETHEUS_MAX_ERROR_RATE` | Block when gateway error rate exceeds threshold (default `0.05`) |
| `PROMETHEUS_MAX_P95_LATENCY_MS` | Block when p95 latency exceeds threshold (default `2500`) |

Queries align with the [SLO catalog](../observability/slo/README.md):

- `gateway_chat_duration_seconds_bucket` → p95 latency
- `gateway_chat_errors_total` / `gateway_chat_requests_total` → error rate
- `gateway_governance_decisions_total` → governance block rate
- `gateway_tenant_requests_total` → tenant request rate

Responses include a `telemetry` object with fetched values. Threshold breaches prepend block reasons to the final verdict.

## Local overlay

### Platform demo (recommended)

```sh
# Production path: Redis + Prometheus + full governance verify
make platform-demo-production
make platform-demo-production-verify

# Enterprise reference: production + Keycloak OIDC
make platform-demo-enterprise
make platform-demo-enterprise-verify
```

### Manual env (control plane + runtime outside Compose)

```sh
# Runtime: shared Redis tenant counters
export REDIS_URL=redis://127.0.0.1:6379/0

# Control plane: point at the same Redis + Prometheus
export QUOTA_REDIS_URL=redis://127.0.0.1:6379/0
export PROMETHEUS_GOVERNANCE_ENABLED=true
export PROMETHEUS_URL=http://127.0.0.1:9090
```

Legacy runtime compose overlays:

```sh
docker compose \
  -f deploy/local/docker-compose.yaml \
  -f deploy/local/docker-compose.shared-state.yaml \
  up --build
```

## Related

- [Workload identity and quotas](workload-identity-quotas.md)
- [Identity and audit trail](identity-audit.md)
