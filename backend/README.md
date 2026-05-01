# MedGuard API

FastAPI backend: reads a prescription, checks food and drug interactions, and builds a daily
medicine timetable that a deterministic checker verifies.

## Run

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env            # add ANTHROPIC_API_KEY
.venv/bin/alembic upgrade head  # create/upgrade the database (SQLite at backend/medguard.db by default)
.venv/bin/uvicorn app.main:app --reload
.venv/bin/python -m pytest      # no API key needed (Claude is faked)
.venv/bin/python -m scripts.smoke_test   # live run against Claude (a few cents)
```

`requirements.txt` holds production dependencies only; `requirements-dev.txt` adds the test
tools. Production setup (Render, Postgres, Redis) is in [../DEPLOY.md](../DEPLOY.md).

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
- Rate limits: login is limited per email and per IP. Claude calls are limited per user
  (20 extractions and 20 routines an hour by default). Each user can save up to 50 routines.
  Limits live in Redis when `REDIS_URL` is set (required in production) and in memory
  otherwise. If Redis is unreachable, requests are allowed rather than blocked.

## How a routine is built

```
confirmed medicines + daily schedule
  -> curated dataset (data/drug_food_interactions.csv)       deterministic
  -> curated timing rules (data/timing_rules.json)            deterministic
  -> Claude interaction review (only what's missing)          labelled source="ai"
  -> constraint set (prescription > curated > ai > none)      deterministic
  -> Claude routine draft
  -> validator (app/scheduling/validator.py)                  accept / reject, one retry
  -> safety scrub (app/core/safety.py)
```

What Claude is allowed to do:
- It only proposes times. Dose amounts come from the confirmed prescription, and the validator
  rejects any change to how many doses a medicine gets per day.
- If the timetable still fails the checker after the retry, `routine.valid` is `false`. The
  summary then tells the user not to follow the times and to take the list to a pharmacist.
- Sentences that tell someone to change a dose, stop a medicine, or that diagnose are removed.
  Each removal is listed in `safety_modifications`.
- If Claude is unavailable, curated interactions and constraints are still returned.

## Known gaps

- Only daily medicines are scheduled. Weekly ones are flagged during extraction for the user to handle.
- Overnight schedules (sleep after midnight) are not supported yet.
- Routine jobs run inside the API process (FastAPI background tasks). One still `pending` after
  15 minutes is marked `failed` and can be retried. Use a queue if volume grows.
- No email verification or password reset yet. Both need an email provider.
- `timing_rules.json` is a small, conservative set taken from patient leaflets. It has not been
  clinically validated.
