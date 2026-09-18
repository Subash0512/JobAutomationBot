from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from applications.profile import (
    FULL_NAME,
    RESUME_PATH,
    validate_profile,
)

from jobs.database import get_connection

from notifications.email import (
    send_application,
    send_application_confirmation,
)


# ==========================================================
# SETTINGS
# ==========================================================

# False = send real applications
# True  = test only
DRY_RUN = False

# Maximum applications in one bot execution
MAX_APPLICATIONS_PER_RUN = 3

# Maximum successful applications per calendar day
DAILY_APPLICATION_LIMIT = 3

# User's local timezone
LOCAL_TIMEZONE = ZoneInfo("Asia/Kolkata")


# ==========================================================
# DAILY APPLICATION COUNT
# ==========================================================

def get_today_application_count():
    """
    Count successful applications made today in India time.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT applied_at
        FROM jobs
        WHERE application_status = 'APPLIED'
          AND applied_at IS NOT NULL
        """
    )

    rows = cursor.fetchall()

    connection.close()

    today = datetime.now(LOCAL_TIMEZONE).date()

    count = 0

    for row in rows:

        applied_at = row[0]

        if not applied_at:
            continue

        try:
            timestamp = datetime.fromisoformat(applied_at)

            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(
                    tzinfo=timezone.utc
                )

            local_date = timestamp.astimezone(
                LOCAL_TIMEZONE
            ).date()

            if local_date == today:
                count += 1

        except ValueError:
            continue

    return count


# ==========================================================
# GET PENDING JOBS
# ==========================================================

def get_pending_applications(limit):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            company,
            title,
            location,
            job_url,
            apply_url,
            recruiter_email,
            apply_method
        FROM jobs
        WHERE application_status IN ('NOT_APPLIED', 'READY')
          AND recruiter_email IS NOT NULL
          AND recruiter_email != ''
          AND apply_method = 'RECRUITER_EMAIL'
        ORDER BY
            CASE
                WHEN application_status = 'READY' THEN 0
                ELSE 1
            END,
            posted_at DESC
        LIMIT ?
        """,
        (limit,),
    )

    jobs = cursor.fetchall()

    connection.close()

    return jobs


# ==========================================================
# UPDATE STATUS
# ==========================================================

def update_job_status(job_id, status):
    connection = get_connection()
    cursor = connection.cursor()

    applied_at = None

    if status == "APPLIED":
        applied_at = datetime.now(
            timezone.utc
        ).isoformat()

    cursor.execute(
        """
        UPDATE jobs
        SET
            application_status = ?,
            applied_at = COALESCE(?, applied_at)
        WHERE id = ?
        """,
        (
            status,
            applied_at,
            job_id,
        ),
    )

    connection.commit()
    connection.close()


# ==========================================================
# MAIN
# ==========================================================

def main():

    validate_profile()

    # ----------------------------------------------
    # Check today's application count
    # ----------------------------------------------

    today_count = get_today_application_count()

    print()
    print("=" * 75)
    print("JOB APPLICATION RUNNER")
    print("=" * 75)

    print(
        f"Applications today : "
        f"{today_count}/{DAILY_APPLICATION_LIMIT}"
    )

    if today_count >= DAILY_APPLICATION_LIMIT:

        print()
        print(
            "Daily application limit reached."
        )
        print(
            "No applications will be sent today."
        )
        print("=" * 75)

        return

    # ----------------------------------------------
    # Calculate remaining capacity
    # ----------------------------------------------

    remaining_today = (
        DAILY_APPLICATION_LIMIT - today_count
    )

    applications_this_run = min(
        MAX_APPLICATIONS_PER_RUN,
        remaining_today,
    )

    print(
        f"Available today    : "
        f"{remaining_today}"
    )

    print(
        f"Allowed this run   : "
        f"{applications_this_run}"
    )

    # ----------------------------------------------
    # Get pending jobs
    # ----------------------------------------------

    jobs = get_pending_applications(
        applications_this_run
    )

    if not jobs:

        print()
        print(
            "No pending email applications found."
        )
        print("=" * 75)

        return

    # ----------------------------------------------
    # Process jobs
    # ----------------------------------------------

    successful_this_run = 0

    for job in jobs:

        (
            job_id,
            company,
            title,
            location,
            job_url,
            apply_url,
            recruiter_email,
            apply_method,
        ) = job

        print()
        print("-" * 75)
        print(f"ID            : {job_id}")
        print(f"Company       : {company}")
        print(f"Role          : {title}")
        print(f"Location      : {location}")
        print(f"Recruiter     : {recruiter_email}")
        print(f"Method        : {apply_method}")
        print(f"Job URL       : {job_url}")

        try:

            sent = send_application(
                recruiter_email=recruiter_email,
                company=company,
                role=title,
                location=location,
                applicant_name=FULL_NAME,
                resume_path=RESUME_PATH,
                job_url=job_url,
                dry_run=DRY_RUN,
            )

            # --------------------------------------
            # DRY RUN
            # --------------------------------------

            if DRY_RUN:

                update_job_status(
                    job_id,
                    "READY",
                )

                print()
                print("Status: READY")
                print("No email was sent.")

            # --------------------------------------
            # REAL APPLICATION
            # --------------------------------------

            elif sent:

                update_job_status(
                    job_id,
                    "APPLIED",
                )

                successful_this_run += 1

                print()
                print("Status: APPLIED")

                # ----------------------------------
                # Send confirmation to applicant
                # ----------------------------------

                try:

                    send_application_confirmation(
                        company=company,
                        role=title,
                        location=location,
                        recruiter_email=recruiter_email,
                        job_url=job_url,
                        status="APPLIED",
                    )

                except Exception as confirmation_error:

                    print()
                    print(
                        "Application was sent, but "
                        "confirmation email failed:"
                    )

                    print(confirmation_error)

            # --------------------------------------
            # Unexpected result
            # --------------------------------------

            else:

                print()
                print(
                    "Application was not sent."
                )

        except Exception as error:

            update_job_status(
                job_id,
                "ERROR",
            )

            print()
            print(
                "Application failed:"
            )
            print(error)

    # ----------------------------------------------
    # Final summary
    # ----------------------------------------------

    final_today_count = (
        get_today_application_count()
    )

    print()
    print("=" * 75)

    if DRY_RUN:

        print("DRY RUN COMPLETE")
        print("NO APPLICATIONS WERE SENT")

    else:

        print("APPLICATION RUN COMPLETE")
        print(
            f"Successful this run : "
            f"{successful_this_run}"
        )
        print(
            f"Applications today  : "
            f"{final_today_count}/"
            f"{DAILY_APPLICATION_LIMIT}"
        )

    print("=" * 75)


if __name__ == "__main__":
    main()