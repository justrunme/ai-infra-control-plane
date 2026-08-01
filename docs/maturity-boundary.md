# Maturity Boundary (v2.1.0)

| Tier | Meaning | Examples |
| --- | --- | --- |
| **Supported** | Production path, covered by CI e2e/SLO, semver-stable | `/governance/evaluate`, durable approvals/decisions, Postgres HA / SQLite single-node, tenant isolation + JWT-only tenant, RBAC role gates on sensitive APIs, quota `onUnavailable`, capability contracts registry, durable PolicyBundle lifecycle (monotonic `generation` + replica sync), `/livez`/`/readyz` (policy fail-closed + generation fields), signed OCI Helm |
| **Reference** | Integrated but not fully adapter-complete | Remediation PR **drafts** + inventory-probe verify, CRDs as desired-state schemas (no in-tree controller), live Redis/Prometheus inputs, demos |
| **Experimental** | Prototype / sample-driven | Forecasting sims, FinOps CSV helpers, intent heuristics |

## Golden path

```text
Detect → Decide → Approve → Apply through GitOps → Verify in Runtime
```

Today the Supported core is durable governance + tenancy + registry contracts +
HA PolicyBundle generations. GitOps apply/verify adapters remain Reference until
v2.2+.

Supported APIs follow [api-compatibility.md](api-compatibility.md).
