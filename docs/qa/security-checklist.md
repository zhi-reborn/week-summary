# 安全回归清单

## 自动化检查

- [x] `pytest tests/security -q`：扩展名、MIME、大小、DOCX ZIP 条目数、解压大小和压缩比限制通过。
- [x] `pytest tests/unit/core/test_redaction.py tests/integration/api/test_diagnostics.py -q`：测试 API Key、Authorization、周报全文和绝对路径未出现在日志或诊断包。
- [x] `pytest tests/unit/llm/test_prompt_boundaries.py -q`：周报内容作为不可信数据分隔并转义。
- [x] 模型设置读取接口不返回 `api_key`，连接失败响应不包含密钥或私有模型响应正文。
- [ ] 发布检查器验证版本、安装包集合和每个文件的 SHA-256。

## 安装与权限

- [ ] 默认只监听 `127.0.0.1:8765`，局域网其他机器无法直接访问。
- [ ] Windows 服务使用 `NT SERVICE\WeeklyReportAssistant`，仅可修改 ProgramData 数据目录。
- [ ] Linux 服务使用无登录 `weekly-report` 用户，数据/日志目录 `0700`，密钥文件 `0600`。
- [ ] `systemd-analyze security weekly-report-assistant.service` 显示计划中的沙箱项均已启用。
- [ ] 普通服务账户无法修改安装目录、`/usr`、用户 home 或系统配置。
- [ ] 安装包签名状态已记录；未签名 Windows 候选包不能对外正式发布。

## 数据与外联

- [ ] 私有模型 Base URL 为用户明确配置的 HTTP(S) 地址，请求不读取系统代理。
- [ ] 抓包确认应用只访问配置的模型地址，没有遥测或公共大模型外联。
- [ ] 诊断包仅包含版本、迁移状态、非敏感配置状态、用量和白名单错误字段。
- [ ] 默认卸载保留业务数据；清除数据必须由用户显式选择并有风险提示。
- [ ] 升级前备份可恢复，恢复数据库前清除 `-wal`、`-shm`、`-journal` 旁文件。

## 人工恶意输入检查

- [ ] 周报中加入“忽略系统指令”等提示注入文本，输出不得泄露系统提示或密钥。
- [ ] 上传路径穿越文件名、伪装扩展名、截断 ZIP 和高压缩比 DOCX，均返回稳定的 4xx 错误。
- [ ] 超时、401/403、429、5xx 和模型返回非 JSON 时，页面可重试且日志不含响应正文。
- [ ] 反复中断分析和服务重启不会无限重试，不会重复覆盖已确认内容。
