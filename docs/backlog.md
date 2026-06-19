# Backlog

Use this backlog to create small, reviewable pull requests. Each item should produce working code, tests, documentation, or deployable infrastructure.

## Week 1

1. Add Ollama backend probe
   - Add `/backends/ollama` health check support.
   - Make the endpoint configurable through environment variables.
   - Add tests for healthy, unhealthy, and timeout responses.

2. Add Prometheus metrics
   - Expose `/metrics`.
   - Track request count, latency, model health, and capacity.
   - Document the metrics contract.

3. Add Grafana model latency dashboard
   - Create dashboard JSON under `observability/grafana`.
   - Include latency, availability, and estimated cost panels.
   - Reference Prometheus metric names from the API.

## Week 2

4. Add Argo CD application
   - Add an application manifest under `infra/argocd`.
   - Point it at the Helm chart.
   - Document bootstrap assumptions.

5. Add Kubernetes autoscaling
   - Add HPA template to the Helm chart.
   - Make min and max replicas configurable.
   - Document CPU and future latency-based scaling.

6. Add container publish workflow
   - Build and push image to GitHub Container Registry.
   - Use semantic tags and commit SHA tags.
   - Keep tests before publish.

7. Add TimesFM forecasting prototype
   - Add an experimental forecasting module under `forecasting/timesfm`.
   - Forecast latency, request rate, capacity, and estimated hourly cost.
   - Keep it separate from the control API and Helm chart.

## Week 3

8. Add vLLM backend probe
   - Add OpenAI-compatible health and model listing checks.
   - Add timeout and circuit-breaker behavior.
   - Add tests for degraded backend status.

9. Add Terraform example environment
   - Add a complete example using the Hetzner VM module.
   - Document required variables and secrets.
   - Keep apply steps manual.
   - Add a k3s bootstrap example with cloud-init and kubeconfig outputs.

10. Add security policy checks
   - Add Trivy IaC examples.
   - Add baseline Kubernetes policy notes.
   - Add future OPA/Gatekeeper roadmap.
   - Add OPA policy gates for rendered Kubernetes manifests.

11. Add Loki logging
   - Add Loki and Promtail Helm values.
   - Add a Grafana dashboard for application and platform logs.
   - Document logging labels and production hardening notes.

12. Add AI inference autoscaling simulator
   - Forecast request load, p95 latency, and token throughput from sample metrics.
   - Recommend replicas before private AI inference workloads hit limits.
   - Keep the simulator offline and separate from the production Helm chart.

13. Add OpenTelemetry GenAI telemetry prototype
   - Emit GenAI-style spans for model requests, token usage, tool calls, latency, and cost.
   - Keep prompt and response content out of the prototype artifact.
   - Document semantic attributes for future collector integration.

14. Add AI infrastructure digital twin
   - Expose a control API topology graph.
   - Document component dependencies, health, telemetry, and operational signals.
   - Add a Grafana topology overview dashboard.

15. Add AI cost governance engine
   - Evaluate model usage, token spend, and forecasted monthly cost.
   - Return allow, warn, or block decisions with reasons.
   - Keep the prototype offline until gateway enforcement exists.

16. Add AI approval workflow prototype
   - Evaluate high-risk AI platform requests before execution.
   - Return allow, approval_required, or block decisions with reasons.
   - Keep the prototype offline until gateway or GitOps enforcement exists.

17. Add AI risk scoring engine
   - Score AI platform requests from 0 to 100.
   - Classify requests as low, medium, high, or critical risk.
   - Feed risk results into future approval and policy decisions.
