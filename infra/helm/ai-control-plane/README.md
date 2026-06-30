# AI Control Plane Helm Chart

This chart deploys the AI Control Plane API and optional Kubernetes autoscaling.

## Security Defaults

The chart defaults to non-root containers, a read-only root filesystem, dropped Linux capabilities, and a non-`latest` image tag so rendered manifests can pass the repository OPA policy gates.

## Autoscaling

Autoscaling is enabled by default:

```yaml
autoscaling:
  enabled: true
  minReplicas: 1
  maxReplicas: 3
  targetCPUUtilizationPercentage: 70
```

When autoscaling is enabled, the Deployment does not set `spec.replicas`; the HorizontalPodAutoscaler owns replica count.

To disable autoscaling and use a fixed replica count:

```yaml
replicaCount: 1

autoscaling:
  enabled: false
```

## Resources

The chart renders a production-oriented set of resources:

| Resource | Default | Toggle |
| --- | --- | --- |
| Deployment, Service | always | - |
| HorizontalPodAutoscaler | enabled | `autoscaling.enabled` |
| ServiceAccount (token automount off) | enabled | `serviceAccount.create` |
| ConfigMap (model inventory, mounted read-only) | enabled | `modelInventory.enabled` |
| PodDisruptionBudget | enabled | `podDisruptionBudget.enabled` |
| ServiceMonitor (Prometheus Operator) | disabled | `metrics.serviceMonitor.enabled` |
| Ingress | disabled | `ingress.enabled` |
| NetworkPolicy | disabled | `networkPolicy.enabled` |

## Model Inventory

When `modelInventory.enabled` is true, the chart renders the inventory into a
ConfigMap, mounts it read-only at `modelInventory.mountPath`, and sets
`MODEL_INVENTORY_PATH` so the control API serves it. Edit `modelInventory.models`
in `values.yaml` to declare your backends.

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
