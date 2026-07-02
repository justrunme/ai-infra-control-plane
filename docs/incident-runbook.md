# AI incident runbook generator

Turn SLO alert names into operator-ready incident context by correlating live control-plane signals.

## API

```bash
# List supported Prometheus alert names
curl -sS http://127.0.0.1:8091/incidents/alerts

# Generate a runbook for an alert
curl -sS 'http://127.0.0.1:8091/incidents/runbook?alert=InventoryDriftDetected'
curl -sS 'http://127.0.0.1:8091/incidents/runbook?alert=GovernanceBlockRateHigh&team=finance'
```

## What gets correlated

| Signal source | Used for |
| --- | --- |
| SLO alert catalog | Severity, summary, baseline runbook actions |
| `GET /drift` | Affected models, drift summary |
| `GET /topology` | Unhealthy nodes (Ollama, vLLM, …) |
| `GET /audit/events` | Recent governance blocks by tenant/model |
| `GET /fleet/clusters` | Degraded / unreachable clusters |
| `GET /finops/recommendations` | Cost/capacity remediation actions |

## Response shape

- `affected_models`, `affected_tenants`, `affected_clusters`
- `recent_governance_blocks` with blocking stage and reasons
- `recommended_actions` — static SLO runbook steps plus dynamic context
- `context_markdown` — paste-ready incident ticket body

## Alert catalog

Alert names match [observability/slo/prometheus-rules.yaml](../observability/slo/prometheus-rules.yaml):

- `GatewayLatencyP95High`
- `GatewayFallbackRateHigh`
- `ShadowFailureRateHigh`
- `GovernanceBlockRateHigh`
- `InventoryDriftDetected`
- `ModelAvailabilityLow`

In production, wire this endpoint to Alertmanager webhooks or Grafana OnCall — pass the alert name and optional `team` / `model` labels from the firing alert.

## Related

- [SLO catalog](../observability/slo/README.md)
- [Identity and audit trail](identity-audit.md)
- [Multi-cluster fleet](multi-cluster-fleet.md)
