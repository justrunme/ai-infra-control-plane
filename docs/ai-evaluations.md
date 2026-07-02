# AI Evaluations

Post-response quality, safety, and cost evaluation pipeline.

## Evaluate response API

```bash
curl -sS -X POST http://127.0.0.1:8091/governance/evaluate-response \
  -H 'content-type: application/json' \
  -d '{
    "team": "platform",
    "model": "llama3.1:8b",
    "request_id": "req-abc",
    "prompt_text": "Summarize the Q3 revenue report.",
    "response_text": "Q3 revenue increased 12% year over year.",
    "reference_context": "Q3 revenue report shows 12% YoY growth.",
    "latency_ms": 820,
    "cost_usd": 0.002
  }'
```

## Scores

| Score | Meaning |
| --- | --- |
| `groundedness` | Overlap with prompt/reference context |
| `faithfulness` | Penalizes refusals when answer expected |
| `hallucination_risk` | Heuristic markers (e.g. "as an AI language model") |
| `safety` | Unsafe content patterns |
| `latency_ok` / `cost_ok` | Within configured budgets |

## Decisions

- `pass` — within thresholds
- `warn` — elevated risk or budget exceedance
- `fail` — safety failure or empty response

## Recent results

```bash
curl -sS 'http://127.0.0.1:8091/evaluations/recent?team=platform&limit=10'
```

## Runtime integration

When `GOVERNANCE_EVALUATE_RESPONSE=true`, the execution plane gateway submits evaluations after successful chat completions.
