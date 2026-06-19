# TimesFM Forecasting Prototype

This module is an experimental forecasting prototype for private AI platform metrics. It shows how historical observability signals can feed capacity planning without turning the control plane into a production autoscaler.

Forecasting targets:

- request latency
- request load
- available serving capacity
- estimated hourly cost

The prototype is intentionally separate from the FastAPI service and Helm chart. It is a lab module for exploring how observability data can support future scaling and capacity decisions.

## Install

```sh
cd forecasting/timesfm
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

TimesFM uses model checkpoints from Hugging Face. The first real TimesFM run downloads the checkpoint and can take several minutes depending on network and hardware.

## Run With TimesFM

```sh
python forecast.py \
  --input sample_metrics.csv \
  --metric request_latency_ms \
  --horizon 6 \
  --backend timesfm
```

## Run Lightweight Demo Mode

Use the naive backend when you want to validate the CLI shape without installing or downloading TimesFM:

```sh
python forecast.py \
  --input sample_metrics.csv \
  --metric estimated_hourly_cost_usd \
  --horizon 6 \
  --backend naive
```

The default `auto` backend tries TimesFM first and falls back to the naive trend forecast when TimesFM is not available.

## Output

The command emits JSON with the source metric, observed history length, backend, horizon, and forecast values:

```json
{
  "metric": "request_latency_ms",
  "history_points": 24,
  "backend": "naive",
  "horizon": 6,
  "last_observed": 100.1,
  "forecast": [100.92, 101.74, 102.56, 103.38, 104.2, 105.02]
}
```

## Production Notes

This module is not a production autoscaler. A production design would need model warmup, checkpoint caching, input validation, backtesting, forecast error tracking, bounds per metric, and a human approval path before any scaling action.
