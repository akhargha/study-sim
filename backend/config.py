import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# This is the user in your Supabase users table that the study should use.
STUDY_USERNAME = os.getenv("STUDY_USERNAME", "user25")

# This is the fake login shown on the websites themselves.
FRONTEND_LOGIN_USERNAME = os.getenv("FRONTEND_LOGIN_USERNAME", "user")
FRONTEND_LOGIN_PASSWORD = os.getenv("FRONTEND_LOGIN_PASSWORD", "user")

LOG_FILE = os.getenv("LOG_FILE", "/home/gabriel/study-sim/backend/backend.log")

EMAIL_TO = os.getenv("EMAIL_TO", "moby02@tutamail.com")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "moby@bskyakhargha1.help")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")

STAGE_ORDER = ["tutorial", "stage1", "stage2", "stage3"]

STAGE_QUOTAS = {
    "tutorial": {"regular": 3, "url": 1, "email": 1, "cert": 0},
    "stage1": {"regular": 5, "url": 2, "email": 2, "cert": 1},
    "stage2": {"regular": 5, "url": 2, "email": 2, "cert": 1},
    "stage3": {"regular": 5, "url": 2, "email": 4, "cert": 1},
}

STAGE_BLOCKLISTS = {
    "tutorial": [],
    "stage1": ["citytrust.com", "cltytrust.com", "citytrustbank.com"],
    "stage2": ["meridiansuites.com", "rneridiansuites.com", "meridiansuite.com"],
    "stage3": ["cloudjetairways.com", "cioudjetairways.com", "cloudjetairway.com"],
}

ALL_STUDY_SITES = {
    "citytrust.com",
    "cltytrust.com",
    "citytrustbank.com",
    "meridiansuites.com",
    "rneridiansuites.com",
    "meridiansuite.com",
    "cloudjetairways.com",
    "cioudjetairways.com",
    "cloudjetairway.com",
}

ALLOWED_COMPLETION_TYPES = {
    "done",
    "report_mail",
    "report_extension",
    "previous_block_extension",
}

EXTENSION_ID = "2T7jU3Hr4yC8"

# Dummy certificate chains for now
GOOD_CERT_CHAIN = [
    {
        "subject": {"commonName": "*.studysite.com", "organizationName": "HappyTrust Site"},
        "issuer": {"commonName": "HappyTrust Root CA", "organizationName": "HappyTrust"},
        "serial_number": "happy-0001",
        "version": "v3",
        "not_before": "2026-01-01T00:00:00",
        "not_after": "2028-01-01T00:00:00",
    },
    {
        "subject": {"commonName": "HappyTrust Root CA", "organizationName": "HappyTrust"},
        "issuer": {"commonName": "HappyTrust Root CA", "organizationName": "HappyTrust"},
        "serial_number": "happy-root",
        "version": "v3",
        "not_before": "2026-01-01T00:00:00",
        "not_after": "2036-01-01T00:00:00",
    },
]

BAD_CERT_CHAIN = [
    {
        "subject": {"commonName": "*.studysite.com", "organizationName": "SadTrust Site"},
        "issuer": {"commonName": "SadTrust Root CA", "organizationName": "SadTrust"},
        "serial_number": "sad-0001",
        "version": "v3",
        "not_before": "2026-01-01T00:00:00",
        "not_after": "2028-01-01T00:00:00",
    },
    {
        "subject": {"commonName": "SadTrust Root CA", "organizationName": "SadTrust"},
        "issuer": {"commonName": "SadTrust Root CA", "organizationName": "SadTrust"},
        "serial_number": "sad-root",
        "version": "v3",
        "not_before": "2026-01-01T00:00:00",
        "not_after": "2036-01-01T00:00:00",
    },
]