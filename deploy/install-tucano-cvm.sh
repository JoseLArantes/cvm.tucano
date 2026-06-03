#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_DIR="${ROOT_DIR}/deploy/helm/tucano-cvm"
SECRET_FILE="${ROOT_DIR}/secrets.yaml"

NAMESPACE="${NAMESPACE:-tucano-services}"
RELEASE_NAME="${RELEASE_NAME:-tucano-cvm}"
APP_SECRET_NAME="${APP_SECRET_NAME:-cvm-secret}"
ARGO_ROLLOUTS_NAMESPACE="${ARGO_ROLLOUTS_NAMESPACE:-argo-rollouts}"
INSTALL_ARGO_ROLLOUTS="${INSTALL_ARGO_ROLLOUTS:-true}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-10m}"
HELM_WAIT="${HELM_WAIT:-false}"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-registry.beakcloud.com/tucano-cvm}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
INGRESS_ENABLED="${INGRESS_ENABLED:-false}"
INGRESS_CLASS_NAME="${INGRESS_CLASS_NAME:-}"
INGRESS_HOST="${INGRESS_HOST:-cvm.tucano.beakcloud.com}"
ENABLE_METRICS="${ENABLE_METRICS:-false}"
SERVICE_TYPE="${SERVICE_TYPE:-NodePort}"
SERVICE_PORT="${SERVICE_PORT:-8110}"
NODE_PORT="${NODE_PORT:-30110}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required" >&2
  exit 1
fi

if ! command -v helm >/dev/null 2>&1; then
  echo "helm is required" >&2
  exit 1
fi

if [[ ! -f "${SECRET_FILE}" ]]; then
  echo "Missing secret manifest: ${SECRET_FILE}" >&2
  exit 1
fi

if [[ ! -d "${CHART_DIR}" ]]; then
  echo "Missing Helm chart: ${CHART_DIR}" >&2
  exit 1
fi

require_secret_key() {
  local key="$1"
  if ! grep -Eq "^[[:space:]]+${key}:" "${SECRET_FILE}"; then
    echo "Required key ${key} not found in ${SECRET_FILE}" >&2
    exit 1
  fi
}

require_secret_key "DATABASE_URL"
require_secret_key "TUCANO_CVM_TOKEN"

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

echo "==> Applying application secret to namespace ${NAMESPACE}"
sed -E "s/^([[:space:]]*namespace:).*/\\1 ${NAMESPACE}/" "${SECRET_FILE}" | kubectl apply -f -

if ! kubectl -n "${NAMESPACE}" get secret "${APP_SECRET_NAME}" >/dev/null 2>&1; then
  echo "Secret ${APP_SECRET_NAME} was not found in namespace ${NAMESPACE} after apply" >&2
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
  --set "service.nodePort=${NODE_PORT}"
  --set "ingress.enabled=${INGRESS_ENABLED}"
  --set "ingress.hosts[0].host=${INGRESS_HOST}"
)

if [[ -n "${INGRESS_CLASS_NAME}" ]]; then
  HELM_ARGS+=(--set "ingress.className=${INGRESS_CLASS_NAME}")
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
  ${SERVICE_PORT}:${NODE_PORT}
EOF
