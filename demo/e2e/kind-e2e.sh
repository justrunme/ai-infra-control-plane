#!/usr/bin/env bash
# Kind e2e: install Helm chart, prove allow/block/approval + PVC restart persistence.
# Set SKIP_CLUSTER_CREATE=1 when the cluster already exists (CI kind-action).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-ai-cp-e2e}"
NAMESPACE="${NAMESPACE:-ai-control-e2e}"
RELEASE="${RELEASE:-ai-control-plane}"
IMAGE_REPO="${IMAGE_REPO:-ai-infra-control-plane}"
IMAGE_TAG="${IMAGE_TAG:-e2e}"
TIMEOUT="${TIMEOUT:-180s}"
ARGOCD_VERSION="${ARGOCD_VERSION:-v2.13.4}"

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

echo "==> install Argo CD"
kubectl create namespace argocd || true
kubectl apply -n argocd -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"
kubectl -n argocd wait --for=condition=available --timeout=300s deploy/argocd-server

echo "==> build and load image"
docker build -f "${ROOT}/apps/control-api/Dockerfile" -t "${IMAGE_REPO}:${IMAGE_TAG}" "${ROOT}"
kind load docker-image "${IMAGE_REPO}:${IMAGE_TAG}" --name "${CLUSTER_NAME}"

echo "==> helm install"
kubectl get ns "${NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${NAMESPACE}"
helm upgrade --install "${RELEASE}" "${ROOT}/infra/helm/ai-control-plane" \
  --namespace "${NAMESPACE}" \
  --set image.repository="${IMAGE_REPO}" \
  --set image.tag="${IMAGE_TAG}" \
  --set image.pullPolicy=Never \
  --set autoscaling.enabled=false \
  --set replicaCount=1 \
  --set persistence.enabled=true \
  --set persistence.size=1Gi \
  --set persistence.databaseUrl="sqlite:////var/lib/ai-control-plane/control-plane.db" \
  --set ollama.baseUrl="http://127.0.0.1:11434" \
  --set vllm.baseUrl="http://127.0.0.1:8000" \
  --wait --timeout "${TIMEOUT}"

kubectl -n "${NAMESPACE}" rollout status "deploy/${RELEASE}-ai-control-plane" --timeout="${TIMEOUT}"

echo "==> create Argo CD Application for demo workload"
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ai-control-plane-demo
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/justrunme/ai-infra-control-plane.git
    targetRevision: HEAD
    path: infra/helm/ai-control-plane
    helm:
      parameters:
      - name: image.repository
        value: "${IMAGE_REPO}"
      - name: image.tag
        value: "${IMAGE_TAG}"
      - name: image.pullPolicy
        value: Never
      - name: autoscaling.enabled
        value: "false"
      - name: replicaCount
        value: "1"
  destination:
    server: https://kubernetes.default.svc
    namespace: ${NAMESPACE}
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
EOF

echo "==> wait for Argo CD sync"
kubectl -n argocd wait --for=condition=SyncStatusCode=Synced --timeout=60s app/ai-control-plane-demo || true

echo "==> port-forward"
kubectl -n "${NAMESPACE}" port-forward "svc/${RELEASE}-ai-control-plane" 18080:80 >/tmp/ai-cp-pf.log 2>&1 &
PF_PID=$!
sleep 3

BASE="http://127.0.0.1:18080"
curl -fsS "${BASE}/healthz" >/dev/null

echo "==> allow path"
ALLOW="$(curl -fsS -X POST "${BASE}/governance/evaluate" \
  -H 'content-type: application/json' \
  -d '{"team":"platform","owner":"alice","environment":"development","namespace":"ai-dev","action":"invoke_model","model":"llama3.1:8b","provider":"ollama"}')"
echo "${ALLOW}" | grep -q '"final_verdict":"allow"'
DECISION_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["decision_id"])' <<<"${ALLOW}")"
test -n "${DECISION_ID}"

echo "==> block path"
BLOCK="$(curl -fsS -X POST "${BASE}/governance/evaluate" \
  -H 'content-type: application/json' \
  -d '{"team":"platform","owner":"alice","environment":"development","namespace":"ai-dev","action":"invoke_model","model":"unknown-frontier-model","provider":"external"}')"
echo "${BLOCK}" | grep -q '"final_verdict":"block"'

echo "==> approval lifecycle"
NEED="$(curl -fsS -X POST "${BASE}/governance/evaluate" \
  -H 'content-type: application/json' \
  -d '{"team":"platform","owner":"alice","environment":"production","namespace":"ai-prod","action":"invoke_model","model":"llama3.1:8b","provider":"ollama","tool_access":true,"write_permission":true,"forecast_monthly_cost_usd":300}')"
echo "${NEED}" | grep -q '"final_verdict":"approval_required"'
APPROVAL_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["approval_id"])' <<<"${NEED}")"
curl -fsS -X POST "${BASE}/approvals/${APPROVAL_ID}/approve" \
  -H 'content-type: application/json' \
  -d '{"reviewer":"secops","comment":"e2e"}' | grep -q '"status":"approved"'

echo "==> verify Argo CD sync status"
SYNC_STATUS="$(kubectl -n argocd get app ai-control-plane-demo -o jsonpath='{.status.sync.status}')"
HEALTH_STATUS="$(kubectl -n argocd get app ai-control-plane-demo -o jsonpath='{.status.health.status}')"
echo "Argo CD sync status: ${SYNC_STATUS}, health: ${HEALTH_STATUS}"
if [[ "${SYNC_STATUS}" != "Synced" ]]; then
  echo "ERROR: Expected Synced status, got ${SYNC_STATUS}"
  exit 1
fi
if [[ "${HEALTH_STATUS}" != "Healthy" ]]; then
  echo "ERROR: Expected Healthy status, got ${HEALTH_STATUS}"
  exit 1
fi

echo "==> restart pod and prove decision persistence"
kubectl -n "${NAMESPACE}" delete pod -l "app.kubernetes.io/instance=${RELEASE}" --wait=true
kubectl -n "${NAMESPACE}" rollout status "deploy/${RELEASE}-ai-control-plane" --timeout="${TIMEOUT}"
kill "${PF_PID}" >/dev/null 2>&1 || true
kubectl -n "${NAMESPACE}" port-forward "svc/${RELEASE}-ai-control-plane" 18080:80 >/tmp/ai-cp-pf.log 2>&1 &
PF_PID=$!
sleep 4

curl -fsS "${BASE}/governance/decisions/${DECISION_ID}" | grep -q '"final_verdict":"allow"'
curl -fsS "${BASE}/approvals/${APPROVAL_ID}" | grep -q '"status":"approved"'

kill "${PF_PID}" >/dev/null 2>&1 || true
echo "==> kind e2e passed (Argo CD sync: ${SYNC_STATUS}/${HEALTH_STATUS})"
