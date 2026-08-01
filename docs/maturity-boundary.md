# Maturity Boundary (v2.3.0)

| Tier | Meaning | Examples |
| --- | --- | --- |
| **Supported** | Production path, covered by CI e2e/SLO, semver-stable | `/governance/evaluate`, durable approvals/decisions, Postgres HA / SQLite single-node, tenant isolation + JWT-only tenant, RBAC, quota `onUnavailable`, capability contracts, durable PolicyBundle generations, optional GitOps draft-PR adapter, runtime verification contract (`runtime-verification/2.3`), `/livez`/`/readyz`, signed OCI Helm |
| **Reference** | Integrated but not fully adapter-complete | Argo sync status in verify (`gitops_sync: not_checked`), CRDs without in-tree controller, live Redis/Prometheus inputs, demos |
| **Experimental** | Prototype / sample-driven | Forecasting sims, FinOps CSV helpers, intent heuristics |

## Golden path

```text
Detect → Decide → Approve → Apply through GitOps → Verify in Runtime
```

Supported core now includes typed runtime verification snapshots with baseline
closure. Capability-bound execution digests are next (v2.4).

Supported APIs follow [api-compatibility.md](api-compatibility.md).
