# Policy bundles and GitOps (v2.1)

## Sources

| `POLICY_SOURCE_TYPE` | Behavior |
| --- | --- |
| `filesystem` (default) | Load from `GOVERNANCE_ROOT` or `POLICY_SOURCE_PATH` |
| `oci` | `oras pull` + **cosign verify by default** |

For `POLICY_SOURCE_TYPE=oci`, signature verification is **on by default**.
Opt out only for local/dev unsigned pulls:

```bash
export POLICY_SOURCE_VERIFY_SIGNATURE=false
```

Production recommendation:

```yaml
policySource:
  type: oci
  reference: ghcr.io/justrunme/ai-policies:production
  digest: sha256:...
  verifySignature: true
  failureMode: fail_closed
  initContainer:
    enabled: true
```

With `initContainer.enabled`, Helm pulls/verifies the OCI artifact before the API
starts and mounts it read-only; the API uses `POLICY_SOURCE_TYPE=filesystem`.

### Data-only bundles (no remote code execution)

OCI/filesystem policy roots are treated as **data-only**: the control plane loads
YAML (packs, quota, registry, cost, risk, classification, …) from the bundle, but
runs evaluation engines (`evaluate.py`) from the **shipped** governance tree inside
the control-plane image.

This avoids executing arbitrary Python from a registry write. For local experiments
that intentionally load `evaluate.py` from the materialized root:

```bash
export POLICY_BUNDLE_ALLOW_EXECUTABLE=true
```

`POLICY_SOURCE_FAILURE_MODE`:

| Mode | Behavior |
| --- | --- |
| `fail_closed` (production) | Bootstrap error → `/readyz` 503 |
| `last_known_good` (demo default) | Keep previous valid bundle; mark fallback |

Active selection is **durable**: migration `009_policy_bundles` stores candidates,
impacts, and a monotonic `generation` for the active bundle. Replicas catch up via
`PolicyLifecycle.sync_active_from_store` on bootstrap, `/readyz`, and evaluate.

## Lifecycle API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/governance/policy-bundles` | Active / previous / candidates |
| POST | `/governance/policy-bundles/validate` | Load + validate source → candidate |
| POST | `/governance/policy-bundles/{id}/simulate` | Replay recent decisions |
| GET | `/governance/policy-bundles/{id}/impact` | Cached impact report |
| POST | `/governance/policy-bundles/{id}/activate` | Make candidate active |
| POST | `/governance/policy-bundles/rollback` | Restore last-known-good |

Impact example fields: `allow_to_block`, `allow_to_approval`, `block_to_allow`, …

## Package and push

```bash
POLICY_OCI_REF=ghcr.io/justrunme/ai-policies:dev \
  bash scripts/package_policy_bundle.sh
cosign sign --yes ghcr.io/justrunme/ai-policies:dev
```

Prefer packaging **YAML policy data** (and keep engines in the API image). The
pack script may still include evaluate modules for backwards compatibility; the
API ignores remote engines unless `POLICY_BUNDLE_ALLOW_EXECUTABLE=true`.

## CRD

`AIPolicyBundle` (`infra/crd/ai.justrunme.dev_aipolicybundles.yaml`) declares desired
OCI source + signature requirements. A thin reconciler should:

1. Read CRD
2. Call validate / simulate / activate on Control API
3. Update `status.phase` / `status.observedDigest`

No GPU/workload lifecycle in this controller.
