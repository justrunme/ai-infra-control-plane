# Backlog

Use this backlog to create small, reviewable pull requests.

## Completed

- Ollama/vLLM probes, Prometheus metrics, Grafana dashboards
- Config-driven inventory, operator dashboard, drift detection
- Helm hardening, GHCR cosign/SBOM, Terraform k3s bootstrap
- Governance pipeline, registries, live Redis/Prometheus inputs
- Platform demo tiers (laptop / production / enterprise)
- **v0.2:** PolicyBundle digests, durable SQLite decisions/approvals, approval API, probe cache, shared httpx client (`HTTP_TRUST_ENV=false`)
- **v0.3:** Control API router split, Postgres backend + CI, production JWKS fail-closed profile, kind Helm e2e
- **v0.4:** Governance latency histogram + SLO, Grafana SLO dashboard, concurrent benchmark, failure-injection matrix, SQLite WAL/concurrency, fail-closed 503
- **v0.5:** Request-bound one-time approvals (cost/token digest + OIDC approver auth), production PostgreSQL via Secret, single-node SQLite profile, Helm multi-replica SQLite guard, `/livez` + `/readyz`
- **v1.0:** Postgres connection pool + schema migrations + DB metrics, multi-replica Postgres kind e2e, frozen OpenAPI + compatibility CI, unified error envelope, approval pagination, maturity boundary + upgrade guide

## Next (post-1.0)

1. Optional ITSM webhook adapter behind a single `ApprovalNotifier` interface
2. Retention policies / purge jobs for decisions and audit meta
3. Alembic CLI packaging for operator-run migrations (beyond in-process schema_migrations)
4. Multi-region control-plane federation

## Explicitly deferred

OpenWebUI health, new cloud Terraform modules, ITSM connectors, new forecasting models, Kubernetes operator/CRDs.
