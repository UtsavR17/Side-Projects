# FormEdge — Horse Racing Prediction & Analytics System

Personal intelligence platform for Mauritius (MTC) horse racing: automated data
ingestion, rich profiles, an ensemble ML pipeline with stored explanations,
prediction-accuracy tracking, and a fast cache-first API + web dashboard.

Built from the master plan in `horse-racing-system-plan.md` (prompts A–D + F;
Flutter mobile deferred).

## Repository layout

```
backend/
  app/                 FastAPI application (cache-first REST API)
    models/            SQLAlchemy schema (all §5 entities + prefs + flags)
    routers/           races, horses, jockeys/trainers, predictions,
                       leaderboard, notifications, simulator, admin, SSE
    services/          serializers, profiles, form stats, notifications, FCM
  pipeline/            background stages (NEVER triggered by API requests)
    scrape_mtc.py      polite fixtures/results scraper + ingestion
    import_files.py    human-in-the-loop import (CSV or saved HTML pages)
    parsing.py         shared date/time/number parsers (scraper + importer)
    clean.py           name normalization / entity resolution / flags
    features.py        horse_form_snapshots (leakage-free, precomputed)
    weather.py         Open-Meteo race-day weather enrichment
    cache_warm.py      pushes fresh payloads into Redis
    run.py             stage CLI: python -m pipeline.run --stage <name>
    scheduler.py       APScheduler worker (docker `worker` service)
    ml/                train → predict → explain → evaluate (Prompt C)
  tests/               pytest suite (SQLite + in-memory cache fallback)
  seed_demo.py         SYNTHETIC demo data for local development
docs/                  simulator-guide.md, data-import.md
frontend/              Next.js (App Router, ISR revalidate=300) dashboard
docker-compose.yml     api + worker + postgres + redis + web
```

## Data sources — read this before expecting live data

Checked directly (2026-09):

| Source | Status | Consequence |
|---|---|---|
| `mtcjockeyclub.com` (plan's primary) | `robots.txt` returns **HTTP 403 + Cloudflare JS challenge** | Automated scraping is off the table (RFC 9309: a denied robots file means stay out). I do not attempt to bypass bot protection |
| `supertote.mu` | robots allows crawling, but race data is rendered **client-side** (one JS bundle) | Nothing server-side to parse without reverse-engineering their app — not done |
| `mauritiusturfclub.com` | DNS/connect failure | Not a usable source |
| Open-Meteo (weather) | 200 OK, free | ✅ Works, used by the `weather` stage |

So the platform ingests real data through **two** paths, both feeding the same
downstream pipeline:

```powershell
.\run-pipeline.ps1 scrape                          # if/when a source permits automation
.\run-pipeline.ps1 import .\incoming\*.csv         # human-supplied CSV or saved HTML
```

Full schema, CLI/API examples and troubleshooting:
**[docs/data-import.md](docs/data-import.md)**. The import path is deliberately
idempotent and records every miss in `data_quality_flags` rather than inventing
data.


## Core contract (why it's fast)

The user-facing app **never talks to an external site and never runs a model**.
A background worker executes `scrape → clean → features → predict → explain →
evaluate → cache warm` on a schedule; the API only reads Redis (Postgres on
miss). Explanations (SHAP for tree models) are **stored at prediction time**,
not computed per request.


## Pipeline stages

| Stage | What it does | Notifies |
|---|---|---|
| `scrape` | Polite fetch (robots.txt honoured, rate limit, HTML disk cache), parse, entity-resolve, upsert; flags parse issues; detects >10% odds moves | fixtures, prediction_updated |
| `import <files>` | Human-supplied CSVs / saved HTML pages → same ingest path; idempotent; misses flagged | – |
| `weather` | Open-Meteo forecast → `races.weather` | – |
| `features` | `horse_form_snapshots` for every horse in an upcoming race (strictly pre-race history) | – |
| `train` | RF + LightGBM(+sklearn fallback) + Elo; **time-based** holdout; distance/going slices; refit all history → joblib artifacts | – |
| `predict` | Batch-scores upcoming races; ensemble weighted by recent `model_performance`; leak-free backfill of recent completed races | predictions_ready, followed_horse |
| `explain` | Top-5 positive/negative factors per prediction (SHAP if installed, importance fallback) → `prediction_explanations` | – |
| `evaluate` | Stored predictions vs real results; accuracy/precision/recall/F1/ROC-AUC + slices; incremental periods | result_posted |
| `warm` | Invalidate + repopulate Redis so first reads are fast | – |
| `weekly` | Weekly model digest | weekly_summary |

The `worker` container (`python -m pipeline.scheduler`) runs these on intervals
(4h pipeline cycle, hourly scrape/evaluate, 15-min cache warm, nightly retrain,
Monday digest).

## API surface (cache-first)

`GET /api/races`, `/api/races/{id}`, `/api/horses`, `/api/horses/{id}`,
`/api/jockeys[/{id}]`, `/api/trainers[/{id}]`, `/api/predictions`,
`/api/predictions/history`, `/api/leaderboard`, `/api/notifications` (JWT),
`GET|PUT /api/me/preferences`, `POST /api/simulator/what-if`,
`GET /api/events` (SSE), `POST /api/auth/register|login`,
`/api/admin/flags`, `/api/admin/horses/merge`, `/api/admin/import` (admin JWT),
`GET /api/health`. Interactive docs at `/api/docs`.

## Assumptions & limitations (be aware)

- **The primary source blocks bots.** `mtcjockeyclub.com` answers `robots.txt`
  with 403 (Cloudflare challenge), so the scraper is intentionally inert there
  and real data arrives via the human-in-the-loop import instead (see
  [docs/data-import.md](docs/data-import.md)). Scraper parsers are heuristic:
  anything unrecognised is flagged in `data_quality_flags` rather than crashing
  a run. Always check a source's ToS/robots.txt before automating it.
- **Place target = top-3 finish**; Elo place probability uses a documented
  heuristic `1-(1-p)^1.8`.
- **Race simulator** is an explicit heuristic re-weighting (distance/going fit
  vs the stored ensemble) — not a model re-run. Full walkthrough, worked
  examples, the exact maths, API usage and limitations:
  **[docs/simulator-guide.md](docs/simulator-guide.md)**.
- **FCM push** only with `FCM_ENABLED=true` + credentials; in-app notification
  rows + SSE always work. Web Push not yet implemented. `device_tokens` table
  is ready for the Flutter stage.
- `seed_demo.py` creates **synthetic, clearly-labelled** data only. Demo odds are
  derived from each horse's synthetic true ability, so model metrics on demo
  data look near-perfect — real-world numbers will be far more modest.
- SQLite (tests/dev) uses WAL + `foreign_keys=ON`; production uses Postgres.
- Auth: PBKDF2-SHA256 (390k iters) + JWT (set a strong `JWT_SECRET`).

## Roadmap status

- ✅ MVP: schema, FastAPI + Redis cache-first reads, Docker Compose, JWT,
  RF + rating model, prediction storage + explanations, Next.js dashboard,
  Redis cache warming from day one
- ✅ Advanced: boosting model, ensemble weighting from `model_performance`,
  SHAP explanations, performance slices, what-if simulator, notification core
- ✅ Real-data ingestion: human-in-the-loop CSV / saved-HTML import (CLI + admin
  API), idempotent with data-quality flagging; `evaluate` upserts and re-scores
  late-arriving results
- ⏳ Deferred: Flutter mobile (Prompt E), Web Push, jockey/trainer combo
  features, track-bias detection, media sentiment, NN model; automated scraping
  of MTC pending an official feed or permission

## Quickstart (Docker — recommended)

```bash
cp .env.example .env           # change JWT_SECRET etc.
docker compose up --build -d
docker compose exec api python seed_demo.py       # optional SYNTHETIC demo data
# API:      http://localhost:8000/api/docs
# Web:      http://localhost:3000
# Worker:   docker compose logs -f worker
```

## Quickstart (local dev, no Docker)

Windows one-command helpers (created for you at the repo root):

```powershell
.\seed-demo.ps1      # optional: SYNTHETIC demo data (30 horses, 16 meetings)
.\run-pipeline.ps1   # scrape -> features -> train -> predict -> explain -> evaluate -> warm
.\run-backend.ps1    # API  -> http://127.0.0.1:8000/api/docs
.\run-frontend.ps1   # Web  -> http://localhost:3000
```

Open the API terminal first, then the frontend one (the dashboard reads the
API). Run `.\run-pipeline.ps1 train predict explain evaluate warm` if you only
want specific stages. Stop the servers with `Ctrl+C` in each window (killing
the window instead can leave an orphaned uvicorn child holding port 8000).

These scripts default to SQLite (`backend/dev.db`), the in-process cache
fallback and weather disabled, so no Postgres/Redis/Docker is required. Set
`DATABASE_URL` / `REDIS_URL` before launching to use the real services.

Manual equivalent:

Backend (Python ≥ 3.11):

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate     # or source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -r requirements-ml.txt        # optional: lightgbm + shap
export DATABASE_URL="sqlite:///./dev.db"  # or point at Postgres
python seed_demo.py                       # SYNTHETIC demo data (optional)
python -m pipeline.run --stage all
uvicorn app.main:app --reload
```

Frontend (Node ≥ 20):

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000 (API at localhost:8000)
```

Run tests:

```bash
cd backend && python -m pytest -q
```
