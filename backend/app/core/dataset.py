"""Curated food-medicine interaction dataset (deterministic, citable source)."""

from dataclasses import dataclass
from functools import lru_cache

import pandas as pd
from rapidfuzz import fuzz, process

from app.config import INTERACTIONS_CSV
from app.schemas import InteractionFinding, Medication

REQUIRED_COLUMNS = {"Medicine", "Food", "Interaction_Type", "Severity", "Effect", "Recommendation"}
ALLOWED_SEVERITIES = {"Low", "Medium", "High"}

# fuzz.ratio (normalized edit distance) rather than WRatio: WRatio rewards partial
# substring matches, e.g. "tea" -> Amoxicillin-Clavulanate scored 72.
MATCH_THRESHOLD = 80
SUGGEST_THRESHOLD = 60


class DatasetValidationError(ValueError):
    pass


@dataclass(frozen=True)
class MedicineMatch:
    query: str
    medicine: str | None  # canonical dataset name when score >= MATCH_THRESHOLD
    suggestion: str | None
    score: float


def validate(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise DatasetValidationError(f"Dataset is missing columns: {', '.join(missing)}")

    frame = frame.copy()
    for column in REQUIRED_COLUMNS:
        frame[column] = frame[column].astype("string").str.strip()
    frame["Severity"] = frame["Severity"].str.capitalize()

    nulls = {c: int(n) for c, n in frame[list(REQUIRED_COLUMNS)].isna().sum().items() if n}
    if nulls:
        raise DatasetValidationError(f"Dataset contains empty values: {nulls}")

    bad = sorted(set(frame["Severity"]) - ALLOWED_SEVERITIES)
    if bad:
        raise DatasetValidationError(f"Invalid severity values: {', '.join(bad)}")

    return frame


@lru_cache(maxsize=1)
def load_dataset() -> pd.DataFrame:
    return validate(pd.read_csv(INTERACTIONS_CSV))


@lru_cache(maxsize=1)
def _medicine_index() -> dict[str, str]:
    return {name.lower(): name for name in sorted(load_dataset()["Medicine"].unique())}


def match_medicine(name: str) -> MedicineMatch:
    query = name.strip()
    index = _medicine_index()
    if not query:
        return MedicineMatch(query, None, None, 0.0)

    key, score, _ = process.extractOne(query.lower(), list(index), scorer=fuzz.ratio)
    canonical = index[key]
    return MedicineMatch(
        query=query,
        medicine=canonical if score >= MATCH_THRESHOLD else None,
        suggestion=canonical if score >= SUGGEST_THRESHOLD else None,
        score=round(score, 1),
    )


def resolve(medication: Medication) -> MedicineMatch:
    """Best dataset match using the generic name first, then the written name."""
    candidates = [n for n in (medication.generic_name, medication.name) if n]
    matches = [match_medicine(n) for n in candidates]
    found = [m for m in matches if m.medicine]
    pool = found or matches
    return max(pool, key=lambda m: m.score)


def food_interactions(medication: Medication) -> list[InteractionFinding]:
    match = resolve(medication)
    if not match.medicine:
        return []

    frame = load_dataset()
    rows = frame[frame["Medicine"] == match.medicine]
    order = {"High": 0, "Medium": 1, "Low": 2}
    findings = [
        InteractionFinding(
            medicine=medication.name,
            interacts_with=row.Food,
            kind="food",
            severity=row.Severity,
            effect=row.Effect,
            recommendation=row.Recommendation,
            source="dataset",
        )
        for row in rows.itertuples()
    ]
    return sorted(findings, key=lambda f: order[f.severity])
