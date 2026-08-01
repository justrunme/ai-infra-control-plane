#!/usr/bin/env bash
# Fail when committed OpenAPI introduces breaking changes vs the v1 baseline tag.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASELINE_TAG="${OPENAPI_BASELINE_TAG:-v1.0.0}"
OASDIFF_VERSION="${OASDIFF_VERSION:-1.27.0}"
CURRENT="${ROOT}/apps/control-api/openapi.json"
BASELINE_FILE="${OPENAPI_BASELINE_FILE:-}"

if [[ "${ALLOW_OPENAPI_BREAKING:-0}" == "1" ]]; then
  echo "ALLOW_OPENAPI_BREAKING=1 set; skipping breaking-change check"
  exit 0
fi

if [[ ! -f "${CURRENT}" ]]; then
  echo "missing ${CURRENT}" >&2
  exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

if [[ -n "${BASELINE_FILE}" ]]; then
  cp "${BASELINE_FILE}" "${tmp}/baseline.json"
else
  git -C "${ROOT}" fetch --tags --force origin "${BASELINE_TAG}" >/dev/null 2>&1 || true
  git -C "${ROOT}" show "${BASELINE_TAG}:apps/control-api/openapi.json" >"${tmp}/baseline.json"
fi

os="$(uname -s | tr '[:upper:]' '[:lower:]')"
arch="$(uname -m)"
case "${arch}" in
  x86_64|amd64) arch="amd64" ;;
  aarch64|arm64) arch="arm64" ;;
esac
if [[ "${os}" == "darwin" ]]; then
  archive="oasdiff_${OASDIFF_VERSION}_darwin_all.tar.gz"
else
  archive="oasdiff_${OASDIFF_VERSION}_${os}_${arch}.tar.gz"
fi

curl -fsSL \
  "https://github.com/Tufin/oasdiff/releases/download/v${OASDIFF_VERSION}/${archive}" \
  | tar -xz -C "${tmp}" oasdiff

echo "Checking OpenAPI breaking changes against ${BASELINE_TAG}"
"${tmp}/oasdiff" breaking "${tmp}/baseline.json" "${CURRENT}"
echo "OpenAPI is backward-compatible with ${BASELINE_TAG}"
