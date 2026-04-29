from fastapi.testclient import TestClient

from app.llm.client import LLMError
from app.main import app, get_llm
from app.pipeline import INVALID_ROUTINE_SUMMARY, analyze
from app.schemas import (
    AIInteraction,
    AnalyzeRequest,
    DraftDose,
    ExtractedMedication,
    InteractionReview,
    Medication,
    PrescriptionExtraction,
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


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
def client_with(llm):
    app.dependency_overrides[get_llm] = lambda: llm
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


EXTRACTION = PrescriptionExtraction(
    is_prescription=True,
    medications=[
        ExtractedMedication(
            name="Tab Glucophage 500", generic_name="Metformin", strength="500 mg", dose="1 tab",
            doses_per_day=2, as_needed=False, meal_relation="with_food", instructions="1-0-1 PC",
            duration="30 days", uncertain_fields=[],
        )
    ],
    warnings=[],
)


def test_extract_text():
    llm = FakeLLM({PrescriptionExtraction: [EXTRACTION]})
    response = client_with(llm).post("/api/prescriptions/extract", data={"text": "Glucophage 500 1-0-1 PC"})
    assert response.status_code == 200
    assert response.json()["medications"][0]["generic_name"] == "Metformin"
    assert "<prescription>" in llm.calls[0]["content"][0]["text"]


def test_extract_image_sniffs_type():
    llm = FakeLLM({PrescriptionExtraction: [EXTRACTION]})
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    response = client_with(llm).post(
        "/api/prescriptions/extract", files={"file": ("rx.txt", png, "text/plain")}
    )
    assert response.status_code == 200
    assert llm.calls[0]["content"][0]["source"]["media_type"] == "image/png"


def test_extract_rejects_bad_input():
    client = client_with(FakeLLM())
    assert client.post("/api/prescriptions/extract", data={}).status_code == 422
    bad = client.post("/api/prescriptions/extract", files={"file": ("a.exe", b"MZ\x90\x00", "image/png")})
    assert bad.status_code == 415


def test_extract_llm_error_is_502():
    llm = FakeLLM({PrescriptionExtraction: [LLMError("The AI service is busy.")]})
    response = client_with(llm).post("/api/prescriptions/extract", data={"text": "x"})
    assert response.status_code == 502 and response.json()["detail"] == "The AI service is busy."


def test_analyze_endpoint(schedule):
    llm = FakeLLM({InteractionReview: [EMPTY_REVIEW], RoutineDraft: [good_draft()]})
    body = {
        "medications": [m.model_dump() for m in request(schedule).medications],
        "schedule": {"wake": "07:00", "breakfast": "08:00", "lunch": "13:00", "dinner": "20:00", "sleep": "23:00"},
    }
    response = client_with(llm).post("/api/analyze", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["routine"]["valid"] is True
    assert data["routine"]["doses"][0] == {
        "medicine": "Levothyroxine", "time": "07:15", "dose": "1 tablet",
        "note": "30-60 min before breakfast, with water",
    }


def test_analyze_validates_schedule_and_frequency():
    client = client_with(FakeLLM())
    body = {
        "medications": [{"name": "Metformin"}],
        "schedule": {"wake": "07:00", "breakfast": "08:00", "lunch": "13:00", "dinner": "20:00", "sleep": "23:00"},
    }
    assert client.post("/api/analyze", json=body).status_code == 422  # missing doses_per_day
    body["medications"] = [{"name": "Metformin", "doses_per_day": 2}]
    body["schedule"]["sleep"] = "01:00"
    assert client.post("/api/analyze", json=body).status_code == 422  # overnight
