import os
import sys

import uvicorn

from app.application.analysis_pipeline import AnalysisPipeline
from app.application.export_service import ExportService
from app.application.settings_service import SettingsService
from app.application.startup_recovery import StartupRecovery
from app.config import Settings
from app.core.logging import close_logging, configure_logging
from app.infrastructure.files.task_storage import TaskStorage
from app.infrastructure.jobs.runner import AnalysisRunner
from app.infrastructure.llm.client import OpenAICompatibleClient
from app.main import create_app
from app.migrations import run_migrations


def main() -> None:
    arguments = sys.argv[1:]
    if os.name == "nt" and arguments[:1] == ["--service"]:
        from app.windows_service import run_windows_service_command

        run_windows_service_command(arguments[1:])
        return

    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(settings.log_dir)
    if arguments[:1] == ["--migrate"]:
        try:
            backup_path = run_migrations(settings)
            backup = str(backup_path) if backup_path is not None else "not_required"
            print(f"MIGRATION_OK backup={backup}")
        finally:
            close_logging()
        return
    run_migrations(settings)
    application = create_app(settings)

    def create_llm() -> OpenAICompatibleClient:
        model, api_key = SettingsService(settings.data_dir).load_client_values()
        return OpenAICompatibleClient(
            base_url=str(model.base_url),
            model=model.model,
            api_key=api_key,
            timeout_seconds=model.timeout_seconds,
            temperature=model.temperature,
            max_retries=model.max_retries,
        )

    pipeline = AnalysisPipeline(
        application.state.session_factory,
        TaskStorage(settings.data_dir),
        create_llm,
    )
    runner = AnalysisRunner(application.state.session_factory, pipeline)
    StartupRecovery(
        application.state.session_factory,
        TaskStorage(settings.data_dir),
        ExportService(
            application.state.session_factory,
            TaskStorage(settings.data_dir),
        ).export,
        settings.max_recovery_attempts,
    ).run()
    application.state.llm_factory = create_llm
    application.state.runner = runner
    runner.start()
    try:
        uvicorn.run(application, host=settings.host, port=settings.port)
    finally:
        runner.stop()
        close_logging()


if __name__ == "__main__":
    main()
