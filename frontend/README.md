# MedGuard web app

Next.js 16 (App Router, Cache Components) + Tailwind v4 + shadcn/ui. Brand: see `../brand.md`.

## Run locally

```bash
# 1. API (from ../backend)
.venv/bin/uvicorn app.main:app --port 8000

# 2. Web app
npm install
npm run dev          # http://localhost:3000
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

- Building a routine can take a minute (up to three Claude calls), so `experimental.proxyTimeout`
  is raised to 4 minutes. Uploads up to 10 MB pass through `proxyClientMaxBodySize`.
- Per-user data is fetched in client components. Pages prerender as static shells.
- Types in `src/lib/types.ts` mirror `backend/app/schemas.py`. Update both together.
- shadcn components were adjusted for 40 px minimum touch targets, and Badge/Alert gained
  `warning` and `success` variants for risk levels.
