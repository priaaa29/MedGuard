# MedGuard API

FastAPI backend: reads a prescription, checks food and drug interactions, and builds a daily
medicine timetable that a deterministic checker verifies.

## Run

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env            # add GEMINI_API_KEY (free from aistudio.google.com/apikey)
.venv/bin/alembic upgrade head  # create/upgrade the database (SQLite at backend/medguard.db by default)
.venv/bin/uvicorn app.main:app --reload
.venv/bin/python -m pytest      # no API key needed (the AI is faked)
.venv/bin/python -m scripts.smoke_test   # live run against the configured AI (2 calls)
```

`requirements.txt` holds production dependencies only; `requirements-dev.txt` adds the test
tools. Production setup (Render, Neon Postgres, Redis, all free) is in [../DEPLOY.md](../DEPLOY.md).

## AI provider

| Setting | Default | Options |
|---|---|---|
| `MEDGUARD_LLM_PROVIDER` | `gemini` | `gemini` (free tier) or `anthropic` (Claude, paid) |
| `MEDGUARD_GEMINI_MODEL` | `gemini-3.5-flash-lite` | any Gemini model with JSON-schema output |
| `MEDGUARD_ROUTINE_PLANNER` | `scheduler` | `scheduler` (built-in, no AI call) or `llm` (AI drafts, up to 2 calls) |

The AI is used for two things: reading a prescription (`app/llm/extract.py`) and checking
for interactions the curated data misses (`app/llm/review.py`). Both use JSON-schema output
behind one interface (`StructuredLLM`), with adapters in `app/llm/gemini.py` and
`app/llm/client.py` (Claude).

Gemini's free tier may use inputs to improve Google's products, with human review. Interaction
checks send only medicine details. The upload screen asks people to cover their personal details.
Use a paid tier for real patient data (see DEPLOY.md).

## Endpoints

Every endpoint except health, register and login needs a logged-in session cookie.

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/health` | | `{"status": "ok"}` |
| POST | `/api/auth/register` | `{email, password}` (password ≥10 chars) | `UserOut` + session cookie |
| POST | `/api/auth/login` | `{email, password}` | `UserOut` + session cookie |
| POST | `/api/auth/logout` | | 204, session revoked |
| GET | `/api/auth/me` | | `UserOut` |
| DELETE | `/api/auth/me` | `{password}` | 204, deletes the account and all its routines |
| POST | `/api/prescriptions/extract` | multipart: `file` (JPEG/PNG/WebP/GIF/PDF, ≤10 MB) **or** `text` | `PrescriptionExtraction`, for the user to review and correct |
| POST | `/api/routines` | `{medications, schedule, title?}` | **202** `RoutineDetail` with `status: "pending"`; the routine is built in the background |
| POST | `/api/routines/{id}/retry` | | **202**, re-runs a `failed` routine |
| GET | `/api/routines` | | `[RoutineSummary]` |
| GET | `/api/routines/{id}` | | `RoutineDetail`; poll until `status` is `ready` or `failed` |
| PATCH | `/api/routines/{id}` | `{title}` | `RoutineSummary` |
| DELETE | `/api/routines/{id}` | | 204 |

## Accounts and data

- Passwords are hashed with argon2. A wrong password and an unknown email return the same
  error and take the same time.
- Sessions are server-side. The browser holds a random token in an httpOnly, `SameSite=Lax`
  cookie (also `Secure` in production). The database stores only the token's SHA-256, and
  logging out deletes the session row.
- The frontend is meant to proxy `/api` from its own origin. Writes that carry an `Origin`
  other than `MEDGUARD_CORS_ORIGINS` are rejected (CSRF defence).
- Every query for a routine filters by the logged-in user, and someone else's routine
  returns 404.
- Prescription files are read in memory and never stored. A saved routine keeps the confirmed
  medicines, the schedule and the result.
- Rate limits: login is limited per email and per IP. AI calls are limited per user
  (20 extractions and 20 routines an hour by default). Each user can save up to 50 routines.
  Limits live in Redis when `REDIS_URL` is set (required in production) and in memory
  otherwise. If Redis is unreachable, requests are allowed rather than blocked.

## How a routine is built

```
confirmed medicines + daily schedule
  -> curated dataset (data/drug_food_interactions.csv)       deterministic
  -> curated timing rules (data/timing_rules.json)            deterministic
  -> AI interaction review (only what's missing)              labelled source="ai"
  -> constraint set (prescription > curated > ai > none)      deterministic
  -> timetable: built-in scheduler (app/scheduling/planner.py) deterministic, default
                or AI draft (app/llm/routine.py, one retry)   MEDGUARD_ROUTINE_PLANNER=llm
  -> validator (app/scheduling/validator.py)                  accept / reject
  -> safety scrub (app/core/safety.py)
```

The scheduler lists candidate times for each medicine that meet its own rules: dose count,
waking hours, food timing, morning or evening, and spacing. It then searches across medicines,
most constrained first, for a combination that also keeps every required gap between them.
It prefers times anchored to meals, waking and bedtime. If no combination works,
`routine.valid` is `false` with a `no_schedule` issue.

What the AI is allowed to do:
- Dose amounts always come from the confirmed prescription, and the validator rejects any
  change to how many doses a medicine gets per day.
- If an AI-drafted timetable still fails the checker after the retry, `routine.valid` is
  `false`. The summary then tells the user not to follow the times and to take the list to a
  pharmacist.
- Sentences that tell someone to change a dose, stop a medicine, or that diagnose are removed.
  Each removal is listed in `safety_modifications`.
- If the AI is unavailable or out of quota, curated interactions still come back. With the
  scheduler, the routine is still built.

## Known gaps

- Only daily medicines are scheduled. Weekly ones are flagged during extraction for the user to handle.
- Overnight schedules (sleep after midnight) are not supported yet.
- Routine jobs run inside the API process (FastAPI background tasks). One still `pending` after
  15 minutes is marked `failed` and can be retried. Use a queue if volume grows.
- No email verification or password reset yet. Both need an email provider.
- `timing_rules.json` is a small, conservative set taken from patient leaflets. It has not been
  clinically validated.
