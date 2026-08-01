# Maturity Boundary (v2.2.0)

| Tier | Meaning | Examples |
| --- | --- | --- |
| **Supported** | Production path, covered by CI e2e/SLO, semver-stable | `/governance/evaluate`, durable approvals/decisions, Postgres HA / SQLite single-node, tenant isolation + JWT-only tenant, RBAC role gates on sensitive APIs, quota `onUnavailable`, capability contracts registry, durable PolicyBundle lifecycle (monotonic `generation` + replica sync), optional GitOps draft-PR adapter (`GITOPS_PROVIDER` / GitHub), `/livez`/`/readyz` (policy fail-closed + generation fields), signed OCI Helm |
| **Reference** | Integrated but not fully adapter-complete | Remediation runtime verify (inventory-probe), CRDs as desired-state schemas (no in-tree controller), live Redis/Prometheus inputs, demos |
| **Experimental** | Prototype / sample-driven | Forecasting sims, FinOps CSV helpers, intent heuristics |

## Golden path

```text
Detect → Decide → Approve → Apply through GitOps → Verify in Runtime
```

Supported core includes durable governance, HA PolicyBundle generations, and
optional draft GitHub PRs for remediation. Runtime verification contracts remain
Reference until v2.3+.

Supported APIs follow [api-compatibility.md](api-compatibility.md).
