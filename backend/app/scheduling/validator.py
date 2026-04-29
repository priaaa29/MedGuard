"""Deterministic routine checker.

Claude proposes a timetable; this module decides whether it is acceptable.
Every rule here is plain arithmetic on minutes-since-midnight so it can be
unit-tested and audited without the model.

The routine repeats daily, so the gap between two medicines is checked in both
directions around the clock: A at 08:00 and B at 20:00 means B follows A by
12 hours *and* A follows B (next morning) by 12 hours.
"""

import re
from datetime import time

from app.schemas import (
    ConstraintSet,
    DailySchedule,
    DraftDose,
    MedicationConstraint,
    ValidationIssue,
)

DAY = 24 * 60
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

# Meal windows, in minutes relative to the meal time.
WITH_FOOD_BEFORE = 15  # up to 15 min before the meal
WITH_FOOD_AFTER = 30  # up to 30 min after the meal starts
BEFORE_MEAL_MIN = 30
BEFORE_MEAL_MAX = 60
EMPTY_BEFORE_NEXT_MEAL = 60
EMPTY_AFTER_LAST_MEAL = 120
BEDTIME_WINDOW = 60
MORNING_WINDOW = 180  # once-daily "morning" doses: within 3 h of waking
EVENING_BEFORE_DINNER = 60  # once-daily "evening" doses: from 1 h before dinner


def to_minutes(value: time | str) -> int:
    if isinstance(value, time):
        return value.hour * 60 + value.minute
    match = TIME_PATTERN.match(value.strip())
    if not match:
        raise ValueError(f"Invalid time {value!r}; expected HH:MM")
    return int(match.group(1)) * 60 + int(match.group(2))


def format_minutes(minutes: int) -> str:
    minutes %= DAY
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def min_gap_for(doses_per_day: int, schedule: DailySchedule) -> int:
    """Minimum spacing between doses of the same medicine.

    Half of the even spacing achievable inside waking hours: 2/day with a
    16-hour day must be >= 8 h apart, 3/day >= 4 h, 4/day >= ~2.7 h.
    """
    if doses_per_day <= 1:
        return 0
    window = to_minutes(schedule.sleep) - to_minutes(schedule.wake)
    return int(0.5 * window / (doses_per_day - 1))


def _meal_ok(relation: str, t: int, meals: list[int], sleep: int) -> bool:
    if relation == "any":
        return True
    if relation == "with_food":
        return any(-WITH_FOOD_BEFORE <= t - m <= WITH_FOOD_AFTER for m in meals)
    if relation == "before_meal":
        return any(BEFORE_MEAL_MIN <= m - t <= BEFORE_MEAL_MAX for m in meals)
    if relation == "empty_stomach":
        next_meals = [m for m in meals if m >= t]
        prev_meals = [m for m in meals if m < t]
        ok_next = not next_meals or min(next_meals) - t >= EMPTY_BEFORE_NEXT_MEAL
        ok_prev = not prev_meals or t - max(prev_meals) >= EMPTY_AFTER_LAST_MEAL
        return ok_next and ok_prev
    if relation == "before_bedtime":
        return 0 <= sleep - t <= BEDTIME_WINDOW
    return False


MEAL_RELATION_TEXT = {
    "with_food": "with a meal (from 15 min before to 30 min after it)",
    "before_meal": "30-60 minutes before a meal",
    "empty_stomach": "on an empty stomach (1 h before or 2 h after food)",
    "before_bedtime": "within the hour before sleep",
}


def validate_routine(
    doses: list[DraftDose],
    constraints: ConstraintSet,
    schedule: DailySchedule,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    wake, sleep = to_minutes(schedule.wake), to_minutes(schedule.sleep)
    meals = [to_minutes(schedule.breakfast), to_minutes(schedule.lunch), to_minutes(schedule.dinner)]

    by_name: dict[str, MedicationConstraint] = {
        c.medicine.lower(): c for c in constraints.medications
    }
    times: dict[str, list[int]] = {c.medicine: [] for c in constraints.medications}

    for dose in doses:
        constraint = by_name.get(dose.medicine.strip().lower())
        if constraint is None:
            issues.append(
                ValidationIssue(
                    code="unknown_medicine",
                    medicine=dose.medicine,
                    message=f"'{dose.medicine}' is not one of the scheduled medicines.",
                )
            )
            continue
        try:
            t = to_minutes(dose.time)
        except ValueError as exc:
            issues.append(
                ValidationIssue(code="bad_time", medicine=constraint.medicine, message=str(exc))
            )
            continue
        times[constraint.medicine].append(t)

    for constraint in constraints.medications:
        name = constraint.medicine
        ts = sorted(times[name])

        if len(ts) != constraint.doses_per_day:
            issues.append(
                ValidationIssue(
                    code="wrong_dose_count",
                    medicine=name,
                    message=(
                        f"{name} must have exactly {constraint.doses_per_day} dose(s) per day; "
                        f"got {len(ts)}."
                    ),
                )
            )

        for t in ts:
            if not wake <= t <= sleep:
                issues.append(
                    ValidationIssue(
                        code="outside_waking_hours",
                        medicine=name,
                        message=(
                            f"{name} at {format_minutes(t)} is outside waking hours "
                            f"({format_minutes(wake)}-{format_minutes(sleep)})."
                        ),
                    )
                )
            if not _meal_ok(constraint.meal_relation, t, meals, sleep):
                issues.append(
                    ValidationIssue(
                        code="meal_relation",
                        medicine=name,
                        message=(
                            f"{name} at {format_minutes(t)} must be taken "
                            f"{MEAL_RELATION_TEXT[constraint.meal_relation]}."
                        ),
                    )
                )

        for earlier, later in zip(ts, ts[1:]):
            if later - earlier < constraint.min_gap_minutes:
                issues.append(
                    ValidationIssue(
                        code="doses_too_close",
                        medicine=name,
                        message=(
                            f"{name} doses at {format_minutes(earlier)} and "
                            f"{format_minutes(later)} are less than "
                            f"{constraint.min_gap_minutes} minutes apart."
                        ),
                    )
                )

        if constraint.doses_per_day == 1 and ts:
            t = ts[0]
            if constraint.time_of_day == "morning" and t - wake > MORNING_WINDOW:
                issues.append(
                    ValidationIssue(
                        code="time_of_day",
                        medicine=name,
                        message=f"{name} should be taken in the morning (within 3 hours of waking).",
                    )
                )
            if constraint.time_of_day == "evening" and t < meals[2] - EVENING_BEFORE_DINNER:
                issues.append(
                    ValidationIssue(
                        code="time_of_day",
                        medicine=name,
                        message=f"{name} should be taken in the evening (around dinner or later).",
                    )
                )

    for sep in constraints.separations:
        for ta in times.get(sep.medicine_a, []):
            for tb in times.get(sep.medicine_b, []):
                b_after_a = (tb - ta) % DAY
                a_after_b = (ta - tb) % DAY
                if b_after_a < sep.a_first_minutes or a_after_b < sep.b_first_minutes:
                    issues.append(
                        ValidationIssue(
                            code="separation",
                            medicine=sep.medicine_a,
                            message=(
                                f"{sep.medicine_a} at {format_minutes(ta)} and "
                                f"{sep.medicine_b} at {format_minutes(tb)} are too close. "
                                f"{sep.reason}"
                            ),
                        )
                    )

    return issues
