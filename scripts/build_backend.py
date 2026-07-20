import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    static_index = ROOT / "app" / "web" / "dist" / "index.html"
    if not static_index.is_file():
        raise SystemExit("未找到前端构建产物，请先运行 scripts/build_frontend.py")

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
    _verify_bundle(ROOT / "dist" / "weekly-report-assistant")


def _verify_bundle(bundle: Path) -> None:
    executable_name = "weekly-report-assistant.exe" if os.name == "nt" else "weekly-report-assistant"
    required = (
        bundle / executable_name,
        bundle / "_internal" / "app" / "web" / "dist" / "index.html",
        bundle / "_internal" / "alembic" / "env.py",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"bundle 缺少必要文件：{', '.join(missing)}")
    print(f"BUNDLE_BUILD_OK path={bundle}")


if __name__ == "__main__":
    main()
