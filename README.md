# 智能周报汇总系统

本地运行的周报汇总工具：上传一个包含全团队周报的 TXT 文件和一个 DOCX 模板，连接 OpenAI-compatible 私有模型，生成可校审、可追溯的 Word 汇总文件。

## 系统要求与安装

正式运行支持 x86-64 Windows 10/11、Windows Server 2019/2022，以及使用 glibc、systemd 的 x86-64 Linux。目标机器不需要 Docker、Python 或 Node.js，默认只监听
`http://127.0.0.1:8765/`。

- Windows：运行 `WeeklyReportAssistant-<版本>-windows-x64.exe`，详见 [Windows 安装说明](docs/install/windows.md)。
- Debian/Ubuntu：`sudo dpkg -i weekly-report-assistant_<版本>_amd64.deb`。
- 其他 systemd Linux：解压 `linux-x64.tar.gz` 后运行 `sudo ./install.sh`，详见 [Linux 安装说明](docs/install/linux.md)。

当前仓库尚未完成 Windows/Linux 原生安装矩阵，不能作为正式发布版分发；状态见
[发布验收清单](docs/qa/release-checklist.md)。

## 使用流程

1. 打开“模型设置”，填写私有模型的 OpenAI-compatible Base URL、模型名和可选 API Key，并测试连接。
2. 新建任务，上传一个合并后的 TXT 周报和一个 DOCX 模板。
3. 核对系统识别的人员范围与模板板块。
4. 启动分析；系统先提炼个人事实，再完成跨人员聚合、冲突检查、板块生成和覆盖检查。
5. 校审每个板块并导出 DOCX。中断后可从失败步骤继续，成功结果不会重复调用模型。

模型配置 API 示例：

```bash
curl -X PUT http://127.0.0.1:8765/api/settings/model \
  -H 'Content-Type: application/json' \
  -d '{"base_url":"http://127.0.0.1:8000/v1","model":"private-model","api_key":"replace-me","timeout_seconds":120,"max_retries":2,"temperature":0.1}'
curl -X POST http://127.0.0.1:8765/api/settings/model/test
```

模型请求只访问配置的私有地址且不读取系统代理。API Key 不通过读取接口回传；Windows 使用 DPAPI 保护，Linux 使用仅服务账户可读的密钥文件。

## 数据、备份与恢复

| 系统 | 程序 | 业务数据和数据库 | 日志 |
|---|---|---|---|
| Windows | `%ProgramFiles%\WeeklyReportAssistant` | `%ProgramData%\WeeklyReportAssistant` | 数据目录下 `logs\app.jsonl` |
| Linux | `/opt/weekly-report-assistant` | `/var/lib/weekly-report-assistant` | `/var/log/weekly-report-assistant/app.jsonl` |

数据库迁移前会在数据目录的 `backups/` 创建并校验 SQLite 一致性备份。完整人工备份应先停止服务，再复制整个业务数据目录。恢复时先停止服务，将选定备份复制为 `app.db`，删除同目录的 `app.db-wal`、`app.db-shm` 和 `app.db-journal`，确认文件所有者仍为服务账户，再启动服务并检查 readiness。不要在服务运行时直接覆盖数据库。

Windows 和 Linux tar 安装器会临时备份旧程序、数据库和模型配置，并在升级失败时尝试恢复旧版本。deb 升级失败时恢复迁移前数据、停止服务并保持包为“未配置”状态，需重新安装当前包或明确降级；它不会用旧文件覆盖 dpkg 管理的新程序。升级回滚目录不是长期备份策略。

## 健康检查与诊断

```bash
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/api/health/ready
curl -o diagnostics.zip http://127.0.0.1:8765/api/diagnostics
```

`/health` 只表示进程存活；`/api/health/ready` 还检查数据库可写、数据目录可写和迁移版本。诊断包不包含周报正文、模型响应、API Key 或绝对磁盘路径。服务命令、日志位置和端口冲突处理见对应平台安装文档。

## 卸载

Windows 卸载器和 Linux 卸载脚本默认保留业务数据。只有用户显式勾选 Windows 的数据清除选项，或在 Linux tar 安装中运行 `uninstall.sh --purge`，才会删除周报、模板、导出、数据库和模型配置。deb 使用 `dpkg -r` 时保留数据和 `/etc` 配置。

## 开发与验证

开发环境需要 Python 3.12 和 Node.js 20 或更高版本：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cd frontend && npm install
```

启动后端和前端开发服务器：

```bash
WRA_PORT=8787 .venv/bin/python -m app.bootstrap
cd frontend && npm run dev
```

全量自动化检查：

```bash
.venv/bin/python -m pytest tests/unit tests/integration tests/security tests/contract -q
.venv/bin/ruff check app scripts/release_check.py tests
.venv/bin/mypy app scripts/release_check.py
cd frontend && npm test -- --run && npm run lint && npm run typecheck && npm run build
cd frontend && npm run test:e2e
```

## 无 Docker 原生构建与发布校验

PyInstaller 不支持跨系统构建，必须在对应 x86-64 Windows/Linux 构建机执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

```bash
bash scripts/build_linux.sh
```

收集三个安装包后生成并复核校验清单：

```bash
.venv/bin/python scripts/release_check.py dist/installers --write-checksums
.venv/bin/python scripts/release_check.py dist/installers
```

只有严格检查输出 `RELEASE_OK version=<版本> artifacts=3 checksums=valid`，且发布、DOCX 与安全清单全部完成，才可发布正式版。
# week-summary
