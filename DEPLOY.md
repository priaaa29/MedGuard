# Deploying MedGuard (free)

Everything here runs on free plans:

| Part | Host | Cost |
|---|---|---|
| Web app (Next.js) | Vercel (Hobby) | Free |
| API (FastAPI) + Redis | Render (free web service + free Key Value), via `render.yaml` | Free |
| Postgres | Neon (free plan, doesn't expire) | Free |
| AI: reading prescriptions, extra interaction checks | Google Gemini API (free tier) | Free, with small daily limits |
| Old Streamlit demo | Streamlit Cloud (unchanged) | Free |

Daily times are planned by MedGuard's built-in scheduler, so building a routine doesn't use
the AI quota. Gemini is called once to read a prescription and once to check interactions.

The browser only talks to the Vercel domain. Vercel forwards `/api/*` to the Render API, so
the session cookie stays on one origin.

## Before you start

- [ ] CI is green on `main`. Render only deploys after GitHub Actions passes.
- [ ] Medical review of `backend/data/timing_rules.json` by someone qualified. It hasn't been
      clinically validated.

### About Gemini's free tier (read this)

Google's Gemini API terms for unpaid use say Google may use what you send to improve its
products, and that human reviewers may read it. They also say not to send sensitive or personal
information. MedGuard limits what it sends:

- **Interaction checks** send only medicine names, strengths and timing. No name, email or
  account data.
- **Reading a prescription** sends the photo, PDF or text the user provides. The upload screen
  tells people to cover their name, address and doctor's details, or to type just the medicine
  lines.

For real patients, move to a paid tier: a Gemini key on a billed Google Cloud project, or Claude
with `MEDGUARD_LLM_PROVIDER=anthropic`. Paid use isn't used to improve the provider's models.

Free quotas are per Google Cloud project and only shown in Google AI Studio. Check yours under
**AI Studio → Rate limits**. The default model is `gemini-3.5-flash-lite`, which Google
recommends for low-cost use. Change it with `MEDGUARD_GEMINI_MODEL`.

## 1. Database on Neon

1. Sign up at https://neon.tech (GitHub login works). The free plan needs no card.
2. Create a project. Pick region **AWS Asia Pacific (Singapore)**, the same region as the API.
3. On the project dashboard, open **Connect**, choose the default branch and database, and copy
   two connection strings. Keep both private.
   - **Pooled** (Connection pooling on, hostname contains `-pooler`): the app's `DATABASE_URL`.
   - **Direct** (Connection pooling off): `DATABASE_URL_UNPOOLED`, used to run migrations.

   Or from the repo root, with the Neon CLI: `npx neon@latest init` links the project and
   writes both to `.env.local` (git-ignored).

## 2. Gemini API key

1. Go to https://aistudio.google.com/apikey and sign in with your Google account.
2. **Create API key** and copy it. Don't add billing if you want to stay free.

## 3. API on Render

1. Render dashboard → **New → Blueprint** → connect GitHub if asked → pick `priaaa29/MedGuard`,
   branch `main`. Render reads `render.yaml` and lists `medguard-routines-api` and
   `medguard-redis`, both on free plans.
2. Fill in the secrets when asked:
   - `DATABASE_URL`: the pooled Neon connection string from step 1.
   - `DATABASE_URL_UNPOOLED`: the direct Neon connection string from step 1.
   - `GEMINI_API_KEY`: the key from step 2.
   - `MEDGUARD_CORS_ORIGINS`: the web app's address, e.g. `https://medguard-rose.vercel.app`.
3. **Apply.** On first start the API runs `alembic upgrade head` over the direct connection,
   which creates the tables in Neon, then starts.
4. When the service shows **Live**, copy its URL from the top of the page, e.g.
   `https://medguard-routines-api.onrender.com`. Use the URL Render shows, because it can add a
   suffix. Opening `<that URL>/api/health` should return `{"status":"ok"}`.

The free API sleeps after about 15 minutes without traffic, so the next visit takes around a
minute to wake it.

## 4. Web app on Vercel

The `medguard` project already exists. Point it at the API from step 3:

```bash
cd frontend
vercel env rm MEDGUARD_API_URL production --yes
printf 'https://<your-render-url>' | vercel env add MEDGUARD_API_URL production
vercel deploy --prod
```

Use no trailing slash and no `/api`. If you ever use a different web address (a custom domain,
say), add it to `MEDGUARD_CORS_ORIGINS` on Render. Otherwise sign-up and login fail with
"Cross-site request blocked." Vercel preview URLs are blocked the same way unless you add them.

## 5. Smoke test

- [ ] `https://<web app>/api/health` returns `{"status":"ok"}`. This wakes the API if it's asleep.
- [ ] Sign up → you land on **New routine**. In DevTools → Application → Cookies,
      `medguard_session` is **HttpOnly**, **Secure** and **SameSite=Lax**.
- [ ] **Type it** → `Metformin 500 mg BD after food` → **Read prescription** → the medicine
      appears for review. This is the first real Gemini call.
- [ ] Build the routine → **Building your routine**, then the timetable within seconds.
- [ ] Log out → `/routines` redirects to `/login`.
- [ ] Account → Delete account works.

## Day-to-day

- **Deploys:** merge to `main` → CI → Render deploys the API once checks pass. To update the
  web app, run `vercel deploy --prod` from `frontend/`, or connect the Vercel project to GitHub
  (Settings → Git, Root Directory `frontend`) for automatic deploys.
- **Schema changes:** edit `backend/app/models.py`, then from `backend/` run
  `alembic revision --autogenerate -m "describe it"`, review it, and commit it. CI fails if models
  and migrations drift apart.
- **Logs:** Render → `medguard-routines-api` → Logs. AI calls log model, finish reason and token
  counts. The app doesn't log prescription text or medicine names on purpose, but error
  tracebacks can include request data, so treat logs as sensitive.
- **Rollback:** Render → Deploys → Rollback. Vercel → Deployments → Promote a previous one.
  A rollback doesn't undo database migrations.

## Known limits

- **When the daily Gemini quota runs out,** reading prescriptions shows "usage limit reached".
  Typing medicines on the review screen and building routines still work.
- **Routine jobs run inside the API process.** A restart mid-job marks that routine
  "Couldn't build" after 15 minutes, and the user can press **Try again**.
- **IP-based rate limits trust the forwarded client IP.** Someone hitting the Render URL
  directly can fake it. Per-email and per-user limits don't depend on IP.
- **No email verification or password reset yet.**
