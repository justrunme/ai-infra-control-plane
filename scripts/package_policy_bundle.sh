#!/usr/bin/env bash
# Package governance policy tree for OCI distribution (oras push).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-/tmp/ai-policy-bundle}"
REF="${POLICY_OCI_REF:-}"

rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}/governance"
# Prefer YAML policy data. evaluate.py modules may be included for compatibility;
# the control plane loads engines from its shipped image unless
# POLICY_BUNDLE_ALLOW_EXECUTABLE=true.
rsync -a --exclude 'results' --exclude '__pycache__' \
  "${ROOT}/governance/" "${OUT_DIR}/governance/"

echo "Packed policy data tree at ${OUT_DIR}/governance"
if [[ -n "${REF}" ]]; then
  if ! command -v oras >/dev/null 2>&1; then
    echo "oras not installed; skip push" >&2
    exit 0
  fi
  (
    cd "${OUT_DIR}"
    oras push "${REF}" \
      --artifact-type application/vnd.justrunme.ai.policy.v1+tar \
      governance/:application/vnd.justrunme.ai.policy.layer.v1+tar
  )
  echo "Pushed ${REF}"
fi
