#!/usr/bin/env bash
# Apply Supported v2 CRDs for the AI Infrastructure Control Plane.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

kubectl apply -f "${ROOT}/infra/crd/ai.justrunme.dev_aipolicybundles.yaml"
kubectl apply -f "${ROOT}/infra/crd/ai.justrunme.dev_aicapabilitycontracts.yaml"

echo "Installed CRDs:"
kubectl get crd aipolicybundles.ai.justrunme.dev aicapabilitycontracts.ai.justrunme.dev
