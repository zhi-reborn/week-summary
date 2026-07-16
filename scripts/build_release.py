import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLATFORM_NAMES = {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}


def main() -> None:
    parser = argparse.ArgumentParser(description="构建智能周报汇总系统原生发布目录")
    parser.add_argument("--platform", choices=("linux", "windows", "macos"))
    arguments = parser.parse_args()
    current = PLATFORM_NAMES.get(platform.system(), platform.system().lower())
    if arguments.platform and arguments.platform != current:
        raise SystemExit(f"PyInstaller 不支持交叉编译：当前为 {current}，不能构建 {arguments.platform}")

    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_frontend.py")], check=True)
    environment = os.environ.copy()
    environment["PYINSTALLER_CONFIG_DIR"] = str(ROOT / "build" / "pyinstaller-cache")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(ROOT / "packaging" / "pyinstaller" / "weekly-report.spec"),
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )


if __name__ == "__main__":
    main()
