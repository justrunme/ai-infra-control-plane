# FinOps recommendations

Enterprise slice #5: actionable cost optimization beyond chargeback dashboards.

## Signal sources

| Source | Path | Purpose |
| --- | --- | --- |
| Usage telemetry | `governance/cost/sample_usage.csv` | Team/model spend and forecasts |
| Budget policies | `governance/cost/policies.yaml` | Team monthly budgets and allowed models |
| Utilization | `finops/utilization.yaml` | GPU utilization and request rates |

## Recommendation categories

| Category | Trigger | Example action |
| --- | --- | --- |
| `idle_capacity` | Low GPU util + low RPD | Scale down replicas / move to Ollama |
| `budget_pressure` | Forecast above warn threshold | Tighten quota, require approval |
| `route_local` | External provider with local alternative | Prefer `llama3.1:8b` in gateway routing |

## API

```bash
curl -sS 'http://127.0.0.1:8091/finops/recommendations?severity=high&limit=5' | jq
```

Response includes `estimated_monthly_savings_usd` per item and in the summary.

## CLI prototype

```bash
python experiments/finops-recommendations/analyze.py \
  --usage governance/cost/sample_usage.csv \
  --policies governance/cost/policies.yaml \
  --utilization finops/utilization.yaml
```

(Add argparse main if needed - optional, API uses build_result directly)

## Metrics

`ai_control_finops_recommendations_total{category,severity}`

## Related

- [Chargeback dashboard](../observability/grafana/dashboards/chargeback-attribution.json)
- [Capacity closed loop](../experiments/capacity-loop/bridge.py)
