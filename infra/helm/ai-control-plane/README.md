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

## Render

```sh
helm template ai-control-plane infra/helm/ai-control-plane
```
