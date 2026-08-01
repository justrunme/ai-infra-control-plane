# Backlog

Use this backlog to create small, reviewable pull requests.

## Completed

- Ollama/vLLM probes, Prometheus metrics, Grafana dashboards
- Config-driven inventory, operator dashboard, drift detection
- Helm hardening, GHCR cosign/SBOM, Terraform k3s bootstrap
- Governance pipeline, registries, live Redis/Prometheus inputs
- Platform demo tiers (laptop / production / enterprise)
- **v0.2:** PolicyBundle digests, durable SQLite decisions/approvals, approval API, probe cache, shared httpx client (`HTTP_TRUST_ENV=false`)
- **v0.3:** Control API router split (`main.py` ~76 LOC), Postgres backend + CI, production JWKS fail-closed profile, kind Helm e2e (allow/block/approval + PVC restart)

## Next (depth, not breadth)

1. Documented SLO + governance latency benchmark
2. Chaos/failure-injection matrix (Redis/Prometheus/backend down)
3. Optional ITSM webhook adapter behind a single approval notifier interface

## Explicitly deferred

OpenWebUI health, new cloud Terraform modules, ITSM connectors, new forecasting models, Kubernetes operator/CRDs.
