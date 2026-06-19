# Loki Logging

This directory contains example logging configuration for the AI Infrastructure Control Plane. It complements the existing Prometheus metrics and Grafana dashboards with Kubernetes log collection through Loki and Promtail.

The files are intentionally small and reviewable. They are suitable for a lab or single-node k3s environment, not a production logging platform.

## Files

- `loki-values.yaml` - baseline Helm values for a small Loki deployment.
- `promtail-values.yaml` - baseline Helm values for Kubernetes pod log scraping.
- `../grafana/dashboards/loki-logs.json` - Grafana dashboard for Loki-backed log exploration.

## Install

Add the Grafana Helm repository:

```sh
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
```

Install Loki:

```sh
helm upgrade --install loki grafana/loki \
  --namespace observability \
  --create-namespace \
  -f observability/loki/loki-values.yaml
```

Install Promtail:

```sh
helm upgrade --install promtail grafana/promtail \
  --namespace observability \
  -f observability/loki/promtail-values.yaml
```

## Grafana Datasource

Add a Loki datasource in Grafana that points to:

```text
http://loki-gateway.observability.svc.cluster.local
```

Then import `observability/grafana/dashboards/loki-logs.json`.

## Log Labels

The Promtail values keep Kubernetes labels that are useful for platform debugging:

- `namespace`
- `pod`
- `container`
- `app`
- `component`

Example LogQL queries:

```logql
{namespace="ai-infra-control-plane"}
{app="ai-control-plane"} |= "error"
sum by (container) (count_over_time({namespace="ai-infra-control-plane"}[5m]))
```

## Production Notes

For production, review retention, object storage, ingestion limits, tenant isolation, authentication, and alerting rules before using this baseline.
