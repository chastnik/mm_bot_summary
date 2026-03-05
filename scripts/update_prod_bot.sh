#!/usr/bin/env bash

set -euo pipefail

# Production update script for Mattermost Summary Bot.
# Pulls latest code, rebuilds image and recreates container.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_ENV_FILE="${ROOT_DIR}/.env"
LIB_FILE="${SCRIPT_DIR}/lib/deploy_common.sh"
DEFAULT_PROJECT_DIR="/opt/mattermost-summary-bot"

if [ ! -f "$LIB_FILE" ]; then
    echo "ERROR: shared library not found: $LIB_FILE"
    exit 1
fi

# shellcheck disable=SC1090
source "$LIB_FILE"

if [ -f "$ROOT_ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ROOT_ENV_FILE"
    set +a
fi

PROJECT_DIR="${PROJECT_DIR:-$DEFAULT_PROJECT_DIR}"
BRANCH="${BRANCH:-main}"
IMAGE_NAME="${IMAGE_NAME:-mattermost-summary-bot}"
IMAGE_TAG="${IMAGE_TAG:-prod}"
CONTAINER_NAME="${CONTAINER_NAME:-mattermost-summary-bot-prod}"
HOST_PORT="${HOST_PORT:-8080}"
CONTAINER_PORT="${CONTAINER_PORT:-8080}"

check_project_dir() {
    if [ ! -d "$PROJECT_DIR/.git" ]; then
        echo "ERROR: git repository not found in $PROJECT_DIR"
        echo "Run install script first or set PROJECT_DIR correctly."
        exit 1
    fi
}

pull_latest() {
    cd "$PROJECT_DIR"
    git fetch origin
    git checkout "$BRANCH"
    git pull --ff-only origin "$BRANCH"
}

build_image() {
    cd "$PROJECT_DIR"
    docker build -t "$IMAGE_NAME:$IMAGE_TAG" .
}

recreate_container() {
    local env_file="$PROJECT_DIR/.env"

    if [ ! -f "$env_file" ]; then
        echo "ERROR: .env file not found in $PROJECT_DIR"
        exit 1
    fi

    mkdir -p "$PROJECT_DIR/data" "$PROJECT_DIR/logs"

    if docker ps -a --format '{{.Names}}' | rg -x "$CONTAINER_NAME" >/dev/null 2>&1; then
        docker rm -f "$CONTAINER_NAME"
    fi

    docker run -d \
        --name "$CONTAINER_NAME" \
        --restart unless-stopped \
        --env-file "$env_file" \
        -p "$HOST_PORT:$CONTAINER_PORT" \
        -v "$PROJECT_DIR/data:/app/data" \
        -v "$PROJECT_DIR/logs:/app/logs" \
        "$IMAGE_NAME:$IMAGE_TAG"
}

show_status() {
    docker ps --filter "name=^${CONTAINER_NAME}$"
}

main() {
    require_cmd git
    require_cmd docker
    require_cmd rg
    require_docker_daemon

    check_project_dir
    if ! validate_required_env "$PROJECT_DIR/.env"; then
        echo "Fix .env values and run update again."
        exit 1
    fi
    validate_ports "$HOST_PORT" "$CONTAINER_PORT"
    pull_latest
    build_image
    recreate_container
    show_status
}

main "$@"
