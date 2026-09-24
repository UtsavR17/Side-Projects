# Race Simulator — User Guide

**Where**: web dashboard → **Simulator** (`http://localhost:3000/simulator`),
or `POST /api/simulator/what-if`
**Code**: `backend/app/routers/simulator.py` (endpoint) ·
`backend/app/services/whatif.py` (arithmetic) ·
`frontend/app/simulator/page.tsx` (UI)

---

## 1. What it does (and what it does not do)

The simulator answers one question: **"If this race were run at a different
distance or on a different going, how would the model's opinion of each horse
change?"**

It takes the **already-stored ensemble win probabilities** for a race and
re-weights them using each horse's own precomputed performance profile
(win rate in the relevant distance band, win rate on the relevant going).

| ✅ It does | ❌ It does not |
|---|---|
| Re-weight existing predictions for a new distance / going | Re-train or re-run the ML models |
| Show each horse's gain/loss and how the ranking changes | Scrape the MTC site or fetch live odds |
| Return instantly (pure database read + arithmetic) | Model weight, barrier, jockey change, scratchings or weather |
| Keep probabilities a valid distribution (always sum to 1) | Predict a definite winner or give betting advice |

**Why it's built this way**: the platform's core rule (master plan §4/§6) is
that a user request never triggers a scrape or a model run. The simulator
honours that — it is a *what-if view over stored intelligence*, not a live
simulation engine. That is also why it is instant.

---

## 2. Prerequisites

A race is simulatable only if the background pipeline has already produced:

1. **Stored ensemble predictions** for that race → run the `predict` stage.
2. **Form snapshots** with distance/going breakdowns for the runners
   (`horse_form_snapshots`) → run the `features` stage.
3. Trained artifacts (so `predict` can produce the ensemble) → run `train`.

Local shortcut:

```powershell
.\seed-demo.ps1                                   # SYNTHETIC demo data
.\run-pipeline.ps1 train predict explain evaluate warm
```

Without step 1 the endpoint answers **400** and the UI shows
*"Simulation failed — does this race have stored predictions yet?"*

---

## 3. Using it in the web UI

1. Open **Simulator** in the top navigation.
2. **Race** — pick from the dropdown. Only *upcoming* races are listed, labelled
   `R<number> · <date> · <distance>m · <going>`.
3. **New distance** — pick a trip (1200–2400 m) or leave **keep** to use the
   race's advertised distance.
4. **New going** — heavy / soft / good / good to firm / firm / fast, or
   **keep**.
5. Press **Simulate**.

The result panel contains:

- A heading stating the change, e.g. `Shift: 1600m → 2000m · good to firm → heavy`
- A table: **New rank**, **Horse**, **Base** (stored probability), **Adjusted**
  (after the change), **Δ** in percentage points
- A footer line naming the method, so the numbers are never presented as more
  than they are

### Step 0 — always sanity-check first

Pick any race, leave both dropdowns on **keep**, press Simulate: every Δ must
read `0.0pp` and the order must be unchanged. That is guaranteed by design
(see §5) and confirms the data behind the page is current.

### How to read the output

- **Δ is in percentage points (pp)**, not relative change: `28.4% → 38.3%` is
  `+9.9pp`.
- **It is a zero-sum redistribution.** Probabilities are renormalised to sum to
  1, so one horse's gain is funded by the field.
- **Rank changes carry more signal than small deltas.** A horse going 4th → 1st
  on a going switch is the interesting finding; a ±1pp wobble is noise.
- **Bigger moves mean stronger specialisation** — a horse that has only ever
  won at 1200 m moves sharply when you stretch the trip.
- **Horses with no qualifying history do not move** (§5, §8).

---

## 4. Verified worked examples

Real outputs from the demo dataset — **Race 99, "Demo Plate R1", 1600 m,
Maiden, going "good to firm"**, 9 runners.

### Example 0 — no change (sanity check)

| Setting | Outcome |
|---|---|
| distance `keep`, going `keep` | all Δ = `0.0000`, identical ranking |

### Example 1 — stretch out: 1600 m → 2000 m, going unchanged

| New rank | Horse | Base | Adjusted | Δ |
|---|---|---|---|---|
| 1 | Placeholder Charger 22 | 28.41% | 38.32% | **+9.91pp** |
| 2 | Synth Lagoon 2 | 23.75% | 30.85% | **+7.10pp** |
| 3 | Unit Echo 16 | 12.95% | 10.52% | −2.43pp |
| 4 | Placeholder Falcon 14 | 17.53% | 9.70% | **−7.83pp** |
| 5 | Trial Dancer 3 | 3.15% | 2.56% | −0.59pp |

*Reading*: Charger and Lagoon have their best records over 1800–2000 m, so a
longer trip boosts them; Falcon gives back 7.8pp and slips down the order.
Because the going is unchanged, the going component cancels out exactly — only
distance is doing work here.

### Example 2 — going switch: good to firm → heavy (distance unchanged)

| New rank | Horse | Base | Adjusted | Δ |
|---|---|---|---|---|
| 1 | Placeholder Falcon 14 | 17.53% | 24.56% | **+7.03pp (up from 4th)** |
| 2 | Placeholder Charger 22 | 28.41% | 24.35% | **−4.06pp (down from 1st)** |
| 3 | Synth Lagoon 2 | 23.75% | 19.69% | −4.06pp |
| 4 | Unit Echo 16 | 12.95% | 10.95% | −2.00pp |
| 5 | Sample Kestrel 4 | 6.73% | 9.32% | +2.59pp |

*Reading*: the classic soft-ground flip. Charger's 3 wins from 12 good-to-firm
runs stop counting for him, and none of the runners has a "heavy" record yet —
so each falls back to the nearest going it *does* have (`soft`). Falcon has 2
wins from 11 on soft (18.2%) versus 1 from 14 on good to firm (7.1%), so he
inherits favouritism.

### Example 3 — both levers: 1600 m → 1200 m, going → fast

| New rank | Horse | Base | Adjusted | Δ |
|---|---|---|---|---|
| 1 | Placeholder Falcon 14 | 17.53% | 30.09% | **+12.56pp (up from 4th)** |
| 2 | Placeholder Charger 22 | 28.41% | 26.47% | −1.94pp |
| 3 | Unit Echo 16 | 12.95% | 15.44% | +2.49pp |
| 4 | Synth Lagoon 2 | 23.75% | 15.34% | **−8.41pp (down from 2nd)** |
| 5 | Trial Dancer 3 | 3.15% | 3.14% | −0.01pp |

*Reading*: sprinter-type profiles gain, the two 2000 m horses give ground, and
the ranking is reshuffled — this is the scenario you would use to judge whether
a race is "mis-described" for a particular horse.

### Error handling (verified)

| Input | Response |
|---|---|
| unknown `race_id` | **404** `{"detail":"Race not found"}` |
| `distance_m = 50` | **422** (valid range 200–6000 m) |
| race without stored predictions | **400** `{"detail":"No stored ensemble predictions for this race yet"}` |

---

## 5. How the numbers are made

Each runner is adjusted in **log-odds (logit) space**, which keeps the output a
valid probability:

```
logit  = ln( p / (1 - p) )                    # p = stored ensemble win prob
dlogit = 1.35 * (distance_fit_new - distance_fit_old)
       + 0.90 * (going_fit_new    - going_fit_old)
p_raw  = 1 / (1 + e^(-(logit + dlogit)))       # sigmoid
p_adj  = p_raw / sum(p_raw over the field)     # renormalised to sum to 1
```

`1.35 = 0.9 (distance weight) × 1.5 (scale)` and `0.90 = 0.6 (going weight) × 1.5`.

A **fit** answers "how much better or worse is this horse in *this* context
compared with its own average context", using its precomputed snapshot:

```
gap = win_rate(in the relevant distance / going bucket)
      - average win_rate across the horse's buckets (buckets with >= 2 runs)
fit = clamp(gap * 3, -1, +1)
```

Context selection rules:

| Lever | Rule |
|---|---|
| Distance | Nearest **200 m bucket** the horse has actually run in (`1400-1600`, `1600-1800`, …); a bucket containing the distance wins immediately |
| Going | **Exact going match first** (case-insensitive); otherwise nearest going on the scale `heavy < soft < good < good to firm < firm < fast`, ties resolving to the softer side |

### Real arithmetic — Example 1 broken down

Placeholder Charger 22, base probability `28.411%`:

```
base logit = ln(0.28411 / 0.71589)                        = -0.9242

Distance buckets (runs, wins, win rate):
  1400-1600: 7 runs, 0 wins -> 0.0%      <- OLD context (race is 1600 m)
  1600-1800: 6 runs, 0 wins -> 0.0%
  1200-1400: 7 runs, 1 win  -> 14.29%
  1800-2000: 7 runs, 2 wins -> 28.57%
  2000-2200: 5 runs, 1 win  -> 20.0%     <- NEW context (2000 m)
horse's average across those buckets                      = 12.57%

distance_fit_old = ( 0.0% - 12.57%) * 3 = -0.377
distance_fit_new = (20.0% - 12.57%) * 3 = +0.223

Going (unchanged, exact match "good to firm" found):
  good to firm: 12 runs, 3 wins -> 25.0%  ; horse's going average = 9.38%
  going_fit_old = going_fit_new = (25.0% - 9.38%) * 3 = +0.469  -> cancels

dlogit = 1.35 * (0.223 - (-0.377)) + 0.90 * 0   = +0.8100
p_raw  = sigmoid(-0.9242 + 0.8100)              = 0.4715
p_adj  = renormalised across the 9 runners      = 0.3832   ✅ matches the UI
```

Switching going to **heavy** (he has no "heavy" bucket, so nearest going
`soft` = 12.5% is used, fit `+0.094`):

```
dlogit = 0.90 * (0.094 - 0.469) = -0.3375  ->  p_raw = 0.2207  ->  p_adj = 0.2435  ✅
```

### Why renormalisation matters

The raw sigmoid values do not sum to 1 across a field. Dividing by the field
total is what makes them "chances in *this* race" — and it is why the Adjusted
column always sums to ~100% (rounding aside), and why gains must be funded by
other runners losing ground.

---

## 6. Using it from the API

```bash
curl -X POST http://127.0.0.1:8000/api/simulator/what-if \
  -H "Content-Type: application/json" \
  -d '{"race_id": 99, "distance_m": 2000, "track_condition": "heavy"}'
```

```powershell
$body = @{ race_id = 99; distance_m = 2000; track_condition = 'heavy' } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/simulator/what-if `
  -Method Post -ContentType 'application/json' -Body $body
```

Request fields:

| Field | Required | Notes |
|---|---|---|
| `race_id` | yes | Any race with stored ensemble predictions (upcoming, or completed/backfilled) |
| `distance_m` | no | 200–6000; omit to keep the race's distance |
| `track_condition` | no | Free text, matched case-insensitively; omit to keep the race's going |

Response shape:

```json
{
  "race_id": 99,
  "context": {
    "distance_m":      { "from": 1600, "to": 2000 },
    "track_condition": { "from": "good to firm", "to": "heavy" }
  },
  "picks": [
    { "horse_id": 14, "horse_name": "Placeholder Falcon 14",
      "base_win_prob": 0.1753, "adjusted_win_prob": 0.2456,
      "delta": 0.0703, "rank": 1 }
  ],
  "method": "heuristic-reweight (stored ensemble x distance/condition fit)"
}
```

`picks` is sorted by `adjusted_win_prob` descending; `rank` is 1-based.

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Error *"Simulation failed — does this race have stored predictions yet?"* (400) | No `ensemble` predictions for that race | `.\run-pipeline.ps1 predict` (run `train` first if artifacts are missing) |
| Race dropdown is empty | No upcoming races in the DB | `.\seed-demo.ps1` or `.\run-pipeline.ps1 scrape weather` |
| Every Δ is `0.0pp` | Both dropdowns left on **keep** (expected — that is the sanity check) | Choose a different distance or going |
| A specific horse never moves | No form snapshot, or no runs in the alternative distance band / going | Run the `features` stage; check the horse's profile page for its buckets |
| Deltas look stale next to the odds on the race page | The simulator re-weights the probabilities **stored** by the last `predict` run | `.\run-pipeline.ps1 predict`, then reload the page |
| `404 Race not found` | Stale race id (old bookmark) | Pick the race again from the dropdown |
| `422` on `distance_m` | Value outside 200–6000 | Use 1200–2400 m |

---

## 8. Limitations (read before trusting a number)

- **Win rate only** — place rate and average finish are not used, so a horse
  that places constantly but rarely wins is treated as roughly neutral.
- **Thin records** — buckets with fewer than 2 runs are excluded from the
  horse's *average*, but a bucket with one lucky win still counts for the
  *specific context* (and can clamp the fit to +1). Treat 1-run buckets as noise.
- **Going index is substring based** — on the *fallback* path the numeric scale
  collapses "good" and "good to firm". Exact matches are always preferred, so
  this only affects horses lacking the exact going record.
- **Boundary effects** — distance bands are 200 m wide, so a 1600 m horse
  evaluated at 1500 m can flip between `1400-1600` and `1600-1800`.
- **Two levers only** — weight carried, barrier, jockey/trainer change,
  scratchings and weather are not re-modelled (they are already baked into the
  stored ensemble probabilities).
- **Frozen baseline** — the models are never re-run, so it cannot know about
  anything that arrived after the last `predict` stage.
- **Scratched runners are excluded** — you cannot simulate "what if X is
  withdrawn".
- **Not betting advice** — it is a sensitivity view of one model's stored
  opinion, on data that may include synthetic demo values.

---

## 9. Extending it

| File | Role | What to tune |
|---|---|---|
| `backend/app/services/whatif.py` | Pure maths (fits + adjustment) | `_DISTANCE_WEIGHT` (0.9), `_CONDITION_WEIGHT` (0.6), the `1.5` scale, the `*3` in `fit_score`, `_CONDITION_ORDER` |
| `backend/app/routers/simulator.py` | Endpoint, validation, renormalisation, ranking | distance bounds (200–6000) |
| `frontend/app/simulator/page.tsx` | UI + dropdown options | `DISTANCES`, `CONDITIONS` |
| `backend/tests/test_simulator_engine.py` | Engine unit tests (incl. the hand-calculated case) | — |

Natural next steps:

1. **Composite fits** — combine win rate, place rate and average finish into one
   fit score (fixes the "places but never wins" blind spot).
2. **More levers** — add weight carried and barrier as extra logit terms; both
   are already stored on `race_entries`.
3. **Full re-score mode** — load the joblib artifacts, rebuild feature rows with
   the modified distance/going and re-predict. Still no scraping and no
   training; cache the loaded models so requests stay fast.
4. **Going × distance interaction** — a horse that stays 2000 m *only on soft
   ground* currently gets averaged across two independent axes.

Engine tests any time:

```powershell
cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_simulator_engine.py -q
```






to run the app 
- .\run-backend.ps1
- .\run-frontend.ps1