# GPU placement scoring

Prototype scheduler that scores **workload → GPU** placement using VRAM fit, utilization headroom, queue pressure, and cost.

```text
workload + GPU candidates (CSV)
  -> score placement per row
  -> place | reject per candidate
  -> winner per workload_id
```

## Run

```sh
python experiments/gpu-placement/score.py \
  --input experiments/gpu-placement/sample_workloads.csv
```

## Signals

| Input | Effect |
| --- | --- |
| `model_size_gb` + `batch_size` | Estimated VRAM requirement |
| `gpu_vram_gb` | Capacity fit |
| `gpu_utilization` | Headroom on candidate node |
| `queue_depth` | Congestion penalty |
| `cost_per_hour_usd` | Cost-aware tie-breaker |

## Platform context

This experiment complements:

- [Capacity closed loop](../capacity-loop/README.md) — when to scale replicas
- [Fleet topology](../../docs/portfolio-overview.md) — where models run
- [Model risk registry](../../governance/registry/models.yaml) — which models are approved
