# Durable Governance

Production golden path for auditable, restart-safe governance decisions.

## Promise

> No AI request reaches a model without a checkable, versioned, and auditable Control Plane decision.

## What is durable

| Object | Storage | Notes |
| --- | --- | --- |
| Policy bundle | Process memory + content digest | Loaded once; `GET /governance/policy-bundle` |
| Decision | SQLite (single-node) / Postgres (HA) | `decision_id`, verdict, stages, digests |
| Approval | Same database | `pending → approved\|rejected\|expired\|consumed` |
| Audit meta | Same database + optional JSONL/Loki | Linked by `decision_id` |

## Evaluate response fields

`POST /governance/evaluate` returns:

- `decision_id`
- `policy_bundle_id`
- `policy_digest`
- `approval_id` when `final_verdict == approval_required`

Decisions also persist `request_digest` (SHA-256 over the approval-binding field set).

## Approval lifecycle (request-bound, one-time)

```text
evaluate → approval_required + approval_id
  → POST /approvals/{id}/approve  (reviewer identity)
  → retry evaluate with header x-ai-approval-id: {id}
     AND the same bound request (subject/team/model/action/env/…)
  → allow (approval status becomes consumed)
```

An approved `approval_id` **does not** authorize a different model, environment, action, tenant, or policy digest. Replay after first successful use fails closed to the normal evaluate path.

Endpoints:

- `GET /approvals?status=pending`
- `GET /approvals/{approval_id}`
- `POST /approvals/{approval_id}/approve`
- `POST /approvals/{approval_id}/reject`
- `GET /governance/decisions/{decision_id}`
- `GET /governance/policy-bundle`
- `POST /governance/policy-bundle/reload`

## Health / readiness

| Endpoint | Meaning |
| --- | --- |
| `/livez` | Process alive (no store dependency) |
| `/readyz` | Decision store `ping()` + valid policy bundle (`503` otherwise) |
| `/health` | Operator status (`ok` / `degraded`) |
| `/healthz` | Liveness alias |

## Configuration

| Env | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./data/control-plane.db` | Decision store |
| `APPROVAL_TTL_SECONDS` | `3600` | Pending approval expiry |
| `PROBE_CACHE_TTL_SECONDS` | `5` | Backend probe cache |
| `HTTP_TRUST_ENV` | `false` | Disable proxy env for httpx |

Helm: `persistence.*` in `infra/helm/ai-control-plane/values.yaml`.

## Helm profiles

| Profile | Store | Replicas |
| --- | --- | --- |
| defaults / `values-single-node.yaml` | SQLite + PVC | 1 |
| `values-postgres.yaml` | PostgreSQL | operator choice |
| `values-production.yaml` | PostgreSQL + JWKS fail-closed | HPA 2–6 |

Helm **fails template** if SQLite is combined with `replicaCount` / `autoscaling.minReplicas` / `autoscaling.maxReplicas` > 1.

Kind proof: `bash demo/e2e/kind-e2e.sh` (also runs in CI job `e2e-kind`).
