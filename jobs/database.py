import sqlite3
from pathlib import Path


DATABASE_PATH = Path(
    "data/jobs.db"
)


def get_connection():

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return sqlite3.connect(
        DATABASE_PATH
    )


def create_tables():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
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

            discovered_at TEXT
                DEFAULT CURRENT_TIMESTAMP,

            application_status TEXT
                DEFAULT 'NOT_APPLIED',

            recruiter_email TEXT,

            apply_method TEXT,

            applied_at TEXT,

            posted_at TEXT,

            posted_days INTEGER,

            is_active INTEGER
                DEFAULT 1
        )
        """
    )

    # ======================================================
    # MIGRATION
    # ======================================================

    existing_columns = {
        row[1]
        for row in cursor.execute(
            "PRAGMA table_info(jobs)"
        ).fetchall()
    }

    missing_columns = {
        "recruiter_email": "TEXT",
        "apply_method": "TEXT",
        "applied_at": "TEXT",
        "posted_at": "TEXT",
        "posted_days": "INTEGER",
        "is_active": "INTEGER DEFAULT 1",
    }

    for column, definition in (
        missing_columns.items()
    ):

        if column not in existing_columns:

            cursor.execute(
                f"ALTER TABLE jobs "
                f"ADD COLUMN {column} "
                f"{definition}"
            )

    connection.commit()
    connection.close()


if __name__ == "__main__":

    create_tables()

    print(
        "Database created/migrated successfully."
    )