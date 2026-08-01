# ADR 0001: Durable governance store

## Status

Accepted (v0.2.0)

## Context

Governance evaluate returned ephemeral verdicts. Approvals had no lifecycle.
Policy YAML was reloaded on every request without a digest on the verdict.

## Decision

1. Load a `PolicyBundle` once per process with `bundle_id` + `content_digest`.
2. Persist every evaluate result in SQLite by default (`DATABASE_URL`).
3. Create durable approvals when verdict is `approval_required`.
4. Allow runtime retry via `x-ai-approval-id` after human approve.
5. Keep Prometheus/Loki for telemetry; SQLite/Postgres is authoritative for decisions.

## Consequences

- Restart-safe demos and Helm emptyDir/PVC persistence.
- Clear API surface for reviewers without ITSM integration yet.
- Postgres remains optional; no hard dependency in the default image.
