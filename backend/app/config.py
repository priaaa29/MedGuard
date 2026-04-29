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
