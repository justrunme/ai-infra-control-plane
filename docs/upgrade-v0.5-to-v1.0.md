# Upgrade guide: v0.5 → v1.0

## Breaking / notable changes

1. **Image/chart tags** move to `1.0.0`.
2. **Error responses** include a unified `error` object (legacy `detail` kept).
3. **Postgres production** should use `persistence.existingSecret` (already in v0.5).
4. **Approvals list** supports `limit` / `offset` pagination (defaults preserve prior behavior).
5. **OpenAPI contract** is frozen at `apps/control-api/openapi.json`.

## Recommended steps

1. Deploy Postgres and create Secret `ai-control-plane-database` with `DATABASE_URL`.
2. Helm upgrade with `-f values-production.yaml` (or single-node SQLite profile).
3. Confirm `/readyz` is 200 and `/metrics` exposes `ai_control_db_*`.
4. Rotate any long-lived approval IDs (one-time consume still required).
5. Point scrapers at governance SLO dashboard panels.

## Rollback

Roll image/chart back to `0.5.0`. SQLite single-node PVC data remains compatible.
Postgres schema migrations are additive (`request_digest`, `used_at`, `schema_migrations`).
