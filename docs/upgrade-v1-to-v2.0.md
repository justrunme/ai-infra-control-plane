# Upgrade guide: v1.x → v2.0

v2.0 is a **stability major**: CRDs move from `v1alpha1` → `v1`, and the
Supported surface expands to include the closed-loop path built in v1.5–v1.8.
OpenAPI remains backward-compatible with the v1.0.0 baseline (additive only).

## Prerequisites

- Control plane at **v1.8.0** (or any v1.5+ with migrations through `008`)
- Postgres HA for production (`values-production.yaml`)
- OIDC JWT verify enabled for production trust boundary

## Breaking / notable changes

1. **Image/chart tags** → `2.0.0`.
2. **CRDs** use `apiVersion: ai.justrunme.dev/v1` (re-apply manifests).
3. Production defaults expect:
   - `TENANT_ISOLATION=true`
   - `TENANT_JWT_ONLY=true`
   - `QUOTA_ON_UNAVAILABLE=approval_required`
   - OIDC JWT verify on
4. Schema migrations through **`008_capability_contracts`** (additive).

## Recommended steps

1. Backup Postgres (or SQLite PVC for single-node).
2. Apply CRDs:

   ```bash
   kubectl apply -f infra/crd/ai.justrunme.dev_aipolicybundles.yaml
   kubectl apply -f infra/crd/ai.justrunme.dev_aicapabilitycontracts.yaml
   ```

3. Helm upgrade:

   ```bash
   helm upgrade --install ai-control-plane \
     oci://ghcr.io/justrunme/charts/ai-control-plane \
     --version 2.0.0 \
     -f infra/helm/ai-control-plane/values-production.yaml \
     --set persistence.existingSecret=ai-control-plane-database
   ```

4. Verify:

   - `/readyz` → 200
   - `list_schema_migrations` includes `008_capability_contracts` (via store / ops)
   - `GET /governance/policy-bundles` and `GET /registry/capabilities`
   - Optional: `POST /registry/capabilities/sync` then activate

5. Re-point any GitOps samples from `ai.justrunme.dev/v1alpha1` → `/v1`.

## Rollback

Roll image/chart back to `1.8.0`. Additive migrations remain; CRDs may need the
previous `v1alpha1` manifests if controllers still write that version.

## Related

- [Maturity boundary](maturity-boundary.md)
- [API compatibility](api-compatibility.md)
- [Release verification](release-verification.md)
- [ADR 0007](adr/0007-v2-stability-boundary.md)
