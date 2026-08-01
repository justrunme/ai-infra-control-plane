# Maturity Boundary (v2.0)

| Tier | Meaning | Examples |
| --- | --- | --- |
| **Supported** | Production path, covered by CI e2e/SLO, semver-stable | `/governance/evaluate`, durable approvals/decisions, PolicyBundle lifecycle, RemediationProposal closed-loop, capability contracts, tenant isolation + JWT-only tenant, RBAC role gates, quota `onUnavailable`, Postgres HA / SQLite single-node, `/livez`/`/readyz`, signed OCI Helm |
| **Reference** | Integrated demos and portfolio surfaces | Platform demo overlays, Grafana dashboards, fleet topology, live Redis/Prometheus inputs, CRD samples |
| **Experimental** | Prototype / sample-driven | Forecasting sims, FinOps CSV helpers, intent heuristics |

## Golden path (Supported)

```text
Detect → Decide → Approve → Apply through GitOps → Verify in Runtime
```

Supported APIs follow [api-compatibility.md](api-compatibility.md). Experimental
modules may change without a major version bump.

CRDs under `ai.justrunme.dev/v1` are Supported desired-state contracts; controllers
that apply them are Reference until published as Supported operators.
