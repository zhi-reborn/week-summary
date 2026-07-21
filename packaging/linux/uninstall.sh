#!/usr/bin/env bash
set -Eeuo pipefail

[[ "$EUID" -eq 0 ]] || { echo "必须以 root 运行" >&2; exit 1; }
systemctl disable --now weekly-report-assistant.service 2>/dev/null || true
rm -f /etc/systemd/system/weekly-report-assistant.service
systemctl daemon-reload
rm -rf /opt/weekly-report-assistant

if [[ "${1:-}" == "--purge" ]]; then
    rm -rf /var/lib/weekly-report-assistant
    rm -rf /var/log/weekly-report-assistant
    rm -rf /etc/weekly-report-assistant
    userdel weekly-report 2>/dev/null || true
else
    echo "业务数据已保留在 /var/lib/weekly-report-assistant"
fi
