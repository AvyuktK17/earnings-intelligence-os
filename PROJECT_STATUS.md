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

Ten tables are in use:

* `companies` — ticker → company_name watchlist
* `financial_metrics` — audited quarterly fundamentals, all five tickers
  (AMD, AVGO, INTC, NVDA, QCOM) × 258 rows = 1,290 rows; columns `company,
  ticker, fiscal_year, fiscal_quarter, metric_name, value, unit,
  extraction_method, source_reference, derived_from, requires_manual_review,
  formula`. 252 quarterly operating rows per ticker (21 metrics × 12
  quarters, FY2023–FY2026) plus 6 embedded valuation-derived rows
  (empty-period) that the quantitative API filters out — valuation lives in
  `valuation_snapshots`. The audited dataset (including AVGO) was restored
  from the original public static dashboard; see "Audited static-data
  backfill" below
* `valuation_snapshots` — manually reviewed point-in-time valuation
  snapshots for all five tickers (`ticker, share_price_date, share_price,
  shares_outstanding, shares_outstanding_source_date, market_cap, cash,
  total_debt, enterprise_value, debt_measure, source, manually_reviewed,
  notes`; unique on `(ticker, share_price_date)`). Dated/audited, **not** a
  live market feed; the API surfaces every row with `is_live = false`
* `filings` — one row per detected filing; lifecycle status, Storage paths, timestamps, processing_error; exhibit columns: `exhibit_processing_status` (`not_checked` / `processed` / `not_found` / `failed`, default `not_checked`), `exhibit_checked_at`, `exhibit_processing_error`, `earnings_release_document_id` → `filing_documents(id)`; extraction columns: `claim_extraction_status` (`not_started` / `pending_review` / `approved` / `failed`, default `not_started`), `claim_extracted_at`, `claim_extraction_error`
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
`filing_document_id`). The filename matcher recognizes press-release names
ending in `pr.htm` (NVIDIA's convention) and `99.1` names without a
separator like `q12026991.htm` (AMD's convention). Candidates are ranked
press release / earnings release (tier 1) > financial results (2) >
EX-99.1 marker (3) > slide deck / presentation (4) > other (5), with file
size only breaking ties within a tier — so a small press release always
beats a large slide deck.
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
* **chunk-preservation rule:** discovery and ranking always run first; an
  existing document is reused only when its filename exactly matches the
  currently selected best-ranked exhibit (so AVGO's EX-99.1 keeps its
  chunk ids — grounded claims reference them with a RESTRICT foreign key —
  while a filing can still upgrade from a slide deck to a press release);
  on upgrade the filing's `earnings_release_document_id` moves to the new
  document and the previously ingested document and its chunks are kept as
  secondary evidence, never deleted
* never calls Gemini; extraction stays manual (free-quota control and
  analyst oversight)
* live results: AVGO `0001730168-26-000051` (17 chunks), NVDA
  `0001045810-26-000051` `q1fy27pr.htm` (13 chunks), AMD
  `0000002488-26-000072` `q12026991.htm` (21 chunks; upgraded from the
  slide deck, which remains stored as a secondary document), and QCOM
  `0000804328-26-000060` are `processed`; non-earnings 8-Ks are
  `not_found`

## Gemini claim extraction (complete, manual)

* `src/llm_client.py` + `src/claim_extractor.py`; run via `run_claim_extraction.py`
* extraction is grounded: each claim must include a `supporting_excerpt` that
  is a literal substring of a chunk (after whitespace normalization) plus the
  matching `source_chunk_index` / `source_chunk_id`
* claims insert into `proposed_claims` with `review_status = "pending"`;
  rerun-safe via a DELETE scoped to `(accession_number, document_key, pending)`
* Gemini API key in `.env` and GitHub Secrets; never called from the API or tests

## Manual dashboard-triggered claim extraction (complete)

`src/claim_extraction_status.py` + `src/ready_filing_extraction.py`:

* `extract_claims_for_ready_filing(accession_number, max_claims=5)` requires
  an extraction-ready filing (processed exhibit + document id), builds the
  exhibit `document_key`, and reuses the existing grounded extractor
  (`extract_and_store_claims`), which replaces pending drafts only after
  valid new claims exist — failed runs never delete drafts
* filing lifecycle: `not_started` → `pending_review` (successful run) /
  `failed` (error stored, truncated to 500 chars) → `approved` (set by
  promotion when no grounded pending rows remain for the filing)
* quota / rate-limit / availability errors raise
  `ClaimExtractionQuotaError`; other provider errors raise a caller-safe
  `ClaimExtractionError` (raw detail only on the filing row, never to
  callers)
* Gemini stays manual and admin-triggered (free-quota control + analyst
  oversight); nothing is scheduled and GitHub Actions never extracts

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
  `proposed_claim_id`, so reruns never duplicate; after promotion, any
  affected filing with no grounded pending rows left is marked
  `claim_extraction_status = "approved"` (returned as `approved_filings`)
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
  ordered by ticker; feeds the dashboard's filings filter, sidebar
  Companies section, and brief tabs
* `GET /companies/{ticker}` — one company's research-pipeline summary:
  filing + chunked counts, extraction-ready filings (compact rows),
  trusted promoted claim count, latest brief metadata (no markdown body),
  recent filings (10); ticker uppercased; 404 for unknown companies
* `GET /overview` — cross-company dashboard payload: companies/filings/
  extraction-ready/pending-grounded/trusted/brief totals plus one status
  row per company (extraction-ready count, trusted count, latest brief
  version, latest filing date)
* `GET /admin/validate` — the only token-protected GET; returns
  `{"status": "ok"}` for a valid `X-Admin-Token`, 401 otherwise, safe 500
  when the server token is unconfigured; used by the Admin Access panel
  to verify saved tokens without mutations
* `GET /filings?ticker=&status=&limit=` — filing feed, newest first; ticker
  uppercased; `limit` validated with `Query(ge=1, le=100)` (422 outside range)
* `GET /filings/{accession_number}` — filing + `filing_documents` + chunk
  count; 404 if unknown
* `GET /briefs/latest/{ticker}` — latest stored brief; 404 if none
* `GET /review-queue` — grounded pending claims only; ungrounded legacy rows
  (`source_chunk_id` null) are never exposed
* `GET /extraction-ready` — filings with a processed, chunked
  earnings-release exhibit, newest first; each row carries the exhibit
  filename, `document_key`, `chunk_count`, `ready_for_extraction`, plus
  the extraction lifecycle (`claim_extraction_status`,
  `claim_extracted_at`, `claim_extraction_error` — publicly redacted to
  the generic "Claim extraction failed. Retry later or contact the
  administrator." while the raw provider text stays only in Supabase and
  backend logs),
  `pending_grounded_claim_count`, `trusted_promoted_claim_count`, and
  `latest_brief_version` — the queue for manual grounded-claim extraction

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
* `POST /extraction-ready/{accession_number}/extract` — manual grounded
  Gemini extraction on the filing's processed exhibit; optional body
  `{"max_claims": 1–10}` (default 5, 422 outside range); 404 unknown
  filing, 400 not extraction-ready, 429 on Gemini quota/rate-limit, safe
  500 otherwise (no keys, stack traces, or raw provider responses); the
  only route that calls Gemini

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
  Save/Clear. Saved tokens are verified through `GET /admin/validate` and
  the indicator shows `connected` / `invalid token` / `not connected`
  (plus `checking…` / `unverified` transients). The token lives in browser
  session storage only (never committed, never in a `NEXT_PUBLIC_`
  variable) and is attached as `X-Admin-Token` to protected POSTs and the
  validate route only; a 401 surfaces as "Admin token missing or invalid."

Routes:

* `/` — cross-company overview from `GET /overview`: six stat cards
  (companies, filings tracked, extraction ready, pending review, trusted
  claims, stored briefs) + per-company status table (ticker → company
  page, extraction-ready count, trusted count, latest brief link, latest
  filing date) + latest-filings table
* `/companies/[ticker]` — company research page: name/ticker/CIK/business
  model header, four summary cards, latest-brief panel with "View latest
  brief" link, extraction-ready filings table with extraction badges,
  recent filings table; clean states for unknown tickers and missing
  briefs; the sidebar has a dynamic Companies section from
  `GET /companies` and ticker cells in filings tables link here
* `/filings` — feed with ticker/status/limit filters and status badges;
  the ticker list loads dynamically from `GET /companies` (with a static
  fallback if the endpoint fails)
* `/filings/[accessionNumber]` — full filing metadata, timestamps,
  processing error, document list with Storage flags, chunk count
* `/extraction-ready` — per-filing cards with exhibit filename, document
  key, chunk count, an exhibit badge plus a lifecycle trail
  (`not_started › pending_review › approved`, failed shown as a badge),
  pending/trusted claim counts, and latest brief version; admin-only
  **Extract Claims** button (requires a saved token, disabled while
  running) that calls the protected extract endpoint, shows a compact
  success note with a "Review drafted claims" link to `/review-queue`, a
  dedicated quota message on 429, and the redacted extraction error for
  failed filings; an admin-only **Promote reviewed claims** button appears
  when the filing is `pending_review` with zero grounded pending drafts —
  the terminal promotion that flips the filing to `approved` (the Review
  Queue can no longer trigger it because its per-filing group disappears
  once the last draft is reviewed); approved filings with a stored brief
  show a "View latest brief" link; an admin-only **Generate first brief**
  button appears for approved filings with trusted claims but no stored
  brief (calls `POST /briefs/generate` — no Swagger needed for the first
  version); accession numbers link to the filing detail page; clean empty
  state
* `/review-queue` — grounded pending claims grouped by filing; approve /
  edit-and-approve / reject with optional reviewer notes; per-filing
  "Promote reviewed claims for this filing" button (scoped promotion only —
  the frontend never calls global promotion); clean empty state
* `/briefs/latest/[ticker]` — company ticker tabs loaded from
  `GET /companies` (static fallback if it fails) navigate between all
  watched companies with the active ticker highlighted; brief metadata
  cards + rendered markdown; tickers without a stored brief render a clean
  empty state; "Generate new brief version" button refreshes to the new
  version

## Quantitative research terminal (Bundle A, complete)

Restores the quantitative depth of the original static dashboard as a live,
deterministic layer over Supabase. No AI, no external market-data provider.

### Audited static-data backfill

`src/static_dashboard_backfill.py` + `run_static_dashboard_backfill.py` +
`test_static_dashboard_backfill.py`:

* parses the `METRICS` (1,290 rows) and `VALUATIONS` (5 rows) JS arrays from a
  locally downloaded copy of the public static dashboard
  (`https://avyuktk17.github.io/semiconductor-research/`); the HTML is read
  from a temp path (`/tmp/semiconductor_dashboard.html`) and never committed
* idempotent, dry-run-by-default, writes only with `--confirm`
* AVGO `financial_metrics`: inserts only missing operating rows, scoped to the
  metric names already present for the other tickers (valuation-derived and
  empty-period rows excluded); existing reviewed rows for the other four
  tickers are never overwritten. **In practice AVGO's 252 operating rows were
  already present** (the live table already held the full audited dataset; an
  earlier "AVGO missing" reading was a PostgREST 1000-row pagination
  artifact), so the metrics step is a verified no-op
* `valuation_snapshots`: the 5 manually reviewed snapshots were inserted on
  the confirmed run; a rerun skips all 5 (idempotent). Source references,
  extraction methods, formulas, and manual-review flags are preserved
* never calls Gemini; no credentials printed

### Quantitative read endpoints (public, deterministic)

* `GET /metrics/{ticker}` — historical operating-metric series for one
  company (optional `metric_name` filter); returns metric/period counts,
  per-metric time series, and a latest-period summary. Valuation-derived rows
  excluded; ticker uppercased; 404 unknown ticker
* `GET /peers` — latest-period peer table for all five companies: operating
  fundamentals + valuation snapshot fields + deterministically computed
  multiples (EV/TTM revenue, EV/TTM operating income, price/TTM FCF, FCF
  yield). Honest `null` where inputs are missing; carries
  `valuation_is_live = false`, snapshot dates, a disclaimer, and per-ticker
  comparability notes (business model + debt measure)
* `GET /peers/trends?metric_name=&ticker=&limit=` — chart-ready per-ticker
  time series for one metric (optional single ticker / last N periods)
* `GET /valuation-snapshots` — the 5 manually reviewed snapshots, each tagged
  `is_live = false`, with snapshot dates and a disclaimer

Deterministic math lives in `src/quantitative.py` (period sorting, operating
filtering, series building, latest-period summary, multiple computation);
`compute_multiples` returns `None` for any missing or zero denominator. Tests:
`test_api_metrics.py`, `test_api_peers.py`, `test_api_valuation_snapshots.py`.

### Frontend quantitative pages

`recharts` is the only new dependency. The browser still talks only to the
API.

* `/peers` — peer-comparison terminal: ranked horizontal bar chart with a
  metric selector, full fundamentals + valuation table, comparability-note
  panel, a visible "Valuation snapshot as of 2026-06-04" badge, and the
  "not a live market feed" disclaimer
* `/companies/[ticker]` — extended deep dive: financial KPI cards (latest
  quarter + YoY), revenue / gross+operating margin / FCF-margin / R&D-intensity
  / TTM trend charts, a balance-sheet & cash-flow snapshot, and a valuation
  snapshot (badge + disclaimer), above the existing pipeline panels;
  degrades cleanly when fundamentals are unavailable
* `/` — overview now also shows market-leader cards (top revenue growth,
  highest gross margin, strongest FCF margin), a peer-fundamentals table, and
  a link to `/peers`
* shared helpers: `src/lib/format.ts` (null-safe USD/percent/multiple
  formatting, series merge), `src/components/charts.tsx` (themed recharts
  line/bar charts), `src/components/ValuationNote.tsx` (snapshot badge +
  disclaimer); sidebar nav gains a **Peer Comparison** link

Valuation figures are always presented as a dated, manually reviewed
point-in-time snapshot — never implied to be live. Next milestone: **Bundle B
— Evidence Explorer and professional report engine.**

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
`test_api_extraction_ready.py`, `test_process_pending_exhibits.py`
(worker processed / not-found / failed paths, idempotency, and proof that
grounded chunks and trusted claims survive reruns),
`test_exhibit_selection.py` (synthetic press-release-first ranking, no
network), `test_exhibit_repointing.py` (best-ranked upgrade + exact-match
reuse), `test_api_error_redaction.py` (no provider details in public
payloads), `test_claim_extraction_status.py`,
`test_ready_filing_extraction.py`, `test_promotion_lifecycle.py`
(scoped promotion approves exactly the fully reviewed filing),
`test_api_manual_extraction.py`
(auth, validation, 404/400/429/safe-500 mapping, and the
promotion-driven `approved` lifecycle), `test_api_company_detail.py`,
`test_api_overview.py` (totals consistent with per-company rows),
`test_api_admin_validate.py`, and `test_cleanup_legacy_claims.py`
(dry-run safety only — the destructive mode is never run by tests).
Every extraction test
monkeypatches the Gemini-backed extractor — automated tests never consume
free-tier quota. `test_api_briefs.py` is version-agnostic (analysts
generate new brief versions in production).
Write-endpoint tests supply a temporary admin token via the environment
(never printed),
insert clearly marked temporary rows and delete them in `finally` blocks;
real trusted claims and persisted briefs are never modified.
Frontend checks: `cd frontend && npm run lint && npm run build`.
Known cosmetic warning when importing TestClient:
`StarletteDeprecationWarning: Using httpx with starlette.testclient is
deprecated; install httpx2 instead.` — harmless, left as-is.

## Legacy cleanup script

`cleanup_legacy_claims.py` targets only `proposed_claims` rows with
`source_chunk_id` null **and** `review_status = "pending"` (drafts from the
pre-grounding extractor). Default invocation is a dry run that prints the
matching rows; deletion requires the explicit `--confirm` flag and is never
run by tests, deployment, or GitHub Actions. Deletes repeat the safety
predicates per row id, so a row reviewed in the meantime is left alone.

## Known limitations

* Two ungrounded legacy pending AVGO primary-document claims (ids 11, 12)
  remain in `proposed_claims`. They are excluded from the review queue,
  approval, promotion, and briefs by design. Remove them with
  `python cleanup_legacy_claims.py --confirm` when ready (dry run is safe
  to preview anytime).
* Auth is a single shared admin token — no user accounts, roles, or audit
  trail; suitable for the MVP only.
* 404-vs-400 mapping for workflow errors keys on `ValueError` message
  prefixes (documented as fragile; typed exceptions are the upgrade path).
* Gemini quota detection is string-marker-based ("429", "quota", "rate")
  and could misclassify rare non-quota errors as 429.
* Exhibit selection is filename-heuristic; unusual naming conventions may
  need new narrow patterns (INTC, the last holdout, resolved without one —
  it has 2 extraction-ready filings and a v1 brief).
* The deployed API serves Gemini extraction only on explicit admin action;
  brief content quality still depends on analyst review rigor.

## Live URLs

* Dashboard (Vercel): <https://earnings-intelligence-os.vercel.app>
* API (Render): <https://earnings-intelligence-os-api.onrender.com>

## Status

Level 3 product polish is complete: all five companies (AVGO, NVDA, AMD,
QCOM, INTC) have extraction-ready exhibits, trusted human-reviewed claims,
and at least one persisted brief; the dashboard covers the full workflow
end to end (monitor → exhibits → extraction → review → promotion → briefs)
with cross-company and per-company views.

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
