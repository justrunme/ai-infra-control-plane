# Backlog

Use this backlog for small, reviewable maintenance and deferred-product PRs.

## Current stable

**v2.4.0** is the current Supported control-plane contract:

- Durable decisions/approvals (Postgres HA / SQLite single-node)
- Durable PolicyBundle generations + OCI load/signature verify
- Optional GitHub draft-PR GitOps provider
- Runtime verification contract (`runtime-verification/2.3`)
- Capability-bound approval digests
- RBAC, JWT-only tenant, quota `onUnavailable`, signed OCI Helm/images

See [product-roadmap.md](product-roadmap.md) and [maturity-boundary.md](maturity-boundary.md).

## Completed (selected)

- **v0.2–v0.5:** PolicyBundle digests, durable store, Postgres, SLO/failure-injection, request-bound approvals
- **v1.0–v1.4:** Migrations/pool, OpenAPI freeze, OCI Helm, retention, tenant isolation, ADRs
- **v1.5–v1.8:** OCI PolicyBundle lifecycle APIs, RemediationProposal closed-loop, RBAC/JWT-only/quota policy, capability contracts
- **v2.0–v2.0.1:** CRD/API stabilize + security/correctness patch
- **v2.1:** Durable HA PolicyBundle generations
- **v2.2:** GitOpsProvider + GitHub draft PR adapter
- **v2.3:** Runtime verification contract
- **v2.4:** Capability-bound execution digests

## Deferred (not in Supported scope)

1. Optional ITSM webhook adapter behind a single `ApprovalNotifier` interface
2. External install walkthrough / recorded failure demo
3. Thin Operator Console (approval inbox) — only after external install proof
4. Multi-region control-plane federation
5. In-tree CRD controllers (CRDs remain desired-state schemas)
6. Argo Application sync status inside runtime verify (`gitops_sync: not_checked` today)

## Explicitly out of scope

OpenWebUI health, new cloud Terraform modules, ITSM connectors as a product surface,
new forecasting models, GPU scheduler/big UI/FinOps clone.
