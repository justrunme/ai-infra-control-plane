# Backlog

Use this backlog to create small, reviewable pull requests.

## Completed

- Ollama/vLLM probes, Prometheus metrics, Grafana dashboards
- Config-driven inventory, operator dashboard, drift detection
- Helm hardening, GHCR cosign/SBOM, Terraform k3s bootstrap
- Governance pipeline, registries, live Redis/Prometheus inputs
- Platform demo tiers (laptop / production / enterprise)
- **v0.2:** PolicyBundle digests, durable SQLite decisions/approvals, approval API, probe cache, shared httpx client (`HTTP_TRUST_ENV=false`)

## Next (depth, not breadth)

1. kind/k3d CI job: Helm install → allow/block e2e → restart persistence check
2. Postgres profile (`psycopg`) + Helm PVC example
3. Finish Control API router split (`main.py` composition ≤100 LOC)
4. Fail-closed JWKS default profile for production values
5. Documented SLO + governance latency benchmark

## Explicitly deferred

OpenWebUI health, new cloud Terraform modules, ITSM connectors, new forecasting models, Kubernetes operator/CRDs.
