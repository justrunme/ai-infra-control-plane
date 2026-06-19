# AI Cost Governance

This prototype evaluates private AI usage against policy-based cost controls. It connects GenAI telemetry, cost estimation, forecasted spend, and governance decisions.

The engine answers:

- Is this model allowed for this team?
- Is the model too expensive per hour?
- Has the team exceeded its monthly budget?
- Is the forecasted monthly platform cost too high?
- Should the request be allowed, warned, or blocked?

## Files

- `policies.yaml` - cost governance policy thresholds.
- `sample_usage.csv` - sample usage and forecast data.
- `evaluate.py` - deterministic policy evaluator.
- `results/example_decisions.json` - reproducible decisions generated from the sample data.

## Run

```sh
python3.12 governance/cost/evaluate.py \
  --usage governance/cost/sample_usage.csv \
  --policies governance/cost/policies.yaml
```

Write the example decisions artifact:

```sh
python3.12 governance/cost/evaluate.py \
  --usage governance/cost/sample_usage.csv \
  --policies governance/cost/policies.yaml \
  --output governance/cost/results/example_decisions.json
```

## Decision Levels

- `allow` - usage is inside model, team, and forecast limits.
- `warn` - usage is allowed, but one or more thresholds are close to being exceeded.
- `block` - usage violates a hard policy limit.

## Production Notes

This is an offline governance prototype. A production implementation would integrate with live telemetry, model registry metadata, team ownership data, approval workflows, audit logs, and enforcement points in the gateway or deployment pipeline.
