# 发布验收清单

## 候选版本

- 版本：`0.1.0`
- 提交：发布时填写
- 验收负责人：发布时填写
- SHA256SUMS：收集三个原生安装包后生成并复核
- 当前结论：**阻塞**。Windows/Linux 原生安装矩阵尚未执行。

## 自动化门禁

- [x] `.venv/bin/python -m pytest tests/unit tests/integration tests/security tests/contract -q`（177 项）
- [x] `.venv/bin/ruff check app scripts/release_check.py tests`
- [x] `.venv/bin/mypy app scripts/release_check.py`
- [x] `cd frontend && npm test -- --run && npm run lint && npm run typecheck && npm run build`（16 项）
- [x] `cd frontend && npm run test:e2e`（2 项）
- [x] macOS 开发用 one-folder bundle 冒烟输出 `BUNDLE_OK health=200 ui=200 workflow=passed`
- [ ] 三个原生安装包收集后运行：
  `python scripts/release_check.py dist/installers --write-checksums`
- [ ] 在不改动安装包的独立环境复核：
  `python scripts/release_check.py dist/installers`

严格发布检查要求目录中恰好存在以下三个安装包及 `SHA256SUMS`：

- `WeeklyReportAssistant-0.1.0-windows-x64.exe`
- `weekly-report-assistant_0.1.0_amd64.deb`
- `weekly-report-assistant-0.1.0-linux-x64.tar.gz`

## 原生安装矩阵

| 系统 | 构建 | 全新安装 | 核心流程 | 重启恢复 | 升级 | 保留数据卸载 | 清除数据卸载 |
|---|---|---|---|---|---|---|---|
| Windows 10 x64 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| Windows 11 x64 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| Windows Server 2019 x64 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| Windows Server 2022 x64 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| Debian 12 x64，deb | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| Ubuntu 22.04/24.04 x64，deb | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| RHEL 9 兼容 x64，tar.gz | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |

Windows 使用 `scripts/test_windows_install.ps1`；Debian/Ubuntu 使用
`scripts/test_linux_install.sh`。tar.gz 需按 `docs/install/linux.md` 人工执行等价流程。

## 业务与文档验收

- [ ] 使用真实合并周报验证人员识别、人工修正、模板识别、分析、校审和导出。
- [ ] 使用上一发布版数据升级，确认任务、配置、上传、校审版本和导出保持。
- [ ] 按 `docs/qa/docx-compatibility-checklist.md` 完成 Word 与 LibreOffice 实机检查。
- [ ] 默认地址、目录、服务账户、备份恢复和卸载说明与目标机行为一致。
- [ ] 安全清单全部通过，安装包来自受控构建机，发布页同时提供 `SHA256SUMS`。

任一原生平台、升级数据、DOCX 实机或安全项目未通过时，不得发布正式版。
