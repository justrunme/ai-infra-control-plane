# Retention and cleanup

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `APPROVAL_TTL_SECONDS` | `3600` | Pending approvals expire after this TTL |
| `RETENTION_DAYS` | `90` | Age threshold for deleting decisions (and related rows). `0` disables age deletes |

Helm: `persistence.retentionDays`.

## Behavior

1. Pending approvals past `expires_at` are marked `expired` (lazy on read + purge).
2. `POST /ops/retention/purge` expires stale approvals, then deletes decisions with
   `created_at` older than the cutoff (and their approvals / audit_meta).
3. Default `dry_run=true` — reports counts without deleting. Pass `dry_run=false` to apply.

```bash
curl -sS 'http://127.0.0.1:8080/ops/retention'
curl -sS -X POST 'http://127.0.0.1:8080/ops/retention/purge?dry_run=true'
curl -sS -X POST 'http://127.0.0.1:8080/ops/retention/purge?dry_run=false&limit=5000'
```

Operators typically cron the dry-run first, then apply with a bounded `limit`.

## Referential integrity

Fresh schemas declare `approvals.decision_id` and `audit_meta.decision_id` as
foreign keys to `decisions` with `ON DELETE CASCADE`. PostgreSQL upgrades apply
migration `005_decision_foreign_keys`. SQLite upgrades record the migration in
the ledger; FK enforcement on SQLite applies to freshly created databases
(`PRAGMA foreign_keys=ON`).
