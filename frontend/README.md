# MedGuard web app

Next.js 16 (App Router, Cache Components) + Tailwind v4 + shadcn/ui. Brand: see `../brand.md`.

## Run locally

```bash
# 1. API (from ../backend)
.venv/bin/uvicorn app.main:app --port 8000

# 2. Web app
npm install
npm run dev          # http://localhost:3000

# Deploying: see ../DEPLOY.md
```

The browser only talks to `localhost:3000`. `next.config.ts` forwards `/api/*` to the FastAPI
backend (`MEDGUARD_API_URL`, default `http://127.0.0.1:8000`), so the session cookie stays
same-origin.

## Pages

| Route | What it does |
|---|---|
| `/` | Landing page (static) |
| `/signup`, `/login` | Email and password; `?next=` returns you to where you were |
| `/routines` | Saved routines |
| `/routines/new` | Prescription → review medicines → your day → build |
| `/routines/[id]` | Timetable, interactions, timing rules, rename, delete |
| `/account` | Log out, delete account |

`src/proxy.ts` sends visitors with no session cookie from `/routines` and `/account` to
`/login`. It's only a convenience: the API checks the session on every request.

## Notes

- Routines are built in the background: the wizard saves and goes to `/routines/[id]`, which
  shows progress and polls every 3 s until the routine is ready or failed (with **Try again**).
  No request waits on the AI for long, which keeps under Vercel's 120 s proxy limit.
- Reading a prescription is one AI call (10–30 s). Locally `experimental.proxyTimeout` is
  120 s, and uploads up to 10 MB pass through `proxyClientMaxBodySize`.
- Security headers, including a Content-Security-Policy in production builds, are set in
  `next.config.ts`.
- Per-user data is fetched in client components. Pages prerender as static shells.
- Types in `src/lib/types.ts` mirror `backend/app/schemas.py`. Update both together.
- shadcn components were adjusted for 40 px minimum touch targets, and Badge/Alert gained
  `warning` and `success` variants for risk levels.
