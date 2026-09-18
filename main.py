from jobs.hopin_collector import collect_jobs
from applications.email_apply import main as apply_jobs
from notifications.email import send_daily_summary


DAILY_APPLICATION_LIMIT = 3


def main():
    print("=" * 75)
    print("JOB AUTOMATION BOT STARTED")
    print("=" * 75)

    jobs_received = 0
    matching_jobs = 0
    new_jobs = 0
    applications_sent = 0
    errors = 0

    # ==========================================================
    # STEP 1: COLLECT JOBS
    # ==========================================================

    print()
    print("[1/2] Collecting jobs...")

    try:
        result = collect_jobs()

        if result is not None:
            (
                jobs_received,
                matching_jobs,
                new_jobs,
            ) = result

    except Exception as error:
        print()
        print("Job collection failed:")
        print(error)

        errors += 1

    # ==========================================================
    # STEP 2: PROCESS APPLICATIONS
    # ==========================================================

    print()
    print("[2/2] Processing applications...")

    try:
        result = apply_jobs()

        if result is not None:
            applications_sent = result

    except Exception as error:
        print()
        print("Application processing failed:")
        print(error)

        errors += 1

    # ==========================================================
    # STEP 3: SEND DAILY SUMMARY
    # ==========================================================

    print()
    print("Sending daily summary...")

    try:
        send_daily_summary(
            jobs_received=jobs_received,
            matching_jobs=matching_jobs,
            new_jobs=new_jobs,
            applications_sent=applications_sent,
            daily_limit=DAILY_APPLICATION_LIMIT,
            errors=errors,
        )

    except Exception as error:
        print()
        print("Daily summary email failed:")
        print(error)

        errors += 1

    # ==========================================================
    # FINAL MESSAGE
    # ==========================================================

    print()
    print("=" * 75)
    print("JOB AUTOMATION BOT FINISHED")
    print("=" * 75)


if __name__ == "__main__":
    main()