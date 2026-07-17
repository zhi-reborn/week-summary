import uvicorn

from app.application.analysis_pipeline import AnalysisPipeline
from app.application.settings_service import SettingsService
from app.config import Settings
from app.infrastructure.files.task_storage import TaskStorage
from app.infrastructure.jobs.runner import AnalysisRunner
from app.infrastructure.llm.client import OpenAICompatibleClient
from app.main import create_app
from app.migrations import run_migrations


def main() -> None:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
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
        )

    pipeline = AnalysisPipeline(
        application.state.session_factory,
        TaskStorage(settings.data_dir),
        create_llm,
    )
    runner = AnalysisRunner(application.state.session_factory, pipeline)
    application.state.llm_factory = create_llm
    application.state.runner = runner
    runner.start()
    try:
        uvicorn.run(application, host=settings.host, port=settings.port)
    finally:
        runner.stop()


if __name__ == "__main__":
    main()
