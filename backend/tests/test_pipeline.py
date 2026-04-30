from app.llm.client import LLMError
from app.pipeline import INVALID_ROUTINE_SUMMARY, analyze
from app.schemas import (
    AIInteraction,
    AnalyzeRequest,
    DraftDose,
    InteractionReview,
    Medication,
    RoutineDraft,
)
from tests.conftest import FakeLLM

EMPTY_REVIEW = InteractionReview(interactions=[], separations=[], meal_guidance=[])


def request(schedule):
    return AnalyzeRequest(
        medications=[
            Medication(name="Metformin", strength="500 mg", dose="1 tablet", doses_per_day=2),
            Medication(name="Levothyroxine", dose="1 tablet", doses_per_day=1),
            Medication(name="Paracetamol", as_needed=True),
        ],
        schedule=schedule,
    )


def good_draft(**overrides):
    values = dict(
        doses=[
            DraftDose(medicine="Levothyroxine", time="07:15", note="30-60 min before breakfast, with water"),
            DraftDose(medicine="Metformin", time="08:00", note="With breakfast"),
            DraftDose(medicine="metformin", time="20:00", note="With dinner"),
        ],
        food_guidance=["Limit alcohol while taking metformin."],
        summary="Levothyroxine first thing, metformin with breakfast and dinner.",
    )
    values.update(overrides)
    return RoutineDraft(**values)


def bad_draft():
    # Metformin away from meals and only once.
    return RoutineDraft(
        doses=[
            DraftDose(medicine="Levothyroxine", time="07:15", note=""),
            DraftDose(medicine="Metformin", time="11:00", note=""),
        ],
        food_guidance=[],
        summary="x",
    )


def test_valid_first_try(schedule):
    llm = FakeLLM({InteractionReview: [EMPTY_REVIEW], RoutineDraft: [good_draft()]})
    result = analyze(llm, request(schedule))

    routine = result.routine
    assert routine.valid and routine.attempts == 1 and routine.issues == []
    assert [(d.time, d.medicine) for d in routine.doses] == [
        ("07:15", "Levothyroxine"),
        ("08:00", "Metformin"),
        ("20:00", "Metformin"),
    ]
    # dose label comes from the prescription, not the model
    assert routine.doses[1].dose == "1 tablet (500 mg)"
    assert routine.as_needed == ["Paracetamol"]
    assert any(f.source == "dataset" and f.medicine == "Metformin" for f in result.interactions)
    assert result.disclaimer


def test_retry_after_rejection_includes_problems(schedule):
    llm = FakeLLM({InteractionReview: [EMPTY_REVIEW], RoutineDraft: [bad_draft(), good_draft()]})
    result = analyze(llm, request(schedule))

    assert result.routine.valid and result.routine.attempts == 2
    retry_prompt = llm.calls[-1]["content"][0]["text"]
    assert "rejected by the checker" in retry_prompt and "exactly 2 dose(s)" in retry_prompt


def test_invalid_after_retries_is_flagged(schedule):
    llm = FakeLLM({InteractionReview: [EMPTY_REVIEW], RoutineDraft: [bad_draft(), bad_draft()]})
    routine = analyze(llm, request(schedule)).routine

    assert not routine.valid and routine.attempts == 2
    assert routine.summary == INVALID_ROUTINE_SUMMARY
    assert {i.code for i in routine.issues} >= {"wrong_dose_count", "meal_relation"}


def test_review_failure_degrades_gracefully(schedule):
    llm = FakeLLM({InteractionReview: [LLMError("busy")], RoutineDraft: [good_draft()]})
    result = analyze(llm, request(schedule))
    assert result.routine.valid
    assert any("AI interaction review unavailable" in w for w in result.warnings)


def test_ai_findings_are_labelled_deduped_and_scrubbed(schedule):
    review = InteractionReview(
        interactions=[
            AIInteraction(  # duplicate of a dataset row -> dropped
                medicine="Metformin", interacts_with="Alcohol", kind="food", severity="Medium",
                effect="x", recommendation="y",
            ),
            AIInteraction(
                medicine="levothyroxine", interacts_with="Soy", kind="food", severity="High",
                effect="Soy can reduce absorption.",
                recommendation="Increase your dose if you eat soy daily.",
            ),
            AIInteraction(  # unknown medicine -> dropped
                medicine="Aspirin", interacts_with="Alcohol", kind="food", severity="Low",
                effect="x", recommendation="y",
            ),
        ],
        separations=[],
        meal_guidance=[],
    )
    draft = good_draft(summary="Take as shown. Stop taking metformin if you feel sick.")
    llm = FakeLLM({InteractionReview: [review], RoutineDraft: [draft]})
    result = analyze(llm, request(schedule))

    ai = [f for f in result.interactions if f.source == "ai"]
    assert [(f.medicine, f.interacts_with) for f in ai] == [("Levothyroxine", "Soy")]
    assert ai[0].recommendation == "Ask your doctor or pharmacist how to manage this."
    assert result.routine.summary == "Take as shown."
    assert any("dose_change" in m for m in result.safety_modifications)
    assert any("stop_medicine" in m for m in result.safety_modifications)
    assert result.warnings[0].startswith("High-risk interaction")


def test_only_as_needed_skips_routine_call(schedule):
    llm = FakeLLM({InteractionReview: [EMPTY_REVIEW]})
    req = AnalyzeRequest(medications=[Medication(name="Paracetamol", as_needed=True)], schedule=schedule)
    result = analyze(llm, req)
    assert result.routine.valid and result.routine.doses == [] and result.routine.attempts == 0
