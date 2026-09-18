from config import JOB_ROLES, LOCATIONS


EXCLUDED_TITLE_WORDS = [
    "senior",
    "sr.",
    "lead",
    "principal",
    "staff",
    "manager",
    "director",
]


def normalize(value):
    return " ".join((value or "").lower().split())


def is_allowed_location(location):
    location_text = normalize(location)

    for allowed in LOCATIONS:
        if normalize(allowed) in location_text:
            return True

    return False


def is_allowed_role(title):
    title_text = normalize(title)

    for excluded in EXCLUDED_TITLE_WORDS:
        if excluded in title_text:
            return False

    for role in JOB_ROLES:
        if normalize(role) in title_text:
            return True

    return False


def is_fresher_suitable(experience_text):
    text = normalize(experience_text)

    unsuitable = [
        "senior",
        "lead",
        "principal",
        "staff",
        "manager",
        "5+ years",
        "6+ years",
        "7+ years",
        "8+ years",
    ]

    for word in unsuitable:
        if word in text:
            return False

    suitable = [
        "fresher",
        "freshers",
        "0 year",
        "0-1 year",
        "0 to 1 year",
        "entry level",
        "entry-level",
        "junior",
        "graduate",
        "trainee",
        "associate",
    ]

    for word in suitable:
        if word in text:
            return True

    return True


def is_job_eligible(job):
    return (
        is_allowed_role(job.get("title", ""))
        and is_allowed_location(job.get("location", ""))
        and is_fresher_suitable(job.get("experience", ""))
    )