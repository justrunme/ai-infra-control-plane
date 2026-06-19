# AI Governance Decision Pipeline

This prototype connects the governance modules into one end-to-end control-plane workflow.

The pipeline runs:

```text
request
  -> telemetry sample
  -> cost decision
  -> risk score
  -> approval decision
  -> final verdict
```

It demonstrates how private AI platform operations can move from raw request signals to explainable governance outcomes.

## Files

- `sample_requests.csv` - sample request and telemetry signals.
- `run_pipeline.py` - deterministic pipeline runner.
- `results/example_decisions.json` - reproducible end-to-end decisions.

## Run

```sh
python3.12 governance/pipeline/run_pipeline.py \
  --requests governance/pipeline/sample_requests.csv
```

Write the example decisions artifact:

```sh
python3.12 governance/pipeline/run_pipeline.py \
  --requests governance/pipeline/sample_requests.csv \
  --output governance/pipeline/results/example_decisions.json
```

## Final Verdicts

- `allow` - cost, risk, and approval checks allow the request.
- `approval_required` - the request is valid but needs human review before execution.
- `block` - one or more governance checks found a hard violation.

## Production Notes

This is an offline workflow prototype. A production pipeline would receive live request telemetry from the gateway, cost forecasts from observability, model metadata from a registry, identity context from IAM, and approval state from GitOps or service management systems.
