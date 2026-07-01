#!/usr/bin/env bash
# Verify the AI Infrastructure OS platform demo end-to-end.
set -euo pipefail

CONTROL_PLANE_URL="${CONTROL_PLANE_URL:-http://127.0.0.1:8091}"
GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8090}"
MODEL="${DEMO_MODEL:-llama3.1:8b}"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-180}"

log() {
  printf '[platform-demo] %s\n' "$*"
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local deadline=$((SECONDS + MAX_WAIT_SECONDS))
  until curl -fsS "$url" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      log "ERROR: timed out waiting for ${name} at ${url}"
      exit 1
    fi
    sleep 2
  done
  log "${name} is ready (${url})"
}

wait_for_url "control plane" "${CONTROL_PLANE_URL}/healthz"
wait_for_url "execution plane gateway" "${GATEWAY_URL}/healthz"

log "governance evaluate — expect allow"
allow_payload="$(curl -fsS -X POST "${CONTROL_PLANE_URL}/governance/evaluate" \
  -H 'content-type: application/json' \
  -d '{
    "team": "platform",
    "owner": "alice",
    "environment": "development",
    "namespace": "ai-dev",
    "model": "'"${MODEL}"'",
    "provider": "ollama",
    "input_tokens": 200,
    "output_tokens": 64,
    "sensitive_data": false
  }')"
printf '%s\n' "$allow_payload" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["final_verdict"]=="allow", d; print("  verdict:", d["final_verdict"])'

log "governance evaluate — expect block (finance + sensitive data)"
block_payload="$(curl -fsS -X POST "${CONTROL_PLANE_URL}/governance/evaluate" \
  -H 'content-type: application/json' \
  -d '{
    "team": "finance",
    "owner": "bob",
    "environment": "development",
    "namespace": "ai-dev",
    "model": "'"${MODEL}"'",
    "provider": "ollama",
    "requests_last_minute": 30,
    "sensitive_data": true
  }')"
printf '%s\n' "$block_payload" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["final_verdict"]=="block", d; print("  verdict:", d["final_verdict"])'

log "runtime enforcement — expect allowed chat completion"
curl -fsS -X POST "${GATEWAY_URL}/v1/chat/completions" \
  -H 'content-type: application/json' \
  -H 'x-ai-team: platform' \
  -H 'x-ai-namespace: ai-dev' \
  -d '{
    "model": "'"${MODEL}"'",
    "messages": [{"role": "user", "content": "Say hello in three words."}],
    "max_tokens": 16
  }' | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "choices" in d, d; print("  completion ok")'

log "runtime enforcement — expect HTTP 403 for finance sensitive request"
status="$(curl -sS -o /tmp/platform-demo-block.json -w '%{http_code}' \
  -X POST "${GATEWAY_URL}/v1/chat/completions" \
  -H 'content-type: application/json' \
  -H 'x-ai-team: finance' \
  -H 'x-ai-sensitive-data: true' \
  -H 'x-ai-requests-last-minute: 30' \
  -d '{
    "model": "'"${MODEL}"'",
    "messages": [{"role": "user", "content": "blocked"}],
    "max_tokens": 8
  }')"
if [[ "$status" != "403" ]]; then
  log "ERROR: expected HTTP 403, got ${status}"
  cat /tmp/platform-demo-block.json
  exit 1
fi
log "  gateway returned 403 as expected"

log "inventory drift check"
drift="$(curl -fsS "${CONTROL_PLANE_URL}/drift")"
printf '%s\n' "$drift" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("  in_sync:", d.get("in_sync"), "drift_count:", len(d.get("drift", [])))'

log "prometheus metrics smoke check"
metrics="$(curl -fsS "${GATEWAY_URL}/metrics")"
echo "$metrics" | grep -q 'gateway_governance_decisions_total' && log "  gateway_governance_decisions_total present"
echo "$metrics" | grep -q 'gateway_tenant_requests_total' && log "  gateway_tenant_requests_total present"
curl -fsS "${CONTROL_PLANE_URL}/metrics" | grep -q 'ai_control_' && log "  control plane metrics present"

log ""
log "Platform demo verification passed."
log "  Control Plane dashboard: ${CONTROL_PLANE_URL}/"
log "  Execution Plane gateway: ${GATEWAY_URL}/v1/chat/completions"
