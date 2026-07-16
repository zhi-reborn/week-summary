# 智能周报汇总系统

本地运行的周报汇总工具：上传一个合并的 TXT 周报和一个 DOCX 模板，连接 OpenAI-compatible 私有模型，生成可校审、可追溯的 Word 汇总文件。

## 开发环境

- Python 3.12
- Node.js 20 或更高版本

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cd frontend && npm install
```

## 使用流程

1. 打开“模型设置”，填写私有模型的 OpenAI-compatible Base URL、模型名和可选 API Key，并执行连接测试。
2. 新建汇总任务，上传合并后的一个 TXT 周报文件和一个 DOCX 模板。
3. 确认系统识别的人员范围与模板板块。
4. 系统按人员分别提炼事实，再完成跨人员聚合、冲突检查、模板板块生成和覆盖检查。
5. 分析中断后可从失败步骤继续；已经成功的人员和板块不会重复调用模型。

模型请求只访问所配置的私有地址，不读取系统代理配置。API Key 单独保存在运行数据目录中，不通过读取接口回传。

## 验证

```bash
.venv/bin/python -m pytest tests/unit tests/integration tests/contract -q
.venv/bin/python -m pytest tests/e2e/test_analysis_flow.py -q
cd frontend && npm test -- --run && npm run build
```

## 本地开发运行

应用服务默认监听 `127.0.0.1:8765`，并在同一进程运行可恢复的分析队列。前端开发服务器监听 `127.0.0.1:5173` 并代理 API：

```bash
WRA_PORT=8787 .venv/bin/python -m app.bootstrap
cd frontend && npm run dev
```

## 无 Docker 原生构建

构建必须在对应目标系统执行；PyInstaller 不支持从其他系统交叉构建。Windows 和 Linux 均生成 one-folder 目录，目标机器无需安装 Python、Node.js 或 Docker。

Linux：

```bash
.venv/bin/python scripts/build_release.py --platform linux
.venv/bin/python -m pytest tests/e2e/test_foundation_flow.py -q
```

Windows PowerShell：

```powershell
.venv\Scripts\python.exe scripts\build_release.py --platform windows
.venv\Scripts\python.exe -m pytest tests\e2e\test_foundation_flow.py -q
```

启动发布目录中的 `weekly-report-assistant`（Windows 为 `weekly-report-assistant.exe`），然后访问 `http://127.0.0.1:8765/`。运行数据默认写入启动目录下的 `data/`；可以通过 `WRA_DATA_DIR`、`WRA_HOST` 和 `WRA_PORT` 修改。
