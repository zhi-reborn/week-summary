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

## 验证最小骨架

```bash
.venv/bin/python -m pytest tests/integration/test_health.py -q
cd frontend && npm test -- --run && npm run build
```
