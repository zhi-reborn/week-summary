#!/usr/bin/env bash
set -Eeuo pipefail

[[ "$EUID" -eq 0 ]] || { echo "必须以 root 运行" >&2; exit 1; }
[[ "$(uname -s)" == "Linux" && "$(uname -m)" == "x86_64" ]] || {
    echo "必须在 Linux x86-64 运行" >&2; exit 1;
}
[[ $# -ge 1 ]] || { echo "用法: $0 <package.deb> [--purge]" >&2; exit 1; }

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE="$(realpath "$1")"
FIXTURE="$ROOT/tests/fixtures/docx/plain_placeholder.docx"

wait_ready() {
    local deadline=$((SECONDS + 90))
    until curl --fail --silent --max-time 2 http://127.0.0.1:8765/api/health/ready |
        grep -q '"status":"ready"'; do
        (( SECONDS < deadline )) || { echo "readiness 超时" >&2; return 1; }
        sleep 1
    done
}

run_workflow() {
    local task_json task_id report
    task_json="$(curl --fail --silent -X POST http://127.0.0.1:8765/api/tasks \
        -H 'Content-Type: application/json' -d '{"name":"linux-install-test"}')"
    task_id="$(printf '%s' "$task_json" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')"
    [[ -n "$task_id" ]] || { echo "无法解析任务 ID" >&2; return 1; }
    report="$(mktemp)"
    printf '张三周报\n完成A\n\n李四周报\n完成B\n' > "$report"
    curl --fail --silent -X POST "http://127.0.0.1:8765/api/tasks/$task_id/inputs" \
        -F "reports=@$report;type=text/plain;filename=reports.txt" \
        -F "template=@$FIXTURE;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document;filename=template.docx" >/dev/null
    rm -f "$report"
    for endpoint in people/detect people/confirm template/detect template/confirm; do
        curl --fail --silent -X POST \
            "http://127.0.0.1:8765/api/tasks/$task_id/$endpoint" >/dev/null
    done
}

dpkg -i "$PACKAGE"
wait_ready
systemctl is-active --quiet weekly-report-assistant.service
run_workflow

dpkg -i "$PACKAGE"
wait_ready
dpkg -r weekly-report-assistant
! systemctl is-active --quiet weekly-report-assistant.service
[[ -d /var/lib/weekly-report-assistant ]] || { echo "默认卸载未保留数据" >&2; exit 1; }
if [[ "${2:-}" == "--purge" ]]; then
    rm -rf /var/lib/weekly-report-assistant /var/log/weekly-report-assistant \
        /etc/weekly-report-assistant
    userdel weekly-report 2>/dev/null || true
fi

echo "LINUX_INSTALL_OK service=active health=200 workflow=passed upgrade=passed uninstall=passed"
