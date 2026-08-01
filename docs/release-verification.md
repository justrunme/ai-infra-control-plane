# Release verification

Checklist for publishing a stable Control Plane release.

## Preconditions

- [ ] CI green on the merge commit (`test`, `postgres`, `e2e-kind`, `e2e-kind-postgres`, OpenAPI freeze + breaking check)
- [ ] Chart `version` / `appVersion` and image `tag` match the release
- [ ] `apps/control-api/openapi.json` regenerated and committed
- [ ] Roadmap / changelog notes describe user-visible changes

## Publish

```bash
git tag -a vX.Y.Z -m "vX.Y.Z — <title>"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z — <title>" --notes-file /tmp/notes.md
```

The Release workflow then:

1. Builds and pushes `ghcr.io/justrunme/ai-infra-control-plane:X.Y.Z` (and floating tags)
2. Generates SBOM + cosign signature
3. Packages and pushes the Helm chart to `oci://ghcr.io/justrunme/charts/ai-control-plane`

## Verify artifacts

```bash
# Image
docker pull ghcr.io/justrunme/ai-infra-control-plane:X.Y.Z

# Chart (after tag release)
helm pull oci://ghcr.io/justrunme/charts/ai-control-plane --version X.Y.Z
helm template ai-control-plane oci://ghcr.io/justrunme/charts/ai-control-plane --version X.Y.Z \
  -f infra/helm/ai-control-plane/values-production.yaml >/dev/null
```

Install example:

```bash
helm upgrade --install ai-control-plane \
  oci://ghcr.io/justrunme/charts/ai-control-plane \
  --version X.Y.Z \
  -f infra/helm/ai-control-plane/values-production.yaml \
  --set persistence.existingSecret=ai-control-plane-database
```

## Contract checks

```bash
PYTHONPATH=apps/control-api python scripts/check_openapi_freeze.py
bash scripts/check_openapi_breaking.sh   # vs OPENAPI_BASELINE_TAG (default v1.0.0)
bash scripts/helm_package_smoke.sh
```

Breaking OpenAPI changes require a major version and `ALLOW_OPENAPI_BREAKING=1` in CI for that PR only, with an updated baseline tag policy.
