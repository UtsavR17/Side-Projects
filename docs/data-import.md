# Data Import Guide — getting real races into FormEdge

**Why this exists.** The master plan named `mtcjockeyclub.com` as the primary
source, but it sits behind Cloudflare bot protection: its `robots.txt` answers
**HTTP 403** with a JavaScript challenge, and RFC 9309 says a denied robots file
means *stay out*. `supertote.mu` does allow crawling (`Allow: /`), but its race
data is rendered client-side — one JS bundle, nothing server-side to parse.
`mauritiusturfclub.com` doesn't resolve.

So FormEdge has two ingestion paths, both feeding the **same** downstream
pipeline (`clean → entity resolution → features → train → predict → explain →
evaluate`):

| Path | Use when | Command |
|---|---|---|
| **Scheduled scraper** | A source explicitly permits automation and serves HTML | `.\run-pipeline.ps1 scrape` |
| **Human-in-the-loop import** | A human viewed a page (or has an export) and supplies the data | `.\run-pipeline.ps1 import <files>` or `POST /api/admin/import` |

The import path is the pragmatic unblock: you collect what you can legitimately
see, and everything after ingestion is automated.

---

## 1. CSV format (recommended — most reliable)

### Fixtures / race cards

One row per **runner**; rows sharing the same `date` + `race_no` become one race.

```csv
date,race_no,venue,race_name,distance_m,race_class,track_condition,horse,jockey,trainer,barrier,weight_kg,odds
2026-05-12,3,Champ de Mars,Winter Plate,1400,Handicap,good,Belle Isle,J. Smith,T. Brown,1,55,3.5
2026-05-12,3,Champ de Mars,Winter Plate,1400,Handicap,good,Cafe Noir,A. Test,T. Practice,2,54.5,5
2026-05-12,4,Champ de Mars,Sprint Cup,1200,Maiden,soft,Quick Step,B. Sample,T. Fiction,3,56,2.8
```

| Column | Required | Notes |
|---|---|---|
| `date` | ✅ | `2026-05-12`, `12/05/2026`, `12 May 2026` all work |
| `race_no` | ✅ | race number within the meeting |
| `horse` | ✅ | matched through name normalisation (`Belle Isle (NZ)` = `belle isle`) |
| `venue` | – | defaults to `Champ de Mars` |
| `race_name`, `race_class`, `track_condition`, `distance_m` | – | taken from the first row of the group; blanks filled from later rows |
| `jockey`, `trainer` | – | auto-created (entity resolution) if new |
| `barrier`, `weight_kg`, `odds` | – | aliases accepted: `draw`/`stall`, `weight`/`wt`, `sp`/`price` |

### Results

```csv
date,race_no,horse,finish_position,margin,time_s,dn_category
12/05/2026,3,Belle Isle,1,1.2L,1:23.4,
12/05/2026,3,cafe-noir,2,0.5L,1:24.1,
12/05/2026,3,Lucky Charm,,,0:00.0,PU
```

- A row needs either `finish_position` **or** `dn_category` (PU / UR / F / …).
- Matching uses **date + race_no + horse name** (normalised, with a fuzzy
  fallback) — far more reliable than matching on race number alone.
- Unknown horses, results for races that don't exist, and results for horses not
  on that card are **never invented**: they land in `data_quality_flags` for
  review (`GET /api/admin/flags`).

---

## 2. Saved HTML pages

In your browser, open a race card / results page and save it
(`Ctrl+S → Webpage, HTML only`), then import the file. The existing defensive
parsers are reused; anything they can't understand becomes a parse warning in
the flags table instead of an error.

```powershell
python -m pipeline.import_files racecard.html --date 2026-05-12
python -m pipeline.import_files results.html --kind results-html
```

Saving a page you can view is normal personal use — just don't wrap a
crawler-denying site in automation, and check each source's terms.

---

## 3. Running an import

### PowerShell helper (repo root)

```powershell
.\run-pipeline.ps1 import .\incoming\racecard-2026-05-12.csv .\incoming\results-2026-05-12.csv
```

That imports the files and then runs `features → predict → explain → evaluate →
warm`, so new cards immediately get snapshots, predictions, explanations and a
warm cache.

### CLI

```powershell
cd backend
.\.venv\Scripts\python.exe -m pipeline.import_files ..\incoming\card.csv ..\incoming\results.csv
.\.venv\Scripts\python.exe -m pipeline.import_files card.html --kind fixtures-html --date 2026-05-12
```

`--kind`: `auto` (default), `fixtures-csv`, `results-csv`, `fixtures-html`,
`results-html`. Auto-detection inspects the content (and the filename for HTML):
a header containing `finish` / `position` / `place` means results.

### HTTP API (admin JWT)

```bash
# 1) get a token
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin1234"}' | jq -r .access_token)

# 2) raw body — the saved page or CSV exactly as-is
curl -X POST "http://127.0.0.1:8000/api/admin/import?kind=auto" \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: text/csv" \
     -H "X-Filename: racecard.csv" --data-binary @racecard.csv

# or a JSON envelope
curl -X POST "http://127.0.0.1:8000/api/admin/import?kind=auto" \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d "{\"content\": \"...\", \"filename\": \"card.html\", \"default_date\": \"2026-05-12\"}"
```

The response reports per-file stats (`races_created`, `races_updated`, `entries`,
`results_written`, `warnings`) and invalidates the cache so the UI shows new data
immediately.

---

## 4. What to run after importing

```powershell
.\run-pipeline.ps1 features train predict explain evaluate warm
```

- **features** rebuilds `horse_form_snapshots` for horses in upcoming races
- **train** refits the models (needs ≥ 5 completed races; more history = better)
- **predict** scores upcoming races *and* backfills recent completed ones (leak-free)
- **evaluate** scores stored predictions against the new results, refreshing the
  accuracy page and model leaderboard

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `no usable rows found in CSV` flag | Header renamed, or rows missing `race_no`/`horse` | Only `date`, `race_no`, `horse` are mandatory — see §1 |
| `unknown_horse` flag | Result names a horse that isn't in the DB | Import fixtures first (that's what creates horses), then results |
| `unmatched_entry` flag | Horse exists but isn't on that race's card | Check race number/date, or that the fixtures import created that card |
| `missing_race` flag | Results imported before the card | Import fixtures first |
| `race(s) without runners parsed` (HTML) | Page structure not recognised | Use CSV — it's the supported path for real data |
| `races_updated` but nothing new | Same `date` + `race_no` + `venue` already existed | Expected: imports are idempotent and update in place |
| Predictions/leaderboard unchanged | Pipeline not re-run | `.\run-pipeline.ps1 predict explain evaluate` |

---

## 6. Design notes

- **Idempotent**: re-importing the same file updates rows, never duplicates them
  (unique keys on race slot, entry, snapshot and prediction).
- **Nothing is invented**: misses are written to `data_quality_flags`
  (`source = manual-import`) for review via `GET /api/admin/flags`; duplicate
  horses can be merged with `POST /api/admin/horses/merge`.
- **One shared parser**: `pipeline/parsing.py` is used by both the scraper and
  the importer, so date/time handling can't drift apart.
- **Same downstream path**: imported races are indistinguishable from scraped
  ones — features, predictions, explanations, evaluation and notifications all
  run unchanged. That is exactly why the blocked scraper isn't fatal.

