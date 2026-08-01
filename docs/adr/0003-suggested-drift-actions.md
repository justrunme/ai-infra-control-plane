# ADR 0003: Drift suggested actions without auto-remediation

## Status

Accepted (v1.4)

## Context

Inventory drift was detectable (`GET /drift`) but operators had no structured
next step. Auto-pulling models or mutating inventory is unsafe without change
control.

## Decision

Expose `GET /drift/actions` that returns **suggested** remediations:

- pull / unload / inventory edit commands
- GitHub issue / PR bodies for GitOps workflows

Never auto-apply remediations in the control plane.

## Consequences

- Safe for enterprise: humans or external automation choose apply path.
- GitOps integration is template-based (issue/PR text), not a hard GitHub API
  dependency in the control plane.
