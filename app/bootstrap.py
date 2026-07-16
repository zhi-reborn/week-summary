import uvicorn

from app.config import Settings
from app.main import create_app
from app.migrations import run_migrations


def main() -> None:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    run_migrations(settings)
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
