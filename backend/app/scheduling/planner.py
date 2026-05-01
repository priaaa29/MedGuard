"""Deterministic routine planner (no AI call).

1. For each medicine, list candidate dose-time sets that satisfy its own rules:
   number of doses, waking hours, food requirement, time of day, dose spacing.
   Sets are ranked by how easy they are to follow (anchored to meals, waking,
   bedtime; evenly spread).
2. Search across medicines, most constrained first, for a combination that also
   satisfies every separation between medicines. Candidates are tried best-first,
   so the first complete combination found is a good one.

Every result is still checked by validator.validate_routine before it is shown.
"""

from dataclasses import dataclass
from itertools import combinations

from app.scheduling.validator import (
    BEDTIME_WINDOW,
    DAY,
    EVENING_BEFORE_DINNER,
    MORNING_WINDOW,
    _meal_ok,
    format_minutes,
    to_minutes,
)
from app.schemas import (
    ConstraintSet,
    DailySchedule,
    DraftDose,
    InteractionFinding,
    MedicationConstraint,
    RoutineDraft,
    Separation,
)

GRID = 15  # minutes between candidate times
MAX_SETS_PER_MEDICINE = 40
MAX_SEARCH_STEPS = 50_000
MEAL_NAMES = ("breakfast", "lunch", "dinner")


@dataclass(frozen=True)
class _Day:
    wake: int
    sleep: int
    meals: tuple[int, int, int]

    @property
    def anchors(self) -> list[int]:
        return [self.wake, *self.meals, self.sleep - 30]


def _day(schedule: DailySchedule) -> _Day:
    return _Day(
        wake=to_minutes(schedule.wake),
        sleep=to_minutes(schedule.sleep),
        meals=(to_minutes(schedule.breakfast), to_minutes(schedule.lunch), to_minutes(schedule.dinner)),
    )


# --------------------------------------------------------------------------- #
# Per-medicine candidates
# --------------------------------------------------------------------------- #
def _time_of_day_ok(c: MedicationConstraint, t: int, day: _Day) -> bool:
    if c.doses_per_day != 1:
        return True
    if c.time_of_day == "morning":
        return t - day.wake <= MORNING_WINDOW
    if c.time_of_day == "evening":
        return t >= day.meals[2] - EVENING_BEFORE_DINNER
    return True


def _allowed_times(c: MedicationConstraint, day: _Day) -> list[int]:
    times = set(range(day.wake, day.sleep + 1, GRID))
    # Exact anchors so meal-relative rules can be hit precisely, not just to the grid.
    for m in day.meals:
        times.update({m, m - 30, m - 45, m - 60, m + 15, m + 120})
    times.update({day.sleep - 30, day.sleep - BEDTIME_WINDOW, day.sleep})
    return sorted(
        t
        for t in times
        if day.wake <= t <= day.sleep
        and _meal_ok(c.meal_relation, t, list(day.meals), day.sleep)
        and _time_of_day_ok(c, t, day)
    )


def _preference(c: MedicationConstraint, t: int, day: _Day) -> float:
    """Lower is better: how natural this time is for this medicine."""
    relation = c.meal_relation
    if relation == "with_food":
        cost = min(abs(t - m) for m in day.meals)
    elif relation == "before_meal":
        cost = min(abs((m - t) - 45) for m in day.meals)
    elif relation == "empty_stomach":
        cost = min([abs(t - (m - 60)) for m in day.meals] + [abs(t - day.wake)])
    elif relation == "before_bedtime":
        cost = abs((day.sleep - 30) - t)
    else:
        # No food rule: tie it to something in the day so it's easy to remember.
        cost = 0.5 * min(abs(t - a) for a in day.anchors)
    if c.doses_per_day == 1 and c.time_of_day == "morning":
        cost += (t - day.wake) / 10
    return cost


def _set_score(c: MedicationConstraint, times: tuple[int, ...], day: _Day) -> float:
    score = sum(_preference(c, t, day) for t in times)
    if len(times) > 1:
        gaps = [b - a for a, b in zip(times, times[1:])]
        mean = sum(gaps) / len(gaps)
        score += sum(abs(g - mean) for g in gaps) / 4  # prefer even spacing
    return score


def _snap(target: float, allowed: list[int], earliest: int, tolerance: int = 90) -> int | None:
    best = None
    for t in allowed:
        if t < earliest or abs(t - target) > tolerance:
            continue
        if best is None or abs(t - target) < abs(best - target):
            best = t
    return best


def _candidate_sets(c: MedicationConstraint, day: _Day) -> list[tuple[int, ...]]:
    allowed = _allowed_times(c, day)
    n = c.doses_per_day
    if not allowed:
        return []
    if n == 1:
        sets = {(t,) for t in allowed}
    else:
        sets: set[tuple[int, ...]] = set()
        span = day.sleep - day.wake
        gaps = {c.min_gap_minutes, span // (n - 1), (c.min_gap_minutes + span // (n - 1)) // 2}
        # Meal-anchored sets (e.g. with breakfast and dinner) are often the most natural.
        if c.meal_relation in ("with_food", "before_meal", "any") and n <= 3:

            offset = -45 if c.meal_relation == "before_meal" else 0
            for meals in combinations(day.meals, n):
                snapped = tuple(_snap(m + offset, allowed, day.wake, tolerance=30) for m in meals)
                if None not in snapped:
                    sets.add(snapped)
        for first in allowed:
            for gap in gaps:
                if gap <= 0:
                    continue
                times = [first]
                for i in range(1, n):
                    nxt = _snap(first + i * gap, allowed, times[-1] + c.min_gap_minutes)
                    if nxt is None:
                        break
                    times.append(nxt)
                if len(times) == n:
                    sets.add(tuple(times))

    valid = [
        s
        for s in sets
        if len(set(s)) == n
        and all(b - a >= c.min_gap_minutes for a, b in zip(s, s[1:]))
    ]
    valid.sort(key=lambda s: _set_score(c, s, day))
    return valid[:MAX_SETS_PER_MEDICINE]


# --------------------------------------------------------------------------- #
# Search across medicines
# --------------------------------------------------------------------------- #
def _separation_ok(sep: Separation, a_times: tuple[int, ...], b_times: tuple[int, ...]) -> bool:
    return all(
        (tb - ta) % DAY >= sep.a_first_minutes and (ta - tb) % DAY >= sep.b_first_minutes
        for ta in a_times
        for tb in b_times
    )


def _search(constraints: ConstraintSet, candidates: dict[str, list[tuple[int, ...]]]):
    seps_by_med: dict[str, list[Separation]] = {}
    for sep in constraints.separations:
        seps_by_med.setdefault(sep.medicine_a, []).append(sep)
        seps_by_med.setdefault(sep.medicine_b, []).append(sep)

    order = sorted(
        candidates,
        key=lambda name: (-len(seps_by_med.get(name, [])), len(candidates[name])),
    )
    chosen: dict[str, tuple[int, ...]] = {}
    steps = 0

    def consistent(name: str, times: tuple[int, ...]) -> bool:
        for sep in seps_by_med.get(name, []):
            other = sep.medicine_b if sep.medicine_a == name else sep.medicine_a
            if other not in chosen:
                continue
            a_times = times if sep.medicine_a == name else chosen[other]
            b_times = chosen[other] if sep.medicine_a == name else times
            if not _separation_ok(sep, a_times, b_times):
                return False
        return True

    def assign(index: int) -> bool:
        nonlocal steps
        if index == len(order):
            return True
        name = order[index]
        for times in candidates[name]:
            steps += 1
            if steps > MAX_SEARCH_STEPS:
                return False
            if consistent(name, times):
                chosen[name] = times
                if assign(index + 1):
                    return True
                del chosen[name]
        return False

    return dict(chosen) if assign(0) else None


# --------------------------------------------------------------------------- #
# Wording
# --------------------------------------------------------------------------- #
def _nearest_meal(t: int, day: _Day, after: bool = False) -> tuple[str, int]:
    options = [(name, m) for name, m in zip(MEAL_NAMES, day.meals) if not after or m >= t]
    options = options or list(zip(MEAL_NAMES, day.meals))
    return min(options, key=lambda item: abs(item[1] - t))


def _note(c: MedicationConstraint, t: int, day: _Day, separation_note: str | None) -> str:
    relation = c.meal_relation
    if relation == "with_food":
        meal, _ = _nearest_meal(t, day)
        note = f"With {meal}"
    elif relation == "before_meal":
        meal, m = _nearest_meal(t, day, after=True)
        note = f"{m - t} min before {meal}, with water"
    elif relation == "empty_stomach":
        note = "On an empty stomach"
    elif relation == "before_bedtime":
        note = "At bedtime"
    else:
        # No food rule: name whatever it's anchored to, so it's easy to remember.
        meal, m = _nearest_meal(t, day)
        if abs(t - m) <= 15:
            note = f"With {meal}"
        elif abs(t - day.wake) <= 15:
            note = "When you wake up"
        elif day.sleep - t <= 60:
            note = "Before bed"
        else:
            note = "Same time each day"
    return f"{note}. {separation_note}" if separation_note else note


def _gap_text(minutes: int) -> str:
    hours, rest = divmod(minutes, 60)
    if not hours:
        return f"{rest} min"
    return f"{hours} h" if not rest else f"{hours} h {rest} min"


def _separation_notes(constraints: ConstraintSet) -> dict[str, str]:
    notes: dict[str, list[str]] = {}
    for sep in constraints.separations:
        gap = max(sep.a_first_minutes, sep.b_first_minutes)
        if gap <= 0:
            continue
        notes.setdefault(sep.medicine_a, []).append(f"Keep {_gap_text(gap)} from {sep.medicine_b}")
        notes.setdefault(sep.medicine_b, []).append(f"Keep {_gap_text(gap)} from {sep.medicine_a}")
    return {name: "; ".join(items[:2]) for name, items in notes.items()}


def _food_guidance(findings: list[InteractionFinding]) -> list[str]:
    lines: list[str] = []
    for finding in findings:
        if finding.severity == "Low":
            continue
        line = f"{finding.medicine} and {finding.interacts_with}: {finding.recommendation}"
        if line not in lines:
            lines.append(line)
    return lines[:8]


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def plan_routine(
    constraints: ConstraintSet,
    schedule: DailySchedule,
    findings: list[InteractionFinding],
) -> RoutineDraft | None:
    """Return a timetable that satisfies every constraint, or None if none was found."""
    day = _day(schedule)
    candidates = {c.medicine: _candidate_sets(c, day) for c in constraints.medications}
    if any(not sets for sets in candidates.values()):
        return None
    chosen = _search(constraints, candidates)
    if chosen is None:
        return None

    by_name = {c.medicine: c for c in constraints.medications}
    separation_notes = _separation_notes(constraints)
    doses = [
        DraftDose(
            medicine=name,
            time=format_minutes(t),
            note=_note(by_name[name], t, day, separation_notes.get(name)),
        )
        for name, times in chosen.items()
        for t in times
    ]
    doses.sort(key=lambda d: (to_minutes(d.time), d.medicine.lower()))

    summary = "Times are planned around your meals and sleep, with the gaps each medicine needs."
    if constraints.separations:
        summary += " Medicines that shouldn't be taken together are spaced apart."
    summary += " Check this routine with your pharmacist before you start."

    return RoutineDraft(doses=doses, food_guidance=_food_guidance(findings), summary=summary)
