# AI Control Plane Helm Chart

This chart deploys the AI Control Plane API and optional Kubernetes autoscaling.

## Security Defaults

The chart defaults to non-root containers, a read-only root filesystem, dropped Linux capabilities, and a non-`latest` image tag so rendered manifests can pass the repository OPA policy gates.

## Profiles

| Values file | Store | Replicas | Use |
| --- | --- | --- | --- |
| `values.yaml` (defaults) | SQLite | 1 (autoscaling off) | Local / CI |
| `values-single-node.yaml` | SQLite + PVC | 1 | Single-node reference |
| `values-postgres.yaml` | PostgreSQL | operator choice | Shared DB without full prod toggles |
| `values-production.yaml` | PostgreSQL | HPA 2–6 | HA + JWKS fail-closed |

The chart **fails** when SQLite is paired with more than one replica (`validate-store.yaml`).

## Autoscaling

Autoscaling is **disabled** by default because the default store is SQLite:

```yaml
autoscaling:
  enabled: false
  minReplicas: 1
  maxReplicas: 1
  targetCPUUtilizationPercentage: 70
```

Enable HPA only with PostgreSQL (`values-production.yaml`). When autoscaling is enabled, the Deployment does not set `spec.replicas`; the HorizontalPodAutoscaler owns replica count.

## Resources

The chart renders a production-oriented set of resources:

| Resource | Default | Toggle |
| --- | --- | --- |
| Deployment, Service | always | - |
| HorizontalPodAutoscaler | enabled | `autoscaling.enabled` |
| ServiceAccount (token automount off) | enabled | `serviceAccount.create` |
| ConfigMap (model inventory, mounted read-only) | enabled | `modelInventory.enabled` |
| ConfigMap (governance registry + tenant quota) | enabled | `governance.enabled` |
| ExternalSecret (Vault sync) | disabled | `secrets.externalSecrets.enabled` |
| PodDisruptionBudget | enabled | `podDisruptionBudget.enabled` |
| ServiceMonitor (Prometheus Operator) | disabled | `metrics.serviceMonitor.enabled` |
| Ingress | disabled | `ingress.enabled` |
| NetworkPolicy | disabled | `networkPolicy.enabled` |

## Model Inventory

When `modelInventory.enabled` is true, the chart renders the inventory into a
ConfigMap, mounts it read-only at `modelInventory.mountPath`, and sets
`MODEL_INVENTORY_PATH` so the control API serves it. Edit `modelInventory.models`
in `values.yaml` to declare your backends.

## Governance Policies

When `governance.enabled` is true, the chart renders a ConfigMap with the model
risk registry and tenant quota policies, then mounts them over the bundled
`/app/governance/registry/models.yaml` and `/app/governance/quota/policies.yaml`
files inside the container. Edit `governance.registryModels` and
`governance.quotaPolicies` in `values.yaml` for GitOps-driven policy updates.

## External Secrets

When `secrets.externalSecrets.enabled` is true, the chart renders an
`ExternalSecret` that syncs Vault paths into a Kubernetes `Secret` and mounts
them with `envFrom` on the control-api container. Provider API keys and gateway
credentials must not live in `values.yaml`.

```yaml
secrets:
  externalSecrets:
    enabled: true
    secretStoreRef:
      name: vault-ai-platform
      kind: ClusterSecretStore
```

See `security/secrets/` for Vault policy and example manifests. The control API
exposes `GET /secrets/status` with redacted fingerprints only.

## Observability

Pods are annotated for Prometheus scraping by default (`prometheus.io/scrape`).
For a Prometheus Operator setup, enable the ServiceMonitor instead:

```yaml
metrics:
  serviceMonitor:
    enabled: true
```

## Render

```sh
helm template ai-control-plane infra/helm/ai-control-plane

# Single-node SQLite PVC
helm template ai-control-plane infra/helm/ai-control-plane \
  -f infra/helm/ai-control-plane/values-single-node.yaml

# Production HA (PostgreSQL URL required)
helm template ai-control-plane infra/helm/ai-control-plane \
  -f infra/helm/ai-control-plane/values-production.yaml

# With all optional resources enabled
helm template ai-control-plane infra/helm/ai-control-plane \
  --set metrics.serviceMonitor.enabled=true \
  --set ingress.enabled=true \
  --set networkPolicy.enabled=true
```

Rendered manifests pass the repository OPA policy gates:

```sh
helm template ai-control-plane infra/helm/ai-control-plane > rendered.yaml
conftest test --policy security/opa/policies rendered.yaml
```
