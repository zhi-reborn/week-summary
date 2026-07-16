import os
import socket
import subprocess
import time
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[2]


def _release_executable() -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return ROOT / "dist" / "weekly-report-assistant" / f"weekly-report-assistant{suffix}"


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_health(
    client: httpx.Client, base_url: str, process: subprocess.Popen[bytes]
) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"发布程序提前退出，退出码 {process.returncode}")
        try:
            if client.get(f"{base_url}/health", timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise AssertionError("发布程序未在 20 秒内启动")


def test_release_runs_complete_foundation_flow(tmp_path: Path, valid_docx_bytes: bytes) -> None:
    executable = _release_executable()
    assert executable.exists(), "请先运行 scripts/build_release.py 构建发布目录"

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment.update({"WRA_PORT": str(port), "WRA_DATA_DIR": str(tmp_path / "data")})
    process = subprocess.Popen(
        [str(executable)],
        cwd=executable.parent,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        client = httpx.Client(trust_env=False)
        _wait_for_health(client, base_url, process)
        assert "智能周报汇总系统" in client.get(base_url, timeout=2).text

        task = client.post(f"{base_url}/api/tasks", json={"name": "第29周"}, timeout=2).json()
        upload = client.post(
            f"{base_url}/api/tasks/{task['id']}/inputs",
            files={
                "reports": ("reports.txt", "姓名：张三\n完成A\n\n李四周报\n完成B".encode(), "text/plain"),
                "template": ("template.docx", valid_docx_bytes, "application/octet-stream"),
            },
            timeout=5,
        )
        assert upload.status_code == 200
        assert client.post(f"{base_url}/api/tasks/{task['id']}/people/detect", timeout=2).status_code == 200
        assert client.post(f"{base_url}/api/tasks/{task['id']}/people/confirm", timeout=2).status_code == 200
        assert client.post(f"{base_url}/api/tasks/{task['id']}/template/detect", timeout=5).status_code == 200
        confirmation = client.post(f"{base_url}/api/tasks/{task['id']}/template/confirm", timeout=2)
        assert confirmation.json()["status"] == "ready_for_analysis"
        saved_task = client.get(f"{base_url}/api/tasks/{task['id']}", timeout=2)
        assert saved_task.json()["status"] == "ready_for_analysis"
    finally:
        if "client" in locals():
            client.close()
        process.terminate()
        process.wait(timeout=5)
