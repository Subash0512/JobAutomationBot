import os
import re
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from config import (
    JOB_ROLES,
    LOCATIONS,
    MAX_EXPERIENCE_YEARS,
    MAX_JOB_AGE_DAYS,
)

from jobs.database import get_connection


# ==========================================================
# JOOBLE SETTINGS
# ==========================================================

load_dotenv()

JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY")

JOOBLE_API_URL = (
    f"https://in.jooble.org/api/{JOOBLE_API_KEY}"
    if JOOBLE_API_KEY
    else ""
)

# Six requests per run: three locations x two searches.
# Keep this low because the free key has a limited quota.
MAX_API_REQUESTS_PER_RUN = 6
RESULTS_PER_REQUEST = 10
REQUEST_TIMEOUT = 30


# ==========================================================
# ROLE FILTERS
# ==========================================================

EXCLUDED_TITLE_WORDS = [
    "senior",
    "sr.",
    "lead",
    "principal",
    "staff",
    "manager",
    "director",
    "head",
    "architect",
]


ROLE_KEYWORDS = [
    # Software development
    "software engineer",
    "software developer",
    "software development engineer",
    "sde",
    "java developer",
    "java engineer",
    "java backend",
    "backend developer",
    "spring boot",
    "full stack",
    "full-stack",
    "associate software",
    "junior software",
    "graduate engineer",
    "graduate software",

    # Python development
    "python developer",
    "python engineer",
    "junior python developer",
    "python backend",
    "django developer",
    "flask developer",

    # Data
    "data analyst",
    "junior data analyst",
    "business data analyst",
    "data analytics",
    "data engineer",
    "junior data engineer",

    # Technical / IT support
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
    "technical associate",

    # Testing / QA
    "software tester",
    "qa engineer",
    "junior qa",
    "test engineer",
    "automation test",
    "qa tester",
    "quality analyst",

    # Other entry-level IT
    "system engineer",
    "associate engineer",
    "it analyst",
    "application engineer",
]


# ==========================================================
# SEARCH GROUPS
# ==========================================================

# These are strings, not one-element tuples.

SEARCH_GROUPS = [
    (
        "fresher junior entry level graduate trainee "
        "software developer java developer python developer "
        "backend full stack software engineer SDE"
    ),
    (
        "fresher junior entry level graduate trainee "
        "data analyst technical support IT support "
        "QA tester test engineer system engineer "
        "application support"
    ),
]


# ==========================================================
# GENERAL HELPERS
# ==========================================================

def normalize(value):
    return " ".join(
        str(value or "").lower().split()
    )


def clean_text(value):
    return str(value or "").strip()


# ==========================================================
# LOCATION SEARCH
# ==========================================================

def get_api_locations():
    """
    Avoid duplicate searches for Bangalore and Bengaluru.
    """

    locations = []
    seen = set()

    for location in LOCATIONS:

        value = normalize(location)

        if value in ("bengaluru", "bangalore"):
            canonical = "Bengaluru"

        elif value == "chennai":
            canonical = "Chennai"

        elif value == "hosur":
            canonical = "Hosur"

        else:
            canonical = clean_text(location)

        key = normalize(canonical)

        if key and key not in seen:
            seen.add(key)
            locations.append(canonical)

    return locations


# ==========================================================
# ROLE MATCHING
# ==========================================================

def role_matches(title):

    title_text = normalize(title)

    # Reject senior and management titles.
    for excluded in EXCLUDED_TITLE_WORDS:

        if excluded in title_text:
            return False

    # Check roles configured in config.py.
    for role in JOB_ROLES:

        role_text = normalize(role)

        if role_text and role_text in title_text:
            return True

    # Check our additional role keywords.
    for keyword in ROLE_KEYWORDS:

        if normalize(keyword) in title_text:
            return True

    return False


# ==========================================================
# LOCATION MATCHING
# ==========================================================

def location_matches(location):

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

            if alias and alias in location_text:
                return True

    return False


# ==========================================================
# EXPERIENCE FILTER
# ==========================================================

def get_experience_info(job):
    """
    Returns:
        (False, reason)
            Confirmed unsuitable or experienced role.

        (True, "Fresher / 0-1 year")
            Explicit evidence of entry-level suitability.

        (True, "Experience not stated - manual review")
            Experience unclear. Keep for review, not auto-apply.
    """

    title = normalize(job.get("title"))
    snippet = normalize(job.get("snippet"))

    text = f"{title} {snippet}"

    # ------------------------------------------------------
    # Reject senior / management titles.
    # ------------------------------------------------------

    if any(
        term in title
        for term in EXCLUDED_TITLE_WORDS
    ):
        return False, "Senior/management title"

    if re.search(
        r"\b(experienced professional|"
        r"experienced candidate|"
        r"experienced developer)\b",
        text,
    ):
        return False, "Experienced role"

    # ------------------------------------------------------
    # Explicit experience ranges, e.g. 2-4 years.
    # ------------------------------------------------------

    range_patterns = [
        r"(\d+)\s*-\s*(\d+)\s*years?",
        r"(\d+)\s+to\s+(\d+)\s*years?",
    ]

    for pattern in range_patterns:

        for minimum, maximum in re.findall(
            pattern,
            text,
        ):

            minimum = int(minimum)
            maximum = int(maximum)

            if maximum > MAX_EXPERIENCE_YEARS:

                return (
                    False,
                    f"Requires {minimum}-{maximum} years",
                )

    # ------------------------------------------------------
    # Requirements such as 2+ years or 3+ years.
    #
    # "1+ years" is not treated as proof of a fresher role.
    # ------------------------------------------------------

    plus_matches = re.findall(
        r"(\d+)\s*\+\s*years?",
        text,
    )

    for value in plus_matches:

        years = int(value)

        if years >= MAX_EXPERIENCE_YEARS:

            return (
                False,
                f"Requires {years}+ years",
            )

    # ------------------------------------------------------
    # Requirements such as:
    # 2 years of experience
    # minimum 3 years
    # at least 2 years
    # ------------------------------------------------------

    experience_patterns = [
        r"(\d+)\s+years?\s+of\s+experience",
        r"(\d+)\s+years?\s+experience",
        r"minimum\s+(\d+)\s+years?",
        r"at\s+least\s+(\d+)\s+years?",
        r"minimum\s+of\s+(\d+)\s+years?",
    ]

    for pattern in experience_patterns:

        for value in re.findall(
            pattern,
            text,
        ):

            years = int(value)

            if years > MAX_EXPERIENCE_YEARS:

                return (
                    False,
                    f"Requires {years}+ years",
                )

    # ------------------------------------------------------
    # Explicit fresher / entry-level indicators.
    # ------------------------------------------------------

    fresher_terms = [
        "fresher",
        "freshers",
        "fresh graduate",
        "recent graduate",
        "entry level",
        "entry-level",
        "graduate trainee",
        "trainee",
        "junior",
        "no experience",
        "without experience",
        "experience not required",
        "0-1 year",
        "0 to 1 year",
        "0-1 years",
        "0 to 1 years",
    ]

    if any(
        term in text
        for term in fresher_terms
    ):

        return True, "Fresher / 0-1 year"

    # ------------------------------------------------------
    # Explicit zero/one-year experience.
    # ------------------------------------------------------

    zero_one_patterns = [
        r"\b0\s*years?\b",
        r"\b1\s*year\b",
        r"\b0\s*-\s*1\s*years?\b",
        r"\b0\s+to\s+1\s*years?\b",
    ]

    for pattern in zero_one_patterns:

        if re.search(pattern, text):

            return True, "Fresher / 0-1 year"

    # ------------------------------------------------------
    # Unknown experience: do not assume it is a fresher job.
    # ------------------------------------------------------

    return (
        True,
        "Experience not stated - manual review",
    )


# ==========================================================
# DATE HANDLING
# ==========================================================

def parse_updated_date(value):

    if not value:
        return None

    text = str(value).strip()

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:

        parsed = datetime.fromisoformat(text)

    except ValueError:

        # Some APIs return more than six fractional digits.
        trimmed = re.sub(
            r"(\.\d{6})\d+",
            r"\1",
            text,
        )

        try:
            parsed = datetime.fromisoformat(trimmed)

        except ValueError:
            return None

    if parsed.tzinfo is None:

        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def get_age_days(updated):

    parsed = parse_updated_date(updated)

    if parsed is None:
        return None

    seconds = (
        datetime.now(timezone.utc) - parsed
    ).total_seconds()

    return max(seconds / 86400, 0)


def is_fresh(updated):

    age = get_age_days(updated)

    # We cannot confirm freshness if no usable timestamp exists.
    if age is None:
        return False

    return age <= MAX_JOB_AGE_DAYS


# ==========================================================
# URL AND EMAIL EXTRACTION
# ==========================================================

URL_PATTERN = re.compile(
    r"https?://[^\s<>\"]+",
    re.IGNORECASE,
)


def extract_urls(text):

    if not text:
        return []

    urls = []

    for url in URL_PATTERN.findall(str(text)):

        url = url.rstrip(
            ".,);]}"
        )

        if url not in urls:
            urls.append(url)

    return urls


def extract_recruiter_email(snippet):

    match = re.search(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        snippet or "",
        re.IGNORECASE,
    )

    if match:
        return match.group(0)

    return ""


# ==========================================================
# APPLICATION METHOD CLASSIFICATION
# ==========================================================

def classify_application(snippet, source):
    """
    Returns:
        (application_method, destination)

    The destination may be empty when Jooble gives us
    only the source domain, not the employer application URL.
    """

    source_text = normalize(source)
    urls = extract_urls(snippet)

    # ------------------------------------------------------
    # Google Forms
    # ------------------------------------------------------

    for url in urls:

        lower_url = url.lower()

        if (
            "docs.google.com/forms" in lower_url
            or "forms.gle" in lower_url
        ):

            return "GOOGLE_FORM", url

    # ------------------------------------------------------
    # Recruiter email
    # ------------------------------------------------------

    email = extract_recruiter_email(snippet)

    if email:
        return "RECRUITER_EMAIL", email

    # ------------------------------------------------------
    # LinkedIn
    # ------------------------------------------------------

    if "linkedin" in source_text:
        return "LINKEDIN_POST", ""

    # ------------------------------------------------------
    # Common career platforms
    # ------------------------------------------------------

    career_sources = (
        "greenhouse",
        "lever.co",
        "workday",
        "myworkdayjobs",
        "ashby",
        "smartrecruiters",
        "jobvite",
        "icims",
        "successfactors",
        "oraclecloud",
    )

    if any(
        platform in source_text
        for platform in career_sources
    ):

        return "CAREER_PAGE", ""

    # ------------------------------------------------------
    # Career URLs visible in the job snippet
    # ------------------------------------------------------

    career_keywords = (
        "/careers",
        "/career",
        "/jobs",
        "/job/",
        "careers.",
        "jobs.",
    )

    for url in urls:

        lower_url = url.lower()

        if any(
            keyword in lower_url
            for keyword in career_keywords
        ):

            return "CAREER_PAGE", url

    # ------------------------------------------------------
    # Other external URLs
    # ------------------------------------------------------

    if urls:
        return "EXTERNAL_APPLICATION", urls[0]

    return "UNKNOWN", ""


# ==========================================================
# JOOBLE API REQUEST
# ==========================================================

def search_jooble(keywords, location):

    if not JOOBLE_API_KEY:

        raise ValueError(
            "JOOBLE_API_KEY is missing from .env"
        )

    response = requests.post(
        JOOBLE_API_URL,
        json={
            "keywords": keywords,
            "location": location,
            "page": 1,
            "ResultOnPage": RESULTS_PER_REQUEST,
            "companysearch": False,
        },
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code == 403:

        raise RuntimeError(
            "Jooble rejected the API key (HTTP 403)."
        )

    if not response.ok:

        raise RuntimeError(
            f"Jooble HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )

    data = response.json()

    if not isinstance(data, dict):

        raise RuntimeError(
            "Unexpected Jooble response format."
        )

    return data


# ==========================================================
# SAVE / UPDATE JOB
# ==========================================================

def save_job(
    job,
    experience_label,
    apply_method,
    apply_url,
    recruiter_email,
):
    """
    Insert a new job or refresh an existing one.

    Existing application_status values are preserved.
    Returns True only when a new record is inserted.
    """

    job_url = clean_text(
        job.get("link")
    )

    if not job_url:
        return False

    updated = clean_text(
        job.get("updated")
    )

    age = get_age_days(updated)

    posted_days = (
        int(age)
        if age is not None
        else None
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM jobs
        WHERE job_url = ?
        LIMIT 1
        """,
        (job_url,),
    )

    was_existing = cursor.fetchone() is not None

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
            clean_text(job.get("company")) or "Unknown",
            clean_text(job.get("title")) or "Unknown",
            clean_text(job.get("location")) or "Unknown",
            clean_text(job.get("type")) or "Unknown",
            experience_label,
            job_url,
            apply_url,
            clean_text(job.get("snippet")),
            clean_text(job.get("source")) or "Jooble",
            recruiter_email or None,
            apply_method,
            updated or None,
            posted_days,
            1,
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
    print("=" * 75)
    print("FETCHING FRESHER JOBS FROM JOOBLE")
    print("=" * 75)

    if not JOOBLE_API_KEY:

        print()
        print("ERROR: JOOBLE_API_KEY is missing from .env")

        return 0, 0, 0

    locations = get_api_locations()

    if not locations:

        print("ERROR: No locations configured.")
        return 0, 0, 0

    all_jobs = {}
    request_count = 0

    # Filter counters help explain why jobs are rejected.
    rejected_role = 0
    rejected_location = 0
    rejected_freshness = 0
    rejected_experience = 0
    rejected_missing_url = 0

    # ------------------------------------------------------
    # Search Jooble
    # ------------------------------------------------------

    for location in locations:

        for keywords in SEARCH_GROUPS:

            if request_count >= MAX_API_REQUESTS_PER_RUN:
                break

            request_count += 1

            print()
            print(
                f"Jooble request {request_count}/"
                f"{MAX_API_REQUESTS_PER_RUN}"
            )

            print(f"Location : {location}")
            print(f"Keywords : {keywords}")

            try:

                data = search_jooble(
                    keywords=keywords,
                    location=location,
                )

            except Exception as error:

                print()
                print("Jooble request failed:")
                print(error)

                continue

            jobs = data.get("jobs", [])

            print(
                f"Total matching jobs: "
                f"{data.get('totalCount', 0)}"
            )

            print(
                f"Jobs returned: {len(jobs)}"
            )

            for job in jobs:

                key = (
                    clean_text(job.get("id"))
                    or clean_text(job.get("link"))
                )

                if key:
                    all_jobs[key] = job

    jobs_received = len(all_jobs)

    matched_jobs = 0
    new_jobs = 0

    print()
    print(
        f"Unique jobs received: {jobs_received}"
    )

    # ------------------------------------------------------
    # Filter and save unique jobs
    # ------------------------------------------------------

    for job in all_jobs.values():

        title = clean_text(job.get("title"))
        location = clean_text(job.get("location"))
        snippet = clean_text(job.get("snippet"))
        source = clean_text(job.get("source"))
        updated = clean_text(job.get("updated"))

        # ----------------------------------------------
        # Role filter
        # ----------------------------------------------

        if not role_matches(title):

            rejected_role += 1
            continue

        # ----------------------------------------------
        # Location filter
        # ----------------------------------------------

        if not location_matches(location):

            rejected_location += 1
            continue

        # ----------------------------------------------
        # Freshness filter
        # ----------------------------------------------

        if not is_fresh(updated):

            rejected_freshness += 1
            continue

        # ----------------------------------------------
        # Experience filter
        # ----------------------------------------------

        suitable, experience_label = (
            get_experience_info(job)
        )

        if not suitable:

            rejected_experience += 1
            continue

        # ----------------------------------------------
        # Application route
        # ----------------------------------------------

        apply_method, destination = (
            classify_application(
                snippet,
                source,
            )
        )

        recruiter_email = ""
        apply_url = ""

        # Auto-email applications are enabled by the
        # collector only for explicitly fresher-friendly
        # jobs. Experience-unknown email jobs are retained
        # for manual review instead.
        if apply_method == "RECRUITER_EMAIL":

            if experience_label == "Fresher / 0-1 year":

                recruiter_email = destination

            else:

                apply_method = "MANUAL_REVIEW"

        elif destination:

            apply_url = destination

        # --------------------------------------------------
        # IMPORTANT: preserve a review link
        # --------------------------------------------------

        # Jooble's API often does not expose an employer
        # application URL. When no direct URL is available,
        # preserve the Jooble listing for manual review.
        if not apply_url:

            apply_url = clean_text(
                job.get("link")
            )

        # Unknown destinations are still reviewable.
        if apply_method == "UNKNOWN":

            apply_method = "MANUAL_REVIEW"

        if not apply_url:

            rejected_missing_url += 1
            continue

        # ----------------------------------------------
        # Save job
        # ----------------------------------------------

        matched_jobs += 1

        inserted = save_job(
            job=job,
            experience_label=experience_label,
            apply_method=apply_method,
            apply_url=apply_url,
            recruiter_email=recruiter_email,
        )

        if inserted:
            new_jobs += 1

        # ----------------------------------------------
        # Display
        # ----------------------------------------------

        print()
        print("-" * 75)

        print(f"Company        : {job.get('company', 'Unknown')}")
        print(f"Role           : {title}")
        print(f"Location       : {location}")
        print(f"Experience     : {experience_label}")
        print(f"Source         : {source or 'Jooble'}")
        print(f"Updated        : {updated or 'Unknown'}")
        print(f"Recruiter mail : {recruiter_email or 'None'}")
        print(f"Apply method   : {apply_method}")
        print(f"Apply URL      : {apply_url}")
        print(f"Jooble link    : {job.get('link', 'None')}")

    # ------------------------------------------------------
    # Collection summary
    # ------------------------------------------------------

    print()
    print("=" * 75)
    print("JOOBLE COLLECTION COMPLETED")
    print("-" * 75)

    print(f"API requests made       : {request_count}")
    print(f"Unique jobs received    : {jobs_received}")
    print(f"Matching jobs           : {matched_jobs}")
    print(f"New jobs saved          : {new_jobs}")

    print()
    print("FILTER SUMMARY")
    print(f"Rejected by role        : {rejected_role}")
    print(f"Rejected by location    : {rejected_location}")
    print(f"Rejected by freshness   : {rejected_freshness}")
    print(f"Rejected by experience  : {rejected_experience}")
    print(f"Missing review URL      : {rejected_missing_url}")

    print("=" * 75)

    return (
        jobs_received,
        matched_jobs,
        new_jobs,
    )


# ==========================================================
# DIRECT EXECUTION
# ==========================================================

if __name__ == "__main__":

    collect_jobs()