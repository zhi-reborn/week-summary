# mypy: ignore-errors
import os
import subprocess
import sys
from pathlib import Path

if os.name == "nt":
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil


    class WeeklyReportWindowsService(win32serviceutil.ServiceFramework):
        _svc_name_ = "WeeklyReportAssistant"
        _svc_display_name_ = "智能周报汇总系统"
        _svc_description_ = "汇总 TXT 周报并按 Word 模板生成团队周报。"

        def __init__(self, args):
            super().__init__(args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)
            self._process = None
            self._stopping = False

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self._stopping = True
            win32event.SetEvent(self._stop_event)
            if self._process is not None and self._process.poll() is None:
                self._process.terminate()

        def SvcDoRun(self):
            servicemanager.LogInfoMsg("WeeklyReportAssistant service starting")
            install_dir = Path(sys.executable).resolve().parent
            data_dir = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / (
                "WeeklyReportAssistant"
            )
            environment = os.environ.copy()
            environment.update(
                {
                    "WRA_DATA_DIR": str(data_dir),
                    "WRA_LOG_DIR": str(data_dir / "logs"),
                    "WRA_HOST": "127.0.0.1",
                    "WRA_PORT": "8765",
                }
            )
            self._process = subprocess.Popen(
                [sys.executable, "--run-server"],
                cwd=install_dir,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            while self._process.poll() is None:
                if win32event.WaitForSingleObject(self._stop_event, 1000) == win32event.WAIT_OBJECT_0:
                    break
            if self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            return_code = self._process.wait()
            if not self._stopping:
                servicemanager.LogErrorMsg(
                    f"WeeklyReportAssistant server exited with code {return_code}"
                )
                raise RuntimeError(f"server exited with code {return_code}")
            servicemanager.LogInfoMsg("WeeklyReportAssistant service stopped")


def run_windows_service_command(arguments: list[str]) -> None:
    if os.name != "nt":
        raise RuntimeError("Windows 服务命令只能在 Windows 上运行")
    sys.argv = [sys.argv[0], *arguments]
    win32serviceutil.HandleCommandLine(WeeklyReportWindowsService)
