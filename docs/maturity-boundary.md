# Maturity Boundary (v2.0.1)

| Tier | Meaning | Examples |
| --- | --- | --- |
| **Supported** | Production path, covered by CI e2e/SLO, semver-stable | `/governance/evaluate`, durable approvals/decisions, Postgres HA / SQLite single-node, tenant isolation + JWT-only tenant, RBAC role gates on sensitive APIs, quota `onUnavailable`, capability contracts registry, `/livez`/`/readyz` (policy fail-closed), signed OCI Helm |
| **Reference** | Integrated but not fully HA / adapter-complete | PolicyBundle lifecycle (process-local candidates/active), remediation PR **drafts** + inventory-probe verify, CRDs as desired-state schemas (no in-tree controller), live Redis/Prometheus inputs, demos |
| **Experimental** | Prototype / sample-driven | Forecasting sims, FinOps CSV helpers, intent heuristics |

## Golden path

```text
Detect → Decide → Approve → Apply through GitOps → Verify in Runtime
```

Today the Supported core is durable governance + tenancy + registry contracts.
GitOps apply/verify adapters and HA-durable PolicyBundle generations remain
Reference until v2.1+.

Supported APIs follow [api-compatibility.md](api-compatibility.md).
