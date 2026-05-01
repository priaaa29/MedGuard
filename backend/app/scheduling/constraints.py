"""Turn medicines + rules + the AI review into one constraint set.

Precedence for how a medicine relates to meals:
  1. what the prescription says (user-confirmed),
  2. curated rules (backend/data/timing_rules.json),
  3. the AI's suggestion (labelled "ai"),
  4. no requirement.
"""

from app.scheduling import rules
from app.scheduling.validator import min_gap_for
from app.schemas import (
    ConstraintSet,
    DailySchedule,
    InteractionReview,
    Medication,
    MedicationConstraint,
    Separation,
)

MAX_AI_SEPARATION_MINUTES = 480


def name_resolver(medications: list[Medication]):
    """Map a name the AI returned back to the user's medicine name."""
    lookup = {}
    for med in medications:
        lookup[med.name.lower()] = med.name
        if med.generic_name:
            lookup.setdefault(med.generic_name.lower(), med.name)

    def resolve(name: str) -> str | None:
        return lookup.get(name.strip().lower())

    return resolve


def _merge_separations(separations: list[Separation]) -> list[Separation]:
    merged: dict[tuple[str, str], Separation] = {}
    for sep in separations:
        if sep.medicine_a.lower() > sep.medicine_b.lower():
            sep = Separation(
                medicine_a=sep.medicine_b,
                medicine_b=sep.medicine_a,
                a_first_minutes=sep.b_first_minutes,
                b_first_minutes=sep.a_first_minutes,
                reason=sep.reason,
                source=sep.source,
            )
        key = (sep.medicine_a.lower(), sep.medicine_b.lower())
        existing = merged.get(key)
        if existing is None:
            merged[key] = sep
            continue
        stronger = max(
            (existing, sep), key=lambda s: max(s.a_first_minutes, s.b_first_minutes)
        )
        merged[key] = Separation(
            medicine_a=existing.medicine_a,
            medicine_b=existing.medicine_b,
            a_first_minutes=max(existing.a_first_minutes, sep.a_first_minutes),
            b_first_minutes=max(existing.b_first_minutes, sep.b_first_minutes),
            reason=stronger.reason,
            source="curated_rule" if "curated_rule" in (existing.source, sep.source) else sep.source,
        )
    return list(merged.values())


def build_constraints(
    medications: list[Medication],
    schedule: DailySchedule,
    review: InteractionReview | None,
) -> tuple[ConstraintSet, list[Separation]]:
    """Return (constraints for scheduled medicines, separations involving as-needed ones)."""
    resolve = name_resolver(medications)

    ai_guidance = {}
    ai_separations = []
    if review is not None:
        for guidance in review.meal_guidance:
            name = resolve(guidance.medicine)
            if name:
                ai_guidance[name] = guidance
        for sep in review.separations:
            a, b = resolve(sep.medicine_a), resolve(sep.medicine_b)
            if not a or not b or a == b:
                continue
            ai_separations.append(
                Separation(
                    medicine_a=a,
                    medicine_b=b,
                    a_first_minutes=min(max(sep.a_first_minutes, 0), MAX_AI_SEPARATION_MINUTES),
                    b_first_minutes=min(max(sep.b_first_minutes, 0), MAX_AI_SEPARATION_MINUTES),
                    reason=sep.reason,
                    source="ai",
                )
            )

    med_constraints = []
    for med in medications:
        if med.as_needed:
            continue
        curated = rules.medicine_rule(med)
        if med.meal_relation != "any":
            meal, source, time_of_day = med.meal_relation, "prescription", "any"
        elif curated:
            meal, source, time_of_day = curated.meal_relation, "curated_rule", curated.time_of_day
        elif med.name in ai_guidance:
            guidance = ai_guidance[med.name]
            meal, source, time_of_day = guidance.meal_relation, "ai", guidance.time_of_day
        else:
            meal, source, time_of_day = "any", "default", "any"

        med_constraints.append(
            MedicationConstraint(
                medicine=med.name,
                doses_per_day=med.doses_per_day,
                meal_relation=meal,
                meal_relation_source=source,
                time_of_day=time_of_day,
                min_gap_minutes=min_gap_for(med.doses_per_day, schedule),
            )
        )

    scheduled = {c.medicine for c in med_constraints}
    all_separations = _merge_separations(rules.curated_separations(medications) + ai_separations)
    enforced = [s for s in all_separations if s.medicine_a in scheduled and s.medicine_b in scheduled]
    as_needed = [s for s in all_separations if s not in enforced]

    return ConstraintSet(medications=med_constraints, separations=enforced), as_needed
