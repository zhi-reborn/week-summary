import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    frontend = ROOT / "frontend"
    npm = shutil.which("npm.cmd" if shutil.which("npm.cmd") else "npm")
    if npm is None:
        raise SystemExit("未找到 npm，请安装 Node.js 20 或更高版本")
    subprocess.run([npm, "ci"], cwd=frontend, check=True)
    subprocess.run([npm, "run", "build"], cwd=frontend, check=True)

    target = ROOT / "app" / "web" / "dist"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(frontend / "dist", target)


if __name__ == "__main__":
    main()
