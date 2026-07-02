# Enterprise AI reference architecture

How the two repositories compose a credible **private AI platform** for portfolio and architecture reviews.

## Stack map

```text
┌─────────────────────────────────────────────────────────────┐
│  Client / Agent / IDE                                         │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  Execution Plane (ai-runtime-platform)                        │
│  · OpenAI gateway · MCP proxy · Intent resolve              │
│  · Tenant attribution → Redis · OIDC JWT verify             │
└───────────────────────────┬─────────────────────────────────┘
                            │ CONTROL_PLANE_URL
┌───────────────────────────▼─────────────────────────────────┐
│  Control Plane (ai-infra-control-plane)                       │
│  · Governance pipeline · Registries · Audit · SLO / FinOps    │
│  · Redis quota read · Prometheus live inputs                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
     Redis              Prometheus          Keycloak
   (quota state)      (live telemetry)      (OIDC/JWKS)
```

## Demo tiers

| Tier | Command | Proves |
| --- | --- | --- |
| Laptop | `make platform-demo` | Governance enforcement, agentic layer |
| Production | `make platform-demo-production` | + shared Redis quota, Prometheus inputs |
| Enterprise | `make platform-demo-enterprise` | + OIDC JWT → identity → governance |

## Governance pipeline (control plane)

```text
policy_pack → prompt_security → agent_registry → quota
  → model_registry → sovereign_ai → cost → risk → approval → verdict
```

Post-response: `evaluate-response` quality scores. Tool path: `evaluate-tool` for MCP.

## What is reference vs prototype

| Reference (demo-ready) | Prototype / offline |
| --- | --- |
| Governance pipeline + audit | GPU placement scoring |
| Redis quota + Prometheus inputs | Capacity loop simulator |
| OIDC Keycloak overlay | Multi-cloud placement |
| MCP + Intent + registries | Some FinOps heuristics |

## Portfolio assets

- [Blog outline](blog-outline-enterprise-ai-os.md)
- [Demo GIF script](demo-gif-script.md)

## Target audience narrative

> We separate **decision** (control plane) from **execution** (runtime gateway). Every inference and tool call passes through policy, identity, quota, registry, and audit — the same pattern enterprise AI platforms use, implemented as open source on Kubernetes.
