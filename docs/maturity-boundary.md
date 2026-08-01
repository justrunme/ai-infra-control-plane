# Maturity Boundary (v2.4.0)

| Tier | Meaning | Examples |
| --- | --- | --- |
| **Supported** | Production path, covered by CI e2e/SLO, semver-stable | `/governance/evaluate`, durable approvals/decisions with policy + capability digests, Postgres HA / SQLite single-node, tenant isolation + JWT-only tenant, RBAC, quota `onUnavailable`, capability contracts, durable PolicyBundle generations, optional GitOps draft-PR adapter, runtime verification contract, `/livez`/`/readyz`, signed OCI Helm |
| **Reference** | Integrated but not fully adapter-complete | Argo sync status in verify (`gitops_sync: not_checked`), CRDs without in-tree controller, live Redis/Prometheus inputs, demos |
| **Experimental** | Prototype / sample-driven | Forecasting sims, FinOps CSV helpers, intent heuristics |

## Recommended pair

| Control Plane | Runtime | Status |
| --- | --- | --- |
| **2.4.x** | **2.3.x** | Current stable closed-loop pair |

Runtime release gates also prove CP `2.0.x` (2.x baseline) and legacy `1.3.x`.
Matrix: [ai-runtime-platform compatibility](https://github.com/justrunme/ai-runtime-platform/blob/main/docs/compatibility-matrix.md).

## Golden path

```text
Detect → Decide → Approve → Apply through GitOps → Verify in Runtime
```

Supported core pins evaluate/approval reuse to PolicyBundle digests **and**
active agent/tool capability digests (v2.4).

## Honest limitations

| Limitation | Status |
| --- | --- |
| Argo/Flux reconciliation controller | Reference / deferred (CRDs are desired-state schemas) |
| Actual GitOps sync check in verify | `gitops_sync: not_checked` |
| Full operator console / approval inbox | Deferred (API is the surface) |
| Multi-region control-plane federation | Deferred |
| ITSM webhook / notifier adapters | Deferred |
| Billing / chargeback ledger | Out of scope (attribution only via Runtime metrics) |

Supported APIs follow [api-compatibility.md](api-compatibility.md).
Deferred product notes: [backlog.md](backlog.md).
