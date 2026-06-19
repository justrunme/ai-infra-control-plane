# AI Risk Scoring

This prototype scores private AI platform requests before they reach approval or enforcement workflows. It turns operational, cost, data, and permission signals into a `0-100` risk score and a risk level.

The engine evaluates:

- external model providers;
- production namespaces;
- high token volume;
- high monthly cost forecast;
- sensitive data flags;
- tool access;
- write or deployment permissions;
- missing owners.

## Files

- `rules.yaml` - scoring weights, thresholds, and provider groups.
- `sample_requests.csv` - sample request signals.
- `evaluate.py` - deterministic risk scoring evaluator.
- `results/example_risk_scores.json` - reproducible risk scores generated from sample requests.

## Run

```sh
python3.12 governance/risk/evaluate.py \
  --requests governance/risk/sample_requests.csv \
  --rules governance/risk/rules.yaml
```

Write the example scores artifact:

```sh
python3.12 governance/risk/evaluate.py \
  --requests governance/risk/sample_requests.csv \
  --rules governance/risk/rules.yaml \
  --output governance/risk/results/example_risk_scores.json
```

## Risk Levels

- `low` - routine local or development usage.
- `medium` - elevated usage or moderate governance signals.
- `high` - production, external provider, high forecast, or privileged action.
- `critical` - multiple high-risk signals or missing ownership.

## Production Notes

This is an offline scoring prototype. A production implementation would receive live telemetry, model registry metadata, data classification, identity context, cost forecasts, and deployment permissions from the control plane before passing the score into approval and enforcement systems.
