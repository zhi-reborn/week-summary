"""PyInstaller Windows service entry; the bundled app uses app.windows_service directly."""

import sys

from app.windows_service import run_windows_service_command


if __name__ == "__main__":
    run_windows_service_command(sys.argv[1:])
