#!/usr/bin/env bash
# Verify Redis-backed quota state and Prometheus governance inputs.
set -euo pipefail

CONTROL_PLANE_URL="${CONTROL_PLANE_URL:-http://127.0.0.1:8091}"
GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8090}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://127.0.0.1:9090}"
MODEL="${DEMO_MODEL:-llama3.1:8b}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-180}"

log() {
  printf '[production-demo] %s\n' "$*"
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
wait_for_url "prometheus" "${PROMETHEUS_URL}/-/ready"

log "governance inputs — expect Redis quota backend"
inputs_status="$(curl -fsS "${CONTROL_PLANE_URL}/governance/inputs/status")"
printf '%s\n' "$inputs_status" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["quota"]["enabled"], d; assert d["quota"]["backend"]=="redis", d; print("  quota backend:", d["quota"]["backend"])'

log "governance inputs — expect Prometheus enabled"
printf '%s\n' "$inputs_status" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["prometheus"]["enabled"], d; print("  prometheus url:", d["prometheus"].get("url"))'

log "prometheus targets — expect gateway and control-api up"
targets="$(curl -fsS "${PROMETHEUS_URL}/api/v1/targets")"
printf '%s\n' "$targets" | python3 -c 'import json,sys; d=json.load(sys.stdin); names={t["labels"].get("job") for t in d["data"]["activeTargets"]}; assert "execution-plane-gateway" in names, names; assert "control-plane-api" in names, names; print("  jobs:", sorted(names))'

log "seed Redis tenant counters via gateway (finance team)"
for _ in 1 2 3; do
  curl -sS -o /dev/null -X POST "${GATEWAY_URL}/v1/chat/completions" \
    -H 'content-type: application/json' \
    -H 'x-ai-team: finance' \
    -H 'x-ai-namespace: ai-dev' \
    -d '{
      "model": "'"${MODEL}"'",
      "messages": [{"role": "user", "content": "quota seed"}],
      "max_tokens": 4
    }' || true
done

log "governance evaluate — expect Redis backfill in telemetry"
redis_eval="$(curl -fsS -X POST "${CONTROL_PLANE_URL}/governance/evaluate" \
  -H 'content-type: application/json' \
  -d '{
    "team": "finance",
    "owner": "bob",
    "environment": "development",
    "namespace": "ai-dev",
    "model": "'"${MODEL}"'",
    "provider": "ollama",
    "requests_last_minute": 0,
    "tokens_today": 0,
    "sensitive_data": false
  }')"
printf '%s\n' "$redis_eval" | python3 -c 'import json,sys; d=json.load(sys.stdin); t=d.get("telemetry") or {}; assert t.get("quota_source")=="redis", d; assert t.get("requests_last_minute",0)>=1, d; print("  quota_source:", t.get("quota_source"), "rpm:", t.get("requests_last_minute"))'

log "governance evaluate — expect prometheus telemetry attached"
printf '%s\n' "$redis_eval" | python3 -c 'import json,sys; d=json.load(sys.stdin); t=d.get("telemetry") or {}; assert t.get("prometheus_enabled") is True, d; print("  prometheus_enabled:", t.get("prometheus_enabled"))'

log ""
log "Production overlay checks passed. Running full platform verification..."
bash "${SCRIPT_DIR}/verify-demo.sh"

log ""
log "Production demo verification passed."
log "  Prometheus UI: ${PROMETHEUS_URL}"
log "  Redis: redis://127.0.0.1:6379/0"
