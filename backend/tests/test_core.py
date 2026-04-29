import pytest

from app.core import dataset
from app.core.safety import scrub
from app.scheduling import rules
from app.scheduling.constraints import build_constraints
from app.schemas import AIMealGuidance, AISeparation, InteractionReview, Medication


@pytest.mark.parametrize(
    "query,expected",
    [
        ("Paracetamol", "Paracetamol"),
        ("paracitamol", "Paracetamol"),
        ("warfrin", "Warfarin"),
        ("tea", None),
        ("milk", None),
        ("xyz", None),
        ("", None),
    ],
)
def test_match_medicine(query, expected):
    assert dataset.match_medicine(query).medicine == expected


def test_generic_name_used_for_brand():
    med = Medication(name="Glucophage", generic_name="Metformin", doses_per_day=2)
    findings = dataset.food_interactions(med)
    assert findings and all(f.medicine == "Glucophage" and f.source == "dataset" for f in findings)


def test_dataset_validates():
    frame = dataset.load_dataset()
    assert set(frame["Severity"]) <= {"High", "Medium", "Low"}


@pytest.mark.parametrize(
    "text,removed",
    [
        ("Take with breakfast. Do not skip doses.", []),
        ("Don't stop taking it without advice.", []),
        ("Continue your treatment as prescribed.", []),
        ("If you have stomach pain, take it with food.", []),
        ("Take with food. Stop taking it if you feel dizzy.", ["stop_medicine"]),
        ("You can double the dose if you miss one.", ["dose_change"]),
        ("You probably have an infection.", ["diagnosis"]),
    ],
)
def test_scrub(text, removed):
    clean, codes = scrub(text)
    assert codes == removed
    if removed:
        assert clean == "Take with food." or clean == ""


def test_curated_rules_match_brand_via_generic():
    levo = Medication(name="Thyronorm", generic_name="Levothyroxine", doses_per_day=1)
    calcium = Medication(name="Shelcal 500", generic_name="Calcium carbonate", doses_per_day=1)
    rule = rules.medicine_rule(levo)
    assert rule and rule.meal_relation == "before_meal" and rule.time_of_day == "morning"
    seps = rules.curated_separations([levo, calcium])
    assert [(s.medicine_a, s.medicine_b, s.a_first_minutes) for s in seps] == [
        ("Thyronorm", "Shelcal 500", 240)
    ]


def test_constraint_precedence(schedule):
    meds = [
        # prescription says bedtime -> overrides curated "morning, before meal"
        Medication(name="Levothyroxine", doses_per_day=1, meal_relation="before_bedtime"),
        # no instruction -> curated rule
        Medication(name="Metformin", doses_per_day=2),
        # no instruction, no curated rule -> AI guidance
        Medication(name="Amlodipine", doses_per_day=1),
        Medication(name="Paracetamol", as_needed=True),
    ]
    review = InteractionReview(
        interactions=[],
        separations=[
            AISeparation(
                medicine_a="amlodipine", medicine_b="Metformin",
                a_first_minutes=9999, b_first_minutes=0, reason="test",
            ),
            AISeparation(
                medicine_a="Paracetamol", medicine_b="Metformin",
                a_first_minutes=60, b_first_minutes=60, reason="as-needed test",
            ),
            AISeparation(
                medicine_a="Unknown", medicine_b="Metformin",
                a_first_minutes=60, b_first_minutes=60, reason="ignored",
            ),
        ],
        meal_guidance=[
            AIMealGuidance(medicine="Amlodipine", meal_relation="any", time_of_day="morning", reason="x"),
            AIMealGuidance(medicine="Metformin", meal_relation="empty_stomach", time_of_day="any", reason="ignored"),
        ],
    )
    constraints, as_needed = build_constraints(meds, schedule, review)
    by_name = {c.medicine: c for c in constraints.medications}

    assert set(by_name) == {"Levothyroxine", "Metformin", "Amlodipine"}
    assert (by_name["Levothyroxine"].meal_relation, by_name["Levothyroxine"].meal_relation_source) == ("before_bedtime", "prescription")
    assert by_name["Levothyroxine"].time_of_day == "any"
    assert (by_name["Metformin"].meal_relation, by_name["Metformin"].meal_relation_source) == ("with_food", "curated_rule")
    assert (by_name["Amlodipine"].time_of_day, by_name["Amlodipine"].meal_relation_source) == ("morning", "ai")
    assert by_name["Metformin"].min_gap_minutes == 480

    [sep] = constraints.separations
    assert sep.source == "ai" and max(sep.a_first_minutes, sep.b_first_minutes) == 480  # clamped
    assert [(s.medicine_a, s.medicine_b) for s in as_needed] == [("Metformin", "Paracetamol")]
