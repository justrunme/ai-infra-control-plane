# Backlog

Use this backlog to create small, reviewable pull requests. Each item should produce working code, tests, documentation, or deployable infrastructure.

## Completed

- Ollama and vLLM backend probes with tests
- Prometheus metrics and Grafana dashboards
- Configuration-driven model inventory (`MODEL_INVENTORY_PATH`, Helm ConfigMap)
- Live operator dashboard at `/`
- Live digital twin topology with backend probe health
- Argo CD application manifest
- Helm chart with HPA and production hardening (SA, PDB, ServiceMonitor, Ingress, NetworkPolicy)
- GHCR image publish workflow with cosign signing and SPDX SBOM
- Terraform k3s bootstrap example
- Trivy, Hadolint, OPA unit tests, and Conftest policy gates in CI
- TimesFM forecasting and inference autoscaling simulator
- OpenTelemetry GenAI telemetry prototype
- AI governance engines (cost, risk, approval, pipeline) with unit tests
- MIT LICENSE

## Next

1. Add OpenWebUI service health checks
   - Probe the UI endpoint from the control API.
   - Reflect health in `/topology` and the operator dashboard.

2. Add gateway enforcement for governance verdicts
   - Wire the governance pipeline into an admission or proxy hook.
   - Block or require approval before high-risk requests execute.

3. Add live Prometheus query integration
   - Feed real latency and cost signals into governance decisions.
   - Replace CSV-based telemetry samples where practical.

4. Add probe result caching
   - Cache Ollama and vLLM probe results for `/metrics` and `/topology`.
   - Reduce synchronous backend calls under scrape load.

5. Add latency-based HPA metrics
   - Extend the Helm chart with custom metrics from Prometheus Adapter.
   - Document the ServiceMonitor and scaling contract.

## Archive (original roadmap)

<details>
<summary>Week 1–3 original items (mostly done)</summary>

### Week 1

1. Add Ollama backend probe — **done**
2. Add Prometheus metrics — **done**
3. Add Grafana model latency dashboard — **done**

### Week 2

4. Add Argo CD application — **done**
5. Add Kubernetes autoscaling — **done**
6. Add container publish workflow — **done**
7. Add TimesFM forecasting prototype — **done**

### Week 3

8. Add vLLM backend probe — **done**
9. Add Terraform example environment — **done**
10. Add security policy checks — **done**
11. Add Loki logging — **done**
12. Add AI inference autoscaling simulator — **done**
13. Add OpenTelemetry GenAI telemetry prototype — **done**
14. Add AI infrastructure digital twin — **done**
15. Add AI cost governance engine — **done**
16. Add AI approval workflow prototype — **done**
17. Add AI risk scoring engine — **done**
18. Add AI governance decision pipeline — **done**

</details>
