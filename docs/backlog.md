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
- **v0.4:** Governance latency histogram + SLO (p95 ≤ 250 ms, availability ≥ 99.9%), Grafana SLO dashboard, concurrent benchmark CI job, failure-injection matrix, SQLite WAL/concurrency hardening, fail-closed 503 on store outage

## Next (depth, not breadth)

1. Optional ITSM webhook adapter behind a single approval notifier interface
2. Stable API schema freeze + supported/reference/experimental boundary toward v1.0

## Explicitly deferred

OpenWebUI health, new cloud Terraform modules, ITSM connectors, new forecasting models, Kubernetes operator/CRDs.
