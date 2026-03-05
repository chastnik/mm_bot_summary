#!/usr/bin/env bash

set -euo pipefail

# Production installation script for Mattermost Summary Bot.
# Installs/updates repo on server, builds image and starts bot container.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_ENV_FILE="${ROOT_DIR}/.env"
LIB_FILE="${SCRIPT_DIR}/lib/deploy_common.sh"
DEFAULT_PROJECT_DIR="/opt/mattermost-summary-bot"
DEFAULT_REPO_URL="https://github.com/chastnik/mm_bot_summary.git"

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
REPO_URL="${REPO_URL:-$DEFAULT_REPO_URL}"
BRANCH="${BRANCH:-main}"
IMAGE_NAME="${IMAGE_NAME:-mattermost-summary-bot}"
IMAGE_TAG="${IMAGE_TAG:-prod}"
CONTAINER_NAME="${CONTAINER_NAME:-mattermost-summary-bot-prod}"
HOST_PORT="${HOST_PORT:-8080}"
CONTAINER_PORT="${CONTAINER_PORT:-8080}"

ensure_repo() {
    if [ -d "$PROJECT_DIR/.git" ]; then
        echo "Repository already exists in $PROJECT_DIR"
        return
    fi

    echo "Cloning repository to $PROJECT_DIR ..."
    mkdir -p "$(dirname "$PROJECT_DIR")"
    git clone "$REPO_URL" "$PROJECT_DIR"
}

prepare_env() {
    local env_file="$PROJECT_DIR/.env"
    local env_example="$PROJECT_DIR/env.example"

    if [ -f "$env_file" ]; then
        return
    fi

    if [ ! -f "$env_example" ]; then
        echo "ERROR: $env_file does not exist and env.example not found."
        exit 1
    fi

    cp "$env_example" "$env_file"
    echo "Created $env_file from env.example."
    echo "Fill required values in $env_file and run script again."
    exit 1
}

sync_branch() {
    cd "$PROJECT_DIR"
    git fetch origin
    git checkout "$BRANCH"
    git pull --ff-only origin "$BRANCH"
}

build_image() {
    cd "$PROJECT_DIR"
    docker build -t "$IMAGE_NAME:$IMAGE_TAG" .
}

restart_container() {
    local env_file="$PROJECT_DIR/.env"

    if docker ps -a --format '{{.Names}}' | rg -x "$CONTAINER_NAME" >/dev/null 2>&1; then
        echo "Removing existing container: $CONTAINER_NAME"
        docker rm -f "$CONTAINER_NAME"
    fi

    mkdir -p "$PROJECT_DIR/data" "$PROJECT_DIR/logs"

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
    echo
    echo "Container status:"
    docker ps --filter "name=^${CONTAINER_NAME}$"
    echo
    echo "Health endpoint: http://localhost:${HOST_PORT}/health"
}

main() {
    require_cmd git
    require_cmd docker
    require_cmd rg
    require_docker_daemon

    echo "Starting production install for bot container ..."
    ensure_repo
    sync_branch
    prepare_env
    if ! validate_required_env "$PROJECT_DIR/.env"; then
        echo "Fix .env values and run install again."
        exit 1
    fi
    validate_ports "$HOST_PORT" "$CONTAINER_PORT"
    build_image
    restart_container
    show_status
}

main "$@"
