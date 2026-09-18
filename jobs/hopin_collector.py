import re
import requests

from config import (
    JOB_ROLES,
    LOCATIONS,
    MAX_EXPERIENCE_YEARS,
    MAX_JOB_AGE_DAYS,
)

from jobs.database import get_connection


API_URL = "https://api.hopinjobs.com/api/jobs"


# ==========================================================
# JOB TITLE FILTERS
# ==========================================================

EXCLUDED_TITLE_WORDS = [
    "senior",
    "sr.",
    "sr ",
    "lead",
    "principal",
    "staff",
    "manager",
    "director",
    "head",
]


ROLE_KEYWORDS = [
    "software engineer",
    "software developer",
    "software development engineer",
    "sde",
    "java developer",
    "java backend",
    "backend developer",
    "spring boot",
    "full stack",
    "associate software",
    "junior software",
    "graduate engineer",
    "technical support",
    "technical support engineer",
    "technical support executive",
    "it support",
    "it support engineer",
    "desktop support",
    "application support",
    "production support",
    "l1 support",
    "service desk",
    "help desk",
    "system support",
    "software tester",
    "qa engineer",
    "junior qa",
    "test engineer",
    "automation test",
    "system engineer",
    "associate engineer",
    "it analyst",
    "application engineer",
    "technical associate",
]


# ==========================================================
# HELPERS
# ==========================================================

def normalize(value):
    return " ".join((value or "").lower().split())


# ==========================================================
# ROLE MATCHING
# ==========================================================

def role_matches(title):
    title_text = normalize(title)

    # Reject senior/management positions.
    for excluded in EXCLUDED_TITLE_WORDS:
        if excluded in title_text:
            return False

    # Check configured roles.
    for role in JOB_ROLES:
        if normalize(role) in title_text:
            return True

    # Check related roles.
    for keyword in ROLE_KEYWORDS:
        if keyword in title_text:
            return True

    return False


# ==========================================================
# LOCATION MATCHING
# ==========================================================

def location_matches(location):
    """
    Accept only:
        Chennai
        Hosur
        Bengaluru
        Bangalore
    """

    location_text = normalize(location)

    aliases = {
        "chennai": ["chennai"],
        "hosur": ["hosur"],
        "bengaluru": ["bengaluru", "bangalore"],
        "bangalore": ["bengaluru", "bangalore"],
    }

    for configured_location in LOCATIONS:

        configured = normalize(configured_location)

        for alias in aliases.get(
            configured,
            [configured],
        ):
            if alias in location_text:
                return True

    return False


# ==========================================================
# EXPERIENCE FILTER
# ==========================================================

def get_experience_info(job):
    """
    Returns:
        (True, experience_label)
        (False, rejection_reason)

    Target:
        Fresher / 0-1 year
    """

    title = normalize(job.get("title"))
    description = normalize(job.get("description"))

    criteria = job.get("criteria", [])

    if isinstance(criteria, list):
        criteria_text = normalize(
            " ".join(criteria)
        )
    else:
        criteria_text = normalize(criteria)

    preferred = job.get(
        "preferred_qualifications",
        [],
    )

    if isinstance(preferred, list):
        preferred_text = normalize(
            " ".join(preferred)
        )
    else:
        preferred_text = normalize(preferred)

    text = (
        f"{title} "
        f"{description} "
        f"{criteria_text} "
        f"{preferred_text}"
    )

    # ----------------------------------------------
    # Explicit senior-level rejection
    # ----------------------------------------------

    rejected_terms = [
        "senior",
        "sr.",
        "lead",
        "principal",
        "staff",
        "manager",
        "director",
    ]

    if any(
        term in text
        for term in rejected_terms
    ):
        return False, "Senior/management"

    # ----------------------------------------------
    # Experience ranges
    # ----------------------------------------------

    range_patterns = [
        r"(\d+)\s*-\s*(\d+)\s*years?",
        r"(\d+)\s*to\s*(\d+)\s*years?",
    ]

    for pattern in range_patterns:

        matches = re.findall(
            pattern,
            text,
        )

        for match in matches:

            minimum = int(match[0])
            maximum = int(match[1])

            if maximum > MAX_EXPERIENCE_YEARS:
                return False, f"{minimum}-{maximum} years"

    # ----------------------------------------------
    # X+ years
    # ----------------------------------------------

    plus_matches = re.findall(
        r"(\d+)\s*\+\s*years?",
        text,
    )

    for value in plus_matches:

        years = int(value)

        if years > MAX_EXPERIENCE_YEARS:
            return False, f"{years}+ years"

    # ----------------------------------------------
    # "X years of experience"
    # ----------------------------------------------

    single_year_matches = re.findall(
        r"(\d+)\s+years?\s+(?:of\s+)?experience",
        text,
    )

    for value in single_year_matches:

        years = int(value)

        if years > MAX_EXPERIENCE_YEARS:
            return False, f"{years}+ years"

    # ----------------------------------------------
    # Fresher indicators
    # ----------------------------------------------

    fresher_terms = [
        "fresher",
        "freshers",
        "entry level",
        "entry-level",
        "graduate",
        "trainee",
        "no experience",
        "0-1 year",
        "0 to 1 year",
        "0 year",
        "1 year",
    ]

    if any(
        term in text
        for term in fresher_terms
    ):
        return True, "Fresher / 0-1 year"

    # Hopin's feed is entry-level oriented.
    return True, "Entry-level / experience not stated"


# ==========================================================
# APPLICATION URL
# ==========================================================

def get_application_url(job):

    if job.get("apply_form_url"):
        return job.get("apply_form_url")

    if job.get("apply_url"):
        return job.get("apply_url")

    return ""


# ==========================================================
# APPLICATION METHOD
# ==========================================================

def get_apply_method(job):

    if job.get("apply_form_url"):
        return "DIRECT_FORM"

    if job.get("recruiter_email"):
        return "RECRUITER_EMAIL"

    apply_url = job.get("apply_url") or ""

    if "linkedin.com" in apply_url.lower():
        return "LINKEDIN_POST"

    if apply_url:
        return "EXTERNAL_URL"

    return "UNKNOWN"


# ==========================================================
# SAVE / UPDATE JOB
# ==========================================================

def save_job(job, experience_label):
    """
    Insert a new job or update an existing job.

    Returns:
        True  -> new job inserted
        False -> job already existed
    """

    job_id = job.get("id", "")

    application_url = get_application_url(job)

    job_url = (
        f"https://hopinjobs.com/jobs/{job_id}"
        if job_id
        else application_url
    )

    apply_method = get_apply_method(job)

    connection = get_connection()
    cursor = connection.cursor()

    # Check whether the job already exists.
    cursor.execute(
        """
        SELECT id
        FROM jobs
        WHERE job_url = ?
        LIMIT 1
        """,
        (job_url,),
    )

    existing = cursor.fetchone()

    if existing:
        was_existing = True
    else:
        was_existing = False

    cursor.execute(
        """
        INSERT INTO jobs (
            company,
            title,
            location,
            workplace_type,
            experience,
            job_url,
            apply_url,
            description,
            source,
            recruiter_email,
            apply_method,
            posted_at,
            posted_days,
            is_active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(job_url) DO UPDATE SET
            company = excluded.company,
            title = excluded.title,
            location = excluded.location,
            workplace_type = excluded.workplace_type,
            experience = excluded.experience,
            apply_url = excluded.apply_url,
            description = excluded.description,
            source = excluded.source,
            recruiter_email = excluded.recruiter_email,
            apply_method = excluded.apply_method,
            posted_at = excluded.posted_at,
            posted_days = excluded.posted_days,
            is_active = excluded.is_active
        """,
        (
            job.get("company", "Unknown"),
            job.get("title", "Unknown"),
            job.get("location", "Unknown"),
            job.get("work_type", "Unknown"),
            experience_label,
            job_url,
            application_url,
            job.get("description", ""),
            "Hopin",
            job.get("recruiter_email"),
            apply_method,
            job.get("posted_at"),
            job.get("posted_days"),
            1 if job.get("is_active", True) else 0,
        ),
    )

    connection.commit()
    connection.close()

    return not was_existing


# ==========================================================
# COLLECT JOBS
# ==========================================================

def collect_jobs():

    print()
    print("Fetching Hopin job feed...")
    print("-" * 75)

    # ----------------------------------------------
    # API request
    # ----------------------------------------------

    try:

        response = requests.get(
            API_URL,
            params={
                "is_unofficial": "true",
            },
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

    except requests.RequestException as error:

        print()
        print("ERROR: Could not connect to Hopin.")
        print(error)

        # Always return 3 values so main.py
        # can handle an API failure safely.
        return 0, 0, 0

    # ----------------------------------------------
    # Get jobs
    # ----------------------------------------------

    jobs = data.get("jobs", [])

    print(
        f"Jobs received: {len(jobs)}"
    )

    print()

    matched_jobs = 0
    new_jobs = 0

    # ----------------------------------------------
    # Process every job
    # ----------------------------------------------

    for job in jobs:

        title = job.get("title", "")
        location = job.get("location", "")

        # ------------------------------------------
        # Active job
        # ------------------------------------------

        if not job.get(
            "is_active",
            True,
        ):
            continue

        # ------------------------------------------
        # Role filter
        # ------------------------------------------

        if not role_matches(title):
            continue

        # ------------------------------------------
        # Location filter
        # ------------------------------------------

        if not location_matches(location):
            continue

        # ------------------------------------------
        # Freshness filter
        # ------------------------------------------

        posted_days = job.get(
            "posted_days"
        )

        if posted_days is not None:

            try:

                posted_days_value = int(
                    posted_days
                )

                if (
                    posted_days_value
                    > MAX_JOB_AGE_DAYS
                ):
                    continue

            except (
                TypeError,
                ValueError,
            ):
                pass

        # ------------------------------------------
        # Experience filter
        # ------------------------------------------

        suitable, experience_label = (
            get_experience_info(job)
        )

        if not suitable:
            continue

        # ------------------------------------------
        # Scam filter
        # ------------------------------------------

        scam_verdict = normalize(
            job.get(
                "scam_verdict",
                "",
            )
        )

        if (
            scam_verdict
            and scam_verdict != "clean"
        ):
            continue

        # ------------------------------------------
        # Matching job
        # ------------------------------------------

        matched_jobs += 1

        inserted = save_job(
            job,
            experience_label,
        )

        if inserted:
            new_jobs += 1

        # ------------------------------------------
        # Display
        # ------------------------------------------

        print("=" * 75)

        print(
            f"Company        : "
            f"{job.get('company', 'Unknown')}"
        )

        print(
            f"Role           : "
            f"{title}"
        )

        print(
            f"Location       : "
            f"{location}"
        )

        print(
            f"Work type      : "
            f"{job.get('work_type', 'Unknown')}"
        )

        print(
            f"Role type      : "
            f"{job.get('role_type', 'Unknown')}"
        )

        print(
            f"Experience     : "
            f"{experience_label}"
        )

        print(
            f"Posted         : "
            f"{job.get('posted_at', 'Unknown')}"
        )

        print(
            f"Posted days    : "
            f"{job.get('posted_days', 'Unknown')}"
        )

        print(
            f"Scam verdict   : "
            f"{job.get('scam_verdict', 'Unknown')}"
        )

        print(
            f"Recruiter mail : "
            f"{job.get('recruiter_email', 'None')}"
        )

        print(
            f"Apply method   : "
            f"{get_apply_method(job)}"
        )

        print(
            f"Apply URL      : "
            f"{get_application_url(job) or 'None'}"
        )

        print("=" * 75)

    # ----------------------------------------------
    # Summary
    # ----------------------------------------------

    print()
    print("COLLECTION COMPLETED")
    print("-" * 75)

    print(
        f"Matching jobs : {matched_jobs}"
    )

    print(
        f"New jobs saved: {new_jobs}"
    )

    # IMPORTANT:
    # main.py uses these values for the
    # daily summary email.
    return (
        len(jobs),
        matched_jobs,
        new_jobs,
    )


# ==========================================================
# DIRECT EXECUTION
# ==========================================================

if __name__ == "__main__":
    collect_jobs()