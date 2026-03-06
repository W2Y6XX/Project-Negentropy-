from pathlib import Path
import sqlite3


ROOT_DIR = Path(__file__).resolve().parent
DB_PATH = ROOT_DIR / "negentropy.db"
SCHEMA_PATH = ROOT_DIR / "database" / "schema.sql"
INIT_PATH = ROOT_DIR / "seed" / "init_self_model.json"


def ensure_required_files() -> None:
    missing = [str(path) for path in (SCHEMA_PATH, INIT_PATH) if not path.exists()]
    if missing:
        joined = ", ".join(missing)
        raise FileNotFoundError(f"Missing required foundation files: {joined}")


def recreate_database() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Removed existing database: {DB_PATH.name}")

    conn = sqlite3.connect(DB_PATH)
    try:
        with SCHEMA_PATH.open("r", encoding="utf-8") as schema_file:
            conn.executescript(schema_file.read())
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    ensure_required_files()
    recreate_database()
    print("Database schema initialized successfully.")
    print("Foundation build only: JSON seed import is intentionally deferred.")
    print(f"Schema source: {SCHEMA_PATH}")
    print(f"Retained for later tasks: {INIT_PATH}")


if __name__ == "__main__":
    main()
