#!/bin/bash
set -euo pipefail

PCKS="python3 python3-dev python3-pip python3-venv build-essential swig liblgpio-dev"
PIP_BASE="paho-mqtt influxdb influxdb-client zeroconf"

log() {
    printf '[setup] %s\n' "$*"
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "[setup] error: required command '$1' is not available" >&2
        exit 1
    fi
}

ask_yes_no() {
    local prompt="$1"
    local env_value="${2:-}"
    local default_no="${3:-true}"
    local answer=""

    if [ -n "$env_value" ]; then
        answer="$env_value"
    elif [ -t 0 ]; then
        read -r -p "$prompt" answer
    else
        # Non-interactive execution defaults to "no".
        echo "n"
        return
    fi

    case "${answer,,}" in
        y|yes|1|true) echo "y" ;;
        *)
            if [ "$default_no" = "false" ] && [ -z "$answer" ]; then
                echo "y"
            else
                echo "n"
            fi
            ;;
    esac
}

install_service() {
    local service_name="$1"
    local description="$2"
    local app_file="$3"
    local service_path="/etc/systemd/system/$service_name"

    local user_name
    user_name="$(id -un)"
    local workdir
    workdir="$(pwd)"
    local python_exec
    python_exec="$workdir/.env/bin/python3"
    local app_exec
    app_exec="$workdir/apps/$app_file"

    if [ ! -x "$python_exec" ]; then
        echo "[setup] error: expected Python executable not found at $python_exec" >&2
        return 1
    fi

    if [ ! -f "$app_exec" ]; then
        echo "[setup] error: expected app not found at $app_exec" >&2
        return 1
    fi

    log "Installing systemd unit $service_name"
    sudo tee "$service_path" >/dev/null <<EOF
[Unit]
Description=$description
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=10
User=$user_name
WorkingDirectory=$workdir
ExecStart=$python_exec $app_exec
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable --now "$service_name"
    sudo systemctl --no-pager --full status "$service_name" | sed -n '1,20p'
    log "Systemd service $service_name installed and started"
}

require_cmd python3
require_cmd dpkg-query
require_cmd sudo

missing_packages=""
for pck in $PCKS; do
    status="$(dpkg-query -W --showformat='${db:Status-Status}' "$pck" 2>/dev/null || true)"
    if [ "$status" != "installed" ]; then
        missing_packages="$missing_packages $pck"
    fi
done

if [ -n "${missing_packages// /}" ]; then
    log "Updating apt metadata"
    sudo apt-get update
    for pck in $missing_packages; do
        log "Installing system package: $pck"
        sudo apt-get install -y --no-install-recommends "$pck"
    done
else
    log "All required system packages are already installed"
fi

log "Preparing virtual environment"
python3 -m venv .env
source .env/bin/activate

log "Upgrading pip tooling"
python -m pip install --upgrade pip setuptools wheel

log "Installing Python dependencies"
python -m pip install $PIP_BASE
python -m pip uninstall -y RPi.GPIO || true
python -m pip install rpi-lgpio
python -m pip install -e .

log "Running hardware scan"
python apps/scan.py

install_433_choice="$(ask_yes_no 'Install 433 MHz pulse gateway as systemd daemon? [y/N] ' "${INSTALL_RCPULSEGW_SERVICE:-}" )"
if [ "$install_433_choice" = "y" ]; then
    install_service "rcpulsegw.service" "RaspyRFM RC pulse gateway" "rcpulsegw.py"
else
    log "Skipping 433 MHz pulse gateway systemd installation"
fi

install_868_choice="$(ask_yes_no 'Install 868 MHz gateway as systemd daemon? [y/N] ' "${INSTALL_868GW_SERVICE:-}" )"
if [ "$install_868_choice" = "y" ]; then
    install_service "868gw.service" "RaspyRFM 868 MHz gateway" "868gw.py"
else
    log "Skipping 868 MHz gateway systemd installation"
fi

log "Setup completed successfully"
