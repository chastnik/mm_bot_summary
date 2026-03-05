#!/usr/bin/env bash

# Shared helpers for production deploy scripts.

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "ERROR: required command '$1' not found."
        exit 1
    fi
}

require_docker_daemon() {
    if ! docker info >/dev/null 2>&1; then
        echo "ERROR: Docker daemon is not available."
        echo "Make sure Docker is running and current user can access it."
        exit 1
    fi
}

is_placeholder_value() {
    local value="$1"
    case "$value" in
        your-*|*your-*|llm_token|model_name|url|changeme|change_me|example|localhost)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

validate_required_env() {
    local env_file="$1"
    local key=""
    local line=""
    local value=""
    local missing=0
    local invalid=0
    local required_vars=(
        "MATTERMOST_URL"
        "MATTERMOST_TOKEN"
        "MATTERMOST_BOT_USERNAME"
        "LLM_PROXY_TOKEN"
        "LLM_BASE_URL"
        "LLM_MODEL"
        "WEB_API_TOKEN"
    )

    if [ ! -f "$env_file" ]; then
        echo "ERROR: .env file not found: $env_file"
        exit 1
    fi

    for key in "${required_vars[@]}"; do
        line="$(rg -m 1 "^${key}=" "$env_file" || true)"
        if [ -z "$line" ]; then
            echo "ERROR: missing required variable '$key' in $env_file"
            missing=1
            continue
        fi

        value="${line#*=}"
        value="${value%\"}"
        value="${value#\"}"
        value="${value%\'}"
        value="${value#\'}"

        if [ -z "$value" ]; then
            echo "ERROR: variable '$key' is empty in $env_file"
            invalid=1
            continue
        fi

        if is_placeholder_value "$value"; then
            echo "ERROR: variable '$key' contains placeholder value ('$value') in $env_file"
            invalid=1
        fi
    done

    if [ "$missing" -ne 0 ] || [ "$invalid" -ne 0 ]; then
        return 1
    fi
}

validate_ports() {
    local host_port="$1"
    local container_port="$2"

    if ! [[ "$host_port" =~ ^[0-9]+$ && "$container_port" =~ ^[0-9]+$ ]]; then
        echo "ERROR: HOST_PORT and CONTAINER_PORT must be numeric."
        return 1
    fi
}
