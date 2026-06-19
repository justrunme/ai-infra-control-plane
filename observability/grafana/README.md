# Grafana

This directory contains Grafana dashboards for the AI Infrastructure Control Plane.

## Dashboards

- `dashboards/ai-control-plane.json` - overview dashboard for backend health, latency, request traffic, model availability, capacity, and hourly cost.
- `dashboards/loki-logs.json` - Loki dashboard for control plane logs, Argo CD deployment signals, and observability stack logs.
- `dashboards/topology-overview.json` - digital twin overview for platform dependencies and operational signals.

## Required Metrics

The dashboard expects the control API `/metrics` endpoint to be scraped by Prometheus.

Core metrics:

- `ai_control_backend_up`
- `ai_control_backend_latency_ms`
- `ai_control_http_requests_total`
- `ai_control_http_request_latency_ms_sum`
- `ai_control_http_request_latency_ms_count`
- `ai_control_model_available`
- `ai_control_capacity_available`
- `ai_control_estimated_hourly_cost_usd`

## Import

1. Open Grafana.
2. Go to **Dashboards**.
3. Import `dashboards/ai-control-plane.json`.
4. Select the Prometheus datasource that scrapes the control API.

For the Loki logs dashboard, import `dashboards/loki-logs.json` and select the Loki datasource configured for the cluster.

For the digital twin dashboard, import `dashboards/topology-overview.json` and select the Prometheus datasource that scrapes the control API.
