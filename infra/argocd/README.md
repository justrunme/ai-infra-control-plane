# Argo CD

This directory contains the GitOps entrypoint for deploying the AI Control Plane Helm chart with Argo CD.

## Application

- `application.yaml` deploys `infra/helm/ai-control-plane`.
- The default target namespace is `ai-platform`.
- The Argo CD `Application` resource itself is expected to live in the `argocd` namespace.
- Automated sync is enabled with prune and self-heal.

## Bootstrap Assumptions

- Argo CD is already installed in the cluster.
- Argo CD can read `https://github.com/justrunme/ai-infra-control-plane.git`.
- The control API image is published as `ghcr.io/justrunme/ai-infra-control-plane`.
- Ollama is reachable inside the cluster at `http://ollama.ai-platform.svc.cluster.local:11434`.

## Apply

```sh
kubectl apply -f infra/argocd/application.yaml
```

The application will create the `ai-platform` namespace during sync.

