#!/usr/bin/env bash

set -euo pipefail

WORKSPACE="${GITHUB_WORKSPACE:-$(pwd)}"
DEPLOY_DIR="${DEPLOY_DIR:-${HOME}/apps/rpi-monitoring}"
SERVICE_NAME="${SERVICE_NAME:-rpi-monitoring.service}"
SERVICE_USER="${SERVICE_USER:-${USER}}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-${DEPLOY_DIR}/.venv}"
SYSTEMD_UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}"
SERVICE_TEMPLATE="${WORKSPACE}/deploy/rpi-monitoring.service"

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Missing required command: $1" >&2
        exit 1
    fi
}

require_command "$PYTHON_BIN"
require_command sudo
require_command systemctl
require_command install

if ! sudo -n true >/dev/null 2>&1; then
    echo "sudo without password is required for deployment" >&2
    exit 1
fi

if [[ ! -f "${WORKSPACE}/requirements.txt" ]]; then
    echo "requirements.txt not found in ${WORKSPACE}" >&2
    exit 1
fi

if [[ ! -f "$SERVICE_TEMPLATE" ]]; then
    echo "Service template not found: $SERVICE_TEMPLATE" >&2
    exit 1
fi

mkdir -p "$DEPLOY_DIR"

find "$DEPLOY_DIR" -mindepth 1 -maxdepth 1 \
    ! -name '.venv' \
    ! -name '.git' \
    -exec rm -rf {} +

cp -a "$WORKSPACE/." "$DEPLOY_DIR/"
rm -rf "${DEPLOY_DIR}/.git" "${DEPLOY_DIR}/.github" "${DEPLOY_DIR}/.idea"

"$PYTHON_BIN" -m venv "$VENV_DIR"
"${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel
"${VENV_DIR}/bin/pip" install -r "${DEPLOY_DIR}/requirements.txt"

tmp_unit="$(mktemp)"
sed \
    -e "s|__DEPLOY_DIR__|${DEPLOY_DIR}|g" \
    -e "s|__DEPLOY_USER__|${SERVICE_USER}|g" \
    -e "s|__WORKING_DIR__|${DEPLOY_DIR}|g" \
    "$SERVICE_TEMPLATE" > "$tmp_unit"

sudo install -m 0644 "$tmp_unit" "$SYSTEMD_UNIT_PATH"
rm -f "$tmp_unit"

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" --no-pager
