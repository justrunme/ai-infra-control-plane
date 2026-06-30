# Runtime enforcement integration

The AI Infrastructure Control Plane exposes `POST /governance/evaluate` as the policy decision API. The [AI Runtime Gateway](https://github.com/justrunme/ai-runtime-platform) can consume that API as a **policy enforcement point** before inference execution.

```text
OpenAI chat request
  -> runtime gateway (/v1/chat/completions)
  -> control plane (/governance/evaluate)
  -> allow | approval_required | block
  -> model backend (runtime only when allowed)
```

## Control plane contract

Request body matches `GovernanceEvaluateRequest`:

```json
{
  "team": "platform",
  "owner": "alice",
  "environment": "development",
  "namespace": "ai-dev",
  "action": "invoke_model",
  "model": "qwen2.5:1.5b",
  "provider": "ollama",
  "input_tokens": 1000,
  "output_tokens": 500,
  "cost_per_request_usd": 0.01,
  "cost_per_hour_usd": 0.18,
  "month_to_date_cost_usd": 100,
  "forecast_monthly_cost_usd": 400,
  "sensitive_data": false,
  "tool_access": false,
  "write_permission": false
}
```

Response:

```json
{
  "final_verdict": "allow",
  "reasons": ["all governance stages allow the request"],
  "flow": ["request", "cost_decision", "risk_score", "approval_decision", "final_verdict"],
  "stages": {
    "cost": {"decision": "allow", "reasons": []},
    "risk": {"score": 12, "level": "low", "factors": []},
    "approval": {"decision": "allow", "reasons": []}
  }
}
```

Use the governance playground at `/` or the API directly to validate presets before wiring the runtime adapter.

## Runtime adapter

Configure the runtime gateway with:

```bash
export CONTROL_PLANE_URL=http://ai-control-plane:8080
```

The runtime maps to:

- map chat payloads and `x-ai-*` headers into the governance request
- reject blocked requests with `403`
- reject approval-required requests with `409`
- emit `gateway_governance_decisions_total` Prometheus metrics

Full runtime-side documentation: [runtime enforcement mode](https://github.com/justrunme/ai-runtime-platform/blob/main/docs/runtime-enforcement-mode.md).

## Local end-to-end demo

```bash
# Control plane
make run

# Runtime gateway (separate checkout)
export CONTROL_PLANE_URL=http://127.0.0.1:8080
uvicorn app.gateway.main:app --port 8090
```

Try the block preset from the governance playground, then send the same attributes through the runtime gateway using `x-ai-*` headers.

## Platform split

| Layer | Repository | Responsibility |
| --- | --- | --- |
| Control plane | `ai-infra-control-plane` | Inventory, drift, forecasting, governance evaluation |
| Runtime | `ai-runtime-platform` | Inference execution, routing, enforcement |

Together they demonstrate a private AI platform with separated policy decision and policy enforcement.
