# OpenTelemetry GenAI Telemetry Prototype

This prototype maps private AI inference requests to OpenTelemetry GenAI-style telemetry. It is intentionally offline and dependency-light so the repository can show the telemetry contract before wiring a production collector into the control API.

The goal is to track AI-specific signals that ordinary HTTP metrics miss:

- model name
- provider or backend
- operation name
- input and output tokens
- latency
- tool calls
- estimated request cost

## Semantic Attributes

The prototype uses OpenTelemetry GenAI semantic convention attributes where they fit:

- `gen_ai.operation.name`
- `gen_ai.provider.name`
- `gen_ai.request.model`
- `gen_ai.response.model`
- `gen_ai.usage.input_tokens`
- `gen_ai.usage.output_tokens`
- `gen_ai.response.finish_reasons`
- `gen_ai.request.temperature`
- `gen_ai.request.max_tokens`

It also emits project-specific governance attributes:

- `ai_control.estimated_cost_usd`
- `ai_control.team`
- `ai_control.backend`

## Run

```sh
python3.12 observability/otel-genai/emit_sample.py \
  --input observability/otel-genai/sample_requests.csv
```

Write a reproducible example artifact:

```sh
python3.12 observability/otel-genai/emit_sample.py \
  --input observability/otel-genai/sample_requests.csv \
  --output observability/otel-genai/results/example_telemetry.json
```

## Output

The command emits JSON with two sections:

- `spans` - OTel-style GenAI request spans.
- `metrics` - aggregate model, token, latency, tool-call, and cost metrics.

This is not a full OTLP exporter. It is a contract prototype that can later be implemented with OpenTelemetry SDK instrumentation, an OTLP collector, and Grafana Tempo or another trace backend.

## Production Notes

Before production use, decide which content is safe to capture. Prompts, responses, tool arguments, and retrieved documents can contain secrets or personal data. This prototype captures metadata only.
