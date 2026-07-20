import argparse
import os
import socket
import subprocess
import tempfile
import time
from io import BytesIO
from pathlib import Path

import httpx
from docx import Document


def main() -> None:
    parser = argparse.ArgumentParser(description="验证智能周报汇总系统 bundle")
    parser.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    bundle = arguments.bundle.resolve()
    executable = bundle / ("weekly-report-assistant.exe" if os.name == "nt" else "weekly-report-assistant")
    if not executable.is_file():
        raise SystemExit(f"未找到可执行文件：{executable}")

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="weekly-report-smoke-") as temporary:
        data_dir = Path(temporary) / "data"
        environment = os.environ.copy()
        environment.update(
            {
                "WRA_PORT": str(port),
                "WRA_DATA_DIR": str(data_dir),
                "WRA_LOG_DIR": str(Path(temporary) / "logs"),
            }
        )
        process = subprocess.Popen(
            [str(executable)],
            cwd=bundle,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        try:
            with httpx.Client(base_url=base_url, trust_env=False, timeout=10) as client:
                _wait_until_ready(client, process)
                _verify_workflow(client)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    print("BUNDLE_OK health=200 ui=200 workflow=passed")


def _wait_until_ready(client: httpx.Client, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read().decode("utf-8", errors="replace") if process.stdout else ""
            raise RuntimeError(f"bundle 提前退出，退出码 {process.returncode}：{output[-2000:]}")
        try:
            if (
                client.get("/health", timeout=1).status_code == 200
                and client.get("/api/health/ready", timeout=1).status_code == 200
            ):
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError("bundle 未在 30 秒内就绪")


def _verify_workflow(client: httpx.Client) -> None:
    ui = client.get("/")
    if ui.status_code != 200 or "智能周报汇总系统" not in ui.text:
        raise RuntimeError("前端页面验证失败")
    task_response = client.post("/api/tasks", json={"name": "bundle-smoke"})
    task_response.raise_for_status()
    task_id = task_response.json()["id"]
    upload = client.post(
        f"/api/tasks/{task_id}/inputs",
        files={
            "reports": (
                "reports.txt",
                "张三周报\n完成A\n\n李四周报\n完成B".encode("utf-8"),
                "text/plain",
            ),
            "template": (
                "template.docx",
                _template_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        },
    )
    upload.raise_for_status()
    client.post(f"/api/tasks/{task_id}/people/detect").raise_for_status()
    client.post(f"/api/tasks/{task_id}/people/confirm").raise_for_status()
    client.post(f"/api/tasks/{task_id}/template/detect").raise_for_status()
    confirmation = client.post(f"/api/tasks/{task_id}/template/confirm")
    confirmation.raise_for_status()
    if confirmation.json()["status"] != "ready_for_analysis":
        raise RuntimeError("工作流未进入待分析状态")


def _template_bytes() -> bytes:
    document = Document()
    document.add_paragraph("{{本周重点}}")
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


if __name__ == "__main__":
    main()
