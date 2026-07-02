# AI Infrastructure OS — Product Roadmap

**AI Infrastructure Control Plane** is the open-source **operating layer** for private AI platforms on Kubernetes: policy, cost, capacity, observability, and fleet operations.

The [AI Runtime Platform](https://github.com/justrunme/ai-runtime-platform) is the reference **Execution Plane** — not a separate product, but module #1 of the same platform story.

## Platform map

```text
AI Infrastructure OS
├── Execution Plane       → ai-runtime-platform (OpenAI gateway, routing, shadow)
├── Control Plane         → ai-infra-control-plane (Control API, dashboard)
├── Policy Engine         → governance/ + OPA + runtime enforcement
├── Cost & Chargeback     → cost governance + tenant quota + forecasting
├── Fleet & Topology      → /topology, inventory drift, digital twin
├── Capacity Planner      → experiments/inference-autoscaling
├── Observability & SLO   → observability/slo/, Grafana, OTel
└── GitOps & Security     → infra/helm, Terraform, security/opa
```

## Module maturity (main)

| Module | Location | Maturity | Notes |
| --- | --- | --- | --- |
| Execution Plane | `ai-runtime-platform` | 7/10 | Routing, shadow, governance enforcement |
| Control Plane API | `apps/control-api` | 8/10 | Dashboard, drift, topology, audit API |
| Identity & Audit | `apps/control-api/app/identity_service.py` | 6/10 | JWT/header identity, in-memory audit trail |
| Secrets & ESO | `security/secrets/` + `/secrets/status` | 6/10 | Vault paths, ExternalSecret Helm wiring |
| Policy Engine | `governance/` + OPA | 7/10 | Policy packs + quota → registry → cost → risk |
| Cost & Chargeback | cost + quota + tenant metrics | 6/10 | Helm-wired policies, Grafana chargeback |
| FinOps Recommendations | `finops/` + `/finops/recommendations` | 6/10 | Idle, budget, route-local actions |
| Fleet & Topology | `/topology`, `/drift` | 7/10 | Live probes vs desired inventory |
| Multi-cluster Fleet | `fleet/` + `/fleet/*` | 6/10 | Cluster registry, federation topology |
| Capacity Planner | `experiments/inference-autoscaling` + `experiments/capacity-loop` | 6/10 | Forecast → KEDA hints |
| Model Registry | `governance/registry/` | 6/10 | Risk tier, namespace, PII, budget |
| Observability & SLO | `observability/slo/` | 6/10 | Prometheus rules + alert catalog |
| Canary Analysis | `ai-runtime-platform/experiments/canary-analysis` | 5/10 | Promote/hold/rollback from shadow metrics |
| Platform Demo | `demo/platform/` | 7/10 | One-command Control + Execution planes |
| GPU Placement | `experiments/gpu-placement/` | 5/10 | VRAM / utilization / cost scoring |

## Decision vs execution

```mermaid
flowchart LR
  Client["Client / SDK"] --> Gateway["Execution Plane\n(runtime gateway)"]
  Gateway -->|CONTROL_PLANE_URL| Control["Control Plane\n/governance/evaluate"]
  Control --> Verdict["allow | block | approval"]
  Verdict --> Gateway
  Gateway --> Model["Model backend"]
  Gateway --> Metrics["Prometheus / OTel"]
  Metrics --> SLO["SLO catalog"]
```

## Enterprise epics (inside this repo)

These are **not** new repositories — they extend the flagship:

| Epic | Target | Next slice |
| --- | --- | --- |
| GPU Scheduler | `experiments/gpu-placement/` | Placement scoring prototype |
| AI Chargeback | Grafana + tenant metrics | ✅ chargeback dashboard |
| Capacity closed loop | forecasting + autoscaling | ✅ `experiments/capacity-loop/bridge.py` |
| Platform demo | `demo/platform/` | ✅ `make platform-demo` |
| Incident Copilot | `docs/runbooks/` | Alert → playbook JSON |
| Multi-cloud placement | registry + topology | Cloud/region labels on models |

## Public narrative

> I am building an open-source **AI Infrastructure Control Plane** — the operating system for private AI on Kubernetes: governance enforcement, cost and tenant quotas, SLO catalog, fleet topology, and capacity experiments. The runtime gateway is the reference execution plane.

## Related docs

- [Portfolio overview](portfolio-overview.md)
- [Runtime enforcement](runtime-enforcement.md)
- [Workload identity & quotas](workload-identity-quotas.md)
- [Identity & audit trail](identity-audit.md)
- [Policy packs](policy-packs.md)
- [Secrets management](secrets-management.md)
- [Multi-cluster fleet](multi-cluster-fleet.md)
- [FinOps recommendations](finops-recommendations.md)
- [SLO catalog](../observability/slo/README.md)
