# Evidence

Maps control-plane claims to CI proof. Status vocabulary: **Tested in CI** /
**Reference implementation** / **Simulated** / **Not yet**.

This repository has no `docs/results.md` timing table; claims below cite successful
`main` workflow runs and the scripts those jobs execute. No invented latency numbers.

## Claim table

| Claim | Status | Scenario + environment | Real limits | Proof link | Negative tests |
| --- | --- | --- | --- | --- | --- |
| Governance allow / block / approval (compose) | Tested in CI | Job **e2e-compose** → `demo/e2e/compose-e2e.sh` (control-api container) | Single container compose on CI runner; SQLite/local store as scripted | Latest green CI: [38118789807](https://github.com/justrunme/ai-infra-control-plane/actions/runs/38118789807) · SHA `07ea1586f137956efaf171f2c7b9cff998ba3a5c` · job e2e-compose | Block/approval assertions in script (`grep` approved status, etc.) |
| Helm on kind: allow/block/approval + PVC restart persistence + Argo sync status | Tested in CI | Job **e2e-kind** → `demo/e2e/kind-e2e.sh`; `helm/kind-action` v1.15.1; Argo CD installed in script for sync/health check | Single-node kind; Argo sync verification is kind e2e (Reference tier for full GitOps controller productization per maturity boundary) | Same CI run 38118789807 · job e2e-kind | Script fails if approval/persistence/Argo sync assertions miss |
| Postgres HA-ish evaluate + failover (2 replicas) | Tested in CI | Job **e2e-kind-postgres** → `demo/e2e/kind-postgres-e2e.sh` | Two API replicas + Postgres in kind — not multi-AZ managed Postgres | Same CI run · job e2e-kind-postgres | Failover assertions fail the job |
| Unit/integration tests (Python 3.12/3.13), Postgres job, policy, helm, terraform, trivy, docker | Tested in CI | Matrix jobs on same workflow | Lint/test depth as configured in `ci.yml` | Same CI run 38118789807 | Any failed job fails the workflow |
| Signed OCI Helm/images + SBOM/cosign on release | Tested in CI | Release workflow on tags / release pipeline | Supply-chain proof is release-oriented; verify with cosign as documented | Release workflow success on recent main-associated release activity; see latest [Release run](https://github.com/justrunme/ai-infra-control-plane/actions/workflows/release.yml) and tag **v2.5.0** | Signature verify failures fail release checks where configured |
| Forecasting / FinOps CSV helpers / intent heuristics | Experimental / Simulated | Sample CSVs and sims under `forecasting/`, `governance/cost`, etc. | Not Supported-tier production forecasting | No production soak in CI claim table | — |
| In-tree Argo/Flux reconciliation controller | Not yet / Reference | CRDs are desired-state schemas; sync status checked in kind e2e | Full multi-cluster GitOps control is deferred (see maturity boundary) | kind e2e only | — |
| Multi-region control-plane federation / ITSM adapters / billing ledger | Not yet | Deferred / out of scope in backlog | — | — | — |

## Not proven / out of scope

- Multi-region federation and operator console approval inbox
- Billing/chargeback ledger
- Treating kind e2e as proof of large multi-tenant SaaS scale
- Invented p99 governance latency (benchmark job exists; publish numbers only when captured in-repo)

## How to reproduce

```bash
make platform-demo && make platform-demo-verify
bash demo/e2e/compose-e2e.sh
bash demo/e2e/kind-e2e.sh
bash demo/e2e/kind-postgres-e2e.sh
```

See also [docs/maturity-boundary.md](maturity-boundary.md) and [docs/release-verification.md](release-verification.md).
