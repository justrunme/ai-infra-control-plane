# AI Inference Autoscaling Simulator

This experiment turns historical inference signals into forecast-driven replica recommendations. It is an offline prototype for private AI workloads, not a production autoscaler.

The simulator models this flow:

```text
Prometheus-style metrics -> load and latency forecast -> replica recommendation
```

## Signals

`sample_load.csv` contains example inference traffic signals:

- `request_rate_rps`
- `p95_latency_ms`
- `input_tokens_per_second`
- `output_tokens_per_second`
- `current_replicas`
- `capacity_per_replica_rps`

These map to the platform story already present in the repository: metrics, forecasting, capacity, cost, and Kubernetes autoscaling.

## Run

```sh
python3.12 experiments/inference-autoscaling/simulate.py \
  --input experiments/inference-autoscaling/sample_load.csv \
  --horizon 6
```

The command emits JSON with:

- forecasted request rate
- forecasted p95 latency
- forecasted token throughput
- current capacity
- recommended replicas
- scale reason

## Example

```sh
python3.12 experiments/inference-autoscaling/simulate.py \
  --input experiments/inference-autoscaling/sample_load.csv \
  --horizon 6 \
  --output experiments/inference-autoscaling/results/example_forecast.json
```

## Decision Model

The prototype recommends replicas from the larger of:

- forecasted request load divided by target utilization
- forecasted latency pressure against the latency SLO
- token throughput pressure against per-replica token capacity

Defaults:

- target utilization: `0.70`
- latency SLO: `450 ms`
- token capacity per replica: `1800 tokens/s`
- max scale-up step: `2 replicas`

## Production Notes

A production design would need backtesting, confidence intervals, cooldown windows, HPA/KEDA integration, model-specific capacity profiles, queue depth, GPU metrics, and human approval for high-impact scaling changes.
