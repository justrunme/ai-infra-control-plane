#!/usr/bin/env bash
# Verify Keycloak OIDC -> JWT -> gateway -> control-plane JWKS flow.
set -euo pipefail

CONTROL_PLANE_URL="${CONTROL_PLANE_URL:-http://127.0.0.1:8091}"
GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8090}"
KEYCLOAK_URL="${KEYCLOAK_URL:-http://127.0.0.1:8180}"
MODEL="${DEMO_MODEL:-llama3.1:8b}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-240}"

log() {
  printf '[oidc-demo] %s\n' "$*"
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
    sleep 3
  done
  log "${name} is ready (${url})"
}

wait_for_url "keycloak" "${KEYCLOAK_URL}/realms/ai-platform"
wait_for_url "control plane" "${CONTROL_PLANE_URL}/healthz"
wait_for_url "gateway" "${GATEWAY_URL}/healthz"

fetch_token() {
  local username="$1"
  OIDC_USERNAME="$username" bash "${SCRIPT_DIR}/fetch-oidc-token.sh"
}

log "alice (platform) — expect gateway allow with verified JWT"
alice_token="$(fetch_token alice)"
curl -fsS -X POST "${GATEWAY_URL}/v1/chat/completions" \
  -H "authorization: Bearer ${alice_token}" \
  -H 'content-type: application/json' \
  -d '{
    "model": "'"${MODEL}"'",
    "messages": [{"role": "user", "content": "Say hello in two words."}],
    "max_tokens": 12
  }' | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "choices" in d, d; print("  completion ok")'

log "bob (finance) via control plane — expect governance block"
bob_token="$(fetch_token bob)"
block_payload="$(curl -fsS -X POST "${CONTROL_PLANE_URL}/governance/evaluate" \
  -H "authorization: Bearer ${bob_token}" \
  -H 'content-type: application/json' \
  -d '{
    "model": "'"${MODEL}"'",
    "provider": "ollama",
    "requests_last_minute": 30,
    "sensitive_data": true
  }')"
printf '%s\n' "$block_payload" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["final_verdict"]=="block", d; print("  verdict:", d["final_verdict"])'

log "audit trail — expect bob block with jwt identity source"
audit_events="$(curl -fsS "${CONTROL_PLANE_URL}/audit/events?team=finance&verdict=block&limit=5")"
printf '%s\n' "$audit_events" | python3 -c 'import json,sys; events=json.load(sys.stdin); assert events, events; e=events[0]; assert e.get("identity_source")=="jwt", e; print("  subject:", e.get("subject"), "source:", e.get("identity_source"))'

log "bob via gateway — expect HTTP 403"
status="$(curl -sS -o /tmp/oidc-demo-block.json -w '%{http_code}' \
  -X POST "${GATEWAY_URL}/v1/chat/completions" \
  -H "authorization: Bearer ${bob_token}" \
  -H 'content-type: application/json' \
  -H 'x-ai-sensitive-data: true' \
  -H 'x-ai-requests-last-minute: 30' \
  -d '{
    "model": "'"${MODEL}"'",
    "messages": [{"role": "user", "content": "blocked"}],
    "max_tokens": 8
  }')"
if [[ "$status" != "403" ]]; then
  log "ERROR: expected HTTP 403, got ${status}"
  cat /tmp/oidc-demo-block.json
  exit 1
fi
log "  gateway returned 403 as expected"

log ""
log "OIDC platform demo verification passed."
log "  Keycloak admin: ${KEYCLOAK_URL}"
log "  Fetch token: OIDC_USERNAME=alice bash demo/platform/fetch-oidc-token.sh"
