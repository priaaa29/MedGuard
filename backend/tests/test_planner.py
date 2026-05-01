from datetime import time

import pytest

from app.scheduling.planner import plan_routine
from app.scheduling.validator import min_gap_for, to_minutes, validate_routine
from app.schemas import (
    ConstraintSet,
    DailySchedule,
    InteractionFinding,
    MedicationConstraint,
    Separation,
)


def med(name, n, meal="any", tod="any", schedule=None):
    return MedicationConstraint(
        medicine=name,
        doses_per_day=n,
        meal_relation=meal,
        meal_relation_source="curated_rule",
        time_of_day=tod,
        min_gap_minutes=min_gap_for(n, schedule),
    )


def sep(a, b, a_first, b_first):
    return Separation(medicine_a=a, medicine_b=b, a_first_minutes=a_first, b_first_minutes=b_first,
                      reason="test", source="curated_rule")


def times(draft, name):
    return [d.time for d in draft.doses if d.medicine == name]


def plan_and_validate(constraints, schedule, findings=()):
    draft = plan_routine(constraints, schedule, list(findings))
    assert draft is not None, "planner found no schedule"
    assert validate_routine(draft.doses, constraints, schedule) == []
    return draft


def test_with_food_twice_a_day_lands_on_meals(schedule):
    draft = plan_and_validate(ConstraintSet(medications=[med("Metformin", 2, "with_food", schedule=schedule)],
                                            separations=[]), schedule)
    assert times(draft, "Metformin") == ["08:00", "20:00"]
    assert [d.note for d in draft.doses] == ["With breakfast", "With dinner"]


def test_levothyroxine_calcium_and_metformin(schedule):
    constraints = ConstraintSet(
        medications=[
            med("Levothyroxine", 1, "before_meal", "morning", schedule),
            med("Calcium", 1, "with_food", schedule=schedule),
            med("Metformin", 2, "with_food", schedule=schedule),
        ],
        separations=[sep("Calcium", "Levothyroxine", 240, 240)],
    )
    draft = plan_and_validate(constraints, schedule)
    levo = to_minutes(times(draft, "Levothyroxine")[0])
    calcium = to_minutes(times(draft, "Calcium")[0])
    assert times(draft, "Levothyroxine") == ["07:15"]  # 45 min before breakfast
    assert calcium - levo >= 240
    assert "Keep 4 h from Levothyroxine" in next(d.note for d in draft.doses if d.medicine == "Calcium")


def test_asymmetric_ciprofloxacin_separation(schedule):
    constraints = ConstraintSet(
        medications=[med("Ciprofloxacin", 2, schedule=schedule), med("Calcium", 1, "with_food", schedule=schedule)],
        separations=[sep("Ciprofloxacin", "Calcium", 120, 360)],
    )
    plan_and_validate(constraints, schedule)


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_frequent_doses_are_spread_out(schedule, n):
    draft = plan_and_validate(ConstraintSet(medications=[med("Amoxicillin", n, schedule=schedule)], separations=[]),
                              schedule)
    assert len(times(draft, "Amoxicillin")) == n


def test_bedtime_empty_stomach_and_evening(schedule):
    constraints = ConstraintSet(
        medications=[
            med("Zolpidem", 1, "before_bedtime", schedule=schedule),
            med("Alendronate", 1, "empty_stomach", schedule=schedule),
            med("Simvastatin", 1, "any", "evening", schedule),
        ],
        separations=[],
    )
    draft = plan_and_validate(constraints, schedule)
    assert times(draft, "Zolpidem") == ["22:30"]


def test_impossible_constraints_return_none():
    tight = DailySchedule(wake=time(8), breakfast=time(8, 30), lunch=time(12), dinner=time(16), sleep=time(18))
    constraints = ConstraintSet(
        medications=[med("A", 1, schedule=tight), med("B", 1, schedule=tight)],
        separations=[sep("A", "B", 720, 720)],  # 12 h apart both ways can't fit a 10 h day
    )
    assert plan_routine(constraints, tight, []) is None


def test_food_guidance_from_findings(schedule):
    findings = [
        InteractionFinding(medicine="Simvastatin", interacts_with="Grapefruit Juice", kind="food", severity="High",
                           effect="x", recommendation="Avoid grapefruit", source="dataset"),
        InteractionFinding(medicine="Simvastatin", interacts_with="Tea", kind="food", severity="Low",
                           effect="x", recommendation="Fine in moderation", source="dataset"),
    ]
    draft = plan_and_validate(
        ConstraintSet(medications=[med("Simvastatin", 1, schedule=schedule)], separations=[]), schedule, findings
    )
    assert draft.food_guidance == ["Simvastatin and Grapefruit Juice: Avoid grapefruit"]
