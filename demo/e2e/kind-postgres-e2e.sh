#!/usr/bin/env bash
# Kind e2e: PostgreSQL + 2 control-plane replicas, prove evaluate + failover.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-ai-cp-pg-e2e}"
NAMESPACE="${NAMESPACE:-ai-control-pg-e2e}"
RELEASE="${RELEASE:-ai-control-plane}"
IMAGE_REPO="${IMAGE_REPO:-ai-infra-control-plane}"
IMAGE_TAG="${IMAGE_TAG:-e2e-pg}"
TIMEOUT="${TIMEOUT:-240s}"
DB_SECRET="ai-control-plane-database"
DB_URL="postgresql://ai_control:ai_control@postgres:5432/ai_control"

cleanup() {
  if [[ "${SKIP_CLUSTER_CREATE:-0}" != "1" && "${KEEP_CLUSTER:-0}" != "1" ]]; then
    kind delete cluster --name "${CLUSTER_NAME}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ "${SKIP_CLUSTER_CREATE:-0}" != "1" ]]; then
  echo "==> create kind cluster ${CLUSTER_NAME}"
  kind delete cluster --name "${CLUSTER_NAME}" >/dev/null 2>&1 || true
  kind create cluster --name "${CLUSTER_NAME}" --wait 120s
fi

echo "==> build and load image"
docker build -f "${ROOT}/apps/control-api/Dockerfile" -t "${IMAGE_REPO}:${IMAGE_TAG}" "${ROOT}"
kind load docker-image "${IMAGE_REPO}:${IMAGE_TAG}" --name "${CLUSTER_NAME}"

echo "==> namespace + postgres"
kubectl get ns "${NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${NAMESPACE}"
kubectl -n "${NAMESPACE}" apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: ${DB_SECRET}
type: Opaque
stringData:
  DATABASE_URL: ${DB_URL}
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
spec:
  ports:
    - port: 5432
  selector:
    app: postgres
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16
          env:
            - name: POSTGRES_USER
              value: ai_control
            - name: POSTGRES_PASSWORD
              value: ai_control
            - name: POSTGRES_DB
              value: ai_control
          ports:
            - containerPort: 5432
          readinessProbe:
            exec:
              command: ["pg_isready", "-U", "ai_control", "-d", "ai_control"]
            initialDelaySeconds: 3
            periodSeconds: 5
EOF
kubectl -n "${NAMESPACE}" rollout status deploy/postgres --timeout="${TIMEOUT}"

echo "==> helm install (2 replicas, postgres secret)"
helm upgrade --install "${RELEASE}" "${ROOT}/infra/helm/ai-control-plane" \
  --namespace "${NAMESPACE}" \
  --set image.repository="${IMAGE_REPO}" \
  --set image.tag="${IMAGE_TAG}" \
  --set image.pullPolicy=Never \
  --set autoscaling.enabled=false \
  --set replicaCount=2 \
  --set persistence.enabled=true \
  --set persistence.size="" \
  --set persistence.existingSecret="${DB_SECRET}" \
  --set persistence.databaseUrlKey=DATABASE_URL \
  --set persistence.databaseUrl="" \
  --set oidc.jwtVerify=false \
  --set ollama.baseUrl="http://127.0.0.1:11434" \
  --set vllm.baseUrl="http://127.0.0.1:8000" \
  --wait --timeout "${TIMEOUT}"

kubectl -n "${NAMESPACE}" rollout status "deploy/${RELEASE}-ai-control-plane" --timeout="${TIMEOUT}"
kubectl -n "${NAMESPACE}" wait --for=condition=ready pod \
  -l "app.kubernetes.io/instance=${RELEASE}" --timeout="${TIMEOUT}"

BASE="http://127.0.0.1:18081"
PF_PID=""

start_port_forward() {
  if [[ -n "${PF_PID}" ]]; then
    kill "${PF_PID}" >/dev/null 2>&1 || true
    wait "${PF_PID}" >/dev/null 2>&1 || true
    PF_PID=""
  fi
  # Drop stale listeners from a previous forward after endpoint churn.
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:18081 -sTCP:LISTEN 2>/dev/null | xargs kill >/dev/null 2>&1 || true
  fi
  kubectl -n "${NAMESPACE}" port-forward "svc/${RELEASE}-ai-control-plane" 18081:80 >/tmp/ai-cp-pg-pf.log 2>&1 &
  PF_PID=$!
}

wait_http() {
  local url="$1"
  local attempts="${2:-30}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "timed out waiting for ${url}" >&2
  cat /tmp/ai-cp-pg-pf.log >&2 || true
  return 1
}

echo "==> port-forward"
start_port_forward
wait_http "${BASE}/readyz"

ALLOW="$(curl -fsS -X POST "${BASE}/governance/evaluate" \
  -H 'content-type: application/json' \
  -d '{"team":"platform","owner":"alice","environment":"development","namespace":"ai-dev","action":"invoke_model","model":"llama3.1:8b","provider":"ollama"}')"
echo "${ALLOW}" | grep -q '"final_verdict":"allow"'
DECISION_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["decision_id"])' <<<"${ALLOW}")"

echo "==> delete one replica and prove shared postgres state"
POD="$(kubectl -n "${NAMESPACE}" get pod -l "app.kubernetes.io/instance=${RELEASE}" -o jsonpath='{.items[0].metadata.name}')"
kubectl -n "${NAMESPACE}" delete pod "${POD}" --wait=true
kubectl -n "${NAMESPACE}" rollout status "deploy/${RELEASE}-ai-control-plane" --timeout="${TIMEOUT}"
kubectl -n "${NAMESPACE}" wait --for=condition=ready pod \
  -l "app.kubernetes.io/instance=${RELEASE}" --timeout="${TIMEOUT}"

# Service endpoints changed; restart forward so curl is not stuck on a dead stream.
start_port_forward
wait_http "${BASE}/readyz"
curl -fsS "${BASE}/governance/decisions/${DECISION_ID}" | grep -q '"final_verdict":"allow"'
curl -fsS "${BASE}/readyz" >/dev/null

kill "${PF_PID}" >/dev/null 2>&1 || true
echo "==> kind postgres e2e passed"
