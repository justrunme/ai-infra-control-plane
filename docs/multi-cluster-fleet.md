# Multi-cluster fleet

Enterprise slice #4: federated cluster registry with per-cluster health and a fleet topology graph.

## Architecture

```text
Control Plane
  -> fleet/clusters.yaml (registry)
  -> live probes for primary / probe_enabled clusters
  -> static signals for remote clusters (GitOps-registered)
  -> GET /fleet/clusters
  -> GET /fleet/topology (graph_version: v2-fleet)
```

`GET /topology` remains the single-cluster digital twin (`graph_version: v1`). Use `/fleet/topology` for the federation view.

## Cluster registry

Configured in `fleet/clusters.yaml`:

```yaml
clusters:
  local-demo:
    label: Local Demo Cluster
    cloud: local
    region: local
    environment: development
    primary: true
    probe_enabled: true
  eu-prod:
    label: EU Production
    cloud: hetzner
    region: eu-central
    environment: production
    probe_enabled: false
    ollama_healthy: true
    vllm_healthy: true
```

When `probe_enabled: true`, the control plane probes `ollama_base_url` and `vllm_base_url` (defaults to `OLLAMA_BASE_URL` / `VLLM_BASE_URL` for the primary cluster).

## API

```bash
curl -sS http://127.0.0.1:8091/fleet/clusters | jq '.summary'
curl -sS http://127.0.0.1:8091/fleet/topology | jq '.graph_version,.nodes[].id'
```

## Metrics

`ai_control_fleet_cluster_up{cluster,cloud,region}` — `1` unless the cluster is unreachable.

## Related

- [Digital twin](digital-twin.md)
- [Policy packs](policy-packs.md)
