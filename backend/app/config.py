import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DATA_DIR = BACKEND_DIR / "data"
INTERACTIONS_CSV = DATA_DIR / "drug_food_interactions.csv"
TIMING_RULES_JSON = DATA_DIR / "timing_rules.json"

# Which AI service reads prescriptions and reviews interactions: "gemini" (free tier
# available) or "anthropic" (Claude, paid).
LLM_PROVIDER = os.getenv("MEDGUARD_LLM_PROVIDER", "gemini").lower()
if LLM_PROVIDER not in {"gemini", "anthropic"}:
    raise RuntimeError("MEDGUARD_LLM_PROVIDER must be 'gemini' or 'anthropic'.")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or None
# Flash-Lite: Google's recommended low-cost model, with the largest free daily quota.
GEMINI_MODEL = os.getenv("MEDGUARD_GEMINI_MODEL", "gemini-3.5-flash-lite")

CLAUDE_MODEL = os.getenv("MEDGUARD_MODEL", "claude-opus-5-5")
CLAUDE_EFFORT = os.getenv("MEDGUARD_EFFORT", "high")

# How daily dose times are planned: "scheduler" (built-in, deterministic, no AI call)
# or "llm" (the AI drafts a timetable, then the validator checks it).
ROUTINE_PLANNER = os.getenv("MEDGUARD_ROUTINE_PLANNER", "scheduler").lower()
if ROUTINE_PLANNER not in {"scheduler", "llm"}:
    raise RuntimeError("MEDGUARD_ROUTINE_PLANNER must be 'scheduler' or 'llm'.")

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

def _database_url() -> str:
    url = os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'medguard.db'}")
    # Render and most hosts hand out postgres:// or postgresql:// URLs; SQLAlchemy
    # needs the driver named to use psycopg 3.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = _database_url()
if IS_PRODUCTION and DATABASE_URL.startswith("sqlite"):
    raise RuntimeError("Set DATABASE_URL to a Postgres database in production.")

# Shared store for rate limits. Required in production: an in-memory limiter isn't
# shared between workers or instances, so limits would multiply.
REDIS_URL = os.getenv("REDIS_URL") or None
if IS_PRODUCTION and not REDIS_URL:
    raise RuntimeError("Set REDIS_URL in production so rate limits are shared between workers.")

# A routine still "building" after this long is assumed lost (e.g. the server restarted).
ROUTINE_STALE_MINUTES = 15

SESSION_COOKIE = "medguard_session"
SESSION_DAYS = int(os.getenv("MEDGUARD_SESSION_DAYS", "14"))
# Secure cookies need HTTPS; plain-http localhost can't use them.
COOKIE_SECURE = os.getenv("MEDGUARD_COOKIE_SECURE", "true" if IS_PRODUCTION else "false") == "true"

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128

# Per-user caps on AI calls (protects the API bill) and login throttling.
EXTRACTIONS_PER_HOUR = int(os.getenv("MEDGUARD_EXTRACTIONS_PER_HOUR", "20"))
ROUTINES_PER_HOUR = int(os.getenv("MEDGUARD_ROUTINES_PER_HOUR", "20"))
LOGIN_ATTEMPTS_PER_15_MIN = 10
