# Data Sourcing Options — how to legitimately feed FormEdge

Probed directly on 2026-09-25 with an honest `User-Agent` (no spoofing, no
challenge-solving, 1–2 requests per host):

| Source | What we got | Automatable? |
|---|---|---|
| `mtcjockeyclub.com` (incl. `/news/news`, `robots.txt`) | **403 + Cloudflare JS challenge** (`server: cloudflare`, cf-ray) | ❌ No — and a denied `robots.txt` means *stay out* (RFC 9309) |
| `supertote.mu` | robots allows (`Allow: /`), pages 200 — but race data is **client-rendered** (one JS bundle) | ⚠️ Only by reverse-engineering their app — not doing that |
| `mauritiusturfclub.mu`, `mtc.intnet.mu`, `turfclub.mu` | DNS failure | ❌ Doesn't exist |
| `lexpress.mu` | robots.txt allows, but pages return **403 Cloudflare "Attention Required!"** | ❌ Blocked in practice |
| **`defimedia.info`** (Le Défi Media Group) | **200 with full server-rendered HTML**; 17 sections incl. `/sports`; no robots rules published at the paths tested; no dedicated racing section | ✅ Fetchable — content is news articles, not structured cards |
| **`gra.govmu.org`** (Gambling Regulatory Authority) | 200, live | ✅ Fetchable — regulator publications/statistics, not per-race data |
| `govmu.org` | 404 robots (no rules) | ✅ but government portal, no racing data |

**Bottom line:** nothing in Mauritius publishes a machine-readable race card +
results + odds feed that an automated client may take. So here are the options,
ranked by value-for-effort.

---

## Option A — Ask MTC / the Jockey Club for an official feed or written permission

**Cost:** one email. **Effort:** minutes. **Ceiling:** highest (structured data,
odds, results, maybe historical form).

What to ask for, specifically:

1. Permission to read the form-guide/results pages programmatically, **or**
2. An official data feed / export (CSV, JSON, XML, FTP, whatever they have), **or**
3. A pointer to whoever holds the data rights (the tote operator, the GRA, or their web vendor).

Draft email:

> **Subject:** Request for permission/access to MTC form guide and results data (personal analytics project)
>
> Dear Sir/Madam,
>
> I am a Mauritius-based developer building a personal (non-commercial, not for
> betting or resale) horse-racing analytics project. I would like to use MTC
> race cards, runners, results and — if available — tote odds.
>
> I noticed that automated requests to `mtcjockeyclub.com` are blocked by your
> bot protection, and the `robots.txt` file returns HTTP 403, so I have **not**
> attempted to scrape it. Instead I would like to ask:
>
> 1. Do you offer an official data feed, API or export (CSV/JSON/FTP)?
> 2. If not, may I have written permission to retrieve the publicly published
>    form-guide and results pages at a low, polite rate (identifying myself
>    clearly, e.g. once per day, one request every few seconds)?
> 3. If data licensing is handled elsewhere, could you point me to the right contact?
>
> I am happy to sign any terms you require and to pay a reasonable fee for
> licensed access. I will not redistribute the data or use it for betting.
>
> Thank you for your time.
> *[Your name, phone, email]*

CC/parallel: the **Gambling Regulatory Authority** (`gra.govmu.org` publishes
contact details) — they regulate the sport's betting and will know who licenses
race data.

---

## Option B — Buy licensed data from a commercial provider

**Cost:** usually a monthly fee plus a contract; minimum commitments are common.
**Effort:** a few emails/RFIs. **Ceiling:** high (official form, ratings, odds,
sometimes in-play).

Vendors to approach (ask specifically about **Mauritius / Champ de Mars**):

- **Sportradar**, **LSports**, **Betradar/Genius Sports** — horse-racing and
  tote-odds feeds for operators; broad international coverage, small markets
  vary.
- **Racing & Sports** (AU), **Timeform / Racing Post B2B** (UK), **Equibase**
  (US) — racing specialists; Mauritius coverage unlikely but worth asking who
  does cover it.
- **Supertote** (the local tote operator) — they hold Mauritius tote data and
  may license or share it for personal use.
- **MTC itself** as a data provider (see Option A).

RFI email skeleton:

> I am building a **personal, non-commercial** analytics project for Mauritius
> (Champ de Mars) racing. Please advise: (1) do you cover Mauritius race cards,
> runners, results and tote odds; (2) what is the delivery format and update
> frequency; (3) what are the licensing terms and costs for a single-developer,
> non-redistributing use; (4) is a historical archive available?

---

## Option C — Local media (`defimedia.info`) as a supplementary source

**Cost:** free. **Effort:** medium (brittle article parsing). **Ceiling:** low as
a primary source, useful for colour.

Fetchable right now (200, real HTML). But the sitemap lists 17 news sections —
`/sports` is the only sports one, and there is **no dedicated racing section or
results feed**, so any harvest is prose summarising meetings plus tips.

Realistic use: a **media-sentiment / tip feature** (already on the roadmap),
storing headline, date and text next to the races. Not a substitute for
runner-level cards, odds or results.

Before automating it: re-check `robots.txt` from your own network, keep it
rate-limited and identify clearly, and read their terms. (Our client fetches
`robots.txt` as itself and refuses hosts that deny it.)

---

## Option D — Human-in-the-loop capture automation ✅ *built and tested*

**Cost:** free. **Effort:** one click per page you view. **Ceiling:** everything
you can see as a human, including the MTC stats pages.

This is the pragmatic middle path: **you** satisfy the bot check by browsing
normally; the automation only handles the *capture* into your own database.

### 1. Inbox watcher (already in the repo)

Drop any `.csv` / `.html` / `.txt` file into `incoming/` and run:

```powershell
.\run-pipeline.ps1 watch          # import what's in the inbox, then refresh everything
```

It scans once, imports through the normal pipeline, then runs
`features → predict → explain → evaluate → warm`. Files that import cleanly move
to `incoming/processed/`; unreadable ones go to `incoming/failed/` and are
flagged. Run it continuously with:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pipeline.watch_inbox --interval 15
```

### 2. Browser capture bookmarklet (`tools/formedge-capture.js`)

Runs inside your browser session on the page you are looking at:

- **Select a stats/race table** → click the bookmark → the selection is sent as
  tab-separated data.
- **Nothing selected** → the whole page HTML is sent to the defensive HTML parsers.

Setup:

1. Allow the site's origin in the API config (`.env`):
   `CORS_ORIGINS=http://localhost:3000,https://www.mtcjockeyclub.com` — then restart the API.
2. Get a token: `curl -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" -d '{"email":"admin@example.com","password":"admin1234"}'`
3. Create a bookmark whose URL is this one-liner (first click prompts for the API
   URL and the token, then caches them):

```
javascript:(function(){var K="formedge_capture",c;try{c=JSON.parse(localStorage.getItem(K)||"{}")}catch(e){c={}}var a=c.api||prompt("FormEdge API URL","http://127.0.0.1:8000");if(!a)return;var t=c.token||prompt("FormEdge admin JWT");if(!t)return;localStorage.setItem(K,JSON.stringify({api:a,token:t}));var s=String(window.getSelection?window.getSelection():"").trim(),b=s||document.documentElement.outerHTML,ct=s?"text/csv":"text/html",fn=(document.title||"page").replace(/[^A-Za-z0-9._-]+/g,"_").slice(0,60)+(s?"_selection.tsv":".html");fetch(a.replace(/\/$/,"")+"/api/admin/import?kind=auto",{method:"POST",headers:{"Content-Type":ct,"X-Filename":fn,Authorization:"Bearer "+t},body:b}).then(function(r){return r.json().then(function(d){return{ok:r.ok,status:r.status,data:d}})}).then(function(res){if(res.status===401||res.status===403)localStorage.removeItem(K);alert("FormEdge import "+(res.ok?"OK":"FAILED (HTTP "+res.status+")")+"\n"+fn+"\n\n"+JSON.stringify(res.data&&res.data.warnings?res.data.warnings:res.data,null,2).slice(0,700))}).catch(function(e){alert("FormEdge import error: "+e+"\nCheck API + CORS_ORIGINS includes "+location.origin)})})();
```

### 3. Copy-paste tables now work too

The importer sniffs the delimiter, so a table copied straight out of a browser
(tab-separated) or a European semicolon CSV parses without conversion — verified
by tests (`test_tab_separated_paste_is_supported`,
`test_semicolon_separated_results_are_supported`).

### Why this is legitimate

- You are a person viewing pages you are entitled to view; nothing circumvents
  the site's protection and no extra requests hit their servers beyond what your
  browser already loaded.
- The data goes to **your** API, stored locally; no redistribution.
- The platform still refuses to crawl hosts that deny `robots.txt`.

---

## Option E — Keep doing it by hand (already works)

`.\run-pipeline.ps1 import .\incoming\racecard.csv` — full schema in
[docs/data-import.md](docs/data-import.md). Good enough if you only care about a
handful of meetings.

---

## Recommendation

1. **Today:** use Option D (already built) so capturing a page costs one click.
2. **Today, in parallel:** send the Option A email (and one to the GRA). If it
   lands, the scraper path comes alive with zero new code.
3. **Optional:** Option C only if you want the media-sentiment feature later.
4. **If budget allows:** Option B RFI for depth (historical form, ratings, odds).

## What I need from you to go further

- **A sample of the MTC stats page** — save it (`Ctrl+S`, HTML only) into
  `incoming/`, or paste 3–5 rows of the table with its header row into chat.
  With that I can write a dedicated parser for those stats, store them (new
  `horse_stats_snapshots` table or extra snapshot columns), expose them on the
  horse profile page and optionally use them as model features — with tests.
- **A yes/no on the emails** — I can draft final versions (EN and FR) into
  `docs/` for you to send.

