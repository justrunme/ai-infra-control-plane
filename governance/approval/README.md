# AI Approval Workflow

This prototype evaluates private AI platform requests before they reach an enforcement point. It turns cost governance, ownership, model risk, and deployment context into human approval decisions.

The workflow answers:

- Does the request have a responsible owner?
- Is the model approved for enterprise use?
- Did cost governance already block the request?
- Is the request targeting production?
- Does the request require human approval before execution?

## Files

- `requests.yaml` - sample AI platform requests.
- `evaluate.py` - deterministic approval evaluator.
- `results/example_approvals.json` - reproducible approval decisions generated from the sample requests.

## Run

```sh
python3.12 governance/approval/evaluate.py \
  --requests governance/approval/requests.yaml
```

Write the example decisions artifact:

```sh
python3.12 governance/approval/evaluate.py \
  --requests governance/approval/requests.yaml \
  --output governance/approval/results/example_approvals.json
```

## Decision Levels

- `allow` - the request is low-risk and can proceed automatically.
- `approval_required` - the request is valid, but needs human review before execution.
- `block` - the request violates a hard governance rule.

## Production Notes

This is an offline approval workflow prototype. A production implementation would integrate with identity, model registry metadata, cost governance results, GitOps pull requests, audit logs, and an approval system such as GitHub environments, Argo CD sync windows, ServiceNow, Jira, or an internal platform portal.
