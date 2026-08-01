# Policy bundles and GitOps (v1.5)

## Sources

| `POLICY_SOURCE_TYPE` | Behavior |
| --- | --- |
| `filesystem` (default) | Load from `GOVERNANCE_ROOT` or `POLICY_SOURCE_PATH` |
| `oci` | `oras pull` + optional `cosign verify` |

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

`POLICY_SOURCE_FAILURE_MODE`:

| Mode | Behavior |
| --- | --- |
| `fail_closed` (production) | Bootstrap error → `/readyz` 503 |
| `last_known_good` (demo default) | Keep previous valid bundle; mark fallback |

Policy lifecycle candidates/active remain **process-local** (Reference for HA)
until durable generations land in v2.1.

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

## CRD

`AIPolicyBundle` (`infra/crd/ai.justrunme.dev_aipolicybundles.yaml`) declares desired
OCI source + signature requirements. A thin reconciler should:

1. Read CRD
2. Call validate / simulate / activate on Control API
3. Update `status.phase` / `status.observedDigest`

No GPU/workload lifecycle in this controller.
