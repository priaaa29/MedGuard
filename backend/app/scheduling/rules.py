"""Curated, deterministic timing rules (backend/data/timing_rules.json)."""

import json
import re
from dataclasses import dataclass
from functools import lru_cache

from app.config import TIMING_RULES_JSON
from app.schemas import Medication, Separation


@dataclass(frozen=True)
class CuratedMedicineRule:
    meal_relation: str
    time_of_day: str
    reason: str


@lru_cache(maxsize=1)
def _load() -> dict:
    with TIMING_RULES_JSON.open(encoding="utf-8") as file:
        return json.load(file)


def _tokens(selector: str) -> list[str]:
    if selector.startswith("@"):
        return _load()["groups"][selector[1:]]
    return [selector]


def _haystack(medication: Medication) -> str:
    return f"{medication.name} {medication.generic_name or ''}".lower()


def matches(medication: Medication, selector: str) -> bool:
    text = _haystack(medication)
    return any(
        re.search(r"\b" + re.escape(token.lower()) + r"\b", text) for token in _tokens(selector)
    )


def medicine_rule(medication: Medication) -> CuratedMedicineRule | None:
    for rule in _load()["medicines"]:
        if matches(medication, rule["match"]):
            return CuratedMedicineRule(rule["meal_relation"], rule["time_of_day"], rule["reason"])
    return None


def curated_separations(medications: list[Medication]) -> list[Separation]:
    separations = []
    for rule in _load()["separations"]:
        for med_a in medications:
            if not matches(med_a, rule["a"]):
                continue
            for med_b in medications:
                if med_b is med_a or not matches(med_b, rule["b"]):
                    continue
                separations.append(
                    Separation(
                        medicine_a=med_a.name,
                        medicine_b=med_b.name,
                        a_first_minutes=rule["a_first_minutes"],
                        b_first_minutes=rule["b_first_minutes"],
                        reason=rule["reason"],
                        source="curated_rule",
                    )
                )
    return separations
