# Runtime verification contract (v2.3)

Remediation `POST /remediation/proposals/{id}/verify` persists a typed
`RuntimeVerificationSnapshot` in `verification_snapshot`.

## Schema

```text
schema_version: runtime-verification/2.3
verified_at, proposal_id, outcome (verified|failed)
inventory: DriftStatus (current probes)
checks[]: probe_freshness | inventory_drift | baseline_closure
baseline_closure: baseline/still_missing/resolved/closed
gitops_sync: not_checked   # Argo client deferred; apply remains external
```

For backward compatibility the persisted JSON also dual-writes legacy
`DriftStatus` top-level fields (`in_sync`, `summary`, `backends`, `updated_at`).

## Pass rules

1. `inventory.in_sync`
2. Baseline missing models from the proposal are resolved (`baseline_closure.closed`)
3. Any check with `status=fail` → proposal `failed`

Live verify clears the probe cache so inventory probes are fresh. Injected
`drift` fixtures (tests) mark `probe_freshness=skipped`.
