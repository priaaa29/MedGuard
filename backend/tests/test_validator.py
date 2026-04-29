import pytest

from app.scheduling.validator import min_gap_for, validate_routine
from app.schemas import ConstraintSet, DraftDose, MedicationConstraint, Separation


def med(name, n=1, meal="any", tod="any", gap=0):
    return MedicationConstraint(
        medicine=name,
        doses_per_day=n,
        meal_relation=meal,
        meal_relation_source="prescription",
        time_of_day=tod,
        min_gap_minutes=gap,
    )


def dose(name, t):
    return DraftDose(medicine=name, time=t, note="")


def codes(issues):
    return sorted(i.code for i in issues)


def test_min_gap_scales_with_frequency(schedule):
    # 16 waking hours
    assert min_gap_for(1, schedule) == 0
    assert min_gap_for(2, schedule) == 480
    assert min_gap_for(3, schedule) == 240


def test_valid_simple_routine(schedule):
    constraints = ConstraintSet(
        medications=[med("Metformin", 2, "with_food", gap=480)], separations=[]
    )
    assert validate_routine([dose("Metformin", "08:00"), dose("Metformin", "20:00")], constraints, schedule) == []


def test_wrong_count_unknown_and_bad_time(schedule):
    constraints = ConstraintSet(medications=[med("Metformin", 2)], separations=[])
    issues = validate_routine(
        [dose("Metformin", "08:00"), dose("Aspirin", "09:00"), dose("Metformin", "8pm")],
        constraints,
        schedule,
    )
    assert codes(issues) == ["bad_time", "unknown_medicine", "wrong_dose_count"]


def test_outside_waking_hours(schedule):
    constraints = ConstraintSet(medications=[med("A")], separations=[])
    assert codes(validate_routine([dose("A", "06:30")], constraints, schedule)) == ["outside_waking_hours"]


def test_doses_too_close(schedule):
    constraints = ConstraintSet(medications=[med("A", 2, gap=480)], separations=[])
    issues = validate_routine([dose("A", "08:00"), dose("A", "13:00")], constraints, schedule)
    assert codes(issues) == ["doses_too_close"]


@pytest.mark.parametrize(
    "meal,t,ok",
    [
        ("with_food", "08:00", True),
        ("with_food", "07:45", True),
        ("with_food", "08:30", True),
        ("with_food", "10:00", False),
        ("before_meal", "07:15", True),
        ("before_meal", "07:45", False),  # only 15 min before
        ("empty_stomach", "07:00", True),  # 60 min before breakfast
        ("empty_stomach", "10:00", True),  # 2 h after breakfast, 3 h before lunch
        ("empty_stomach", "09:00", False),  # 1 h after breakfast
        ("empty_stomach", "12:30", False),  # 30 min before lunch
        ("before_bedtime", "22:30", True),
        ("before_bedtime", "20:30", False),
    ],
)
def test_meal_relations(schedule, meal, t, ok):
    constraints = ConstraintSet(medications=[med("A", 1, meal)], separations=[])
    assert (validate_routine([dose("A", t)], constraints, schedule) == []) is ok


def test_time_of_day(schedule):
    morning = ConstraintSet(medications=[med("A", 1, tod="morning")], separations=[])
    assert validate_routine([dose("A", "09:00")], morning, schedule) == []
    assert codes(validate_routine([dose("A", "13:00")], morning, schedule)) == ["time_of_day"]

    evening = ConstraintSet(medications=[med("B", 1, tod="evening")], separations=[])
    assert validate_routine([dose("B", "21:00")], evening, schedule) == []
    assert codes(validate_routine([dose("B", "13:00")], evening, schedule)) == ["time_of_day"]


def ciprofloxacin_calcium():
    return ConstraintSet(
        medications=[med("Ciprofloxacin", 2), med("Calcium", 1)],
        separations=[
            Separation(
                medicine_a="Ciprofloxacin",
                medicine_b="Calcium",
                a_first_minutes=120,
                b_first_minutes=360,
                reason="2 h before or 6 h after.",
                source="curated_rule",
            )
        ],
    )


def test_asymmetric_separation_passes(schedule):
    doses = [dose("Ciprofloxacin", "08:00"), dose("Ciprofloxacin", "20:00"), dose("Calcium", "14:00")]
    assert validate_routine(doses, ciprofloxacin_calcium(), schedule) == []


def test_asymmetric_separation_fails_when_calcium_first(schedule):
    # Calcium 13:00 then cipro 17:00 is only 4 h; 6 h are required in that direction.
    doses = [dose("Ciprofloxacin", "08:00"), dose("Ciprofloxacin", "17:00"), dose("Calcium", "13:00")]
    assert "separation" in codes(validate_routine(doses, ciprofloxacin_calcium(), schedule))


def test_separation_counts_across_midnight(schedule):
    constraints = ConstraintSet(
        medications=[med("A"), med("B")],
        separations=[
            Separation(
                medicine_a="A",
                medicine_b="B",
                a_first_minutes=0,
                b_first_minutes=600,
                reason="B then A needs 10 h.",
                source="ai",
            )
        ],
    )
    # B at 23:00, A at 07:00 next morning = 8 h: too close.
    assert codes(validate_routine([dose("A", "07:00"), dose("B", "23:00")], constraints, schedule)) == ["separation"]
    # B at 21:00 -> A at 07:00 = 10 h: fine.
    assert validate_routine([dose("A", "07:00"), dose("B", "21:00")], constraints, schedule) == []
