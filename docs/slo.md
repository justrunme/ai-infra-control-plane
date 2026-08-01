# Control Plane SLOs

Service level objectives for the AI Infrastructure Control Plane governance path.

## Objectives

| SLO | SLI | Target | Validation |
| --- | --- | --- | --- |
| Governance evaluate latency p95 | `histogram_quantile(0.95, ai_control_governance_evaluate_latency_ms_bucket)` | ≤ 250 ms | `demo/e2e/benchmark_governance.sh` |
| Governance evaluate availability | `1 - errors / evaluate_count` | ≥ 99.9% | Prometheus rule + fail-closed tests |
| Model availability | `avg(ai_control_model_available)` | ≥ 99% | Existing inventory drift alerts |

## Metrics

Emitted by `GET /metrics`:

- `ai_control_governance_evaluate_latency_ms` (histogram)
- `ai_control_governance_evaluate_latency_ms_sum` / `_count`
- `ai_control_governance_evaluate_errors_total{reason=...}`

Recording rules and alerts live in [`observability/slo/prometheus-rules.yaml`](../observability/slo/prometheus-rules.yaml).

## Dashboard

Import [`observability/grafana/dashboards/governance-slo.json`](../observability/grafana/dashboards/governance-slo.json) for p95 latency, error ratio, and throughput.

## Benchmark

```sh
bash demo/e2e/benchmark_governance.sh
```

Defaults: 300 requests, concurrency 10, fail if any error or p95 > 250 ms.
