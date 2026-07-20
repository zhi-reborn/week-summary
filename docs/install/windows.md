# Windows 原生安装与运维

## 支持范围

- Windows 10/11 x86-64、Windows Server 2019/2022 x86-64。
- 目标机不需要 Docker、Python 或 Node.js。
- 服务仅监听 `127.0.0.1:8765`，使用虚拟专用账户 `NT SERVICE\WeeklyReportAssistant`。

## 安装与静默参数

双击安装器，或以管理员 PowerShell 静默安装：

```powershell
WeeklyReportAssistant-0.1.0-windows-x64.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
```

打开 `http://127.0.0.1:8765`。数据库、上传、导出、模型配置和日志位于
`%PROGRAMDATA%\WeeklyReportAssistant`，程序文件位于
`%ProgramFiles%\WeeklyReportAssistant`。

## 服务、日志与故障检查

```powershell
Get-Service WeeklyReportAssistant
Invoke-WebRequest http://127.0.0.1:8765/health
Invoke-WebRequest http://127.0.0.1:8765/api/health/ready
Get-Content "$env:ProgramData\WeeklyReportAssistant\logs\app.jsonl" -Tail 100
```

若 8765 端口被占用，安装后的 readiness 会失败并触发升级回滚。当前版本不支持从界面修改端口；应先停止占用该端口的程序，再重新安装。

## 升级和卸载

直接运行新安装器即可升级。安装器会先停止服务，将旧程序及 SQLite/配置复制到
`%PROGRAMDATA%\WeeklyReportAssistant\upgrade-rollback`，再替换文件、迁移并检查 readiness；失败时恢复旧版本。

卸载页的“同时删除全部周报、模板、导出文件和模型配置”默认不勾选，因此默认保留业务数据。无人值守卸载同样默认保留；如需清除，可在卸载后以管理员身份删除数据目录。

## 原生验证记录

当前开发环境为 macOS，不能生成或执行 Windows 安装器。下表必须由 Windows x86-64 构建机/干净 VM 执行 `scripts/test_windows_install.ps1` 后填写，不得以静态检查代替。

| 系统 | 构建/安装/升级/卸载 | 结果 |
|---|---|---|
| Windows 10 x86-64 | 待执行 | 未验证 |
| Windows 11 x86-64 | 待执行 | 未验证 |
| Windows Server 2019 x86-64 | 待执行 | 未验证 |
| Windows Server 2022 x86-64 | 待执行 | 未验证 |
