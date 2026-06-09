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

**Public (GET, no token):** `/health`, `/companies`, `/filings`,
`/filings/{accession_number}`, `/briefs/latest/{ticker}`, `/review-queue`.

**Protected (POST, token required):** `/review-queue/{id}/approve`,
`/review-queue/{id}/edit`, `/review-queue/{id}/reject`, `/claims/promote`,
`/briefs/generate`.

In the dashboard, paste the token into the **Admin Access** panel at the
bottom of the sidebar. It is kept in browser session storage only — never
in committed files and never in a `NEXT_PUBLIC_` variable.

`POST /claims/promote` accepts an optional JSON body
`{"ticker": "...", "accession_number": "..."}` to scope promotion to one
ticker and/or one filing; with no body it promotes every eligible reviewed
claim (the original global behavior). The dashboard always promotes scoped
to a filing.

`GET /companies` returns the monitored watchlist (ticker, company_name,
cik, business_model) ordered by ticker; the dashboard's filings filter is
populated from it.

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
environment (never printed).
