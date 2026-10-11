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

echo "==> redis-down fail-closed (QUOTA_ON_UNAVAILABLE unset)"
REDIS_DOWN_NAME="${NAME}-quota-down"
docker rm -f "${REDIS_DOWN_NAME}" >/dev/null 2>&1 || true
# QUOTA_ON_UNAVAILABLE intentionally unset — must fail closed (not allow).
docker run -d --name "${REDIS_DOWN_NAME}" \
  -p "$((PORT + 1)):8080" \
  -e DATABASE_URL="sqlite:////tmp/control-plane.db" \
  -e HTTP_TRUST_ENV=false \
  -e QUOTA_REDIS_URL="redis://127.0.0.1:1/0" \
  "${IMAGE}" >/dev/null
cleanup_redis_down() {
  docker rm -f "${REDIS_DOWN_NAME}" >/dev/null 2>&1 || true
}
trap 'cleanup_redis_down; cleanup' EXIT

DOWN_BASE="http://127.0.0.1:$((PORT + 1))"
for _ in $(seq 1 60); do
  if curl -fsS "${DOWN_BASE}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
DOWN_EVAL="$(curl -fsS -X POST "${DOWN_BASE}/governance/evaluate" \
  -H 'content-type: application/json' \
  -d '{"team":"platform","owner":"alice","environment":"development","namespace":"ai-dev","action":"invoke_model","model":"llama3.1:8b","provider":"ollama"}')"
echo "${DOWN_EVAL}" | grep -q '"final_verdict":"approval_required"'
if echo "${DOWN_EVAL}" | grep -q '"final_verdict":"allow"'; then
  echo "ERROR: redis-down evaluate must not allow when QUOTA_ON_UNAVAILABLE is unset" >&2
  echo "${DOWN_EVAL}" >&2
  exit 1
fi
cleanup_redis_down
trap cleanup EXIT

echo "==> compose e2e passed"
