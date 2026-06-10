# Earnings Intelligence OS

A research platform for semiconductor earnings: a Python backend that monitors
SEC EDGAR, parses and chunks filings, extracts evidence-linked draft claims,
and requires human review before claims reach trusted outputs — plus a Next.js
analyst dashboard that drives the review workflow through a FastAPI service.

**Live MVP:**

* Dashboard (Vercel): <https://earnings-intelligence-os.vercel.app>
* API (Render): <https://earnings-intelligence-os-api.onrender.com>

## Repository layout

| Path | Purpose |
|------|---------|
| `src/` | Ingestion, extraction, review, promotion, and brief modules |
| `app/main.py` | FastAPI research API (read + analyst write endpoints) |
| `frontend/` | Next.js analyst dashboard (TypeScript, Tailwind) |
| `test_*.py` | Script-style tests run with `python test_<name>.py` |
| `.github/workflows/run-monitor.yml` | Scheduled filing monitor (every 6 h) |

## Backend setup

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

- `SUPABASE_URL` — your Supabase project URL
- `SUPABASE_SECRET_KEY` — your Supabase service-role key
- `SEC_USER_AGENT` — required by SEC EDGAR, e.g. `Your Name your@email.com`
- `GEMINI_API_KEY` — used only by the manual extraction scripts, never by
  the API
- `GEMINI_MODEL` — optional, defaults to `gemini-2.5-flash`
- `ALLOWED_ORIGINS` — optional, comma-separated browser origins allowed to
  call the API (defaults to `http://localhost:3000`)
- `ADMIN_API_TOKEN` — shared secret for analyst write endpoints. Generate a
  long random private value, e.g.
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`, and keep
  it only in `.env` (and later in your deployment's secret settings)

> **Warning: never commit `.env` to Git.** It is listed in `.gitignore`.

### Run the API

```bash
uvicorn app.main:app --reload
```

Interactive docs at `http://localhost:8000/docs`.

### Authentication

Simple MVP admin-token design: every mutating endpoint requires the
`X-Admin-Token` request header to match the server's `ADMIN_API_TOKEN`.
Missing or wrong header → `401` with `Admin token missing or invalid.`;
if the server itself has no `ADMIN_API_TOKEN` configured, write endpoints
fail closed with a generic `500` (`Server configuration error.`). There are
no user accounts yet.

**Public (GET, no token):** `/health`, `/companies`, `/companies/{ticker}`,
`/overview`, `/filings`, `/filings/{accession_number}`,
`/briefs/latest/{ticker}`, `/review-queue`, `/extraction-ready`,
`/metrics/{ticker}`, `/peers`, `/peers/trends`, `/valuation-snapshots`.

**Protected (GET, token required):** `/admin/validate` — returns
`{"status": "ok"}` for a valid `X-Admin-Token`, 401 otherwise; the
dashboard's Admin Access panel uses it to verify a saved token without
performing any mutation.

**Protected (POST, token required):** `/review-queue/{id}/approve`,
`/review-queue/{id}/edit`, `/review-queue/{id}/reject`, `/claims/promote`,
`/briefs/generate`, `/extraction-ready/{accession_number}/extract`.

In the dashboard, paste the token into the **Admin Access** panel at the
bottom of the sidebar. It is kept in browser session storage only — never
in committed files and never in a `NEXT_PUBLIC_` variable. Saved tokens are
verified against `/admin/validate` and the indicator shows `connected`,
`invalid token`, or `not connected` accordingly.

`POST /claims/promote` accepts an optional JSON body
`{"ticker": "...", "accession_number": "..."}` to scope promotion to one
ticker and/or one filing; with no body it promotes every eligible reviewed
claim (the original global behavior). The dashboard always promotes scoped
to a filing.

`GET /companies` returns the monitored watchlist (ticker, company_name,
cik, business_model) ordered by ticker; the dashboard's filings filter,
sidebar Companies section, and brief tabs are populated from it.

`GET /companies/{ticker}` returns one company's research-pipeline summary:
filing counts, extraction-ready filings, trusted-claim count, latest brief
metadata, and recent filings. `GET /overview` returns cross-company totals
plus a per-company status row for the dashboard's Overview page.

`GET /extraction-ready` lists filings whose earnings-release exhibit has
been ingested and chunked — the queue for the manual AI claim-extraction
step — including each filing's claim-extraction state, pending and trusted
claim counts, and latest brief version.

### Quantitative research terminal (Bundle A)

A set of deterministic, AI-free read endpoints power the peer-comparison and
company-financials views. All figures are computed arithmetically from stored
values; unavailable inputs are returned as `null`, never fabricated.

- `GET /metrics/{ticker}` — historical quarterly operating metrics for one
  company (revenue, margins, EPS, R&D intensity, TTM series, …), with an
  optional `metric_name` filter and a latest-period summary. Valuation-derived
  rows are excluded. 404 for an unknown ticker.
- `GET /peers` — latest-period peer-comparison table across all five
  companies: operating fundamentals plus a valuation snapshot and
  deterministically computed multiples (EV/TTM revenue, EV/TTM operating
  income, price/TTM FCF, FCF yield), with comparability notes and snapshot
  dates.
- `GET /peers/trends?metric_name=&ticker=&limit=` — chart-ready time series
  for one metric across companies (optionally one ticker / last *N* periods).
- `GET /valuation-snapshots` — the manually reviewed point-in-time valuation
  snapshots for all five companies. Every row carries `is_live = false`.

**Valuation data is a manually reviewed point-in-time snapshot, not a live
market feed.** The snapshots are dated (`share_price_date`) and audited; there
is no external market-data provider wired in. Operating fundamentals were
restored from the original public semiconductor research dashboard's audited
dataset (see below) and never overwrite existing reviewed rows.

#### Audited static-data backfill

`run_static_dashboard_backfill.py` (module: `src/static_dashboard_backfill.py`)
restores audited fundamentals and valuation snapshots from a locally
downloaded copy of the original static dashboard. It is idempotent and writes
nothing without `--confirm`:

```bash
# download the public dashboard to a temp path (never committed)
curl -sL https://avyuktk17.github.io/semiconductor-research/ \
    -o /tmp/semiconductor_dashboard.html
python run_static_dashboard_backfill.py            # dry run (safe)
python run_static_dashboard_backfill.py --confirm  # insert missing rows
```

It inserts only missing AVGO `financial_metrics` operating rows (scoped to
metric names already present for the other tickers — valuation-derived and
empty-period rows are excluded) and upserts the five `valuation_snapshots`,
preserving source references, extraction methods, formulas, and manual-review
flags. Reruns insert nothing.

### Manual claim extraction (admin-triggered)

`POST /extraction-ready/{accession_number}/extract` (optional body
`{"max_claims": 1–10}`, default 5) runs grounded Gemini extraction on the
filing's processed earnings exhibit. It is the **only** route that calls
Gemini, and only when an admin triggers it from the dashboard or CLI —
extraction is never scheduled, keeping free-tier quota under analyst
control. Quota and rate-limit failures return `429` (no drafts are ever
deleted by a failed run); other provider failures return a safe `500` and
the error is recorded on the filing.

Filing-level extraction lifecycle (`claim_extraction_status`):

- `not_started` — no extraction run yet
- `pending_review` — drafts stored and awaiting analyst review
- `approved` — every grounded draft reviewed and promotion completed
  (set automatically when a promotion run leaves no grounded pending rows;
  once the Review Queue empties for a filing, the terminal promotion is
  triggered from the Extraction Ready page)
- `failed` — last run errored; the message is stored in
  `claim_extraction_error`

Exhibit selection ranks document quality first — press releases beat
financial-results pages, which beat bare EX-99.1 markers, which beat slide
decks — and file size only breaks ties within a tier.

### Automated exhibit ingestion

A scheduled worker (`run_exhibit_processor.py`, also a GitHub Actions step)
checks up to 3 chunked 8-K filings per run for an earnings-release exhibit
(EX-99.1 style), downloads/parses/uploads it, chunks it, and records the
outcome on the filing row. The exhibit status lifecycle is:

- `not_checked` — default; the worker has not inspected the filing yet
- `processed` — exhibit ingested and chunked; `earnings_release_document_id`
  points at the `filing_documents` row
- `not_found` — the 8-K has no likely earnings-release exhibit (never
  rechecked automatically)
- `failed` — last attempt errored; the error is stored and the filing is
  retried only with `process_pending_exhibits(include_failed=True)`

Gemini claim extraction remains a deliberate manual step (free-quota
control and analyst oversight) — the worker and the deployed API never
call AI.

### CLI utilities

```bash
python run_monitor.py            # check EDGAR for new filings
python run_exhibit_processor.py  # ingest earnings-release exhibits (max 3)
python run_static_dashboard_backfill.py  # restore audited metrics + valuations
                                 # (dry run; writes need --confirm)
python list_filings.py           # list stored filings
python review_claims.py          # interactive claim review
python promote_claims.py         # promote reviewed claims
python cleanup_legacy_claims.py  # list legacy ungrounded pending drafts
                                 # (dry run; deletion needs --confirm)
```

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env.local   # sets NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev
```

Open `http://localhost:3000` (start the backend first). The browser talks
only to the FastAPI service — never directly to Supabase.

### Dashboard routes

| Route | Purpose |
|-------|---------|
| `/` | Cross-company overview: totals, market leaders, peer-fundamentals table, per-company status, latest filings |
| `/peers` | Peer-comparison terminal: ranked bar chart, full fundamentals + valuation table, comparability notes (charts via `recharts`) |
| `/companies/[ticker]` | Company deep dive: KPI cards, revenue/margin/FCF/R&D/TTM trend charts, balance-sheet & valuation snapshot, plus pipeline summary, extraction-ready filings, latest brief |
| `/filings` | Filing feed with ticker/status/limit filters |
| `/filings/[accessionNumber]` | Filing detail, documents, chunk count |
| `/extraction-ready` | Exhibit queue with a lifecycle trail (not_started › pending_review › approved), Extract Claims, terminal Promote reviewed claims, first-brief generation, and View latest brief links |
| `/review-queue` | Approve / edit / reject grounded pending claims; scoped promotion |
| `/briefs/latest/[ticker]` | Latest stored brief with company tabs (from `/companies`), markdown rendering, and version generation |

## Deployment (live)

The MVP is deployed:

* **Backend:** Render web service at
  `https://earnings-intelligence-os-api.onrender.com`, built from the
  `render.yaml` blueprint with start command:

  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
  ```

* **Frontend:** Vercel at `https://earnings-intelligence-os.vercel.app`,
  with `NEXT_PUBLIC_API_BASE_URL` set to the Render API origin.

Backend environment variables (configured in Render): `SUPABASE_URL`,
`SUPABASE_SECRET_KEY`, `SEC_USER_AGENT`, `GEMINI_API_KEY`, `GEMINI_MODEL`
(optional), `ALLOWED_ORIGINS`, and `ADMIN_API_TOKEN`. `ALLOWED_ORIGINS` is
set to `http://localhost:3000,https://earnings-intelligence-os.vercel.app`
so both local development and the deployed dashboard can call the API. The
Supabase server-side key configuration in Render was corrected after the
initial deploy.

A production smoke test confirmed the public GET endpoints and the
admin-token-protected POST endpoints work against the live deployment.
Notes: Gemini extraction remains a manual local step — the deployed API
never calls Gemini — and scheduled SEC ingestion stays in GitHub Actions.

## Tests

```bash
python test_api_health.py          # and the other test_api_*.py scripts
cd frontend && npm run lint && npm run build
```

API tests run against live Supabase data; mutation tests use temporary rows
and clean up after themselves, supplying a temporary admin token through the
environment (never printed). The quantitative endpoints are covered by
`test_api_metrics.py`, `test_api_peers.py`, and
`test_api_valuation_snapshots.py`; the backfill parser/idempotency logic is
covered offline by `test_static_dashboard_backfill.py`.

## Roadmap

- **Bundle A — Quantitative research terminal (complete):** audited metrics
  + valuation backfill, `/metrics`, `/peers`, `/peers/trends`,
  `/valuation-snapshots`, the `/peers` page, charted company deep dives, and a
  fundamentals-driven overview.
- **Bundle B — Evidence Explorer & report engine (next):** a trusted-evidence
  explorer, draft-vs-reviewed report records with versioning, a professional
  earnings-update report template, and PDF export.
