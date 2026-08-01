# Durable Governance

Production golden path for auditable, restart-safe governance decisions.

## Promise

> No AI request reaches a model without a checkable, versioned, and auditable Control Plane decision.

## What is durable

| Object | Storage | Notes |
| --- | --- | --- |
| Policy bundle | Process memory + content digest | Loaded once; `GET /governance/policy-bundle` |
| Decision | SQLite (default) / Postgres optional | `decision_id`, verdict, stages, digest |
| Approval | Same database | `pending → approved\|rejected\|expired` |
| Audit meta | Same database + optional JSONL/Loki | Linked by `decision_id` |

## Evaluate response fields

`POST /governance/evaluate` now returns:

- `decision_id`
- `policy_bundle_id`
- `policy_digest`
- `approval_id` when `final_verdict == approval_required`

## Approval lifecycle

```text
evaluate → approval_required + approval_id
  → POST /approvals/{id}/approve  (reviewer identity)
  → retry evaluate with header x-ai-approval-id: {id}
  → allow
```

Endpoints:

- `GET /approvals?status=pending`
- `GET /approvals/{approval_id}`
- `POST /approvals/{approval_id}/approve`
- `POST /approvals/{approval_id}/reject`
- `GET /governance/decisions/{decision_id}`
- `GET /governance/policy-bundle`
- `POST /governance/policy-bundle/reload`

## Configuration

| Env | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./data/control-plane.db` | Decision store |
| `APPROVAL_TTL_SECONDS` | `3600` | Pending approval expiry |
| `PROBE_CACHE_TTL_SECONDS` | `5` | Backend probe cache |
| `HTTP_TRUST_ENV` | `false` | Disable proxy env for httpx |

Helm: `persistence.*` in `infra/helm/ai-control-plane/values.yaml`.

## Status legend

| Status | Meaning |
| --- | --- |
| Production path | Used on the deployable runtime evaluate path |
| Integrated | Works in platform demo |
| Prototype | Sample-driven / offline module |
| Design only | Documented intent |

Durable decisions and approvals are **Production path** (SQLite by default, Postgres supported).

Helm profiles:

- `values-production.yaml` — PVC + JWKS verify fail-closed
- `values-postgres.yaml` — `DATABASE_URL=postgresql://...`

Kind proof: `bash demo/e2e/kind-e2e.sh` (also runs in CI job `e2e-kind`).
