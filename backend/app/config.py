import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DATA_DIR = BACKEND_DIR / "data"
INTERACTIONS_CSV = DATA_DIR / "drug_food_interactions.csv"
TIMING_RULES_JSON = DATA_DIR / "timing_rules.json"

CLAUDE_MODEL = os.getenv("MEDGUARD_MODEL", "claude-opus-5-5")
CLAUDE_EFFORT = os.getenv("MEDGUARD_EFFORT", "high")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PRESCRIPTION_TEXT_CHARS = 5000
MAX_MEDICATIONS = 20

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("MEDGUARD_CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

ENVIRONMENT = os.getenv("MEDGUARD_ENV", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'medguard.db'}")
if IS_PRODUCTION and DATABASE_URL.startswith("sqlite"):
    raise RuntimeError("Set DATABASE_URL to a Postgres database in production.")

SESSION_COOKIE = "medguard_session"
SESSION_DAYS = int(os.getenv("MEDGUARD_SESSION_DAYS", "14"))
# Secure cookies need HTTPS; plain-http localhost can't use them.
COOKIE_SECURE = os.getenv("MEDGUARD_COOKIE_SECURE", "true" if IS_PRODUCTION else "false") == "true"

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128

# Per-user caps on Claude calls (protects the API bill) and login throttling.
EXTRACTIONS_PER_HOUR = int(os.getenv("MEDGUARD_EXTRACTIONS_PER_HOUR", "20"))
ROUTINES_PER_HOUR = int(os.getenv("MEDGUARD_ROUTINES_PER_HOUR", "20"))
LOGIN_ATTEMPTS_PER_15_MIN = 10
