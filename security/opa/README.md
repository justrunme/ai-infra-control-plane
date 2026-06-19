# OPA Policy Gates

This directory contains baseline OPA policies for Kubernetes manifests. The goal is to catch unsafe workload defaults before manifests are applied to a cluster.

The policies are designed for `conftest` and can be used against rendered Helm manifests, plain Kubernetes YAML, or CI-generated deployment bundles.

## Policies

`policies/kubernetes.rego` checks:

- privileged containers are not allowed
- `latest` image tags are not allowed
- CPU and memory requests and limits are required
- `readOnlyRootFilesystem` is recommended
- `runAsNonRoot` is required at pod or container level

## Run Tests

```sh
conftest verify \
  --policy security/opa
```

## Test Rendered Helm Manifests

```sh
helm template ai-control-plane infra/helm/ai-control-plane \
  | conftest test - --policy security/opa/policies
```

## Policy Scope

The policy inspects Kubernetes workload pod specs from:

- `Pod`
- `Deployment`
- `StatefulSet`
- `DaemonSet`
- `Job`
- `CronJob`

## Production Notes

These gates are a baseline. A production policy set should add namespace exceptions, image registry allowlists, signature verification, network policy checks, pod security standards, and an explicit rollout path for existing workloads.
