# Maturity Boundary (v1.0)

| Tier | Meaning | Examples |
| --- | --- | --- |
| **Supported** | Production path, covered by CI e2e/SLO, semver-stable | `/governance/evaluate`, approvals, PolicyBundle, decision store (SQLite single-node / Postgres HA), `/livez`/`/readyz`, Helm profiles |
| **Reference** | Integrated demos and portfolio surfaces | Platform demo overlays, Grafana dashboards, fleet topology, live Redis/Prometheus inputs |
| **Experimental** | Prototype / sample-driven | Forecasting sims, FinOps CSV helpers, agent/tool YAML registries, intent heuristics |

Supported APIs follow [api-compatibility.md](api-compatibility.md). Experimental modules may change without a major version bump.
