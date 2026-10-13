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
    send_manual_application_notification,
)


# ==========================================================
# SETTINGS
# ==========================================================

# False = real recruiter applications
# True  = do not send recruiter applications
DRY_RUN = True

# Maximum automatic recruiter-email applications
# in one execution.
MAX_APPLICATIONS_PER_RUN = 20

# Maximum successful automatic applications per day.
DAILY_APPLICATION_LIMIT = 20

# Maximum manual notifications sent to the user per run.
MAX_MANUAL_NOTIFICATIONS_PER_RUN = 20

LOCAL_TIMEZONE = ZoneInfo(
    "Asia/Kolkata"
)


# ==========================================================
# DAILY APPLICATION COUNT
# ==========================================================

def get_today_application_count():

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

    today = datetime.now(
        LOCAL_TIMEZONE
    ).date()

    count = 0

    for row in rows:

        applied_at = row[0]

        if not applied_at:
            continue

        try:

            timestamp = datetime.fromisoformat(
                applied_at
            )

            if timestamp.tzinfo is None:

                timestamp = (
                    timestamp.replace(
                        tzinfo=timezone.utc
                    )
                )

            local_date = (
                timestamp
                .astimezone(
                    LOCAL_TIMEZONE
                )
                .date()
            )

            if local_date == today:
                count += 1

        except ValueError:

            continue

    return count


# ==========================================================
# AUTOMATIC RECRUITER-EMAIL JOBS
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
          AND experience = 'Fresher / 0-1 year'
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
# MANUAL APPLICATION JOBS
# ==========================================================
def get_manual_application_jobs(limit):

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
            apply_method
        FROM jobs
        WHERE application_status = 'NOT_APPLIED'
          AND apply_url IS NOT NULL
          AND apply_url != ''
          AND apply_method IN (
              'GOOGLE_FORM',
              'CAREER_PAGE',
              'LINKEDIN_POST',
              'EXTERNAL_APPLICATION',
              'MANUAL_REVIEW'
          )
        ORDER BY posted_at DESC
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

def update_job_status(
    job_id,
    status,
):

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
            applied_at = COALESCE(
                ?,
                applied_at
            )
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
# MANUAL APPLICATION PROCESSING
# ==========================================================

def process_manual_applications():

    print()
    print("=" * 75)
    print("CHECKING MANUAL APPLICATIONS")
    print("=" * 75)

    jobs = get_manual_application_jobs(
        MAX_MANUAL_NOTIFICATIONS_PER_RUN
    )

    if not jobs:

        print()
        print(
            "No new manual application links found."
        )

        return 0

    notifications_sent = 0

    for job in jobs:

        (
            job_id,
            company,
            title,
            location,
            job_url,
            apply_url,
            apply_method,
        ) = job

        print()
        print("-" * 75)

        print(
            f"ID            : {job_id}"
        )

        print(
            f"Company       : {company}"
        )

        print(
            f"Role          : {title}"
        )

        print(
            f"Location      : {location}"
        )

        print(
            f"Method        : {apply_method}"
        )

        print(
            f"Application   : {apply_url}"
        )

        print(
            f"Job URL       : {job_url}"
        )

        try:

            send_manual_application_notification(
                company=company,
                role=title,
                location=location,
                apply_method=apply_method,
                application_url=apply_url,
                job_url=job_url,
            )

            # Prevent the same manual notification
            # from being sent again on every run.
            update_job_status(
                job_id,
                "REVIEW_REQUIRED",
            )

            notifications_sent += 1

            print()
            print(
                "Status: REVIEW_REQUIRED"
            )

        except Exception as error:

            # Leave it NOT_APPLIED so a future run
            # can retry the notification.
            print()
            print(
                "Manual notification failed:"
            )
            print(error)

    print()
    print(
        f"Manual notifications sent : "
        f"{notifications_sent}"
    )

    return notifications_sent


# ==========================================================
# AUTOMATIC RECRUITER APPLICATIONS
# ==========================================================

def process_email_applications():

    validate_profile()

    today_count = (
        get_today_application_count()
    )

    print()
    print("=" * 75)
    print("AUTOMATIC EMAIL APPLICATIONS")
    print("=" * 75)

    print(
        f"Applications today : "
        f"{today_count}/"
        f"{DAILY_APPLICATION_LIMIT}"
    )

    if (
        today_count
        >= DAILY_APPLICATION_LIMIT
    ):

        print()
        print(
            "Daily automatic application "
            "limit reached."
        )

        return 0

    remaining_today = (
        DAILY_APPLICATION_LIMIT
        - today_count
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

    jobs = get_pending_applications(
        applications_this_run
    )

    if not jobs:

        print()
        print(
            "No pending recruiter-email "
            "applications found."
        )

        return 0

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

        print(
            f"ID            : {job_id}"
        )

        print(
            f"Company       : {company}"
        )

        print(
            f"Role          : {title}"
        )

        print(
            f"Location      : {location}"
        )

        print(
            f"Recruiter     : {recruiter_email}"
        )

        print(
            f"Method        : {apply_method}"
        )

        print(
            f"Job URL       : {job_url}"
        )

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
                print(
                    "Status: READY"
                )

                print(
                    "No recruiter email was sent."
                )

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
                print(
                    "Status: APPLIED"
                )

                # ----------------------------------
                # Applicant confirmation
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
                        "Application was sent, "
                        "but confirmation email failed:"
                    )

                    print(
                        confirmation_error
                    )

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

    return successful_this_run


# ==========================================================
# MAIN
# ==========================================================

def main():

    print()
    print("=" * 75)
    print("APPLICATION PROCESSOR")
    print("=" * 75)

    # Manual notifications are independent of the
    # automatic 20/day application limit.
    try:

        manual_notifications = (
            process_manual_applications()
        )

    except Exception as error:

        print()
        print(
            "Manual application processing failed:"
        )

        print(error)

        manual_notifications = 0

    # Automatic recruiter applications.
    try:

        successful_applications = (
            process_email_applications()
        )

    except Exception as error:

        print()
        print(
            "Automatic application processing failed:"
        )

        print(error)

        successful_applications = 0

    print()
    print("=" * 75)
    print(
        "APPLICATION PROCESSING COMPLETE"
    )
    print("=" * 75)

    print(
        f"Automatic applications : "
        f"{successful_applications}"
    )

    print(
        f"Manual notifications   : "
        f"{manual_notifications}"
    )

    print("=" * 75)

    return successful_applications


if __name__ == "__main__":

    main()