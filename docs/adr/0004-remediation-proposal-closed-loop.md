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
- `pr_created` persists a GitOps PR **draft** (title/body) and optional
  `pr_url`. From v2.2 an optional `GitOpsProvider` may open a **draft** GitHub
  PR when configured; default remains noop (no network).
- `mark-applied` is an operator/automation signal that Argo (or equivalent)
  reconciled the change.
- `verify` re-probes inventory drift and marks `verified` / `failed`.

## Consequences

- Closed-loop remediation is auditable and tenant-scoped.
- Apply remains outside the control plane (GitOps); the adapter never mutates
  cluster inventory or backends.
- GitHub draft-PR creation is opt-in via env (`GITHUB_TOKEN` +
  `GITHUB_REPOSITORY` or `GITOPS_PROVIDER=github`) without changing the
  lifecycle contract.
