from sqlalchemy import func, select

from app.config import SESSION_COOKIE
from app.llm.client import LLMError
from app.models import AuthSession, SavedRoutine, User
from app.ratelimit import RateLimiter
from app.schemas import (
    DraftDose,
    ExtractedMedication,
    InteractionReview,
    PrescriptionExtraction,
    RoutineDraft,
)
from tests.conftest import FakeLLM

PASSWORD = "correct horse battery"
SCHEDULE = {"wake": "07:00", "breakfast": "08:00", "lunch": "13:00", "dinner": "20:00", "sleep": "23:00"}
MEDICATIONS = [
    {"name": "Metformin", "strength": "500 mg", "dose": "1 tablet", "doses_per_day": 2},
    {"name": "Paracetamol", "as_needed": True},
]
EMPTY_REVIEW = InteractionReview(interactions=[], separations=[], meal_guidance=[])
GOOD_DRAFT = RoutineDraft(
    doses=[
        DraftDose(medicine="Metformin", time="08:00", note="With breakfast"),
        DraftDose(medicine="Metformin", time="20:00", note="With dinner"),
    ],
    food_guidance=["Limit alcohol."],
    summary="Metformin with breakfast and dinner.",
)
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


def routine_llm(n=1):
    return FakeLLM({InteractionReview: [EMPTY_REVIEW] * n, RoutineDraft: [GOOD_DRAFT] * n})


def signup(client, email="priya@example.com"):
    response = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return response


def create_routine(client, title=None):
    body = {"medications": MEDICATIONS, "schedule": SCHEDULE}
    if title:
        body["title"] = title
    return client.post("/api/routines", json=body)


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
def test_register_sets_secure_session_cookie(make_client):
    client = make_client()
    response = signup(client, "Priya@Example.com")
    assert response.json()["email"] == "priya@example.com"

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert client.get("/api/auth/me").json()["email"] == "priya@example.com"

    with make_client.session() as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith("$argon2")
        token = client.cookies[SESSION_COOKIE]
        assert token not in db.scalar(select(AuthSession.token_hash))


def test_register_rejects_duplicates_and_weak_passwords(make_client):
    client = make_client()
    signup(client)
    dup = client.post("/api/auth/register", json={"email": "PRIYA@example.com", "password": PASSWORD})
    assert dup.status_code == 409
    weak = client.post("/api/auth/register", json={"email": "a@example.com", "password": "short"})
    assert weak.status_code == 422
    bad_email = client.post("/api/auth/register", json={"email": "nope", "password": PASSWORD})
    assert bad_email.status_code == 422


def test_login_logout_and_revocation(make_client):
    signup(make_client())
    client = make_client()

    wrong = client.post("/api/auth/login", json={"email": "priya@example.com", "password": "wrong password"})
    unknown = client.post("/api/auth/login", json={"email": "who@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # no account enumeration

    assert client.post("/api/auth/login", json={"email": "priya@example.com", "password": PASSWORD}).status_code == 200
    token = client.cookies[SESSION_COOKIE]
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    # The old token is dead server-side, not just deleted from the browser.
    replay = make_client()
    replay.cookies.set(SESSION_COOKIE, token)
    assert replay.get("/api/auth/me").status_code == 401


def test_login_is_rate_limited(make_client):
    client = make_client()
    signup(client)
    body = {"email": "priya@example.com", "password": "wrong password"}
    codes = [client.post("/api/auth/login", json=body).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_rate_limiter_window():
    limiter = RateLimiter()
    assert all(limiter.hit("k", 3, 60) for _ in range(3))
    assert not limiter.hit("k", 3, 60)
    assert limiter.hit("other", 3, 60)
    assert limiter.hit("k2", 1, 0)  # zero-length window never blocks


def test_delete_account_removes_everything(make_client):
    client = make_client(routine_llm())
    signup(client)
    assert create_routine(client).status_code == 202

    assert client.request("DELETE", "/api/auth/me", json={"password": "nope"}).status_code == 401
    assert client.request("DELETE", "/api/auth/me", json={"password": PASSWORD}).status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    with make_client.session() as db:
        for model in (User, AuthSession, SavedRoutine):
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_cross_site_writes_are_blocked(make_client):
    client = make_client()
    body = {"email": "priya@example.com", "password": PASSWORD}
    evil = client.post("/api/auth/register", json=body, headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403
    ours = client.post("/api/auth/register", json=body, headers={"Origin": "http://localhost:3000"})
    assert ours.status_code == 201


# --------------------------------------------------------------------------- #
# Prescriptions
# --------------------------------------------------------------------------- #
def test_extract_requires_login(make_client):
    response = make_client().post("/api/prescriptions/extract", data={"text": "x"})
    assert response.status_code == 401


def test_extract_text(make_client):
    llm = FakeLLM({PrescriptionExtraction: [EXTRACTION]})
    client = make_client(llm)
    signup(client)
    response = client.post("/api/prescriptions/extract", data={"text": "Glucophage 500 1-0-1 PC"})
    assert response.status_code == 200
    assert response.json()["medications"][0]["generic_name"] == "Metformin"
    assert "<prescription>" in llm.calls[0]["content"][0]["text"]


def test_extract_image_sniffs_type(make_client):
    llm = FakeLLM({PrescriptionExtraction: [EXTRACTION]})
    client = make_client(llm)
    signup(client)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    response = client.post("/api/prescriptions/extract", files={"file": ("rx.txt", png, "text/plain")})
    assert response.status_code == 200
    assert llm.calls[0]["content"][0]["source"]["media_type"] == "image/png"


def test_extract_rejects_bad_input(make_client):
    client = make_client()
    signup(client)
    assert client.post("/api/prescriptions/extract", data={}).status_code == 422
    exe = client.post("/api/prescriptions/extract", files={"file": ("a.png", b"MZ\x90\x00", "image/png")})
    assert exe.status_code == 415


def test_extract_llm_error_is_502(make_client):
    client = make_client(FakeLLM({PrescriptionExtraction: [LLMError("The AI service is busy.")]}))
    signup(client)
    response = client.post("/api/prescriptions/extract", data={"text": "x"})
    assert response.status_code == 502 and response.json()["detail"] == "The AI service is busy."


# --------------------------------------------------------------------------- #
# Routines
# --------------------------------------------------------------------------- #
def test_routine_lifecycle(make_client):
    client = make_client(routine_llm())
    signup(client)

    created = create_routine(client)
    assert created.status_code == 202, created.text
    data = created.json()
    # The response comes back before the routine is built...
    assert data["status"] == "pending" and data["result"] is None
    assert data["title"] == "Metformin, Paracetamol"
    assert data["schedule"] == SCHEDULE
    assert [m["name"] for m in data["medications"]] == ["Metformin", "Paracetamol"]

    # ...and the background job has finished by the next request (TestClient runs it inline).
    detail = client.get(f"/api/routines/{data['id']}").json()
    assert detail["status"] == "ready" and detail["error"] is None
    assert detail["result"]["routine"]["valid"] is True
    assert detail["result"]["routine"]["doses"][0]["dose"] == "1 tablet (500 mg)"

    [summary] = client.get("/api/routines").json()
    assert summary["id"] == data["id"] and summary["status"] == "ready"
    assert summary["dose_count"] == 2 and summary["valid"] is True
    assert summary["medicines"] == ["Metformin", "Paracetamol"]

    renamed = client.patch(f"/api/routines/{data['id']}", json={"title": "Mum's tablets"})
    assert renamed.json()["title"] == "Mum's tablets"
    assert client.delete(f"/api/routines/{data['id']}").status_code == 204
    assert client.get("/api/routines").json() == []


def test_routines_are_private(make_client):
    owner = make_client(routine_llm())
    signup(owner, "owner@example.com")
    routine_id = create_routine(owner).json()["id"]

    other = make_client()
    signup(other, "other@example.com")
    assert other.get("/api/routines").json() == []
    assert other.get(f"/api/routines/{routine_id}").status_code == 404
    assert other.patch(f"/api/routines/{routine_id}", json={"title": "x"}).status_code == 404
    assert other.delete(f"/api/routines/{routine_id}").status_code == 404
    assert owner.get(f"/api/routines/{routine_id}").status_code == 200


def test_routines_require_login(make_client):
    client = make_client()
    assert client.get("/api/routines").status_code == 401
    assert create_routine(client).status_code == 401


def test_routine_fails_cleanly_when_ai_unavailable_then_retries(make_client, monkeypatch):
    monkeypatch.setattr("app.config.ROUTINE_PLANNER", "llm")  # timetable drafted by the AI
    llm = FakeLLM({InteractionReview: [LLMError("busy")], RoutineDraft: [LLMError("The AI service is busy.")]})
    client = make_client(llm)
    signup(client)
    routine_id = create_routine(client).json()["id"]

    failed = client.get(f"/api/routines/{routine_id}").json()
    assert failed["status"] == "failed" and failed["error"] == "The AI service is busy."
    assert failed["result"] is None
    [summary] = client.get("/api/routines").json()
    assert summary["status"] == "failed" and summary["valid"] is None and summary["dose_count"] == 0

    # Retry once Claude is back.
    llm.responses = {InteractionReview: [EMPTY_REVIEW], RoutineDraft: [GOOD_DRAFT]}
    retried = client.post(f"/api/routines/{routine_id}/retry")
    assert retried.status_code == 202 and retried.json()["status"] == "pending"
    assert client.get(f"/api/routines/{routine_id}").json()["status"] == "ready"
    # Only failed routines can be retried.
    assert client.post(f"/api/routines/{routine_id}/retry").status_code == 409


def test_unexpected_job_error_marks_routine_failed(make_client, monkeypatch):
    monkeypatch.setattr("app.config.ROUTINE_PLANNER", "llm")
    llm = FakeLLM({InteractionReview: [EMPTY_REVIEW], RoutineDraft: [RuntimeError("boom")]})
    client = make_client(llm)
    signup(client)
    routine_id = create_routine(client).json()["id"]
    detail = client.get(f"/api/routines/{routine_id}").json()
    assert detail["status"] == "failed"
    assert "boom" not in detail["error"]  # internals never reach the user


def test_scheduler_routine_ready_even_when_ai_is_down(make_client, monkeypatch):
    monkeypatch.setattr("app.config.ROUTINE_PLANNER", "scheduler")
    client = make_client(FakeLLM({InteractionReview: [LLMError("The AI service has reached its usage limit for now.")]}))
    signup(client)
    routine_id = create_routine(client).json()["id"]
    detail = client.get(f"/api/routines/{routine_id}").json()
    assert detail["status"] == "ready" and detail["result"]["routine"]["valid"] is True
    assert any("unavailable" in w for w in detail["result"]["warnings"])


def test_stale_pending_routine_is_marked_failed(make_client):
    from datetime import timedelta

    from app.db import utcnow

    client = make_client(routine_llm())
    signup(client)
    with make_client.session() as db:
        user = db.scalar(select(User))
        row = SavedRoutine(
            user_id=user.id, title="Lost", medications=MEDICATIONS, schedule=SCHEDULE, status="pending",
            created_at=utcnow() - timedelta(hours=1), updated_at=utcnow() - timedelta(hours=1),
        )
        db.add(row)
        db.commit()
        routine_id = row.id

    detail = client.get(f"/api/routines/{routine_id}").json()
    assert detail["status"] == "failed" and "too long" in detail["error"]


def test_routine_validation(make_client):
    client = make_client()
    signup(client)
    body = {"medications": [{"name": "Metformin"}], "schedule": SCHEDULE}
    assert client.post("/api/routines", json=body).status_code == 422  # missing doses_per_day
    body = {"medications": [{"name": "Metformin", "doses_per_day": 2}], "schedule": {**SCHEDULE, "sleep": "01:00"}}
    assert client.post("/api/routines", json=body).status_code == 422  # overnight
    dupes = {"medications": [MEDICATIONS[0], {**MEDICATIONS[0], "name": "metformin"}], "schedule": SCHEDULE}
    assert client.post("/api/routines", json=dupes).status_code == 422


# --------------------------------------------------------------------------- #
# Hardening
# --------------------------------------------------------------------------- #
def test_api_responses_are_never_cached(make_client):
    client = make_client()
    signup(client)
    response = client.get("/api/auth/me")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_health_checks_database(make_client):
    response = make_client().get("/api/health")
    assert response.status_code == 200 and response.json() == {"status": "ok"}


def test_unhandled_errors_return_generic_json(make_client, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api import accounts
    from app.main import app

    def explode(*args, **kwargs):
        raise RuntimeError("secret internals")

    make_client()
    monkeypatch.setattr(accounts, "user_for_token", explode, raising=False)
    monkeypatch.setattr("app.api.deps.user_for_token", explode)
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set(SESSION_COOKIE, "anything")
    response = client.get("/api/auth/me")
    assert response.status_code == 500
    assert "secret" not in response.text and response.headers["cache-control"] == "no-store"


def test_redis_rate_limiter():
    import fakeredis

    from app.ratelimit import RedisRateLimiter

    limiter = RedisRateLimiter(fakeredis.FakeRedis())
    assert all(limiter.hit("k", 3, 60) for _ in range(3))
    assert not limiter.hit("k", 3, 60)
    assert limiter.hit("other", 3, 60)
    limiter.reset()
    assert limiter.hit("k", 3, 60)


def test_redis_outage_fails_open():
    from app.ratelimit import RedisRateLimiter

    class Down:
        def pipeline(self):
            raise ConnectionError("redis down")

    assert RedisRateLimiter(Down()).hit("k", 1, 60)
