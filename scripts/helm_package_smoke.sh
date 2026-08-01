#!/usr/bin/env bash
# Package the chart and render manifests from the packaged artifact (not checkout path).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_DIR="${ROOT}/infra/helm/ai-control-plane"
OUT_DIR="${HELM_PACKAGE_DIR:-$(mktemp -d)}"

mkdir -p "${OUT_DIR}"
echo "==> helm lint"
helm lint "${CHART_DIR}"

echo "==> helm package"
pkg="$(helm package "${CHART_DIR}" -d "${OUT_DIR}" | awk '/Successfully packaged chart and saved it to:/{print $NF}')"
echo "package=${pkg}"

echo "==> helm template from package (defaults)"
helm template ai-control-plane "${pkg}" >/dev/null

echo "==> helm template from package (production profile)"
helm template ai-control-plane "${pkg}" \
  -f "${CHART_DIR}/values-production.yaml" >/dev/null

echo "==> helm template from package (single-node profile)"
helm template ai-control-plane "${pkg}" \
  -f "${CHART_DIR}/values-single-node.yaml" >/dev/null

echo "Helm package smoke passed: ${pkg}"
