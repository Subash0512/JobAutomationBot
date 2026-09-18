import requests

from config import JOB_ROLES, SKILLS, LOCATIONS
from jobs.database import get_connection


API_URL = "https://jobicy.com/api/v2/remote-jobs"


# Titles/keywords that should never be treated as suitable for our target.
EXCLUDED_TITLE_KEYWORDS = [
    "senior",
    "sr.",
    "sr ",
    "lead",
    "principal",
    "staff",
    "manager",
    "director",
    "head of",
]


# Additional title keywords related to your target roles.
ROLE_KEYWORDS = [
    "software engineer",
    "software developer",
    "sde",
    "java developer",
    "backend developer",
    "java backend",
    "spring boot",
    "full stack",
    "junior software",
    "associate software",
    "graduate engineer",
    "technical support",
    "it support",
    "desktop support",
    "application support",
    "production support",
    "l1 support",
    "service desk",
    "help desk",
    "system support",
    "software tester",
    "qa engineer",
    "test engineer",
    "automation test",
    "system engineer",
    "associate engineer",
    "it analyst",
    "application engineer",
    "technical associate",
]


def normalize(text):
    """Convert text to lowercase and clean whitespace."""
    return " ".join((text or "").lower().split())


def title_matches_role(title):
    """
    Match roles using the JOB TITLE only.

    This prevents unrelated jobs from matching because a skill
    such as Java or Python happened to appear in the description.
    """
    title_text = normalize(title)

    # Reject senior-level titles first.
    for excluded in EXCLUDED_TITLE_KEYWORDS:
        if excluded in title_text:
            return False

    # Check the exact configured roles.
    for role in JOB_ROLES:
        if normalize(role) in title_text:
            return True

    # Check additional related role keywords.
    for keyword in ROLE_KEYWORDS:
        if keyword in title_text:
            return True

    return False


def location_matches(job_location):
    """
    Accept only jobs in the configured target locations.
    """
    location = normalize(job_location)

    for allowed_location in LOCATIONS:
        if normalize(allowed_location) in location:
            return True

    return False

def experience_matches(job):
    """
    Target fresher / 0-1 year opportunities.

    'Any' is retained because the company has not specified
    an experience limit. These can later be marked for review.
    """
    level = normalize(job.get("jobLevel"))
    title = normalize(job.get("jobTitle"))
    description = normalize(job.get("jobDescription"))

    combined = f"{level} {title} {description}"

    clearly_senior = [
        "senior",
        "sr.",
        "lead",
        "principal",
        "staff engineer",
        "manager",
        "director",
        "5+ years",
        "6+ years",
        "7+ years",
        "8+ years",
        "10+ years",
    ]

    for term in clearly_senior:
        if term in combined:
            return False

    suitable_terms = [
        "fresher",
        "freshers",
        "entry level",
        "entry-level",
        "junior",
        "associate",
        "graduate",
        "trainee",
        "0-1 year",
        "0 to 1 year",
        "no experience",
    ]

    for term in suitable_terms:
        if term in combined:
            return True

    # "Any" means experience isn't specified.
    # Keep it for later/manual review.
    if level in ("", "any", "not specified"):
        return True

    # Explicitly reject common mid-level levels.
    mid_level_terms = [
        "mid",
        "mid-level",
        "midweight",
        "intermediate",
    ]

    for term in mid_level_terms:
        if term in level or term in title:
            return False

    return True


def find_skills(description):
    """Find configured skills mentioned in the job description."""
    text = normalize(description)
    found = []

    for skill in SKILLS:
        if normalize(skill) in text:
            found.append(skill)

    return found


def save_job(job):
    """Save the job into SQLite without duplicates."""
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO jobs (
            company,
            title,
            location,
            workplace_type,
            experience,
            job_url,
            apply_url,
            description,
            source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job.get("companyName", "Unknown"),
            job.get("jobTitle", "Unknown"),
            job.get("jobGeo", "Remote"),
            "remote",
            job.get("jobLevel", "Unknown"),
            job.get("url", ""),
            job.get("url", ""),
            job.get("jobDescription", ""),
            "Jobicy",
        ),
    )

    inserted = cursor.rowcount > 0

    connection.commit()
    connection.close()

    return inserted


def collect_jobs():
    print()
    print("Fetching remote jobs from Jobicy...")
    print("-" * 70)

    try:
        response = requests.get(
            API_URL,
            params={"count": 200},
            timeout=30,
        )

        response.raise_for_status()
        data = response.json()

    except requests.RequestException as error:
        print("ERROR: Could not connect to Jobicy.")
        print(error)
        return

    jobs = data.get("jobs", [])

    print(f"Jobs received: {len(jobs)}")
    print()

    matched_jobs = 0
    new_jobs = 0

    for job in jobs:

        title = job.get("jobTitle", "")
        location = job.get("jobGeo", "")
        description = job.get("jobDescription", "")

        # 1. Role filter
        if not title_matches_role(title):
            continue

        # 2. Location filter
        if not location_matches(location):
            continue

        # 3. Experience filter
        if not experience_matches(job):
            continue

        matched_jobs += 1

        skills = find_skills(description)

        if save_job(job):
            new_jobs += 1

        print("=" * 70)
        print(f"Company   : {job.get('companyName', 'Unknown')}")
        print(f"Role      : {title}")
        print(f"Location  : {location or 'Remote'}")
        print(f"Experience: {job.get('jobLevel', 'Not specified')}")

        if skills:
            print(f"Skills    : {', '.join(skills)}")
        else:
            print("Skills    : None detected")

        print(f"Posted    : {job.get('pubDate', 'Unknown')}")
        print(f"Job URL   : {job.get('url', 'N/A')}")
        print("=" * 70)

    print()
    print("Collection completed.")
    print(f"Matching jobs : {matched_jobs}")
    print(f"New jobs saved: {new_jobs}")


if __name__ == "__main__":
    collect_jobs()