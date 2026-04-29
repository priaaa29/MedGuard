# MedGuard API

FastAPI backend: reads a prescription, checks food and drug interactions, and builds a daily
medicine timetable that a deterministic checker verifies.

## Run

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # add ANTHROPIC_API_KEY
.venv/bin/uvicorn app.main:app --reload
.venv/bin/python -m pytest      # no API key needed (Claude is faked)
.venv/bin/python -m scripts.smoke_test   # live run against Claude (a few cents)
```

## Endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/health` | | `{"status": "ok"}` |
| POST | `/api/prescriptions/extract` | multipart: `file` (JPEG/PNG/WebP/GIF/PDF, ≤10 MB) **or** `text` | `PrescriptionExtraction`, for the user to review and correct |
| POST | `/api/analyze` | `{"medications": [Medication], "schedule": DailySchedule}` | `AnalysisResult` |

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
- `timing_rules.json` is a small, conservative set taken from patient leaflets. It has not been
  clinically validated.
