# Earnings Intelligence OS — Project Status

## Project goal

Build an Earnings Intelligence OS for semiconductor companies:

* monitor SEC EDGAR automatically;
* detect new filings;
* download and parse filings;
* store documents permanently in Supabase Storage;
* split documents into AI-ready chunks;
* extract evidence-linked draft claims;
* require human review before claims enter trusted research outputs;
* publish trusted claims as versioned earnings briefs;
* expose everything through a research API;
* drive the analyst workflow from a web dashboard.

## Companies monitored

* QCOM
* AMD
* NVDA
* INTC
* AVGO

## Supabase tables

* `companies` — ticker → company_name watchlist
* `financial_metrics`
* `filings` — one row per detected filing; lifecycle status, Storage paths, timestamps, processing_error; exhibit columns: `exhibit_processing_status` (`not_checked` / `processed` / `not_found` / `failed`, default `not_checked`), `exhibit_checked_at`, `exhibit_processing_error`, `earnings_release_document_id` → `filing_documents(id)`
* `filing_documents` — exhibit documents (e.g. EX-99.1) per filing; unique on `(accession_number, filename)`
* `filing_chunks` — AI-ready chunks; unique on `(accession_number, document_key, chunk_index)`; primary chunks use `document_key = "primary"`, exhibit chunks use `document_key = "exhibit:{filename}"`
* `proposed_claims` — AI-drafted claims awaiting review; `review_status` is `pending` / `approved` / `edited` / `rejected`; grounded rows have `source_chunk_id`
* `qualitative_claims` — trusted human-reviewed claims; promoted rows carry `proposed_claim_id`, `source_chunk_id`, `document_key`, `promoted_at` (note: this table has **no `id` column** — promoted rows are keyed by `proposed_claim_id`)
* `earnings_briefs` — versioned brief rows; unique versions per accession; stores `markdown_content`, `storage_path`, claim counts, `generated_at`
* `pipeline_runs` — run bookkeeping

## Supabase Storage (private bucket: `filing-documents`)

* `html/{ticker}/{accession}/...` — raw primary HTML
* `parsed/{ticker}/{accession}/...` — parsed primary text
* `html/{ticker}/{accession}/exhibits/{filename}` — raw exhibit HTML
* `parsed/{ticker}/{accession}/exhibits/{filename}.txt` — parsed exhibit text
* `briefs/{ticker}/{accession}/v{n}.md` — versioned earnings briefs

## GitHub Actions (`.github/workflows/run-monitor.yml`)

* manual `workflow_dispatch` + scheduled cron `17 */6 * * *` (every 6 hours)
* concurrency group `sec-filing-monitor`
* steps:
  1. Run filing monitor (`run_monitor.py`)
  2. Process detected filings (`run_processor.py`)
  3. Process earnings-release exhibits (`run_exhibit_processor.py`, max 3
     filings per run)
  4. Backfill missing Storage paths (`run_backfill.py`)
  5. Backfill missing chunks (`run_chunk_backfill.py`)
  6. List detected filings (`list_filings.py`)
* AI extraction, review, promotion, and brief generation are **not** in the
  workflow — they remain manual by design.

## Ingestion pipeline (complete)

Filing lifecycle: `detected → downloaded → parsed → chunked`.
A filing only reaches `chunked` after HTML download, text parsing, HTML+text
Storage upload, Storage-path persistence, and chunk creation. Failures are
recorded in `processing_error`.

Exhibit support (`src/filing_exhibits.py`, `src/process_filing_exhibit.py`):
discovers the SEC filing index, selects the likely earnings-release exhibit
(EX-99.1), downloads/parses/uploads it, and records it in `filing_documents`
(`process_earnings_release_exhibit` returns the row's
`filing_document_id`). The filename matcher also recognizes
press-release names ending in `pr.htm` (NVIDIA's convention).
Multi-document chunking (`src/filing_chunker.py`) chunks both primary
documents and exhibits idempotently.

## Automated exhibit ingestion (complete)

`src/exhibit_status.py` + `src/process_pending_exhibits.py` +
`run_exhibit_processor.py` (GitHub Actions step 3, batch limit 3):

* selects 8-K filings with `processing_status = "chunked"` and
  `exhibit_processing_status = "not_checked"` (plus `"failed"` only with
  `include_failed=True`), newest filing_date first
* per filing: discover exhibit → download/parse/upload → chunk → mark
  `processed` with `earnings_release_document_id`; no exhibit → mark
  `not_found`; any error → mark `failed` with the error message and continue
  the batch
* status lifecycle: `not_checked` → `processed` / `not_found` / `failed`;
  `processed` and `not_found` rows are never re-inspected
* **chunk-preservation rule:** if a filing already has an earnings-release
  document with stored chunks (e.g. the manually ingested AVGO 8-K), the
  worker reuses the existing document id and never re-chunks — grounded
  claims reference chunk ids with a RESTRICT foreign key, so existing
  exhibit chunks must never be deleted
* never calls Gemini; extraction stays manual (free-quota control and
  analyst oversight)
* live results: AVGO `0001730168-26-000051` (17 chunks), NVDA
  `0001045810-26-000051` `q1fy27pr.htm` (13 chunks), AMD
  `0000002488-26-000072` `amdq126earningsslidesfin.htm` (15 chunks) are
  `processed`; non-earnings 8-Ks are `not_found`

## Gemini claim extraction (complete, manual)

* `src/llm_client.py` + `src/claim_extractor.py`; run via `run_claim_extraction.py`
* extraction is grounded: each claim must include a `supporting_excerpt` that
  is a literal substring of a chunk (after whitespace normalization) plus the
  matching `source_chunk_index` / `source_chunk_id`
* claims insert into `proposed_claims` with `review_status = "pending"`;
  rerun-safe via a DELETE scoped to `(accession_number, document_key, pending)`
* Gemini API key in `.env` and GitHub Secrets; never called from the API or tests

## Human review workflow (complete)

* `src/claim_review.py`: `approve_claim`, `approve_claim_with_edits`
  (preserves original `claim_text`, stores `edited_claim_text`), `reject_claim`
* approval/editing require a grounded row (`source_chunk_id` non-null);
  rejection is allowed on any row, including ungrounded legacy rows
* interactive CLI: `review_claims.py`; read-only queue: `list_proposed_claims.py`

## Trusted promotion (complete)

* `src/claim_promotion.py`: `promote_reviewed_claims()` promotes `approved` /
  `edited` grounded claims into `qualitative_claims`, using the reviewer's
  edited wording when present; already-promoted claims are skipped by
  `proposed_claim_id`, so reruns never duplicate
* CLI: `promote_claims.py`
* 5 trusted AVGO claims are live (proposed_claim_ids 30–34)

## Versioned earnings briefs (complete)

* `src/earnings_brief.py`: builds a markdown brief from trusted grounded
  claims only (pending/rejected drafts never appear); no AI calls
* `src/brief_storage.py`: `generate_and_store_earnings_brief()` assigns the
  next version number, writes `output/briefs/` locally (gitignored), uploads
  to Storage, and inserts an `earnings_briefs` row; prior versions are never
  overwritten
* CLIs: `generate_earnings_brief.py`, `store_earnings_brief.py`
* AVGO 8-K `0001730168-26-000051` brief v1 is persisted (5 trusted claims)

## FastAPI research API (complete)

`app/main.py` — `FastAPI(title="Earnings Intelligence OS API")`; run locally
with `uvicorn app.main:app --reload`. Uses
`src.database.get_supabase_client()` via a single `lru_cache`d client.
Deployed on Render at `https://earnings-intelligence-os-api.onrender.com`.

Authentication (MVP admin token): every write endpoint requires the
`X-Admin-Token` header to match the `ADMIN_API_TOKEN` env var, compared
with `secrets.compare_digest`. Missing/wrong header → 401
("Admin token missing or invalid."); server token unconfigured → generic
500 ("Server configuration error.") that never names the variable. Read
endpoints are public. No user accounts yet.

Read endpoints (public):

* `GET /health` — liveness
* `GET /companies` — watchlist (ticker, company_name, cik, business_model)
  ordered by ticker; feeds the dashboard's filings filter
* `GET /filings?ticker=&status=&limit=` — filing feed, newest first; ticker
  uppercased; `limit` validated with `Query(ge=1, le=100)` (422 outside range)
* `GET /filings/{accession_number}` — filing + `filing_documents` + chunk
  count; 404 if unknown
* `GET /briefs/latest/{ticker}` — latest stored brief; 404 if none
* `GET /review-queue` — grounded pending claims only; ungrounded legacy rows
  (`source_chunk_id` null) are never exposed
* `GET /extraction-ready` — filings with a processed, chunked
  earnings-release exhibit, newest first; each row carries the exhibit
  filename, `document_key`, `chunk_count`, and
  `ready_for_extraction` — the queue for manual grounded-claim extraction

Write endpoints (analyst workflow; all require `X-Admin-Token`):

* `POST /review-queue/{claim_id}/approve` — optional `{"reviewer_notes"}`;
  404 unknown claim, 400 ungrounded
* `POST /review-queue/{claim_id}/edit` — requires `{"edited_claim_text"}`
  (422 if empty/missing), optional notes; 404 unknown, 400 ungrounded
* `POST /review-queue/{claim_id}/reject` — optional notes; works on
  ungrounded legacy rows; 404 unknown
* `POST /claims/promote` — runs `promote_reviewed_claims()`; idempotent;
  accepts an optional body `{"ticker", "accession_number"}` to scope
  promotion to one ticker and/or one filing (no body = global mode; the
  dashboard only ever calls the scoped form)
* `POST /briefs/generate` — requires `{"ticker", "accession_number"}`;
  ticker uppercased; 404 unknown filing, 400 when no trusted claims exist

CORS: `CORSMiddleware` allows browser calls from the origins in the optional
`ALLOWED_ORIGINS` env var (comma-separated; defaults to
`http://localhost:3000`), with credentials and all methods/headers. Verified
with a preflight test (`test_api_cors.py`).

Error mapping: `ValueError` messages starting with "No proposed claim found" /
"No filing found" → 404; other workflow `ValueError`s → 400; Pydantic
validation → 422; unexpected errors → bare 500 with no secrets or stack trace.

Database client hardening: `src/database.py` raises `RuntimeError` (instead
of the old `sys.exit(1)`) when `SUPABASE_URL` / `SUPABASE_SECRET_KEY` are
missing, so a misconfigured API process returns controlled 500s instead of
dying; the message names the variables but never their values.

## Frontend analyst dashboard (complete, deployed)

`frontend/` — Next.js (App Router, stable 16.2.7) + TypeScript + Tailwind v4,
scaffolded with create-next-app (`src/` directory, npm, ESLint). Only extra
runtime dependency: `react-markdown`. Dark, data-dense research-terminal
styling with a left sidebar (Overview / Filings / Review Queue / Latest
Brief). Deployed on Vercel at
`https://earnings-intelligence-os.vercel.app` with
`NEXT_PUBLIC_API_BASE_URL` pointing at the Render API.

* setup: `cd frontend && npm install && cp .env.example .env.local`
* run: `npm run dev` (backend must be running on
  `NEXT_PUBLIC_API_BASE_URL`, default `http://localhost:8000`)
* the browser talks only to the FastAPI service, never to Supabase
* shared typed client in `src/lib/api.ts` with explicit loading and error
  states on every page
* **Admin Access panel** at the bottom of the sidebar: token input with
  Save/Clear and a connected indicator. The token lives in browser session
  storage only (never committed, never in a `NEXT_PUBLIC_` variable) and is
  attached as `X-Admin-Token` to protected POSTs only; a 401 surfaces as
  "Admin token missing or invalid."

Routes:

* `/` — overview: stat cards (recent filings, extraction-ready filings,
  pending grounded claims, latest AVGO brief version) + latest-filings
  table; a missing brief renders as "—", not an error
* `/filings` — feed with ticker/status/limit filters and status badges;
  the ticker list loads dynamically from `GET /companies` (with a static
  fallback if the endpoint fails)
* `/filings/[accessionNumber]` — full filing metadata, timestamps,
  processing error, document list with Storage flags, chunk count
* `/extraction-ready` — ingested + chunked earnings-release exhibits with
  exhibit filename, document key, chunk count, and status badge; accession
  numbers link to the filing detail page; clean empty state
* `/review-queue` — grounded pending claims grouped by filing; approve /
  edit-and-approve / reject with optional reviewer notes; per-filing
  "Promote reviewed claims for this filing" button (scoped promotion only —
  the frontend never calls global promotion); clean empty state
* `/briefs/latest/[ticker]` — brief metadata cards + rendered markdown;
  "Generate new brief version" button refreshes to the new version

## Deployment (complete — MVP live)

* **Backend (Render):** `https://earnings-intelligence-os-api.onrender.com`
  — deployed from the `render.yaml` blueprint (Python web service, health
  check on `/health`, start command
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`)
* **Frontend (Vercel):** `https://earnings-intelligence-os.vercel.app`
* backend env vars configured in Render: `SUPABASE_URL`,
  `SUPABASE_SECRET_KEY`, `SEC_USER_AGENT`, `GEMINI_API_KEY`, `GEMINI_MODEL`
  (optional, default `gemini-2.5-flash`), `ALLOWED_ORIGINS`, `ADMIN_API_TOKEN`
* production CORS: Render `ALLOWED_ORIGINS` is set to
  `http://localhost:3000,https://earnings-intelligence-os.vercel.app`
* the Supabase server-side key configuration in Render was initially wrong
  and has been corrected; the API now reaches Supabase in production
* production smoke test passed: public GET endpoints (health, companies,
  filings, briefs, review queue) and admin-token-protected POST endpoints
  are working against the live deployment
* frontend env var: `NEXT_PUBLIC_API_BASE_URL` set in Vercel to the Render
  API origin (production-safe `frontend/.env.example` documents it)
* the deployed API never calls Gemini (extraction stays manual); scheduled
  SEC ingestion stays in GitHub Actions

## Tests

Script-style tests run with `python test_*.py` against live Supabase data.
API tests: `test_api_health.py`, `test_api_filings.py`, `test_api_briefs.py`,
`test_api_review_queue.py`, `test_api_companies.py`, `test_api_cors.py`,
`test_api_auth.py` (public reads, 401s, correct-token action, fail-closed
500), `test_api_review_actions.py`,
`test_api_promotion.py` (global + scoped modes), `test_api_brief_generation.py`,
`test_api_extraction_ready.py`, and `test_process_pending_exhibits.py`
(worker processed / not-found / failed paths, idempotency, and proof that
grounded chunks and trusted claims survive reruns).
Write-endpoint tests supply a temporary admin token via the environment
(never printed),
insert clearly marked temporary rows and delete them in `finally` blocks;
real trusted AVGO claims and the persisted v1 brief are never modified.
Frontend checks: `cd frontend && npm run lint && npm run build`.
Known cosmetic warning when importing TestClient:
`StarletteDeprecationWarning: Using httpx with starlette.testclient is
deprecated; install httpx2 instead.` — harmless, left as-is.

## Known issues

* Two ungrounded legacy pending AVGO primary-document claims remain in
  `proposed_claims` (`source_chunk_id` null). They are excluded from the
  review queue, approval, promotion, and briefs by design; they can only be
  rejected. Resolve by re-extracting the primary document with the current
  grounded extractor or rejecting them.

## Next milestone

1. Add protected dashboard-triggered manual claim extraction for
   extraction-ready filings.
2. Generate reviewed briefs for AMD, NVDA, INTC, and QCOM.
3. Add company pages and polish the cross-company overview.

## Safety rules

* Never expose `.env`, Supabase credentials, or API keys
* Do not commit local downloaded/parsed documents or generated briefs
* Keep the Supabase Storage bucket private
* Do not write AI output directly into trusted `qualitative_claims` —
  promotion only happens after human review
* Require exact grounded excerpts after whitespace normalization
* Keep AI extraction manual until quality is reviewed
* Write endpoints require the admin token; keep `ADMIN_API_TOKEN` private
  and never commit or print it
* Production secrets (Supabase keys, admin token) live only in Render's and
  Vercel's environment settings — never in the repository; keep
  `ALLOWED_ORIGINS` restricted to known frontend origins
