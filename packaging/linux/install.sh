#!/usr/bin/env bash
set -Eeuo pipefail

SERVICE_NAME="weekly-report-assistant"
SERVICE_USER="weekly-report"
INSTALL_DIR="/opt/weekly-report-assistant"
DATA_DIR="/var/lib/weekly-report-assistant"
LOG_DIR="/var/log/weekly-report-assistant"
CONFIG_DIR="/etc/weekly-report-assistant"
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_DIR="$SOURCE_DIR/bundle"
UNIT_SOURCE="$SOURCE_DIR/weekly-report-assistant.service"
ENV_SOURCE="$SOURCE_DIR/environment"
PREVIOUS_DIR="/opt/.weekly-report-assistant.previous"
ROLLBACK_DIR="$DATA_DIR/installer-rollback"
HAD_PREVIOUS=0
INSTALL_MUTATED=0
ORIGINAL_SERVICE_ACTIVE=0
ORIGINAL_SERVICE_ENABLED=0
INSTALL_SUCCESS=0

require_environment() {
    [[ "$EUID" -eq 0 ]] || { echo "必须以 root 运行" >&2; exit 1; }
    [[ "$(uname -s)" == "Linux" ]] || { echo "仅支持 Linux" >&2; exit 1; }
    [[ "$(uname -m)" == "x86_64" ]] || { echo "仅支持 x86-64" >&2; exit 1; }
    [[ "$(ps -p 1 -o comm= | tr -d ' ')" == "systemd" ]] || {
        echo "仅支持 systemd Linux" >&2; exit 1;
    }
    command -v systemctl >/dev/null
    command -v useradd >/dev/null
    command -v runuser >/dev/null
    command -v curl >/dev/null
    command -v ss >/dev/null
    [[ -x "$BUNDLE_DIR/weekly-report-assistant" ]] || {
        echo "安装包缺少 bundle/weekly-report-assistant" >&2; exit 1;
    }
}

restore_previous() {
    if [[ "$INSTALL_SUCCESS" -eq 1 ]]; then
        return
    fi
    trap - EXIT HUP INT TERM ERR
    systemctl stop "$SERVICE_NAME.service" 2>/dev/null || true
    if [[ "$HAD_PREVIOUS" -eq 1 && -d "$PREVIOUS_DIR" ]]; then
        rm -rf "$INSTALL_DIR"
        mv "$PREVIOUS_DIR" "$INSTALL_DIR"
        if [[ -d "$ROLLBACK_DIR/data" ]]; then
            rm -f "$DATA_DIR/app.db-wal" "$DATA_DIR/app.db-shm" \
                "$DATA_DIR/app.db-journal"
            find "$ROLLBACK_DIR/data" -maxdepth 1 -type f -exec cp -a {} "$DATA_DIR/" \;
        fi
        rm -f /etc/systemd/system/weekly-report-assistant.service
        if [[ -f "$ROLLBACK_DIR/service" ]]; then
            cp -a "$ROLLBACK_DIR/service" /etc/systemd/system/weekly-report-assistant.service
        fi
    elif [[ "$INSTALL_MUTATED" -eq 1 ]]; then
        rm -rf "$INSTALL_DIR"
        rm -f /etc/systemd/system/weekly-report-assistant.service
    fi
    systemctl daemon-reload
    if [[ "$ORIGINAL_SERVICE_ENABLED" -eq 1 ]]; then
        systemctl enable "$SERVICE_NAME.service" 2>/dev/null || true
    else
        systemctl disable "$SERVICE_NAME.service" 2>/dev/null || true
    fi
    if [[ "$ORIGINAL_SERVICE_ACTIVE" -eq 1 ]]; then
        systemctl start "$SERVICE_NAME.service" 2>/dev/null || true
    fi
    echo "安装失败，已尝试恢复原版本" >&2
}

abort_install() {
    exit 1
}

wait_ready() {
    local deadline=$((SECONDS + 60))
    until curl --fail --silent --max-time 2 http://127.0.0.1:8765/api/health/ready |
        grep -q '"status":"ready"'; do
        (( SECONDS < deadline )) || return 1
        sleep 1
    done
}

require_environment
if systemctl is-active --quiet "$SERVICE_NAME.service" 2>/dev/null; then
    ORIGINAL_SERVICE_ACTIVE=1
fi
if systemctl is-enabled --quiet "$SERVICE_NAME.service" 2>/dev/null; then
    ORIGINAL_SERVICE_ENABLED=1
fi
trap restore_previous EXIT
trap abort_install HUP INT TERM
systemctl stop "$SERVICE_NAME.service" 2>/dev/null || true
if ss -ltnH 'sport = :8765' | grep -q .; then
    echo "端口 8765 已被占用" >&2
    exit 1
fi

getent passwd "$SERVICE_USER" >/dev/null || useradd \
    --system --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
rm -rf "$ROLLBACK_DIR"
install -d -m 0700 -o "$SERVICE_USER" -g "$SERVICE_USER" "$DATA_DIR" "$LOG_DIR"
install -d -m 0755 -o root -g root "$CONFIG_DIR"
install -d -m 0700 -o root -g root "$ROLLBACK_DIR/data"

for name in app.db model_settings.json model_api_key config.toml; do
    [[ -f "$DATA_DIR/$name" ]] && cp -a "$DATA_DIR/$name" "$ROLLBACK_DIR/data/"
done
[[ -f /etc/systemd/system/weekly-report-assistant.service ]] && \
    cp -a /etc/systemd/system/weekly-report-assistant.service "$ROLLBACK_DIR/service"
if [[ -d "$PREVIOUS_DIR" ]]; then rm -rf "$PREVIOUS_DIR"; fi
if [[ -d "$INSTALL_DIR" ]]; then
    mv "$INSTALL_DIR" "$PREVIOUS_DIR"
    HAD_PREVIOUS=1
fi
INSTALL_MUTATED=1
install -d -m 0755 -o root -g root "$INSTALL_DIR"
cp -a "$BUNDLE_DIR/." "$INSTALL_DIR/"
install -d -m 0755 -o root -g root "$INSTALL_DIR/installer"
install -m 0755 -o root -g root "$SOURCE_DIR/uninstall.sh" \
    "$INSTALL_DIR/installer/uninstall.sh"
chown -R root:root "$INSTALL_DIR"
chmod -R go-w "$INSTALL_DIR"
install -m 0644 -o root -g root "$UNIT_SOURCE" /etc/systemd/system/weekly-report-assistant.service
if [[ ! -f "$CONFIG_DIR/environment" ]]; then
    install -m 0644 -o root -g root "$ENV_SOURCE" "$CONFIG_DIR/environment"
fi

runuser -u "$SERVICE_USER" -- "$INSTALL_DIR/weekly-report-assistant" --migrate
systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME.service"
wait_ready

rm -rf "$PREVIOUS_DIR" "$ROLLBACK_DIR"
INSTALL_SUCCESS=1
trap - EXIT HUP INT TERM ERR
echo "LINUX_INSTALL_COMPLETE url=http://127.0.0.1:8765"
