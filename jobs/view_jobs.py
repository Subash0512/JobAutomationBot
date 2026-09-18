from jobs.database import get_connection


def main():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            company,
            title,
            location,
            experience,
            job_url,
            apply_url,
            source,
            application_status
        FROM jobs
        ORDER BY id DESC
        """
    )

    jobs = cursor.fetchall()

    connection.close()

    if not jobs:
        print("No jobs found in database.")
        return

    print()
    print("=" * 100)
    print("SAVED JOBS")
    print("=" * 100)

    for job in jobs:
        (
            job_id,
            company,
            title,
            location,
            experience,
            job_url,
            apply_url,
            source,
            status,
        ) = job

        print()
        print(f"ID          : {job_id}")
        print(f"Company     : {company}")
        print(f"Role        : {title}")
        print(f"Location    : {location}")
        print(f"Experience  : {experience}")
        print(f"Source      : {source}")
        print(f"Status      : {status}")
        print(f"Job URL     : {job_url}")
        print(f"Apply URL   : {apply_url or 'No direct application URL'}")
        print("-" * 100)


if __name__ == "__main__":
    main()