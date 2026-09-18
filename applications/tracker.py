from jobs.database import get_connection


def create_application_table():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            location TEXT,
            job_url TEXT UNIQUE NOT NULL,
            application_url TEXT,
            status TEXT NOT NULL DEFAULT 'FOUND',
            applied_at TEXT,
            notes TEXT
        )
        """
    )

    connection.commit()
    connection.close()


def already_applied(job_url):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT 1
        FROM applications
        WHERE job_url = ?
        LIMIT 1
        """,
        (job_url,),
    )

    result = cursor.fetchone()
    connection.close()

    return result is not None


def record_application(
    company,
    title,
    location,
    job_url,
    application_url=None,
    status="FOUND",
    notes=None,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO applications (
            company,
            title,
            location,
            job_url,
            application_url,
            status,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company,
            title,
            location,
            job_url,
            application_url,
            status,
            notes,
        ),
    )

    connection.commit()
    connection.close()


if __name__ == "__main__":
    create_application_table()
    print("Application tracker is ready.")