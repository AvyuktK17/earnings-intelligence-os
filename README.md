# Earnings Intelligence OS

A research platform for semiconductor earnings: a Python backend that monitors
SEC EDGAR, parses and chunks filings, extracts evidence-linked draft claims,
and requires human review before claims reach trusted outputs — plus a Next.js
analyst dashboard that drives the review workflow through a FastAPI service.

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
- `ALLOWED_ORIGINS` — optional, comma-separated browser origins allowed to
  call the API (defaults to `http://localhost:3000`)

> **Warning: never commit `.env` to Git.** It is listed in `.gitignore`.

### Run the API

```bash
uvicorn app.main:app --reload
```

Interactive docs at `http://localhost:8000/docs`.

Read endpoints: `/health`, `/filings`, `/filings/{accession_number}`,
`/briefs/latest/{ticker}`, `/review-queue`.

Analyst write endpoints: `POST /review-queue/{id}/approve|edit|reject`,
`POST /claims/promote`, `POST /briefs/generate`.

`POST /claims/promote` accepts an optional JSON body
`{"ticker": "...", "accession_number": "..."}` to scope promotion to one
ticker and/or one filing; with no body it promotes every eligible reviewed
claim (the original global behavior). The dashboard always promotes scoped
to a filing.

### CLI utilities

```bash
python run_monitor.py        # check EDGAR for new filings
python list_filings.py       # list stored filings
python review_claims.py      # interactive claim review
python promote_claims.py     # promote reviewed claims
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
| `/` | Overview: summary cards + latest filings |
| `/filings` | Filing feed with ticker/status/limit filters |
| `/filings/[accessionNumber]` | Filing detail, documents, chunk count |
| `/review-queue` | Approve / edit / reject grounded pending claims; scoped promotion |
| `/briefs/latest/[ticker]` | Latest stored brief with markdown rendering and version generation |

## Tests

```bash
python test_api_health.py          # and the other test_api_*.py scripts
cd frontend && npm run lint && npm run build
```

API tests run against live Supabase data; mutation tests use temporary rows
and clean up after themselves.
