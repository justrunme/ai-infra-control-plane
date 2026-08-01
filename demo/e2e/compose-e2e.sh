#!/usr/bin/env bash
# Compose e2e: control-api only — allow/block/approval + container restart persistence.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE="${IMAGE:-ai-infra-control-plane:e2e}"
NAME="${NAME:-ai-cp-compose-e2e}"
PORT="${PORT:-18081}"
DATA_DIR="$(mktemp -d)"
chmod 777 "${DATA_DIR}"

cleanup() {
  docker rm -f "${NAME}" >/dev/null 2>&1 || true
  rm -rf "${DATA_DIR}"
}
trap cleanup EXIT

echo "==> build image"
docker build -f "${ROOT}/apps/control-api/Dockerfile" -t "${IMAGE}" "${ROOT}"

echo "==> run control-api with durable volume"
docker run -d --name "${NAME}" \
  -p "${PORT}:8080" \
  -v "${DATA_DIR}:/var/lib/ai-control-plane" \
  -e DATABASE_URL="sqlite:////var/lib/ai-control-plane/control-plane.db" \
  -e HTTP_TRUST_ENV=false \
  "${IMAGE}"

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null; then
  echo "control-api failed to become healthy" >&2
  docker logs "${NAME}" >&2 || true
  exit 1
fi
BASE="http://127.0.0.1:${PORT}"

echo "==> allow"
if ! ALLOW="$(curl -fsS -X POST "${BASE}/governance/evaluate" \
  -H 'content-type: application/json' \
  -d '{"team":"platform","owner":"alice","environment":"development","namespace":"ai-dev","action":"invoke_model","model":"llama3.1:8b","provider":"ollama"}')"; then
  docker logs "${NAME}" >&2 || true
  exit 1
fi
echo "${ALLOW}" | grep -q '"final_verdict":"allow"'
DECISION_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["decision_id"])' <<<"${ALLOW}")"

echo "==> block"
BLOCK="$(curl -fsS -X POST "${BASE}/governance/evaluate" \
  -H 'content-type: application/json' \
  -d '{"team":"platform","owner":"alice","environment":"development","namespace":"ai-dev","action":"invoke_model","model":"unknown-frontier-model","provider":"external"}')"
echo "${BLOCK}" | grep -q '"final_verdict":"block"'

echo "==> approval"
NEED="$(curl -fsS -X POST "${BASE}/governance/evaluate" \
  -H 'content-type: application/json' \
  -d '{"team":"platform","owner":"alice","environment":"production","namespace":"ai-prod","action":"invoke_model","model":"llama3.1:8b","provider":"ollama","tool_access":true,"write_permission":true,"forecast_monthly_cost_usd":300}')"
echo "${NEED}" | grep -q '"final_verdict":"approval_required"'
APPROVAL_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["approval_id"])' <<<"${NEED}")"
curl -fsS -X POST "${BASE}/approvals/${APPROVAL_ID}/approve" \
  -H 'content-type: application/json' \
  -d '{"reviewer":"secops","comment":"compose-e2e"}' | grep -q '"status":"approved"'

echo "==> restart container and verify persistence"
docker restart "${NAME}" >/dev/null
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl -fsS "${BASE}/governance/decisions/${DECISION_ID}" | grep -q '"final_verdict":"allow"'
curl -fsS "${BASE}/approvals/${APPROVAL_ID}" | grep -q '"status":"approved"'
echo "==> compose e2e passed"
