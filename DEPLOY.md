# Deploying MedGuard

Two parts, plus the old Streamlit demo that stays as it is for now:

| Part | Host | Config |
|---|---|---|
| API (FastAPI), Postgres, Redis | Render, Singapore region | `render.yaml` |
| Web app (Next.js) | Vercel | `frontend/` + one env var |
| Old Streamlit demo | Streamlit Cloud (unchanged) | root `requirements.txt`, `src/app.py` |

The browser only talks to the Vercel domain. Vercel forwards `/api/*` to Render, so the
session cookie stays on one origin.

## Before you start

- [ ] **Anthropic API key** for production, ideally a separate one from development.
      Set a monthly **spend limit** in the Anthropic Console. Per-user limits in the app cap
      each account at 20 prescription reads and 20 routines an hour.
- [ ] **CI is green on `main`.** Render only deploys after GitHub Actions passes
      (`autoDeployTrigger: checksPass`).
- [ ] **Medical review of `backend/data/timing_rules.json`** by someone qualified. It's a
      small, conservative set of rules, but it hasn't been clinically validated.
- [ ] Optional: `render blueprints validate render.yaml` (Render CLI v2.7+).

## 1. API on Render

1. Render dashboard → **New → Blueprint** → pick the `MedGuard` repo. Render reads `render.yaml`
   and plans three resources: `medguard-api`, `medguard-db` (Postgres 17) and `medguard-redis`.
2. When asked for secrets:
   - `ANTHROPIC_API_KEY`: your production key.
   - `MEDGUARD_CORS_ORIGINS`: put `https://placeholder.invalid` for now. You'll set the real
     Vercel URL in step 3.
3. Create the Blueprint. On first start the API runs `alembic upgrade head`, which creates the
   tables, then starts uvicorn.
4. Check `https://medguard-api.onrender.com/api/health` (your service URL may differ). It
   should return `{"status":"ok"}`. That also confirms the database connection.

Plans in `render.yaml`:
- **API on `free`:** sleeps after ~15 min idle, and the next request takes about a minute.
  Move to a paid instance before real users.
- **Postgres on the smallest paid plan:** free Render databases are deleted after 30 days.
- **Key Value on `free`.**

## 2. Web app on Vercel

1. Vercel → **Add New → Project** → import the repo.
2. **Root Directory:** `frontend`. Vercel detects Next.js.
3. **Environment variable** (Production): `MEDGUARD_API_URL` = your Render API URL, e.g.
   `https://medguard-api.onrender.com`. No trailing slash, no `/api`.
4. Deploy, and note the production URL (e.g. `https://medguard.vercel.app`, or your custom domain).

## 3. Connect them

1. Render → `medguard-api` → Environment → set `MEDGUARD_CORS_ORIGINS` to the Vercel
   production URL exactly, e.g. `https://medguard.vercel.app`. Comma-separate if you also use a
   custom domain. Save; Render redeploys.
2. Without this, every sign-up, login and save fails with **"Cross-site request blocked."**
   (403). That's the CSRF check working. **Vercel preview deployments** have their own URLs,
   so writes are blocked there unless you add those origins too.

## 4. Smoke test (production)

- [ ] Landing page loads over HTTPS. DevTools shows `Content-Security-Policy` on the page.
- [ ] Sign up → you land on **New routine**. In DevTools → Application → Cookies,
      `medguard_session` is **HttpOnly**, **Secure** and **SameSite=Lax**.
- [ ] Type a short prescription (e.g. `Metformin 500 mg BD after food`) → **Read prescription**
      → the medicine appears for review. This is the first real Claude call.
- [ ] Build the routine → the page shows **Building your routine**, then the timetable on its
      own within about a minute.
- [ ] Upload a photo of a prescription → the medicines are read.
- [ ] Log out → `/routines` redirects to `/login`.
- [ ] Account → Delete account works and you're logged out.

## Day-to-day

- **Deploys:** merge to `main` → CI runs → Render deploys the API once checks pass. Vercel
  deploys the web app on every push (previews for branches, production for `main`).
- **Schema changes:** edit `backend/app/models.py`, then from `backend/` run
  `alembic revision --autogenerate -m "describe it"`. Review the file and commit it. Production
  applies it on the next deploy. CI fails if models and migrations drift apart (`alembic check`).
- **Logs:** Render → `medguard-api` → Logs. Each Claude call logs model, request id, stop reason
  and token counts. The app doesn't log prescription text or medicine names on purpose, but
  error tracebacks can include request data, so treat logs as sensitive.
- **Rollback:** Render → Deploys → pick a previous deploy → Rollback. Vercel → Deployments →
  Promote a previous one. A rollback doesn't undo a database migration; write a new migration
  instead.

## Known limits

- **Routine jobs run inside the API process.** If it restarts mid-job, that routine shows
  "Couldn't build" after 15 minutes, and the user can press **Try again**. Move to a queue (e.g.
  a Render background worker) if volume grows.
- **IP-based limits rely on the forwarded client IP.** Someone calling the Render URL directly
  can fake it. The per-email and per-user limits don't depend on IP.
- **Email verification and password reset need an email provider.** Neither exists yet.
- **The Streamlit demo still runs separately** with its own CSV path (`backend/data/`). Retire
  it once the new app is live.
