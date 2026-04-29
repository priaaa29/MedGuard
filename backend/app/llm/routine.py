"""Step 3: ask Claude for a daily timetable that satisfies the constraints.

The output is always checked by app.scheduling.validator; the prompt spells out
the same windows the validator enforces so the two agree.
"""

import json

from app.llm.client import StructuredLLM
from app.schemas import (
    ConstraintSet,
    DailySchedule,
    InteractionFinding,
    RoutineDraft,
    ValidationIssue,
)

SYSTEM = """You plan daily medicine timetables for MedGuard. Given a person's daily schedule, \
their medicines and timing constraints, place every dose at a clock time.

Hard rules (a program checks every one; a timetable that breaks any is rejected):
- Give each medicine exactly doses_per_day doses. Never add, drop or merge doses, and never \
mention changing an amount.
- Every dose between wake and sleep time (inclusive), as 24-hour HH:MM.
- Doses of the same medicine at least min_gap_minutes apart.
- Food requirements, relative to the breakfast/lunch/dinner times given:
  with_food: from 15 min before to 30 min after a meal time.
  before_meal: 30 to 60 min before a meal time.
  empty_stomach: at least 60 min before the next meal and at least 120 min after the previous meal.
  before_bedtime: within the 60 min before sleep.
- time_of_day for once-daily medicines: morning = within 3 h of waking; evening = no earlier \
than 1 h before dinner.
- Separations: the routine repeats every day, so after a dose of medicine_a, medicine_b must \
wait a_first_minutes; after a dose of medicine_b, medicine_a must wait b_first_minutes. Count \
the gap across midnight too.

Within those rules, make it easy to follow: spread doses of the same medicine evenly, anchor \
times to waking, meals and bedtime, and group medicines at the same time when allowed. Notes \
are practical and short (e.g. "30 min before breakfast, with water"). food_guidance turns the \
listed food interactions into plain reminders. The summary explains the timetable in two or \
three sentences. Never advise stopping, skipping or changing a medicine or dose, and don't \
diagnose. If the constraints truly cannot all be met, get as close as you can and say which \
one could not be met in the summary."""


def generate_routine(
    llm: StructuredLLM,
    constraints: ConstraintSet,
    schedule: DailySchedule,
    food_interactions: list[InteractionFinding],
    previous: RoutineDraft | None = None,
    issues: list[ValidationIssue] | None = None,
) -> RoutineDraft:
    payload = {
        "schedule": schedule.model_dump(mode="json"),
        "medicines": [c.model_dump(exclude={"meal_relation_source"}) for c in constraints.medications],
        "separations": [s.model_dump(exclude={"source"}) for s in constraints.separations],
        "food_interactions": [
            {
                "medicine": f.medicine,
                "food": f.interacts_with,
                "severity": f.severity,
                "advice": f.recommendation,
            }
            for f in food_interactions
            if f.kind == "food"
        ],
    }
    text = "Plan the daily timetable.\n\n<input>\n" + json.dumps(payload, indent=2) + "\n</input>"

    if previous is not None and issues:
        text += (
            "\n\nA previous timetable was rejected by the checker:\n<previous>\n"
            + json.dumps([d.model_dump() for d in previous.doses], indent=2)
            + "\n</previous>\n<problems>\n"
            + "\n".join(f"- {issue.message}" for issue in issues)
            + "\n</problems>\nFix every problem while keeping all the other rules."
        )

    return llm.parse(
        system=SYSTEM,
        content=[{"type": "text", "text": text}],
        output_model=RoutineDraft,
    )
