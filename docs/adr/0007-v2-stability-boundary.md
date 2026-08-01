# ADR 0007: v2.0 stability boundary

## Status

Accepted (v2.0)

## Context

v1.5–v1.8 added PolicyBundle GitOps, RemediationProposal closed-loop, RBAC /
JWT-only tenant, quota fail-closed, and durable capability contracts — mostly as
`v1alpha1` CRDs and evolving APIs. Operators need a clear Supported contract.

## Decision

Ship **v2.0.0** as a stability major:

1. Promote CRDs to `ai.justrunme.dev/v1`.
2. Expand the Supported maturity tier to the Detect → Decide → Approve → Apply
   (GitOps) → Verify path.
3. Keep OpenAPI additive vs `v1.0.0` baseline (no intentional REST breaks).
4. Document upgrade from v1.x in `docs/upgrade-v1-to-v2.0.md`.

## Consequences

- GitOps manifests must use `/v1` CRDs.
- Experimental FinOps/forecasting/agent heuristics remain Experimental.
- Future breaking REST changes still require a new major and baseline move.
