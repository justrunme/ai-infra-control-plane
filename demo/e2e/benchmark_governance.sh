#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_URL="${TARGET_URL:-}"
REQUESTS="${REQUESTS:-300}"
CONCURRENCY="${CONCURRENCY:-10}"
P95_MAX_MS="${P95_MAX_MS:-250}"
PORT="${PORT:-18091}"
DB_PATH="${DB_PATH:-}"
STARTED_SERVER=0
PID=""

cleanup() {
  if [[ "${STARTED_SERVER}" == "1" && -n "${PID}" ]]; then
    kill "${PID}" 2>/dev/null || true
    wait "${PID}" 2>/dev/null || true
  fi
  if [[ -n "${DB_PATH}" && -f "${DB_PATH}" ]]; then
    rm -f "${DB_PATH}" "${DB_PATH}-wal" "${DB_PATH}-shm" || true
  fi
}
trap cleanup EXIT

if [[ -z "${TARGET_URL}" ]]; then
  DB_PATH="$(mktemp -t ai-cp-bench-XXXXXX.db)"
  export DATABASE_URL="sqlite:///${DB_PATH}"
  export HTTP_TRUST_ENV=false
  cd "${ROOT}/apps/control-api"
  PYTHONPATH=. python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT}" >/tmp/ai-cp-bench-uvicorn.log 2>&1 &
  PID=$!
  STARTED_SERVER=1
  TARGET_URL="http://127.0.0.1:${PORT}/governance/evaluate"

  for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done
  curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null
fi

python3 "${ROOT}/demo/e2e/benchmark_governance.py" \
  --url "${TARGET_URL}" \
  --requests "${REQUESTS}" \
  --concurrency "${CONCURRENCY}" \
  --p95-max-ms "${P95_MAX_MS}"
