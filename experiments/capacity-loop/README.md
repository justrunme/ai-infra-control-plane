# Capacity closed loop

Connects offline capacity forecasting to Kubernetes scaling hints.

```text
load CSV history
  -> inference-autoscaling/simulate.py (forecast + replica recommendation)
  -> capacity-loop/bridge.py (KEDA / HPA hint JSON)
  -> GitOps or operator applies scale target
```

## Run

```sh
# Step 1: forecast replicas from load history
python experiments/inference-autoscaling/simulate.py \
  --input experiments/inference-autoscaling/sample_load.csv \
  --output /tmp/forecast.json

# Step 2: convert to KEDA / HPA hints
python experiments/capacity-loop/bridge.py \
  --input /tmp/forecast.json \
  --output /tmp/keda-hint.json
```

Example output:

```json
{
  "action": "scale_up",
  "recommended_replicas": 4,
  "keda": {
    "metric": "vllm:num_requests_waiting",
    "threshold": 2.5,
    "maxReplicaCount": 6
  }
}
```

## Closed loop story

| Stage | Component |
| --- | --- |
| Observe | Prometheus queue + latency metrics |
| Forecast | `inference-autoscaling/simulate.py` |
| Recommend | replica count + reasons |
| Actuate | KEDA `ScaledObject` threshold from `bridge.py` |
| Govern | SLO catalog alerts if latency SLO burns |

Pair with the [SLO catalog](../../observability/slo/README.md) and [platform demo](../../demo/platform/README.md).
