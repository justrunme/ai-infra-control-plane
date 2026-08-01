# Control Plane SLOs

Service level objectives for the AI Infrastructure Control Plane governance path.

## Objectives

| SLO | SLI | Target | Validation |
| --- | --- | --- | --- |
| Governance evaluate latency p95 | `histogram_quantile(0.95, ai_control_governance_evaluate_latency_ms_bucket)` | ≤ 250 ms | `demo/e2e/benchmark_governance.sh` |
| Governance evaluate availability | `1 - errors / evaluate_count` | ≥ 99.9% | Prometheus rule + fail-closed tests |
| Model availability | `avg(ai_control_model_available)` | ≥ 99% | Existing inventory drift alerts |
| Approval queue depth | `ai_control_approvals_pending` | ≤ 25 (warn) | PrometheusRule |
| Decision store error rate | `ai_control_db_operation_errors_total` | ≤ 1% | PrometheusRule |
| Decision store latency | avg DB op latency | ≤ 100 ms (warn) | PrometheusRule |

## Metrics

Emitted by `GET /metrics`:

- `ai_control_governance_evaluate_latency_ms` (histogram)
- `ai_control_governance_evaluate_latency_ms_sum` / `_count`
- `ai_control_governance_evaluate_errors_total{reason=...}`
- `ai_control_approvals_pending`
- `ai_control_db_operation_*` / pool gauges
- `ai_control_inventory_in_sync` / `ai_control_inventory_drift`

Recording rules and alerts live in [`observability/slo/prometheus-rules.yaml`](../observability/slo/prometheus-rules.yaml).
Helm can install the control-plane subset via `metrics.prometheusRule.enabled`
([`templates/prometheusrule.yaml`](../infra/helm/ai-control-plane/templates/prometheusrule.yaml)).

## Dashboard

Import [`observability/grafana/dashboards/governance-slo.json`](../observability/grafana/dashboards/governance-slo.json) for p95 latency, error ratio, and throughput.

## Benchmark

```sh
bash demo/e2e/benchmark_governance.sh
```

Defaults: 300 requests, concurrency 10, fail if any error or p95 > 250 ms.
