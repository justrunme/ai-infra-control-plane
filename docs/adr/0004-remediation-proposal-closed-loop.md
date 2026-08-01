# ADR 0004: RemediationProposal closed-loop without direct apply

## Status

Accepted (v1.6)

## Context

`GET /drift/actions` (ADR 0003) returns suggestions only. Operators still need a
durable object that tracks Detect → Decide → Approve → Apply (GitOps) → Verify.

Direct mutation of production inventory or backends from the control plane would
bypass GitOps and break the trust boundary.

## Decision

Introduce durable `RemediationProposal` records with explicit lifecycle:

`proposed` → `policy_evaluated` → `approved`|`rejected` → `pr_created` →
`applied` → `verifying` → `verified`|`failed`

- Policy evaluation reuses the existing governance pipeline and optional durable
  approvals.
- `pr_created` persists a GitOps PR **draft** (title/body) and optional external
  `pr_url`. The control plane does not call the GitHub API.
- `mark-applied` is an operator/automation signal that Argo (or equivalent)
  reconciled the change.
- `verify` re-probes inventory drift and marks `verified` / `failed`.

## Consequences

- Closed-loop remediation is auditable and tenant-scoped.
- Apply remains outside the control plane (GitOps).
- Future releases may attach a GitHub adapter behind a feature flag without
  changing the lifecycle contract.
