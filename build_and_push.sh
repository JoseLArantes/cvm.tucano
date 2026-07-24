#!/usr/bin/env bash

set -euo pipefail

if (( $# > 1 )); then
    echo "Usage: $0 [image-tag]" >&2
    exit 1
fi

REGISTRY_URL="${REGISTRY_URL:-registry.beakcloud.com}"
REGISTRY="${REGISTRY_URL#http://}"
REGISTRY="${REGISTRY#https://}"
REGISTRY="${REGISTRY%/}"
IMAGE_NAME="${IMAGE_NAME:-tucano-cvm}"
TAG="${1:-${IMAGE_TAG:-latest}}"
PLATFORM="${PLATFORM:-linux/amd64}"
BUILD_TARGET="${BUILD_TARGET:-runtime}"
PUSH_IMAGE="${PUSH_IMAGE:-true}"
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${TAG}"

if [[ -z "${REGISTRY}" ]]; then
    echo "Error: REGISTRY_URL cannot be empty." >&2
    exit 1
fi

if [[ ! "${TAG}" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]]; then
    echo "Error: '${TAG}' is not a valid container image tag." >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker daemon is not running." >&2
    exit 1
fi

if [[ -n "${REGISTRY_USER:-}" || -n "${REGISTRY_PASS:-}" ]]; then
    if [[ -z "${REGISTRY_USER:-}" || -z "${REGISTRY_PASS:-}" ]]; then
        echo "Error: REGISTRY_USER and REGISTRY_PASS must be provided together." >&2
        exit 1
    fi

    printf '%s' "${REGISTRY_PASS}" | docker login "${REGISTRY}" \
        --username "${REGISTRY_USER}" \
        --password-stdin
fi

echo "=========================================================="
echo "Building ${FULL_IMAGE_NAME}"
echo "Platform: ${PLATFORM}"
echo "Target: ${BUILD_TARGET}"
echo "=========================================================="

build_output=(--push)
if [[ "${PUSH_IMAGE}" == "false" ]]; then
    build_output=(--load)
elif [[ "${PUSH_IMAGE}" != "true" ]]; then
    echo "Error: PUSH_IMAGE must be either 'true' or 'false'." >&2
    exit 1
fi

docker buildx build \
    --platform "${PLATFORM}" \
    --target "${BUILD_TARGET}" \
    --tag "${FULL_IMAGE_NAME}" \
    "${build_output[@]}" \
    .

if [[ "${PUSH_IMAGE}" == "true" ]]; then
    echo "Published: ${FULL_IMAGE_NAME}"
else
    echo "Built locally: ${FULL_IMAGE_NAME}"
fi
