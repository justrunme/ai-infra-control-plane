# Failure-injection matrix

Dependency failure modes for the control-plane governance path.

| Dependency | Role | Behavior when down | HTTP outcome |
| --- | --- | --- | --- |
| Redis quota state | Best-effort enrichment | Fail-open; use request fields | `200` evaluate |
| Prometheus telemetry | Best-effort enrichment | Fail-open; record errors in stage | `200` evaluate |
| Ollama / vLLM probes | Inventory / backend health | Probe endpoints report `down` | API stays up (`/health` `200`) |
| Decision store (SQLite/Postgres) | Authoritative durable state | Fail-closed | `503` on evaluate / approvals |

## Rationale

Non-authoritative inputs must not block inference governance decisions. The durable decision/approval store is authoritative: if it cannot persist or read approvals, the control plane returns `503` rather than silently losing auditability.

## Tests

- `apps/control-api/tests/test_failure_injection.py`
- `apps/control-api/tests/test_store_fail_closed.py`
- `apps/control-api/tests/test_sqlite_concurrency.py`
