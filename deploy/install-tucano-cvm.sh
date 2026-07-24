#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_DIR="${ROOT_DIR}/deploy/helm/tucano-cvm"

NAMESPACE="${NAMESPACE:-tucano-services}"
RELEASE_NAME="${RELEASE_NAME:-tucano-cvm}"
APP_SECRET_NAME="${APP_SECRET_NAME:-cvm-secret}"
ARGO_ROLLOUTS_NAMESPACE="${ARGO_ROLLOUTS_NAMESPACE:-argo-rollouts}"
INSTALL_ARGO_ROLLOUTS="${INSTALL_ARGO_ROLLOUTS:-true}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-10m}"
HELM_WAIT="${HELM_WAIT:-false}"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-registry.beakcloud.com/tucano-cvm}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
HTTPPROXY_ENABLED="${HTTPPROXY_ENABLED:-true}"
HTTPPROXY_FQDN="${HTTPPROXY_FQDN:-cvm.tucano.beakcloud.com}"
HTTPPROXY_TLS_ENABLED="${HTTPPROXY_TLS_ENABLED:-true}"
HTTPPROXY_TLS_SECRET_NAME="${HTTPPROXY_TLS_SECRET_NAME:-tucano-cvm-tls}"
CERT_MANAGER_ENABLED="${CERT_MANAGER_ENABLED:-false}"
ENABLE_METRICS="${ENABLE_METRICS:-false}"
SERVICE_TYPE="${SERVICE_TYPE:-ClusterIP}"
SERVICE_PORT="${SERVICE_PORT:-8110}"
NODE_PORT="${NODE_PORT:-}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required" >&2
  exit 1
fi

if ! command -v helm >/dev/null 2>&1; then
  echo "helm is required" >&2
  exit 1
fi

if [[ ! -d "${CHART_DIR}" ]]; then
  echo "Missing Helm chart: ${CHART_DIR}" >&2
  exit 1
fi

echo "==> Ensuring namespace ${NAMESPACE}"
kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${NAMESPACE}"

if [[ "${INSTALL_ARGO_ROLLOUTS}" == "true" ]]; then
  echo "==> Ensuring Argo Rollouts namespace ${ARGO_ROLLOUTS_NAMESPACE}"
  kubectl get namespace "${ARGO_ROLLOUTS_NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${ARGO_ROLLOUTS_NAMESPACE}"

  echo "==> Installing or updating Argo Rollouts controller"
  kubectl apply -n "${ARGO_ROLLOUTS_NAMESPACE}" -f \
    "https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml"
fi

if ! kubectl get crd rollouts.argoproj.io >/dev/null 2>&1; then
  echo "Argo Rollouts CRD rollouts.argoproj.io is not installed" >&2
  exit 1
fi

if ! kubectl -n "${NAMESPACE}" get secret "${APP_SECRET_NAME}" >/dev/null 2>&1; then
  echo "Required Kubernetes Secret ${APP_SECRET_NAME} was not found in namespace ${NAMESPACE}." >&2
  echo "Please create it before running this install script." >&2
  exit 1
fi

if ! kubectl -n "${NAMESPACE}" get secret "${APP_SECRET_NAME}" -o jsonpath='{.data.MCP_TOKEN}' | grep -q .; then
  cat >&2 <<EOF
Required key MCP_TOKEN was not found in Kubernetes Secret ${APP_SECRET_NAME}.
Create or patch it before deploying the public MCP endpoint, for example:

kubectl -n ${NAMESPACE} patch secret ${APP_SECRET_NAME} \\
  --type='merge' \\
  -p '{"stringData":{"MCP_TOKEN":"<long-random-token>"}}'
EOF
  exit 1
fi

if ! kubectl -n "${NAMESPACE}" get secret registry-cred >/dev/null 2>&1; then
  cat >&2 <<EOF
registry-cred is not present in the target namespace.
Create it before continuing, for example:

kubectl -n ${NAMESPACE} create secret docker-registry registry-cred \
  --docker-server=registry.beakcloud.com \
  --docker-username='<user>' \
  --docker-password='<password>'
EOF
  exit 1
fi

HELM_ARGS=(
  upgrade
  --install "${RELEASE_NAME}" "${CHART_DIR}"
  --namespace "${NAMESPACE}"
  --create-namespace
  --timeout "${WAIT_TIMEOUT}"
  --set "rollout.type=argo-rollout"
  --set "image.repository=${IMAGE_REPOSITORY}"
  --set "image.tag=${IMAGE_TAG}"
  --set "appSecret.name=${APP_SECRET_NAME}"
  --set "env.ENABLE_PROMETHEUS_METRICS=${ENABLE_METRICS}"
  --set "service.type=${SERVICE_TYPE}"
  --set "service.port=${SERVICE_PORT}"
  --set "httpProxy.enabled=${HTTPPROXY_ENABLED}"
  --set "httpProxy.fqdn=${HTTPPROXY_FQDN}"
  --set "httpProxy.tls.enabled=${HTTPPROXY_TLS_ENABLED}"
  --set "httpProxy.tls.secretName=${HTTPPROXY_TLS_SECRET_NAME}"
  --set "certManager.enabled=${CERT_MANAGER_ENABLED}"
)

if [[ -n "${NODE_PORT}" && "${SERVICE_TYPE}" == "NodePort" ]]; then
  HELM_ARGS+=(--set "service.nodePort=${NODE_PORT}")
fi

if [[ "${HELM_WAIT}" == "true" ]]; then
  HELM_ARGS+=(--wait)
fi

echo "==> Deploying ${RELEASE_NAME} with Argo Rollouts enabled"
helm "${HELM_ARGS[@]}"

echo "==> Current resources"
kubectl -n "${NAMESPACE}" get all

echo "==> Rollout resource"
kubectl -n "${NAMESPACE}" get rollouts.argoproj.io "${RELEASE_NAME}" --request-timeout=15s || true

if command -v kubectl-argo-rollouts >/dev/null 2>&1; then
  echo "==> Argo Rollout status"
  kubectl-argo-rollouts -n "${NAMESPACE}" get rollout "${RELEASE_NAME}" --watch=false || true
else
  echo "==> Argo Rollouts plugin not found; skipping rollout CLI status"
fi

cat <<EOF

Install completed.

Namespace: ${NAMESPACE}
Release:   ${RELEASE_NAME}
Chart:     ${CHART_DIR}

Useful commands:
  kubectl -n ${NAMESPACE} get svc ${RELEASE_NAME}
  kubectl -n ${NAMESPACE} get rollout ${RELEASE_NAME}
  kubectl -n ${NAMESPACE} get pods
  helm -n ${NAMESPACE} status ${RELEASE_NAME}

Expected service exposure:
  Service Type:   ${SERVICE_TYPE}
  HTTPProxy FQDN: ${HTTPPROXY_FQDN} (TLS: ${HTTPPROXY_TLS_ENABLED})
  MCP Endpoint:   https://${HTTPPROXY_FQDN}/mcp
EOF
