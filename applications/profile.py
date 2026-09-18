from pathlib import Path


# ==========================================================
# PERSONAL INFORMATION
# ==========================================================

FULL_NAME = "Subash M"
EMAIL = "subashmadhavan05@gmail.com"
PHONE = "+91 7397160512"

CITY = "Chennai"
STATE = "Tamil Nadu"
COUNTRY = "India"


# ==========================================================
# ONLINE PROFILES
# ==========================================================

LINKEDIN_URL = "https://www.linkedin.com/in/subash-m-6802a4311"
GITHUB_URL = "https://github.com/Subash0512"
PORTFOLIO_URL = ""


# ==========================================================
# CAREER INFORMATION
# ==========================================================

EXPERIENCE_YEARS = 0
EXPERIENCE_LEVEL = "Fresher"
NOTICE_PERIOD = "Immediate"


TARGET_LOCATIONS = [
    "Chennai",
    "Hosur",
    "Bengaluru",
    "Bangalore",
]


# ==========================================================
# PROJECT PATHS
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

RESUME_PATH = BASE_DIR / "resume" / "Subash_M_Resume.pdf"


# ==========================================================
# PROFILE USED BY APPLICATION BOT
# ==========================================================

PROFILE = {
    "full_name": FULL_NAME,
    "email": EMAIL,
    "phone": PHONE,
    "linkedin": LINKEDIN_URL,
    "github": GITHUB_URL,
    "portfolio": PORTFOLIO_URL,
    "city": CITY,
    "state": STATE,
    "country": COUNTRY,
}


# ==========================================================
# APPLICATION QUESTIONS
#
# Keep unknown answers as None.
# The bot must NOT guess answers.
# ==========================================================

ANSWERS = {
    "work_authorization_india": None,
    "work_authorization_us": None,
    "requires_sponsorship": None,
    "willing_to_relocate": None,
    "willing_to_work_shifts": None,
}


# ==========================================================
# VALIDATION
# ==========================================================

def validate_profile():
    required_values = {
        "FULL_NAME": FULL_NAME,
        "EMAIL": EMAIL,
        "PHONE": PHONE,
    }

    missing = [
        name
        for name, value in required_values.items()
        if not value or value.startswith("YOUR_")
    ]

    if missing:
        raise ValueError(
            "Please fill these fields: "
            + ", ".join(missing)
        )

    if not RESUME_PATH.exists():
        raise FileNotFoundError(
            f"Resume not found: {RESUME_PATH}"
        )

    return True


# ==========================================================
# TEST PROFILE
# ==========================================================

if __name__ == "__main__":

    try:
        validate_profile()

        print("Profile is ready.")
        print(f"Name   : {FULL_NAME}")
        print(f"Email  : {EMAIL}")
        print(f"Phone  : {PHONE}")
        print(f"Resume : {RESUME_PATH}")

    except (ValueError, FileNotFoundError) as error:

        print(
            f"Profile check failed: {error}"
        )