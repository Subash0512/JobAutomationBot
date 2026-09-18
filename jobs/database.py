import sqlite3
from pathlib import Path


DATABASE_PATH = Path("data/jobs.db")


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)


def create_tables():
    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            location TEXT,
            workplace_type TEXT,
            experience TEXT,
            job_url TEXT UNIQUE NOT NULL,
            apply_url TEXT,
            description TEXT,
            source TEXT,
            discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            application_status TEXT DEFAULT 'NOT_APPLIED'
        )
    """)

    connection.commit()
    connection.close()


if __name__ == "__main__":
    create_tables()
    print("Database created successfully.")