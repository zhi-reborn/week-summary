import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def main() -> None:
    from app.config import Settings
    from app.migrations import run_migrations

    backup_path = run_migrations(Settings())
    if backup_path is None:
        print("MIGRATION_OK backup=not_required")
    else:
        print(f"MIGRATION_OK backup={backup_path}")


if __name__ == "__main__":
    main()
