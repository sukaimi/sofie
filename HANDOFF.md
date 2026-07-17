# SOFIE — Developer Handoff

Quick-start for anyone picking up this repo. For the full build spec read `CLAUDE.md`
and the `docs/` folder; this file is just current state + how to run and verify.

## What SOFIE is
AI-powered brand-compliant image compositor with a chat front-end (persona "Sofie").
A `.docx` brief is uploaded, a pipeline of agents (Priya, Ray, Celeste, Kai, Dana)
validates it, fetches/generates assets, composites layers (Pillow + Cairo/Pango), runs
QA, and delivers a downloadable image. See `docs/` for PRD/TDD/AGENTS/FLOWS.

## Current state (2026-07-17)
- **Deployed and working in production** at `https://sofie.codeandcraft.ai`.
- Full pipeline verified end-to-end on prod: fresh brief → composited 1080×1080 JPEG →
  operator approve → download. (Latest verified job: `JOB-c3b9395132d4`, Aurora Coffee.)
- **`.jpg` download issue is fixed** (commits `7613b48`, `e422aa7`, `3b6603e`): the
  download endpoint sets an explicit `Content-Disposition: attachment` with the real
  filename and `image/jpeg` MIME. Verified live (200, correct filename, full bytes,
  valid JPEG magic).

## Run locally
```bash
docker compose up --build          # redis + backend + celery + frontend + dashboard
# or backend only, for dev:
.venv/bin/python -m uvicorn backend.main:app --reload   # needs .env (see docs/ENV.md)
```
Frontend dev: `cd frontend && npm install && npm run dev`.
Secrets live in `.env` (never committed — see `docs/ENV.md` for the required keys).

## Verify a deployment (end-to-end smoke test)
`scripts/prod_e2e_smoke.py` drives one brief through the live system via the public
API + WebSocket (no browser needed). Useful as a post-deploy check.
```bash
# Needs a brief with LIVE asset links to produce an image and auto-approve delivery:
.venv/bin/python scripts/prod_e2e_smoke.py path/to/real_brief.docx --approve
# Against a different deployment:
.venv/bin/python scripts/prod_e2e_smoke.py brief.docx --base https://staging.example --approve
```
It uploads, confirms the brief, runs the pipeline, optionally approves, downloads the
JPEG, and verifies headers + bytes. Exit 0 = verified.

**Note:** `tests/test_brief.docx` uses `example.com` placeholder asset URLs that 404, so
the pipeline (correctly) blocks it at Ray's asset check — good for testing the
block/error path, but it will NOT produce an image. Use a brief with real asset links
for a full render.

## Production server (see the team for SSH access)
- Host: Hostinger KVM 2 (`srv1330842.hstgr.cloud`), Docker Compose in `/opt/sofie/`.
- Backend on host **:8002** (container 8000; nginx proxies `/api/` and `/ws/` there).
  Do **not** map the backend to :8000 — a co-hosted app owns it.
- Frontend static files served by host nginx from `/opt/sofie/frontend/dist`
  (`cd frontend && npm run build` then rsync to that path).
- Public API paths are under `/api/…`; bare `/job/…`/`/upload-brief` return nginx 404.
- Push access to `github.com/sukaimi/sofie` is on the `sukaimi` GitHub account.

## Known open items
- **Composition quality** — the headline can overlap faint background/hero text with a
  muddy overlay. Tracked with ~20 other polish items from first live testing.
- **`file_upload` via the browser UI** works for real users; automated browser tooling
  for uploads may be flaky depending on client versions — the smoke script above is the
  reliable headless path.

## Gotchas
- **SQLite "database is locked"**: WAL + `busy_timeout` are set per-connection in
  `backend/db.py`; don't set `journal_mode=WAL` inside a transaction (it's ignored).
- **WebSocket handler holds the pipeline synchronously** — concurrent uploads serialize
  (acceptable for the single-operator POC).
- **macOS python.org Python**: `websockets` needs an explicit certifi CA bundle for
  `wss://` (already handled in the smoke script) — otherwise `CERTIFICATE_VERIFY_FAILED`.
