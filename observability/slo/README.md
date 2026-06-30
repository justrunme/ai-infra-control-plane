# AI Platform SLO Catalog

Declarative service level objectives for the private AI platform spanning runtime execution and control-plane operations.

## Objectives

| SLO | SLI | Target | Owner |
| --- | --- | --- | --- |
| Gateway time-to-first-token p95 | `histogram_quantile(0.95, gateway_chat_duration_seconds_bucket)` on streaming routes | ≤ 800 ms | Runtime |
| Gateway end-to-end latency p95 | `histogram_quantile(0.95, gateway_chat_duration_seconds_bucket)` | ≤ 2.5 s | Runtime |
| Gateway fallback rate | `rate(gateway_chat_fallback_total[5m]) / rate(gateway_chat_requests_total[5m])` | ≤ 2% | Runtime |
| Shadow failure rate | `rate(gateway_chat_shadow_total{outcome="error"}[5m]) / rate(gateway_chat_shadow_total[5m])` | ≤ 5% | Runtime |
| Governance block rate | `rate(gateway_governance_decisions_total{verdict="block"}[5m]) / rate(gateway_governance_decisions_total[5m])` | ≤ 10% | Control plane |
| Inventory drift detection time | `time() - ai_control_inventory_drift_detected_timestamp` | ≤ 15 min | Control plane |
| Model availability | `avg_over_time(ai_control_model_available[5m])` | ≥ 99% | Control plane |

## Prometheus rules

Apply `prometheus-rules.yaml` in your monitoring stack or reference the expressions in Grafana alert rules.

## Dashboard notes

- **Runtime gateway dashboard** (`ai-runtime-platform/deploy/observability/gateway-dashboard.yaml`): add panels for TTFT proxy via `gateway_chat_duration_seconds` and fallback ratio.
- **Control plane dashboard** (`observability/grafana/`): add governance verdict and drift panels using `gateway_governance_decisions_total` (remote write or federation) and `ai_control_inventory_in_sync`.
- **Error budget policy**: burn > 2x for 1 h → page; burn > 5x for 15 min → block canary promotion.

## Related work

- Runtime canary analysis: `ai-runtime-platform/experiments/canary-analysis/`
- Inference autoscaling SLO: `experiments/inference-autoscaling/simulate.py`
- Runtime enforcement: `docs/runtime-enforcement.md`
